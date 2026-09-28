from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from pipeline.config import DEFAULT_CONFIG, ROOT, Config

EXAMPLE_DIR = ROOT / "data" / "raw" / "example"
CLASSIFIERS = ROOT / "pipeline" / "resources" / "zh_classifiers.tsv"


@pytest.fixture
def project(tmp_path: Path) -> Config:
    """Изолированный проект: пример текста, конфиг и пустые папки вывода во временной папке."""
    data = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    shutil.copytree(EXAMPLE_DIR, tmp_path / "data" / "raw" / "example")
    (tmp_path / "pipeline" / "resources").mkdir(parents=True)
    shutil.copy(CLASSIFIERS, tmp_path / "pipeline" / "resources" / "zh_classifiers.tsv")
    return Config(data=data, root=tmp_path)


def spacy_model_available(name: str = "en_core_web_sm") -> bool:
    try:
        import spacy

        spacy.load(name)
    except (ImportError, OSError):
        return False
    return True


requires_spacy = pytest.mark.skipif(
    not spacy_model_available(), reason="нет модели spaCy en_core_web_sm"
)
