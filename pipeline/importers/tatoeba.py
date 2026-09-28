"""Импорт троек EN–ZH–RU из открытых выгрузок Tatoeba (https://tatoeba.org/downloads).

    python -m pipeline import tatoeba [--limit 500] [--seed 2026] [--from-dir ПАПКА]

Файлы (адреса — в config.yaml, importers.tatoeba.files):
- {eng,cmn,rus}_sentences_detailed.tsv.bz2 — предложения языка:
  id, язык, текст, имя автора, дата добавления, дата изменения (через табуляцию);
- links.tar.bz2 → links.csv — пары «предложение — перевод» (id, id);
- sentences_CC0.tar.bz2 (необязательно) — id предложений под CC0 1.0.

Отбор: английское предложение, у которого есть прямые переводы на китайский
(cmn, только упрощённые иероглифы — текст не меняется при переводе OpenCC t2s) и
на русский. Если переводов несколько, берётся перевод с наименьшим id (стабильно
при повторном импорте). Дальше — общие фильтры (длина, дубликаты, хотя бы одно из
целевых явлений) и случайная выборка limit троек с фиксированным seed.

Для каждого предложения сохраняются id, автор и лицензия: CC BY 2.0 FR требует
указывать автора (см. страницу «Источники» на сайте).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from pipeline.difficulty import DEFAULT_THRESHOLDS
from pipeline.importers.common import (
    Filters,
    ImportFailed,
    ImportStats,
    SourceMeta,
    Unit,
    clean,
    download,
    find_file,
    han_chars,
    open_text,
    select,
    write_text,
)

LICENSE_BY = "CC BY 2.0 FR"
LICENSE_CC0 = "CC0 1.0"
TATOEBA_LANG = {"en": "eng", "zh": "cmn", "ru": "rus"}
SENTENCE_URL = "https://tatoeba.org/sentences/show/{id}"
DEFAULT_FILES = {
    "eng": "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences_detailed.tsv.bz2",
    "cmn": "https://downloads.tatoeba.org/exports/per_language/cmn/cmn_sentences_detailed.tsv.bz2",
    "rus": "https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences_detailed.tsv.bz2",
    "links": "https://downloads.tatoeba.org/exports/links.tar.bz2",
    "cc0": "https://downloads.tatoeba.org/exports/sentences_CC0.tar.bz2",
}
LOCAL_PATTERNS = {
    "eng": ["eng_sentences_detailed.tsv*", "eng_sentences_detailed*"],
    "cmn": ["cmn_sentences_detailed.tsv*", "cmn_sentences_detailed*"],
    "rus": ["rus_sentences_detailed.tsv*", "rus_sentences_detailed*"],
    "links": ["links.tar*", "links.csv*"],
    "cc0": ["sentences_CC0.tar*", "sentences_CC0.csv*"],
}

META = SourceMeta(
    text_id="tatoeba",
    title="Tatoeba: sentences with translations",
    title_ru="Tatoeba: предложения с переводами",
    title_zh="Tatoeba：例句及其翻译",
    source="Tatoeba — открытая база предложений и переводов, составляемая участниками "
           "(https://tatoeba.org)",
    source_url="https://tatoeba.org",
    license="CC BY 2.0 FR (часть предложений — CC0 1.0)",
    license_url="https://tatoeba.org/terms_of_use",
    attribution="Для каждого предложения указаны автор (имя пользователя Tatoeba) и номер "
                "предложения со ссылкой на tatoeba.org",
    register="бытовой",
    topic="Бытовые предложения на разные темы",
)


@dataclass
class Sentence:
    id: int
    text: str
    author: str


@cache
def _t2s():  # type: ignore[no-untyped-def]
    import opencc

    return opencc.OpenCC("t2s")


def is_simplified(text: str) -> bool:
    """Упрощённые иероглифы: текст не меняется при переводе «традиционные → упрощённые»."""
    return han_chars(text) > 0 and _t2s().convert(text) == text


def read_sentences(lines: Iterable[str], keep: set[int] | None = None) -> Iterator[Sentence]:
    """Строки *_sentences_detailed: id, язык, текст, автор, дата добавления, дата изменения."""
    for line in lines:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        sid = int(parts[0])
        if keep is not None and sid not in keep:
            continue
        author = parts[3] if len(parts) > 3 and parts[3] not in ("\\N", "") else ""
        yield Sentence(sid, clean(parts[2]), author)


def read_links(lines: Iterable[str]) -> Iterator[tuple[int, int]]:
    for line in lines:
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].strip().isdigit():
            yield int(parts[0]), int(parts[1])


def read_ids(lines: Iterable[str]) -> set[int]:
    return {int(line.split("\t", 1)[0]) for line in lines if line[:1].isdigit()}


class Files:
    """Где взять файлы: локальная папка (--from-dir) или скачивание в кэш."""

    def __init__(self, config: dict[str, Any], cache_dir: Path, from_dir: Path | None) -> None:
        self.urls = {**DEFAULT_FILES, **(config.get("files") or {})}
        self.cache_dir = cache_dir
        self.from_dir = from_dir

    def path(self, key: str, required: bool = True) -> Path | None:
        if self.from_dir is not None:
            found = find_file(self.from_dir, LOCAL_PATTERNS[key])
            if found is None and required:
                raise ImportFailed(
                    f"в {self.from_dir} нет файла {LOCAL_PATTERNS[key][0]} — скачайте его со "
                    f"страницы https://tatoeba.org/downloads ({self.urls[key]})")
            return found
        url = self.urls[key]
        try:
            return download(url, self.cache_dir / url.rsplit("/", 1)[-1])
        except ImportFailed:
            if required:
                raise
            return None

    def lines(self, key: str, required: bool = True) -> Iterator[str] | None:
        path = self.path(key, required)
        if path is None:
            return None
        return open_text(path, "links.csv" if key == "links" else ".csv")


def build_units(files: Files, stats: ImportStats) -> list[Unit]:
    # 1. Китайские предложения (только упрощённые иероглифы).
    cmn_lines = files.lines("cmn")
    assert cmn_lines is not None
    cmn = {s.id: s for s in read_sentences(cmn_lines) if is_simplified(s.text)}
    if not cmn:
        raise ImportFailed("в выгрузке cmn нет предложений на упрощённых иероглифах")
    # 2. Кто переводит китайские предложения (первый проход по связям).
    zh_of: dict[int, list[int]] = {}
    links = files.lines("links")
    assert links is not None
    for a, b in read_links(links):
        if b in cmn:
            zh_of.setdefault(a, []).append(b)
    # 3. Английские предложения с китайским переводом.
    eng_lines = files.lines("eng")
    assert eng_lines is not None
    eng = {s.id: s for s in read_sentences(eng_lines, keep=set(zh_of))}
    # 4. Все переводы этих английских предложений (второй проход) и русские предложения.
    partners: dict[int, list[int]] = {}
    links = files.lines("links")
    assert links is not None
    for a, b in read_links(links):
        if a in eng:
            partners.setdefault(a, []).append(b)
    wanted = {b for bs in partners.values() for b in bs}
    rus_lines = files.lines("rus")
    assert rus_lines is not None
    rus = {s.id: s for s in read_sentences(rus_lines, keep=wanted)}
    # 5. Лицензии: по умолчанию CC BY 2.0 FR, список CC0 — если удалось получить.
    cc0_lines = files.lines("cc0", required=False)
    cc0 = read_ids(cc0_lines) if cc0_lines is not None else set()
    if cc0_lines is None:
        stats.notes.append("список CC0 недоступен — все предложения помечены CC BY 2.0 FR "
                           "(это не нарушает условий: указание автора сохраняется)")

    def described(lang: str, s: Sentence) -> dict[str, Any]:
        return {"id": s.id, "lang": TATOEBA_LANG[lang], "author": s.author,
                "license": LICENSE_CC0 if s.id in cc0 else LICENSE_BY,
                "url": SENTENCE_URL.format(id=s.id)}

    units: list[Unit] = []
    for eid in sorted(eng):
        zh_ids = sorted(z for z in set(zh_of.get(eid, [])) if z in cmn)
        ru_ids = sorted(r for r in set(partners.get(eid, [])) if r in rus)
        if not zh_ids or not ru_ids:
            continue
        e, z, r = eng[eid], cmn[zh_ids[0]], rus[ru_ids[0]]
        units.append(Unit(e.text, z.text, r.text, origin={
            "source": "tatoeba",
            "en": described("en", e), "zh": described("zh", z), "ru": described("ru", r),
        }))
    return units


def run(raw_dir: Path, cache_dir: Path, config: dict[str, Any], limit: int | None = None,
        seed: int | None = None, from_dir: Path | None = None,
        require_phenomenon: bool = True,
        thresholds: Sequence[float] = DEFAULT_THRESHOLDS) -> tuple[Path, ImportStats]:
    stats = ImportStats()
    files = Files(config, cache_dir, from_dir)
    units = build_units(files, stats)
    filters = Filters.from_config(config.get("filters"), require_phenomenon)
    chosen = select(units, filters, int(limit if limit is not None else config.get("limit", 500)),
                    int(seed if seed is not None else config.get("seed", 2026)), stats,
                    order_key=lambda u: u.origin["en"]["id"])
    path = write_text(raw_dir, META, chosen, thresholds)
    stats.written = len(chosen)
    return path, stats
