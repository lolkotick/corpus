"""Журнал сборки logs/build_report.md — материал для описания апробации в курсовой."""

from __future__ import annotations

import platform
import sys
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pipeline.build import BuildResult
    from pipeline.config import Config

METHOD_NAMES = {
    "gale_church": "Гейл–Чёрч (длина предложений)",
    "labse": "LaBSE-эмбеддинги (алгоритм Bertalign)",
    "bertalign": "пакет bertalign (LaBSE)",
}
PACKAGES = ("razdel", "pysbd", "jieba", "pymorphy3", "spacy", "en_core_web_sm", "numpy",
            "anthropic", "sentence-transformers", "bertalign")


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "—"


def _table(header: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return lines


def write_report(path: Path, result: BuildResult, config: Config) -> None:
    stats = result.stats
    totals = stats.get("totals", {})
    alignment = stats.get("alignment", {})
    llm = result.llm
    method_name = METHOD_NAMES.get(result.alignment_method, result.alignment_method)
    lines: list[str] = [
        "# Журнал сборки корпуса",
        "",
        f"- Дата сборки (UTC): **{result.started_at}**",
        f"- Общее время: **{result.total_seconds:.2f} с**",
        f"- Метод выравнивания: **{method_name}**",
        f"- Порог низкого alignment_score: {alignment.get('low_score_threshold')}",
        f"- Текстов: **{totals.get('texts', 0)}**, пар (троек предложений): "
        f"**{totals.get('pairs', 0)}**",
        "",
        "## Этапы",
        "",
        *_table(["Этап", "Время, с", "Результат"],
                [[s.name, f"{s.seconds:.2f}", s.detail] for s in result.stages]),
        "",
        "## Тексты",
        "",
        *_table(
            ["Текст", "Уровень", "Предложений EN / ZH / RU", "Пар", "Выравнивание",
             "Типы соответствий", "Средний score", "Низкий score"],
            [[f"{t['title']} (`{t['id']}`)", t["level"],
              f"{t['sentences']['en']} / {t['sentences']['zh']} / {t['sentences']['ru']}",
              t["pairs"], t["mode"],
              ", ".join(f"{k}: {v}" for k, v in sorted(t["types"].items(),
                                                       key=lambda kv: -kv[1])),
              t["mean_score"], t["low"]] for t in result.text_rows],
        ),
        "",
        "## Выравнивание",
        "",
        f"- Средний alignment_score: {alignment.get('mean')}, медиана: {alignment.get('median')}",
        f"- Пар ниже порога: {alignment.get('low_count')}",
        "- Типы соответствий (EN-ZH-RU): "
        + ", ".join(f"{k} — {v}" for k, v in alignment.get("types", {}).items()),
        "",
        "## Разметка",
        "",
        *_table(
            ["Явление", "Язык", "Метод", "Элементов"],
            [
                ["Артикли a / an / the", "EN", result.annotation_methods.get("en", ""),
                 totals.get("annotations", {}).get("article", 0)],
                ["Счётные слова 量词", "ZH", result.annotation_methods.get("zh", ""),
                 totals.get("annotations", {}).get("classifier", 0)],
                ["Падежи существительных", "RU", result.annotation_methods.get("ru", ""),
                 totals.get("annotations", {}).get("case", 0)],
            ],
        ),
        "",
        "- Артикли: " + ", ".join(
            f"{k} — {v}" for k, v in stats.get("articles", {}).get("counts", {}).items()),
        f"- Разных 量词: {totals.get('distinct_classifiers', 0)}; без существительного "
        f"(эллипсис): {stats.get('classifier_elliptical', 0)}",
        "- Падежи: " + ", ".join(
            f"{c['label']} — {c['sing'] + c['plur']}" for c in stats.get("cases", [])),
        f"- Спорных элементов разметки: {totals.get('disputed', 0)} "
        f"(из них неоднозначных падежей: {totals.get('ambiguous_cases', 0)})",
        "",
        "## Ручная проверка",
        "",
        f"- Правок из data/manual/overrides.json применено: {result.manual.get('applied', 0)}, "
        f"удалено пар: {result.manual.get('deleted', 0)}, пропущено: "
        f"{result.manual.get('skipped', 0)}",
        "- Статусы пар: " + ", ".join(f"{k} — {v}" for k, v in totals.get("status", {}).items()),
        "",
        "## LLM-проверка",
        "",
        f"- Модель: {llm.model} (режим: "
        f"{'запросы к API' if llm.enabled else 'только сохранённые ответы'})",
        f"- Кандидатов на проверку: {llm.candidates}",
        f"- Проверено пар: {llm.checked} (из сохранённых ответов: {llm.from_cache})",
        f"- Предложено правок: **{llm.suggestions}** (выравнивание: {llm.alignment_flags}, "
        f"разметка: {llm.annotation_flags})",
        f"- Ошибок API: {llm.errors}",
    ]
    if llm.reason:
        lines.append(f"- Примечание: {llm.reason}")
    lines += ["", "## Предупреждения", ""]
    lines += [f"- {w}" for w in result.warnings] or ["- нет"]
    lines += [
        "",
        "## Окружение",
        "",
        f"- Python {sys.version.split()[0]} ({platform.system()} {platform.machine()})",
        "- Пакеты: " + ", ".join(f"{p} {_version(p)}" for p in PACKAGES),
        f"- Конфигурация: `{Path('pipeline/config.yaml')}`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
