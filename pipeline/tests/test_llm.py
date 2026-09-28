import json

import pipeline.llm as llm


def record(idx, score, disputed=False):
    return {
        "id": f"t-{idx:03d}", "text_id": "t", "en": "A cat.", "zh": "一只猫。", "ru": "Кошка.",
        "alignment_type": "1-1-1", "alignment_score": score,
        "alignment": {"method": "gale_church", "en_zh": score, "en_ru": score},
        "annotations": {"en": [], "zh": [], "ru": [{
            "id": "ru1", "text": "Кошка", "lemma": "кошка", "case": "nomn", "number": "sing",
            "confidence": 0.6, "alternatives": ["accs"], "disputed": disputed,
        }]},
        "status": "auto", "llm_note": None, "comment": "",
    }


CONFIG = {"model": "claude-opus-5", "effort": "medium", "max_items": 10}
ANSWER = {
    "alignment_ok": False,
    "alignment_comment": "Русское предложение относится к следующей паре.",
    "annotations": [{"id": "ru1", "ok": False, "suggestion": "падеж: винительный",
                     "comment": "прямое дополнение"}],
    "summary": "Нужна правка.",
}


def test_select_candidates_orders_by_score():
    records = [record(1, 0.9), record(2, 0.1), record(3, 0.9, disputed=True)]
    selected = llm.select_candidates(records, 0.35, CONFIG)
    assert [records[i]["id"] for i, _r, _d in selected] == ["t-002", "t-003"]
    assert selected[1][1] == ["спорная разметка"]


def test_prompt_contains_triple_and_disputed_items():
    records = [record(1, 0.1, disputed=True)]
    idx, reasons, disputed = llm.select_candidates(records, 0.35, CONFIG)[0]
    prompt = llm.build_prompt(records, idx, reasons, disputed, "Test")
    assert "EN: A cat." in prompt and "ZH: 一只猫。" in prompt
    assert "ru1" in prompt and "винительный" in prompt


def test_without_key_nothing_is_called(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "api_key_available", lambda root: False)
    monkeypatch.setattr(llm, "_call_claude", lambda *a: (_ for _ in ()).throw(AssertionError))
    records = [record(1, 0.1, disputed=True)]
    stats = llm.review(records, {}, CONFIG, 0.35, tmp_path / "cache", tmp_path)
    assert stats.enabled is False and stats.checked == 0
    assert "ANTHROPIC_API_KEY" in stats.reason
    assert records[0]["llm_note"] is None


def test_review_with_fake_api_and_cache(tmp_path, monkeypatch):
    calls = []

    def fake_call(client, model, effort, prompt, *_):
        calls.append(prompt)
        return dict(ANSWER, _model=model)

    monkeypatch.setattr(llm, "api_key_available", lambda root: True)
    monkeypatch.setattr(llm, "_call_claude", fake_call)
    records = [record(1, 0.1, disputed=True)]
    cache = tmp_path / "cache"
    stats = llm.review(records, {"t": {"title": "Test"}}, CONFIG, 0.35, cache, tmp_path)
    assert stats.enabled and stats.checked == 1 and len(calls) == 1
    assert stats.suggestions == 2 and stats.alignment_flags == 1
    note = records[0]["llm_note"]
    assert note["annotations"][0]["suggestion"] == "падеж: винительный"
    assert note["alignment_ok"] is False
    assert len(list(cache.glob("*.json"))) == 1

    # Без ключа сохранённый ответ применяется из кэша, API не вызывается.
    monkeypatch.setattr(llm, "api_key_available", lambda root: False)
    records2 = [record(1, 0.1, disputed=True)]
    stats2 = llm.review(records2, {"t": {"title": "Test"}}, CONFIG, 0.35, cache, tmp_path)
    assert stats2.from_cache == 1 and len(calls) == 1
    assert records2[0]["llm_note"]["summary"] == "Нужна правка."


def test_api_errors_do_not_break_build(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "api_key_available", lambda root: True)
    monkeypatch.setattr(llm, "_call_claude",
                        lambda *a: (_ for _ in ()).throw(RuntimeError("ответ обрезан")))
    records = [record(i, 0.1, disputed=True) for i in range(1, 6)]
    stats = llm.review(records, {}, CONFIG, 0.35, tmp_path / "cache", tmp_path)
    assert stats.errors == 3  # после трёх ошибок подряд проверка останавливается
    assert any("остановлена" in w for w in stats.warnings)
    assert all(r["llm_note"] is None for r in records)


def test_response_schema_is_strict():
    schema = llm.RESPONSE_SCHEMA
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    json.dumps(schema)
