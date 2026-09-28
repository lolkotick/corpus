"""Чтение исходных текстов: data/raw/<text_id>/{en,zh,ru}.txt + meta.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LANGS = ("en", "zh", "ru")
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
DEFAULT_REGISTER = "учебный"
_BLANK_LINE = re.compile(r"\n\s*\n")


class SourceError(ValueError):
    """Ошибка во входных данных (понятное сообщение для пользователя)."""


@dataclass
class TextMeta:
    id: str
    title: str
    source: str
    topic: str
    level: str
    title_ru: str = ""
    title_zh: str = ""
    author: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        data = {
            "id": self.id,
            "title": self.title,
            "title_ru": self.title_ru,
            "title_zh": self.title_zh,
            "source": self.source,
            "topic": self.topic,
            "level": self.level,
            "author": self.author,
            "register": DEFAULT_REGISTER,
        }
        data.update(self.extra)
        return data

    @property
    def register(self) -> str:
        return self.extra.get("register") or DEFAULT_REGISTER


@dataclass
class RawText:
    meta: TextMeta
    # Абзацы каждого языка (после нормализации пробелов).
    paragraphs: dict[str, list[str]]
    # Для импортированных источников — сведения о каждом абзаце-тройке (units.jsonl).
    units: list[dict[str, Any]] | None = None


def normalize_text(text: str) -> str:
    """Нормализация без изменения содержания: BOM, переводы строк, пробелы."""
    text = text.replace("﻿", "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(" ", " ").replace("\t", " ")
    return text.strip()


def split_paragraphs(text: str, lang: str) -> list[str]:
    """Абзацы разделяются пустой строкой; переносы внутри абзаца склеиваются."""
    joiner = "" if lang == "zh" else " "
    paragraphs = []
    for block in _BLANK_LINE.split(normalize_text(text)):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if lines:
            paragraph = joiner.join(lines)
            paragraphs.append(re.sub(r" {2,}", " ", paragraph))
    return paragraphs


def read_meta(text_dir: Path) -> TextMeta:
    meta_path = text_dir / "meta.json"
    if not meta_path.exists():
        raise SourceError(f"{text_dir.name}: нет файла meta.json")
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SourceError(f"{meta_path}: некорректный JSON ({exc})") from exc

    missing = [key for key in ("title", "source", "topic", "level") if not raw.get(key)]
    if missing:
        raise SourceError(f"{meta_path}: не заполнены поля {', '.join(missing)}")
    level = str(raw["level"]).upper()
    if level not in LEVELS:
        raise SourceError(f"{meta_path}: уровень «{raw['level']}» не из списка {LEVELS}")

    known = {"title", "title_ru", "title_zh", "source", "topic", "level", "author", "id"}
    return TextMeta(
        id=text_dir.name,
        title=str(raw["title"]),
        title_ru=str(raw.get("title_ru", "")),
        title_zh=str(raw.get("title_zh", "")),
        source=str(raw["source"]),
        topic=str(raw["topic"]),
        level=level,
        author=str(raw.get("author", "")),
        extra={k: str(v) for k, v in raw.items() if k not in known},
    )


def read_text(text_dir: Path) -> RawText:
    meta = read_meta(text_dir)
    paragraphs: dict[str, list[str]] = {}
    for lang in LANGS:
        path = text_dir / f"{lang}.txt"
        if not path.exists():
            raise SourceError(f"{text_dir.name}: нет файла {lang}.txt")
        paragraphs[lang] = split_paragraphs(path.read_text(encoding="utf-8-sig"), lang)
        if not paragraphs[lang]:
            raise SourceError(f"{text_dir.name}: файл {lang}.txt пустой")
    return RawText(meta=meta, paragraphs=paragraphs, units=read_units(text_dir, paragraphs))


def read_units(text_dir: Path, paragraphs: dict[str, list[str]]) -> list[dict[str, Any]] | None:
    """units.jsonl импортированного источника: строка на абзац (тройку предложений)."""
    path = text_dir / "units.jsonl"
    if not path.exists():
        return None
    units = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            units.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SourceError(f"{path}: строка {n} — некорректный JSON ({exc})") from exc
    counts = {len(paragraphs[lang]) for lang in LANGS}
    if counts != {len(units)}:
        raise SourceError(f"{path}: {len(units)} строк, а абзацев в {text_dir.name}/*.txt — "
                          + "/".join(str(len(paragraphs[lang])) for lang in LANGS)
                          + "; повторите импорт")
    return units


def discover_texts(raw_dir: Path) -> list[Path]:
    """Папки текстов в алфавитном порядке (папки, начинающиеся с «_» или «.», пропускаются)."""
    if not raw_dir.exists():
        raise SourceError(f"Папка с текстами не найдена: {raw_dir}")
    return sorted(
        p for p in raw_dir.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))
    )
