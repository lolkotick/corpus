"""Описание корпуса для курсовой: reports/corpus.md, таблицы CSV и графики PNG.

    python -m pipeline corpus-report [--out reports]

Все числа берутся из собранного корпуса (web/public/data/corpus.json и
stats.json), поэтому отчёт всегда соответствует текущей сборке.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline import charts
from pipeline.tables import md_table, write_csv

CASE_SHORT = {"nomn": "им.", "gent": "род.", "datv": "дат.", "accs": "вин.", "ablt": "твор.",
              "loct": "предл.", "voct": "зв."}
METHOD_LABEL = {"gale_church": "Гейл–Чёрч (длина предложений)",
                "labse": "LaBSE (алгоритм Bertalign)", "bertalign": "bertalign (LaBSE)"}
RU_LIGHT = "#5bb38d"  # вторая ступень зелёного RU (проверена как упорядоченная пара на сайте)


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _origin_note(texts: list[dict[str, Any]]) -> list[str]:
    registers = Counter(t.get("register") or "учебный" for t in texts)
    notes = []
    if registers.get("учебный"):
        notes.append("Учебные тексты корпуса составлены и переведены с помощью ИИ для "
                     "демонстрации метода (указано в `data/raw/*/meta.json`).")
    imported = [t for t in texts if (t.get("register") or "учебный") != "учебный"]
    if imported:
        notes.append("Импортированные источники: " + "; ".join(
            f"{t.get('title_ru') or t['title']} — {t.get('license', 'лицензия не указана')}"
            for t in imported) + " (подробно — страница «Источники» на сайте).")
    return [" ".join(notes)] if notes else []


def _register_section(stats: dict[str, Any]) -> list[str]:
    registers = stats.get("registers") or []
    if len(registers) < 2:
        return []
    rows = [[r["register"], r["texts"], r["pairs"], r["articles"]["per_100_words"],
             r["classifiers"]["per_100_chars"], r["cases"]["per_100_words"],
             r["difficulty_mean"]] for r in registers]
    codes = [c for c in CASE_SHORT if any(d["case"] == c and d["count"]
                                          for r in registers for d in r["cases"]["distribution"])]
    case_rows = [[r["register"], *[next((d["share"] for d in r["cases"]["distribution"]
                                         if d["case"] == c), 0.0) for c in codes]]
                 for r in registers]
    top_rows = [[r["register"], ", ".join(f"{c['value']} {charts.fmt(c['share'], 1)} %"
                                          for c in r["classifiers"]["top"][:5]) or "—"]
                for r in registers]
    return [
        "## Регистры",
        "",
        "Показатели нормированы на объём регистра: артикли — на 100 слов EN, 量词 — на 100 "
        "иероглифов ZH, существительные — на 100 слов RU; сложность — средняя оценка пар "
        "(0–1, см. «Оценка сложности»).",
        "",
        md_table(["Регистр", "Текстов", "Пар", "Артиклей на 100 слов", "量词 на 100 иероглифов",
                  "Сущ. RU на 100 слов", "Сложность"], rows, digits=2, text_columns=[0]),
        "",
        "Распределение падежей (доля среди существительных регистра, %):",
        "",
        md_table(["Регистр", *[CASE_SHORT[c] for c in codes]], case_rows, digits=1,
                 text_columns=[0]),
        "",
        "Самые частые 量词 (доля среди конструкций регистра):",
        "",
        md_table(["Регистр", "量词"], top_rows, text_columns=[0, 1]),
        "",
    ]


def _difficulty_section(corpus: dict[str, Any]) -> list[str]:
    """Калибровка оценки сложности на учебных текстах и распределение уровней по регистрам."""
    import statistics

    texts = {t["id"]: t for t in corpus["texts"]}
    by_level: dict[str, list[float]] = {}
    levels_by_register: dict[str, Counter[str]] = {}
    for pair in corpus["pairs"]:
        if "difficulty" not in pair:
            continue
        text = texts.get(pair["text_id"], {})
        register = text.get("register") or "учебный"
        levels_by_register.setdefault(register, Counter())[pair.get("level", "")] += 1
        if register == "учебный" and not pair.get("origin"):
            by_level.setdefault(text.get("level", ""), []).append(pair["difficulty"])
    if not by_level:
        return []
    calib = [[level, len(v), statistics.median(v), min(v), max(v)]
             for level, v in sorted(by_level.items())]
    all_levels = sorted({lv for c in levels_by_register.values() for lv in c})
    dist = [[reg, *[c.get(lv, 0) for lv in all_levels]] for reg, c in levels_by_register.items()]
    return [
        "## Оценка сложности",
        "",
        "Оценка пары = среднее по трём языкам от 0,5 · min(длина / L, 1) + 0,5 · доля слов с "
        "частотностью ниже Zipf 4 (wordfreq); L = 30 слов EN, 30 слов ZH, 25 слов RU. Границы "
        "уровней — середины между медианами оценок учебных текстов с уровнем, заданным "
        "автором (таблица ниже). Уровень учебной пары — уровень её текста; импортированной — "
        "по оценке.",
        "",
        md_table(["Уровень текста", "Пар", "Медиана оценки", "Мин.", "Макс."], calib, digits=3,
                 text_columns=[0]),
        "",
        "Пары по уровням и регистрам:",
        "",
        md_table(["Регистр", *all_levels], dist, text_columns=[0]),
        "",
    ]


def build(corpus: dict[str, Any], stats: dict[str, Any], out: Path, root: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    totals = stats["totals"]
    texts = corpus["texts"]
    types_by_text: dict[str, Counter[str]] = {t["id"]: Counter() for t in texts}
    for pair in corpus["pairs"]:
        types_by_text[pair["text_id"]][pair["alignment_type"]] += 1
    stat_by_text = {t["id"]: t for t in stats["texts"]}

    # Тексты
    text_rows = []
    for t in texts:
        st = stat_by_text.get(t["id"], {})
        sents = t.get("sentences", {})
        text_rows.append([
            t.get("title_ru") or t["title"], t["level"],
            len(sents.get("en", [])), len(sents.get("zh", [])), len(sents.get("ru", [])),
            t["pairs"],
            ", ".join(f"{k.replace('-', '–')}: {v}"
                      for k, v in types_by_text[t["id"]].most_common()),
            st.get("mean_score"),
            st.get("words", {}).get("en"), st.get("words", {}).get("zh"),
            st.get("words", {}).get("ru"),
        ])
    text_head = ["Текст", "Уровень", "Предл. EN", "Предл. ZH", "Предл. RU", "Пар",
                 "Типы соответствий", "Средний score", "Слов EN", "Иероглифов ZH", "Слов RU"]
    files.append(write_csv(out / "corpus_texts.csv", text_head, text_rows))

    # Разметка по текстам
    ann_rows = []
    for t in texts:
        st = stat_by_text.get(t["id"], {})
        arts = st.get("articles", {})
        dens = st.get("density", {})
        ann_rows.append([t.get("title_ru") or t["title"], sum(arts.values()),
                         st.get("classifiers"), st.get("nouns_ru"),
                         dens.get("articles_per_100_words"),
                         dens.get("classifiers_per_100_chars"),
                         dens.get("nouns_per_100_words")])
    ann_head = ["Текст", "Артиклей", "Конструкций с 量词", "Существительных RU",
                "Артиклей на 100 слов", "量词 на 100 иероглифов", "Сущ. на 100 слов"]
    files.append(write_csv(out / "corpus_annotation.csv", ann_head, ann_rows))

    cases = stats["cases"]
    case_rows = [[c["label"], c["sing"], c["plur"], c["sing"] + c["plur"], c["ambiguous"]]
                 for c in cases]
    files.append(write_csv(out / "corpus_cases.csv",
                           ["падеж", "ед. ч.", "мн. ч.", "всего", "неоднозначных"], case_rows))
    cl = stats["classifiers"]
    cl_rows = [[c["value"], c["pinyin"], c["type"], c["gloss"], c["count"],
                ", ".join(f"{n['noun']} ({n['count']})" for n in c["nouns"])] for c in cl]
    files.append(write_csv(out / "corpus_classifiers.csv",
                           ["量词", "пиньинь", "тип", "значение", "число", "существительные"],
                           cl_rows))

    # Графики
    files.append(charts.hbars(
        out / "corpus_texts.png",
        [f"{r[0]} ({r[1]})" for r in text_rows], [float(r[5]) for r in text_rows],
        [charts.SERIES[0]] * len(text_rows),
        title="Число пар (троек предложений) по текстам", xlabel="пар",
    ))
    files.append(charts.grouped_bars(
        out / "corpus_cases.png", [CASE_SHORT.get(c["case"], c["case"]) for c in cases],
        {"ед. ч.": [float(c["sing"]) for c in cases],
         "мн. ч.": [float(c["plur"]) for c in cases]},
        title="Падежи существительных (RU)", ylim=None, value_digits=0, tick_digits=0,
        colors=[charts.LANG_COLORS["ru"], RU_LIGHT],
    ))
    top = cl[:12]
    files.append(charts.hbars(
        out / "corpus_classifiers.png", [c["pinyin"] for c in top],
        [float(c["count"]) for c in top], [charts.LANG_COLORS["zh"]] * len(top),
        title="Самые частые счётные слова (ZH), по пиньиню", xlabel="употреблений",
    ))
    arts = stats["articles"]["counts"]
    files.append(charts.grouped_bars(
        out / "corpus_articles.png", ["the", "a", "an"],
        {"Артиклей": [float(arts.get(k, 0)) for k in ("the", "a", "an")]},
        title="Артикли (EN)", ylim=None, value_digits=0, tick_digits=0,
        colors=[charts.LANG_COLORS["en"]],
    ))
    hist = stats["alignment"]["histogram"]
    files.append(charts.grouped_bars(
        out / "corpus_alignment.png",
        [f"{charts.fmt(h['from'], 1)}–{charts.fmt(h['to'], 1)}" for h in hist],
        {"Пар": [float(h["count"]) for h in hist]},
        title="Распределение alignment_score", ylim=None, value_digits=0, tick_digits=0,
        colors=[charts.ALIGN_COLOR],
    ))

    align = stats["alignment"]
    build_info = stats.get("build", {})
    method = METHOD_LABEL.get(align["method"], align["method"])
    ann = totals["annotations"]
    lines = [
        "# Описание корпуса",
        "",
        f"- Отчёт построен: {datetime.now(UTC).isoformat(timespec='seconds')}; сборка корпуса "
        f"{corpus.get('generated_at', '—')}.",
        f"- Текстов: **{totals['texts']}**, пар (троек предложений EN–ZH–RU): "
        f"**{totals['pairs']}**; предложений EN {totals['sentences']['en']}, ZH "
        f"{totals['sentences']['zh']}, RU {totals['sentences']['ru']}.",
        f"- Объём: слов EN {totals['tokens']['en']}, иероглифов ZH {totals['tokens']['zh']}, "
        f"слов RU {totals['tokens']['ru']}.",
        f"- Размечено: артиклей {ann['article']}, конструкций с 量词 {ann['classifier']} "
        f"({totals['distinct_classifiers']} разных 量词), существительных RU {ann['case']}; "
        f"спорных пометок {totals['disputed']}, из них неоднозначных падежей "
        f"{totals['ambiguous_cases']}.",
        f"- Выравнивание: {method}; средний alignment_score {charts.fmt(align['mean'], 3)}, "
        f"медиана {charts.fmt(align['median'], 3)}; ниже порога "
        f"{charts.fmt(align['low_score_threshold'], 2)} — {align['low_count']} пар.",
        f"- Ручная проверка: проверено {totals['status']['checked']}, исправлено "
        f"{totals['status']['corrected']}, автоматически {totals['status']['auto']}.",
        "",
        *_origin_note(texts),
        "",
        "## Тексты",
        "",
        md_table(text_head, text_rows, text_columns=[1, 6]),
        "",
        "## Разметка по текстам",
        "",
        md_table(ann_head, ann_rows, digits=1),
        "",
        "## Падежи (RU)",
        "",
        md_table(["Падеж", "Ед. ч.", "Мн. ч.", "Всего", "Неоднозначных"], case_rows),
        "",
        "## Счётные слова 量词 (ZH)",
        "",
        md_table(["量词", "Пиньинь", "Значение", "Число", "С какими существительными"],
                 [[c["value"], c["pinyin"], c["gloss"], c["count"],
                   ", ".join(n["noun"] for n in c["nouns"])] for c in cl[:15]],
                 text_columns=[1, 2, 4]),
        "",
        f"Показаны 15 самых частых из {len(cl)}; полный список — `corpus_classifiers.csv`.",
        "",
        "## Артикли (EN)",
        "",
        md_table(["Артикль", "Число"], [[k, arts.get(k, 0)] for k in ("the", "a", "an")]),
        "",
        "Чаще всего с *the*: " + ", ".join(
            f"{h['lemma']} ({h['count']})" for h in stats["articles"]["top_heads"]["the"][:8])
        + "; с *a/an*: " + ", ".join(
            f"{h['lemma']} ({h['count']})" for h in stats["articles"]["top_heads"]["a/an"][:8])
        + ".",
        "",
        *_register_section(stats),
        *_difficulty_section(corpus),
        "## Выравнивание",
        "",
        md_table(["Тип (EN–ZH–RU)", "Пар"],
                 [[k.replace("-", "–"), v] for k, v in align["types"].items()]),
        "",
    ]
    warnings = build_info.get("warnings", [])
    if warnings:
        lines += ["Предупреждения последней сборки: " + "; ".join(warnings) + ".", ""]
    lines += ["## Файлы", ""] + [f"- `{_rel(f, root)}`" for f in files]
    lines += ["", "Пересобрать: `python -m pipeline corpus-report` (после "
              "`python -m pipeline build`).", ""]
    path = out / "corpus.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return [path, *files]


def run(data_dir: Path, out: Path, root: Path) -> tuple[int, list[Path]]:
    corpus_path, stats_path = data_dir / "corpus.json", data_dir / "stats.json"
    if not corpus_path.exists() or not stats_path.exists():
        print(f"Нет {corpus_path.name} или {stats_path.name} — сначала соберите корпус: "
              "python -m pipeline build")
        return 1, []
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    files = build(corpus, stats, out, root)
    print(f"Описание корпуса: {stats['totals']['texts']} текстов, "
          f"{stats['totals']['pairs']} пар")
    return 0, files
