import pytest

from pipeline.difficulty import DEFAULT_THRESHOLDS, LEVELS, estimate, lang_score, to_level

wordfreq = pytest.importorskip("wordfreq")


def test_to_level_boundaries():
    assert to_level(0.0) == "A1"
    assert to_level(DEFAULT_THRESHOLDS[0]) == "A2"  # граница относится к следующему уровню
    assert to_level(0.25) == "B1"
    assert to_level(0.99) == "C2"
    assert to_level(0.5, (0.3, 0.6)) == "A2"
    assert to_level(0.7, (0.3, 0.6)) == "B1"


def test_lang_score_range_and_empty():
    assert lang_score("", "en") == 0.0
    assert lang_score("123 …", "ru") == 0.0
    for lang, text in (("en", "The cat sleeps."), ("zh", "猫在睡觉。"), ("ru", "Кошка спит.")):
        assert 0.0 < lang_score(text, lang) <= 1.0


def test_long_rare_sentence_is_harder():
    simple = estimate({"en": "I have a cat.", "zh": "我有一只猫。", "ru": "У меня есть кошка."})
    hard = estimate({
        "en": "The intergovernmental committee reaffirmed its commitment to the "
              "implementation of the multilateral environmental agreements.",
        "zh": "政府间委员会重申致力于执行多边环境协定。",
        "ru": "Межправительственный комитет подтвердил приверженность осуществлению "
              "многосторонних природоохранных соглашений.",
    })
    assert set(simple.by_lang) == {"en", "zh", "ru"}
    assert simple.score < hard.score
    assert LEVELS.index(simple.level) < LEVELS.index(hard.level)
