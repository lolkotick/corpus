"""EN: артикли a / an / the и существительное, к которому они относятся (spaCy).

Разметка — позиции в символах внутри сегмента, текст не изменяется.
Если модель spaCy не установлена, используется запасной вариант на правилах
(артикль + следующее слово), о чём пишется предупреждение в журнал сборки.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from functools import cache
from typing import Any

log = logging.getLogger(__name__)

ARTICLES = {"a", "an", "the"}
_NOUN_POS = {"NOUN", "PROPN"}
_RULE_ARTICLE = re.compile(r"\b(the|an|a)\b\s+([A-Za-z][\w'-]*)", re.IGNORECASE)


def _span(token: Any) -> dict[str, Any]:
    return {"start": token.idx, "end": token.idx + len(token.text), "text": token.text}


def _article(token: Any, index: int) -> dict[str, Any]:
    value = token.lower_
    head = token.head
    ann: dict[str, Any] = {
        "id": f"en{index}",
        "kind": "article",
        **_span(token),
        "value": value,
        "definite": value == "the",
        "head": None,
        "disputed": False,
    }
    nxt = token.nbor(1) if token.i + 1 < len(token.doc) else None
    if nxt is not None and not nxt.is_punct:
        ann["next"] = _span(nxt)

    if head is token or head.i < token.i:
        ann["disputed"] = True
        ann["note"] = "не найдено существительное справа от артикля"
        return ann

    number = head.morph.get("Number")
    ann["head"] = {
        **_span(head),
        "lemma": head.lemma_.lower(),
        "pos": head.pos_,
        "number": {"Sing": "sing", "Plur": "plur"}.get(number[0]) if number else None,
    }
    if head.pos_ not in _NOUN_POS:
        ann["disputed"] = True
        ann["note"] = f"вершина артикля — {head.pos_}, а не существительное"
    elif head.i - token.i > 6:
        ann["disputed"] = True
        ann["note"] = "существительное далеко от артикля"
    return ann


def _annotate_rules(texts: Sequence[str]) -> list[list[dict[str, Any]]]:
    result = []
    for text in texts:
        anns = []
        for k, match in enumerate(_RULE_ARTICLE.finditer(text), start=1):
            word_start, word_end = match.span(2)
            anns.append(
                {
                    "id": f"en{k}",
                    "kind": "article",
                    "start": match.start(1),
                    "end": match.end(1),
                    "text": match.group(1),
                    "value": match.group(1).lower(),
                    "definite": match.group(1).lower() == "the",
                    "head": {"start": word_start, "end": word_end, "text": match.group(2),
                             "lemma": match.group(2).lower(), "pos": None, "number": None},
                    "next": {"start": word_start, "end": word_end, "text": match.group(2)},
                    "disputed": True,
                    "note": "разметка по правилам (без spaCy): вершина определена приблизительно",
                }
            )
        result.append(anns)
    return result


@cache
def load_spacy(model_name: str) -> Any:
    import spacy

    return spacy.load(model_name, disable=["ner"])


def annotate_en(
    texts: Sequence[str], model_name: str = "en_core_web_sm"
) -> tuple[list[list[dict[str, Any]]], str, list[str]]:
    """Вернуть (разметка по сегментам, метод, предупреждения)."""
    warnings: list[str] = []
    try:
        nlp = load_spacy(model_name)
    except (ImportError, OSError) as exc:
        message = (
            f"spaCy-модель {model_name} недоступна ({exc.__class__.__name__}); "
            "артикли размечены по правилам. Установите: python -m spacy download "
            f"{model_name}"
        )
        log.warning(message)
        warnings.append(message)
        return _annotate_rules(texts), "rules", warnings

    result = []
    for doc in nlp.pipe(texts, batch_size=64):
        anns = []
        for token in doc:
            if token.lower_ in ARTICLES and token.pos_ == "DET":
                anns.append(_article(token, len(anns) + 1))
        result.append(anns)
    return result, f"spacy:{model_name}", warnings
