"""Выравнивание Гейла–Чёрча (Gale & Church, 1993) по длине предложений.

Идея: длины переводных предложений пропорциональны. Разность длин после
нормализации распределена примерно нормально, поэтому вероятность
соответствия оценивается через δ = (l₂ − l₁) / √(s² · (l₁ + l₂) / 2).

Адаптация для EN–ZH: одна графема китайского письма соответствует в среднем
нескольким латинским буквам, поэтому длины второго языка умножаются на
отношение суммарных длин текстов (c = Σ|src| / Σ|tgt|).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from pipeline.align.dp import Bead, default_band, dp_align

DEFAULT_PRIORS = {"1-1": 0.89, "1-2": 0.0445, "2-1": 0.0445, "1-0": 0.0049, "0-1": 0.0049}
_MIN_PROB = 1e-12


def text_length(text: str) -> int:
    """Длина в символах без пробелов (для ZH пробелов почти нет, для EN/RU их вес мешает)."""
    return sum(1 for ch in text if not ch.isspace())


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def length_probability(l1: float, l2: float, variance: float) -> float:
    """Двусторонняя вероятность расхождения длин не меньше наблюдаемого (0..1)."""
    mean = (l1 + l2) / 2.0
    if mean <= 0:
        return 1.0
    delta = (l2 - l1) / math.sqrt(variance * mean)
    return max(_MIN_PROB, 2.0 * (1.0 - norm_cdf(abs(delta))))


def gale_church_align(
    src: Sequence[str],
    tgt: Sequence[str],
    types: Sequence[tuple[int, int]],
    variance: float = 6.8,
    priors: Mapping[str, float] | None = None,
) -> list[Bead]:
    priors = {**DEFAULT_PRIORS, **(priors or {})}
    src_len = [text_length(s) for s in src]
    tgt_len = [text_length(t) for t in tgt]
    total_src, total_tgt = sum(src_len), sum(tgt_len)
    ratio = total_src / total_tgt if total_src and total_tgt else 1.0
    tgt_norm = [length * ratio for length in tgt_len]

    # Префиксные суммы для быстрого подсчёта длины фрагмента.
    src_prefix = [0.0]
    for length in src_len:
        src_prefix.append(src_prefix[-1] + length)
    tgt_prefix = [0.0]
    for length in tgt_norm:
        tgt_prefix.append(tgt_prefix[-1] + length)

    def prob(i: int, j: int, di: int, dj: int) -> float:
        l1 = src_prefix[i + di] - src_prefix[i]
        l2 = tgt_prefix[j + dj] - tgt_prefix[j]
        return length_probability(l1, l2, variance)

    def cost(i: int, j: int, di: int, dj: int) -> float:
        prior = priors.get(f"{di}-{dj}", 1e-4)
        return -math.log(prior) - math.log(prob(i, j, di, dj))

    steps = dp_align(len(src), len(tgt), cost, types, band=default_band(len(src), len(tgt)))
    return [
        Bead(i, i + di, j, j + dj, round(prob(i, j, di, dj), 4) if di and dj else 0.0)
        for i, j, di, dj in steps
    ]
