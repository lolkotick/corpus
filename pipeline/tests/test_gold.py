import json
from pathlib import Path

import pytest

from pipeline.gold import (
    GoldError,
    alignment_truth,
    link_components,
    load_gold,
    mulberry32,
    pair_complete,
    sample_pair_ids,
    truth_items,
)

FIXTURES = Path(__file__).parent / "fixtures"
GOLD = FIXTURES / "gold_synthetic.json"


def test_fixtures_are_marked_synthetic():
    for name in ("gold_synthetic.json", "corpus_synthetic.json", "sample_crosscheck.json"):
        data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        assert data["synthetic"] is True
        assert "СИНТЕТИЧЕСКИЕ" in data["_comment"]


def test_mulberry32_matches_javascript():
    # Эталонные числа получены из web/src/lib/random.ts (Node.js) для seed = 42.
    random = mulberry32(42)
    assert [random() for _ in range(3)] == [
        0.6011037519201636, 0.44829055899754167, 0.8524657934904099,
    ]


def test_sample_matches_typescript_crosscheck():
    data = json.loads((FIXTURES / "sample_crosscheck.json").read_text(encoding="utf-8"))
    for case in data["cases"]:
        assert sample_pair_ids(data["pairs"], case["size"], case["seed"]) == case["expected"]


def test_sample_is_proportional_and_prefix_stable():
    pairs = [{"id": f"{t}-{k}", "text_id": t} for t, n in (("a", 10), ("b", 30)) for k in range(n)]
    ids = sample_pair_ids(pairs, 8, 5)
    assert len(set(ids)) == 8
    assert 1 <= sum(i.startswith("a-") for i in ids) <= 3
    assert sample_pair_ids(pairs, 20, 5)[:8] == ids


def test_load_gold_missing_and_invalid(tmp_path):
    assert load_gold(tmp_path / "gold.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text('{"format": "other"}', encoding="utf-8")
    with pytest.raises(GoldError):
        load_gold(bad)
    bad.write_text("не json", encoding="utf-8")
    with pytest.raises(GoldError):
        load_gold(bad)


def test_complete_pairs_and_alignment_truth():
    gold = load_gold(GOLD)
    assert gold is not None and gold.synthetic
    by_id = {p["id"]: p for p in gold.pairs}
    assert pair_complete(by_id["syn-001"]) and not pair_complete(by_id["syn-005"])
    truth = alignment_truth(by_id["syn-003"], "zh")
    assert truth.auto == ((2, 3), (3,))
    assert truth.gold == [((2,), (2,)), ((3,), (3,))]
    assert not alignment_truth(by_id["syn2-001"], "ru").known


def test_link_components_groups_many_to_many():
    assert link_components([[0, 0], [0, 1], [1, 2], [2, 2]]) == [((0,), (0, 1)), ((1, 2), (2,))]


def test_truth_items_apply_corrections_and_missed():
    gold = load_gold(GOLD)
    assert gold is not None
    by_id = {p["id"]: p for p in gold.pairs}
    items, judged = truth_items(by_id["syn-003"], "en")
    assert [i.head for i in items] == ["cat", "chair"]
    assert [j.verdict for j in judged] == ["corrected", "correct"]
    zh, _ = truth_items(by_id["syn-003"], "zh")
    assert [(i.text, i.head, i.source) for i in zh] == [("张", "椅子", "missed")]
    ru, _ = truth_items(by_id["syn-003"], "ru")
    assert [i.text for i in ru] == ["кошка", "стуле"]  # «него» — ложное срабатывание


def test_classifier_boundary_correction_moves_span():
    pair = {
        "text": {"zh": "我买了一本书。"},
        "phenomena": {"zh": {"mode": "itemized", "missed": [], "items": [{
            "id": "zh1", "verdict": "corrected",
            "auto": {"kind": "classifier", "start": 3, "end": 4, "text": "一", "value": "一"},
            "correction": {"classifier": "本", "head": "书"},
        }]}},
    }
    items, _ = truth_items(pair, "zh")
    assert (items[0].start, items[0].end, items[0].text, items[0].head) == (4, 5, "本", "书")
