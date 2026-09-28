"""Оценка качества автоматической разметки по золотому стандарту.

    python -m pipeline evaluate [--gold data/gold/gold.json] [--out reports]

Сравнивает текущий web/public/data/corpus.json с эталоном, который эксперт
составил в режиме «Проверка», и считает precision, recall и F1 отдельно для
выравнивания (EN–ZH, EN–RU), артиклей, 量词 и падежей; для падежей — ещё матрицу
ошибок. Результат: reports/evaluation.md, CSV-таблицы и графики PNG.

Если эталона нет или в нём нет ни одной полностью проверенной пары, скрипт
пишет понятное сообщение и не выводит никаких чисел.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline import charts
from pipeline.export import CASE_ORDER, CASE_SHORT
from pipeline.gold import (
    LANGS,
    TARGETS,
    Gold,
    GoldError,
    TruthItem,
    alignment_truth,
    is_stale,
    load_gold,
    pair_complete,
    truth_items,
)
from pipeline.metrics import AlignmentScore, Counts, format_ci, link_label, score_alignment
from pipeline.tables import md_table, write_csv

PHENOMENON = {"en": "Артикли (EN)", "zh": "量词 (ZH)", "ru": "Падежи (RU)"}
PHENOMENON_PLAIN = {"en": "Артикли", "zh": "Счётные слова", "ru": "Падежи"}
ATTRIBUTE = {"en": "вершина", "zh": "существительное", "ru": "падеж"}
TARGET_LABEL = {"zh": "EN–ZH", "ru": "EN–RU"}
NONE_CASE = "—"
VERDICT_LABEL = {"correct": "верно", "wrong": "ошибка", "corrected": "исправлено"}


class NoGoldData(Exception):
    """Эталона нет или он пуст: отчёт с числами строить не из чего."""


@dataclass
class LangScore:
    detection: Counts = field(default_factory=Counts)
    full: Counts = field(default_factory=Counts)
    lemma_ok: int = 0
    lemma_total: int = 0
    confusion: Counter[tuple[str, str]] = field(default_factory=Counter)
    items: list[dict[str, Any]] = field(default_factory=list)
    pairs: int = 0


@dataclass
class Evaluation:
    gold: Gold
    corpus_generated_at: str
    sample_total: int
    complete: int
    partial: int
    stale: list[str]
    used: list[str]
    alignment: dict[str, AlignmentScore]
    verdicts: dict[str, Counter[str]]
    langs: dict[str, LangScore]


def _norm(value: str | None) -> str:
    return (value or "").strip().lower().replace("ё", "е")


def _attribute(lang: str, pred: dict[str, Any]) -> str:
    if lang == "ru":
        return str(pred.get("case", ""))
    head = pred.get("head")
    return head.get("text", "") if head else ""


def _truth_attribute(lang: str, truth: TruthItem) -> str:
    return truth.case if lang == "ru" else truth.head


def score_lang(lang: str, pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> LangScore:
    """pairs — (пара эталона, та же пара текущего корпуса)."""
    score = LangScore(pairs=len(pairs))
    for gold_pair, corpus_pair in pairs:
        truth, _ = truth_items(gold_pair, lang)
        truth_by_key = {t.key: t for t in truth}
        pred_by_key = {(a["start"], a["end"]): a for a in corpus_pair["annotations"][lang]}
        text = corpus_pair[lang]
        for key in sorted(set(truth_by_key) | set(pred_by_key)):
            t = truth_by_key.get(key)
            p = pred_by_key.get(key)
            pred_attr = _attribute(lang, p) if p else ""
            gold_attr = _truth_attribute(lang, t) if t else ""
            if t and p:
                score.detection.tp += 1
                attr_ok = _norm(pred_attr) == _norm(gold_attr)
                if attr_ok:
                    score.full.tp += 1
                else:
                    score.full.fp += 1
                    score.full.fn += 1
                outcome = "верно" if attr_ok else "неверный признак"
                if lang == "ru":
                    score.confusion[(gold_attr, pred_attr)] += 1
                    if t.lemma:
                        score.lemma_total += 1
                        score.lemma_ok += _norm(p.get("lemma")) == _norm(t.lemma)
            elif p:
                score.detection.fp += 1
                score.full.fp += 1
                outcome = "ложное срабатывание"
                if lang == "ru":
                    score.confusion[(NONE_CASE, pred_attr)] += 1
            else:
                assert t is not None
                score.detection.fn += 1
                score.full.fn += 1
                outcome = "пропуск"
                if lang == "ru":
                    score.confusion[(gold_attr, NONE_CASE)] += 1
            start, end = key
            score.items.append({
                "pair_id": corpus_pair["id"],
                "lang": lang,
                "start": start,
                "end": end,
                "text": text[start:end],
                "outcome": outcome,
                "auto": pred_attr if p else "",
                "gold": gold_attr if t else "",
                "gold_source": t.source if t else "",
                "auto_lemma": p.get("lemma", "") if (p and lang == "ru") else "",
                "gold_lemma": t.lemma if (t and lang == "ru") else "",
            })
    return score


def corpus_links(corpus: dict[str, Any]) -> dict[str, dict[str, list[tuple[tuple[int, ...],
                                                                          tuple[int, ...]]]]]:
    """Группы предложений текущего корпуса: links[lang][text_id]."""
    links: dict[str, dict[str, list[tuple[tuple[int, ...], tuple[int, ...]]]]] = {
        t: {} for t in TARGETS
    }
    for pair in corpus["pairs"]:
        for lang in TARGETS:
            links[lang].setdefault(pair["text_id"], []).append(
                (tuple(pair["sentences"]["en"]), tuple(pair["sentences"][lang]))
            )
    return links


def evaluate(corpus: dict[str, Any], gold: Gold) -> Evaluation:
    by_id = {p["id"]: p for p in corpus["pairs"]}
    complete = [p for p in gold.pairs if pair_complete(p)]
    if not complete:
        raise NoGoldData(
            "в файле эталона нет ни одной полностью проверенной пары — "
            "закончите проверку хотя бы одной пары в режиме «Проверка»"
        )
    if "sentences" not in corpus["pairs"][0]:
        raise GoldError("corpus.json собран старой версией pipeline (нет номеров предложений) "
                        "— пересоберите корпус: python -m pipeline build")
    stale = [p["id"] for p in complete if is_stale(p, by_id.get(p["id"]))]
    used = [p for p in complete if p["id"] not in stale]
    if not used:
        raise NoGoldData(
            "все проверенные пары устарели: после проверки корпус пересобран и текст пар "
            "изменился. Проверьте эти пары заново"
        )

    links = corpus_links(corpus)
    alignment = {}
    verdicts: dict[str, Counter[str]] = {}
    for lang in TARGETS:
        truths = [alignment_truth(p, lang) for p in used]
        alignment[lang] = score_alignment(truths, links[lang])
        verdicts[lang] = Counter(t.verdict for t in truths)
    pairs = [(p, by_id[p["id"]]) for p in used]
    langs = {lang: score_lang(lang, pairs) for lang in LANGS}
    sample = gold.sample_ids
    partial = sum(1 for p in gold.pairs if not pair_complete(p))
    return Evaluation(
        gold=gold,
        corpus_generated_at=str(corpus.get("generated_at", "")),
        sample_total=len(sample),
        complete=len(complete),
        partial=partial,
        stale=stale,
        used=[p["id"] for p in used],
        alignment=alignment,
        verdicts=verdicts,
        langs=langs,
    )


# ─── Вывод ────────────────────────────────────────────────────────────────


def metric_rows(ev: Evaluation) -> list[list[Any]]:
    rows: list[list[Any]] = []

    def add(task: str, level: str, c: Counts) -> None:
        rows.append([task, level, c.tp, c.fp, c.fn, c.precision, c.recall, c.f1,
                     format_ci(c.precision_ci()), format_ci(c.recall_ci())])

    for lang in TARGETS:
        add(f"Выравнивание {TARGET_LABEL[lang]}", "строгая (группы предложений)",
            ev.alignment[lang].strict)
        add(f"Выравнивание {TARGET_LABEL[lang]}", "мягкая (пары предложений)",
            ev.alignment[lang].lax)
    for lang in LANGS:
        add(PHENOMENON[lang], "обнаружение", ev.langs[lang].detection)
        add(PHENOMENON[lang], f"обнаружение + {ATTRIBUTE[lang]}", ev.langs[lang].full)
    return rows


METRIC_HEAD = ["Задача", "Уровень", "TP", "FP", "FN", "Точность (P)", "Полнота (R)", "F1",
               "95% ДИ точности", "95% ДИ полноты"]


def confusion_matrix(score: LangScore) -> tuple[list[str], list[str], list[list[int]]]:
    """Строки — эталон, столбцы — автоматическая разметка; «—» — нет пометки."""
    present = {c for pair in score.confusion for c in pair if c != NONE_CASE}
    cases = [c for c in CASE_ORDER if c in present] + sorted(present - set(CASE_ORDER))
    rows = [*cases, NONE_CASE]
    cols = [*cases, NONE_CASE]
    matrix = [[score.confusion.get((r, c), 0) for c in cols] for r in rows]
    return rows, cols, matrix


def case_label(code: str) -> str:
    return "нет" if code == NONE_CASE else CASE_SHORT.get(code, code)


def write_outputs(ev: Evaluation, out: Path, root: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    rows = metric_rows(ev)
    files.append(write_csv(out / "evaluation_metrics.csv", METRIC_HEAD, rows))

    ru = ev.langs["ru"]
    r_labels, c_labels, matrix = confusion_matrix(ru)
    files.append(write_csv(
        out / "evaluation_case_confusion.csv",
        ["эталон \\ автоматически", *[case_label(c) for c in c_labels]],
        [[case_label(r), *row] for r, row in zip(r_labels, matrix, strict=True)],
    ))
    item_rows = [[i["pair_id"], i["lang"], i["text"], i["start"], i["end"], i["outcome"],
                  i["auto"], i["gold"], i["gold_source"], i["auto_lemma"], i["gold_lemma"]]
                 for lang in LANGS for i in ev.langs[lang].items]
    files.append(write_csv(
        out / "evaluation_items.csv",
        ["pair_id", "язык", "слово", "начало", "конец", "итог", "автоматически", "эталон",
         "источник эталона", "лемма (авто)", "лемма (эталон)"],
        item_rows,
    ))
    align_rows = [[p.pair_id, TARGET_LABEL[p.lang], VERDICT_LABEL[p.verdict],
                   link_label(p.auto, p.lang),
                   "; ".join(link_label(g, p.lang) for g in p.gold),
                   "; ".join(link_label(m, p.lang) for m in p.method),
                   {True: "да", False: "нет", None: "неизвестно"}[p.ok]]
                  for lang in TARGETS for p in ev.alignment[lang].per_pair]
    files.append(write_csv(
        out / "evaluation_alignment.csv",
        ["pair_id", "языки", "вердикт", "автоматически (при проверке)", "эталон",
         "текущий корпус", "совпадает с эталоном"],
        align_rows,
    ))

    categories = [f"Выравн.\n{TARGET_LABEL[t]}" for t in TARGETS] + [
        PHENOMENON_PLAIN[lang] for lang in LANGS]
    counts = [ev.alignment[t].strict for t in TARGETS] + [ev.langs[lang].full for lang in LANGS]
    files.append(charts.grouped_bars(
        out / "evaluation_prf.png",
        categories,
        dict(zip(charts.PRF_LABELS, ([c.precision for c in counts], [c.recall for c in counts],
                                     [c.f1 for c in counts]), strict=True)),
        title=f"Качество автоматической разметки (эталон: {len(ev.used)} "
              f"{charts.plural(len(ev.used), 'пара', 'пары', 'пар')})",
    ))
    if any(any(row) for row in matrix):
        files.append(charts.heatmap(
            out / "evaluation_case_confusion.png",
            matrix,
            [case_label(r) for r in r_labels],
            [case_label(c) for c in c_labels],
            title="Падежи: матрица ошибок",
            xlabel="автоматическая разметка",
            ylabel="эталон",
        ))
    report = render_report(ev, rows, (r_labels, c_labels, matrix), files, out, root)
    path = out / "evaluation.md"
    path.write_text(report, encoding="utf-8")
    return [path, *files]


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def render_report(ev: Evaluation, rows: list[list[Any]],
                  confusion: tuple[list[str], list[str], list[list[int]]],
                  files: list[Path], out: Path, root: Path) -> str:
    gold = ev.gold
    lines = ["# Оценка качества автоматической разметки", ""]
    if gold.synthetic:
        lines += ["> **ВНИМАНИЕ: синтетические данные.** Файл эталона помечен как тестовый "
                  "(`synthetic: true`), числа ниже ничего не говорят о качестве корпуса.", ""]
    lines += [
        f"- Отчёт построен: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Эталон: `{_rel(gold.path, root)}`"
        + (f", эксперт: {gold.annotator}" if gold.annotator else "")
        + f", обновлён {gold.data.get('updated_at', '—')}",
        f"- Корпус: сборка {ev.corpus_generated_at}; эталон составлялся по сборке "
        f"{gold.data.get('corpus', {}).get('generated_at', '—')}",
        f"- Выборка: {ev.sample_total} пар, seed {gold.data.get('sample', {}).get('seed', '—')}, "
        "пропорционально по текстам",
        f"- Проверено полностью: **{ev.complete}**; начато, но не закончено: {ev.partial}"
        f"; устарели после пересборки: {len(ev.stale)}; вошло в расчёт: **{len(ev.used)}**",
        "",
    ]
    if ev.stale:
        lines += ["Устаревшие пары (текст изменился после пересборки или пары больше нет; "
                  f"в расчёт не вошли): {', '.join(ev.stale)}", ""]
    lines += ["## Сводная таблица", "", md_table(METRIC_HEAD, rows, digits=3,
                                                  align_right_from=2), ""]
    lines += [
        "TP — верные автоматические пометки, FP — лишние или неверные, FN — пропущенные. "
        "Точность (precision) — доля верных среди автоматических пометок; полнота (recall) — "
        "доля найденных среди эталонных; F1 — их гармоническое среднее. 95% ДИ — "
        "доверительный интервал Уилсона: при малой выборке он широкий, и это нужно учитывать "
        "при выводах.",
        "",
        "На графике `evaluation_prf.png` выравнивание показано по строгой оценке, разметка — "
        "по уровню «обнаружение + признак».",
        "",
        "## Выравнивание",
        "",
        md_table(["Языки", "Проверено пар", "верно", "ошибка", "исправлено",
                  "без эталона (ошибка без исправления)"],
                 [[TARGET_LABEL[t], ev.alignment[t].judged, ev.verdicts[t].get("correct", 0),
                   ev.verdicts[t].get("wrong", 0), ev.verdicts[t].get("corrected", 0),
                   ev.alignment[t].unknown] for t in TARGETS]),
        "",
        "- **Строгая оценка**: группа предложений (например, EN 4 ↔ ZH 4–5) верна, только "
        "если совпадает с эталонной целиком.",
        "- **Мягкая оценка**: считаются отдельные связи «предложение EN – предложение ZH/RU»; "
        "частично верная группа получает частичный балл.",
        "- Вердикт «ошибка» без исправления учитывается только в строгой точности.",
        "",
        "## Разметка",
        "",
        "- **Обнаружение**: пометка стоит на том же слове (те же позиции в тексте).",
        "- **Обнаружение + признак**: дополнительно совпадает признак — у артиклей "
        "существительное-вершина, у 量词 существительное при счётном слове, у падежей падеж.",
        "",
    ]
    ru = ev.langs["ru"]
    r_labels, c_labels, matrix = confusion
    lines += ["## Падежи: матрица ошибок", "",
              "Строки — падеж по эталону, столбцы — по автоматической разметке; "
              "«нет» — пометки нет (пропуск или ложное срабатывание).", "",
              md_table(["эталон \\ авто", *[case_label(c) for c in c_labels]],
                       [[case_label(r), *row] for r, row in zip(r_labels, matrix, strict=True)]),
              ""]
    if ru.lemma_total:
        lines += [f"Начальная форма (лемма) верна у {ru.lemma_ok} из {ru.lemma_total} "
                  "найденных существительных.", ""]
    lines += ["## Файлы", ""]
    lines += [f"- `{_rel(f, root)}`" for f in files]
    lines += ["", "Пересобрать: `python -m pipeline evaluate`.", ""]
    return "\n".join(lines)


def no_data_report(message: str, gold_path: Path, root: Path) -> str:
    return "\n".join([
        "# Оценка качества автоматической разметки",
        "",
        f"**Данных для оценки нет:** {message}.",
        "",
        "Как получить эталон:",
        "",
        "1. Откройте сайт корпуса → «Проверка» и разметьте выборку пар.",
        "2. Нажмите «Экспорт gold.json» и сохраните файл как "
        f"`{_rel(gold_path, root)}`.",
        "3. Запустите `python -m pipeline evaluate`.",
        "",
        "Эталон составляет только эксперт вручную; скрипт не придумывает данные.",
        "",
    ])


def run(corpus_path: Path, gold_path: Path, out: Path, root: Path) -> tuple[int, list[Path]]:
    """Код возврата (0 — отчёт или сообщение «нет данных», 1 — ошибка файла) и файлы."""
    try:
        gold = load_gold(gold_path)
        if gold is None:
            raise NoGoldData(f"файл {_rel(gold_path, root)} не найден")
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        ev = evaluate(corpus, gold)
    except NoGoldData as exc:
        message = str(exc)
        print(f"Оценка не выполнена: {message}.")
        out.mkdir(parents=True, exist_ok=True)
        path = out / "evaluation.md"
        path.write_text(no_data_report(message, gold_path, root), encoding="utf-8")
        return 0, [path]
    except GoldError as exc:
        print(f"Ошибка: {exc}")
        return 1, []
    files = write_outputs(ev, out, root)
    n = len(ev.used)
    print(f"Оценка по {n} {charts.plural(n, 'паре', 'парам', 'парам')} эталона"
          + (" (СИНТЕТИЧЕСКИЕ ДАННЫЕ)" if gold.synthetic else "") + ":")
    for row in metric_rows(ev):
        p, r, f = (charts.fmt(v) for v in row[5:8])
        print(f"  {row[0]:<24} {row[1]:<42} P {p}  R {r}  F1 {f}")
    return 0, files
