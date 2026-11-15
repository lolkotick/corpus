"""Подсказки ИИ для режима «Проверка» (data/gold/hints.json) и согласие с ними эксперта.

    python -m pipeline hints-template [--size 99] [--seed 2026] [--blind 21]
    python -m pipeline hints-agreement [--gold …] [--hints …] [--out reports]

Подсказка — предварительный вердикт языковой модели по выравниванию или пометке.
Эталоном она не является: вердикт по каждой строке выносит эксперт в режиме
«Проверка», а в gold.json у пары ставится `hints_shown: true`, если подсказки при
этом были на экране (web/src/lib/hints.ts).

`hints-template` пишет заготовку: пары выборки, их текст и автоматические пометки с
пустыми вердиктами. Вердикты вписывает модель; pipeline их не придумывает.
Первые `--blind` пар выборки — контрольные: подсказки для них на сайте скрыты.

`hints-agreement` сравнивает вердикты эксперта и модели отдельно для пар,
проверенных вслепую и с подсказками. Согласие на парах «с подсказками» завышено
тем, что эксперт видел предложение модели; честная оценка — на парах «вслепую».
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.gold import LANGS, TARGETS, Gold, GoldError, load_gold, pair_complete, sample_pair_ids
from pipeline.metrics import format_ci, wilson
from pipeline.sources import DEFAULT_REGISTER
from pipeline.tables import md_table, write_csv

HINTS_FORMAT = "corpus-gold-hints"
HINTS_VERSION = 1
VERDICTS = ("correct", "wrong", "corrected")
VERDICT_LABEL = {"correct": "верно", "wrong": "ошибка", "corrected": "исправлено", None: "—"}
OBJECTS = {"align": "Выравнивание", "en": "Артикли (EN)", "zh": "量词 (ZH)", "ru": "Падежи (RU)"}
BLIND, ASSISTED = "вслепую", "с подсказками"
FIX_KEYS = {"en": ("head",), "zh": ("classifier", "head"), "ru": ("case", "lemma")}


class NoHintsData(Exception):
    """Сравнивать нечего: нет эталона, подсказок или общих проверенных пар."""


# ─── Заготовка ────────────────────────────────────────────────────────────


def _auto_label(lang: str, ann: dict[str, Any]) -> str:
    """Автоматическая пометка одной строкой — чтобы модель видела, что именно оценивает."""
    if lang == "ru":
        return f"{ann['text']}: падеж {ann.get('case', '')}, число {ann.get('number', '')}, " \
               f"лемма {ann.get('lemma', '')}"
    head = (ann.get("head") or {}).get("text") or "нет"
    det = (ann.get("det") or {}).get("text", "") if lang == "zh" else ""
    return f"{det}{ann['text']} → существительное: {head}"


def build_template(corpus: dict[str, Any], size: int, seed: int, strategy: str, blind: int,
                   source: str = "") -> dict[str, Any]:
    registers = {t["id"]: (t.get("register") or "").strip() or DEFAULT_REGISTER
                 for t in corpus.get("texts", [])}
    ids = sample_pair_ids(corpus["pairs"], size, seed, strategy, registers)
    by_id = {p["id"]: p for p in corpus["pairs"]}
    pairs = []
    for pair_id in ids:
        pair = by_id[pair_id]
        pairs.append({
            "id": pair_id,
            "_register": registers.get(pair["text_id"], DEFAULT_REGISTER),
            "_text": {lang: pair[lang] for lang in LANGS},
            "_sentences": pair.get("sentences", {}),
            "alignment": {t: {"verdict": None, "note": ""} for t in TARGETS},
            "items": {
                lang: [{"id": a["id"], "_auto": _auto_label(lang, a), "verdict": None,
                        "correction": None, "note": ""} for a in pair["annotations"][lang]]
                for lang in LANGS
            },
            "missed": {lang: [] for lang in LANGS},
        })
    return {
        "format": HINTS_FORMAT,
        "version": HINTS_VERSION,
        "_comment": (
            "Заготовка подсказок ИИ. Модель вписывает verdict (correct / wrong / corrected), "
            "для corrected — correction (en: head; zh: classifier, head; ru: case, lemma), "
            "пропуски — в missed (start, end, text в кодовых точках и те же поля), note — "
            "короткое обоснование. Поля с подчёркиванием — справочные, сайт их не читает."
        ),
        "source": source,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "corpus": {"generated_at": corpus.get("generated_at", "")},
        "sample": {"seed": seed, "size": len(ids), "strategy": strategy},
        "blind_pair_ids": ids[: max(0, blind)],
        "pairs": pairs,
    }


def write_template(corpus_path: Path, out: Path, size: int, seed: int, strategy: str,
                   blind: int, source: str = "", force: bool = False) -> tuple[int, list[Path]]:
    if out.exists() and not force:
        print(f"Файл {out} уже существует. Чтобы не стереть вписанные подсказки, "
              "он не перезаписан; для перезаписи добавьте --force.")
        return 1, []
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    template = build_template(corpus, size, seed, strategy, blind, source)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    items = sum(len(v) for p in template["pairs"] for v in p["items"].values())
    print(f"Заготовка: {len(template['pairs'])} пар, {items} пометок, "
          f"контрольных пар (вслепую): {len(template['blind_pair_ids'])}.")
    return 0, [out]


# ─── Чтение ───────────────────────────────────────────────────────────────


def load_hints(path: Path) -> dict[str, Any] | None:
    """None — файла нет; GoldError — файл есть, но это не подсказки."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GoldError(f"{path}: не JSON ({exc})") from exc
    if not isinstance(data, dict) or data.get("format") != HINTS_FORMAT:
        raise GoldError(f"{path}: это не файл подсказок (ожидается format = {HINTS_FORMAT})")
    if int(data.get("version", 0)) > HINTS_VERSION:
        raise GoldError(f"{path}: версия {data.get('version')} новее поддерживаемой")
    if not isinstance(data.get("pairs"), list):
        raise GoldError(f"{path}: нет списка pairs")
    return data


# ─── Согласие ─────────────────────────────────────────────────────────────


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def _same_fix(lang: str, a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    return all(_norm((a or {}).get(k)) == _norm((b or {}).get(k)) for k in FIX_KEYS[lang])


def _links(value: Any) -> set[tuple[int, int]]:
    return {(int(e), int(t)) for e, t in (value or [])}


@dataclass
class Decision:
    pair_id: str
    condition: str
    obj: str  # align | en | zh | ru
    target: str
    expert: str
    model: str
    same: bool
    expert_fix: str = ""
    model_fix: str = ""
    note: str = ""


@dataclass
class Agreement:
    decisions: list[Decision] = field(default_factory=list)
    missed: Counter[tuple[str, str, str]] = field(default_factory=Counter)
    pairs: Counter[str] = field(default_factory=Counter)
    skipped: int = 0

    def rows(self) -> list[list[Any]]:
        out: list[list[Any]] = []
        for condition in (BLIND, ASSISTED):
            for obj in [*OBJECTS, "all"]:
                chosen = [d for d in self.decisions
                          if d.condition == condition and obj in (d.obj, "all")]
                if not chosen:
                    continue
                same = sum(d.same for d in chosen)
                out.append([condition, OBJECTS.get(obj, "Все решения"), len(chosen), same,
                            same / len(chosen), format_ci(wilson(same, len(chosen))),
                            kappa(chosen)])
        return out


def kappa(decisions: list[Decision]) -> float | None:
    """Каппа Коэна по вердиктам (верно / ошибка / исправлено); None — посчитать нельзя."""
    n = len(decisions)
    if n == 0:
        return None
    observed = sum(d.expert == d.model for d in decisions) / n
    expert = Counter(d.expert for d in decisions)
    model = Counter(d.model for d in decisions)
    expected = sum(expert[v] * model[v] for v in VERDICTS) / (n * n)
    if expected >= 1:
        return None
    return (observed - expected) / (1 - expected)


def _fix_text(fix: dict[str, Any] | None, lang: str) -> str:
    return ", ".join(f"{k}: {(fix or {}).get(k) or '—'}" for k in FIX_KEYS[lang]) if fix else ""


def compare(gold: Gold, hints: dict[str, Any]) -> Agreement:
    hinted = {p["id"]: p for p in hints["pairs"]}
    result = Agreement()
    for pair in gold.pairs:
        hint = hinted.get(pair["id"])
        if hint is None or not pair_complete(pair):
            result.skipped += 1
            continue
        condition = ASSISTED if pair.get("hints_shown") else BLIND
        compared = False
        for target in TARGETS:
            h = (hint.get("alignment") or {}).get(target) or {}
            if h.get("verdict") not in VERDICTS:
                continue
            e = pair["alignment"][target]
            same = e["verdict"] == h["verdict"] and (
                h["verdict"] != "corrected" or not h.get("links")
                or _links(e.get("links")) == _links(h.get("links")))
            result.decisions.append(Decision(
                pair["id"], condition, "align", f"EN–{target.upper()}", e["verdict"],
                h["verdict"], same, note=h.get("note", "")))
            compared = True
        for lang in LANGS:
            by_id = {h["id"]: h for h in (hint.get("items") or {}).get(lang, [])}
            for item in pair["phenomena"][lang].get("items", []):
                h = by_id.get(item["id"]) or {}
                if h.get("verdict") not in VERDICTS or item.get("verdict") not in VERDICTS:
                    continue
                same = item["verdict"] == h["verdict"] and (
                    h["verdict"] != "corrected"
                    or _same_fix(lang, item.get("correction"), h.get("correction")))
                result.decisions.append(Decision(
                    pair["id"], condition, lang, item["auto"]["text"], item["verdict"],
                    h["verdict"], same, _fix_text(item.get("correction"), lang),
                    _fix_text(h.get("correction"), lang), h.get("note", "")))
                compared = True
            expert_missed = {(m["start"], m["end"]) for m in pair["phenomena"][lang]["missed"]}
            model_missed = {(m["start"], m["end"])
                            for m in (hint.get("missed") or {}).get(lang, [])}
            result.missed[(condition, lang, "оба")] += len(expert_missed & model_missed)
            result.missed[(condition, lang, "только эксперт")] += len(expert_missed - model_missed)
            result.missed[(condition, lang, "только модель")] += len(model_missed - expert_missed)
        if compared:
            result.pairs[condition] += 1
        else:
            result.skipped += 1
    return result


# ─── Отчёт ────────────────────────────────────────────────────────────────

HEAD = ["Условие", "Что сравнивается", "Решений", "Совпало", "Доля совпадений", "95% ДИ",
        "Каппа Коэна"]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def no_data_report(message: str, hints_path: Path, root: Path) -> str:
    return "\n".join([
        "# Согласие эксперта с подсказками ИИ",
        "",
        f"**Данных для сравнения нет:** {message}.",
        "",
        "Отчёт нужен, только если эталон размечался с подсказками ИИ:",
        "",
        f"1. `python -m pipeline hints-template` — заготовка `{_rel(hints_path, root)}`.",
        "2. Модель вписывает в заготовку вердикты и обоснования.",
        "3. Эксперт проверяет контрольные пары вслепую, остальные — с подсказками "
        "(сайт → «Проверка» → «Загрузить подсказки ИИ»), и экспортирует `gold.json`.",
        "4. `python -m pipeline hints-agreement`.",
        "",
        "Подсказки не являются эталоном; скрипт их не создаёт и не дополняет.",
        "",
    ])


def render_report(result: Agreement, gold: Gold, hints: dict[str, Any], files: list[Path],
                  gold_path: Path, hints_path: Path, root: Path) -> str:
    lines = ["# Согласие эксперта с подсказками ИИ", ""]
    if gold.synthetic or hints.get("synthetic"):
        lines += ["> **ВНИМАНИЕ: синтетические данные.** Файлы помечены как тестовые "
                  "(`synthetic: true`), числа ниже ничего не говорят о качестве подсказок.", ""]
    lines += [
        f"- Отчёт построен: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Эталон: `{_rel(gold_path, root)}`"
        + (f", эксперт: {gold.annotator}" if gold.annotator else ""),
        f"- Подсказки: `{_rel(hints_path, root)}`"
        + (f", источник: {hints['source']}" if hints.get("source") else ""),
        f"- Пар в сравнении: вслепую — **{result.pairs[BLIND]}**, с подсказками — "
        f"**{result.pairs[ASSISTED]}**; без сравнения (не проверены полностью или нет "
        f"подсказок): {result.skipped}",
        "",
        "## Совпадение вердиктов",
        "",
        md_table(HEAD, result.rows(), digits=3, align_right_from=2, text_columns=(5,)),
        "",
        "Решение — один вердикт по выравниванию или по пометке. Совпадение — тот же вердикт, "
        "а для «исправлено» ещё и то же исправление. Каппа Коэна поправляет долю совпадений "
        "на случайное согласие: вердикт «верно» встречается намного чаще остальных, поэтому "
        "доля совпадений высока даже при слабом согласии.",
        "",
        "**Как читать.** Пары «вслепую» эксперт проверял, не видя подсказок: это оценка того, "
        "насколько модель годится как предразметчик. На парах «с подсказками» согласие "
        "завышено, потому что эксперт видел предложение модели; разница между двумя "
        "условиями показывает возможный размер этого влияния.",
        "",
    ]
    missed_rows = [[condition, OBJECTS[lang], *[result.missed[(condition, lang, k)]
                                               for k in ("оба", "только эксперт", "только модель")]]
                   for condition in (BLIND, ASSISTED) if result.pairs[condition] for lang in LANGS]
    if missed_rows:
        lines += ["## Пропуски", "",
                  md_table(["Условие", "Явление", "Нашли оба", "Только эксперт", "Только модель"],
                           missed_rows, align_right_from=2), ""]
    lines += ["## Файлы", ""]
    lines += [f"- `{_rel(f, root)}`" for f in files]
    lines += ["", "Пересобрать: `python -m pipeline hints-agreement`.", ""]
    return "\n".join(lines)


def run(gold_path: Path, hints_path: Path, out: Path, root: Path) -> tuple[int, list[Path]]:
    """Код возврата (0 — отчёт или сообщение «нет данных», 1 — ошибка файла) и файлы."""
    report = out / "hints.md"
    try:
        gold = load_gold(gold_path)
        hints = load_hints(hints_path)
        if hints is None:
            raise NoHintsData(f"файл {_rel(hints_path, root)} не найден")
        if gold is None:
            raise NoHintsData(f"файл {_rel(gold_path, root)} не найден")
        result = compare(gold, hints)
        if not result.decisions:
            raise NoHintsData("в эталоне нет полностью проверенных пар, для которых модель "
                              "вписала вердикты")
    except NoHintsData as exc:
        print(f"Согласие с подсказками не посчитано: {exc}.")
        out.mkdir(parents=True, exist_ok=True)
        report.write_text(no_data_report(str(exc), hints_path, root), encoding="utf-8")
        return 0, [report]
    except GoldError as exc:
        print(f"Ошибка: {exc}")
        return 1, []
    out.mkdir(parents=True, exist_ok=True)
    files = [
        write_csv(out / "hints_agreement.csv", HEAD, result.rows()),
        write_csv(
            out / "hints_disagreements.csv",
            ["pair_id", "условие", "что", "слово или языки", "эксперт", "модель",
             "исправление эксперта", "исправление модели", "обоснование модели"],
            [[d.pair_id, d.condition, OBJECTS[d.obj], d.target, VERDICT_LABEL[d.expert],
              VERDICT_LABEL[d.model], d.expert_fix, d.model_fix, d.note]
             for d in result.decisions if not d.same],
        ),
    ]
    report.write_text(render_report(result, gold, hints, files, gold_path, hints_path, root),
                      encoding="utf-8")
    for row in result.rows():
        if row[1] == "Все решения":
            print(f"  {row[0]}: совпало {row[3]} из {row[2]}")
    return 0, [report, *files]
