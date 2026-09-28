"""Обёртка над пакетом bertalign (https://github.com/bfsujason/bertalign).

Пакет bertalign 2.x требует Python ≥ 3.12, поэтому используется, только если он
установлен. Предложения передаются уже сегментированными (``is_split=True``),
чтобы сегментация была одинаковой для всех методов. Bertalign не возвращает
оценку для каждой бусины, поэтому score считается как косинусное сходство
эмбеддингов LaBSE частей бусины той же моделью.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from pipeline.align.dp import Bead


class BertalignBackend:
    def __init__(self, model_name: str) -> None:
        from bertalign import Bertalign  # noqa: F401 — проверяем, что пакет доступен
        from bertalign.encoder import get_encoder

        self.model_name = model_name
        self.encoder = get_encoder(model_name)

    def _embed(self, texts: list[str]) -> np.ndarray:
        vectors = self.encoder.model.encode(texts, normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float32)

    def align(
        self, src: Sequence[str], tgt: Sequence[str], src_joiner: str, tgt_joiner: str
    ) -> list[Bead]:
        from bertalign import Bertalign

        # max_align=3 даёт типы 1–1, 1–2, 2–1 (и пропуски 1–0 / 0–1).
        aligner = Bertalign(
            "\n".join(src), "\n".join(tgt), is_split=True, max_align=3, model=self.encoder
        )
        raw_beads = aligner.align_sents()

        beads: list[Bead] = []
        src_pos = tgt_pos = 0
        pieces_src: list[str] = []
        pieces_tgt: list[str] = []
        spans: list[tuple[int, int, int, int]] = []
        for src_idx, tgt_idx in raw_beads:
            s0 = src_idx[0] if src_idx else src_pos
            s1 = src_idx[-1] + 1 if src_idx else src_pos
            t0 = tgt_idx[0] if tgt_idx else tgt_pos
            t1 = tgt_idx[-1] + 1 if tgt_idx else tgt_pos
            spans.append((s0, s1, t0, t1))
            pieces_src.append(src_joiner.join(src[s0:s1]))
            pieces_tgt.append(tgt_joiner.join(tgt[t0:t1]))
            src_pos, tgt_pos = s1, t1

        src_vecs = self._embed(pieces_src)
        tgt_vecs = self._embed(pieces_tgt)
        for k, (s0, s1, t0, t1) in enumerate(spans):
            score = float(np.dot(src_vecs[k], tgt_vecs[k])) if s1 > s0 and t1 > t0 else 0.0
            beads.append(Bead(s0, s1, t0, t1, round(max(0.0, min(1.0, score)), 4)))
        return beads
