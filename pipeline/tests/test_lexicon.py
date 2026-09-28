import json

from pipeline.build import run_build
from pipeline.lexicon import Occurrence, competitive_links, dice_table
from pipeline.tests.conftest import requires_spacy


def occ(lang, lemma, pos, start=0):
    return Occurrence(lang, lemma, start, start + len(lemma), pos)


def test_dice_requires_repeated_cooccurrence():
    ru = [[occ("ru", "книга", 0.5)], [occ("ru", "книга", 0.2)], [occ("ru", "чай", 0.1)]]
    en = [[occ("en", "book", 0.5)], [occ("en", "book", 0.3)], [occ("en", "tea", 0.1)]]
    table = dice_table(ru, en)
    assert table == {("книга", "book"): 1.0}  # «чай / tea» встретились лишь однажды


def test_competitive_linking_uses_position_to_break_ties():
    # «Мужчина подарил мне апельсин» / «The man gave me an orange»: Dice одинаковый.
    table = {(a, b): 1.0 for a in ("мужчина", "апельсин") for b in ("man", "orange")}
    ru = [occ("ru", "мужчина", 0.0), occ("ru", "апельсин", 0.8, 20)]
    en = [occ("en", "man", 0.1, 4), occ("en", "orange", 0.85, 24)]
    links = {(a.lemma, b.lemma) for a, b, _ in competitive_links(ru, en, table)}
    assert links == {("мужчина", "man"), ("апельсин", "orange")}


@requires_spacy
def test_links_in_example(project):
    run_build(project, use_llm=False)
    corpus = json.loads((project.path("output") / "corpus.json").read_text(encoding="utf-8"))
    pair = next(p for p in corpus["pairs"] if p["en"].startswith("Anna wanted to find a book"))
    words = []
    for link in pair["links"]:
        spans = {lang: link[lang] for lang in ("en", "zh", "ru") if lang in link}
        words.append({lang: pair[lang][s:e] for lang, (s, e) in spans.items()})
    assert {"en": "book", "zh": "书", "ru": "книгу"} in words
