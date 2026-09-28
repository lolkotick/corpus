"""Выравнивание предложений с помощью LLM (Claude) — для сравнения методов.

Модели дают пронумерованные предложения EN и ZH/RU (один абзац) и просят вернуть
группы соответствий по порядку. Ответ проверяется: группы должны идти подряд,
без пропусков и повторов, каждая — не больше трёх предложений с каждой стороны.
Если ответ некорректен или API недоступен, для этого абзаца используется
Гейл–Чёрч, а в предупреждения пишется причина. Ответы кэшируются в
data/llm_cache/align/, поэтому повторный запуск бесплатен и воспроизводим.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pipeline.align.dp import AlignmentError, Bead
from pipeline.align.gale_church import gale_church_align

PROMPT_VERSION = 1
MAX_GROUP = 3
LANG_NAMES = {"zh": "китайском", "ru": "русском"}

SYSTEM_PROMPT = """Ты выравниваешь параллельный текст по предложениям: английский оригинал \
и его перевод. Верни группы соответствий в порядке следования текста. Каждая группа — \
номера подряд идущих предложений EN и номера подряд идущих предложений перевода, которые \
передают одно и то же содержание. Обычно группа 1–1; 1–2 или 2–1, если переводчик разделил \
или объединил предложения. Пустой список с одной стороны — только если у предложения \
действительно нет соответствия. Каждое предложение должно попасть ровно в одну группу, \
порядок групп совпадает с порядком текста."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "en": {"type": "array", "items": {"type": "integer"}},
                    "target": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["en", "target"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["groups"],
    "additionalProperties": False,
}


def build_prompt(src: Sequence[str], tgt: Sequence[str], tgt_lang: str) -> str:
    lines = ["Предложения на английском:"]
    lines += [f"{i + 1}. {s}" for i, s in enumerate(src)]
    lines += ["", f"Предложения на {LANG_NAMES.get(tgt_lang, tgt_lang)}:"]
    lines += [f"{j + 1}. {t}" for j, t in enumerate(tgt)]
    lines += ["", "Номера — с единицы, как в списках выше."]
    return "\n".join(lines)


def parse_groups(data: dict[str, Any], n: int, m: int) -> list[Bead]:
    """Ответ модели → бусины (номера с нуля). AlignmentError, если группы некорректны."""
    beads: list[Bead] = []
    i = j = 0
    for group in data.get("groups", []):
        en = [int(x) - 1 for x in group.get("en", [])]
        tgt = [int(x) - 1 for x in group.get("target", [])]
        if not en and not tgt:
            continue
        if en != list(range(i, i + len(en))) or tgt != list(range(j, j + len(tgt))):
            raise AlignmentError("группы идут не подряд или с пропусками")
        if len(en) > MAX_GROUP or len(tgt) > MAX_GROUP:
            raise AlignmentError("слишком большая группа")
        beads.append(Bead(i, i + len(en), j, j + len(tgt), 1.0 if en and tgt else 0.0))
        i += len(en)
        j += len(tgt)
    if i != n or j != m:
        raise AlignmentError("не все предложения попали в группы")
    return beads


class LlmAligner:
    """Интерфейс как у pipeline.align.Aligner: align_pair(src, tgt, lang) → (бусины, метод)."""

    method = "llm"

    def __init__(self, client: Any, anthropic: Any, config: dict[str, Any], cache_dir: Path,
                 gale_church: dict[str, Any], types: list[tuple[int, int]]) -> None:
        self.client = client
        self.anthropic = anthropic
        self.model = str(config.get("model", "claude-opus-5"))
        self.effort = str(config.get("effort", "medium"))
        self.cache_dir = cache_dir
        self.gale_church = gale_church
        self.types = types
        self.warnings: list[str] = []
        self.requests = 0
        self.from_cache = 0
        self.fallbacks = 0
        self.stopped = False

    def _cache_file(self, prompt: str) -> Path:
        payload = json.dumps([PROMPT_VERSION, self.model, self.effort, SYSTEM_PROMPT, prompt],
                             ensure_ascii=False)
        return self.cache_dir / f"{hashlib.sha256(payload.encode()).hexdigest()[:32]}.json"

    def _ask(self, prompt: str) -> dict[str, Any] | None:
        from pipeline.llm import _request

        cache_file = self._cache_file(prompt)
        if cache_file.exists():
            self.from_cache += 1
            return dict(json.loads(cache_file.read_text(encoding="utf-8")))
        if self.stopped or self.client is None:
            return None
        self.requests += 1
        result, error, stop = _request(self.anthropic, self.client, self.model, self.effort,
                                       prompt, SYSTEM_PROMPT, RESPONSE_SCHEMA)
        if error:
            self.warnings.append(f"LLM-выравнивание: {error}")
            self.stopped = self.stopped or stop
            return None
        assert result is not None
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
        return result

    def align_pair(self, src: Sequence[str], tgt: Sequence[str], tgt_lang: str) -> tuple[
        list[Bead], str
    ]:
        if not src or not tgt:
            raise AlignmentError("пустой текст")
        result = self._ask(build_prompt(src, tgt, tgt_lang))
        if result is not None:
            try:
                return parse_groups(result, len(src), len(tgt)), self.method
            except (AlignmentError, TypeError, ValueError) as exc:
                self.warnings.append(f"LLM-выравнивание EN–{tgt_lang.upper()}: ответ отклонён "
                                     f"({exc})")
        self.fallbacks += 1
        variance = float(self.gale_church.get("variance", {}).get(tgt_lang, 6.8))
        beads = gale_church_align(src, tgt, self.types, variance=variance,
                                  priors=self.gale_church.get("priors"))
        return beads, "gale_church"
