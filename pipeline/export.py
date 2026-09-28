"""Экспорт: corpus.json (для сайта), corpus.csv (для ручной проверки), stats.json."""

from __future__ import annotations

import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pipeline.annotate.ru import CASE_LABELS

CASE_ORDER = ["nomn", "gent", "datv", "accs", "ablt", "loct", "voct"]
CASE_SHORT = {"nomn": "им.", "gent": "род.", "datv": "дат.", "accs": "вин.", "ablt": "твор.",
              "loct": "предл.", "voct": "зв."}
CSV_COLUMNS = ["id", "text_id", "level", "status", "en", "zh", "ru", "comment",
               "alignment_type", "alignment_score", "annotations", "llm_note"]
_WORD = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)
_HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")


def count_words(text: str) -> int:
    return len(_WORD.findall(text))


def count_han(text: str) -> int:
    return len(_HAN.findall(text))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", "utf-8")


def annotation_summary(record: dict[str, Any]) -> str:
    parts = []
    en = [f"{a['text']}→{a['head']['text'] if a.get('head') else '?'}"
          for a in record["annotations"]["en"]]
    zh = [f"{a['det']['text']}{a['text']}→{a['head']['text'] if a.get('head') else '∅'}"
          for a in record["annotations"]["zh"]]
    ru = [f"{a['text']} ({CASE_SHORT.get(a['case'], a['case'])}{'?' if a.get('ambiguous') else ''}"
          f"{', мн.' if a['number'] == 'plur' else ''})" for a in record["annotations"]["ru"]]
    for label, items in (("EN", en), ("ZH", zh), ("RU", ru)):
        if items:
            parts.append(f"{label}: {', '.join(items)}")
    return " | ".join(parts)


def llm_summary(note: dict[str, Any] | None) -> str:
    if not note:
        return ""
    parts = [note.get("summary", "")]
    if not note.get("alignment_ok", True):
        parts.append(f"Выравнивание: {note.get('alignment_comment', '')}")
    for item in note.get("annotations", []):
        if not item.get("ok"):
            parts.append(f"{item['id']}: {item.get('suggestion', '')} — {item.get('comment', '')}")
    return " | ".join(p for p in parts if p)


def write_csv(path: Path, records: list[dict[str, Any]], texts: dict[str, dict[str, Any]],
              delimiter: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig (BOM) — чтобы Excel сразу правильно показал кириллицу и иероглифы.
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, delimiter=delimiter)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "id": r["id"],
                "text_id": r["text_id"],
                "level": texts.get(r["text_id"], {}).get("level", ""),
                "status": r["status"],
                "en": r["en"],
                "zh": r["zh"],
                "ru": r["ru"],
                "comment": r.get("comment", ""),
                "alignment_type": r["alignment_type"],
                "alignment_score": f"{r['alignment_score']:.3f}",
                "annotations": annotation_summary(r),
                "llm_note": llm_summary(r.get("llm_note")),
            })


def _histogram(scores: list[float], bins: int) -> list[dict[str, Any]]:
    counts = [0] * bins
    for s in scores:
        counts[min(bins - 1, max(0, int(s * bins)))] += 1
    return [
        {"from": round(k / bins, 3), "to": round((k + 1) / bins, 3), "count": counts[k]}
        for k in range(bins)
    ]


def compute_stats(
    records: list[dict[str, Any]],
    texts: list[dict[str, Any]],
    classifiers: list[dict[str, Any]],
    build: dict[str, Any],
    bins: int = 10,
) -> dict[str, Any]:
    articles: Counter[str] = Counter()
    article_heads: dict[str, Counter[str]] = {"the": Counter(), "a/an": Counter()}
    cl_counts: Counter[str] = Counter()
    cl_nouns: dict[str, Counter[str]] = defaultdict(Counter)
    elliptical = 0
    cases: dict[str, dict[str, int]] = {c: {"sing": 0, "plur": 0, "ambiguous": 0}
                                        for c in CASE_ORDER}
    lemmas: Counter[str] = Counter()
    types: Counter[str] = Counter()
    status: Counter[str] = Counter()
    per_text: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "pairs": 0, "articles": Counter(), "classifiers": 0, "cases": Counter(),
        "scores": [], "en_words": 0, "zh_chars": 0, "ru_words": 0,
    })
    tokens = {"en": 0, "zh": 0, "ru": 0}
    sentences = {"en": 0, "zh": 0, "ru": 0}
    ambiguous_total = 0
    disputed_total = 0

    for r in records:
        t = per_text[r["text_id"]]
        t["pairs"] += 1
        t["scores"].append(r["alignment_score"])
        en_w, zh_c, ru_w = count_words(r["en"]), count_han(r["zh"]), count_words(r["ru"])
        t["en_words"] += en_w
        t["zh_chars"] += zh_c
        t["ru_words"] += ru_w
        tokens["en"] += en_w
        tokens["zh"] += zh_c
        tokens["ru"] += ru_w
        for lang, n in zip(("en", "zh", "ru"), r["alignment_type"].split("-"), strict=True):
            sentences[lang] += int(n)
        types[r["alignment_type"]] += 1
        status[r["status"]] += 1
        for a in r["annotations"]["en"]:
            articles[a["value"]] += 1
            t["articles"][a["value"]] += 1
            if a.get("head"):
                key = "the" if a["value"] == "the" else "a/an"
                article_heads[key][a["head"]["lemma"]] += 1
            disputed_total += bool(a.get("disputed"))
        for a in r["annotations"]["zh"]:
            cl_counts[a["value"]] += 1
            t["classifiers"] += 1
            if a.get("head"):
                cl_nouns[a["value"]][a["head"]["text"]] += 1
            elif a.get("elliptical"):
                elliptical += 1
            disputed_total += bool(a.get("disputed"))
        for a in r["annotations"]["ru"]:
            bucket = cases.setdefault(a["case"], {"sing": 0, "plur": 0, "ambiguous": 0})
            bucket[a["number"]] += 1
            if a.get("ambiguous"):
                bucket["ambiguous"] += 1
                ambiguous_total += 1
            lemmas[a["lemma"]] += 1
            t["cases"][a["case"]] += 1
            disputed_total += bool(a.get("disputed"))

    cl_info = {c["value"]: c for c in classifiers}
    scores = [r["alignment_score"] for r in records]
    low = build.get("low_score_threshold", 0.0)

    text_rows = []
    for meta in texts:
        t = per_text.get(meta["id"])
        if not t:
            continue
        n_articles = sum(t["articles"].values())
        n_cases = sum(t["cases"].values())
        text_rows.append({
            "id": meta["id"],
            "title": meta["title"],
            "title_ru": meta.get("title_ru", ""),
            "level": meta["level"],
            "pairs": t["pairs"],
            "articles": {k: t["articles"].get(k, 0) for k in ("the", "a", "an")},
            "classifiers": t["classifiers"],
            "cases": {c: t["cases"].get(c, 0) for c in CASE_ORDER if t["cases"].get(c, 0)},
            "nouns_ru": n_cases,
            "mean_score": round(statistics.fmean(t["scores"]), 3),
            "words": {"en": t["en_words"], "zh": t["zh_chars"], "ru": t["ru_words"]},
            "density": {
                "articles_per_100_words": round(100 * n_articles / t["en_words"], 1)
                if t["en_words"] else 0,
                "classifiers_per_100_chars": round(100 * t["classifiers"] / t["zh_chars"], 1)
                if t["zh_chars"] else 0,
                "nouns_per_100_words": round(100 * n_cases / t["ru_words"], 1)
                if t["ru_words"] else 0,
            },
        })

    levels: Counter[str] = Counter()
    for row in text_rows:
        levels[row["level"]] += row["pairs"]

    return {
        "generated_at": build["generated_at"],
        "totals": {
            "pairs": len(records),
            "texts": len(text_rows),
            "sentences": sentences,
            "tokens": tokens,
            "annotations": {
                "article": sum(articles.values()),
                "classifier": sum(cl_counts.values()),
                "case": sum(sum(v[n] for n in ("sing", "plur")) for v in cases.values()),
            },
            "distinct_classifiers": len(cl_counts),
            "ambiguous_cases": ambiguous_total,
            "disputed": disputed_total,
            "status": {s: status.get(s, 0) for s in ("auto", "checked", "corrected")},
            "llm_notes": sum(1 for r in records if r.get("llm_note")),
        },
        "levels": dict(sorted(levels.items())),
        "articles": {
            "counts": {k: articles.get(k, 0) for k in ("the", "a", "an")},
            "top_heads": {
                key: [{"lemma": w, "count": c} for w, c in counter.most_common(10)]
                for key, counter in article_heads.items()
            },
        },
        "classifiers": [
            {
                "value": value,
                "pinyin": cl_info.get(value, {}).get("pinyin", ""),
                "gloss": cl_info.get(value, {}).get("gloss", ""),
                "type": cl_info.get(value, {}).get("type", ""),
                "count": count,
                "nouns": [{"noun": n, "count": c} for n, c in cl_nouns[value].most_common(5)],
            }
            for value, count in cl_counts.most_common()
        ],
        "classifier_elliptical": elliptical,
        "cases": [
            {"case": c, "label": CASE_LABELS.get(c, c), **cases[c]}
            for c in CASE_ORDER if c in cases and (c != "voct" or sum(cases[c].values()))
        ],
        "top_lemmas_ru": [{"lemma": w, "count": c} for w, c in lemmas.most_common(15)],
        "alignment": {
            "method": build["alignment_method"],
            "low_score_threshold": low,
            "low_count": sum(1 for s in scores if s < low),
            "mean": round(statistics.fmean(scores), 3) if scores else 0,
            "median": round(statistics.median(scores), 3) if scores else 0,
            "types": dict(types.most_common()),
            "histogram": _histogram(scores, bins),
        },
        "texts": text_rows,
    }


def write_outputs(
    output_dir: Path,
    records: list[dict[str, Any]],
    texts: list[dict[str, Any]],
    classifiers: list[dict[str, Any]],
    build: dict[str, Any],
    delimiter: str = ",",
    bins: int = 10,
) -> dict[str, Any]:
    counts = Counter(r["text_id"] for r in records)
    texts_out = [{**t, "pairs": counts.get(t["id"], 0)} for t in texts]
    corpus = {
        "version": 2,
        **build,
        "texts": texts_out,
        "classifiers": classifiers,
        "pairs": records,
    }
    stats = compute_stats(records, texts_out, classifiers, build, bins)
    dump_json(output_dir / "corpus.json", corpus)
    dump_json(output_dir / "stats.json", stats)
    write_csv(output_dir / "corpus.csv", records, {t["id"]: t for t in texts_out}, delimiter)
    return stats
