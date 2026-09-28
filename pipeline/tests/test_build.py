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

    # Номера предложений покрывают каждый текст без пропусков и собираются в текст пары.
    from pipeline.segment import join_sentences

    sentences = corpus["texts"][0]["sentences"]
    for lang in ("en", "zh", "ru"):
        ids = [i for p in corpus["pairs"] for i in p["sentences"][lang]]
        assert ids == list(range(len(sentences[lang])))
        for p in corpus["pairs"]:
            assert join_sentences([sentences[lang][i] for i in p["sentences"][lang]],
                                  lang) == p[lang]

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


@requires_spacy
def test_build_with_imported_source(project):
    """Импортированный источник (синтетические файлы ООН): происхождение, уровень и регистры."""
    import shutil
    from pathlib import Path

    from pipeline.importers import un_corpus

    src = project.root / "downloads"
    src.mkdir()
    fixtures = Path(__file__).parent / "fixtures" / "un_synthetic"
    for lang in ("en", "zh", "ru"):
        shutil.copy(fixtures / f"UNv1.0.testset.{lang}", src)
    un_corpus.run(project.path("raw"), project.root / "cache", {}, source=src)
    run_build(project, use_llm=False)
    out = project.path("output")
    corpus = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))

    imported = [p for p in corpus["pairs"] if p["text_id"] == "un_corpus"]
    assert len(imported) == 4
    assert [p["origin"]["line"] for p in imported] == [1, 3, 5, 6]
    assert all(p["origin"]["source"] == "un_corpus" and "level" not in p["origin"]
               for p in imported)
    example = [p for p in corpus["pairs"] if p["text_id"] == "example"]
    assert all("origin" not in p and p["level"] == "A2" for p in example)
    assert all(0 <= p["difficulty"] <= 1 and p["level"] for p in corpus["pairs"])

    texts = {t["id"]: t for t in corpus["texts"]}
    assert texts["un_corpus"]["register"] == "официальный"
    assert texts["example"]["register"] == "учебный"
    registers = {r["register"]: r for r in stats["registers"]}
    assert list(registers) == ["учебный", "официальный"]
    official = registers["официальный"]
    assert official["pairs"] == 4 and official["texts"] == 1
    assert official["articles"]["counts"]["the"] >= 3
    assert sum(c["count"] for c in official["cases"]["distribution"]) == \
        official["cases"]["nouns"]
    assert sum(stats["levels"].values()) == stats["totals"]["pairs"]


def test_units_must_match_paragraphs(tmp_path):
    import pytest

    from pipeline.sources import SourceError, read_text

    d = tmp_path / "src"
    d.mkdir()
    for lang, text in (("en", "One.\n\nTwo."), ("zh", "一。\n\n二。"), ("ru", "Один.\n\nДва.")):
        (d / f"{lang}.txt").write_text(text, encoding="utf-8")
    (d / "meta.json").write_text(json.dumps({"title": "t", "source": "s", "topic": "t",
                                             "level": "A1"}), encoding="utf-8")
    (d / "units.jsonl").write_text('{"n": 1}\n', encoding="utf-8")
    with pytest.raises(SourceError, match="повторите импорт"):
        read_text(d)
    (d / "units.jsonl").write_text('{"n": 1}\n{"n": 2}\n', encoding="utf-8")
    assert [u["n"] for u in read_text(d).units or []] == [1, 2]
