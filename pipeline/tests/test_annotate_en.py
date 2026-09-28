import pipeline.annotate.en as en_module
from pipeline.annotate.en import annotate_en
from pipeline.tests.conftest import requires_spacy


def articles(text):
    anns, method, _warnings = annotate_en([text])
    return anns[0], method


@requires_spacy
def test_articles_with_heads_and_offsets():
    text = "An old man bought a book and the apples at the market."
    anns, method = articles(text)
    assert method == "spacy:en_core_web_sm"
    assert [(a["value"], a["head"]["text"]) for a in anns] == [
        ("an", "man"), ("a", "book"), ("the", "apples"), ("the", "market"),
    ]
    for ann in anns:
        assert text[ann["start"]:ann["end"]].lower() == ann["value"]
        head = ann["head"]
        assert text[head["start"]:head["end"]] == head["text"]
    assert anns[0]["definite"] is False and anns[2]["definite"] is True
    assert anns[2]["head"]["number"] == "plur"
    assert anns[0]["next"]["text"] == "old"  # для объяснения выбора a / an


@requires_spacy
def test_correlative_the_is_not_an_article():
    anns, _ = articles("The more you read, the better you write.")
    assert anns == []


@requires_spacy
def test_non_noun_head_is_disputed():
    anns, _ = articles("At first it was a luxury that only the rich could afford.")
    rich = next(a for a in anns if a["head"] and a["head"]["text"] == "rich")
    assert rich["disputed"] is True
    assert "ADJ" in rich["note"]


@requires_spacy
def test_capitalised_article_and_ids():
    anns, _ = articles("The Great Wall is a long wall.")
    assert [a["id"] for a in anns] == ["en1", "en2"]
    assert anns[0]["text"] == "The"
    assert anns[0]["head"]["text"] == "Wall"


def test_rule_fallback_without_spacy(monkeypatch):
    def broken(_name):
        raise OSError("model not found")

    monkeypatch.setattr(en_module, "load_spacy", broken)
    anns, method, warnings = annotate_en(["She took an umbrella and a pen."])
    assert method == "rules"
    assert warnings and "spacy download" in warnings[0]
    assert [(a["value"], a["head"]["text"]) for a in anns[0]] == [("an", "umbrella"), ("a", "pen")]
    assert all(a["disputed"] for a in anns[0])
