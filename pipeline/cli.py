"""Командная строка pipeline.

    python -m pipeline build                 # полная сборка корпуса
    python -m pipeline build --no-llm        # без запросов к LLM
    python -m pipeline import-csv FILE.csv   # импорт ручных правок и пересборка
    python -m pipeline check                 # проверить входные тексты без сборки
    python -m pipeline evaluate              # оценка разметки по data/gold/gold.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from pipeline.config import load_config


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
    )
    # На Windows консоль может быть не в UTF-8 — не падаем на иероглифах.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _print_summary(result) -> None:
    totals = result.stats["totals"]
    print()
    print(f"Готово за {result.total_seconds:.1f} с")
    print(f"  Текстов: {totals['texts']}, пар: {totals['pairs']}, "
          f"метод выравнивания: {result.alignment_method}")
    ann = totals["annotations"]
    print(f"  Артиклей: {ann['article']}, 量词: {ann['classifier']}, "
          f"существительных RU: {ann['case']}")
    print(f"  LLM: проверено {result.llm.checked}, предложено правок {result.llm.suggestions}"
          + (f" ({result.llm.reason})" if result.llm.reason else ""))
    if result.warnings:
        print(f"  Предупреждений: {len(result.warnings)} — см. logs/build_report.md")


def cmd_build(args: argparse.Namespace) -> int:
    from pipeline.build import run_build

    config = load_config(Path(args.config) if args.config else None)
    result = run_build(config, use_llm=not args.no_llm)
    _print_summary(result)
    return 0


def cmd_import_csv(args: argparse.Namespace) -> int:
    from pipeline.build import run_build
    from pipeline.manual import ManualImportError, Overrides, import_csv

    config = load_config(Path(args.config) if args.config else None)
    corpus_path = config.path("output") / "corpus.json"
    if not corpus_path.exists():
        print("Сначала соберите корпус: python -m pipeline build", file=sys.stderr)
        return 1
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    overrides_path = config.path("manual") / "overrides.json"
    overrides = Overrides.load(overrides_path)
    try:
        counts, problems = import_csv(Path(args.file), corpus, overrides)
    except ManualImportError as exc:
        print(f"Ошибка импорта: {exc}", file=sys.stderr)
        return 1
    for problem in problems:
        print(f"  ! {problem}")
    print(f"Строк: {counts['rows']}; изменён текст: {counts['changed']}, "
          f"изменён статус/комментарий: {counts['checked']}, удалено: {counts['deleted']}, "
          f"без изменений: {counts['unchanged']}")
    if args.dry_run:
        print("Пробный запуск (--dry-run): правки не сохранены.")
        return 0
    overrides.save(overrides_path)
    print(f"Правки сохранены в {overrides_path.relative_to(config.root)}; пересобираю корпус…")
    result = run_build(config, use_llm=not args.no_llm)
    _print_summary(result)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from pipeline.segment import segment_paragraphs
    from pipeline.sources import LANGS, SourceError, discover_texts, read_text

    config = load_config(Path(args.config) if args.config else None)
    ok = True
    for text_dir in discover_texts(config.path("raw")):
        try:
            raw = read_text(text_dir)
        except SourceError as exc:
            print(f"✗ {exc}")
            ok = False
            continue
        counts = {lang: sum(len(p) for p in segment_paragraphs(raw.paragraphs[lang], lang,
                                                               config.get("segmentation", {})))
                  for lang in LANGS}
        paragraphs = {lang: len(raw.paragraphs[lang]) for lang in LANGS}
        mark = "✓" if len(set(paragraphs.values())) == 1 else "△"
        print(f"{mark} {raw.meta.id} [{raw.meta.level}] «{raw.meta.title}»: абзацев "
              + "/".join(str(paragraphs[lang]) for lang in LANGS)
              + ", предложений " + "/".join(str(counts[lang]) for lang in LANGS))
    return 0 if ok else 1


def cmd_evaluate(args: argparse.Namespace) -> int:
    from pipeline.evaluate import run

    config = load_config(Path(args.config) if args.config else None)
    gold = Path(args.gold) if args.gold else config.path("gold")
    out = Path(args.out) if args.out else config.path("reports")
    corpus = Path(args.corpus) if args.corpus else config.path("output") / "corpus.json"
    code, files = run(corpus, gold, out, config.root)
    for path in files:
        print(f"  → {path}")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline",
                                     description="Pipeline учебного корпуса EN/ZH/RU")
    parser.add_argument("--config", help="путь к config.yaml (по умолчанию pipeline/config.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true", help="подробный вывод")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="собрать корпус")
    p_build.add_argument("--no-llm", action="store_true",
                         help="не обращаться к API (сохранённые ответы всё равно применяются)")
    p_build.set_defaults(func=cmd_build)

    p_import = sub.add_parser("import-csv", help="импортировать правки из CSV и пересобрать")
    p_import.add_argument("file", help="CSV-файл (экспорт corpus.csv после правки)")
    p_import.add_argument("--dry-run", action="store_true", help="только показать изменения")
    p_import.add_argument("--no-llm", action="store_true")
    p_import.set_defaults(func=cmd_import_csv)

    p_check = sub.add_parser("check", help="проверить входные тексты")
    p_check.set_defaults(func=cmd_check)

    p_eval = sub.add_parser("evaluate", help="оценить разметку по золотому стандарту")
    p_eval.add_argument("--gold", help="файл эталона (по умолчанию data/gold/gold.json)")
    p_eval.add_argument("--corpus", help="corpus.json (по умолчанию web/public/data/corpus.json)")
    p_eval.add_argument("--out", help="папка отчётов (по умолчанию reports)")
    p_eval.set_defaults(func=cmd_evaluate)

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return int(args.func(args))
