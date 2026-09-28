import pytest

from pipeline.annotate.zh import annotate_zh, build_pattern, load_classifiers
from pipeline.tests.conftest import CLASSIFIERS

EXCLUDE = ["一样", "一下", "一点儿", "一口气", "一部分"]


def constructions(text):
    anns, _ = annotate_zh([text], CLASSIFIERS, exclude_words=EXCLUDE)
    return [(a["det"]["text"], a["value"], a["head"]["text"] if a["head"] else None)
            for a in anns[0]]


def test_classifier_list_is_loaded_with_comments_skipped():
    classifiers = load_classifiers(CLASSIFIERS)
    assert classifiers["本"].pinyin == "běn"
    assert "书" in classifiers["本"].examples
    assert classifiers["次"].verbal is True
    assert "classifier" not in classifiers  # строка заголовка не попала в список


def test_custom_classifier_file(tmp_path):
    path = tmp_path / "list.tsv"
    path.write_text(
        "# комментарий\n"
        "classifier\tpinyin\ttype\tgloss_ru\texamples\n"
        "本\tběn\tименной\tкниги\t书\n",
        encoding="utf-8",
    )
    anns, classifiers = annotate_zh(["我有三本书和两张纸。"], path)
    assert list(classifiers) == ["本"]
    assert [a["value"] for a in anns[0]] == ["本"]  # 张 не в списке — не размечается


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # jieba делит «三 | 本书», а «一个» склеивает — конструкция всё равно находится
        ("我买了三本书和一个苹果。", [("三", "本", "书"), ("一", "个", "苹果")]),
        ("这个人每天看两张报纸。", [("这", "个", "人"), ("两", "张", "报纸")]),
        ("那几只小猫很可爱。", [("那几", "只", "小猫")]),
        ("每个学生都有一支笔。", [("每", "个", "学生"), ("一", "支", "笔")]),
        ("第一本书讲的是长城的故事。", [("第一", "本", "书")]),
        ("奶奶买了两公斤苹果。", [("两", "公斤", "苹果")]),
        ("人们每天要喝几十亿杯茶。", [("几十亿", "杯", "茶")]),
    ],
)
def test_determiner_classifier_noun(text, expected):
    assert constructions(text) == expected


def test_offsets_point_into_unchanged_text():
    text = "她带了一把伞、一个笔记本和两支笔。"
    anns, _ = annotate_zh([text], CLASSIFIERS)
    for ann in anns[0]:
        assert text[ann["start"]:ann["end"]] == ann["text"]
        assert text[ann["det"]["start"]:ann["det"]["end"]] == ann["det"]["text"]
        assert text[ann["head"]["start"]:ann["head"]["end"]] == ann["head"]["text"]
        assert ann["det"]["end"] == ann["start"]


def test_numeral_inside_another_word_is_rejected():
    assert constructions("他统一个国家。") == []
    assert constructions("唯一一个办法。") == [("一", "个", "办法")]


def test_excluded_words():
    assert constructions("他们一样好。") == []
    assert constructions("这是中国文化的一部分。") == []


def test_ellipsis_and_verbal_classifiers():
    anns, _ = annotate_zh(["另外两本很薄。", "我去过三次。"], CLASSIFIERS)
    ellipsis, verbal = anns[0][0], anns[1][0]
    assert ellipsis["head"] is None and ellipsis["elliptical"] is True
    assert ellipsis["disputed"] is True
    assert verbal["value"] == "次" and verbal["head"] is None
    assert "elliptical" not in verbal


@pytest.mark.parametrize(
    ("text", "head"),
    [
        ("她是一所学校的老师。", "学校"),            # 所 — для учреждений
        ("那是一张古代中国的地图。", "地图"),         # вершина группы с 的
        ("出口附近有一家卖茶叶的小店。", "小店"),     # определительный оборот
        ("她点了一块苹果派。", "苹果派"),             # составное существительное
        ("安娜想找一本关于中国历史的书。", "书"),
        ("每个士兵的脸都不一样。", "士兵"),
        ("图书馆在河边的一座老楼里。", "楼"),         # послелог 里 отбрасывается
    ],
)
def test_head_noun_selection(text, head):
    assert constructions(text)[0][2] == head


def test_nominalised_verb_is_disputed():
    anns, _ = annotate_zh(["这些观察对教师有直接的意义。"], CLASSIFIERS)
    ann = anns[0][0]
    assert ann["head"]["text"] == "观察"
    assert ann["disputed"] is True


def test_pattern_prefers_longest_classifier():
    pattern = build_pattern(["斤", "公斤", "个"], ["这"])
    match = pattern.match("三公斤")
    assert match and match.group("cl") == "公斤"
