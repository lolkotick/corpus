import json
import shutil
from pathlib import Path

from pipeline.cli import main
from pipeline.evaluate import evaluate, run
from pipeline.gold import load_gold

FIXTURES = Path(__file__).parent / "fixtures"
GOLD = FIXTURES / "gold_synthetic.json"
CORPUS = FIXTURES / "corpus_synthetic.json"


def counts(c):
    return (c.tp, c.fp, c.fn)


def test_synthetic_metrics_match_hand_calculation():
    gold = load_gold(GOLD)
    assert gold is not None
    ev = evaluate(json.loads(CORPUS.read_text(encoding="utf-8")), gold)
    assert ev.complete == 5 and ev.partial == 1
    assert ev.stale == ["syn-099"]
    assert sorted(ev.used) == ["syn-001", "syn-002", "syn-003", "syn2-001"]

    # EN–ZH: из трёх групп syn верна одна (EN1↔ZH1), в эталоне четыре 1–1; syn2 верна.
    assert counts(ev.alignment["zh"].strict) == (2, 2, 3)
    assert counts(ev.alignment["zh"].lax) == (4, 2, 1)
    # EN–RU: «ошибка» без исправления в syn2 — только лишнее срабатывание в строгой оценке.
    assert counts(ev.alignment["ru"].strict) == (2, 2, 2)
    assert counts(ev.alignment["ru"].lax) == (4, 2, 0)
    assert ev.alignment["ru"].unknown == 1

    en, zh, ru = ev.langs["en"], ev.langs["zh"], ev.langs["ru"]
    assert counts(en.detection) == (5, 0, 0) and counts(en.full) == (4, 1, 1)
    assert counts(zh.detection) == (1, 1, 1) and counts(zh.full) == (1, 1, 1)
    assert counts(ru.detection) == (5, 1, 0) and counts(ru.full) == (4, 2, 1)
    assert ru.confusion[("gent", "nomn")] == 1 and ru.confusion[("—", "gent")] == 1
    assert (ru.lemma_ok, ru.lemma_total) == (5, 5)
    assert abs(ru.full.precision - 4 / 6) < 1e-9 and abs(ru.full.f1 - 8 / 11) < 1e-9


def test_report_files_and_synthetic_warning(tmp_path):
    code, files = run(CORPUS, GOLD, tmp_path, tmp_path)
    assert code == 0
    names = {f.name for f in files}
    assert {"evaluation.md", "evaluation_metrics.csv", "evaluation_case_confusion.csv",
            "evaluation_items.csv", "evaluation_alignment.csv", "evaluation_prf.png",
            "evaluation_case_confusion.png"} <= names
    report = (tmp_path / "evaluation.md").read_text(encoding="utf-8")
    assert "синтетические данные" in report
    assert "| Падежи (RU) | обнаружение + падеж | 4 | 2 | 1 | 0,667 | 0,800 | 0,727 |" in report
    png = (tmp_path / "evaluation_prf.png").read_bytes()
    assert png.startswith(b"\x89PNG")
    csv_text = (tmp_path / "evaluation_metrics.csv").read_text(encoding="utf-8-sig")
    assert csv_text.splitlines()[0].startswith("Задача;Уровень;TP;FP;FN")


def _no_numbers(report: str) -> None:
    assert "Данных для оценки нет" in report
    assert "Точность" not in report and "| TP |" not in report


def test_missing_gold_gives_message_without_numbers(tmp_path, capsys):
    gold_path = tmp_path / "data" / "gold" / "gold.json"
    code, files = run(CORPUS, gold_path, tmp_path / "reports", tmp_path)
    assert code == 0 and [f.name for f in files] == ["evaluation.md"]
    assert "не найден" in capsys.readouterr().out
    _no_numbers(files[0].read_text(encoding="utf-8"))
    assert not gold_path.exists()  # скрипт никогда не создаёт эталон сам


def test_gold_without_complete_pairs(tmp_path):
    data = json.loads(GOLD.read_text(encoding="utf-8"))
    data["pairs"] = [p for p in data["pairs"] if p["id"] == "syn-005"]
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    code, files = run(CORPUS, path, tmp_path / "reports", tmp_path)
    assert code == 0
    _no_numbers(files[0].read_text(encoding="utf-8"))


def test_all_stale_pairs_give_message(tmp_path):
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    for pair in corpus["pairs"]:
        pair["ru"] += " (изменено)"
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    _, files = run(path, GOLD, tmp_path / "reports", tmp_path)
    _no_numbers(files[0].read_text(encoding="utf-8"))


def test_invalid_gold_returns_error(tmp_path, capsys):
    path = tmp_path / "gold.json"
    path.write_text('{"format": "corpus-gold", "version": 1}', encoding="utf-8")
    code, files = run(CORPUS, path, tmp_path, tmp_path)
    assert code == 1 and files == []
    assert "Ошибка" in capsys.readouterr().out


def test_cli_evaluate(tmp_path):
    shutil.copy(GOLD, tmp_path / "gold.json")
    code = main(["evaluate", "--gold", str(tmp_path / "gold.json"), "--corpus", str(CORPUS),
                 "--out", str(tmp_path / "out")])
    assert code == 0
    assert (tmp_path / "out" / "evaluation.md").exists()
