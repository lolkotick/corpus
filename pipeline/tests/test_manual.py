import csv

import pytest

from pipeline.manual import (
    ManualImportError,
    Overrides,
    apply_overrides,
    import_csv,
    normalize_status,
)


def corpus():
    return {"pairs": [
        {"id": "t-001", "en": "A cat.", "zh": "一只猫。", "ru": "Кошка.", "status": "auto",
         "comment": ""},
        {"id": "t-002", "en": "The dog.", "zh": "那只狗。", "ru": "Собака.", "status": "auto",
         "comment": ""},
        {"id": "t-003", "en": "Bye.", "zh": "再见。", "ru": "Пока.", "status": "auto",
         "comment": ""},
    ]}


def write_csv(path, rows, delimiter=","):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "status", "en", "zh", "ru", "comment"],
                                delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def test_status_aliases():
    assert normalize_status("Проверено") == "checked"
    assert normalize_status(" исправлено ") == "corrected"
    assert normalize_status("") is None
    with pytest.raises(ManualImportError):
        normalize_status("maybe")


@pytest.mark.parametrize("delimiter", [",", ";"])
def test_import_records_only_differences(tmp_path, delimiter):
    path = tmp_path / "edit.csv"
    write_csv(path, [
        {"id": "t-001", "status": "auto", "en": "A cat.", "zh": "一只猫。", "ru": "Кошка.",
         "comment": ""},
        {"id": "t-002", "status": "", "en": "The dog.", "zh": "那条狗。", "ru": "Собака.",
         "comment": "классификатор"},
        {"id": "t-003", "status": "проверено", "en": "Bye.", "zh": "再见。", "ru": "Пока.",
         "comment": ""},
    ], delimiter)
    overrides = Overrides()
    counts, problems = import_csv(path, corpus(), overrides)
    assert problems == []
    assert counts == {"rows": 3, "changed": 1, "checked": 1, "deleted": 0, "unchanged": 1}
    assert overrides.pairs["t-002"] == {
        "zh": "那条狗。", "comment": "классификатор", "status": "corrected",
        "base": {"en": "The dog."},
    }
    assert overrides.pairs["t-003"]["status"] == "checked"
    assert "t-001" not in overrides.pairs


def test_import_delete_and_unknown_rows(tmp_path):
    path = tmp_path / "edit.csv"
    write_csv(path, [
        {"id": "t-003", "status": "удалить", "en": "", "zh": "", "ru": "", "comment": ""},
        {"id": "t-999", "status": "auto", "en": "x", "zh": "x", "ru": "x", "comment": ""},
        {"id": "t-001", "status": "???", "en": "A cat.", "zh": "一只猫。", "ru": "Кошка.",
         "comment": ""},
    ])
    overrides = Overrides()
    counts, problems = import_csv(path, corpus(), overrides)
    assert counts["deleted"] == 1
    assert overrides.pairs["t-003"]["deleted"] is True
    assert len(problems) == 2


def test_non_utf8_file_is_rejected(tmp_path):
    path = tmp_path / "cp1251.csv"
    path.write_bytes("id,status,en,zh,ru\nt-001,проверено,a,b,c\n".encode("cp1251"))
    with pytest.raises(ManualImportError, match="UTF-8"):
        import_csv(path, corpus(), Overrides())


def test_apply_overrides_and_base_check(tmp_path):
    overrides = Overrides(pairs={
        "t-001": {"ru": "Кот.", "status": "corrected", "base": {"en": "A cat."}},
        "t-002": {"zh": "那条狗。", "status": "corrected", "base": {"en": "Another text."}},
        "t-003": {"deleted": True, "base": {"en": "Bye."}},
        "t-404": {"status": "checked", "base": {"en": "?"}},
    })
    records = [dict(p) for p in corpus()["pairs"]]
    kept, stats, warnings = apply_overrides(records, overrides)
    assert [r["id"] for r in kept] == ["t-001", "t-002"]
    assert kept[0]["ru"] == "Кот." and kept[0]["status"] == "corrected"
    assert kept[1]["zh"] == "那只狗。"  # автоматический сегмент изменился — правка не применена
    assert stats == {"applied": 1, "deleted": 1, "skipped": 2}
    assert len(warnings) == 2

    overrides.save(tmp_path / "overrides.json")
    loaded = Overrides.load(tmp_path / "overrides.json")
    assert loaded.pairs == overrides.pairs
