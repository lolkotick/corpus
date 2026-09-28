import json

import pytest

from pipeline import llm
from pipeline.align.baseline import DiagonalAligner
from pipeline.align.dp import AlignmentError, Bead
from pipeline.align.llm_align import LlmAligner, build_prompt, parse_groups
from pipeline.cli import main
from pipeline.compare_aligners import agreement, compare, run
from pipeline.segment import join_sentences

GC = {"variance": {"zh": 9.0, "ru": 6.8}}
TYPES = [(1, 1), (1, 2), (2, 1), (1, 0), (0, 1)]


def test_diagonal_aligner_puts_leftovers_into_last_group():
    beads, method = DiagonalAligner().align_pair(["a", "b", "c"], ["x", "y"], "zh")
    assert method == "diagonal"
    assert beads == [Bead(0, 1, 0, 1, 1.0), Bead(1, 3, 1, 2, 1.0)]
    with pytest.raises(AlignmentError):
        DiagonalAligner().align_pair([], ["x"], "zh")


def test_parse_groups_accepts_valid_and_rejects_gaps():
    beads = parse_groups({"groups": [{"en": [1], "target": [1, 2]}, {"en": [2], "target": [3]}]},
                         2, 3)
    assert [(b.src_start, b.src_end, b.tgt_start, b.tgt_end) for b in beads] == [
        (0, 1, 0, 2), (1, 2, 2, 3)]
    with pytest.raises(AlignmentError):
        parse_groups({"groups": [{"en": [1], "target": [2]}]}, 1, 2)  # пропущено ZH 1
    with pytest.raises(AlignmentError):
        parse_groups({"groups": [{"en": [1], "target": [1]}]}, 2, 1)  # EN 2 без группы


def test_llm_aligner_uses_cache_and_falls_back(tmp_path, monkeypatch):
    calls = []

    def fake_request(anthropic, client, model, effort, prompt, system, schema):
        calls.append(prompt)
        if "broken" in prompt:
            return {"groups": [{"en": [5], "target": [1]}]}, "", False
        return {"groups": [{"en": [1], "target": [1]}, {"en": [2], "target": [2]}]}, "", False

    monkeypatch.setattr(llm, "_request", fake_request)
    aligner = LlmAligner(object(), object(), {"model": "claude-opus-5"}, tmp_path / "cache", GC,
                         TYPES)
    src, tgt = ["One.", "Two."], ["一。", "二。"]
    beads, method = aligner.align_pair(src, tgt, "zh")
    assert method == "llm" and len(beads) == 2
    aligner.align_pair(src, tgt, "zh")
    assert len(calls) == 1 and aligner.from_cache == 1  # второй раз — из кэша

    beads, method = aligner.align_pair(["broken"], ["坏。"], "zh")
    assert method == "gale_church" and aligner.fallbacks == 1
    assert any("отклонён" in w for w in aligner.warnings)
    assert "1. One." in build_prompt(src, tgt, "zh")


def test_llm_aligner_without_client_uses_gale_church(tmp_path):
    aligner = LlmAligner(None, None, {}, tmp_path, GC, TYPES)
    beads, method = aligner.align_pair(["A.", "B."], ["А.", "Б."], "ru")
    assert method == "gale_church" and len(beads) == 2


def _synthetic_gold(project, cmp, path):
    """Синтетический эталон для теста: вердикт «верно» для групп Гейла–Чёрча."""
    gc = next(r for r in cmp.runs if r.method == "gale_church")
    text_id = "example"
    sents = cmp.sentences[text_id]
    pairs = []
    for k, (en, zh) in enumerate(gc.links["zh"][text_id][:6]):
        ru = next(link for link in gc.links["ru"][text_id] if link[0] == en)[1]
        ids = {"en": list(en), "zh": list(zh), "ru": list(ru)}
        pairs.append({
            "id": f"{text_id}-{k + 1:03d}", "text_id": text_id, "reviewed_at": "2026-01-01",
            "text": {lang: join_sentences([sents[lang][i] for i in ids[lang]], lang)
                     for lang in ids},
            "sentences": ids,
            "alignment": {"zh": {"verdict": "correct", "links": []},
                          "ru": {"verdict": "correct", "links": []}},
            "phenomena": {lang: {"mode": "all-correct", "items": [], "missed": []}
                          for lang in ("en", "zh", "ru")},
            "comment": "",
        })
    path.write_text(json.dumps({
        "format": "corpus-gold", "version": 1, "synthetic": True,
        "_comment": "СИНТЕТИЧЕСКИЕ ДАННЫЕ ДЛЯ ТЕСТА",
        "sample": {"seed": 1, "size": len(pairs), "strategy": "proportional",
                   "pair_ids": [p["id"] for p in pairs]},
        "pairs": pairs,
    }, ensure_ascii=False), encoding="utf-8")


def test_compare_without_gold_reports_no_metrics(project, tmp_path):
    methods = ["gale_church", "diagonal", "labse", "llm"]
    code, files = run(project, tmp_path / "gold.json", tmp_path / "out", methods)
    assert code == 0
    names = {f.name for f in files}
    assert "aligners_metrics.csv" not in names and "aligners_f1.png" not in names
    assert {"aligners.md", "aligners_time.csv", "aligners_time.png"} <= names
    report = (tmp_path / "out" / "aligners.md").read_text(encoding="utf-8")
    assert "Метрики не рассчитаны" in report and "Точность" not in report
    assert "LaBSE (алгоритм Bertalign) | нет" in report or "LLM (Claude) | нет" in report
    assert not (tmp_path / "gold.json").exists()


def test_compare_with_synthetic_gold(project, tmp_path):
    gold = tmp_path / "gold.json"
    first = compare(project, gold, ["gale_church", "diagonal"])
    assert first.gold_message
    _synthetic_gold(project, first, gold)

    cmp = compare(project, gold, ["gale_church", "diagonal"])
    assert not cmp.gold_message and len(cmp.truths["zh"]) == 6
    gc, diag = cmp.runs
    assert gc.scores["zh"].strict.precision == 1.0 and gc.scores["zh"].strict.recall == 1.0
    assert diag.scores["zh"].strict.f1 is not None
    assert len(cmp.examples) <= 10
    same, total = agreement(gc, gc, "zh")
    assert same == total > 0

    code, _ = run(project, gold, tmp_path / "out", ["gale_church", "diagonal"])
    report = (tmp_path / "out" / "aligners.md").read_text(encoding="utf-8")
    assert code == 0 and "синтетические данные" in report
    assert (tmp_path / "out" / "aligners_f1.png").read_bytes().startswith(b"\x89PNG")


def test_cli_rejects_unknown_method(capsys):
    assert main(["compare-aligners", "--methods", "magic"]) == 1
    assert "неизвестные методы" in capsys.readouterr().out
