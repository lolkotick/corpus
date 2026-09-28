import csv
import json

from pipeline.build import run_build
from pipeline.cli import main
from pipeline.tests.conftest import requires_spacy

REQUIRED_FIELDS = {"id", "text_id", "en", "zh", "ru", "alignment_type", "alignment_score",
                   "annotations", "status", "llm_note", "comment"}


@requires_spacy
def test_full_build_on_example(project):
    result = run_build(project, use_llm=False)
    out = project.path("output")
    corpus = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))

    assert corpus["alignment_method"] in {"gale_church", "labse", "bertalign"}
    assert len(corpus["pairs"]) == 24
    pair = corpus["pairs"][0]
    assert set(pair) >= REQUIRED_FIELDS
    assert pair["id"] == "example-001" and pair["status"] == "auto"
    assert 0 <= pair["alignment_score"] <= 1
    kinds = {lang: {a["kind"] for p in corpus["pairs"] for a in p["annotations"][lang]}
             for lang in ("en", "zh", "ru")}
    assert kinds == {"en": {"article"}, "zh": {"classifier"}, "ru": {"case"}}

    # Разметка ссылается на неизменённый текст.
    for p in corpus["pairs"]:
        for lang in ("en", "zh", "ru"):
            for ann in p["annotations"][lang]:
                assert p[lang][ann["start"]:ann["end"]] == ann["text"]

    assert stats["totals"]["pairs"] == 24
    assert stats["totals"]["annotations"]["article"] == sum(stats["articles"]["counts"].values())
    assert sum(b["count"] for b in stats["alignment"]["histogram"]) == 24
    assert {c["case"] for c in stats["cases"]} >= {"nomn", "gent", "datv", "accs", "ablt", "loct"}
    assert stats["build"]["stages"][0]["name"] == "Чтение текстов"
    assert stats["build"]["llm"]["api"] is False

    with open(out / "corpus.csv", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 24 and rows[0]["id"] == "example-001"

    report = (project.path("logs") / "build_report.md").read_text(encoding="utf-8")
    assert "Журнал сборки" in report and "LLM-проверка" in report
    assert result.stages[0].name == "Чтение текстов"


@requires_spacy
def test_csv_round_trip(project, monkeypatch):
    run_build(project, use_llm=False)
    out = project.path("output")
    with open(out / "corpus.csv", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    rows[0]["ru"] = rows[0]["ru"].replace("городскую", "центральную")
    rows[1]["status"] = "проверено"
    edited = project.root / "edited.csv"
    with open(edited, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    monkeypatch.setattr("pipeline.cli.load_config", lambda path=None: project)
    assert main(["import-csv", str(edited), "--no-llm"]) == 0

    corpus = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
    first, second = corpus["pairs"][0], corpus["pairs"][1]
    assert "центральную" in first["ru"] and first["status"] == "corrected"
    # Исправленный текст размечен заново.
    assert any(a["lemma"] == "библиотека" for a in first["annotations"]["ru"])
    assert second["status"] == "checked"
    overrides = json.loads((project.path("manual") / "overrides.json").read_text("utf-8"))
    assert set(overrides["pairs"]) == {"example-001", "example-002"}


def test_check_command(project, monkeypatch, capsys):
    monkeypatch.setattr("pipeline.cli.load_config", lambda path=None: project)
    assert main(["check"]) == 0
    assert "example" in capsys.readouterr().out
