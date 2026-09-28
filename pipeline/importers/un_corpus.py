"""Импорт фрагмента Параллельного корпуса ООН v1.0 (EN/ZH/RU).

    python -m pipeline import un [--limit 2000] [--from ПАПКА_ИЛИ_АРХИВ] [--max-lines 200000]

Корпус распространяется на официальной странице
https://www.un.org/dgacm/en/content/uncorpus/download. Импортёр читает файлы,
выровненные построчно для всех шести языков: полностью выровненный подкорпус
(UNv1.0.6way.en / .zh / .ru) или наборы для проверки (UNv1.0.devset.*,
UNv1.0.testset.*), а также любые три файла en.txt / zh.txt / ru.txt с одинаковым
числом строк. Можно указать папку или архив .tar.gz — нужные файлы будут
извлечены в кэш (data/sources/un_corpus/).

Второй вариант — попарные выгрузки того же корпуса на OPUS (UNPC v1.0, формат
Moses: en-zh.txt.zip и en-ru.txt.zip с файлами UNPC.en-zh.en / .zh и
UNPC.en-ru.en / .ru). Они выровнены отдельно для каждой пары языков, поэтому
тройка собирается по совпадающему английскому предложению: берётся первое
вхождение в паре EN–ZH и первое — в паре EN–RU.

Порядок поиска данных: --from; data/sources/un_corpus/; importers.un_corpus.url
(архив с тремя файлами); importers.un_corpus.opus (архивы OPUS). Если скачать
не удалось, импортёр объясняет, какие файлы и куда положить вручную.

Из первых max_lines строк отбираются тройки, прошедшие фильтры (длина,
дубликаты, хотя бы одно из целевых явлений), затем случайная выборка limit
троек (по умолчанию 2000) с фиксированным seed.
"""

from __future__ import annotations

import html
import io
import re
import tarfile
import zipfile
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from itertools import islice
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
    han_chars,
    select,
    write_text,
)

LANGS = ("en", "zh", "ru")
DOWNLOAD_PAGE = "https://www.un.org/dgacm/en/content/uncorpus/download"
CITATION = ("Ziemski, M., Junczys-Dowmunt, M., Pouliquen, B. The United Nations Parallel "
            "Corpus v1.0 // Proceedings of LREC 2016. Portorož, 2016. P. 3530–3534.")

META = SourceMeta(
    text_id="un_corpus",
    title="United Nations Parallel Corpus v1.0 (excerpt)",
    title_ru="Параллельный корпус ООН v1.0 (фрагмент)",
    title_zh="联合国平行语料库 v1.0（节选）",
    source="United Nations Parallel Corpus v1.0 — официальные документы ООН "
           "(https://www.un.org/dgacm/en/content/uncorpus)",
    source_url="https://www.un.org/dgacm/en/content/uncorpus",
    license="документы ООН, находящиеся в общественном достоянии; условия использования "
            "корпуса — на официальной странице",
    license_url="https://www.un.org/dgacm/en/content/uncorpus",
    attribution="Источник — Организация Объединённых Наций; ссылка на корпус: " + CITATION,
    register="официальный",
    topic="Официальные документы ООН",
)

MANUAL = f"""Как положить файлы корпуса ООН вручную:
  1. Откройте {DOWNLOAD_PAGE} и скачайте полностью выровненный подкорпус (UNv1.0.6way)
     или наборы для проверки (dev/test sets), где есть английский, китайский и русский.
  2. Распакуйте и положите в data/sources/un_corpus/ три файла с одинаковым числом строк:
     *.en, *.zh, *.ru (например, UNv1.0.testset.en / .zh / .ru) — или en.txt, zh.txt, ru.txt.
     Или положите туда же попарные файлы OPUS UNPC v1.0 (https://opus.nlpl.eu/UNPC/corpus/version/UNPC):
     архивы en-zh.txt.zip и en-ru.txt.zip (распаковывать не нужно)
     либо файлы UNPC.en-zh.en/.zh и UNPC.en-ru.en/.ru.
  3. Запустите: python -m pipeline import un  (или укажите путь: --from ПАПКА_ИЛИ_АРХИВ)."""
OPUS_PAIRS = ("en-zh", "en-ru")



def _wanted(name: str) -> bool:
    return name.endswith((".en", ".zh", ".ru")) or Path(name).name in ("en.txt", "zh.txt",
                                                                       "ru.txt")


def _extract(archive: Path, target: Path) -> Path:
    """Извлечь из архива (.tar.* или .zip) файлы *.en / *.zh / *.ru (и en.txt / zh.txt / ru.txt)."""
    target.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        try:
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    out = target / Path(info.filename).name
                    if info.is_dir() or not _wanted(info.filename) or out.exists():
                        continue
                    with zf.open(info) as src, open(out, "wb") as fh:
                        while chunk := src.read(1 << 20):
                            fh.write(chunk)
        except (zipfile.BadZipFile, OSError) as exc:
            raise ImportFailed(f"не удалось прочитать архив {archive}: {exc}") from exc
        return target
    try:
        with tarfile.open(archive, "r:*") as tar:
            members = [m for m in tar.getmembers() if m.isfile() and _wanted(m.name)]
            for member in members:
                out = target / Path(member.name).name
                if out.exists():
                    continue
                handle = tar.extractfile(member)
                assert handle is not None
                with open(out, "wb") as fh:
                    while chunk := handle.read(1 << 20):
                        fh.write(chunk)
    except (tarfile.TarError, OSError) as exc:
        raise ImportFailed(f"не удалось прочитать архив {archive}: {exc}") from exc
    return target


def find_sets(directory: Path) -> list[tuple[str, dict[str, Path]]]:
    """Наборы параллельных файлов: {основа: {язык: путь}}; сначала полные наборы 6way."""
    sets: dict[str, dict[str, Path]] = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if path.name in ("en.txt", "zh.txt", "ru.txt"):
            sets.setdefault("txt", {})[path.name[:2]] = path
        elif path.suffix in (".en", ".zh", ".ru") and not path.stem.endswith(OPUS_PAIRS):
            sets.setdefault(path.stem, {})[path.suffix[1:]] = path
    complete = [(stem, files) for stem, files in sets.items() if set(files) >= set(LANGS)]
    complete.sort(key=lambda item: (not item[0].endswith("6way"), item[0]))
    return complete


_ENDS = {"en": ".!?;:", "ru": ".!?;:", "zh": "。！？；：.!?;:"}
_OPENERS = "\"“«‘'(["


def is_sentence(text: str, lang: str) -> bool:
    """Законченное предложение, а не заголовок, пункт таблицы или обрывок: начинается с
    заглавной буквы (для ZH — с иероглифа), кончается знаком конца предложения и не набрано
    прописными целиком."""
    text = text.strip().rstrip("\"”»’')]")
    letters = [ch for ch in text if ch.isalpha()]
    if not text or not letters or text[-1] not in _ENDS[lang]:
        return False
    if lang != "zh" and sum(ch.isupper() for ch in letters) / len(letters) >= 0.5:
        return False
    first = text.lstrip(_OPENERS)[:1]
    return bool(first) and (first.isupper() if lang != "zh" else han_chars(first) == 1)


def sentences_only(units: Iterable[Unit], stats: ImportStats) -> Iterator[Unit]:
    for unit in units:
        if all(is_sentence(getattr(unit, lang), lang) for lang in LANGS):
            yield unit
        else:
            stats.fragments += 1


def iter_units(sets: list[tuple[str, dict[str, Path]]], max_lines: int) -> Iterator[Unit]:
    for stem, files in sets:
        with open(files["en"], encoding="utf-8-sig") as fe, \
                open(files["zh"], encoding="utf-8-sig") as fz, \
                open(files["ru"], encoding="utf-8-sig") as fr:
            for n, lines in enumerate(islice(zip(fe, fz, fr, strict=False), max_lines), start=1):
                en, zh, ru = (clean(line) for line in lines)
                if en and zh and ru:
                    yield Unit(en, zh, ru, origin={"source": "un_corpus", "file": stem,
                                                   "line": n})


# Файл OPUS: обычный файл или член zip-архива (архив не распаковывается — он большой).
Member = Path | tuple[Path, str]


def find_opus(directory: Path) -> dict[str, tuple[Member, Member]] | None:
    """Попарные файлы OPUS: {"en-zh": (…en, …zh), "en-ru": (…en, …ru)} — распакованные
    UNPC.en-zh.en/.zh или архивы en-zh.txt.zip."""
    found: dict[str, tuple[Member, Member]] = {}
    for pair in OPUS_PAIRS:
        other = pair.split("-")[1]
        for en in sorted(directory.glob(f"*{pair}.en")):
            partner = en.with_suffix(f".{other}")
            if partner.exists():
                found[pair] = (en, partner)
                break
        else:
            for archive in sorted(directory.glob(f"*{pair}*.zip")):
                try:
                    with zipfile.ZipFile(archive) as zf:
                        names = zf.namelist()
                except (zipfile.BadZipFile, OSError):
                    continue
                en_name = next((n for n in names if n.endswith(f"{pair}.en")), None)
                other_name = next((n for n in names if n.endswith(f"{pair}.{other}")), None)
                if en_name and other_name:
                    found[pair] = ((archive, en_name), (archive, other_name))
                    break
    return found if len(found) == len(OPUS_PAIRS) else None


@contextmanager
def _lines(member: Member) -> Iterator[Iterator[str]]:
    if isinstance(member, Path):
        with open(member, encoding="utf-8-sig") as fh:
            yield fh
        return
    archive, name = member
    with zipfile.ZipFile(archive) as zf, zf.open(name) as raw:
        yield io.TextIOWrapper(raw, encoding="utf-8-sig")


_SPACE_BEFORE = re.compile(r" +([.,;:!?%)\]])")
_SPACE_AFTER = re.compile(r"([(\[]) +")
_POSSESSIVE = re.compile(r"(\w) '(s|t|re|ve|ll|d|m)\b")  # It 's → It's, don 't → don't
_PLURAL_POSSESSIVE = re.compile(r"(\ws) ' (?=\w)")  # respondents ' lawyers → respondents'


def opus_text(line: str) -> str:
    """Строка Moses-файла OPUS: сущности (&quot; &apos; &amp;) → символы; убираются пробелы,
    которые токенизация Moses ставит перед знаками препинания, после открывающей скобки и
    вокруг апострофа (It 's → It's). Другие изменения текста не вносятся."""
    text = clean(html.unescape(line))
    text = _PLURAL_POSSESSIVE.sub(r"\1' ", _POSSESSIVE.sub(r"\1'\2", text))
    return _SPACE_AFTER.sub(r"\1", _SPACE_BEFORE.sub(r"\1", text))


def iter_opus_units(pairs: dict[str, tuple[Member, Member]], max_lines: int,
                    stats: ImportStats | None = None) -> Iterator[Unit]:
    """Тройки по совпадающему английскому предложению в парах EN–ZH и EN–RU.

    Английская строка, которая встречается в файле больше одного раза (типовые заголовки,
    формулы), пропускается: её переводы могут относиться к разным документам.
    """
    zh_of: dict[str, tuple[int, str]] = {}
    repeated: set[str] = set()
    en_src, zh_src = pairs["en-zh"]
    with _lines(en_src) as fe, _lines(zh_src) as fz:
        for n, (en, zh) in enumerate(islice(zip(fe, fz, strict=False), max_lines), start=1):
            key = opus_text(en)
            if not key:
                continue
            if key in zh_of:
                repeated.add(key)
            else:
                zh_of[key] = (n, opus_text(zh))
    en_src, ru_src = pairs["en-ru"]
    ru_of: dict[str, tuple[int, str]] = {}
    with _lines(en_src) as fe, _lines(ru_src) as fr:
        for n, (en, ru) in enumerate(islice(zip(fe, fr, strict=False), max_lines), start=1):
            key = opus_text(en)
            if key not in zh_of:
                continue
            if key in ru_of:
                repeated.add(key)
            else:
                ru_of[key] = (n, opus_text(ru))
    if stats is not None:
        stats.notes.append(f"пропущено английских строк, повторяющихся в файлах: "
                           f"{len(repeated & ru_of.keys())}")
    for key, (ru_line, ru) in sorted(ru_of.items(), key=lambda item: zh_of[item[0]][0]):
        zh_line, zh = zh_of[key]
        if key in repeated or not zh or not ru:
            continue
        yield Unit(key, zh, ru, origin={"source": "un_corpus", "file": "OPUS UNPC v1.0",
                                        "line": zh_line, "line_en_ru": ru_line})


def locate(source: Path | None, cache_dir: Path, config: dict[str, Any]) -> Path:
    """Папка с файлами корпуса: --from, кэш data/sources/un_corpus или скачивание по url."""
    if source is not None:
        if not source.exists():
            raise ImportFailed(f"{source} не найден.\n{MANUAL}")
        if source.is_file():
            if source.suffix == ".zip" and source.parent.is_dir() and find_opus(source.parent):
                return source.parent
            return _extract(source, cache_dir)
        return source
    if cache_dir.exists() and (find_sets(cache_dir) or find_opus(cache_dir)):
        return cache_dir
    url = str(config.get("url") or "")
    if url:
        archive = download(url, cache_dir / url.rsplit("/", 1)[-1])
        return _extract(archive, cache_dir)
    opus = config.get("opus") or {}
    if all(opus.get(pair) for pair in OPUS_PAIRS):
        for pair in OPUS_PAIRS:
            link = str(opus[pair])
            download(link, cache_dir / link.rsplit("/", 1)[-1], timeout=300)
        return cache_dir
    raise ImportFailed(f"файлы корпуса ООН не найдены в {cache_dir}.\n{MANUAL}")


def run(raw_dir: Path, cache_dir: Path, config: dict[str, Any], limit: int | None = None,
        seed: int | None = None, source: Path | None = None, max_lines: int | None = None,
        require_phenomenon: bool = True,
        thresholds: Sequence[float] = DEFAULT_THRESHOLDS) -> tuple[Path, ImportStats]:
    stats = ImportStats()
    try:
        folder = locate(source, cache_dir, config)
    except ImportFailed as exc:
        if "Как положить" in str(exc):
            raise
        raise ImportFailed(f"{exc}\n{MANUAL}") from exc
    sets = find_sets(folder)
    opus = None if sets else find_opus(folder)
    if not sets and not opus:
        raise ImportFailed(f"в {folder} нет трёх параллельных файлов *.en / *.zh / *.ru "
                           f"и попарных файлов OPUS.\n{MANUAL}")
    lines = int(max_lines if max_lines is not None else config.get("max_lines", 3_000_000))
    filters = Filters.from_config(config.get("filters"), require_phenomenon)
    units: Iterable[Unit] = iter_units(sets, lines) if sets else \
        iter_opus_units(opus or {}, lines, stats)
    if config.get("sentences_only", True):
        units = sentences_only(units, stats)
    chosen = select(units, filters,
                    int(limit if limit is not None else config.get("limit", 2000)),
                    int(seed if seed is not None else config.get("seed", 2026)), stats,
                    order_key=lambda u: (u.origin["file"], u.origin["line"]))
    stats.notes.append("файлы: " + (", ".join(stem for stem, _ in sets) if sets else
                                     "OPUS UNPC v1.0 (en-zh + en-ru, тройки по английскому)"))
    path = write_text(raw_dir, META, chosen, thresholds)
    stats.written = len(chosen)
    return path, stats
