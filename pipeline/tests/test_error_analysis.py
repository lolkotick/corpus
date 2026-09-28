import json
from pathlib import Path

from pipeline.cli import main
from pipeline.error_analysis import (
    case_homonymous,
    classify_alignment,
    classify_case,
    classify_classifier,
    collect,
    run,
)
from pipeline.gold import load_gold

GOLD = Path(__file__).parent / "fixtures" / "gold_synthetic.json"


def test_classify_alignment_types():
    # EN 2 ↔ ZH 2–3, а верно EN 2 ↔ ZH 2: в группу попало лишнее предложение.
    assert classify_alignment(((1,), (1, 2)), [((1,), (1,))]) == "merge"
    # Две эталонные группы внутри одной автоматической.
    assert classify_alignment(((2, 3), (2, 3)), [((2,), (2,)), ((3,), (3,))]) == "merge"
    # Автоматическая группа уже эталонной.
    assert classify_alignment(((4,), (4,)), [((4,), (4, 5))]) == "split"
    # Тот же размер, другие предложения.
    assert classify_alignment(((5,), (6,)), [((5,), (5,))]) == "shift"
    assert classify_alignment(((2, 3), (3,)), [((2,), (2,)), ((3,), (3,))]) == "mixed"


def test_classify_classifier_boundary_and_noun():
    auto = {"text": "只", "head": {"text": "黑猫"}}
    assert classify_classifier(auto, {"classifier": "只", "head": "猫"}) == "boundary"
    assert classify_classifier(auto, {"classifier": "个", "head": "黑猫"}) == "boundary"
    assert classify_classifier(auto, {"classifier": "只", "head": "狗"}) == "noun"


def test_case_homonymy_uses_pymorphy():
    # «книги»: род. ед. = им./вин. мн. — омонимия; «книгу» — только вин.
    assert case_homonymous("книги", "nomn", "gent", "книга")
    assert not case_homonymous("книгу", "accs", "datv", "книга")
    auto = {"text": "стали", "case": "nomn", "lemma": "сталь"}
    assert classify_case(auto, {"case": "nomn", "lemma": "стать"})[0] == "lemma"
    assert classify_case(auto, {"case": "gent", "lemma": "сталь"})[0] == "homonymy"
    assert classify_case({"text": "Книга", "case": "nomn", "lemma": "книга"},
                         {"case": "gent", "lemma": "книга"}) == ("other",
                                                                 "неверный падеж без омонимии")


def test_collect_on_synthetic_gold():
    gold = load_gold(GOLD)
    assert gold is not None and gold.synthetic
    cases, checked = collect(gold)
    kinds = sorted((c.phenomenon, c.kind) for c in cases)
    assert kinds == [
        ("align", "merge"), ("align", "merge"), ("align", "mixed"), ("align", "unknown"),
        ("en", "head"), ("ru", "other"), ("ru", "other"), ("zh", "false"), ("zh", "missed"),
    ]
    assert checked["align"] == 10  # 5 пар × 2 языка
    head = next(c for c in cases if c.kind == "head")
    assert head.text[head.span[0]:head.span[1]] == "a" and head.gold == "a → cat"


def test_report_and_chart(tmp_path):
    code, files = run(GOLD, tmp_path, tmp_path)
    assert code == 0
    report = (tmp_path / "errors.md").read_text(encoding="utf-8")
    assert "синтетические данные" in report
    assert "| неверное объединение | 2 | 50,0 % |" in report
    assert "He has **a** black cat." in report
    assert (tmp_path / "errors_types.png").read_bytes().startswith(b"\x89PNG")
    assert {f.name for f in files} == {"errors.md", "errors.csv", "errors_types.png"}


def test_no_gold_message(tmp_path, capsys):
    code, files = run(tmp_path / "gold.json", tmp_path / "out", tmp_path)
    assert code == 0 and [f.name for f in files] == ["errors.md"]
    text = files[0].read_text(encoding="utf-8")
    assert "Данных для анализа нет" in text and "%" not in text
    assert "не найден" in capsys.readouterr().out
    assert not (tmp_path / "gold.json").exists()

    data = json.loads(GOLD.read_text(encoding="utf-8"))
    data["pairs"] = [p for p in data["pairs"] if p["id"] == "syn-005"]  # незаконченная пара
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    _, files = run(partial, tmp_path / "out2", tmp_path)
    assert "нет ни одной полностью проверенной пары" in files[0].read_text(encoding="utf-8")


def test_cli_errors(tmp_path):
    assert main(["errors", "--gold", str(GOLD), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "errors.md").exists()
