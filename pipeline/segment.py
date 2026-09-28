"""Сегментация на предложения: pysbd (EN), razdel (RU), правила для ZH."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

DEFAULT_ZH_TERMINATORS = "。！？；…!?"
DEFAULT_ZH_CLOSING = "」』”’）》)\"'"


@cache
def _en_segmenter():  # pragma: no cover - тривиальная обёртка
    import pysbd

    return pysbd.Segmenter(language="en", clean=False, char_span=False)


def segment_en(paragraph: str) -> list[str]:
    """Английский: pysbd (правила Golden Rules, устойчив к сокращениям Mr., e.g. и т. п.)."""
    sentences = _en_segmenter().segment(paragraph)
    return [s.strip() for s in sentences if s.strip()]


def segment_ru(paragraph: str) -> list[str]:
    """Русский: razdel.sentenize (учитывает сокращения «т. е.», инициалы, прямую речь)."""
    from razdel import sentenize

    return [s.text.strip() for s in sentenize(paragraph) if s.text.strip()]


def segment_zh(
    paragraph: str,
    terminators: str = DEFAULT_ZH_TERMINATORS,
    closing: str = DEFAULT_ZH_CLOSING,
) -> list[str]:
    """Китайский: граница после серии знаков 。！？；… и следующих за ними 」”.

    Пример: «他说：“你好！”然后走了。» → «他说：“你好！”» + «然后走了。».
    Многоточие «……» и сочетания «！？» считаются одним концом предложения.
    """
    sentences: list[str] = []
    start = 0
    i = 0
    n = len(paragraph)
    while i < n:
        if paragraph[i] in terminators:
            j = i
            while j < n and paragraph[j] in terminators:
                j += 1
            while j < n and paragraph[j] in closing:
                ch = paragraph[j]
                # Прямые кавычки ASCII не различают открытие/закрытие: считаем кавычку
                # закрывающей, только если внутри текущего предложения их нечётное число.
                if ch in "\"'" and paragraph.count(ch, start, j) % 2 == 0:
                    break
                j += 1
            chunk = paragraph[start:j].strip()
            if chunk:
                sentences.append(chunk)
            start = j
            i = j
        else:
            i += 1
    tail = paragraph[start:].strip()
    if tail:
        # Хвост без знака конца (например, заголовок) — отдельное предложение,
        # а одиночные закрывающие знаки прикрепляем к предыдущему.
        if sentences and all(ch in closing for ch in tail):
            sentences[-1] += tail
        else:
            sentences.append(tail)
    return sentences


def get_segmenter(lang: str, config: dict | None = None) -> Callable[[str], list[str]]:
    config = config or {}
    if lang == "en":
        return segment_en
    if lang == "ru":
        return segment_ru
    if lang == "zh":
        terminators = config.get("zh_terminators", DEFAULT_ZH_TERMINATORS)
        closing = config.get("zh_closing", DEFAULT_ZH_CLOSING)
        return lambda paragraph: segment_zh(paragraph, terminators, closing)
    raise ValueError(f"Неизвестный язык: {lang}")


def segment_paragraphs(
    paragraphs: list[str], lang: str, config: dict | None = None
) -> list[list[str]]:
    """Сегментировать каждый абзац отдельно; возвращает список абзацев-предложений."""
    segmenter = get_segmenter(lang, config)
    return [segmenter(p) for p in paragraphs]


def join_sentences(sentences: list[str], lang: str) -> str:
    """Склеить предложения одного сегмента (для соответствий 1–2 / 2–1)."""
    return ("" if lang == "zh" else " ").join(sentences)
