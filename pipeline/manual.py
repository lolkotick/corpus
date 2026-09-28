"""Ручная проверка: импорт правок из CSV и их применение при каждой сборке.

Правки хранятся в data/manual/overrides.json отдельно от автоматического
результата, поэтому пересборка корпуса их не затирает. Для каждой правки
запоминается исходный (автоматический) английский сегмент: если после
изменения входных текстов сегмент с тем же id стал другим, правка не
применяется, а в журнал пишется предупреждение.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUSES = ("auto", "checked", "corrected")
STATUS_ALIASES = {
    "": None,
    "auto": "auto", "авто": "auto", "автоматически": "auto",
    "checked": "checked", "проверено": "checked", "ok": "checked", "ок": "checked",
    "corrected": "corrected", "исправлено": "corrected",
    "delete": "delete", "удалить": "delete", "deleted": "delete",
}
EDITABLE_TEXT = ("en", "zh", "ru")


class ManualImportError(ValueError):
    pass


def normalize_status(value: str | None) -> str | None:
    key = (value or "").strip().lower()
    if key not in STATUS_ALIASES:
        raise ManualImportError(
            f"неизвестный статус «{value}»: допустимо auto / checked / corrected / delete "
            "(или по-русски: авто / проверено / исправлено / удалить)"
        )
    return STATUS_ALIASES[key]


@dataclass
class Overrides:
    pairs: dict[str, dict[str, Any]] = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def load(cls, path: Path) -> Overrides:
        if not path.exists():
            return cls(path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(pairs=dict(data.get("pairs", {})), path=path)

    def save(self, path: Path | None = None) -> Path:
        target = path or self.path
        if target is None:
            raise ValueError("не указан путь для overrides.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "pairs": dict(sorted(self.pairs.items())),
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8")
        return target


def apply_overrides(
    records: list[dict[str, Any]], overrides: Overrides
) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    """Применить правки к записям (до разметки). Возвращает записи, счётчики, предупреждения."""
    warnings: list[str] = []
    stats = {"applied": 0, "deleted": 0, "skipped": 0}
    by_id = {r["id"]: r for r in records}
    for pair_id, change in overrides.pairs.items():
        record = by_id.get(pair_id)
        if record is None:
            warnings.append(f"ручная правка {pair_id}: такой пары больше нет — пропущена")
            stats["skipped"] += 1
            continue
        base_en = change.get("base", {}).get("en")
        if base_en is not None and base_en.strip() != record["en"].strip():
            warnings.append(
                f"ручная правка {pair_id}: автоматический сегмент изменился после пересборки "
                "— правка не применена, проверьте пару заново"
            )
            stats["skipped"] += 1
            continue
        if change.get("deleted"):
            record["_deleted"] = True
            stats["deleted"] += 1
            continue
        for lang in EDITABLE_TEXT:
            if lang in change:
                record[lang] = change[lang]
        if change.get("status"):
            record["status"] = change["status"]
        if "comment" in change:
            record["comment"] = change["comment"]
        stats["applied"] += 1
    kept = [r for r in records if not r.pop("_deleted", False)]
    return kept, stats, warnings


def _read_csv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ManualImportError(
            f"{path.name}: файл не в кодировке UTF-8. В Excel сохраняйте как "
            "«CSV UTF-8 (разделитель — запятая)», иначе иероглифы будут потеряны."
        ) from exc
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delimiter))
    if not rows:
        raise ManualImportError(f"{path.name}: в файле нет строк")
    missing = {"id", "status", "en", "zh", "ru"} - set(rows[0].keys())
    if missing:
        raise ManualImportError(f"{path.name}: нет колонок {', '.join(sorted(missing))}")
    return rows


def import_csv(
    csv_path: Path, corpus: dict[str, Any], overrides: Overrides
) -> tuple[dict[str, int], list[str]]:
    """Сравнить CSV с текущим corpus.json и записать отличия в overrides."""
    rows = _read_csv(csv_path)
    current = {p["id"]: p for p in corpus.get("pairs", [])}
    counts = {"rows": len(rows), "changed": 0, "checked": 0, "deleted": 0, "unchanged": 0}
    problems: list[str] = []

    for line_no, row in enumerate(rows, start=2):
        pair_id = (row.get("id") or "").strip()
        if not pair_id:
            continue
        pair = current.get(pair_id)
        if pair is None:
            problems.append(f"строка {line_no}: пары {pair_id} нет в корпусе — пропущена")
            continue
        try:
            status = normalize_status(row.get("status"))
        except ManualImportError as exc:
            problems.append(f"строка {line_no} ({pair_id}): {exc}")
            continue

        existing = overrides.pairs.get(pair_id, {})
        # Без прежней правки текущий сегмент в corpus.json и есть автоматический.
        base = existing.get("base") or {"en": pair["en"]}
        change: dict[str, Any] = {k: v for k, v in existing.items() if k != "base"}

        if status == "delete":
            overrides.pairs[pair_id] = {"deleted": True, "base": base}
            counts["deleted"] += 1
            continue

        text_changed = False
        for lang in EDITABLE_TEXT:
            new_value = (row.get(lang) or "").strip()
            if new_value and new_value != pair[lang].strip():
                change[lang] = new_value
                text_changed = True
        comment = (row.get("comment") or "").strip()
        if comment != (pair.get("comment") or ""):
            change["comment"] = comment

        if status in ("checked", "corrected"):
            change["status"] = status
        elif text_changed:
            change["status"] = "corrected"
        elif status == "auto" and pair.get("status") != "auto":
            change["status"] = "auto"

        if change == {k: v for k, v in existing.items() if k != "base"}:
            counts["unchanged"] += 1
            continue
        overrides.pairs[pair_id] = {**change, "base": base}
        if text_changed:
            counts["changed"] += 1
        else:
            counts["checked"] += 1
    return counts, problems
