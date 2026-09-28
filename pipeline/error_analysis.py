"""Анализ ошибок автоматической разметки по золотому стандарту.

    python -m pipeline errors [--gold data/gold/gold.json] [--out reports]

Разбирает ошибки, которые эксперт отметил в режиме «Проверка» (по снимку той
разметки, которую он видел), и относит каждую к типу:

- выравнивание: сдвиг, неверное объединение, неверное разделение (по исправлению);
- артикли: пропуск, лишнее срабатывание, неверная вершина;
- 量词: пропуск, ложное срабатывание, неверная граница сегментации,
  неверное существительное;
- падежи: омонимия форм, неверная лемма, прочее (ложное срабатывание, пропуск,
  неверный падеж без омонимии).

Типы определяются правилами (см. classify_*), а не вручную. Для каждого типа —
частота и до трёх показательных примеров. Результат: reports/errors.md,
errors.csv и errors_types.png. Без эталона — понятное сообщение без чисел.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline import charts
from pipeline.gold import TARGETS, Gold, GoldError, Link, link_components, load_gold
from pipeline.metrics import link_label
from pipeline.tables import md_table, write_csv

EXAMPLES_PER_TYPE = 3

# Типы в порядке вывода: (явление, код, подпись, определение)
TYPES: list[tuple[str, str, str, str]] = [
    ("align", "shift", "сдвиг",
     "группа того же размера, но из других предложений (соответствие «съехало»)"),
    ("align", "merge", "неверное объединение",
     "автоматическая группа шире эталонной: в неё попали лишние предложения"),
    ("align", "split", "неверное разделение",
     "автоматическая группа уже эталонной: часть соответствия ушла в соседнюю группу"),
    ("align", "mixed", "смешанная ошибка",
     "одновременно лишние и недостающие предложения"),
    ("align", "unknown", "без исправления",
     "эксперт отметил ошибку, но не указал верный вариант — тип определить нельзя"),
    ("en", "missed", "пропуск", "артикль в тексте есть, автоматика его не разметила"),
    ("en", "false", "лишнее срабатывание", "размечено то, что не является артиклем"),
    ("en", "head", "неверная вершина", "артикль найден, но отнесён не к тому существительному"),
    ("zh", "missed", "пропуск", "конструкция с 量词 есть, автоматика её не нашла"),
    ("zh", "false", "ложное срабатывание", "размечено то, что не является счётным словом"),
    ("zh", "boundary", "неверная граница сегментации",
     "неверно определены границы слова: 量词 или существительное взяты не целиком или с "
     "лишними иероглифами"),
    ("zh", "noun", "неверное существительное",
     "счётное слово найдено, но существительное выбрано другое"),
    ("ru", "homonymy", "омонимия форм",
     "словоформа совпадает в нескольких падежах, выбран не тот (эталонный падеж есть среди "
     "разборов pymorphy3)"),
    ("ru", "lemma", "неверная лемма", "неверно определена начальная форма"),
    ("ru", "other", "прочее",
     "ложное срабатывание (не существительное), пропуск или неверный падеж без омонимии"),
]
PHENOMENON_TITLE = {
    "align": "Выравнивание",
    "en": "Артикли (EN)",
    "zh": "Счётные слова 量词 (ZH)",
    "ru": "Падежи (RU)",
}
PHENOMENON_PLAIN = {"align": "Выравнивание", "en": "Артикли", "zh": "Счётные слова",
                    "ru": "Падежи"}
PHENOMENON_COLOR = {"align": charts.ALIGN_COLOR, "en": charts.LANG_COLORS["en"],
                    "zh": charts.LANG_COLORS["zh"], "ru": charts.LANG_COLORS["ru"]}
CASE_NAMES = {"nomn": "им.", "gent": "род.", "datv": "дат.", "accs": "вин.", "ablt": "твор.",
              "loct": "предл.", "voct": "зв."}


class NoGoldData(Exception):
    pass


@dataclass
class ErrorCase:
    phenomenon: str  # align | en | zh | ru
    kind: str
    pair_id: str
    lang: str
    text: str  # предложение (или группа предложений) для примера
    span: tuple[int, int] | None  # выделить в тексте
    auto: str
    gold: str
    detail: str = ""


# ─── Классификация ────────────────────────────────────────────────────────


def classify_alignment(auto: Link, gold: list[Link]) -> str:
    """Тип ошибки выравнивания: сравнение автоматической группы с эталонными."""
    en_auto, tgt_auto = set(auto[0]), set(auto[1])
    related = [g for g in gold if set(g[0]) & en_auto or set(g[1]) & tgt_auto]
    if not related:
        return "mixed"
    en_gold = set().union(*(set(g[0]) for g in related))
    tgt_gold = set().union(*(set(g[1]) for g in related))
    if len(related) >= 2 and en_gold <= en_auto and tgt_gold <= tgt_auto:
        return "merge"
    if len(related) == 1:
        extra = (en_auto - en_gold) | {("t", t) for t in tgt_auto - tgt_gold}
        missing = (en_gold - en_auto) | {("t", t) for t in tgt_gold - tgt_auto}
        if extra and not missing:
            return "merge"
        if missing and not extra:
            return "split"
        if len(en_auto) == len(en_gold) and len(tgt_auto) == len(tgt_gold):
            return "shift"
    return "mixed"


def _norm(text: str | None) -> str:
    return (text or "").strip().lower().replace("ё", "е")


def classify_classifier(auto: dict[str, Any], fix: dict[str, Any]) -> str:
    classifier = fix.get("classifier") or auto.get("text", "")
    if classifier != auto.get("text"):
        return "boundary"
    auto_head = (auto.get("head") or {}).get("text", "") or ""
    gold_head = fix.get("head", "") or ""
    if auto_head and gold_head and auto_head != gold_head and (
            auto_head in gold_head or gold_head in auto_head):
        return "boundary"
    return "noun"


def case_homonymous(word: str, auto_case: str, gold_case: str, gold_lemma: str) -> bool:
    """Есть ли у словоформы разбор с эталонным падежом (и леммой) — омонимия форм."""
    from pipeline.annotate.ru import _norm_case, get_morph

    parses = {(_norm(p.normal_form), _norm_case(p.tag.case)) for p in get_morph().parse(word)
              if p.tag.case}
    lemma = _norm(gold_lemma)
    cases = {case for norm, case in parses if not lemma or norm == lemma}
    return gold_case in cases and auto_case in {case for _, case in parses}


def classify_case(auto: dict[str, Any], fix: dict[str, Any]) -> tuple[str, str]:
    gold_case = fix.get("case") or auto.get("case", "")
    gold_lemma = fix.get("lemma") or auto.get("lemma", "")
    if _norm(gold_lemma) != _norm(auto.get("lemma")):
        return "lemma", ""
    if gold_case != auto.get("case"):
        if case_homonymous(auto.get("text", ""), auto.get("case", ""), gold_case, gold_lemma):
            return "homonymy", ""
        return "other", "неверный падеж без омонимии"
    return "other", "исправление без изменения признаков"


# ─── Сбор ошибок ─────────────────────────────────────────────────────────


def _sentences_text(pair: dict[str, Any], lang: str) -> str:
    return pair["text"][lang]


def _case_label(case: str | None) -> str:
    return CASE_NAMES.get(case or "", case or "—")


def collect(gold: Gold) -> tuple[list[ErrorCase], dict[str, int]]:
    """Ошибки из полностью проверенных пар и объём проверенного (для долей)."""
    cases: list[ErrorCase] = []
    checked = Counter[str]()
    for pair in gold.complete_pairs():
        pid = pair["id"]
        for lang in TARGETS:
            review = pair["alignment"][lang]
            checked["align"] += 1
            auto: Link = (tuple(pair["sentences"]["en"]), tuple(pair["sentences"][lang]))
            verdict = review["verdict"]
            if verdict == "correct":
                continue
            gold_links = link_components(review.get("links", [])) if verdict == "corrected" \
                else []
            kind = classify_alignment(auto, gold_links) if gold_links else "unknown"
            cases.append(ErrorCase(
                "align", kind, pid, lang,
                f"EN: {pair['text']['en']}\n{lang.upper()}: {pair['text'][lang]}", None,
                link_label(auto, lang), "; ".join(link_label(g, lang) for g in gold_links) or "—",
            ))
        for lang in ("en", "zh", "ru"):
            phen = pair["phenomena"][lang]
            text = _sentences_text(pair, lang)
            checked[lang] += len(phen.get("items", [])) + len(phen.get("missed", []))
            for item in phen.get("items", []):
                auto_item = item["auto"]
                verdict = item["verdict"]
                fix = item.get("correction") or {}
                span = (auto_item["start"], auto_item["end"])
                if verdict == "correct":
                    continue
                if lang == "en":
                    auto_head = (auto_item.get("head") or {}).get("text", "") or "—"
                    if verdict == "wrong":
                        cases.append(ErrorCase("en", "false", pid, lang, text, span,
                                               f"{auto_item['text']} → {auto_head}", "не артикль"))
                    elif _norm(fix.get("head")) != _norm(auto_head):
                        cases.append(ErrorCase("en", "head", pid, lang, text, span,
                                               f"{auto_item['text']} → {auto_head}",
                                               f"{auto_item['text']} → {fix.get('head') or '—'}"))
                elif lang == "zh":
                    auto_head = (auto_item.get("head") or {}).get("text", "") or "∅"
                    det = (auto_item.get("det") or {}).get("text", "")
                    auto_label = f"{det}{auto_item['text']} → {auto_head}"
                    if verdict == "wrong":
                        cases.append(ErrorCase("zh", "false", pid, lang, text, span, auto_label,
                                               "не счётное слово"))
                    else:
                        classifier = fix.get("classifier") or auto_item["text"]
                        head = fix.get("head") or ""
                        raw_head = (auto_item.get("head") or {}).get("text", "") or ""
                        if classifier == auto_item["text"] and head == raw_head:
                            continue  # «исправление» совпало с автоматической разметкой
                        cases.append(ErrorCase("zh", classify_classifier(auto_item, fix), pid,
                                               lang, text, span, auto_label,
                                               f"{classifier} → {head or '∅'}"))
                else:
                    auto_label = (f"{auto_item['text']}: {_case_label(auto_item.get('case'))}, "
                                  f"{auto_item.get('lemma', '')}")
                    if verdict == "wrong":
                        cases.append(ErrorCase("ru", "other", pid, lang, text, span, auto_label,
                                               "не существительное", "ложное срабатывание"))
                    else:
                        kind, detail = classify_case(auto_item, fix)
                        if detail == "исправление без изменения признаков":
                            continue
                        cases.append(ErrorCase(
                            "ru", kind, pid, lang, text, span, auto_label,
                            f"{auto_item['text']}: {_case_label(fix.get('case'))}, "
                            f"{fix.get('lemma', '')}", detail))
            for missed in phen.get("missed", []):
                span = (missed["start"], missed["end"])
                if lang == "ru":
                    cases.append(ErrorCase(
                        "ru", "other", pid, lang, text, span, "нет пометки",
                        f"{missed['text']}: {_case_label(missed.get('case'))}, "
                        f"{missed.get('lemma', '')}", "пропуск"))
                else:
                    head = missed.get("head") or ("∅" if lang == "zh" else "—")
                    cases.append(ErrorCase(lang, "missed", pid, lang, text, span, "нет пометки",
                                           f"{missed['text']} → {head}"))
    return cases, dict(checked)


# ─── Отчёт ────────────────────────────────────────────────────────────────


def _highlight(text: str, span: tuple[int, int] | None) -> str:
    if span is None:
        return text
    a, b = span
    return f"{text[:a]}**{text[a:b]}**{text[b:]}"


def pick_examples(items: list[ErrorCase], limit: int = EXAMPLES_PER_TYPE) -> list[ErrorCase]:
    """Примеры из разных пар; порядок — как в эталоне."""
    picked: list[ErrorCase] = []
    pairs: set[str] = set()
    for item in items:
        if item.pair_id not in pairs:
            picked.append(item)
            pairs.add(item.pair_id)
        if len(picked) == limit:
            return picked
    for item in items:
        if item not in picked:
            picked.append(item)
        if len(picked) == limit:
            break
    return picked


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def write_outputs(gold: Gold, cases: list[ErrorCase], checked: dict[str, int], out: Path,
                  root: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    counts = Counter((c.phenomenon, c.kind) for c in cases)
    files.append(write_csv(
        out / "errors.csv",
        ["явление", "тип", "pair_id", "язык", "автоматически", "эталон", "уточнение", "фрагмент"],
        [[PHENOMENON_PLAIN[c.phenomenon], next(t[2] for t in TYPES if t[:2] == (c.phenomenon,
                                                                               c.kind)),
          c.pair_id, c.lang, c.auto, c.gold, c.detail,
          c.text[c.span[0]:c.span[1]] if c.span else ""] for c in cases],
    ))
    present = [t for t in TYPES if counts.get((t[0], t[1]))]
    if present:
        files.append(charts.hbars(
            out / "errors_types.png",
            [t[2] for t in present],
            [counts[(t[0], t[1])] for t in present],
            [PHENOMENON_COLOR[t[0]] for t in present],
            title="Типы ошибок автоматической разметки",
            xlabel="число ошибок",
            groups=[t[0] for t in present],
            legend={PHENOMENON_PLAIN[p]: PHENOMENON_COLOR[p]
                    for p in dict.fromkeys(t[0] for t in present)},
        ))

    n_pairs = len(gold.complete_pairs())
    lines = ["# Анализ ошибок автоматической разметки", ""]
    if gold.synthetic:
        lines += ["> **ВНИМАНИЕ: синтетические данные.** Эталон помечен как тестовый "
                  "(`synthetic: true`), ошибки ниже выдуманы для проверки кода.", ""]
    lines += [
        f"- Отчёт построен: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Эталон: `{_rel(gold.path, root)}`"
        + (f", эксперт: {gold.annotator}" if gold.annotator else "")
        + f"; полностью проверенных пар: **{n_pairs}**.",
        "- Разбираются ошибки, которые эксперт отметил в разметке, показанной ему при проверке "
        "(снимок в gold.json). Тип ошибки определяется правилами — см. определения в таблицах.",
        "",
        "## Сводка",
        "",
    ]
    summary_rows = []
    for phen in ("align", "en", "zh", "ru"):
        n_err = sum(v for (p, _), v in counts.items() if p == phen)
        base = checked.get(phen, 0)
        unit = "соответствий" if phen == "align" else "пометок (с пропусками)"
        summary_rows.append([PHENOMENON_TITLE[phen], base, unit, n_err,
                             f"{charts.fmt(100 * n_err / base, 1)} %" if base else "—"])
    lines += [md_table(["Явление", "Проверено", "Единица", "Ошибок", "Доля ошибок"],
                       summary_rows, text_columns=[2]), ""]

    for phen in ("align", "en", "zh", "ru"):
        phen_types = [t for t in TYPES if t[0] == phen]
        total = sum(counts.get((phen, t[1]), 0) for t in phen_types)
        lines += [f"## {PHENOMENON_TITLE[phen]}", ""]
        if total == 0:
            lines += ["Ошибок не отмечено.", ""]
            continue
        rows = [[t[2], counts.get((phen, t[1]), 0),
                 f"{charts.fmt(100 * counts.get((phen, t[1]), 0) / total, 1)} %", t[3]]
                for t in phen_types]
        lines += [md_table(["Тип", "Число", "Доля", "Определение"], rows,
                           text_columns=[3]), ""]
        for t in phen_types:
            items = [c for c in cases if (c.phenomenon, c.kind) == (phen, t[1])]
            if not items:
                continue
            lines += [f"### {t[2].capitalize()}: примеры", ""]
            for c in pick_examples(items):
                if phen == "align":
                    lines.append(f"- `{c.pair_id}` · автоматически: {c.auto} · эталон: {c.gold}")
                    for row in c.text.split("\n"):
                        lines.append(f"  - {row}")
                else:
                    lines.append(f"- `{c.pair_id}` · {_highlight(c.text, c.span)}")
                    lines.append(f"  - автоматически: {c.auto}; эталон: {c.gold}"
                                 + (f" ({c.detail})" if c.detail else ""))
            lines.append("")
    lines += ["## Файлы", ""] + [f"- `{_rel(f, root)}`" for f in files]
    lines += ["", "Пересобрать: `python -m pipeline errors`.", ""]
    path = out / "errors.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return [path, *files]


def no_data_report(message: str, gold_path: Path, root: Path) -> str:
    return "\n".join([
        "# Анализ ошибок автоматической разметки",
        "",
        f"**Данных для анализа нет:** {message}.",
        "",
        "Ошибки берутся из эталона, который эксперт размечает в режиме «Проверка» на сайте. "
        f"Сохраните экспорт как `{_rel(gold_path, root)}` и запустите "
        "`python -m pipeline errors`.",
        "",
    ])


def run(gold_path: Path, out: Path, root: Path) -> tuple[int, list[Path]]:
    try:
        gold = load_gold(gold_path)
        if gold is None:
            raise NoGoldData(f"файл {_rel(gold_path, root)} не найден")
        if not gold.complete_pairs():
            raise NoGoldData("в эталоне нет ни одной полностью проверенной пары")
    except NoGoldData as exc:
        print(f"Анализ ошибок не выполнен: {exc}.")
        out.mkdir(parents=True, exist_ok=True)
        path = out / "errors.md"
        path.write_text(no_data_report(str(exc), gold_path, root), encoding="utf-8")
        return 0, [path]
    except GoldError as exc:
        print(f"Ошибка: {exc}")
        return 1, []
    cases, checked = collect(gold)
    files = write_outputs(gold, cases, checked, out, root)
    counts = Counter(c.phenomenon for c in cases)
    print(f"Ошибок: {len(cases)} ("
          + ", ".join(f"{PHENOMENON_PLAIN[p].lower()} {counts.get(p, 0)}"
                      for p in ("align", "en", "zh", "ru")) + ")"
          + (" — СИНТЕТИЧЕСКИЕ ДАННЫЕ" if gold.synthetic else ""))
    return 0, files
