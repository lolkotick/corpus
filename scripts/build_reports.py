"""Собрать все отчёты для курсовой: python scripts/build_reports.py [--no-llm] [--no-docx].

Обёртка над `python -m pipeline reports` — удобно запускать из корня проекта
на Windows без make. Подробности — в reports/README.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["reports", *sys.argv[1:]]))
