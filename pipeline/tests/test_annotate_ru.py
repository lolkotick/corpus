import pytest

from pipeline.annotate.ru import annotate_ru_text


def cases(text):
    return {a["text"]: (a["lemma"], a["case"], a["number"]) for a in annotate_ru_text(text)}


def test_offsets_lemma_case_number():
    text = "Анна пошла в городскую библиотеку."
    anns = annotate_ru_text(text)
    assert [(a["text"], a["lemma"], a["case"], a["number"]) for a in anns] == [
        ("Анна", "анна", "nomn", "sing"),
        ("библиотеку", "библиотека", "accs", "sing"),
    ]
    for ann in anns:
        assert text[ann["start"]:ann["end"]] == ann["text"]


@pytest.mark.parametrize(
    ("text", "word", "case"),
    [
        ("Библиотека находится в старом здании у реки.", "здании", "loct"),
        ("Библиотека находится в старом здании у реки.", "реки", "gent"),
        ("В зале стояло около двадцати столов.", "столов", "gent"),
        ("Мы гуляем в лесу.", "лесу", "loct"),              # второй предложный → предложный
        ("Анна хотела найти книгу по истории Китая.", "истории", "datv"),
        ("Она пошла в кафе с мамой.", "мамой", "ablt"),
        ("Считается, что дети улавливают закономерности в окружающей их речи.", "речи", "loct"),
    ],
)
def test_prepositions_and_agreement(text, word, case):
    assert cases(text)[word][1] == case


def test_subcase_is_kept():
    ann = next(a for a in annotate_ru_text("Мы гуляем в лесу.") if a["text"] == "лесу")
    assert ann["case"] == "loct" and ann["subcase"] == "loc2"
    assert ann["prep"] == "в"


def test_numerals_two_to_four_and_five_plus():
    assert cases("Она взяла две книги.")["книги"] == ("книга", "gent", "sing")
    assert cases("Он купил пять книг.")["книг"] == ("книга", "gent", "plur")


def test_locative_requires_preposition():
    # «Анне» без предлога — дательный, а не предложный
    assert cases("Женщина выдала Анне билет.")["Анне"][1] == "datv"


@pytest.mark.parametrize(
    ("text", "word", "case"),
    [
        ("Она взяла зонт, тетрадь и две ручки.", "зонт", "accs"),
        ("Мама готовит большой салат.", "салат", "accs"),
        ("На улице всё ещё шёл дождь.", "дождь", "nomn"),
        ("Кошки целый день спят на диване.", "Кошки", "nomn"),
        ("У нас есть дом и большой сад.", "сад", "nomn"),
        ("Караваны верблюдов везли ящики с чаем.", "ящики", "accs"),
        ("Каждый день люди выпивают миллиарды чашек чая.", "миллиарды", "accs"),
    ],
)
def test_word_order_heuristics(text, word, case):
    ann = next(a for a in annotate_ru_text(text) if a["text"] == word)
    assert ann["case"] == case
    assert ann["confidence"] == 0.85  # эвристика отмечена пониженной уверенностью


def test_homonyms_are_not_nouns():
    words = cases("Анна села за стол. Сначала он был дорогой роскошью, а книга толстой.")
    assert "села" not in words        # глагол «сесть», а не «село»
    assert "дорогой" not in words     # прилагательное при «роскошью»
    assert "толстой" not in words     # не фамилия Толстой


def test_ambiguous_case_is_flagged():
    ann = next(a for a in annotate_ru_text("Сегодня чай — самый популярный напиток.")
               if a["text"] == "напиток")
    assert ann["ambiguous"] is True and ann["disputed"] is True
    assert "accs" in ann["alternatives"]
