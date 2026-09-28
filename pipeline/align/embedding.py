"""Нейросетевое выравнивание по эмбеддингам LaBSE (алгоритм в духе Bertalign).

Как в Bertalign (Liu & Zhu, 2022):
* каждое предложение и каждая пара соседних предложений кодируются моделью
  LaBSE в общее для всех языков векторное пространство;
* сходство бусины — косинус между векторами её частей, умноженный на штраф
  за расхождение длин log₂(1 + min/max);
* DP максимизирует сумму сходств (здесь — минимизирует сумму со знаком минус).

Отличия от пакета bertalign: полный (или полосный) DP без первого прохода —
для учебных текстов в сотни предложений это быстро и точнее; нет сетевых
зависимостей для определения языка. Пакет bertalign 2.x требует Python ≥ 3.12,
поэтому для Python 3.11 используется эта реализация (см. также bertalign_backend.py).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np

from pipeline.align.dp import Bead, default_band, dp_align
from pipeline.align.gale_church import text_length

EmbedFn = Callable[[list[str]], np.ndarray]
SKIP_COST = 0.1  # штраф за пропуск (1–0 / 0–1), как skip = −0.1 в Bertalign


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _overlaps(sents: Sequence[str], size: int, joiner: str) -> list[str]:
    return [joiner.join(sents[i : i + size]) for i in range(len(sents))]


def embedding_align(
    src: Sequence[str],
    tgt: Sequence[str],
    embed: EmbedFn,
    types: Sequence[tuple[int, int]],
    src_joiner: str = " ",
    tgt_joiner: str = " ",
) -> list[Bead]:
    max_src = max((di for di, _ in types), default=1)
    max_tgt = max((dj for _, dj in types), default=1)

    # Векторы для фрагментов из 1..k подряд идущих предложений.
    src_vecs = {
        k: _normalize(np.asarray(embed(_overlaps(src, k, src_joiner)), dtype=np.float32))
        for k in range(1, max_src + 1)
    }
    tgt_vecs = {
        k: _normalize(np.asarray(embed(_overlaps(tgt, k, tgt_joiner)), dtype=np.float32))
        for k in range(1, max_tgt + 1)
    }

    src_len = [text_length(s) for s in src]
    tgt_len = [text_length(t) for t in tgt]
    ratio = (sum(src_len) / sum(tgt_len)) if sum(src_len) and sum(tgt_len) else 1.0

    def similarity(i: int, j: int, di: int, dj: int) -> float:
        return float(np.dot(src_vecs[di][i], tgt_vecs[dj][j]))

    def cost(i: int, j: int, di: int, dj: int) -> float:
        if di == 0 or dj == 0:
            return SKIP_COST
        l1 = sum(src_len[i : i + di])
        l2 = sum(tgt_len[j : j + dj]) * ratio
        penalty = math.log2(1 + min(l1, l2) / max(l1, l2)) if l1 and l2 else 0.0
        return -similarity(i, j, di, dj) * penalty

    steps = dp_align(len(src), len(tgt), cost, types, band=default_band(len(src), len(tgt)))
    beads = []
    for i, j, di, dj in steps:
        score = max(0.0, min(1.0, similarity(i, j, di, dj))) if di and dj else 0.0
        beads.append(Bead(i, i + di, j, j + dj, round(score, 4)))
    return beads


class LabseEncoder:
    """Обёртка над sentence-transformers; модель скачивается при первом запуске (~1,8 ГБ)."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def __call__(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype=np.float32)
