"""Апробация упражнений: анализ результатов режима «Тест» (предтест / посттест).

    python -m pipeline approbation [ФАЙЛЫ_ИЛИ_ПАПКИ ...] [--out reports]

По умолчанию читает все CSV из data/approbation/ (экспорт кнопкой «Экспорт
результатов (CSV)» на странице теста). Считает:

- средний балл по этапам (предтест — набор A, посттест — набор B);
- прирост от предтеста к посттесту у участников, прошедших оба этапа:
  разность в процентных пунктах, нормализованный прирост Хейка
  g = (post − pre) / (100 − pre), парный t-критерий, критерий Уилкоксона,
  размер эффекта d_z;
- точность и прирост по явлениям (артикли, 量词, падежи);
- типичные ошибки по явлениям (для падежей — в какой падеж поставлено слово,
  по разборам pymorphy3);
- сопоставимость наборов (средний уровень и состав заданий).

Выход: reports/approbation.md, CSV-таблицы и графики PNG. Без данных —
понятное сообщение без чисел. Файлы, начинающиеся со строки «#», считаются
помеченными: «# СИНТЕТИЧЕСКИЕ ДАННЫЕ» выводит предупреждение в отчёте.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pipeline import charts
from pipeline.tables import md_table, write_csv

REQUIRED = {"participant", "stage", "attempt_id", "set_id", "finished_at", "item_id",
            "phenomenon", "level", "subtype", "correct_answer", "answer", "correct", "time_ms"}
KINDS = ("article", "classifier", "case")
KIND_LABEL = {"article": "Артикли", "classifier": "Счётные слова", "case": "Падежи"}
KIND_TITLE = {"article": "Артикли (EN)", "classifier": "Счётные слова 量词 (ZH)",
              "case": "Падежи (RU)"}
STAGE_LABEL = {"pre": "Предтест", "post": "Посттест"}
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
CASE_SHORT = {"nomn": "им.", "gent": "род.", "datv": "дат.", "accs": "вин.", "ablt": "твор.",
              "loct": "предл.", "voct": "зв."}


class NoData(Exception):
    pass


@dataclass
class PhenStat:
    kind: str
    n_pre: int
    acc_pre: float | None
    n_post: int
    acc_post: float | None
    gain: float | None  # средний прирост по участникам с обоими этапами, п. п.


@dataclass
class Answer:
    item_id: str
    kind: str
    level: str
    subtype: str
    correct_answer: str
    answer: str
    correct: bool
    ms: int


@dataclass
class Attempt:
    id: str
    participant: str
    stage: str
    set_id: str
    started_at: str
    finished: bool
    source: str
    answers: list[Answer] = field(default_factory=list)

    @property
    def score(self) -> float:
        return 100 * sum(a.correct for a in self.answers) / len(self.answers)

    def kind_score(self, kind: str) -> float | None:
        items = [a for a in self.answers if a.kind == kind]
        return 100 * sum(a.correct for a in items) / len(items) if items else None


# ─── Чтение ───────────────────────────────────────────────────────────────


def collect_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files += sorted(p for p in path.glob("*.csv") if p.is_file())
        elif path.exists():
            files.append(path)
    return files


def read_csv(path: Path) -> tuple[list[dict[str, str]], bool]:
    """Строки файла и признак «синтетические данные» (строка-комментарий в начале)."""
    text = path.read_bytes().decode("utf-8-sig")
    lines = text.splitlines()
    comments = [line for line in lines if line.startswith("#")]
    synthetic = any("синтетич" in c.lower() or "synthetic" in c.lower() for c in comments)
    body = "\n".join(line for line in lines if not line.startswith("#"))
    if not body.strip():
        return [], synthetic
    try:
        delimiter = csv.Sniffer().sniff(body[:2048], delimiters=";,\t").delimiter
    except csv.Error:
        delimiter = ";"
    rows = list(csv.DictReader(io.StringIO(body), delimiter=delimiter))
    if rows and not set(rows[0]) >= REQUIRED:
        missing = ", ".join(sorted(REQUIRED - set(rows[0])))
        raise ValueError(f"{path.name}: нет столбцов {missing} — это не экспорт режима «Тест»")
    return rows, synthetic


@dataclass
class Dataset:
    files: list[Path]
    synthetic: bool
    attempts: list[Attempt]  # использованные: завершённые, первая попытка участника на этап
    dropped_unfinished: int
    dropped_repeat: list[str]
    problems: list[str]


def load(paths: Iterable[Path]) -> Dataset:
    files = collect_files(paths)
    if not files:
        raise NoData("нет CSV-файлов с результатами теста")
    by_id: dict[str, Attempt] = {}
    synthetic = False
    problems: list[str] = []
    for path in files:
        try:
            rows, marked = read_csv(path)
        except (ValueError, UnicodeDecodeError) as exc:
            problems.append(str(exc))
            continue
        synthetic = synthetic or marked
        for row in rows:
            attempt = by_id.setdefault(row["attempt_id"], Attempt(
                row["attempt_id"], row["participant"].strip(), row["stage"].strip(),
                row["set_id"], row.get("started_at", ""), bool(row["finished_at"].strip()),
                path.name,
            ))
            if any(a.item_id == row["item_id"] for a in attempt.answers):
                continue  # тот же файл выгружен дважды
            attempt.answers.append(Answer(
                row["item_id"], row["phenomenon"], row["level"], row["subtype"],
                row["correct_answer"], row["answer"], row["correct"].strip() in ("1", "true"),
                int(float(row["time_ms"] or 0)),
            ))
    unfinished = [a for a in by_id.values() if not a.finished or not a.answers]
    finished = sorted((a for a in by_id.values() if a.finished and a.answers),
                      key=lambda a: a.started_at)
    used: dict[tuple[str, str], Attempt] = {}
    repeats: list[str] = []
    for attempt in finished:
        key = (attempt.participant, attempt.stage)
        if key in used:
            stage = STAGE_LABEL.get(attempt.stage, attempt.stage)
            repeats.append(f"{attempt.participant} ({stage})")
            continue
        used[key] = attempt
    if not used:
        raise NoData("в файлах нет ни одной завершённой попытки теста"
                     + (f" ({'; '.join(problems)})" if problems else ""))
    return Dataset(files, synthetic, list(used.values()), len(unfinished), repeats, problems)


# ─── Статистика ───────────────────────────────────────────────────────────


def _betacf(a: float, b: float, x: float) -> float:
    """Непрерывная дробь для неполной бета-функции (Numerical Recipes, 6.4)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(1 + aa / c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(1 + aa / c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1) < 3e-14:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def t_test_p(t: float, df: int) -> float:
    """Двусторонний p для t-распределения Стьюдента."""
    if df <= 0:
        return float("nan")
    return _betainc(df / 2, 0.5, df / (df + t * t))


@dataclass
class PairedTest:
    n: int
    mean_diff: float
    sd_diff: float | None
    t: float | None
    p_t: float | None
    dz: float | None
    w_plus: float | None
    p_w: float | None
    wilcoxon_exact: bool


def paired_test(pre: Sequence[float], post: Sequence[float]) -> PairedTest:
    diffs = [b - a for a, b in zip(pre, post, strict=True)]
    n = len(diffs)
    mean = statistics.fmean(diffs) if diffs else 0.0
    sd = statistics.stdev(diffs) if n >= 2 else None
    t = p_t = dz = None
    if sd is not None and sd > 0:
        t = mean / (sd / math.sqrt(n))
        p_t = t_test_p(t, n - 1)
        dz = mean / sd
    elif sd == 0 and n >= 2:
        dz = None
    w_plus, p_w, exact = wilcoxon(diffs)
    return PairedTest(n, mean, sd, t, p_t, dz, w_plus, p_w, exact)


def wilcoxon(diffs: Sequence[float]) -> tuple[float | None, float | None, bool]:
    """Критерий знаковых рангов Уилкоксона (двусторонний).

    Нулевые разности отбрасываются, одинаковые по модулю — получают средний ранг.
    При n ≤ 60 p-значение точное: распределение W+ строится перебором всех
    сочетаний знаков через динамическое программирование (удвоенные ранги —
    целые числа, поэтому связи учитываются точно). Иначе — нормальное приближение.
    """
    nonzero = [round(d, 9) for d in diffs if abs(d) > 1e-9]
    n = len(nonzero)
    if n == 0:
        return None, None, True
    order = sorted(range(n), key=lambda i: abs(nonzero[i]))
    ranks2 = [0] * n  # удвоенные ранги
    i = 0
    ties: list[int] = []
    while i < n:
        j = i
        while j + 1 < n and abs(nonzero[order[j + 1]]) == abs(nonzero[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks2[order[k]] = i + j + 2  # 2 × средний ранг
        if j > i:
            ties.append(j - i + 1)
        i = j + 1
    w2 = sum(r for r, d in zip(ranks2, nonzero, strict=True) if d > 0)
    total2 = sum(ranks2)
    if n <= 60:
        counts = [0] * (total2 + 1)
        counts[0] = 1
        for r in ranks2:
            for s_ in range(total2, r - 1, -1):
                counts[s_] += counts[s_ - r]
        deviation = abs(2 * w2 - total2)
        extreme = sum(c for s_, c in enumerate(counts) if abs(2 * s_ - total2) >= deviation)
        return w2 / 2, min(1.0, extreme / 2**n), True
    mean = total2 / 4
    var = n * (n + 1) * (2 * n + 1) / 24 - sum(t**3 - t for t in ties) / 48
    if var <= 0:
        return w2 / 2, None, False
    z = (abs(w2 / 2 - mean) - 0.5) / math.sqrt(var)
    return w2 / 2, min(1.0, math.erfc(max(z, 0) / math.sqrt(2))), False


def hake_gain(pre: float, post: float) -> float | None:
    return (post - pre) / (100 - pre) if pre < 100 else None


# ─── Типичные ошибки ─────────────────────────────────────────────────────


def case_of_answer(answer: str, correct: str) -> str | None:
    """Падеж неверной формы того же слова (по pymorphy3) или None."""
    from pipeline.annotate.ru import _norm_case, get_morph

    morph = get_morph()
    lemmas = {p.normal_form for p in morph.parse(correct.lower())}
    cases = sorted({_norm_case(p.tag.case) or "" for p in morph.parse(answer.lower())
                    if p.normal_form in lemmas and p.tag.case})
    cases = [c for c in cases if c]
    if not cases:
        return None
    return "/".join(CASE_SHORT.get(c, c) for c in cases)


def error_label(answer: Answer) -> str:
    given = answer.answer or "(пусто)"
    if answer.kind == "article":
        return f"{answer.correct_answer.lower()} → {given.lower()}"
    if answer.kind == "classifier":
        return f"{answer.correct_answer} → {given}"
    target = CASE_SHORT.get(answer.subtype, answer.subtype)
    found = case_of_answer(given, answer.correct_answer)
    if found:
        return f"нужен {target}, дан {found}"
    return f"нужен {target}, форма не того слова или с опечаткой"


# ─── Отчёт ────────────────────────────────────────────────────────────────


def _pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{charts.fmt(value, digits)} %"


def _num(value: float | None, digits: int = 2) -> str:
    return charts.fmt(value, digits)


def _p(value: float | None) -> str:
    if value is None or math.isnan(value):
        return "—"
    return "< 0,001" if value < 0.001 else charts.fmt(value, 3)


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def analyse(ds: Dataset, out: Path, root: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    by_stage: dict[str, list[Attempt]] = defaultdict(list)
    for a in ds.attempts:
        by_stage[a.stage].append(a)
    pre = {a.participant: a for a in by_stage["pre"]}
    post = {a.participant: a for a in by_stage["post"]}
    paired = sorted(set(pre) & set(post))

    # Участники
    part_rows = []
    for name in sorted(set(pre) | set(post)):
        a, b = pre.get(name), post.get(name)
        part_rows.append([name, a.score if a else None, b.score if b else None,
                          (b.score - a.score) if a and b else None,
                          hake_gain(a.score, b.score) if a and b else None])
    files.append(write_csv(out / "approbation_participants.csv",
                           ["участник", "предтест, %", "посттест, %", "прирост, п. п.",
                            "нормализованный прирост g"], part_rows, digits=2))

    # Явления
    phen: list[PhenStat] = []
    for kind in KINDS:
        acc: dict[str, tuple[int, float | None]] = {}
        for stage in ("pre", "post"):
            answers = [x for a in by_stage[stage] for x in a.answers if x.kind == kind]
            acc[stage] = (len(answers), 100 * sum(x.correct for x in answers) / len(answers)
                          if answers else None)
        gains = []
        for name in paired:
            before, after = pre[name].kind_score(kind), post[name].kind_score(kind)
            if before is not None and after is not None:
                gains.append(after - before)
        phen.append(PhenStat(kind, acc["pre"][0], acc["pre"][1], acc["post"][0], acc["post"][1],
                             statistics.fmean(gains) if gains else None))
    files.append(write_csv(out / "approbation_phenomena.csv",
                           ["явление", "ответов (пред)", "верно (пред), %", "ответов (пост)",
                            "верно (пост), %", "средний прирост, п. п."],
                           [[KIND_TITLE[p.kind], p.n_pre, p.acc_pre, p.n_post, p.acc_post, p.gain]
                            for p in phen], digits=2))

    # Ошибки
    error_counts: dict[str, Counter[str]] = {k: Counter() for k in KINDS}
    error_stage: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for a in ds.attempts:
        for x in a.answers:
            if not x.correct:
                label = error_label(x)
                error_counts[x.kind][label] += 1
                error_stage[(x.kind, label)][a.stage] += 1
    files.append(write_csv(
        out / "approbation_errors.csv",
        ["явление", "ошибка", "всего", "в предтесте", "в посттесте"],
        [[KIND_LABEL[k], label, n, error_stage[(k, label)]["pre"],
          error_stage[(k, label)]["post"]]
         for k in KINDS for label, n in error_counts[k].most_common()],
    ))

    # Графики
    categories = [KIND_LABEL[k] for k in KINDS] + ["Всего"]
    series: dict[str, list[float | None]] = {}
    colors: list[str] = []
    for stage, color in (("pre", charts.SERIES[1]), ("post", charts.SERIES[0])):
        if not by_stage[stage]:
            continue
        values = [p.acc_pre if stage == "pre" else p.acc_post for p in phen]
        values.append(statistics.fmean(a.score for a in by_stage[stage]))
        series[f"{STAGE_LABEL[stage]} (n = {len(by_stage[stage])})"] = values
        colors.append(color)
    files.append(charts.grouped_bars(
        out / "approbation_scores.png", categories, series,
        title="Доля верных ответов по явлениям, %", ylim=(0, 100), value_digits=0,
        tick_digits=0, colors=colors,
    ))
    if paired:
        files.append(charts.slope(
            out / "approbation_participants.png",
            [pre[p].score for p in paired], [post[p].score for p in paired],
            left="Предтест", right="Посттест",
            title=f"Результат каждого участника, % (n = {len(paired)})",
        ))

    lines = render(ds, by_stage, pre, post, paired, phen, error_counts, error_stage, files, root)
    path = out / "approbation.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return [path, *files]


def render(ds: Dataset, by_stage: dict[str, list[Attempt]], pre: dict[str, Attempt],
           post: dict[str, Attempt], paired: list[str], phen: list[PhenStat],
           error_counts: dict[str, Counter[str]],
           error_stage: dict[tuple[str, str], Counter[str]], files: list[Path],
           root: Path) -> list[str]:
    lines = ["# Апробация упражнений: предтест и посттест", ""]
    if ds.synthetic:
        lines += ["> **ВНИМАНИЕ: синтетические данные.** Хотя бы один файл помечен как "
                  "тестовый — числа ниже ничего не говорят о результатах апробации.", ""]
    participants = sorted({a.participant for a in ds.attempts})
    lines += [
        f"- Отчёт построен: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Файлы ({len(ds.files)}): " + ", ".join(f"`{f.name}`" for f in ds.files),
        f"- Участников: **{len(participants)}**; прошли оба этапа: **{len(paired)}**; "
        f"предтест: {len(by_stage['pre'])}, посттест: {len(by_stage['post'])}.",
        f"- Не учтены: незавершённых попыток — {ds.dropped_unfinished}"
        + (f"; повторных попыток (учитывается первая) — {len(ds.dropped_repeat)}: "
           f"{', '.join(ds.dropped_repeat)}" if ds.dropped_repeat else ""),
    ]
    if ds.problems:
        lines += [f"- Пропущенные файлы: {'; '.join(ds.problems)}"]
    lines += ["", "## Наборы заданий", ""]
    set_rows = []
    for stage in ("pre", "post"):
        attempts = by_stage[stage]
        if not attempts:
            continue
        sample = attempts[0].answers
        levels = [LEVELS.index(x.level) + 1 for x in sample if x.level in LEVELS]
        kinds = Counter(x.kind for x in sample)
        set_rows.append([STAGE_LABEL[stage], ", ".join(sorted({a.set_id for a in attempts})),
                         len(sample), _num(statistics.fmean(levels) if levels else None, 1),
                         ", ".join(f"{KIND_LABEL[k].lower()} {kinds.get(k, 0)}" for k in KINDS)])
    lines += [md_table(["Этап", "Набор", "Заданий", "Средний уровень (A1 = 1)", "Состав"],
                       set_rows, text_columns=[1, 4]), "",
              "Наборы A и B построены из разных предложений корпуса и подобраны по уровню "
              "текста и подтипу задания (the/a/an; 个 или специальное 量词; падеж).", ""]
    if len({a.set_id for a in ds.attempts if a.stage == "pre"}) > 1 or \
            len({a.set_id for a in ds.attempts if a.stage == "post"}) > 1:
        lines += ["> Участники проходили разные версии набора (корпус пересобирался между "
                  "попытками) — сравнивайте результаты осторожно.", ""]

    lines += ["## Средний балл", ""]
    rows = []
    for stage in ("pre", "post"):
        attempts = by_stage[stage]
        if not attempts:
            continue
        scores = [a.score for a in attempts]
        times = [x.ms / 1000 for a in attempts for x in a.answers]
        rows.append([STAGE_LABEL[stage], len(attempts), _pct(statistics.fmean(scores)),
                     _num(statistics.stdev(scores), 1) if len(scores) > 1 else "—",
                     _pct(min(scores), 0), _pct(max(scores), 0),
                     _num(statistics.fmean(times), 1)])
    lines += [md_table(["Этап", "Участников", "Средний балл", "SD, п. п.", "Мин.", "Макс.",
                        "Время на задание, с"], rows), ""]

    lines += ["## Прирост от предтеста к посттесту", ""]
    if not paired:
        lines += ["Нет участников, прошедших оба этапа под одним кодом, — прирост не "
                  "рассчитан.", ""]
    else:
        pre_scores = [pre[p].score for p in paired]
        post_scores = [post[p].score for p in paired]
        test = paired_test(pre_scores, post_scores)
        gains = [g for p in paired if (g := hake_gain(pre[p].score, post[p].score)) is not None]
        lines += [md_table(["Показатель", "Значение"], [
            ["Участников с обоими этапами", test.n],
            ["Средний балл: предтест → посттест",
             f"{_pct(statistics.fmean(pre_scores))} → {_pct(statistics.fmean(post_scores))}"],
            ["Средний прирост, п. п.", _num(test.mean_diff, 1)],
            ["SD прироста, п. п.", _num(test.sd_diff, 1)],
            ["Нормализованный прирост g (Хейк), среднее",
             _num(statistics.fmean(gains)) if gains else "—"],
            ["Парный t-критерий", f"t({test.n - 1}) = {_num(test.t)}, p = {_p(test.p_t)}"
             if test.t is not None else "—"],
            ["Критерий Уилкоксона", f"W+ = {_num(test.w_plus, 1)}, p = {_p(test.p_w)}"
             + (" (точное)" if test.wilcoxon_exact else " (нормальное приближение)")
             if test.p_w is not None else "—"],
            ["Размер эффекта d_z", _num(test.dz)],
            ["Улучшили / без изменений / ухудшили результат",
             f"{sum(b > a for a, b in zip(pre_scores, post_scores, strict=True))} / "
             f"{sum(b == a for a, b in zip(pre_scores, post_scores, strict=True))} / "
             f"{sum(b < a for a, b in zip(pre_scores, post_scores, strict=True))}"],
        ], align_right_from=1), ""]
        lines += ["g = (посттест − предтест) / (100 − предтест): доля возможного прироста, "
                  "которая реализована. d_z — средний прирост, делённый на SD прироста."]
        if test.n < 10:
            lines += ["", f"> Участников всего {test.n}: статистические критерии на такой "
                      "выборке ненадёжны, выводы — только предварительные."]
        lines.append("")

    lines += ["## По явлениям", "",
              md_table(["Явление", "Ответов (пред)", "Верно (пред)", "Ответов (пост)",
                        "Верно (пост)", "Средний прирост, п. п."],
                       [[KIND_TITLE[p.kind], p.n_pre, _pct(p.acc_pre), p.n_post, _pct(p.acc_post),
                         _num(p.gain, 1)] for p in phen]), "",
              "Средний прирост считается только по участникам, прошедшим оба этапа.", ""]

    lines += ["## Типичные ошибки", ""]
    for kind in KINDS:
        top = error_counts[kind].most_common(5)
        lines += [f"### {KIND_TITLE[kind]}", ""]
        if not top:
            lines += ["Ошибок нет.", ""]
            continue
        lines += [md_table(["Ошибка (верно → ответ)", "Всего", "Предтест", "Посттест"],
                           [[label, n, error_stage[(kind, label)]["pre"],
                             error_stage[(kind, label)]["post"]] for label, n in top]), ""]
    lines += ["Для падежей тип ошибки определяется по разборам pymorphy3: в какой падеж "
              "поставлена неверная форма того же слова.", "",
              "## Файлы", ""] + [f"- `{_rel(f, root)}`" for f in files]
    lines += ["", "Пересобрать: `python -m pipeline approbation`.", ""]
    return lines


def no_data_report(message: str, sources: Sequence[Path], root: Path) -> str:
    where = ", ".join(f"`{_rel(p, root)}`" for p in sources) or "`data/approbation/`"
    return "\n".join([
        "# Апробация упражнений: предтест и посттест",
        "",
        f"**Данных для анализа нет:** {message}.",
        "",
        "Как собрать данные:",
        "",
        "1. Участники проходят «Упражнения → Режим «Тест»» на сайте: сначала предтест "
        "(набор A), после занятий — посттест (набор B) под тем же кодом.",
        "2. Каждый нажимает «Экспорт результатов (CSV)» и передаёт файл преподавателю.",
        f"3. Файлы кладутся в {where}, затем запускается `python -m pipeline approbation`.",
        "",
    ])


def run(sources: Sequence[Path], out: Path, root: Path) -> tuple[int, list[Path]]:
    try:
        ds = load(sources)
    except NoData as exc:
        print(f"Анализ апробации не выполнен: {exc}.")
        out.mkdir(parents=True, exist_ok=True)
        path = out / "approbation.md"
        path.write_text(no_data_report(str(exc), sources, root), encoding="utf-8")
        return 0, [path]
    files = analyse(ds, out, root)
    pre = [a.score for a in ds.attempts if a.stage == "pre"]
    post = [a.score for a in ds.attempts if a.stage == "post"]
    print(f"Попыток: {len(ds.attempts)}; средний балл: предтест "
          f"{_pct(statistics.fmean(pre)) if pre else '—'}, посттест "
          f"{_pct(statistics.fmean(post)) if post else '—'}"
          + (" — СИНТЕТИЧЕСКИЕ ДАННЫЕ" if ds.synthetic else ""))
    return 0, files
