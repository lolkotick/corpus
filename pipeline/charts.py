"""Единый стиль графиков для отчётов (reports/*.png): 300 dpi, подписи на русском.

Размер по умолчанию — 16 × 9 см: ширина полосы набора страницы A4 в Word при
полях 2,5–3 см, поэтому картинка вставляется без масштабирования.

Цвета:
- ряды P / R / F1 и другие категории — первые слоты проверенной палитры
  (синий, оранжевый, бирюзовый — различимы при дальтонизме, проверено
  валидатором палитры); значения подписываются прямо на столбцах;
- языки — цвета сайта (EN синий, ZH терракотовый, RU зелёный);
- количественные шкалы (матрица ошибок) — один тон, от светлого к тёмному.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

CM = 1 / 2.54
WIDTH_CM = 16.0
DPI = 300

INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"
SURFACE = "#ffffff"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
LANG_COLORS = {"en": "#1f5fad", "zh": "#b5421f", "ru": "#007a52"}
SEQUENTIAL = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95",
              "#0d366b"]


def setup() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 10.5,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 10,
        "axes.labelsize": 9,
        "axes.labelcolor": INK_SECONDARY,
        "axes.edgecolor": GRID,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK_SECONDARY,
        "ytick.color": INK_SECONDARY,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "legend.fontsize": 8.5,
        "text.color": INK,
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "savefig.dpi": DPI,
    })


def figure(height_cm: float = 9.0, width_cm: float = WIDTH_CM) -> tuple[Figure, plt.Axes]:
    setup()
    fig, ax = plt.subplots(figsize=(width_cm * CM, height_cm * CM))
    return fig, ax


def save(fig: Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.08,
                metadata={"Software": None})
    plt.close(fig)
    return path


PRF_LABELS = ("Точность (P)", "Полнота (R)", "F1-мера")


def plural(n: int, one: str, few: str, many: str) -> str:
    """plural(4, "пара", "пары", "пар") → «пары»."""
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def fmt(value: float | None, digits: int = 2) -> str:
    """Число с десятичной запятой (как принято в русском тексте)."""
    if value is None:
        return "—"
    return f"{value:.{digits}f}".replace(".", ",")


def grouped_bars(
    path: Path,
    categories: Sequence[str],
    series: dict[str, Sequence[float | None]],
    title: str,
    ylabel: str = "",
    ylim: tuple[float, float] | None = (0.0, 1.0),
    colors: Sequence[str] | None = None,
    value_digits: int = 2,
) -> Path:
    """Сгруппированные столбцы с подписями значений; None — «нет данных»."""
    fig, ax = figure()
    names = list(series)
    n = len(names)
    group_width = 0.78
    width = group_width / max(n, 1)
    palette = list(colors or SERIES)
    for k, name in enumerate(names):
        xs = [i - group_width / 2 + width * (k + 0.5) for i in range(len(categories))]
        values = list(series[name])
        heights = [v if v is not None else 0.0 for v in values]
        bars = ax.bar(xs, heights, width=width * 0.9, color=palette[k % len(palette)],
                      label=name, linewidth=0, zorder=2)
        for bar, value in zip(bars, values, strict=True):
            label = fmt(value, value_digits) if value is not None else "н/д"
            ax.annotate(label, (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 2), textcoords="offset points", ha="center", va="bottom",
                        fontsize=7, color=INK_SECONDARY)
    ax.set_xticks(range(len(categories)), categories)
    if ylim:
        ax.set_ylim(ylim[0], ylim[1] * 1.08)
        ax.set_yticks([ylim[0] + (ylim[1] - ylim[0]) * k / 5 for k in range(6)])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(v, 1 if ylim else 0)))
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.set_title(title)
    if n > 1:
        ax.legend(loc="upper left", bbox_to_anchor=(0, 1.0), ncol=n, handlelength=1.0,
                  columnspacing=1.2, borderaxespad=0.0)
        ax.set_ylim(ax.get_ylim()[0], ax.get_ylim()[1] * 1.12)
    return save(fig, path)


def heatmap(
    path: Path,
    matrix: Sequence[Sequence[int]],
    row_labels: Sequence[str],
    col_labels: Sequence[str],
    title: str,
    xlabel: str,
    ylabel: str,
) -> Path:
    """Матрица (например, ошибок по падежам): значения подписаны в ячейках."""
    size = 3.2 + 1.05 * max(len(row_labels), len(col_labels))
    fig, ax = figure(height_cm=min(size, 14), width_cm=min(size + 2, WIDTH_CM))
    cmap = LinearSegmentedColormap.from_list("seq", SEQUENTIAL)
    peak = max((v for row in matrix for v in row), default=0) or 1
    ax.imshow(matrix, cmap=cmap, vmin=0, vmax=peak, aspect="auto")
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            color = SURFACE if value > peak * 0.55 else INK
            ax.text(j, i, str(value) if value else "·", ha="center", va="center",
                    fontsize=8, color=color)
    ax.set_xticks(range(len(col_labels)), col_labels)
    ax.set_yticks(range(len(row_labels)), row_labels)
    ax.set_xticks([x - 0.5 for x in range(1, len(col_labels))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(row_labels))], minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=1.5)
    ax.tick_params(which="minor", length=0)
    ax.xaxis.set_label_position("top")
    ax.xaxis.tick_top()
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, pad=28)
    return save(fig, path)
