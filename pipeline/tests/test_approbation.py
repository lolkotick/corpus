import statistics
from pathlib import Path

import pytest

from pipeline.approbation import (
    case_of_answer,
    hake_gain,
    load,
    paired_test,
    run,
    t_test_p,
    wilcoxon,
)
from pipeline.cli import main

DATA = Path(__file__).parent / "fixtures" / "approbation_synthetic"


def test_fixtures_are_marked_synthetic():
    for path in DATA.glob("*.csv"):
        first = path.read_text(encoding="utf-8-sig").splitlines()[0]
        assert first.startswith("# СИНТЕТИЧЕСКИЕ ДАННЫЕ")


def test_t_distribution_matches_tables():
    assert t_test_p(2.0, 10) == pytest.approx(0.07339, abs=1e-5)
    assert t_test_p(2.0, 2) == pytest.approx(0.1835, abs=1e-4)
    assert t_test_p(2.228, 10) == pytest.approx(0.05, abs=1e-3)  # критическое значение t(10)


def test_wilcoxon_exact_with_and_without_ties():
    assert wilcoxon([1, 2, 3, 4, 5]) == (15.0, 0.0625, True)
    assert wilcoxon([1, -2, 3, 4, 5, 6, 7, -8])[1] == pytest.approx(0.3125)
    w, p, exact = wilcoxon([2, 2, -1, 0])  # связь и нулевая разность
    assert exact and w == 5.0 and p == pytest.approx(0.5)
    assert wilcoxon([0, 0]) == (None, None, True)


def test_paired_test_and_gain():
    test = paired_test([40, 50, 60], [60, 50, 80])
    assert test.mean_diff == pytest.approx(40 / 3)
    assert test.sd_diff == pytest.approx(statistics.stdev([20, 0, 20]))
    assert test.dz == pytest.approx(test.mean_diff / test.sd_diff)
    assert hake_gain(50, 75) == 0.5 and hake_gain(100, 100) is None


def test_case_of_wrong_answer():
    assert case_of_answer("книге", "книгу") == "дат./предл."
    assert case_of_answer("стол", "книгу") is None


def test_load_drops_unfinished_and_repeats():
    ds = load([DATA])
    assert ds.synthetic
    assert ds.dropped_unfinished == 1 and ds.dropped_repeat == ["P1 (Предтест)"]
    scores = {(a.participant, a.stage): round(a.score, 1) for a in ds.attempts}
    assert scores == {("P1", "pre"): 33.3, ("P1", "post"): 100.0, ("P2", "pre"): 66.7,
                      ("P2", "post"): 66.7, ("P3", "pre"): 0.0, ("P3", "post"): 66.7,
                      ("P4", "pre"): 100.0}


def test_report_on_synthetic_data(tmp_path):
    code, files = run([DATA], tmp_path, tmp_path)
    assert code == 0
    report = (tmp_path / "approbation.md").read_text(encoding="utf-8")
    assert "синтетические данные" in report
    assert "| Средний прирост, п. п. | 44,4 |" in report
    assert "t(2) = 2,00, p = 0,184" in report
    assert "| the → a | 2 | 1 | 1 |" in report
    assert "нужен вин., дан дат./предл." in report
    names = {f.name for f in files}
    assert {"approbation_scores.png", "approbation_participants.png",
            "approbation_participants.csv", "approbation_errors.csv"} <= names
    rows = (tmp_path / "approbation_participants.csv").read_text("utf-8-sig").splitlines()
    assert rows[1].startswith("P1;33,33;100,00;66,67;1,00")


def test_no_data_message(tmp_path, capsys):
    code, files = run([tmp_path / "missing"], tmp_path / "out", tmp_path)
    assert code == 0 and [f.name for f in files] == ["approbation.md"]
    text = files[0].read_text(encoding="utf-8")
    assert "Данных для анализа нет" in text and "%" not in text
    assert "нет CSV" in capsys.readouterr().out


def test_wrong_file_is_reported(tmp_path):
    (tmp_path / "other.csv").write_text("id;text\n1;x\n", encoding="utf-8")
    _, files = run([tmp_path], tmp_path / "out", tmp_path)
    text = files[0].read_text(encoding="utf-8")
    assert "нет ни одной завершённой попытки" in text and "не экспорт режима" in text


def test_cli(tmp_path):
    assert main(["approbation", str(DATA), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "approbation.md").exists()
