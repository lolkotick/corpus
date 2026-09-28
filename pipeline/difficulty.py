"""Оценка сложности тройки предложений по длине и частотности лексики.

Для каждого языка считаются две величины:

- длина: число слов (для китайского — слов по сегментации jieba), делённое на
  «длинное предложение» L (EN 30, RU 25, ZH 30) и ограниченное единицей;
- редкость лексики: доля слов, частотность которых ниже порога — Zipf < 4,0,
  то есть реже 10 употреблений на миллион слов (частоты — пакет wordfreq).

Оценка языка = 0,5 · длина + 0,5 · редкость; оценка тройки — среднее по трём
языкам (0 — очень просто, 1 — очень сложно). Шкала переводится в условные
уровни A1–C2 порогами (DEFAULT_THRESHOLDS, можно переопределить в config.yaml:
difficulty.thresholds). Это эвристика для сортировки и фильтров, а не
сертифицированный уровень CEFR.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
WFLANG = {"en": "en", "zh": "zh", "ru": "ru"}
LONG_SENTENCE = {"en": 30, "zh": 30, "ru": 25}
RARE_ZIPF = 4.0
# Границы A1|A2|B1|B2|C1|C2: середины между медианами оценок пар учебных текстов с
# уровнями, заданными авторами (A1 0,183; A2 0,204; B1 0,240; B2 0,316; C1 0,374;
# n = 110, ранговая корреляция Спирмена с авторским уровнем 0,575).
DEFAULT_THRESHOLDS = (0.19, 0.22, 0.28, 0.345, 0.45)


@dataclass(frozen=True)
class Difficulty:
    score: float
    level: str
    by_lang: Mapping[str, float]


@cache
def _wordfreq():  # type: ignore[no-untyped-def]
    import wordfreq

    return wordfreq


def lang_score(text: str, lang: str) -> float:
    wf = _wordfreq()
    tokens = [t for t in wf.tokenize(text, WFLANG[lang]) if any(ch.isalpha() for ch in t)]
    if not tokens:
        return 0.0
    length = min(len(tokens) / LONG_SENTENCE[lang], 1.0)
    rare = sum(wf.zipf_frequency(t, WFLANG[lang]) < RARE_ZIPF for t in tokens) / len(tokens)
    return 0.5 * length + 0.5 * rare


def to_level(score: float, thresholds: Sequence[float] = DEFAULT_THRESHOLDS) -> str:
    for level, bound in zip(LEVELS, thresholds, strict=False):
        if score < bound:
            return level
    return LEVELS[len(thresholds)] if len(thresholds) < len(LEVELS) else LEVELS[-1]


def estimate(texts: Mapping[str, str],
             thresholds: Sequence[float] = DEFAULT_THRESHOLDS) -> Difficulty:
    """texts — {"en": …, "zh": …, "ru": …}."""
    by_lang = {lang: round(lang_score(text, lang), 4) for lang, text in texts.items()}
    score = round(sum(by_lang.values()) / len(by_lang), 4) if by_lang else 0.0
    return Difficulty(score, to_level(score, thresholds), by_lang)
