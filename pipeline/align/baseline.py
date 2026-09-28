"""Базовый метод «по порядку»: i-е предложение соответствует i-му.

Нижняя граница для сравнения методов: так выравнивал бы тот, кто не смотрит ни
на длину, ни на смысл. Лишние предложения более длинного текста присоединяются
к последней группе.
"""

from __future__ import annotations

from collections.abc import Sequence

from pipeline.align.dp import AlignmentError, Bead


class DiagonalAligner:
    method = "diagonal"

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def align_pair(self, src: Sequence[str], tgt: Sequence[str], tgt_lang: str) -> tuple[
        list[Bead], str
    ]:
        if not src or not tgt:
            raise AlignmentError("пустой текст")
        n, m = len(src), len(tgt)
        k = min(n, m)
        beads = [Bead(i, i + 1, i, i + 1, 1.0) for i in range(k - 1)]
        beads.append(Bead(k - 1, n, k - 1, m, 1.0))
        return beads, self.method
