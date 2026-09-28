"""Трёхъязычное выравнивание с опорным языком (EN).

EN–ZH и EN–RU выравниваются независимо, затем результаты объединяются по
английским предложениям: граница между сегментами остаётся, только если её
поставили оба попарных выравнивания. Так получаются тройки вида 1–1–1,
1–2–1, 2–1–2 и т. п.
"""

from __future__ import annotations

import logging
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from pipeline.align.dp import AlignmentError, Bead, allowed_types
from pipeline.align.gale_church import gale_church_align
from pipeline.segment import join_sentences

log = logging.getLogger(__name__)

__all__ = [
    "AlignedSegment",
    "Aligner",
    "AlignmentError",
    "Bead",
    "align_three",
    "create_aligner",
    "merge_on_pivot",
]


@dataclass
class AlignedSegment:
    en: list[str]
    zh: list[str]
    ru: list[str]
    en_zh: float
    en_ru: float
    method: str

    @property
    def alignment_type(self) -> str:
        return f"{len(self.en)}-{len(self.zh)}-{len(self.ru)}"

    @property
    def score(self) -> float:
        """Итоговая оценка — по самому слабому из двух попарных соответствий."""
        return round(min(self.en_zh, self.en_ru), 4)

    def text(self, lang: str) -> str:
        return join_sentences(getattr(self, lang), lang)


class _GaleChurchBackend:
    name = "gale_church"

    def __init__(self, config: dict, types: list[tuple[int, int]]) -> None:
        self.config = config
        self.types = types

    def align_pair(self, src: Sequence[str], tgt: Sequence[str], tgt_lang: str) -> list[Bead]:
        gc = self.config.get("gale_church", {})
        variance = float(gc.get("variance", {}).get(tgt_lang, 6.8))
        return gale_church_align(src, tgt, self.types, variance=variance, priors=gc.get("priors"))


@dataclass
class Aligner:
    """Выбранный метод выравнивания и история переключений на запасной метод."""

    method: str
    config: dict
    types: list[tuple[int, int]]
    backend: object | None = None
    warnings: list[str] = field(default_factory=list)

    def align_pair(self, src: Sequence[str], tgt: Sequence[str], tgt_lang: str) -> tuple[
        list[Bead], str
    ]:
        """Выровнять пару; при сбое нейросетевого метода — Гейл–Чёрч для этого текста."""
        if not src or not tgt:
            raise AlignmentError("пустой текст")
        if self.method in ("labse", "bertalign") and self.backend is not None:
            try:
                return self._align_neural(src, tgt, tgt_lang), self.method
            except Exception as exc:
                message = f"{self.method}: ошибка на паре EN–{tgt_lang.upper()} ({exc}); " \
                    "использован Гейл–Чёрч"
                log.warning(message)
                self.warnings.append(message)
        gc = _GaleChurchBackend(self.config, self.types)
        return gc.align_pair(src, tgt, tgt_lang), "gale_church"

    def _align_neural(self, src: Sequence[str], tgt: Sequence[str], tgt_lang: str) -> list[Bead]:
        tgt_joiner = "" if tgt_lang == "zh" else " "
        if self.method == "bertalign":
            return self.backend.align(src, tgt, " ", tgt_joiner)  # type: ignore[union-attr]
        from pipeline.align.embedding import embedding_align

        return embedding_align(src, tgt, self.backend, self.types, " ", tgt_joiner)  # type: ignore[arg-type]


def create_aligner(config: dict) -> Aligner:
    """Выбрать метод: bertalign → LaBSE → Гейл–Чёрч (для method: auto)."""
    requested = str(config.get("method", "auto")).lower()
    types = allowed_types(config.get("types", [[1, 1], [1, 2], [2, 1]]),
                          bool(config.get("allow_skips", True)))
    model = str(config.get("model", "sentence-transformers/LaBSE"))
    warnings: list[str] = []

    candidates = ["bertalign", "labse", "gale_church"] if requested == "auto" else [requested]
    if requested not in ("auto", "bertalign", "labse", "gale_church"):
        raise ValueError(f"Неизвестный метод выравнивания: {requested}")

    for method in candidates:
        if method == "gale_church":
            return Aligner("gale_church", config, types, None, warnings)
        try:
            if method == "bertalign":
                from pipeline.align.bertalign_backend import BertalignBackend

                backend: object = BertalignBackend(model)
            else:
                from pipeline.align.embedding import LabseEncoder

                backend = LabseEncoder(model)
            return Aligner(method, config, types, backend, warnings)
        except ImportError as exc:
            warnings.append(f"{method}: пакет не установлен ({exc.name or exc})")
        except Exception as exc:
            warnings.append(f"{method}: не удалось загрузить модель {model} ({exc})")

    # Метод задан явно, но недоступен — честно переходим на Гейла–Чёрча.
    warnings.append(f"{requested}: недоступен, используется запасной метод Гейла–Чёрча")
    return Aligner("gale_church", config, types, None, warnings)


def _en_cuts(beads: Sequence[Bead], n: int) -> set[int]:
    return {b.src_end for b in beads if b.src_end > b.src_start and 0 < b.src_end < n}


def merge_on_pivot(
    en: Sequence[str],
    zh: Sequence[str],
    ru: Sequence[str],
    zh_beads: Sequence[Bead],
    ru_beads: Sequence[Bead],
    method: str,
) -> list[AlignedSegment]:
    """Объединить попарные выравнивания EN–ZH и EN–RU в тройки."""
    n = len(en)
    cuts = sorted(_en_cuts(zh_beads, n) & _en_cuts(ru_beads, n))
    bounds = [0, *cuts, n]
    groups = list(pairwise(bounds))

    def group_of(index: int) -> int:
        return bisect_right(bounds, index) - 1

    def collect(beads: Sequence[Bead]) -> list[tuple[int, int, float]]:
        """Для каждой группы: диапазон второго языка и минимальный score."""
        result: list[list[float]] = [[float("inf"), -1.0, 1.0] for _ in groups]
        for bead in beads:
            if bead.src_end > bead.src_start:
                target = group_of(bead.src_start)
            else:
                # Пропуск 0–1 присоединяем к группе предыдущего английского предложения.
                target = group_of(max(0, bead.src_start - 1))
            slot = result[target]
            if bead.tgt_end > bead.tgt_start:
                slot[0] = min(slot[0], bead.tgt_start)
                slot[1] = max(slot[1], bead.tgt_end)
            slot[2] = min(slot[2], bead.score)
        spans = []
        prev_end = 0
        for start, end, score in result:
            if end < 0:  # во второй язык ничего не попало (1–0)
                spans.append((prev_end, prev_end, 0.0))
            else:
                spans.append((int(start), int(end), score))
                prev_end = int(end)
        return spans

    zh_spans = collect(zh_beads)
    ru_spans = collect(ru_beads)
    segments = []
    for (a, b), (zs, ze, zscore), (rs, re_, rscore) in zip(groups, zh_spans, ru_spans,
                                                           strict=True):
        segments.append(
            AlignedSegment(
                en=list(en[a:b]),
                zh=list(zh[zs:ze]),
                ru=list(ru[rs:re_]),
                en_zh=round(zscore, 4),
                en_ru=round(rscore, 4),
                method=method,
            )
        )
    return segments


def align_three(
    aligner: Aligner, en: Sequence[str], zh: Sequence[str], ru: Sequence[str]
) -> list[AlignedSegment]:
    zh_beads, zh_method = aligner.align_pair(en, zh, "zh")
    ru_beads, ru_method = aligner.align_pair(en, ru, "ru")
    method = zh_method if zh_method == ru_method else f"{zh_method}+{ru_method}"
    return merge_on_pivot(en, zh, ru, zh_beads, ru_beads, method)
