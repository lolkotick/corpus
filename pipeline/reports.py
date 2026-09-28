"""Все отчёты для курсовой одной командой.

    python -m pipeline reports [--no-llm] [--no-docx]
    python scripts/build_reports.py            # то же самое
    make reports                               # то же самое (Linux/macOS)

Порядок: описание корпуса → оценка по эталону → сравнение методов
выравнивания → анализ ошибок → апробация → копии отчётов в Word
(reports/docx/). Отчёт, для которого нет данных (нет gold.json или CSV теста),
содержит понятное сообщение — сборка остальных отчётов не прерывается.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pipeline.charts import plural
from pipeline.config import Config

NO_DATA = "**Данных для"
NO_METRICS = "**Метрики не рассчитаны"


@dataclass
class Step:
    name: str
    report: str
    status: str = ""
    seconds: float = 0.0
    files: int = 0


def build_all(config: Config, use_llm: bool = True, docx: bool = True,
              log: Callable[[str], None] = print) -> list[Step]:
    from pipeline import approbation, compare_aligners, corpus_report, error_analysis, evaluate

    out = config.path("reports")
    gold = config.path("gold")
    root = config.root
    methods = [m for m in compare_aligners.METHODS if use_llm or m != "llm"]
    steps: list[tuple[Step, Callable[[], tuple[int, list[Path]]]]] = [
        (Step("Описание корпуса", "corpus.md"),
         lambda: corpus_report.run(config.path("output"), out, root)),
        (Step("Оценка по эталону", "evaluation.md"),
         lambda: evaluate.run(config.path("output") / "corpus.json", gold, out, root)),
        (Step("Сравнение методов выравнивания", "aligners.md"),
         lambda: compare_aligners.run(config, gold, out, methods)),
        (Step("Анализ ошибок", "errors.md"), lambda: error_analysis.run(gold, out, root)),
        (Step("Апробация", "approbation.md"),
         lambda: approbation.run([config.path("approbation")], out, root)),
    ]
    done: list[Step] = []
    for step, action in steps:
        log(f"▶ {step.name}")
        start = time.perf_counter()
        code, files = action()
        step.seconds = time.perf_counter() - start
        step.files = len(files)
        report = out / step.report
        if code != 0:
            step.status = "ошибка"
        elif report.exists() and NO_DATA in (text := report.read_text(encoding="utf-8")):
            step.status = "нет данных — в отчёте инструкция"
        elif report.exists() and NO_METRICS in text:
            step.status = "готово без метрик качества (нет эталона)"
        else:
            step.status = "готово"
        done.append(step)

    if docx:
        from pipeline.docx_export import convert

        log("▶ Копии отчётов в Word")
        start = time.perf_counter()
        converted = [convert(out / s.report, out / "docx" / f"{Path(s.report).stem}.docx")
                     for s in done if (out / s.report).exists()]
        done.append(Step("Копии в Word (reports/docx)", "docx", "готово",
                         time.perf_counter() - start, len(converted)))

    log("")
    width = max(len(s.name) for s in done)
    for s in done:
        files = plural(s.files, "файл", "файла", "файлов")
        log(f"  {s.name:<{width}}  {s.status} ({s.files} {files}, {s.seconds:.1f} с)")
    return done
