"""ZH: конструкция «числительное / 这 / 那 / 几 / 每 + 量词 + существительное».

jieba часто склеивает числительное со счётным словом («一个», «两张») или
счётное слово с существительным («三 | 本书» — здесь «本书» значит «эта книга»).
Поэтому конструкция ищется по символам (регулярное выражение по списку 量词),
а jieba используется для проверки границ слов и поиска существительного:
остаток предложения после 量词 токенизируется заново.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

NUMERAL_CHARS = "零〇一二三四五六七八九十百千万亿两半几0123456789０１２３４５６７８９"
DEFAULT_DEMONSTRATIVES = ("这", "那", "哪", "每", "某")
PUNCT = set("，。！？；：、,.!?;:“”‘’「」『』（）()《》…—-·\"' \n")

# Теги jieba (ICTCLAS): существительные, модификаторы, стоп-слова.
_NOUN_TAGS = ("n", "t", "s")          # n*, t (время), s (место); nr/ns/nz начинаются с n
_MODIFIER_TAGS = {"a", "ad", "ag", "an", "b", "d", "z", "zg", "m", "mq", "uj", "f", "l", "i"}
_PREP_MODIFIERS = {"关于", "对于"}          # «一本关于中国历史的书»
_LOCALIZERS = "里上下中"
_KEEP_LOCALIZER = {"上下", "中中"}
# Слова, которые jieba иногда помечает как существительные, но которые
# начинают сказуемое или обстоятельство после именной группы.
_POST_STOP = {"时", "时候", "以后", "之后", "以前", "之前", "回家", "工作", "学习", "之一"}


@dataclass(frozen=True)
class Classifier:
    value: str
    pinyin: str
    type: str
    gloss_ru: str
    examples: tuple[str, ...] = field(default_factory=tuple)

    @property
    def verbal(self) -> bool:
        return self.type.startswith("глагол")

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "pinyin": self.pinyin,
            "type": self.type,
            "gloss": self.gloss_ru,
            "examples": list(self.examples),
        }


def load_classifiers(path: Path) -> dict[str, Classifier]:
    """Прочитать редактируемый TSV-список 量词 (строки с «#» — комментарии)."""
    lines = [
        line for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    reader = csv.DictReader(lines, delimiter="\t")
    result: dict[str, Classifier] = {}
    for row in reader:
        value = (row.get("classifier") or "").strip()
        if not value:
            continue
        examples = tuple(x.strip() for x in (row.get("examples") or "").split(",") if x.strip())
        result[value] = Classifier(
            value=value,
            pinyin=(row.get("pinyin") or "").strip(),
            type=(row.get("type") or "именной").strip(),
            gloss_ru=(row.get("gloss_ru") or "").strip(),
            examples=examples,
        )
    if not result:
        raise ValueError(f"{path}: список счётных слов пуст")
    return result


def build_pattern(classifiers: Iterable[str], demonstratives: Sequence[str]) -> re.Pattern[str]:
    cl = "|".join(re.escape(c) for c in sorted(classifiers, key=len, reverse=True))
    dem = "|".join(re.escape(d) for d in demonstratives)
    num = f"(?:第)?[{NUMERAL_CHARS}]+"
    return re.compile(f"(?P<det>(?:{dem})(?:{num})?|{num})(?P<cl>{cl})")


@cache
def _jieba():
    import jieba
    import jieba.posseg as pseg

    jieba.setLogLevel(60)  # без служебных сообщений
    return pseg


def tokenize(text: str) -> list[tuple[int, int, str, str]]:
    """Токены jieba с позициями: (start, end, слово, тег)."""
    pseg = _jieba()
    tokens = []
    pos = 0
    for pair in pseg.cut(text):
        word, flag = pair.word, pair.flag
        start = text.find(word, pos)
        if start < 0:  # pragma: no cover - jieba не меняет текст
            start = pos
        tokens.append((start, start + len(word), word, flag))
        pos = start + len(word)
    return tokens


def _is_noun(tag: str) -> bool:
    return tag.startswith(_NOUN_TAGS) or tag in ("vn", "nr", "ns", "nz", "nt")


def _strip_localizer(word: str) -> str:
    """«楼里» → «楼», «树下» → «树»: послелог не входит в существительное."""
    if len(word) >= 2 and word[-1] in _LOCALIZERS and word not in _KEEP_LOCALIZER:
        return word[:-1]
    return word


def compatible(noun: str, classifier: Classifier) -> bool:
    """Совпадает ли существительное с типичными для 量词 словами из списка."""
    for example in classifier.examples:
        if noun == example or noun.endswith(example):
            return True
        if len(example) >= 2 and noun.startswith(example):
            return True
    return False


def _window_tokens(
    text: str, start: int, end: int, sentence_tokens: list[tuple[int, int, str, str]] | None
) -> list[tuple[int, int, str, str]]:
    """Токены окна [start, end) с позициями относительно start.

    По возможности берутся токены всего предложения (теги jieba точнее в контексте);
    токен, который начинается до start («本书» в «三本书»), токенизируется заново.
    """
    if sentence_tokens is None:
        return tokenize(text[start:end])
    result: list[tuple[int, int, str, str]] = []
    for s, e, word, tag in sentence_tokens:
        if e <= start or s >= end:
            continue
        if s < start:
            result += tokenize(text[start:min(e, end)])
        else:
            result.append((s - start, min(e, end) - start, word, tag))
    return result


Token = tuple[int, int, str, str]


def _run_head(run: list[Token]) -> tuple[int, int]:
    """Вершина цепочки существительных (китайская группа — с вершиной справа).

    «俄罗斯|孩子» → 孩子; односложный последний элемент присоединяется к
    предыдущему: «苹果|派» → 苹果派, «借书|卡» → 借书卡, «语法|课» → 语法课.
    """
    last = run[-1]
    if len(run) >= 2 and min(len(last[2]), len(run[-2][2])) == 1 \
            and len(last[2]) + len(run[-2][2]) <= 4:
        return run[-2][0], last[1]  # «手|擀面», «苹果|派»
    return last[0], last[1]


def find_head(
    text: str,
    start: int,
    pattern: re.Pattern[str],
    classifier: Classifier,
    max_modifiers: int = 4,
    sentence_tokens: list[Token] | None = None,
    classifiers: dict[str, Classifier] | None = None,
) -> tuple[tuple[int, int] | None, str]:
    """Найти существительное, к которому относится 量词. Возвращает (позиция, способ).

    Именная группа может содержать определения с 的 («一张古代中国的地图»,
    «一家卖茶叶的小店»), поэтому собираются все цепочки существительных группы:
    1) выбирается существительное из списка типичных для этого 量词
       («一所学校的老师» → 学校, «那家咖啡馆里的长谈» → 咖啡馆);
    2) иначе — вершина группы после 的; но если она типична для другого 量词,
       а перед 的 есть существительное, берётся оно («每个士兵的脸» → 士兵);
    3) иначе — первая цепочка;
    4) если сразу после 量词 стоит глагол — номинализация («这种对比»), спорный случай.
    """
    end = start
    while end < len(text) and text[end] not in PUNCT and end - start < 20:
        end += 1
    if end == start:
        return None, ""
    tokens = _window_tokens(text, start, end, sentence_tokens)
    words = [t[2] for t in tokens]
    runs: list[tuple[list[Token], bool]] = []  # (цепочка токенов, стоит ли после 的)
    current: list[Token] | None = None
    seen_de = False
    modifiers = 0
    for k, (s, e, word, tag) in enumerate(tokens):
        if runs and (word in _POST_STOP or tag == "vn"):
            break  # «医院|工作», «…时» — дальше начинается сказуемое или обстоятельство
        if word == "的":
            seen_de = True
            current = None
            continue
        verb_compound = (  # «借书|卡», «烹饪|课»: глагол + односложное существительное
            tag.startswith("v") and k + 1 < len(tokens) and tokens[k + 1][0] == e
            and _is_noun(tokens[k + 1][3]) and len(tokens[k + 1][2]) == 1
        )
        if _is_noun(tag) or verb_compound or compatible(_strip_localizer(word), classifier):
            if current is not None and current[-1][1] == s:
                current.append((s, e, word, tag))
            else:
                current = [(s, e, word, tag)]
                runs.append((current, seen_de))
            continue
        current = None
        between = words[k + 1 : k + 4]
        relative = "的" in between and not any(
            t[3].startswith("v") for t in tokens[k + 1 : k + 1 + between.index("的")]
        ) if "的" in between else False
        if tag.startswith("v") and relative:
            modifiers += 1  # определительный оборот: «卖茶叶的», «学英语的»
        elif (tag in _MODIFIER_TAGS or word in _PREP_MODIFIERS) and not pattern.match(word):
            modifiers += 1
        else:
            break
        if modifiers > max_modifiers:
            break

    def span(head: tuple[int, int]) -> tuple[int, int]:
        noun = _strip_localizer(text[start + head[0] : start + head[1]])
        return start + head[0], start + head[0] + len(noun)

    if runs:
        for run, _after in runs:
            for token in reversed(run):
                if compatible(_strip_localizer(token[2]), classifier):
                    head = _run_head(run) if token is run[-1] else (token[0], token[1])
                    return span(head), "список типичных существительных"
        after = [run for run, after_de in runs if after_de]
        before = [run for run, after_de in runs if not after_de]
        if after:
            head_text = _strip_localizer(after[0][-1][2])
            typical_elsewhere = classifiers is not None and any(
                compatible(head_text, other) for other in classifiers.values()
                if other.value != classifier.value
            )
            if typical_elsewhere and before:
                return span(_run_head(before[0])), "существительное перед 的"
            return span(_run_head(after[0])), "вершина группы с 的"
        return span(_run_head(runs[0][0])), "первое существительное"
    if tokens and tokens[0][3] in ("v", "vn") and not classifier.verbal:
        return span((tokens[0][0], tokens[0][1])), "глагол в роли существительного"
    return None, ""


def annotate_zh_text(
    text: str,
    classifiers: dict[str, Classifier],
    pattern: re.Pattern[str],
    exclude_words: set[str],
    max_modifiers: int = 4,
) -> list[dict[str, Any]]:
    tokens = tokenize(text)
    owner = [0] * len(text)  # индекс токена для каждого символа
    for idx, (s, e, _w, _t) in enumerate(tokens):
        for p in range(s, e):
            owner[p] = idx

    anns: list[dict[str, Any]] = []
    i = 0
    while i < len(text):
        match = pattern.match(text, i)
        if not match:
            i += 1
            continue
        det_start, cl_start, cl_end = match.start("det"), match.start("cl"), match.end("cl")
        tok_start, tok_end, word, _tag = tokens[owner[det_start]]
        inside_word = tok_start != det_start and tok_end < cl_end  # «统一|个», «唯一|一个»
        if inside_word or word in exclude_words:
            i += 1
            continue

        cl = classifiers[match.group("cl")]
        head, how = find_head(text, cl_end, pattern, cl, max_modifiers, tokens, classifiers)
        ann: dict[str, Any] = {
            "id": f"zh{len(anns) + 1}",
            "kind": "classifier",
            "start": cl_start,
            "end": cl_end,
            "text": match.group("cl"),
            "value": cl.value,
            "pinyin": cl.pinyin,
            "type": cl.type,
            "det": {"start": det_start, "end": cl_start, "text": match.group("det")},
            "head": None,
            "disputed": False,
        }
        if head is not None:
            ann["head"] = {"start": head[0], "end": head[1], "text": text[head[0]:head[1]]}
            ann["head_method"] = how
            if how == "глагол в роли существительного":
                ann["disputed"] = True
                ann["note"] = "после 量词 стоит глагол — проверьте, что это номинализация"
        elif not cl.verbal:
            ann["note"] = "существительное опущено или не найдено (эллипсис: 这个, 另外两本)"
            ann["elliptical"] = True
            ann["disputed"] = True
        anns.append(ann)
        i = cl_end
    return anns


def annotate_zh(
    texts: Sequence[str],
    classifiers_file: Path,
    demonstratives: Sequence[str] = DEFAULT_DEMONSTRATIVES,
    exclude_words: Iterable[str] = (),
    max_modifiers: int = 4,
) -> tuple[list[list[dict[str, Any]]], dict[str, Classifier]]:
    classifiers = load_classifiers(classifiers_file)
    pattern = build_pattern(classifiers, demonstratives)
    excluded = set(exclude_words)
    return (
        [annotate_zh_text(t, classifiers, pattern, excluded, max_modifiers) for t in texts],
        classifiers,
    )
