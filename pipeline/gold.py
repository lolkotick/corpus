"""Золотой стандарт (data/gold/gold.json): чтение, проверка и эталонные значения.

Файл создаёт эксперт вручную в режиме «Проверка» на сайте (web/src/lib/gold.ts);
этот модуль только читает его. Отсюда же берут данные evaluate.py,
compare_aligners.py и error_analysis.py.

Эталон восстанавливается из вердиктов:
- выравнивание: «верно» — автоматическая пара предложений и есть эталон;
  «исправление» — эталон задан списком связей [номер EN, номер ZH/RU];
  «ошибка» — известно только, что автоматический вариант неверен;
- пометки: «верно» — пометка входит в эталон как есть; «исправление» — входит
  с исправленными признаками; «ошибка» — ложное срабатывание (в эталон не входит);
  пропуски, добавленные экспертом, — тоже часть эталона.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GOLD_FORMAT = "corpus-gold"
GOLD_VERSION = 1
LANGS = ("en", "zh", "ru")
TARGETS = ("zh", "ru")
KIND_BY_LANG = {"en": "article", "zh": "classifier", "ru": "case"}


class GoldError(ValueError):
    """Файл эталона повреждён или имеет чужой формат."""


# ─── Выборка (порт samplePairIds из web/src/lib/gold.ts) ──────────────────

_MASK = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    return (a * b) & _MASK


def mulberry32(seed: int) -> Callable[[], float]:
    """Тот же генератор, что в web/src/lib/random.ts: одинаковые числа при одном seed."""
    state = seed & _MASK

    def random() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & _MASK
        t = state
        t = _imul(t ^ (t >> 15), t | 1)
        t = t ^ ((t + _imul(t ^ (t >> 7), t | 61)) & _MASK)
        return ((t ^ (t >> 14)) & _MASK) / 4294967296

    return random


def shuffle(items: Sequence[Any], random: Callable[[], float]) -> list[Any]:
    result = list(items)
    for i in range(len(result) - 1, 0, -1):
        j = int(random() * (i + 1))
        result[i], result[j] = result[j], result[i]
    return result


def sample_pair_ids(pairs: Iterable[dict[str, Any]], size: int, seed: int) -> list[str]:
    """Пропорциональная выборка по текстам (как в режиме «Проверка» на сайте)."""
    random = mulberry32(seed)
    by_text: dict[str, list[str]] = {}
    for pair in pairs:
        by_text.setdefault(pair["text_id"], []).append(pair["id"])
    keyed: list[tuple[float, str]] = []
    for ids in by_text.values():
        order = shuffle(ids, random)
        offset = random()
        keyed += [((k + offset) / len(order), pair_id) for k, pair_id in enumerate(order)]
    keyed.sort()
    return [pair_id for _, pair_id in keyed[: max(0, size)]]


# ─── Чтение файла ─────────────────────────────────────────────────────────


@dataclass
class Gold:
    path: Path
    data: dict[str, Any]

    @property
    def pairs(self) -> list[dict[str, Any]]:
        return list(self.data.get("pairs", []))

    @property
    def sample_ids(self) -> list[str]:
        return list(self.data.get("sample", {}).get("pair_ids", []))

    @property
    def synthetic(self) -> bool:
        return bool(self.data.get("synthetic"))

    @property
    def annotator(self) -> str:
        return str(self.data.get("annotator") or "")

    def complete_pairs(self) -> list[dict[str, Any]]:
        return [p for p in self.pairs if pair_complete(p)]


def load_gold(path: Path) -> Gold | None:
    """Прочитать gold.json. None — файла нет; GoldError — файл есть, но повреждён."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GoldError(f"{path}: не JSON ({exc})") from exc
    if not isinstance(data, dict) or data.get("format") != GOLD_FORMAT:
        raise GoldError(f"{path}: это не файл эталона (ожидается format = {GOLD_FORMAT})")
    if int(data.get("version", 0)) > GOLD_VERSION:
        raise GoldError(f"{path}: версия {data.get('version')} новее поддерживаемой")
    if not isinstance(data.get("pairs"), list):
        raise GoldError(f"{path}: нет списка pairs")
    for pair in data["pairs"]:
        for key in ("id", "text", "sentences", "alignment", "phenomena"):
            if key not in pair:
                raise GoldError(f"{path}: у пары {pair.get('id', '?')} нет поля {key}")
    return Gold(path, data)


def alignment_done(review: dict[str, Any]) -> bool:
    verdict = review.get("verdict")
    return verdict is not None and (verdict != "corrected" or bool(review.get("links")))


def lang_done(review: dict[str, Any]) -> bool:
    if review.get("mode") == "all-correct":
        return True
    return review.get("mode") == "itemized" and all(
        item.get("verdict") is not None for item in review.get("items", [])
    )


def pair_complete(pair: dict[str, Any]) -> bool:
    return all(alignment_done(pair["alignment"][t]) for t in TARGETS) and all(
        lang_done(pair["phenomena"][lang]) for lang in LANGS
    )


def is_stale(gold_pair: dict[str, Any], corpus_pair: dict[str, Any] | None) -> bool:
    """Текст пары изменился после проверки — сравнивать разметку нельзя."""
    if corpus_pair is None:
        return True
    return any(gold_pair["text"][lang] != corpus_pair[lang] for lang in LANGS)


# ─── Эталон выравнивания ──────────────────────────────────────────────────

Link = tuple[tuple[int, ...], tuple[int, ...]]


def link_components(links: Iterable[Sequence[int]]) -> list[Link]:
    """Связи «предложение–предложение» → группы (EN-предложения, предложения 2-го языка)."""
    parent: dict[tuple[str, int], tuple[str, int]] = {}

    def find(x: tuple[str, int]) -> tuple[str, int]:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e, t in links:
        a, b = find(("e", int(e))), find(("t", int(t)))
        if a != b:
            parent[b] = a
    groups: dict[tuple[str, int], tuple[set[int], set[int]]] = {}
    for node in list(parent):
        root = find(node)
        en, tgt = groups.setdefault(root, (set(), set()))
        (en if node[0] == "e" else tgt).add(node[1])
    return sorted((tuple(sorted(en)), tuple(sorted(tgt))) for en, tgt in groups.values())


@dataclass
class AlignmentTruth:
    """Эталон выравнивания одной пары для одного языка."""

    pair_id: str
    text_id: str
    lang: str
    verdict: str
    auto: Link
    gold: list[Link] = field(default_factory=list)

    @property
    def known(self) -> bool:
        return self.verdict in ("correct", "corrected")

    def gold_pairs(self) -> set[tuple[int, int]]:
        return {(e, t) for en, tgt in self.gold for e in en for t in tgt}


def alignment_truth(pair: dict[str, Any], lang: str) -> AlignmentTruth:
    review = pair["alignment"][lang]
    auto: Link = (tuple(pair["sentences"]["en"]), tuple(pair["sentences"][lang]))
    verdict = review["verdict"]
    if verdict == "correct":
        gold = [auto]
    elif verdict == "corrected":
        gold = link_components(review.get("links", []))
    else:
        gold = []
    return AlignmentTruth(pair["id"], pair["text_id"], lang, verdict, auto, gold)


# ─── Эталон разметки ─────────────────────────────────────────────────────


@dataclass
class TruthItem:
    """Эталонная пометка: позиция ключевого слова и признаки."""

    start: int
    end: int
    text: str
    head: str = ""
    case: str = ""
    lemma: str = ""
    source: str = ""  # correct | corrected | missed

    @property
    def key(self) -> tuple[int, int]:
        return (self.start, self.end)


@dataclass
class JudgedItem:
    """Автоматическая пометка из снимка и решение эксперта о ней."""

    id: str
    verdict: str
    auto: dict[str, Any]
    correction: dict[str, Any] | None


def _locate(text: str, needle: str, near: int) -> tuple[int, int] | None:
    """Найти needle в тексте ближе всего к позиции near (в кодовых точках)."""
    if not needle:
        return None
    best: tuple[int, int] | None = None
    start = text.find(needle)
    while start >= 0:
        if best is None or abs(start - near) < abs(best[0] - near):
            best = (start, start + len(needle))
        start = text.find(needle, start + 1)
    return best


def truth_items(pair: dict[str, Any], lang: str) -> tuple[list[TruthItem], list[JudgedItem]]:
    """Эталонные пометки языка и список оценённых автоматических пометок."""
    review = pair["phenomena"][lang]
    text = pair["text"][lang]
    items: list[TruthItem] = []
    judged: list[JudgedItem] = []
    for item in review.get("items", []):
        auto = item["auto"]
        verdict = item["verdict"]
        fix = item.get("correction") or {}
        judged.append(JudgedItem(item["id"], verdict, auto, item.get("correction")))
        if verdict == "wrong":
            continue
        truth = TruthItem(auto["start"], auto["end"], auto["text"], source=verdict)
        if lang == "en":
            truth.head = (fix.get("head") if verdict == "corrected"
                          else (auto.get("head") or {}).get("text", "")) or ""
        elif lang == "zh":
            truth.head = (fix.get("head") if verdict == "corrected"
                          else (auto.get("head") or {}).get("text", "")) or ""
            classifier = fix.get("classifier") if verdict == "corrected" else None
            if classifier and classifier != auto["text"]:
                span = _locate(text, classifier, auto["start"])
                if span:
                    truth.start, truth.end = span
                    truth.text = classifier
        else:
            truth.case = (fix.get("case") if verdict == "corrected" else auto["case"]) or ""
            truth.lemma = (fix.get("lemma") if verdict == "corrected" else auto["lemma"]) or ""
        items.append(truth)
    for missed in review.get("missed", []):
        items.append(TruthItem(
            missed["start"], missed["end"], missed["text"],
            head=missed.get("head", "") or "",
            case=missed.get("case", "") or "",
            lemma=missed.get("lemma", "") or "",
            source="missed",
        ))
    return items, judged
