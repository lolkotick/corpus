"""Сравнение методов выравнивания на одних и тех же текстах.

    python -m pipeline compare-aligners [--methods gale_church,labse,...] [--out reports]

Каждый доступный метод выравнивает все тексты data/raw с одной и той же
сегментацией и теми же настройками, что и сборка корпуса (по абзацам, EN —
опорный язык). Для каждого метода и каждой языковой пары (EN–ZH, EN–RU)
считаются метрики по золотому стандарту (data/gold/gold.json), время работы и
согласие методов между собой; отбираются 10 показательных расхождений.

Методы:
- bertalign — пакет bertalign (LaBSE), нужен Python ≥ 3.12 и requirements-neural.txt;
- labse — собственная реализация алгоритма Bertalign на эмбеддингах LaBSE;
- gale_church — длина предложений (Gale & Church, 1993);
- llm — Claude, только если в .env есть ANTHROPIC_API_KEY;
- diagonal — базовый уровень «i-е предложение ↔ i-е предложение».
Недоступный метод пропускается, причина пишется в отчёт.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline import charts
from pipeline.align import create_aligner
from pipeline.align.baseline import DiagonalAligner
from pipeline.align.dp import allowed_types
from pipeline.build import align_text
from pipeline.config import Config
from pipeline.gold import (
    TARGETS,
    AlignmentTruth,
    Gold,
    GoldError,
    Link,
    alignment_truth,
    load_gold,
    pair_complete,
)
from pipeline.metrics import AlignmentScore, format_ci, link_label, score_alignment
from pipeline.segment import join_sentences, segment_paragraphs
from pipeline.sources import LANGS, LEVELS, RawText, discover_texts, read_text
from pipeline.tables import md_table, write_csv

METHODS = ("bertalign", "labse", "gale_church", "llm", "diagonal")
METHOD_LABELS = {
    "bertalign": "bertalign (LaBSE)",
    "labse": "LaBSE (алгоритм Bertalign)",
    "gale_church": "Гейл–Чёрч",
    "llm": "LLM (Claude)",
    "diagonal": "По порядку (базовый)",
}
TARGET_LABEL = {"zh": "EN–ZH", "ru": "EN–RU"}
EXAMPLES = 10


@dataclass
class MethodRun:
    method: str
    available: bool
    reason: str = ""
    load_seconds: float = 0.0
    align_seconds: float = 0.0
    # links[lang][text_id] — группы предложений (номера EN, номера ZH/RU)
    links: dict[str, dict[str, list[Link]]] = field(default_factory=dict)
    types: dict[str, dict[str, int]] = field(default_factory=dict)
    used_methods: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    scores: dict[str, AlignmentScore] = field(default_factory=dict)
    note: str = ""


@dataclass
class Comparison:
    texts: list[RawText]
    sentences: dict[str, dict[str, list[str]]]  # text_id → lang → предложения
    runs: list[MethodRun]
    gold: Gold | None
    gold_message: str
    truths: dict[str, list[AlignmentTruth]]
    stale: list[str]
    examples: list[dict[str, Any]]


def _segment(config: Config) -> tuple[list[RawText], dict[str, dict[str, list[list[str]]]]]:
    texts = [read_text(d) for d in discover_texts(config.path("raw"))]
    texts.sort(key=lambda t: (LEVELS.index(t.meta.level), t.meta.id))
    seg = config.get("segmentation", {}) or {}
    paragraphs = {
        t.meta.id: {lang: segment_paragraphs(t.paragraphs[lang], lang, seg) for lang in LANGS}
        for t in texts
    }
    return texts, paragraphs


def _make_aligner(method: str, config: Config) -> tuple[Any | None, str]:
    """Создать выравниватель; (None, причина), если метод недоступен."""
    align_config = dict(config.get("alignment", {}) or {})
    types = allowed_types(align_config.get("types", [[1, 1], [1, 2], [2, 1]]),
                          bool(align_config.get("allow_skips", True)))
    if method == "diagonal":
        return DiagonalAligner(), ""
    if method == "llm":
        from pipeline.align.llm_align import LlmAligner
        from pipeline.llm import api_key_available

        if not api_key_available(config.root):
            return None, "нет ANTHROPIC_API_KEY в .env — метод пропущен"
        try:
            import anthropic
        except ImportError:
            return None, "пакет anthropic не установлен"
        llm_config = config.get("llm", {}) or {}
        client = anthropic.Anthropic(timeout=float(llm_config.get("timeout_seconds", 120)))
        return LlmAligner(client, anthropic, llm_config, config.path("llm_cache") / "align",
                          align_config.get("gale_church", {}) or {}, types), ""
    aligner = create_aligner({**align_config, "method": method})
    if aligner.method != method:
        reasons = [w.removeprefix(f"{method}: ") for w in aligner.warnings
                   if w.startswith(method) and "запасной метод" not in w]
        return None, "; ".join(reasons) or "недоступен"
    return aligner, ""


def run_method(method: str, config: Config, texts: list[RawText],
               paragraphs: dict[str, dict[str, list[list[str]]]]) -> MethodRun:
    start = time.perf_counter()
    aligner, reason = _make_aligner(method, config)
    run = MethodRun(method, aligner is not None, reason,
                    load_seconds=time.perf_counter() - start)
    if aligner is None:
        return run
    use_paragraphs = bool(config.get("alignment.use_paragraphs", True))
    run.links = {lang: {} for lang in TARGETS}
    run.types = {lang: {} for lang in TARGETS}
    start = time.perf_counter()
    for raw in texts:
        segments, _ = align_text(aligner, raw, paragraphs[raw.meta.id], use_paragraphs,
                                 run.warnings)
        for seg in segments:
            run.used_methods.update(seg.method.split("+"))
            for lang in TARGETS:
                link: Link = (tuple(seg.sentence_ids("en")), tuple(seg.sentence_ids(lang)))
                run.links[lang].setdefault(raw.meta.id, []).append(link)
                kind = f"{len(link[0])}-{len(link[1])}"
                run.types[lang][kind] = run.types[lang].get(kind, 0) + 1
    run.align_seconds = time.perf_counter() - start
    run.warnings += list(getattr(aligner, "warnings", []))
    if method == "llm":
        run.note = (f"запросов к API {getattr(aligner, 'requests', 0)}, из кэша "
                    f"{getattr(aligner, 'from_cache', 0)}, абзацев с запасным методом "
                    f"{getattr(aligner, 'fallbacks', 0)}")
    elif run.used_methods - {method}:
        run.note = "часть абзацев выровнена запасным методом: " + ", ".join(
            sorted(run.used_methods - {method}))
    return run


# ─── Эталон ───────────────────────────────────────────────────────────────


def gold_truths(gold: Gold, sentences: dict[str, dict[str, list[str]]]
                ) -> tuple[dict[str, list[AlignmentTruth]], list[str]]:
    """Эталонные связи по полностью проверенным парам; устаревшие пары отбрасываются.

    Пара устарела, если её текст на момент проверки не совпадает с предложениями
    текущей сегментации под теми же номерами.
    """
    truths: dict[str, list[AlignmentTruth]] = {lang: [] for lang in TARGETS}
    stale: list[str] = []
    for pair in gold.complete_pairs():
        text = sentences.get(pair["text_id"])
        ok = text is not None
        if ok:
            assert text is not None
            for lang in LANGS:
                ids = pair["sentences"][lang]
                if any(i >= len(text[lang]) for i in ids) or join_sentences(
                        [text[lang][i] for i in ids], lang) != pair["text"][lang]:
                    ok = False
        if not ok:
            stale.append(pair["id"])
            continue
        for lang in TARGETS:
            truths[lang].append(alignment_truth(pair, lang))
    return truths, stale


# ─── Расхождения между методами ───────────────────────────────────────────


def _link_of(links: Iterable[Link], en: int) -> Link | None:
    return next((link for link in links if en in link[0]), None)


def disagreements(runs: Sequence[MethodRun], sentences: dict[str, dict[str, list[str]]],
                  truths: dict[str, list[AlignmentTruth]]) -> list[dict[str, Any]]:
    """Участки текста, где методы группируют предложения по-разному."""
    active = [r for r in runs if r.available]
    if len(active) < 2:
        return []
    gold_en = {(t.text_id, t.lang): set() for lang in TARGETS for t in truths[lang]}
    for lang in TARGETS:
        for t in truths[lang]:
            if t.known:
                gold_en[(t.text_id, lang)] |= set(t.auto[0])
    found: list[dict[str, Any]] = []
    for text_id, text in sentences.items():
        for lang in TARGETS:
            n = len(text["en"])
            e = 0
            while e < n:
                links = {r.method: _link_of(r.links[lang].get(text_id, []), e) for r in active}
                if len(set(links.values())) <= 1:
                    e += 1
                    continue
                # Расширяем участок, пока группы методов перекрываются.
                region = {e}
                changed = True
                while changed:
                    changed = False
                    for r in active:
                        for link in r.links[lang].get(text_id, []):
                            if region & set(link[0]) and not set(link[0]) <= region:
                                region |= set(link[0])
                                changed = True
                groups = {
                    r.method: sorted({link for link in r.links[lang].get(text_id, [])
                                      if region & set(link[0])})
                    for r in active
                }
                gold_known = gold_en.get((text_id, lang), set())
                found.append({
                    "text_id": text_id,
                    "lang": lang,
                    "en": sorted(region),
                    "groups": groups,
                    "has_gold": bool(region & gold_known),
                    "size": len(region),
                })
                e = max(region) + 1
    return found


def pick_examples(found: list[dict[str, Any]], limit: int = EXAMPLES) -> list[dict[str, Any]]:
    """Сначала участки с эталоном, затем разные тексты и языки, затем более крупные."""
    ordered = sorted(found, key=lambda d: (not d["has_gold"], -d["size"], d["text_id"],
                                           d["lang"], d["en"][0]))
    picked: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], int] = {}
    for rounds in range(3):
        for item in ordered:
            key = (item["text_id"], item["lang"])
            if item in picked or seen.get(key, 0) > rounds:
                continue
            picked.append(item)
            seen[key] = seen.get(key, 0) + 1
            if len(picked) >= limit:
                return picked
    return picked


def agreement(a: MethodRun, b: MethodRun, lang: str) -> tuple[int, int]:
    """Сколько предложений EN оба метода отнесли к одинаковой группе."""
    same = total = 0
    for text_id, links in a.links[lang].items():
        other = b.links[lang].get(text_id, [])
        for link in links:
            for e in link[0]:
                total += 1
                same += _link_of(other, e) == link
    return same, total


# ─── Запуск ───────────────────────────────────────────────────────────────


def compare(config: Config, gold_path: Path, methods: Sequence[str] = METHODS) -> Comparison:
    texts, paragraphs = _segment(config)
    if not texts:
        raise SystemExit(f"В {config.path('raw')} нет ни одного текста")
    sentences = {tid: {lang: [s for para in p[lang] for s in para] for lang in LANGS}
                 for tid, p in paragraphs.items()}
    runs = [run_method(m, config, texts, paragraphs) for m in methods]

    gold: Gold | None = None
    message = ""
    try:
        gold = load_gold(gold_path)
    except GoldError as exc:
        message = f"файл эталона повреждён: {exc}"
    if gold is None and not message:
        message = f"файл {gold_path.name} не найден"
    truths: dict[str, list[AlignmentTruth]] = {lang: [] for lang in TARGETS}
    stale: list[str] = []
    if gold is not None:
        if not any(pair_complete(p) for p in gold.pairs):
            message = "в эталоне нет ни одной полностью проверенной пары"
        else:
            truths, stale = gold_truths(gold, sentences)
            if not truths["zh"]:
                message = "все проверенные пары устарели (тексты изменились после проверки)"
    if not message:
        for run in runs:
            if run.available:
                run.scores = {lang: score_alignment(truths[lang], run.links[lang])
                              for lang in TARGETS}
    examples = pick_examples(disagreements(runs, sentences, truths))
    return Comparison(texts, sentences, runs, gold, message, truths, stale, examples)


# ─── Отчёт ────────────────────────────────────────────────────────────────


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _fmt_seconds(value: float) -> str:
    return charts.fmt(value, 2 if value < 10 else 1)


def _quote(text: str, limit: int = 220) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _group_text(group: Link, lang: str, sentences: dict[str, list[str]]) -> str:
    en = join_sentences([sentences["en"][i] for i in group[0]], "en")
    tgt = join_sentences([sentences[lang][i] for i in group[1]], lang) if group[1] else "∅"
    return f"{link_label(group, lang)}: «{_quote(en)}» ↔ «{_quote(tgt)}»"


def write_outputs(cmp: Comparison, out: Path, root: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    active = [r for r in cmp.runs if r.available]

    time_rows = [[METHOD_LABELS[r.method], "да" if r.available else "нет",
                  round(r.load_seconds, 3) if r.available else None,
                  round(r.align_seconds, 3) if r.available else None,
                  r.reason or r.note] for r in cmp.runs]
    files.append(write_csv(out / "aligners_time.csv",
                           ["метод", "выполнен", "загрузка, с", "выравнивание, с",
                            "примечание"], time_rows))

    metric_head = ["Метод", "Языки", "Оценка", "TP", "FP", "FN", "Точность (P)",
                   "Полнота (R)", "F1", "95% ДИ точности", "95% ДИ полноты"]
    metric_rows: list[list[Any]] = []
    if not cmp.gold_message:
        for r in active:
            for lang in TARGETS:
                for level, c in (("строгая", r.scores[lang].strict),
                                 ("мягкая", r.scores[lang].lax)):
                    metric_rows.append([METHOD_LABELS[r.method], TARGET_LABEL[lang], level,
                                        c.tp, c.fp, c.fn, c.precision, c.recall, c.f1,
                                        format_ci(c.precision_ci()), format_ci(c.recall_ci())])
        files.append(write_csv(out / "aligners_metrics.csv", metric_head, metric_rows))
        files.append(charts.grouped_bars(
            out / "aligners_f1.png",
            [METHOD_LABELS[r.method] for r in active],
            {TARGET_LABEL[lang]: [r.scores[lang].strict.f1 for r in active]
             for lang in TARGETS},
            title="F1 выравнивания по эталону (строгая оценка)",
            colors=[charts.LANG_COLORS["zh"], charts.LANG_COLORS["ru"]],
        ))

    if active:
        peak = max(r.load_seconds + r.align_seconds for r in active)
        scale, unit = (1000.0, "мс") if peak < 1 else (1.0, "с")
        values = {"Загрузка модели": [r.load_seconds * scale for r in active],
                  "Выравнивание": [r.align_seconds * scale for r in active]}
        top = max(v for series in values.values() for v in series)
        digits = 0 if top >= 10 else 1 if top >= 1 else 2
        files.append(charts.grouped_bars(
            out / "aligners_time.png",
            [METHOD_LABELS[r.method] for r in active],
            values,
            title=f"Время работы на {len(cmp.texts)} текстах, {unit}",
            ylim=None,
            tick_digits=digits,
            value_digits=digits,
            colors=[charts.SERIES[1], charts.SERIES[0]],
        ))

    example_rows = []
    for k, ex in enumerate(cmp.examples, start=1):
        for method, groups in ex["groups"].items():
            example_rows.append([k, ex["text_id"], TARGET_LABEL[ex["lang"]],
                                 METHOD_LABELS[method],
                                 "; ".join(link_label(g, ex["lang"]) for g in groups),
                                 "да" if ex["has_gold"] else "нет"])
    files.append(write_csv(out / "aligners_disagreements.csv",
                           ["№", "текст", "языки", "метод", "группы", "есть эталон"],
                           example_rows))

    report = render_report(cmp, metric_head, metric_rows, files, root)
    path = out / "aligners.md"
    path.write_text(report, encoding="utf-8")
    return [path, *files]


def render_report(cmp: Comparison, metric_head: list[str], metric_rows: list[list[Any]],
                  files: list[Path], root: Path) -> str:
    n_sent = {lang: sum(len(s[lang]) for s in cmp.sentences.values()) for lang in LANGS}
    active = [r for r in cmp.runs if r.available]
    lines = ["# Сравнение методов выравнивания", ""]
    if cmp.gold is not None and cmp.gold.synthetic:
        lines += ["> **ВНИМАНИЕ: синтетические данные.** Эталон помечен как тестовый "
                  "(`synthetic: true`), метрики ниже ничего не говорят о методах.", ""]
    lines += [
        f"- Тексты: {len(cmp.texts)} ({', '.join(t.meta.id for t in cmp.texts)}); предложений "
        f"EN {n_sent['en']}, ZH {n_sent['zh']}, RU {n_sent['ru']}.",
        "- Условия одинаковы для всех методов: та же сегментация, выравнивание по абзацам, "
        "EN — опорный язык, EN–ZH и EN–RU выравниваются отдельно.",
        "- Сравниваются группы предложений в тройках EN–ZH–RU — так, как они попали бы в "
        "корпус: граница между группами остаётся, только если её поставили оба попарных "
        "выравнивания. Поэтому объединение предложений в одной паре языков отражается и в "
        "группах другой.",
        "",
        "## Методы и время работы",
        "",
        md_table(["Метод", "Выполнен", "Загрузка, с", "Выравнивание, с", "Примечание"],
                 [[METHOD_LABELS[r.method], "да" if r.available else "нет",
                   _fmt_seconds(r.load_seconds) if r.available else "—",
                   _fmt_seconds(r.align_seconds) if r.available else "—",
                   r.reason or r.note or ""] for r in cmp.runs],
                 align_right_from=2),
        "",
        "Время зависит от компьютера; для нейросетевых методов «загрузка» включает чтение "
        "модели LaBSE. Время LLM включает сетевые запросы (из кэша — почти мгновенно).",
        "",
    ]
    unavailable = [r for r in cmp.runs if not r.available]
    if unavailable:
        lines += ["Как запустить пропущенные методы:", ""]
        for r in unavailable:
            if r.method == "llm":
                lines.append("- **LLM**: добавьте `ANTHROPIC_API_KEY=…` в файл `.env` в корне "
                             "проекта (запросы платные; ответы кэшируются в "
                             "`data/llm_cache/align/`).")
            elif r.method in ("labse", "bertalign"):
                lines.append(f"- **{METHOD_LABELS[r.method]}**: `pip install -r "
                             "pipeline/requirements-neural.txt` (≈ 2 ГБ, нужен доступ к "
                             "huggingface.co)" + ("; пакет bertalign 2.x — Python ≥ 3.12"
                                                  if r.method == "bertalign" else "") + ".")
        lines.append("")

    lines += ["## Качество по эталону", ""]
    if cmp.gold_message:
        lines += [f"**Метрики не рассчитаны:** {cmp.gold_message}. Эталон составляет эксперт "
                  "в режиме «Проверка» на сайте (см. `data/gold/README.md`).", ""]
    else:
        n_pairs = len(cmp.truths["zh"])
        lines += [f"Эталон: {n_pairs} полностью проверенных пар"
                  + (f", устаревших (исключены): {len(cmp.stale)}" if cmp.stale else "") + ".",
                  "", md_table(metric_head, metric_rows, align_right_from=3), "",
                  "Строгая оценка — группа предложений совпадает с эталонной целиком; мягкая — "
                  "по отдельным связям «предложение–предложение». 95% ДИ — интервал Уилсона.",
                  ""]

    if len(active) >= 2:
        lines += ["## Согласие методов между собой", "",
                  "Доля предложений EN, которые два метода отнесли к одинаковой группе "
                  "(эталон не нужен).", ""]
        rows = []
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                row: list[Any] = [f"{METHOD_LABELS[a.method]} — {METHOD_LABELS[b.method]}"]
                for lang in TARGETS:
                    same, total = agreement(a, b, lang)
                    row.append(f"{charts.fmt(100 * same / total, 1)} % ({same}/{total})"
                               if total else "—")
                rows.append(row)
        lines += [md_table(["Пара методов", "EN–ZH", "EN–RU"], rows), ""]

    lines += ["## Показательные расхождения", ""]
    if len(active) < 2:
        lines += ["Выполнен только один метод — сравнивать не с чем.", ""]
    elif not cmp.examples:
        lines += ["Все выполненные методы выровняли тексты одинаково.", ""]
    else:
        lines += [f"Отобрано {len(cmp.examples)}: "
                  + ("сначала участки, где есть эталон, затем " if cmp.truths["zh"] else "")
                  + "разные тексты и языковые пары, более крупные участки — раньше.", ""]
        for k, ex in enumerate(cmp.examples, start=1):
            sents = cmp.sentences[ex["text_id"]]
            lines.append(f"### {k}. {ex['text_id']}, {TARGET_LABEL[ex['lang']]}, "
                         f"EN {', '.join(str(e + 1) for e in ex['en'])}"
                         + (" · есть эталон" if ex["has_gold"] else ""))
            lines.append("")
            for method, groups in ex["groups"].items():
                lines.append(f"- **{METHOD_LABELS[method]}**:")
                lines += [f"  - {_group_text(g, ex['lang'], sents)}" for g in groups]
            lines.append("")

    warnings = [(r.method, w) for r in cmp.runs for w in r.warnings]
    if warnings:
        lines += ["## Предупреждения", ""]
        lines += [f"- {METHOD_LABELS[m]}: {w}" for m, w in warnings[:30]]
        lines.append("")
    lines += ["## Файлы", ""] + [f"- `{_rel(f, root)}`" for f in files]
    lines += ["", "Пересобрать: `python -m pipeline compare-aligners`.", ""]
    return "\n".join(lines)


def run(config: Config, gold_path: Path, out: Path,
        methods: Sequence[str] = METHODS) -> tuple[int, list[Path]]:
    unknown = [m for m in methods if m not in METHODS]
    if unknown:
        print(f"Ошибка: неизвестные методы {', '.join(unknown)}; допустимо: {', '.join(METHODS)}")
        return 1, []
    cmp = compare(config, gold_path, methods)
    files = write_outputs(cmp, out, config.root)
    for r in cmp.runs:
        status = (f"{_fmt_seconds(r.load_seconds + r.align_seconds)} с" if r.available
                  else f"пропущен: {r.reason}")
        print(f"  {METHOD_LABELS[r.method]:<28} {status}")
    if cmp.gold_message:
        print(f"Метрики качества не рассчитаны: {cmp.gold_message}.")
    else:
        for r in cmp.runs:
            if r.available:
                print(f"  {METHOD_LABELS[r.method]:<28} F1 (строгая): "
                      + ", ".join(f"{TARGET_LABEL[lang]} {charts.fmt(r.scores[lang].strict.f1)}"
                                  for lang in TARGETS))
    return 0, files
