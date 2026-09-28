"""Полная сборка корпуса: от data/raw до web/public/data и logs/build_report.md."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pipeline.align import AlignedSegment, align_three, create_aligner
from pipeline.annotate.en import annotate_en
from pipeline.annotate.ru import annotate_ru
from pipeline.annotate.zh import annotate_zh
from pipeline.config import Config
from pipeline.export import write_outputs
from pipeline.llm import LlmStats, review
from pipeline.manual import Overrides, apply_overrides
from pipeline.report import write_report
from pipeline.segment import segment_paragraphs
from pipeline.sources import LANGS, RawText, discover_texts, read_text

log = logging.getLogger(__name__)


@dataclass
class Stage:
    name: str
    seconds: float
    detail: str = ""


@dataclass
class BuildResult:
    stages: list[Stage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    texts: list[dict[str, Any]] = field(default_factory=list)
    text_rows: list[dict[str, Any]] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    alignment_method: str = ""
    annotation_methods: dict[str, str] = field(default_factory=dict)
    manual: dict[str, int] = field(default_factory=dict)
    llm: LlmStats = field(default_factory=LlmStats)
    started_at: str = ""
    total_seconds: float = 0.0


@contextmanager
def _stage(result: BuildResult, name: str) -> Iterator[Stage]:
    stage = Stage(name, 0.0)
    start = time.perf_counter()
    log.info("▶ %s", name)
    try:
        yield stage
    finally:
        stage.seconds = time.perf_counter() - start
        result.stages.append(stage)
        log.info("  %s: %.2f с %s", name, stage.seconds, stage.detail)


def _align_text(aligner: Any, raw: RawText, sentences: dict[str, list[list[str]]],
                use_paragraphs: bool, warnings: list[str]) -> tuple[list[AlignedSegment], str]:
    counts = {lang: len(sentences[lang]) for lang in LANGS}
    if use_paragraphs and len(set(counts.values())) == 1:
        segments: list[AlignedSegment] = []
        for p in range(counts["en"]):
            segments += align_three(aligner, sentences["en"][p], sentences["zh"][p],
                                    sentences["ru"][p])
        return segments, f"по абзацам ({counts['en']})"
    if use_paragraphs:
        warnings.append(
            f"{raw.meta.id}: число абзацев различается (EN {counts['en']}, ZH {counts['zh']}, "
            f"RU {counts['ru']}) — текст выровнен целиком"
        )
    flat = {lang: [s for para in sentences[lang] for s in para] for lang in LANGS}
    return align_three(aligner, flat["en"], flat["zh"], flat["ru"]), "целиком"


def run_build(config: Config, use_llm: bool = True) -> BuildResult:
    result = BuildResult(started_at=datetime.now(UTC).isoformat(timespec="seconds"))
    t0 = time.perf_counter()

    # 1. Чтение
    with _stage(result, "Чтение текстов") as st:
        raw_texts = [read_text(d) for d in discover_texts(config.path("raw"))]
        if not raw_texts:
            raise SystemExit(f"В {config.path('raw')} нет ни одного текста")
        result.texts = [t.meta.to_dict() for t in raw_texts]
        st.detail = f"{len(raw_texts)} текстов"

    # 2. Сегментация
    with _stage(result, "Сегментация") as st:
        seg_config = config.get("segmentation", {}) or {}
        sentences = {
            t.meta.id: {lang: segment_paragraphs(t.paragraphs[lang], lang, seg_config)
                        for lang in LANGS}
            for t in raw_texts
        }
        totals = {lang: sum(len(p) for s in sentences.values() for p in s[lang]) for lang in LANGS}
        st.detail = ", ".join(f"{lang.upper()} {n}" for lang, n in totals.items())

    # 3. Выравнивание
    with _stage(result, "Выравнивание") as st:
        align_config = config.get("alignment", {}) or {}
        aligner = create_aligner(align_config)
        result.warnings += aligner.warnings[:]
        seen_warnings = len(aligner.warnings)
        result.alignment_method = aligner.method
        use_paragraphs = bool(align_config.get("use_paragraphs", True))
        threshold = float(
            (align_config.get("low_score_threshold") or {}).get(aligner.method, 0.35)
        )
        records: list[dict[str, Any]] = []
        for raw in raw_texts:
            segments, mode = _align_text(aligner, raw, sentences[raw.meta.id], use_paragraphs,
                                         result.warnings)
            types: dict[str, int] = {}
            for n, seg in enumerate(segments, start=1):
                types[seg.alignment_type] = types.get(seg.alignment_type, 0) + 1
                records.append({
                    "id": f"{raw.meta.id}-{n:03d}",
                    "text_id": raw.meta.id,
                    "position": n,
                    "en": seg.text("en"),
                    "zh": seg.text("zh"),
                    "ru": seg.text("ru"),
                    "alignment_type": seg.alignment_type,
                    "alignment_score": seg.score,
                    "alignment": {"method": seg.method, "en_zh": seg.en_zh, "en_ru": seg.en_ru,
                                  "low": seg.score < threshold},
                    "annotations": {"en": [], "zh": [], "ru": []},
                    "status": "auto",
                    "llm_note": None,
                    "comment": "",
                })
            sents = sentences[raw.meta.id]
            result.text_rows.append({
                "id": raw.meta.id,
                "title": raw.meta.title,
                "level": raw.meta.level,
                "sentences": {lang: sum(len(p) for p in sents[lang]) for lang in LANGS},
                "pairs": len(segments),
                "mode": mode,
                "types": types,
                "mean_score": round(sum(s.score for s in segments) / len(segments), 3),
                "low": sum(1 for s in segments if s.score < threshold),
            })
        result.warnings += aligner.warnings[seen_warnings:]
        st.detail = f"{len(records)} пар, метод {aligner.method}"

    # 4. Ручные правки (до разметки: исправленный текст размечается заново)
    with _stage(result, "Ручные правки") as st:
        overrides = Overrides.load(config.path("manual") / "overrides.json")
        records, manual_stats, manual_warnings = apply_overrides(records, overrides)
        result.manual = manual_stats
        result.warnings += manual_warnings
        st.detail = (f"применено {manual_stats['applied']}, удалено {manual_stats['deleted']}, "
                     f"пропущено {manual_stats['skipped']}")

    # 5. Разметка
    with _stage(result, "Разметка EN (артикли)") as st:
        en_anns, en_method, en_warnings = annotate_en(
            [r["en"] for r in records], config.get("annotation.en.spacy_model", "en_core_web_sm")
        )
        result.warnings += en_warnings
        result.annotation_methods["en"] = en_method
        for r, anns in zip(records, en_anns, strict=True):
            r["annotations"]["en"] = anns
        st.detail = f"{sum(len(a) for a in en_anns)} артиклей ({en_method})"

    with _stage(result, "Разметка ZH (量词)") as st:
        zh_config = config.get("annotation.zh", {}) or {}
        zh_anns, classifiers = annotate_zh(
            [r["zh"] for r in records],
            config.resolve(zh_config.get("classifiers_file",
                                         "pipeline/resources/zh_classifiers.tsv")),
            demonstratives=zh_config.get("demonstratives", ["这", "那", "哪", "每", "某"]),
            exclude_words=zh_config.get("exclude_words", []),
            max_modifiers=int(zh_config.get("max_modifiers", 4)),
        )
        result.annotation_methods["zh"] = f"jieba + список 量词 ({len(classifiers)})"
        for r, anns in zip(records, zh_anns, strict=True):
            r["annotations"]["zh"] = anns
        st.detail = f"{sum(len(a) for a in zh_anns)} конструкций"

    with _stage(result, "Разметка RU (падежи)") as st:
        ru_anns = annotate_ru([r["ru"] for r in records],
                              float(config.get("annotation.ru.ambiguity_threshold", 0.8)))
        result.annotation_methods["ru"] = "pymorphy3 + контекст (предлоги, согласование)"
        for r, anns in zip(records, ru_anns, strict=True):
            r["annotations"]["ru"] = anns
        st.detail = f"{sum(len(a) for a in ru_anns)} существительных"

    # 6. LLM-проверка (необязательно)
    with _stage(result, "LLM-проверка") as st:
        result.llm = review(
            records,
            {t["id"]: t for t in result.texts},
            config.get("llm", {}) or {},
            threshold,
            config.path("llm_cache"),
            config.root,
            enabled=use_llm,
        )
        result.warnings += result.llm.warnings
        st.detail = (f"проверено {result.llm.checked}, предложено правок "
                     f"{result.llm.suggestions}" + (f" — {result.llm.reason}"
                                                    if result.llm.reason else ""))

    # 7. Экспорт
    with _stage(result, "Экспорт JSON/CSV/статистики") as st:
        build_info = {
            "generated_at": result.started_at,
            "alignment_method": result.alignment_method,
            "low_score_threshold": threshold,
            "annotation_methods": result.annotation_methods,
        }
        result.stats = write_outputs(
            config.path("output"),
            records,
            result.texts,
            [c.to_dict() for c in classifiers.values()],
            build_info,
            delimiter=str(config.get("export.csv_delimiter", ",")),
            bins=int(config.get("export.histogram_bins", 10)),
        )
        st.detail = str(config.path("output").relative_to(config.root))

    result.records = records
    result.total_seconds = time.perf_counter() - t0
    write_report(config.path("logs") / "build_report.md", result, config)
    return result
