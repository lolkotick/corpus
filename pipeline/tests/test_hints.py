import json
from pathlib import Path

from pipeline.cli import main
from pipeline.gold import load_gold
from pipeline.hints import ASSISTED, BLIND, build_template, compare, kappa, load_hints, run

FIXTURES = Path(__file__).parent / "fixtures"
GOLD = FIXTURES / "gold_synthetic.json"
CORPUS = FIXTURES / "corpus_synthetic.json"


def synthetic_hints() -> dict:
    """СИНТЕТИЧЕСКИЕ подсказки к gold_synthetic.json: расхождения расставлены вручную."""
    return {
        "format": "corpus-gold-hints", "version": 1, "synthetic": True,
        "source": "тест", "blind_pair_ids": ["syn-001", "syn-002"],
        "pairs": [
            {"id": "syn-001",
             "alignment": {"zh": {"verdict": "correct"}, "ru": {"verdict": "wrong"}},
             "items": {"en": [{"id": "en1", "verdict": "correct"}],
                       "zh": [{"id": "zh1", "verdict": "correct"}],
                       "ru": [{"id": "ru1", "verdict": None}]}},
            {"id": "syn-002",
             "alignment": {"zh": {"verdict": "corrected"}, "ru": {"verdict": "correct"}},
             "items": {"zh": [{"id": "zh1", "verdict": "wrong"}],
                       "ru": [{"id": "ru1", "verdict": "corrected",
                               "correction": {"case": "datv", "lemma": "книга"},
                               "note": "проверка"}]}},
            {"id": "syn-003",
             "alignment": {"zh": {"verdict": "corrected"}},
             "items": {"en": [{"id": "en1", "verdict": "corrected",
                               "correction": {"head": "Cat"}}]},
             "missed": {"zh": [{"start": 4, "end": 5, "text": "只"},
                               {"start": 9, "end": 10, "text": "个"}]}},
            {"id": "syn-005", "alignment": {"zh": {"verdict": "correct"}}},
            {"id": "нет-в-эталоне", "alignment": {"zh": {"verdict": "correct"}}},
        ],
    }


def gold_with_hints_shown(tmp_path: Path) -> Path:
    data = json.loads(GOLD.read_text(encoding="utf-8"))
    for pair in data["pairs"]:
        if pair["id"] == "syn-003":
            pair["hints_shown"] = True
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_agreement_splits_blind_and_assisted(tmp_path):
    gold = load_gold(gold_with_hints_shown(tmp_path))
    assert gold is not None
    result = compare(gold, synthetic_hints())
    assert result.pairs == {BLIND: 2, ASSISTED: 1}
    blind = [d for d in result.decisions if d.condition == BLIND]
    # syn-001: 2 выравнивания + en1 + zh1 (ru1 без вердикта модели не считается);
    # syn-002: 2 выравнивания + zh1 + ru1.
    assert len(blind) == 8
    wrong = {(d.pair_id, d.obj, d.target) for d in blind if not d.same}
    # Расходятся: вердикт выравнивания EN–RU и исправление падежа (тот же вердикт, другой падеж).
    assert wrong == {("syn-001", "align", "EN–RU"), ("syn-002", "ru", wrong_target(blind))}
    assisted = [d for d in result.decisions if d.condition == ASSISTED]
    assert [(d.obj, d.same) for d in assisted] == [("align", True), ("en", True)]
    assert result.missed[(ASSISTED, "zh", "оба")] == 1
    assert result.missed[(ASSISTED, "zh", "только модель")] == 1
    rows = {(r[0], r[1]): r for r in result.rows()}
    assert rows[(BLIND, "Все решения")][2:4] == [8, 6]
    assert rows[(ASSISTED, "Все решения")][2:4] == [2, 2]


def wrong_target(decisions) -> str:
    return next(d.target for d in decisions if d.pair_id == "syn-002" and d.obj == "ru")


def test_kappa_values():
    gold = load_gold(GOLD)
    assert gold is not None
    decisions = compare(gold, synthetic_hints()).decisions
    assert kappa([]) is None
    same = [d for d in decisions if d.expert == d.model == "correct"]
    assert kappa(same) is None  # все вердикты одинаковы: случайное согласие равно 1
    value = kappa(decisions)
    assert value is not None and 0 < value < 1


def test_report_and_no_data_messages(tmp_path, capsys):
    hints_path = tmp_path / "hints.json"
    code, files = run(GOLD, hints_path, tmp_path, tmp_path)
    assert code == 0 and [f.name for f in files] == ["hints.md"]
    assert "Данных для сравнения нет" in (tmp_path / "hints.md").read_text(encoding="utf-8")

    hints_path.write_text(json.dumps(synthetic_hints(), ensure_ascii=False), encoding="utf-8")
    code, files = run(gold_with_hints_shown(tmp_path), hints_path, tmp_path, tmp_path)
    assert code == 0
    assert {f.name for f in files} == {"hints.md", "hints_agreement.csv",
                                       "hints_disagreements.csv"}
    report = (tmp_path / "hints.md").read_text(encoding="utf-8")
    assert "синтетические данные" in report
    assert "| вслепую | Все решения | 8 | 6 | 0,750 |" in report
    rows = (tmp_path / "hints_disagreements.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(rows) == 3 and "проверка" in rows[2]

    hints_path.write_text('{"format": "other"}', encoding="utf-8")
    assert run(GOLD, hints_path, tmp_path, tmp_path) == (1, [])
    assert "не файл подсказок" in capsys.readouterr().out


def test_template_lists_sample_with_empty_verdicts(tmp_path):
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    template = build_template(corpus, 3, 1, "by-register", 2, "модель")
    assert len(template["pairs"]) == 3 and len(template["blind_pair_ids"]) == 2
    assert template["blind_pair_ids"] == [p["id"] for p in template["pairs"][:2]]
    first = template["pairs"][0]
    assert first["alignment"] == {"zh": {"verdict": None, "note": ""},
                                  "ru": {"verdict": None, "note": ""}}
    assert all(i["verdict"] is None for items in first["items"].values() for i in items)
    assert set(first["_text"]) == {"en", "zh", "ru"}

    out = tmp_path / "hints.json"
    args = ["hints-template", "--corpus", str(CORPUS), "--hints", str(out), "--size", "3"]
    assert main(args) == 0
    loaded = load_hints(out)
    assert loaded is not None and loaded["sample"]["strategy"] == "by-register"
    out.write_text(out.read_text(encoding="utf-8").replace('"source": ""', '"source": "x"'),
                   encoding="utf-8")
    assert main(args) == 1  # вписанные подсказки не перезаписываются без --force
    assert '"source": "x"' in out.read_text(encoding="utf-8")
