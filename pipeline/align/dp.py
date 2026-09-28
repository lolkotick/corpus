"""Динамическое программирование для выравнивания предложений.

Общая часть для всех методов: метод задаёт только функцию стоимости «бусины»
(bead) — фрагмента src[i:i+di] ↔ tgt[j:j+dj]. DP ищет разбиение обоих текстов
на последовательные бусины разрешённых типов с минимальной суммарной стоимостью.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

CostFn = Callable[[int, int, int, int], float]


class AlignmentError(RuntimeError):
    """Выравнивание невозможно при заданных типах соответствий."""


@dataclass(frozen=True)
class Bead:
    """Соответствие src[src_start:src_end] ↔ tgt[tgt_start:tgt_end]."""

    src_start: int
    src_end: int
    tgt_start: int
    tgt_end: int
    score: float  # качество соответствия в диапазоне 0..1

    @property
    def type(self) -> str:
        return f"{self.src_end - self.src_start}-{self.tgt_end - self.tgt_start}"


def dp_align(
    n: int,
    m: int,
    cost: CostFn,
    types: Sequence[tuple[int, int]],
    band: int | None = None,
) -> list[tuple[int, int, int, int]]:
    """Вернуть список бусин (i, j, di, dj) минимальной суммарной стоимости.

    ``band`` ограничивает поиск диагональной полосой (для длинных текстов).
    """
    if n == 0 and m == 0:
        return []
    inf = math.inf
    best = [[inf] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    ratio = m / n if n else 0.0

    for i in range(n + 1):
        if band is not None and n and m:
            centre = i * ratio
            j_from = max(0, int(centre - band))
            j_to = min(m, int(centre + band) + 1)
        else:
            j_from, j_to = 0, m
        for j in range(j_from, j_to + 1):
            if i == 0 and j == 0:
                continue
            cell_best = inf
            cell_back = None
            for di, dj in types:
                pi, pj = i - di, j - dj
                if pi < 0 or pj < 0 or best[pi][pj] == inf:
                    continue
                total = best[pi][pj] + cost(pi, pj, di, dj)
                if total < cell_best:
                    cell_best = total
                    cell_back = (di, dj)
            best[i][j] = cell_best
            back[i][j] = cell_back

    if best[n][m] == inf:
        raise AlignmentError(
            f"не удалось выровнять {n} и {m} предложений разрешёнными типами {list(types)}"
        )

    beads: list[tuple[int, int, int, int]] = []
    i, j = n, m
    while i > 0 or j > 0:
        step = back[i][j]
        assert step is not None
        di, dj = step
        beads.append((i - di, j - dj, di, dj))
        i, j = i - di, j - dj
    beads.reverse()
    return beads


def allowed_types(types: Sequence[Sequence[int]], allow_skips: bool) -> list[tuple[int, int]]:
    result = [(int(a), int(b)) for a, b in types]
    if allow_skips:
        for extra in ((1, 0), (0, 1)):
            if extra not in result:
                result.append(extra)
    return result


def default_band(n: int, m: int) -> int | None:
    """Для коротких текстов — полный поиск, для длинных — полоса вокруг диагонали."""
    size = max(n, m)
    if size <= 200:
        return None
    return max(20, int(size * 0.1))
