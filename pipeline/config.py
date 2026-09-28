"""Загрузка конфигурации pipeline из config.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"


@dataclass
class Config:
    """Обёртка над словарём конфигурации с удобным доступом к путям."""

    data: dict[str, Any]
    root: Path = ROOT

    def get(self, dotted: str, default: Any = None) -> Any:
        """Вернуть значение по пути вида ``"alignment.method"``."""
        node: Any = self.data
        for key in dotted.split("."):
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def path(self, key: str) -> Path:
        """Абсолютный путь из секции ``paths``."""
        value = self.get(f"paths.{key}")
        if value is None:
            raise KeyError(f"В config.yaml нет paths.{key}")
        return (self.root / value).resolve()

    def resolve(self, relative: str) -> Path:
        return (self.root / relative).resolve()


def load_config(path: Path | None = None, root: Path | None = None) -> Config:
    config_path = path or DEFAULT_CONFIG
    with open(config_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Config(data=data, root=root or ROOT)
