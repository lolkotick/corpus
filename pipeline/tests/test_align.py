import sys
import types

import numpy as np
import pytest

from pipeline.align import Aligner, align_three, create_aligner, merge_on_pivot
from pipeline.align.dp import AlignmentError, Bead, allowed_types, dp_align
from pipeline.align.embedding import embedding_align
from pipeline.align.gale_church import gale_church_align, length_probability
from pipeline.config import load_config
from pipeline.segment import segment_paragraphs
from pipeline.sources import LANGS, read_text
from pipeline.tests.conftest import EXAMPLE_DIR

TYPES = allowed_types([[1, 1], [1, 2], [2, 1]], allow_skips=True)
GC_CONFIG = {"gale_church": {"variance": {"zh": 9.0, "ru": 6.8}}}

EN = [
    "Anna went to the library.",
    "It was raining.",
    "She took an umbrella and two pens with her because the weather was bad.",
    "The librarian smiled.",
]
RU_SPLIT = [
    "Анна пошла в библиотеку.",
    "Шёл дождь.",
    "Она взяла зонт и две ручки.",
    "Погода была плохой.",
    "Библиотекарь улыбнулась.",
]


def spans(beads):
    return [(b.src_start, b.src_end, b.tgt_start, b.tgt_end) for b in beads]


def test_length_probability_is_symmetric_and_bounded():
    assert length_probability(50, 50, 6.8) == pytest.approx(1.0)
    p = length_probability(50, 80, 6.8)
    assert 0 < p < 1
    assert p == pytest.approx(length_probability(80, 50, 6.8))


def test_gale_church_one_to_one():
    ru = ["Анна пошла в библиотеку.", "Шёл дождь.",
          "Она взяла с собой зонт и две ручки, потому что погода была плохой.",
          "Библиотекарь улыбнулась."]
    beads = gale_church_align(EN, ru, TYPES)
    assert spans(beads) == [(0, 1, 0, 1), (1, 2, 1, 2), (2, 3, 2, 3), (3, 4, 3, 4)]
    assert all(0 < b.score <= 1 for b in beads)


def test_gale_church_finds_one_to_two():
    beads = gale_church_align(EN, RU_SPLIT, TYPES)
    assert [b.type for b in beads] == ["1-1", "1-1", "1-2", "1-1"]
    assert spans(beads)[2] == (2, 3, 2, 4)


def test_dp_raises_when_types_cannot_cover():
    with pytest.raises(AlignmentError):
        dp_align(1, 5, lambda *_: 0.0, [(1, 1), (1, 2)])


def test_embedding_align_with_fake_encoder():
    """Алгоритм LaBSE-выравнивания проверяется на «эмбеддингах» из словаря смыслов."""
    meaning = {
        "Anna went to the library.": 0, "Анна пошла в библиотеку.": 0,
        "It was raining.": 1, "Шёл дождь.": 1,
        "She took an umbrella and two pens with her because the weather was bad.": 2,
        "Она взяла зонт и две ручки.": 2, "Погода была плохой.": 2,
        "The librarian smiled.": 3, "Библиотекарь улыбнулась.": 3,
    }

    def embed(texts):
        vectors = []
        for text in texts:
            vec = np.zeros(8, dtype=np.float32)
            for sentence, idx in meaning.items():
                if sentence in text:
                    vec[idx] += 1.0
            vectors.append(vec + 0.01)
        return np.stack(vectors)

    beads = embedding_align(EN, RU_SPLIT, embed, TYPES)
    assert spans(beads) == [(0, 1, 0, 1), (1, 2, 1, 2), (2, 3, 2, 4), (3, 4, 4, 5)]
    assert beads[0].score > 0.9


def test_merge_on_pivot_combines_pairwise_alignments():
    en = ["E0", "E1", "E2"]
    zh = ["Z0", "Z1"]
    ru = ["R0", "R1", "R2", "R3"]
    zh_beads = [Bead(0, 2, 0, 1, 0.8), Bead(2, 3, 1, 2, 0.9)]          # 2-1, 1-1
    ru_beads = [Bead(0, 1, 0, 1, 0.7), Bead(1, 2, 1, 2, 0.6), Bead(2, 3, 2, 4, 0.5)]
    segments = merge_on_pivot(en, zh, ru, zh_beads, ru_beads, "test")
    assert [s.alignment_type for s in segments] == ["2-1-2", "1-1-2"]
    assert segments[0].en == ["E0", "E1"] and segments[0].ru == ["R0", "R1"]
    assert segments[0].score == 0.6  # минимум по обоим попарным выравниваниям
    assert segments[1].zh == ["Z1"] and segments[1].ru == ["R2", "R3"]
    assert segments[1].sentence_ids("ru") == [2, 3]
    shifted = segments[1].shifted({"en": 10, "zh": 20, "ru": 30})
    assert shifted.sentence_ids("en") == [12] and shifted.sentence_ids("ru") == [32, 33]


def test_merge_attaches_insertions_to_previous_group():
    en = ["E0", "E1"]
    zh = ["Z0", "Zx", "Z1"]
    ru = ["R0", "R1"]
    zh_beads = [Bead(0, 1, 0, 1, 0.9), Bead(1, 1, 1, 2, 0.0), Bead(1, 2, 2, 3, 0.9)]
    ru_beads = [Bead(0, 1, 0, 1, 0.9), Bead(1, 2, 1, 2, 0.9)]
    segments = merge_on_pivot(en, zh, ru, zh_beads, ru_beads, "test")
    assert segments[0].zh == ["Z0", "Zx"]
    assert segments[0].en_zh == 0.0  # пропуск снижает оценку → пара уйдёт на проверку


def test_create_aligner_falls_back_to_gale_church(monkeypatch):
    monkeypatch.setitem(sys.modules, "bertalign", None)
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    aligner = create_aligner({"method": "auto", **GC_CONFIG})
    assert aligner.method == "gale_church"
    assert any("bertalign" in w for w in aligner.warnings)
    assert any("labse" in w for w in aligner.warnings)


def test_explicit_labse_without_package_falls_back(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    aligner = create_aligner({"method": "labse", **GC_CONFIG})
    assert aligner.method == "gale_church"
    assert aligner.warnings[-1].startswith("labse: недоступен")


def test_neural_failure_on_a_pair_uses_gale_church():
    class Broken:
        def __call__(self, texts):
            raise RuntimeError("CUDA out of memory")

    aligner = Aligner("labse", GC_CONFIG, TYPES, Broken(), [])
    beads, method = aligner.align_pair(EN, RU_SPLIT, "ru")
    assert method == "gale_church"
    assert len(beads) == 4
    assert "ошибка" in aligner.warnings[0]


def test_bertalign_backend_wrapper(monkeypatch):
    """Обёртка над пакетом bertalign проверяется на подменённом модуле."""

    class FakeModel:
        def encode(self, texts, normalize_embeddings=True):
            return np.ones((len(texts), 4), dtype=np.float32) / 2.0

    class FakeEncoder:
        model = FakeModel()

    class FakeBertalign:
        def __init__(self, src, tgt, **kwargs):
            assert kwargs["is_split"] is True
            self.n = len(src.splitlines())

        def align_sents(self):
            return [([0], [0]), ([1], [1, 2]), ([2], [3])]

    pkg = types.ModuleType("bertalign")
    pkg.Bertalign = FakeBertalign
    encoder_mod = types.ModuleType("bertalign.encoder")
    encoder_mod.get_encoder = lambda name: FakeEncoder()
    monkeypatch.setitem(sys.modules, "bertalign", pkg)
    monkeypatch.setitem(sys.modules, "bertalign.encoder", encoder_mod)

    aligner = create_aligner({"method": "bertalign", **GC_CONFIG})
    assert aligner.method == "bertalign"
    beads, method = aligner.align_pair(["a", "b", "c"], ["1", "2", "3", "4"], "ru")
    assert method == "bertalign"
    assert [b.type for b in beads] == ["1-1", "1-2", "1-1"]
    assert beads[0].score == pytest.approx(1.0)


@pytest.mark.parametrize("use_paragraphs", [True, False])
def test_example_text_alignment(use_paragraphs):
    """Пример из data/raw/example: известные соответствия 1–2 и 2–1 находятся верно."""
    config = load_config()
    raw = read_text(EXAMPLE_DIR)
    sentences = {lang: segment_paragraphs(raw.paragraphs[lang], lang,
                                          config.get("segmentation")) for lang in LANGS}
    aligner = create_aligner({**config.get("alignment"), "method": "gale_church"})
    if use_paragraphs:
        segments = []
        for p in range(len(sentences["en"])):
            segments += align_three(aligner, *(sentences[lang][p] for lang in LANGS))
    else:
        flat = [[s for para in sentences[lang] for s in para] for lang in LANGS]
        segments = align_three(aligner, *flat)

    by_en = {s.text("en"): s for s in segments}
    assert len(segments) == 24
    assert by_en["One of the books was very thick; the other two were thin."].alignment_type \
        == "1-2-1"
    assert by_en["At noon Anna felt hungry. Near the library there is a small café."] \
        .alignment_type == "2-1-2"
    quote = by_en['"Come again next Saturday," she said.']
    assert quote.zh == ["“下个星期六再来吧！”", "她说。"]
    assert sum(1 for s in segments if s.alignment_type == "1-1-1") == 21
