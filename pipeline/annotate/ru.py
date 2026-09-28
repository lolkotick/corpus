"""RU: падеж, число и лемма существительных (pymorphy3).

pymorphy3 разбирает слово без контекста, поэтому добавлены два простых
контекстных фильтра, которые уменьшают омонимию:
1) предлог слева (через прилагательные): «в библиотеку» → только вин./предл.;
2) согласование с прилагательными слева: «в старом здании» → предл.;
3) числительные 2–4 / 5+ в им.–вин. падеже: «две книги» → род. ед.
Если после фильтров лучший разбор всё ещё неуверенный, разметка
помечается как спорная (ambiguous) и может быть проверена LLM или вручную.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from functools import cache
from typing import Any

CASE_LABELS = {
    "nomn": "именительный",
    "gent": "родительный",
    "datv": "дательный",
    "accs": "винительный",
    "ablt": "творительный",
    "loct": "предложный",
    "voct": "звательный",
}
# Второй родительный / предложный / винительный сводятся к основным падежам.
CASE_NORMALIZE = {"gen2": "gent", "loc2": "loct", "acc2": "accs", "gen1": "gent", "loc1": "loct"}

PREP_CASES: dict[str, set[str]] = {
    "без": {"gent"}, "безо": {"gent"},
    "в": {"accs", "loct"}, "во": {"accs", "loct"},
    "для": {"gent"}, "до": {"gent"},
    "за": {"accs", "ablt"},
    "из": {"gent"}, "изо": {"gent"}, "из-за": {"gent"}, "из-под": {"gent"},
    "к": {"datv"}, "ко": {"datv"},
    "кроме": {"gent"}, "между": {"ablt", "gent"},
    "на": {"accs", "loct"},
    "над": {"ablt"}, "надо": {"ablt"},
    "о": {"accs", "loct"}, "об": {"accs", "loct"}, "обо": {"accs", "loct"},
    "около": {"gent"}, "от": {"gent"}, "ото": {"gent"},
    "перед": {"ablt"}, "передо": {"ablt"},
    "по": {"datv", "accs"},
    "под": {"accs", "ablt"}, "подо": {"accs", "ablt"},
    "при": {"loct"}, "про": {"accs"}, "ради": {"gent"},
    "с": {"gent", "accs", "ablt"}, "со": {"gent", "accs", "ablt"},
    "сквозь": {"accs"}, "среди": {"gent"}, "у": {"gent"}, "через": {"accs"},
    "после": {"gent"}, "вокруг": {"gent"}, "возле": {"gent"}, "мимо": {"gent"},
    "против": {"gent"}, "вместо": {"gent"}, "вдоль": {"gent"}, "внутри": {"gent"},
    "напротив": {"gent"}, "благодаря": {"datv"}, "согласно": {"datv"},
    "навстречу": {"datv"}, "насчёт": {"gent"}, "насчет": {"gent"}, "вроде": {"gent"},
    "ввиду": {"gent"}, "вследствие": {"gent"}, "посреди": {"gent"}, "сверх": {"gent"},
}
_PAUCAL = {"два", "две", "три", "четыре", "оба", "обе", "полтора", "полторы"}
_ADJ_POS = {"ADJF", "PRTF"}
_SKIP_POS = {"ADJF", "PRTF", "ADVB", "NUMR"}


@cache
def get_morph():
    import pymorphy3

    return pymorphy3.MorphAnalyzer()


def _norm_case(case: str | None) -> str | None:
    if case is None:
        return None
    return CASE_NORMALIZE.get(case, case)


def _tokens(text: str) -> list[tuple[int, int, str]]:
    from razdel import tokenize

    return [(t.start, t.stop, t.text) for t in tokenize(text)]


def _is_word(token: str) -> bool:
    return any(ch.isalpha() for ch in token)


def _noun_candidates(parses: Sequence[Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Сгруппировать разборы-существительные по (падеж, число), суммируя вероятности."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    nouns = [p for p in parses if "NOUN" in p.tag]
    declinable = [p for p in nouns if "Fixd" not in p.tag]
    # «Анне»: если есть склоняемый разбор (Анна, дат. п.), несклоняемый омоним не нужен.
    for p in declinable or nouns:
        if "NOUN" not in p.tag:
            continue
        case = _norm_case(p.tag.case)
        if case is None:
            continue
        number = p.tag.number or "sing"
        key = (case, number)
        if key not in groups:
            groups[key] = {"score": 0.0, "parse": p}
        groups[key]["score"] += p.score
    return groups


def _adj_keys(parses: Sequence[Any]) -> set[tuple[str, str]]:
    keys = set()
    for p in parses:
        if p.tag.POS in _ADJ_POS and p.tag.case:
            keys.add((_norm_case(p.tag.case) or "", p.tag.number or "sing"))
    return keys


_NAME_TAGS = ("Surn", "Name", "Patr")
_NOT_NOUNS = {"напрокат", "наизусть", "нараспашку", "вдогонку"}  # наречия, которые pymorphy
_POSSESSIVES = {"его", "её", "ее", "их"}                           # считает существительными
_COPULAS = {"быть", "стать", "являться", "оставаться", "казаться", "становиться", "бывать"}
_CLAUSE_PUNCT = set(".;:!?—()«»\"")
_CLAUSE_WORDS = {"и", "а", "но", "что", "который", "которая", "которое", "которые", "которую",
                 "которого", "которой", "которым", "когда", "если", "потому", "поэтому", "где",
                 "как", "чтобы", "пока", "хотя", "поскольку", "однако"}


def _clause_ids(tokens: Sequence[tuple[int, int, str]]) -> list[int]:
    """Номер простого предложения (клаузы) для каждого токена."""
    ids = []
    clause = 0
    for k, (_s, _e, tok) in enumerate(tokens):
        next_word = tokens[k + 1][2].lower() if k + 1 < len(tokens) else ""
        if tok in _CLAUSE_PUNCT or tok in ("–", "...") or (
            tok == "," and next_word in _CLAUSE_WORDS
        ):
            clause += 1
        ids.append(clause)
    return ids


def _is_verb_homonym(k: int, parses: Sequence[Any], parsed: Sequence[Sequence[Any]]) -> bool:
    """«Анна села», «она села»: существительное-омоним глагола, согласованного с подлежащим."""
    verbs = [p for p in parses if p.tag.POS == "VERB" and p.score >= 0.05]
    if not verbs or k == 0 or not parsed[k - 1]:
        return False
    subject = parsed[k - 1][0]
    if subject.tag.POS not in ("NOUN", "NPRO") or subject.tag.case != "nomn":
        return False
    for verb in verbs:
        if verb.tag.number != subject.tag.number:
            continue
        if verb.tag.gender and subject.tag.gender and verb.tag.gender != subject.tag.gender:
            continue
        return True
    return False


_GENITIVE_WORDS = {"больше", "меньше", "много", "мало", "сколько", "столько", "немного"}


def _is_adjective_homonym(k: int, parses: Sequence[Any], parsed: Sequence[Sequence[Any]]) -> bool:
    """«дорогой роскошью»: слово-омоним прилагательного, согласованного со следующим словом."""
    if k + 1 >= len(parsed) or not parsed[k + 1] or "NOUN" not in parsed[k + 1][0].tag:
        return False
    adj = {(_norm_case(p.tag.case), p.tag.number) for p in parses
           if p.tag.POS in _ADJ_POS and p.score >= 0.02}
    nxt = {(_norm_case(p.tag.case), p.tag.number) for p in parsed[k + 1] if "NOUN" in p.tag}
    return bool(adj & nxt)


def _agrees(verb: Any, noun_number: str, noun_gender: str | None) -> bool:
    tag = verb.tag
    if tag.person and tag.person != "3per":
        return False
    if tag.number and tag.number != noun_number:
        return False
    return not (tag.gender and noun_gender and tag.number == "sing" and tag.gender != noun_gender)


def _keep(item: dict[str, Any], case: str, label: str) -> None:
    item["filtered"] = {key: v for key, v in item["filtered"].items() if key[0] == case}
    item["filters"].append(label)
    item["heuristic"] = True


def _resolve_by_clause(
    items: list[dict[str, Any]],
    tokens: Sequence[tuple[int, int, str]],
    parsed: Sequence[Sequence[Any]],
    clauses: Sequence[int],
) -> None:
    """Снять омонимию им./вин. (и род./вин.) по синтаксису простого предложения.

    * приложение: «император Шэньнун», «подруга Ли» — падеж как у предыдущего слова;
    * «у нас есть дом» — после «есть» стоит подлежащее (им. п.);
    * после переходного глагола при наличии подлежащего — прямое дополнение (вин. п.):
      «Она взяла зонт», «Караваны везли ящики»;
    * если в клаузе ещё нет подлежащего, существительное, согласованное с глаголом
      по числу и роду, — подлежащее (им. п.): «шёл дождь», «кошки спят».
    Все такие решения помечаются как эвристические (уверенность 0,85).
    """
    verbs: dict[int, list[tuple[int, Any, bool]]] = defaultdict(list)
    for k, parses in enumerate(parsed):
        if parses and parses[0].tag.POS in ("VERB", "INFN"):
            top = parses[0]
            # «выпивают»: tran/intr с равной вероятностью — переходность по той же лемме.
            transitive = any("tran" in p.tag for p in parses[:4]
                             if p.normal_form == top.normal_form and p.tag.POS == top.tag.POS)
            verbs[clauses[k]].append((k, top, transitive))

    def single(item: dict[str, Any]) -> str | None:
        cases = {key[0] for key in item["filtered"]}
        return next(iter(cases)) if len(cases) == 1 else None

    subject: dict[int, bool] = defaultdict(bool)
    for k, parses in enumerate(parsed):
        if parses and parses[0].tag.case == "nomn" and (
            parses[0].tag.POS == "NPRO" or parses[0].normal_form == "который"
        ):
            subject[clauses[k]] = True
    for item in items:
        if single(item) == "nomn":
            subject[clauses[item["k"]]] = True

    by_k = {item["k"]: item for item in items}
    for item in items:
        k = item["k"]
        clause = clauses[k]
        cases = {key[0] for key in item["filtered"]}
        if item["prep"] or len(cases) < 2:
            continue

        prev = by_k.get(k - 1)
        token = tokens[k][2]
        if prev is not None and token[:1].isupper() and single(prev) in cases:
            prev_parse = next(iter(prev["filtered"].values()))["parse"]
            if prev_parse.tag.animacy == "anim" and "Geox" not in parsed[k][0].tag:
                _keep(item, single(prev) or "", "приложение")
                continue

        if "nomn" in cases and any(
            tokens[i][2].lower() == "есть" and clauses[i] == clause for i in range(k)
        ):
            _keep(item, "nomn", "подлежащее при «есть»")
            subject[clause] = True
            continue

        clause_verbs = verbs.get(clause, [])
        transitive = [
            (v, p) for v, p, is_tran in clause_verbs
            if v < k and is_tran and p.normal_form not in _COPULAS
            and not (v > 0 and tokens[v - 1][2].lower() == "не")
        ]
        animate = any(v["parse"].tag.animacy == "anim" for v in item["filtered"].values())
        recipient = "datv" in cases and animate  # «выдала Анне билет» — адресат, не объект
        if "accs" in cases and transitive and not recipient:
            v, verb = transitive[-1]
            adjacent = all(
                parsed[i] and parsed[i][0].tag.POS in _SKIP_POS for i in range(v + 1, k)
            )
            has_subject = subject[clause] or verb.tag.POS == "INFN" or any(
                o["k"] < v and clauses[o["k"]] == clause
                and any(key[0] == "nomn" for key in o["filtered"]) for o in items
            )
            if has_subject and (cases <= {"nomn", "accs"} or adjacent):
                _keep(item, "accs", "дополнение при переходном глаголе")
                continue

        if "nomn" in cases and not subject[clause]:
            nomn_keys = [key for key in item["filtered"] if key[0] == "nomn"]
            gender = item["filtered"][nomn_keys[0]]["parse"].tag.gender
            agreeing = any(
                p.tag.POS == "VERB" and any(_agrees(p, key[1], gender) for key in nomn_keys)
                for _v, p, _tran in clause_verbs
            )
            if agreeing:
                _keep(item, "nomn", "подлежащее (согласование с глаголом)")
                subject[clause] = True


def annotate_ru_text(text: str, ambiguity_threshold: float = 0.8) -> list[dict[str, Any]]:
    morph = get_morph()
    tokens = _tokens(text)
    parsed = [morph.parse(tok) if _is_word(tok) else [] for _s, _e, tok in tokens]
    clauses = _clause_ids(tokens)
    items: list[dict[str, Any]] = []

    # Проход 1: существительные и локальный контекст (предлог, согласование, числительное).
    for k, (start, end, token) in enumerate(tokens):
        parses = parsed[k]
        if not parses or "NOUN" not in parses[0].tag or token.lower() in _NOT_NOUNS:
            continue
        best_parse = parses[0]
        if token[:1].islower() and any(t in best_parse.tag for t in _NAME_TAGS):
            continue  # «толстой» — прилагательное, а не фамилия
        if _is_verb_homonym(k, parses, parsed):
            continue  # «Анна села за стол»
        if _is_adjective_homonym(k, parses, parsed):
            continue  # «был дорогой роскошью»
        candidates = _noun_candidates(parses)
        if not candidates:
            continue
        indeclinable = "Fixd" in best_parse.tag

        adj_keys: list[set[tuple[str, str]]] = []
        prep: str | None = None
        numeral: Any = None
        left_noun = False
        quantity = False
        j = k - 1
        while j >= 0 and k - j <= 5:
            left = tokens[j][2].lower()
            left_parses = parsed[j]
            if left in PREP_CASES:
                prep = left
                break
            if not left_parses:
                break
            if left in _POSSESSIVES:  # «в окружающей их речи»
                j -= 1
                continue
            pos = left_parses[0].tag.POS
            if left in _GENITIVE_WORDS:
                quantity = True
                break
            if pos not in _SKIP_POS:
                left_noun = pos == "NOUN" and clauses[j] == clauses[k]
                break
            if pos in _ADJ_POS:
                adj_keys.append(_adj_keys(left_parses))
            elif pos == "NUMR" and numeral is None and j == k - 1 - len(adj_keys):
                numeral = left_parses[0]
            j -= 1

        filters: list[str] = []
        filtered = dict(candidates)
        rules: list[tuple[str, Any]] = []
        if prep:
            allowed = PREP_CASES[prep]
            rules.append(("предлог", lambda key, allowed=allowed: key[0] in allowed))
        else:
            # Предложный падеж без предлога не употребляется.
            rules.append(("нет предлога", lambda key: key[0] != "loct"))
        rules.append(("нет обращения", lambda key: key[0] != "voct"))
        for keys in adj_keys:
            rules.append(("согласование", lambda key, keys=keys: key in keys))
        if numeral is not None and not prep and _norm_case(numeral.tag.case) in ("nomn", "accs"):
            paucal = numeral.normal_form in _PAUCAL or numeral.word in _PAUCAL
            wanted = ("gent", "sing") if paucal else ("gent", "plur")
            rules.append(("числительное", lambda key, wanted=wanted: key == wanted))
        if quantity:
            rules.append(("родительный после «больше/много»", lambda key: key[0] == "gent"))
        if left_noun and not prep:
            rules.append(("родительный при существительном", lambda key: key[0] == "gent"))
        for label, keep in rules:
            narrowed = {key: v for key, v in filtered.items() if keep(key)}
            if narrowed and len(narrowed) < len(filtered):
                filtered = narrowed
                filters.append(label)

        items.append({
            "k": k, "start": start, "end": end, "token": token, "filtered": filtered,
            "filters": filters, "prep": prep, "indeclinable": indeclinable,
            "adjacent_left": j + 1 + len(adj_keys) if prep is None else None,
        })

    # Проход 2: порядок слов и согласование с глаголом внутри клаузы.
    _resolve_by_clause(items, tokens, parsed, clauses)

    anns: list[dict[str, Any]] = []
    for item in items:
        filtered = item["filtered"]
        total = sum(v["score"] for v in filtered.values()) or 1.0
        ranked = sorted(filtered.items(), key=lambda kv: kv[1]["score"], reverse=True)
        (case, number), best = ranked[0]
        confidence = best["score"] / total
        if item.get("heuristic"):
            confidence = min(confidence, 0.85)  # правило порядка слов — эвристика
        all_cases = {key[0] for key in _noun_candidates(parsed[item["k"]])}
        alternatives = sorted(c for c in all_cases if c != case) if confidence < 1 else []
        ambiguous = (confidence < ambiguity_threshold and bool(alternatives)) or (
            item["indeclinable"] and not item["filters"]
        )
        parse = best["parse"]
        ann: dict[str, Any] = {
            "id": f"ru{len(anns) + 1}",
            "kind": "case",
            "start": item["start"],
            "end": item["end"],
            "text": item["token"],
            "lemma": parse.normal_form,
            "case": case,
            "number": number,
            "gender": parse.tag.gender,
            "animacy": parse.tag.animacy,
            "confidence": round(confidence, 3),
            "ambiguous": ambiguous,
            "disputed": ambiguous,
        }
        if parse.tag.case and parse.tag.case != case:
            ann["subcase"] = parse.tag.case
        if item["prep"]:
            ann["prep"] = item["prep"]
        if item["filters"]:
            ann["context"] = item["filters"]
        if alternatives:
            ann["alternatives"] = alternatives
        if item["indeclinable"]:
            ann["indeclinable"] = True
        anns.append(ann)
    return anns


def annotate_ru(
    texts: Sequence[str], ambiguity_threshold: float = 0.8
) -> list[list[dict[str, Any]]]:
    return [annotate_ru_text(t, ambiguity_threshold) for t in texts]


def case_counts(annotations: Sequence[Sequence[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"sing": 0, "plur": 0})
    for anns in annotations:
        for ann in anns:
            counts[ann["case"]][ann["number"]] += 1
    return dict(counts)
