"""Метрики качества: precision, recall, F1 и доверительные интервалы.

Оценка выравнивания вынесена сюда, потому что её используют и evaluate.py
(текущий корпус), и compare_aligners.py (несколько методов на одних текстах).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from pipeline.gold import AlignmentTruth, Link


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __iadd__(self, other: Counts) -> Counts:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn
        return self

    @property
    def predicted(self) -> int:
        return self.tp + self.fp

    @property
    def gold(self) -> int:
        return self.tp + self.fn

    @property
    def precision(self) -> float | None:
        return self.tp / self.predicted if self.predicted else None

    @property
    def recall(self) -> float | None:
        return self.tp / self.gold if self.gold else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None:
            return None
        return 2 * p * r / (p + r) if p + r else 0.0

    def precision_ci(self) -> tuple[float, float] | None:
        return wilson(self.tp, self.predicted)

    def recall_ci(self) -> tuple[float, float] | None:
        return wilson(self.tp, self.gold)


def wilson(successes: int, total: int, z: float = 1.959964) -> tuple[float, float] | None:
    """95% доверительный интервал Уилсона для доли (устойчив при малых выборках)."""
    if total <= 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def format_ci(ci: tuple[float, float] | None) -> str:
    if ci is None:
        return "—"
    return f"{ci[0]:.2f}–{ci[1]:.2f}".replace(".", ",")


# ─── Выравнивание ─────────────────────────────────────────────────────────


@dataclass
class PairAlignment:
    """Итог по одной проверенной паре: автоматический вариант, эталон и вариант метода."""

    pair_id: str
    text_id: str
    lang: str
    verdict: str
    auto: Link
    gold: list[Link]
    method: list[Link]
    ok: bool | None  # None — эталон неизвестен


@dataclass
class AlignmentScore:
    """Результат сравнения выравнивания с эталоном для одного языка (EN–ZH или EN–RU)."""

    strict: Counts = field(default_factory=Counts)  # совпадение групп предложений целиком
    lax: Counts = field(default_factory=Counts)  # совпадение пар «предложение–предложение»
    judged: int = 0  # проверенных пар
    unknown: int = 0  # «ошибка» без исправления: эталон неизвестен
    per_pair: list[PairAlignment] = field(default_factory=list)


def links_covering(links: Iterable[Link], en: Iterable[int]) -> list[Link]:
    wanted = set(en)
    return [link for link in links if wanted & set(link[0])]


def score_alignment(
    truths: Sequence[AlignmentTruth],
    predicted: Mapping[str, Sequence[Link]],
) -> AlignmentScore:
    """Сравнить выравнивание метода (predicted[text_id] — группы предложений) с эталоном.

    Строгая оценка: группа метода верна, только если совпадает с эталонной группой
    целиком (те же предложения EN и те же предложения второго языка). Мягкая оценка
    считает отдельные пары «предложение EN – предложение ZH/RU».
    Пары с вердиктом «ошибка» (без исправления) учитываются только в строгой
    точности: известно лишь, что автоматический вариант неверен.
    """
    score = AlignmentScore(judged=len(truths))
    by_text: dict[str, list[AlignmentTruth]] = {}
    for truth in truths:
        by_text.setdefault(truth.text_id, []).append(truth)

    for text_id, items in by_text.items():
        method_links = list(predicted.get(text_id, []))
        gold_links: set[Link] = set()
        gold_pairs: set[tuple[int, int]] = set()
        region: set[int] = set()
        known_wrong: set[Link] = set()
        for truth in items:
            if truth.known:
                gold_links.update(truth.gold)
                gold_pairs |= truth.gold_pairs()
                region |= set(truth.auto[0])
                for en, _ in truth.gold:
                    region |= set(en)
            else:
                known_wrong.add(truth.auto)
                score.unknown += 1

        in_region = {link for link in method_links if region & set(link[0])}
        wrong_hits = {link for link in method_links if link in known_wrong} - in_region
        tp = len(in_region & gold_links)
        score.strict += Counts(tp, len(in_region) - tp + len(wrong_hits),
                               len(gold_links - in_region))

        pred_pairs = {(e, t) for en, tgt in in_region for e in en for t in tgt if e in region}
        lax_tp = len(pred_pairs & gold_pairs)
        score.lax += Counts(lax_tp, len(pred_pairs) - lax_tp, len(gold_pairs - pred_pairs))

        for truth in items:
            covering = links_covering(method_links, truth.auto[0])
            if truth.known:
                ok = bool(covering) and all(link in gold_links for link in covering) and all(
                    link in covering for link in truth.gold
                    if set(link[0]) & set(truth.auto[0])
                )
            else:
                ok = False if truth.auto in covering else None
            score.per_pair.append(PairAlignment(truth.pair_id, text_id, truth.lang,
                                                truth.verdict, truth.auto, truth.gold,
                                                covering, ok))
    return score


def link_label(link: Link, lang: str) -> str:
    """((3,), (3, 4)) → «EN 4 ↔ ZH 4–5» (нумерация с единицы, как в интерфейсе)."""

    def ids(values: Sequence[int]) -> str:
        if not values:
            return "∅"
        if len(values) > 1 and list(values) == list(range(values[0], values[-1] + 1)):
            return f"{values[0] + 1}–{values[-1] + 1}"
        return ",".join(str(v + 1) for v in values)

    return f"EN {ids(link[0])} ↔ {lang.upper()} {ids(link[1])}"
