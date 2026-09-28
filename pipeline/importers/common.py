"""Общее для импортёров: фильтры, проверка целевых явлений и запись в data/raw.

Импортированный источник записывается как обычный текст корпуса
(data/raw/<text_id>/{en,zh,ru}.txt + meta.json), но каждая тройка предложений —
отдельный абзац. Поэтому pipeline выравнивает тройки независимо друг от друга,
а сведения о каждой тройке (ID и авторы предложений, лицензия, уровень) лежат в
units.jsonl — строка на абзац — и попадают в corpus.json как поле pair.origin.
"""

from __future__ import annotations

import bz2
import gzip
import io
import json
import random
import re
import statistics
import tarfile
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from pipeline.difficulty import DEFAULT_THRESHOLDS, LEVELS, estimate

LANGS = ("en", "zh", "ru")
_WORD = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)
_HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_ARTICLE = re.compile(r"\b(?:a|an|the)\b", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


class ImportFailed(RuntimeError):
    """Данные не удалось скачать или прочитать; сообщение объясняет, что сделать."""


@dataclass
class Unit:
    """Тройка предложений из источника и сведения о её происхождении."""

    en: str
    zh: str
    ru: str
    origin: dict[str, Any]
    level: str = ""
    difficulty: float = 0.0

    def texts(self) -> dict[str, str]:
        return {"en": self.en, "zh": self.zh, "ru": self.ru}


@dataclass
class SourceMeta:
    text_id: str
    title: str
    title_ru: str
    title_zh: str
    source: str
    source_url: str
    license: str
    license_url: str
    attribution: str
    register: str
    topic: str
    author: str = ""
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class Filters:
    """Длина в словах (EN/RU) и в иероглифах (ZH): (минимум, максимум) включительно."""

    en_words: tuple[int, int] = (3, 25)
    ru_words: tuple[int, int] = (3, 25)
    zh_chars: tuple[int, int] = (4, 40)
    require_phenomenon: bool = True

    @classmethod
    def from_config(cls, cfg: Mapping[str, Any] | None,
                    require_phenomenon: bool = True) -> Filters:
        cfg = cfg or {}
        base = cls()

        def pair(key: str, default: tuple[int, int]) -> tuple[int, int]:
            lo, hi = cfg.get(key, default)
            return int(lo), int(hi)

        return cls(pair("en_words", base.en_words), pair("ru_words", base.ru_words),
                   pair("zh_chars", base.zh_chars), require_phenomenon)


@dataclass
class ImportStats:
    candidates: int = 0
    fragments: int = 0  # строки-заголовки и обрывки (отбрасываются до подсчёта кандидатов)
    too_short_or_long: int = 0
    duplicates: int = 0
    no_phenomenon: int = 0
    kept: int = 0
    written: int = 0
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        skipped = (f"пропущено заголовков и фрагментов {self.fragments}; "
                   if self.fragments else "")
        return (f"{skipped}кандидатов {self.candidates}; "
                f"отброшено: длина {self.too_short_or_long}, "
                f"дубликаты {self.duplicates}, без целевых явлений {self.no_phenomenon}; "
                f"прошло фильтры {self.kept}; записано {self.written}")


# ─── Нормализация и фильтры ───────────────────────────────────────────────


def clean(text: str) -> str:
    """Одна строка без лишних пробелов (перенос строки разделил бы тройку на абзацы)."""
    return _SPACES.sub(" ", text.replace("　", " ")).strip()


def words(text: str) -> int:
    return len(_WORD.findall(text))


def han_chars(text: str) -> int:
    return len(_HAN.findall(text))


def length_ok(unit: Unit, filters: Filters) -> bool:
    ranges = ((words(unit.en), filters.en_words), (words(unit.ru), filters.ru_words),
              (han_chars(unit.zh), filters.zh_chars))
    return all(lo <= n <= hi for n, (lo, hi) in ranges)


def dedupe_key(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.lower().replace("ё", "е")).strip()


@cache
def _classifier_pattern() -> re.Pattern[str]:
    from pipeline.annotate.zh import DEFAULT_DEMONSTRATIVES, build_pattern, load_classifiers
    from pipeline.config import ROOT

    classifiers = load_classifiers(ROOT / "pipeline" / "resources" / "zh_classifiers.tsv")
    return build_pattern(classifiers, DEFAULT_DEMONSTRATIVES)


def has_article(en: str) -> bool:
    return bool(_ARTICLE.search(en))


def has_classifier(zh: str) -> bool:
    return bool(_classifier_pattern().search(zh))


def has_oblique_noun(ru: str) -> bool:
    """Существительное в косвенном падеже (по наиболее вероятному разбору pymorphy3)."""
    from pipeline.annotate.ru import get_morph

    morph = get_morph()
    for word in _WORD.findall(ru):
        parse = morph.parse(word)[0]
        if parse.tag.POS == "NOUN" and parse.tag.case not in (None, "nomn") \
                and parse.score >= 0.5:
            return True
    return False


def phenomena(unit: Unit) -> dict[str, bool]:
    return {"article": has_article(unit.en), "classifier": has_classifier(unit.zh),
            "case": has_oblique_noun(unit.ru)}


def select(units: Iterable[Unit], filters: Filters, limit: int, seed: int,
           stats: ImportStats, order_key: Callable[[Unit], Any] | None = None) -> list[Unit]:
    """Фильтры → удаление дубликатов → случайная выборка limit троек (seed) в исходном порядке."""
    seen: dict[str, set[str]] = {lang: set() for lang in LANGS}
    kept: list[Unit] = []
    for unit in units:
        stats.candidates += 1
        if not length_ok(unit, filters):
            stats.too_short_or_long += 1
            continue
        keys = {lang: dedupe_key(getattr(unit, lang)) for lang in LANGS}
        if any(keys[lang] in seen[lang] for lang in LANGS):
            stats.duplicates += 1
            continue
        if filters.require_phenomenon and not any(phenomena(unit).values()):
            stats.no_phenomenon += 1
            continue
        for lang in LANGS:
            seen[lang].add(keys[lang])
        kept.append(unit)
    stats.kept = len(kept)
    if limit > 0 and len(kept) > limit:
        chosen = set(random.Random(seed).sample(range(len(kept)), limit))
        kept = [u for i, u in enumerate(kept) if i in chosen]
    if order_key is not None:
        kept.sort(key=order_key)
    return kept


# ─── Запись в data/raw ────────────────────────────────────────────────────


def write_text(raw_dir: Path, meta: SourceMeta, units: Sequence[Unit],
               thresholds: Sequence[float] = DEFAULT_THRESHOLDS) -> Path:
    """Записать источник как текст корпуса (перезаписывает прежний импорт)."""
    if not units:
        raise ImportFailed("после фильтров не осталось ни одной тройки — ничего не записано")
    for unit in units:
        d = estimate(unit.texts(), thresholds)
        unit.level, unit.difficulty = d.level, d.score
    ranks = sorted(LEVELS.index(u.level) for u in units)
    median_level = LEVELS[int(statistics.median_low(ranks))]

    target = raw_dir / meta.text_id
    target.mkdir(parents=True, exist_ok=True)
    for lang in LANGS:
        body = "\n\n".join(clean(getattr(u, lang)) for u in units)
        (target / f"{lang}.txt").write_text(body + "\n", encoding="utf-8")
    payload = {
        "title": meta.title,
        "title_ru": meta.title_ru,
        "title_zh": meta.title_zh,
        "source": meta.source,
        "source_url": meta.source_url,
        "license": meta.license,
        "license_url": meta.license_url,
        "attribution": meta.attribution,
        "register": meta.register,
        "topic": meta.topic,
        "level": median_level,
        "level_method": "медиана оценок сложности троек (pipeline/difficulty.py)",
        "author": meta.author,
        "units": str(len(units)),
        **meta.extra,
    }
    (target / "meta.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    with open(target / "units.jsonl", "w", encoding="utf-8") as fh:
        for unit in units:
            fh.write(json.dumps({**unit.origin, "level": unit.level,
                                 "difficulty": unit.difficulty}, ensure_ascii=False) + "\n")
    return target


# ─── Скачивание и чтение архивов ──────────────────────────────────────────


def download(url: str, target: Path, timeout: float = 60.0) -> Path:
    """Скачать файл (если его ещё нет в кэше)."""
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response, open(tmp, "wb") as fh:
            while chunk := response.read(1 << 20):
                fh.write(chunk)
    except (OSError, ValueError) as exc:
        tmp.unlink(missing_ok=True)
        raise ImportFailed(f"не удалось скачать {url}: {exc}") from exc
    tmp.replace(target)
    return target


def open_text(path: Path, member_suffix: str | None = None) -> Iterator[str]:
    """Строки файла: .bz2, .gz, .tar.bz2/.tar.gz (член архива с окончанием member_suffix)
    или обычный текст."""
    name = path.name
    if ".tar" in name:
        mode = "r:bz2" if name.endswith(".bz2") else "r:gz" if name.endswith(".gz") else "r:"
        with tarfile.open(path, mode) as tar:
            member = next((m for m in tar.getmembers()
                           if m.isfile() and (member_suffix is None
                                              or m.name.endswith(member_suffix))), None)
            if member is None:
                raise ImportFailed(f"{name}: в архиве нет файла *{member_suffix}")
            handle = tar.extractfile(member)
            assert handle is not None
            yield from io.TextIOWrapper(handle, encoding="utf-8")
        return
    if name.endswith(".bz2"):
        with bz2.open(path, "rt", encoding="utf-8") as fh:
            yield from fh
        return
    if name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            yield from fh
        return
    with open(path, encoding="utf-8-sig") as fh:
        yield from fh


def find_file(directory: Path, patterns: Sequence[str]) -> Path | None:
    for pattern in patterns:
        found = sorted(directory.glob(pattern))
        if found:
            return found[0]
    return None
