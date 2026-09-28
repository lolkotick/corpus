from pipeline.segment import join_sentences, segment_en, segment_ru, segment_zh
from pipeline.sources import split_paragraphs


def test_en_keeps_abbreviations_together():
    text = "Mr. Smith lives in the U.S. now. He bought a car, e.g. a Ford. Is it new?"
    assert segment_en(text) == [
        "Mr. Smith lives in the U.S. now.",
        "He bought a car, e.g. a Ford.",
        "Is it new?",
    ]


def test_en_semicolon_is_not_a_boundary():
    assert segment_en("One was thick; the other was thin. Done.") == [
        "One was thick; the other was thin.",
        "Done.",
    ]


def test_ru_razdel_handles_abbreviations_and_quotes():
    text = "Т. е. это пример. «Приходите снова», — сказала она. В 1950-х гг. всё было иначе!"
    assert segment_ru(text) == [
        "Т. е. это пример.",
        "«Приходите снова», — сказала она.",
        "В 1950-х гг. всё было иначе!",
    ]


def test_zh_terminators_and_semicolon():
    assert segment_zh("其中一本书很厚；另外两本很薄。外面还在下雨！") == [
        "其中一本书很厚；",
        "另外两本很薄。",
        "外面还在下雨！",
    ]


def test_zh_closing_quote_stays_with_sentence():
    assert segment_zh("“下个星期六再来吧！”她说。") == ["“下个星期六再来吧！”", "她说。"]
    assert segment_zh("他说：「好。」然后走了。") == ["他说：「好。」", "然后走了。"]


def test_zh_ellipsis_and_mixed_marks_are_one_boundary():
    assert segment_zh("他等了很久……终于来了！？真的吗？") == [
        "他等了很久……", "终于来了！？", "真的吗？",
    ]


def test_zh_ascii_quotes_open_vs_close():
    # Кавычка после 。 открывает следующее предложение, а не закрывает текущее.
    assert segment_zh('他走了。"你好！"她说。') == ["他走了。", '"你好！"', "她说。"]


def test_zh_tail_without_terminator():
    assert segment_zh("亲爱的玛莎：") == ["亲爱的玛莎："]
    assert segment_zh("爱你的卡佳") == ["爱你的卡佳"]


def test_paragraphs_and_joining():
    raw = "﻿First line\ncontinues.\r\n\r\nSecond  paragraph.\n\n\n"
    assert split_paragraphs(raw, "en") == ["First line continues.", "Second paragraph."]
    assert split_paragraphs("第一行\n继续。\n\n第二段。", "zh") == ["第一行继续。", "第二段。"]
    assert join_sentences(["A.", "B."], "en") == "A. B."
    assert join_sentences(["甲。", "乙。"], "zh") == "甲。乙。"
