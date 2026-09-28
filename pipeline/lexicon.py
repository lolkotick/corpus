"""Переводные эквиваленты существительных внутри пар (для подсветки в поиске).

Метод — классический для извлечения двуязычного словаря из параллельного корпуса:
1) в каждой паре собираются существительные: EN — spaCy (NOUN/PROPN, лемма),
   ZH — jieba (теги n*) и существительные из разметки 量词, RU — леммы из разметки;
2) по всему корпусу считается коэффициент Дайса для пар лемм
   Dice(x, y) = 2·c(x, y) / (c(x) + c(y)), где c — число пар, в которых встретилось слово;
3) в каждой паре слова связываются «конкурентным связыванием» (Melamed, 2000):
   жадно берётся лучшая по оценке связь, её слова больше не участвуют.
   Оценка = Dice − 0,5 · |разница относительных позиций в предложении| — позиция
   разрешает ничьи вроде «мужчина / man / orange» в «Мужчина подарил мне апельсин».
Связи EN–RU, EN–ZH и RU–ZH объединяются в группы по общим словам.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

LANG_PAIRS = (("en", "ru"), ("en", "zh"), ("ru", "zh"))
MIN_COOCCURRENCE = 2
MIN_DICE = 0.5
POSITION_WEIGHT = 0.5
# jieba иногда помечает как существительные глаголы и служебные слова.
_ZH_NOT_NOUNS = {"回家", "时", "时候", "东西", "以后", "之后", "之一", "工作"}


@dataclass(frozen=True)
class Occurrence:
    lang: str
    lemma: str
    start: int
    end: int
    relpos: float


def en_nouns(texts: Sequence[str], model_name: str) -> list[list[Occurrence]] | None:
    try:
        from pipeline.annotate.en import load_spacy

        nlp = load_spacy(model_name)
    except (ImportError, OSError):
        return None
    result = []
    for doc in nlp.pipe(texts, batch_size=64):
        length = max(1, len(doc.text))
        result.append([
            Occurrence("en", t.lemma_.lower(), t.idx, t.idx + len(t.text), t.idx / length)
            for t in doc if t.pos_ in ("NOUN", "PROPN") and t.is_alpha
        ])
    return result


def zh_nouns(texts: Sequence[str], annotations: Sequence[Sequence[dict[str, Any]]]
             ) -> list[list[Occurrence]]:
    from pipeline.annotate.zh import tokenize

    result = []
    for text, anns in zip(texts, annotations, strict=True):
        length = max(1, len(text))
        occ: dict[tuple[int, int], Occurrence] = {}
        # Существительные из разметки 量词 надёжнее токенов jieba («三本书» → 书).
        for ann in anns:
            head = ann.get("head")
            if head:
                occ[(head["start"], head["end"])] = Occurrence(
                    "zh", head["text"], head["start"], head["end"], head["start"] / length)
        covered = {i for s, e in occ for i in range(s, e)}
        for start, end, word, tag in tokenize(text):
            if word in _ZH_NOT_NOUNS:
                continue
            if tag.startswith("n") and not covered.intersection(range(start, end)):
                occ[(start, end)] = Occurrence("zh", word, start, end, start / length)
        result.append(sorted(occ.values(), key=lambda o: o.start))
    return result


def ru_nouns(texts: Sequence[str], annotations: Sequence[Sequence[dict[str, Any]]]
             ) -> list[list[Occurrence]]:
    result = []
    for text, anns in zip(texts, annotations, strict=True):
        length = max(1, len(text))
        result.append([
            Occurrence("ru", a["lemma"], a["start"], a["end"], a["start"] / length) for a in anns
        ])
    return result


def dice_table(a_side: Sequence[Sequence[Occurrence]], b_side: Sequence[Sequence[Occurrence]]
               ) -> dict[tuple[str, str], float]:
    count_a: Counter[str] = Counter()
    count_b: Counter[str] = Counter()
    joint: Counter[tuple[str, str]] = Counter()
    for occ_a, occ_b in zip(a_side, b_side, strict=True):
        lemmas_a = {o.lemma for o in occ_a}
        lemmas_b = {o.lemma for o in occ_b}
        count_a.update(lemmas_a)
        count_b.update(lemmas_b)
        joint.update((x, y) for x in lemmas_a for y in lemmas_b)
    table = {}
    for (x, y), c in joint.items():
        if c < MIN_COOCCURRENCE:
            continue
        dice = 2 * c / (count_a[x] + count_b[y])
        if dice >= MIN_DICE:
            table[(x, y)] = round(dice, 3)
    return table


def competitive_links(occ_a: Sequence[Occurrence], occ_b: Sequence[Occurrence],
                      table: dict[tuple[str, str], float]
                      ) -> list[tuple[Occurrence, Occurrence, float]]:
    candidates = []
    for a in occ_a:
        for b in occ_b:
            dice = table.get((a.lemma, b.lemma))
            if dice is not None:
                score = dice - POSITION_WEIGHT * abs(a.relpos - b.relpos)
                candidates.append((score, dice, a, b))
    candidates.sort(key=lambda c: (-c[0], c[2].start, c[3].start))
    used_a: set[Occurrence] = set()
    used_b: set[Occurrence] = set()
    links = []
    for score, dice, a, b in candidates:
        if a in used_a or b in used_b or score <= 0:
            continue
        used_a.add(a)
        used_b.add(b)
        links.append((a, b, dice))
    return links


def _find(parent: dict[Occurrence, Occurrence], occ: Occurrence) -> Occurrence:
    """Корень группы в системе непересекающихся множеств."""
    while parent.setdefault(occ, occ) != occ:
        occ = parent[occ]
    return occ


def build_links(records: list[dict[str, Any]], spacy_model: str
                ) -> tuple[dict[str, int], list[str]]:
    """Добавить к каждой записи поле `links` и вернуть статистику словаря."""
    warnings: list[str] = []
    en = en_nouns([r["en"] for r in records], spacy_model)
    if en is None:
        warnings.append("эквиваленты не построены: нет spaCy-модели для английского")
        for r in records:
            r["links"] = []
        return {"entries": 0, "links": 0}, warnings
    nouns = {
        "en": en,
        "zh": zh_nouns([r["zh"] for r in records], [r["annotations"]["zh"] for r in records]),
        "ru": ru_nouns([r["ru"] for r in records], [r["annotations"]["ru"] for r in records]),
    }
    tables = {pair: dice_table(nouns[pair[0]], nouns[pair[1]]) for pair in LANG_PAIRS}

    total_links = 0
    for i, record in enumerate(records):
        parent: dict[Occurrence, Occurrence] = {}
        scores: dict[Occurrence, float] = {}
        for a_lang, b_lang in LANG_PAIRS:
            for a, b, dice in competitive_links(nouns[a_lang][i], nouns[b_lang][i],
                                                tables[(a_lang, b_lang)]):
                parent[_find(parent, a)] = _find(parent, b)
                scores[a] = max(scores.get(a, 0.0), dice)
                scores[b] = max(scores.get(b, 0.0), dice)

        groups: dict[Occurrence, list[Occurrence]] = {}
        for occ in parent:
            groups.setdefault(_find(parent, occ), []).append(occ)
        links = []
        for members in groups.values():
            link: dict[str, Any] = {}
            for occ in sorted(members, key=lambda o: (o.lang, o.start)):
                link.setdefault(occ.lang, [occ.start, occ.end])
            if len(link) >= 2:
                link["score"] = round(max(scores.get(o, 0.0) for o in members), 3)
                links.append(link)
        links.sort(key=lambda lk: lk.get("en", lk.get("ru", [0]))[0])
        record["links"] = links
        total_links += len(links)

    entries = sum(len(t) for t in tables.values())
    log.info("  словарь эквивалентов: %s пар лемм, %s связей в корпусе", entries, total_links)
    return {"entries": entries, "links": total_links}, warnings


def lexicon_pairs(records: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Для отладки и отчёта: тексты связанных слов (en, zh, ru) по всему корпусу."""
    rows = []
    for r in records:
        for link in r.get("links", []):
            parts = [r[lang][link[lang][0]:link[lang][1]] if lang in link else "—"
                     for lang in ("en", "zh", "ru")]
            rows.append((parts[0], parts[1], parts[2]))
    return rows

