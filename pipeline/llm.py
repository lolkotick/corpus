"""Необязательная LLM-проверка (Claude) сомнительных пар и спорной разметки.

Модуль включается, только если задан ANTHROPIC_API_KEY (в .env или окружении).
Модель проверяет пары с низким alignment_score и спорную разметку и
записывает в поле llm_note вердикт, предложение исправления и комментарий.
Сами данные LLM не меняет: решение о правке принимает человек (через CSV).
Ответы кэшируются в data/cache/llm/, поэтому повторная сборка не тратит запросы.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.annotate.ru import CASE_LABELS

log = logging.getLogger(__name__)

PROMPT_VERSION = 1
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """Ты — эксперт-лингвист, который проверяет учебный параллельный корпус \
английский–китайский–русский. Корпус нужен студентам для отработки трёх явлений: \
артиклей a/an/the (EN), счётных слов 量词 (ZH) и падежей существительных (RU).

Тебе дают одну тройку предложений (с соседними парами для контекста), данные \
автоматического выравнивания и список разметки, которую алгоритм счёл спорной.

1. Выравнивание: реши, передают ли EN, ZH и RU одно и то же содержание целиком. \
Если какое-то предложение явно относится к соседней паре или часть текста пропущена, \
alignment_ok = false и в alignment_comment кратко объясни, как исправить.
2. Разметка: для каждого элемента из списка реши, верна ли она. Если нет, в suggestion \
дай исправление коротко и однозначно, например «падеж: винительный», \
«существительное: 地图», «вершина: book». Если верна — suggestion пустой.
3. summary — одно-два предложения итога для преподавателя.

Пиши по-русски, кратко и по делу. Не придумывай ошибок: если всё верно, так и скажи."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "alignment_ok": {"type": "boolean"},
        "alignment_comment": {"type": "string"},
        "annotations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "ok": {"type": "boolean"},
                    "suggestion": {"type": "string"},
                    "comment": {"type": "string"},
                },
                "required": ["id", "ok", "suggestion", "comment"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["alignment_ok", "alignment_comment", "annotations", "summary"],
    "additionalProperties": False,
}


@dataclass
class LlmStats:
    enabled: bool = False
    reason: str = ""
    model: str = ""
    candidates: int = 0
    checked: int = 0
    from_cache: int = 0
    suggestions: int = 0
    alignment_flags: int = 0
    annotation_flags: int = 0
    errors: int = 0
    warnings: list[str] = field(default_factory=list)


def api_key_available(root: Path) -> bool:
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env", override=False)
    except ImportError:  # pragma: no cover
        pass
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def describe_annotation(lang: str, ann: dict[str, Any]) -> str:
    if lang == "ru":
        alts = ", ".join(CASE_LABELS.get(a, a) for a in ann.get("alternatives", []))
        return (
            f"{ann['id']}: «{ann['text']}» → лемма «{ann['lemma']}», "
            f"{CASE_LABELS.get(ann['case'], ann['case'])} падеж, "
            f"{'ед.' if ann['number'] == 'sing' else 'мн.'} ч.; уверенность {ann['confidence']}"
            + (f"; другие варианты: {alts}" if alts else "")
        )
    if lang == "zh":
        head = ann["head"]["text"] if ann.get("head") else "не найдено"
        return (
            f"{ann['id']}: «{ann['det']['text']}{ann['text']}» (量词 {ann['text']}, "
            f"{ann.get('pinyin', '')}) → существительное: {head}"
        )
    head = ann["head"]["text"] if ann.get("head") else "не найдена"
    return f"{ann['id']}: артикль «{ann['text']}» → вершина: {head}" + (
        f" ({ann['note']})" if ann.get("note") else ""
    )


def select_candidates(
    records: list[dict[str, Any]], low_threshold: float, config: dict[str, Any]
) -> list[tuple[int, list[str], list[tuple[str, dict[str, Any]]]]]:
    """Пары для проверки: (индекс, причины, спорные элементы разметки)."""
    selected = []
    for idx, record in enumerate(records):
        reasons: list[str] = []
        disputed: list[tuple[str, dict[str, Any]]] = []
        if config.get("check_low_scores", True) and record["alignment_score"] < low_threshold:
            reasons.append("низкий alignment_score")
        if config.get("check_disputed", True):
            for lang in ("en", "zh", "ru"):
                disputed += [(lang, a) for a in record["annotations"][lang] if a.get("disputed")]
            if disputed:
                reasons.append("спорная разметка")
        if reasons and record.get("status") == "auto":
            selected.append((idx, reasons, disputed))
    # Сначала самые сомнительные: низкий score, затем больше спорных элементов.
    selected.sort(key=lambda item: (records[item[0]]["alignment_score"], -len(item[2])))
    return selected


def build_prompt(
    records: list[dict[str, Any]], idx: int, reasons: list[str],
    disputed: list[tuple[str, dict[str, Any]]], text_title: str,
) -> str:
    record = records[idx]
    lines = [
        f"Пара {record['id']} из текста «{text_title}». Причины проверки: {', '.join(reasons)}.",
        f"Выравнивание: тип {record['alignment_type']} (число предложений EN-ZH-RU), "
        f"метод {record['alignment']['method']}, alignment_score={record['alignment_score']} "
        f"(EN–ZH {record['alignment']['en_zh']}, EN–RU {record['alignment']['en_ru']}).",
        "",
    ]
    for label, offset in (("Предыдущая пара", -1), ("Следующая пара", 1)):
        j = idx + offset
        if 0 <= j < len(records) and records[j]["text_id"] == record["text_id"]:
            neighbor = records[j]
            lines += [f"{label} (контекст):", f"  EN: {neighbor['en']}",
                      f"  ZH: {neighbor['zh']}", f"  RU: {neighbor['ru']}", ""]
    lines += ["Проверяемая пара:", f"  EN: {record['en']}", f"  ZH: {record['zh']}",
              f"  RU: {record['ru']}", ""]
    if disputed:
        lines.append("Спорная разметка:")
        lines += [f"- [{lang.upper()}] {describe_annotation(lang, ann)}" for lang, ann in disputed]
    else:
        lines.append("Спорной разметки нет — проверь только выравнивание (annotations = []).")
    return "\n".join(lines)


def _cache_key(model: str, effort: str, prompt: str) -> str:
    payload = json.dumps([PROMPT_VERSION, model, effort, SYSTEM_PROMPT, prompt], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _call_claude(client: Any, model: str, effort: str, prompt: str) -> dict[str, Any]:
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        thinking={"type": "adaptive"},
        output_config={
            "effort": effort,
            "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
        },
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("модель отказалась отвечать (refusal)")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("ответ обрезан по max_tokens")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise RuntimeError("в ответе нет текстового блока")
    data = json.loads(text)
    data["_model"] = response.model
    return data


def _request(
    anthropic: Any, client: Any, model: str, effort: str, prompt: str
) -> tuple[dict[str, Any] | None, str, bool]:
    """Запрос к API: (результат, текст ошибки, нужно ли остановить проверку)."""
    try:
        return _call_claude(client, model, effort, prompt), "", False
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        return None, f"ключ API не принят: {exc.__class__.__name__}", True
    except anthropic.NotFoundError:
        return None, f"модель {model} не найдена — проверьте llm.model в config.yaml", True
    except anthropic.RateLimitError:
        return None, "превышен лимит запросов", True
    except anthropic.APIStatusError as exc:
        return None, f"ошибка API {exc.status_code}", exc.status_code < 500
    except anthropic.APIConnectionError:
        return None, "нет соединения с API", False
    except (RuntimeError, json.JSONDecodeError) as exc:
        return None, str(exc), False


def review(
    records: list[dict[str, Any]],
    texts_meta: dict[str, dict[str, Any]],
    config: dict[str, Any],
    low_threshold: float,
    cache_dir: Path,
    root: Path,
    enabled: bool = True,
) -> LlmStats:
    """Проверить кандидатов. Без ключа применяются только сохранённые ответы из кэша."""
    stats = LlmStats(model=str(config.get("model", "claude-opus-5")))
    candidates = select_candidates(records, low_threshold, config)
    stats.candidates = len(candidates)
    limit = int(config.get("max_items", 40))
    effort = str(config.get("effort", "medium"))

    client: Any = None
    anthropic: Any = None
    if not enabled:
        stats.reason = "запросы к API отключены (--no-llm); применены сохранённые ответы"
    elif not api_key_available(root):
        stats.reason = "нет ANTHROPIC_API_KEY — применены только сохранённые ответы"
    else:
        try:
            import anthropic
        except ImportError:
            stats.reason = "пакет anthropic не установлен — применены сохранённые ответы"
        else:
            client = anthropic.Anthropic(timeout=float(config.get("timeout_seconds", 120)))
            stats.enabled = True
    consecutive_errors = 0

    for idx, reasons, disputed in candidates[:limit]:
        record = records[idx]
        title = texts_meta.get(record["text_id"], {}).get("title", record["text_id"])
        prompt = build_prompt(records, idx, reasons, disputed, title)
        cache_file = cache_dir / f"{_cache_key(stats.model, effort, prompt)}.json"

        result: dict[str, Any] | None = None
        if cache_file.exists():
            try:
                result = json.loads(cache_file.read_text(encoding="utf-8"))
                stats.from_cache += 1
            except (OSError, json.JSONDecodeError) as exc:
                stats.warnings.append(f"LLM: повреждён сохранённый ответ {cache_file.name} ({exc})")
        if result is None:
            if client is None:
                continue
            result, error, stop = _request(anthropic, client, stats.model, effort, prompt)
            if error:
                stats.errors += 1
                stats.warnings.append(f"LLM: пара {record['id']} не проверена ({error})")
                consecutive_errors += 1
                if stop or consecutive_errors >= 3:
                    stats.warnings.append("LLM: проверка остановлена")
                    break
                continue
            assert result is not None
            consecutive_errors = 0
            result["_checked_at"] = datetime.now(UTC).date().isoformat()
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")

        known_ids = {ann["id"] for _lang, ann in disputed}
        reviews = [r for r in result.get("annotations", []) if r.get("id") in known_ids]
        flagged = [r for r in reviews if not r.get("ok")]
        alignment_flag = not result.get("alignment_ok", True)
        record["llm_note"] = {
            "model": result.get("_model", stats.model),
            "reasons": reasons,
            "alignment_ok": bool(result.get("alignment_ok", True)),
            "alignment_comment": result.get("alignment_comment", ""),
            "annotations": reviews,
            "summary": result.get("summary", ""),
            "suggestions": len(flagged) + (1 if alignment_flag else 0),
            "checked_at": result.get("_checked_at", ""),
        }
        stats.checked += 1
        stats.annotation_flags += len(flagged)
        stats.alignment_flags += int(alignment_flag)
        stats.suggestions += record["llm_note"]["suggestions"]

    if client is None and not stats.reason:
        stats.reason = "модуль пропущен"
    if len(candidates) > limit and client is not None:
        stats.warnings.append(
            f"LLM: проверено {min(limit, len(candidates))} из {len(candidates)} кандидатов "
            f"(ограничение llm.max_items = {limit})"
        )
    return stats
