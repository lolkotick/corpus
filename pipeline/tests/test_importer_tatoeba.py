"""Импорт Tatoeba на синтетических файлах (fixtures/tatoeba_synthetic — не настоящие данные)."""

import bz2
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from pipeline.importers import tatoeba
from pipeline.importers.common import ImportFailed

pytest.importorskip("wordfreq")
pytest.importorskip("opencc")

FIXTURES = Path(__file__).parent / "fixtures" / "tatoeba_synthetic"


def pack(target: Path, with_cc0: bool = True) -> Path:
    """Разложить фикстуры так, как они лежат на downloads.tatoeba.org."""
    target.mkdir(parents=True, exist_ok=True)
    for lang in ("eng", "cmn", "rus"):
        name = f"{lang}_sentences_detailed.tsv"
        (target / f"{name}.bz2").write_bytes(bz2.compress((FIXTURES / name).read_bytes()))
    archives = [("links", "links.csv")] + ([("sentences_CC0", "sentences_CC0.csv")]
                                           if with_cc0 else [])
    for archive, member in archives:
        with tarfile.open(target / f"{archive}.tar.bz2", "w:bz2") as tar:
            tar.add(FIXTURES / member, arcname=member)
    return target


def test_simplified_check():
    assert tatoeba.is_simplified("她有一只狗。")
    assert not tatoeba.is_simplified("她有一隻狗。")
    assert not tatoeba.is_simplified("Hello")


def test_import_selects_triples_with_attribution(tmp_path):
    src = pack(tmp_path / "downloads")
    path, stats = tatoeba.run(tmp_path / "raw", tmp_path / "cache", {}, from_dir=src)
    assert path == tmp_path / "raw" / "tatoeba"
    # Кандидаты: предложения 1, 2, 3, 4, 5, 7 (у 6 только традиционные иероглифы, у 9 нет RU).
    assert stats.candidates == 6
    assert (stats.too_short_or_long, stats.duplicates, stats.no_phenomenon) == (1, 1, 1)
    assert stats.kept == stats.written == 3

    units = [json.loads(line) for line in
             (path / "units.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [u["en"]["id"] for u in units] == [1, 2, 7]
    assert [u["zh"]["id"] for u in units] == [101, 102, 107]  # 107 — упрощённый вариант
    assert [u["ru"]["id"] for u in units] == [201, 202, 207]  # 207 < 208 — меньший id
    first = units[0]
    assert first["source"] == "tatoeba"
    assert first["en"] == {"id": 1, "lang": "eng", "author": "synth_anna",
                           "license": "CC BY 2.0 FR",
                           "url": "https://tatoeba.org/sentences/show/1"}
    assert units[1]["zh"]["license"] == units[1]["ru"]["license"] == "CC0 1.0"
    assert units[2]["en"]["author"] == ""  # \N — автор не указан
    assert all(u["level"] and 0 < u["difficulty"] < 1 for u in units)

    en = (path / "en.txt").read_text(encoding="utf-8").split("\n\n")
    zh = (path / "zh.txt").read_text(encoding="utf-8").split("\n\n")
    assert en[0] == "The cat is sleeping on the chair." and zh[2].strip() == "她有一只狗。"
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    assert meta["register"] == "бытовой" and meta["license"].startswith("CC BY 2.0 FR")
    assert meta["license_url"] == "https://tatoeba.org/terms_of_use"


def test_limit_seed_and_any_sentence(tmp_path):
    src = pack(tmp_path / "downloads")
    _, stats = tatoeba.run(tmp_path / "raw", tmp_path / "cache", {"limit": 2, "seed": 7},
                           from_dir=src, require_phenomenon=False)
    assert stats.no_phenomenon == 0 and stats.kept == 4 and stats.written == 2
    first = (tmp_path / "raw" / "tatoeba" / "units.jsonl").read_text(encoding="utf-8")
    tatoeba.run(tmp_path / "raw", tmp_path / "cache", {"limit": 2, "seed": 7}, from_dir=src,
                require_phenomenon=False)
    assert (tmp_path / "raw" / "tatoeba" / "units.jsonl").read_text(encoding="utf-8") == first


def test_without_cc0_list_everything_is_cc_by(tmp_path):
    src = pack(tmp_path / "downloads", with_cc0=False)
    path, stats = tatoeba.run(tmp_path / "raw", tmp_path / "cache", {}, from_dir=src)
    licenses = {u[lang]["license"] for line in (path / "units.jsonl").read_text("utf-8").split("\n")
                if line for u in [json.loads(line)] for lang in ("en", "zh", "ru")}
    assert licenses == {"CC BY 2.0 FR"}
    assert any("CC0" in note for note in stats.notes)


def test_uncompressed_files_are_accepted(tmp_path):
    src = tmp_path / "plain"
    shutil.copytree(FIXTURES, src)
    _, stats = tatoeba.run(tmp_path / "raw", tmp_path / "cache", {}, from_dir=src)
    assert stats.written == 3


def test_missing_file_explains_where_to_get_it(tmp_path):
    src = pack(tmp_path / "downloads")
    (src / "links.tar.bz2").unlink()
    with pytest.raises(ImportFailed, match=r"tatoeba\.org/downloads"):
        tatoeba.run(tmp_path / "raw", tmp_path / "cache", {}, from_dir=src)


def test_download_failure_is_reported(tmp_path):
    config = {"files": {key: f"file://{tmp_path}/nope/{key}.bz2"
                        for key in ("eng", "cmn", "rus", "links", "cc0")}}
    with pytest.raises(ImportFailed, match="не удалось скачать"):
        tatoeba.run(tmp_path / "raw", tmp_path / "cache", config)
