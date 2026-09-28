"""Отчёты reports/*.md → Word (reports/docx/*.docx) для вставки в курсовую.

Конвертер рассчитан на Markdown, который пишут скрипты pipeline: заголовки,
абзацы, списки, цитаты, таблицы, блоки кода, **жирный**, *курсив*, `код`.
Оформление близко к требованиям к курсовым работам (ГОСТ 7.32): A4, поля
30/15/20/20 мм, Times New Roman 14 пт, полуторный интервал; таблицы — 11 пт с
подписью «Таблица N — …» над таблицей; графики из раздела «Файлы» вставляются
в конец документа в натуральную величину (300 dpi, до 16 см — ширины полосы) с
подписью «Рисунок N — …» под рисунком.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph

FONT = "Times New Roman"
MONO = "Courier New"
IMAGE_WIDTH_CM = 16.0

# Подписи рисунков по имени файла (иначе — имя файла).
CAPTIONS = {
    "evaluation_prf.png": "Точность, полнота и F1 автоматической разметки по эталону",
    "evaluation_case_confusion.png": "Матрица ошибок разметки падежей",
    "aligners_f1.png": "F1 методов выравнивания по эталону",
    "aligners_time.png": "Время работы методов выравнивания",
    "errors_types.png": "Типы ошибок автоматической разметки",
    "approbation_scores.png": "Доля верных ответов в предтесте и посттесте по явлениям",
    "approbation_participants.png": "Результаты участников в предтесте и посттесте",
    "corpus_texts.png": "Число пар по текстам корпуса",
    "corpus_cases.png": "Распределение падежей существительных (RU)",
    "corpus_classifiers.png": "Самые частые счётные слова (ZH)",
    "corpus_articles.png": "Артикли в английских текстах",
    "corpus_alignment.png": "Распределение оценки выравнивания alignment_score",
}

_INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)")
_TABLE_SEP = re.compile(r"^\|(\s*:?-{3,}:?\s*\|)+\s*$")
_PNG = re.compile(r"`([^`]+\.png)`")


def _set_font(run_or_style: Any, name: str, size: float | None = None) -> None:
    """Шрифт для всех алфавитов (иначе Word подставит свой для кириллицы и иероглифов)."""
    font = run_or_style.font
    font.name = name
    if size is not None:
        font.size = Pt(size)
    element = run_or_style.element
    rpr = element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)


def _setup(document: DocxDocument) -> None:
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin, section.right_margin = Cm(3), Cm(1.5)
    section.top_margin, section.bottom_margin = Cm(2), Cm(2)
    normal = document.styles["Normal"]
    _set_font(normal, FONT, 14)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(0)
    for level, size in ((1, 16), (2, 14), (3, 14)):
        style = document.styles[f"Heading {level}"]
        _set_font(style, FONT, size)
        style.font.bold = True
        style.font.italic = False
        style.font.color.rgb = None
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True


def add_inline(paragraph: Paragraph, text: str, size: float | None = None) -> None:
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            _set_font(run, MONO, (size or 14) - 2)
            continue
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            run.italic = True
        else:
            run = paragraph.add_run(part.replace("\\|", "|"))
        if size is not None:
            run.font.size = Pt(size)


def _split_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [c.strip() for c in cells]


def _caption(document: DocxDocument, text: str, *, before: bool) -> None:
    p = document.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = before
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT if before else WD_ALIGN_PARAGRAPH.CENTER
    add_inline(p, text, 12)


def _table(document: DocxDocument, rows: list[list[str]], aligns: Sequence[str],
           caption: str, number: int) -> None:
    _caption(document, f"Таблица {number} — {caption}", before=True)
    width = max(len(r) for r in rows)
    table = document.add_table(rows=len(rows), cols=width)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j in range(width):
            cell = table.cell(i, j)
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.first_line_indent = Cm(0)
            if j < len(aligns) and aligns[j] == "right" and i > 0:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            text = row[j] if j < len(row) else ""
            if i == 0:
                run = p.add_run(text)
                run.bold = True
                run.font.size = Pt(11)
            else:
                add_inline(p, text, 11)
    document.add_paragraph()


def _image_width(image: Path) -> Cm:
    """Натуральная ширина PNG при 300 dpi (не больше полосы набора) — без масштабирования."""
    from PIL import Image

    with Image.open(image) as im:
        dpi = im.info.get("dpi", (300, 300))[0] or 300
        width_cm = im.width / float(dpi) * 2.54
    return Cm(min(width_cm, IMAGE_WIDTH_CM))


def convert(md_path: Path, docx_path: Path, figures: Sequence[Path] = ()) -> Path:
    """Преобразовать отчёт; figures — PNG для раздела «Рисунки» (по умолчанию из «Файлы»)."""
    document = Document()
    _setup(document)
    lines = md_path.read_text(encoding="utf-8").splitlines()
    heading = ""
    table_no = 0
    i = 0
    found_figures: list[Path] = []
    in_files = False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                p = document.add_paragraph()
                p.paragraph_format.line_spacing = 1.0
                _set_font(p.add_run(lines[i]), MONO, 11)
                i += 1
            i += 1
            continue
        match = re.match(r"^(#{1,3})\s+(.*)", stripped)
        if match:
            level = len(match.group(1))
            heading = match.group(2)
            in_files = heading.strip() == "Файлы"
            if not in_files:
                p = document.add_heading(level=level)
                add_inline(p, heading)
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(
                lines[i + 1].strip()):
            aligns = ["right" if c.strip().endswith(":") else "left"
                      for c in lines[i + 1].strip().strip("|").split("|")]
            rows = [_split_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            table_no += 1
            _table(document, rows, aligns, heading or md_path.stem, table_no)
            continue
        if in_files:
            png = _PNG.search(stripped)
            if png:
                found_figures.append(md_path.parent / Path(png.group(1)).name)
            i += 1
            continue
        if stripped.startswith(">"):
            p = document.add_paragraph()
            p.paragraph_format.left_indent = Cm(1)
            add_inline(p, stripped.lstrip("> ").strip())
            for run in p.runs:
                run.italic = True
            i += 1
            continue
        bullet = re.match(r"^(\s*)[-*]\s+(.*)", line)
        if bullet:
            depth = len(bullet.group(1)) // 2
            p = document.add_paragraph(style="List Bullet 2" if depth else "List Bullet")
            add_inline(p, bullet.group(2))
            i += 1
            continue
        numbered = re.match(r"^\s*\d+\.\s+(.*)", line)
        if numbered:
            p = document.add_paragraph(style="List Number")
            add_inline(p, numbered.group(1))
            i += 1
            continue
        paragraph = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#|\||>|\s*[-*]\s|\s*\d+\.\s|```)", lines[i]):
            paragraph.append(lines[i].strip())
            i += 1
        p = document.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(1.25)
        add_inline(p, " ".join(paragraph))

    images = [f for f in (figures or found_figures) if f.exists()]
    if images:
        document.add_heading("Рисунки", level=2)
        for n, image in enumerate(images, start=1):
            p = document.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(str(image), width=_image_width(image))
            _caption(document, f"Рисунок {n} — {CAPTIONS.get(image.name, image.stem)}",
                     before=False)
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    document.core_properties.author = "pipeline корпуса EN/ZH/RU"
    document.save(str(docx_path))
    return docx_path
