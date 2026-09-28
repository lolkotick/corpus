"""Импорт корпуса ООН на синтетических файлах (fixtures/un_synthetic — не настоящие документы)."""

import json
import shutil
import tarfile
import zipfile
from pathlib import Path

import pytest

from pipeline.cli import main
from pipeline.importers import un_corpus
from pipeline.importers.common import ImportFailed

pytest.importorskip("wordfreq")

FIXTURES = Path(__file__).parent / "fixtures" / "un_synthetic"
ALIGNED = [f"UNv1.0.testset.{lang}" for lang in ("en", "zh", "ru")]
OPUS = ["UNPC.en-zh.en", "UNPC.en-zh.zh", "UNPC.en-ru.en", "UNPC.en-ru.ru"]


def copy(names, target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(FIXTURES / name, target / name)
    return target


def read_units(path: Path) -> list[dict]:
    return [json.loads(line) for line in
            (path / "units.jsonl").read_text(encoding="utf-8").splitlines()]


def test_aligned_files(tmp_path):
    src = copy(ALIGNED, tmp_path / "src")
    path, stats = un_corpus.run(tmp_path / "raw", tmp_path / "cache", {}, source=src)
    assert path == tmp_path / "raw" / "un_corpus"
    assert stats.candidates == 6 and stats.too_short_or_long == 1 and stats.duplicates == 1
    assert stats.written == 4
    units = read_units(path)
    assert [u["line"] for u in units] == [1, 3, 5, 6]
    assert units[0]["source"] == "un_corpus" and units[0]["file"] == "UNv1.0.testset"
    ru = (path / "ru.txt").read_text(encoding="utf-8").split("\n\n")
    assert ru[1] == "Комитет рассмотрел доклад Генерального секретаря."
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    assert meta["register"] == "официальный" and "Ziemski" in meta["attribution"]


def test_limit(tmp_path):
    src = copy(ALIGNED, tmp_path / "src")
    _, stats = un_corpus.run(tmp_path / "raw", tmp_path / "cache", {"limit": 2}, source=src)
    assert stats.kept == 4 and stats.written == 2
    _, stats = un_corpus.run(tmp_path / "raw", tmp_path / "cache", {}, source=src, max_lines=3)
    assert stats.candidates == 3


def test_tar_archive_is_extracted_to_cache(tmp_path):
    archive = tmp_path / "testsets.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in ALIGNED:
            tar.add(FIXTURES / name, arcname=f"testsets/{name}")
    _, stats = un_corpus.run(tmp_path / "raw", tmp_path / "cache", {}, source=archive)
    assert stats.written == 4
    assert sorted(p.name for p in (tmp_path / "cache").iterdir()) == sorted(ALIGNED)
    # Второй запуск находит распакованные файлы в кэше.
    _, stats = un_corpus.run(tmp_path / "raw", tmp_path / "cache", {})
    assert stats.written == 4


def test_opus_pairs_are_joined_by_english(tmp_path):
    src = copy(OPUS, tmp_path / "src")
    path, stats = un_corpus.run(tmp_path / "raw", tmp_path / "cache", {}, source=src)
    # Заголовок прописными и пункт «(a) …» — не предложения; строка про доклад дважды
    # встречается в паре EN–RU с разными переводами — пропущена.
    assert stats.fragments == 2 and stats.candidates == 2 and stats.written == 2
    assert any("повторяющихся в файлах: 1" in note for note in stats.notes)
    units = read_units(path)
    assert [(u["line"], u["line_en_ru"]) for u in units] == [(3, 4), (5, 2)]
    zh = (path / "zh.txt").read_text(encoding="utf-8").split("\n\n")
    ru = (path / "ru.txt").read_text(encoding="utf-8").split("\n\n")
    assert zh[1].strip() == "两名专家出席了会议。"
    assert ru[1].strip() == "В сессии приняли участие два эксперта."


def test_opus_zip_download(tmp_path):
    links = {}
    for pair in ("en-zh", "en-ru"):
        archive = tmp_path / "remote" / f"{pair}.txt.zip"
        archive.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive, "w") as zf:
            for name in OPUS:
                if f".{pair}." in name:
                    zf.write(FIXTURES / name, arcname=name)
            zf.writestr("README", "synthetic")
        links[pair] = archive.as_uri()
    _, stats = un_corpus.run(tmp_path / "raw", tmp_path / "cache", {"opus": links})
    assert stats.written == 2
    # Архивы не распаковываются: строки читаются прямо из zip.
    assert sorted(p.name for p in (tmp_path / "cache").iterdir()) == \
        ["en-ru.txt.zip", "en-zh.txt.zip"]
    _, stats = un_corpus.run(tmp_path / "raw", tmp_path / "cache", {})
    assert stats.written == 2


def test_sentence_check():
    assert un_corpus.is_sentence("The meeting rose at 1 p.m.", "en")
    assert un_corpus.is_sentence("“Requests the Secretary-General to report;”", "en")
    assert un_corpus.is_sentence("大会通过了该决议。", "zh")
    assert un_corpus.is_sentence("Комитет рассмотрел доклад.", "ru")
    assert not un_corpus.is_sentence("OF THE UNITED NATIONS ADDRESSED.", "en")
    assert not un_corpus.is_sentence("Chairman of the Second Committee", "en")
    assert not un_corpus.is_sentence("10. Air and surface freight", "en")
    assert not un_corpus.is_sentence("(a) 运送装备", "zh")
    assert not un_corpus.is_sentence("а) перевозка имущества.", "ru")


def test_sentences_only_can_be_switched_off(tmp_path):
    src = copy(OPUS, tmp_path / "src")
    _, stats = un_corpus.run(tmp_path / "raw", tmp_path / "cache", {"sentences_only": False},
                             source=src, require_phenomenon=False)
    assert stats.fragments == 0 and stats.candidates == 4


def test_missing_files_print_manual_instructions(tmp_path):
    with pytest.raises(ImportFailed, match="Как положить файлы корпуса ООН вручную"):
        un_corpus.run(tmp_path / "raw", tmp_path / "cache", {})
    with pytest.raises(ImportFailed, match="Как положить"):
        un_corpus.run(tmp_path / "raw", tmp_path / "cache",
                      {"url": (tmp_path / "missing.tar.gz").as_uri()})
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ImportFailed, match="нет трёх параллельных файлов"):
        un_corpus.run(tmp_path / "raw", tmp_path / "cache", {}, source=empty)


def test_cli_import(project, capsys):
    src = copy(ALIGNED, project.root / "downloads")
    import yaml

    # Абсолютные пути: CLI считает относительные пути от корня репозитория.
    data = {**project.data, "paths": {**project.data["paths"], "raw": str(project.path("raw")),
                      "logs": str(project.path("logs"))},
            "importers": {**project.data["importers"], "cache": str(project.root / "cache")}}
    config = project.root / "config.yaml"
    config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    code = main(["--config", str(config), "import", "un", "--from", str(src), "--limit", "3"])
    assert code == 0
    out = capsys.readouterr().out
    assert "записано 3" in out and "python -m pipeline build" in out
    assert (project.path("raw") / "un_corpus" / "units.jsonl").exists()
    assert "записано 3" in (project.path("logs") / "import_un.md").read_text("utf-8")
    code = main(["--config", str(config), "import", "un", "--from", str(project.root / "nope")])
    assert code == 1 and "вручную" in capsys.readouterr().err
