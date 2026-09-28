import bz2
import io
import json
import tarfile

import pytest

from pipeline.importers.common import (
    Filters,
    ImportFailed,
    ImportStats,
    SourceMeta,
    Unit,
    dedupe_key,
    length_ok,
    open_text,
    phenomena,
    select,
    write_text,
)

pytest.importorskip("wordfreq")

META = SourceMeta(text_id="synthetic", title="Synthetic", title_ru="Синтетика",
                  title_zh="合成", source="тест", source_url="", license="—", license_url="",
                  attribution="—", register="бытовой", topic="тест")


def unit(en, zh, ru, n=0):
    return Unit(en, zh, ru, origin={"source": "test", "n": n})


def test_filters_length_and_config():
    f = Filters.from_config({"en_words": [2, 4], "zh_chars": [2, 10]})
    assert f.en_words == (2, 4) and f.ru_words == (3, 25) and f.zh_chars == (2, 10)
    assert length_ok(unit("A big cat.", "一只猫", "Большая кошка спит."), f)
    assert not length_ok(unit("Cat.", "一只猫", "Большая кошка спит."), f)
    assert not length_ok(unit("A very big grey cat.", "一只猫", "Большая кошка спит."), f)


def test_dedupe_key_ignores_case_punctuation_and_yo():
    assert dedupe_key("Ёлка стоит!") == dedupe_key("елка стоит.")


def test_phenomena_detection():
    assert phenomena(unit("The cat sleeps.", "我们回家。", "Мы идём.")) == \
        {"article": True, "classifier": False, "case": False}
    assert phenomena(unit("Cats sleep.", "三本书", "Мы идём.")) == \
        {"article": False, "classifier": True, "case": False}
    assert phenomena(unit("Cats sleep.", "我们回家。", "Я читаю книгу.")) == \
        {"article": False, "classifier": False, "case": True}
    # «a» внутри слова — не артикль.
    assert not phenomena(unit("Cats have fun.", "好", "Мы"))["article"]


def test_select_filters_dedupes_and_samples_reproducibly():
    units = [unit(f"The cat number {n} sleeps.", f"第{n}只猫在睡觉", f"Кошка номер {n} спит.", n)
             for n in range(10)]
    units.append(unit("The cat number 3 sleeps!", "别的猫在睡觉", "Другая кошка спит.", 99))
    units.append(unit("Short.", "猫在睡觉", "Кошка спит тут.", 100))
    stats = ImportStats()
    kept = select(units, Filters(), limit=4, seed=1, stats=stats,
                  order_key=lambda u: u.origin["n"])
    assert stats.candidates == 12 and stats.too_short_or_long == 1 and stats.duplicates == 1
    assert stats.kept == 10 and len(kept) == 4
    assert [u.origin["n"] for u in kept] == sorted(u.origin["n"] for u in kept)
    again = select(units, Filters(), limit=4, seed=1, stats=ImportStats(),
                   order_key=lambda u: u.origin["n"])
    assert [u.origin for u in again] == [u.origin for u in kept]


def test_write_text_creates_raw_text_and_units(tmp_path):
    from pipeline.sources import read_text

    units = [unit("The cat is sleeping.", "猫在睡觉。", "Кошка спит.", 1),
             unit("I bought\nthree books.", "我买了三本书。", "Я купил три книги.", 2)]
    target = write_text(tmp_path, META, units)
    raw = read_text(target)
    assert raw.meta.id == "synthetic" and raw.meta.register == "бытовой"
    assert raw.meta.extra["units"] == "2"
    assert raw.paragraphs["en"] == ["The cat is sleeping.", "I bought three books."]
    assert raw.units is not None and [u["n"] for u in raw.units] == [1, 2]
    assert all(u["level"] and 0 <= u["difficulty"] <= 1 for u in raw.units)
    meta = json.loads((target / "meta.json").read_text(encoding="utf-8"))
    assert meta["level"] in {u["level"] for u in raw.units}
    with pytest.raises(ImportFailed):
        write_text(tmp_path, META, [])


def test_open_text_reads_archives(tmp_path):
    (tmp_path / "a.txt.bz2").write_bytes(bz2.compress("один\nдва\n".encode()))
    assert list(open_text(tmp_path / "a.txt.bz2")) == ["один\n", "два\n"]
    data = b"1\t2\n"
    with tarfile.open(tmp_path / "links.tar.bz2", "w:bz2") as tar:
        info = tarfile.TarInfo("links.csv")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    assert list(open_text(tmp_path / "links.tar.bz2", "links.csv")) == ["1\t2\n"]
    with pytest.raises(ImportFailed):
        list(open_text(tmp_path / "links.tar.bz2", "other.csv"))
