"""Таблицы для отчётов: Markdown (для чтения на GitHub) и CSV (для Excel и Word).

CSV пишется в UTF-8 с BOM, разделитель — точка с запятой, десятичная запятая:
так файл сразу правильно открывается в русском Excel, а оттуда таблица
копируется в Word без перенастройки.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

Cell = str | int | float | None


def cell(value: Cell, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, float):
        return f"{value:.{digits}f}".replace(".", ",")
    return str(value)


def md_table(head: Sequence[str], rows: Sequence[Sequence[Cell]], digits: int = 3,
             align_right_from: int = 1) -> str:
    def esc(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(esc(h) for h in head) + " |",
             "|" + "|".join("---:" if i >= align_right_from else "---"
                            for i in range(len(head))) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(esc(cell(v, digits)) for v in row) + " |")
    return "\n".join(lines)


def write_csv(path: Path, head: Sequence[str], rows: Sequence[Sequence[Cell]],
              digits: int = 4) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(head)
        for row in rows:
            writer.writerow(["" if v is None else cell(v, digits) for v in row])
    return path
