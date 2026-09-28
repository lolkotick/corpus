import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Rectangle,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type BarShapeProps,
  type TooltipContentProps,
} from 'recharts';

import type { ClassifierInfo, Lang, Stats } from '../../data/types';
import {
  AXIS_TICK,
  CURSOR,
  formatInt,
  formatPercent,
  GRID_STROKE,
  MARK,
  SURFACE,
} from '../../lib/chartTheme';
import { CASE_ORDER, CASES, formatScore } from '../../lib/labels';
import { ChartCard, DataTable, Legend, TooltipBox } from './ChartParts';

type TooltipArgs = TooltipContentProps;

const LABEL_STYLE = { fill: 'var(--muted)', fontSize: 12 } as const;
const BAR = { maxBarSize: 22, stroke: SURFACE, strokeWidth: 2 } as const;

/** Столбец своего цвета (вместо устаревшего Cell); наведённый столбец чуть светлеет. */
function coloredBar(fillAt: (index: number) => string) {
  function ColoredBar(props: BarShapeProps) {
    return (
      <Rectangle {...props} fill={fillAt(props.index)} fillOpacity={props.isActive ? 0.8 : 1} />
    );
  }
  return ColoredBar;
}

function activeKey(args: TooltipArgs): string | null {
  return args.active && args.label !== undefined ? String(args.label) : null;
}

/* ─── RU: падежи ─────────────────────────────────────────────────────────── */

export function CaseChart({ stats }: { stats: Stats }) {
  const data = CASE_ORDER.map((code) => {
    const row = stats.cases.find((c) => c.case === code);
    const sing = row?.sing ?? 0;
    const plur = row?.plur ?? 0;
    return {
      name: CASES[code].label,
      question: CASES[code].question,
      sing,
      plur,
      total: sing + plur,
      ambiguous: row?.ambiguous ?? 0,
    };
  });
  const total = data.reduce((sum, d) => sum + d.total, 0);
  const top = [...data].sort((a, b) => b.total - a.total)[0];

  return (
    <ChartCard
      id="cases"
      lang="ru"
      title="Падежи существительных"
      subtitle={`${formatInt(total)} существительных в русских предложениях; чаще всего — ${
        top?.name.toLowerCase() ?? ''
      } падеж.`}
      legend={
        <Legend
          items={[
            { label: 'единственное число', color: MARK.ru },
            { label: 'множественное число', color: MARK.ru2 },
          ]}
        />
      }
      summary={`Распределение падежей: ${data.map((d) => `${d.name} ${d.total}`).join(', ')}.`}
      table={
        <DataTable
          caption="Падежи существительных"
          head={['Падеж', 'Ед. ч.', 'Мн. ч.', 'Всего', 'Доля', 'Неоднозначно']}
          rows={data.map((d) => [
            d.name,
            d.sing,
            d.plur,
            d.total,
            formatPercent(d.total, total),
            d.ambiguous,
          ])}
        />
      }
    >
      <ResponsiveContainer width="100%" height={data.length * 40 + 30}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 44, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} stroke={GRID_STROKE} />
          <XAxis
            type="number"
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: GRID_STROKE }}
            width={104}
          />
          <Tooltip
            cursor={CURSOR}
            content={(args: TooltipArgs) => {
              const d = data.find((x) => x.name === activeKey(args));
              if (!d) return null;
              return (
                <TooltipBox
                  title={`${d.name} (${d.question})`}
                  rows={[
                    { label: 'ед. ч.', value: formatInt(d.sing), color: MARK.ru },
                    { label: 'мн. ч.', value: formatInt(d.plur), color: MARK.ru2 },
                  ]}
                  note={`Всего ${formatInt(d.total)} (${formatPercent(d.total, total)})${
                    d.ambiguous ? `, неоднозначных: ${d.ambiguous}` : ''
                  }`}
                />
              );
            }}
          />
          <Bar dataKey="sing" name="ед. ч." stackId="n" fill={MARK.ru} {...BAR} />
          <Bar
            dataKey="plur"
            name="мн. ч."
            stackId="n"
            fill={MARK.ru2}
            radius={[0, 4, 4, 0]}
            {...BAR}
          >
            <LabelList dataKey="total" position="right" style={LABEL_STYLE} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

/* ─── ZH: счётные слова ──────────────────────────────────────────────────── */

const TOP_CLASSIFIERS = 12;

export function ClassifierChart({
  stats,
  classifiers,
}: {
  stats: Stats;
  classifiers: ReadonlyMap<string, ClassifierInfo>;
}) {
  const all = stats.classifiers;
  const top = all.slice(0, TOP_CLASSIFIERS);
  const rest = all.slice(TOP_CLASSIFIERS);
  const data = [
    ...top.map((c) => ({
      key: c.value,
      label: `${c.value} ${c.pinyin}`,
      count: c.count,
      gloss: c.gloss,
      nouns: c.nouns.map((n) => n.noun).join('、'),
    })),
    ...(rest.length
      ? [
          {
            key: 'other',
            label: `ещё ${rest.length}`,
            count: rest.reduce((s, c) => s + c.count, 0),
            gloss: rest.map((c) => c.value).join(' '),
            nouns: '',
          },
        ]
      : []),
  ];
  const total = all.reduce((s, c) => s + c.count, 0);
  const first = all[0];

  return (
    <ChartCard
      id="classifiers"
      lang="zh"
      title="Частотность счётных слов 量词"
      subtitle={
        first
          ? `${formatInt(total)} конструкций, ${all.length} разных 量词. Универсальное ${first.value} — ${formatPercent(first.count, total)} всех употреблений.`
          : undefined
      }
      summary={`Частотность счётных слов: ${data.map((d) => `${d.label} ${d.count}`).join(', ')}.`}
      table={
        <DataTable
          caption="Счётные слова"
          head={['量词', 'Пиньинь', 'Употреблений', 'Доля', 'С какими словами']}
          rows={all.map((c) => [
            c.value,
            c.pinyin,
            c.count,
            formatPercent(c.count, total),
            c.nouns.length > 0
              ? c.nouns.map((n) => n.noun).join('、')
              : (classifiers.get(c.value)?.gloss ?? '—'),
          ])}
        />
      }
    >
      <ResponsiveContainer width="100%" height={data.length * 30 + 30}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} stroke={GRID_STROKE} />
          <XAxis
            type="number"
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ ...AXIS_TICK, fontFamily: 'var(--font-zh)' }}
            tickLine={false}
            axisLine={{ stroke: GRID_STROKE }}
            width={104}
          />
          <Tooltip
            cursor={CURSOR}
            content={(args: TooltipArgs) => {
              const d = data.find((x) => x.label === activeKey(args));
              if (!d) return null;
              return (
                <TooltipBox
                  title={<span lang="zh-Hans">{d.label}</span>}
                  rows={[
                    {
                      label: `употреблений (${formatPercent(d.count, total)})`,
                      value: formatInt(d.count),
                      color: MARK.zh,
                    },
                  ]}
                  note={
                    <>
                      {d.gloss}
                      {d.nouns && (
                        <span lang="zh-Hans" className="mt-1 block">
                          {d.nouns}
                        </span>
                      )}
                    </>
                  }
                />
              );
            }}
          />
          <Bar
            dataKey="count"
            fill={MARK.zh}
            radius={[0, 4, 4, 0]}
            {...BAR}
            shape={coloredBar((i) => (data[i]?.key === 'other' ? MARK.neutral : MARK.zh))}
          >
            <LabelList dataKey="count" position="right" style={LABEL_STYLE} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

/* ─── EN: артикли ────────────────────────────────────────────────────────── */

export function ArticleChart({ stats }: { stats: Stats }) {
  const counts = stats.articles.counts;
  const total = counts.the + counts.a + counts.an;
  const data = (['the', 'a', 'an'] as const).map((value) => ({
    value,
    count: counts[value],
    kind: value === 'the' ? 'определённый' : 'неопределённый',
  }));
  const heads = stats.articles.top_heads;

  return (
    <ChartCard
      id="articles"
      lang="en"
      title="Артикли the / a / an"
      subtitle={`${formatInt(total)} артиклей: определённый the — ${formatPercent(counts.the, total)}, неопределённые a/an — ${formatPercent(counts.a + counts.an, total)}.`}
      summary={`Артикли: the ${counts.the}, a ${counts.a}, an ${counts.an}.`}
      table={
        <DataTable
          caption="Артикли"
          head={['Артикль', 'Вид', 'Употреблений', 'Доля']}
          rows={data.map((d) => [d.value, d.kind, d.count, formatPercent(d.count, total)])}
        />
      }
    >
      <ResponsiveContainer width="100%" height={data.length * 40 + 30}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 64, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} stroke={GRID_STROKE} />
          <XAxis
            type="number"
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="value"
            tick={{ ...AXIS_TICK, fontSize: 14 }}
            tickLine={false}
            axisLine={{ stroke: GRID_STROKE }}
            width={44}
          />
          <Tooltip
            cursor={CURSOR}
            content={(args: TooltipArgs) => {
              const d = data.find((x) => x.value === activeKey(args));
              if (!d) return null;
              return (
                <TooltipBox
                  title={`${d.value} — ${d.kind}`}
                  rows={[
                    {
                      label: `употреблений (${formatPercent(d.count, total)})`,
                      value: formatInt(d.count),
                      color: MARK.en,
                    },
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="count" fill={MARK.en} radius={[0, 4, 4, 0]} {...BAR}>
            <LabelList
              dataKey="count"
              position="right"
              style={LABEL_STYLE}
              formatter={(v: unknown) =>
                typeof v === 'number' ? `${v} · ${formatPercent(v, total)}` : ''
              }
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-4 grid gap-4 border-t border-rule pt-4 text-sm sm:grid-cols-2">
        {(['the', 'a/an'] as const).map((key) => (
          <div key={key}>
            <p className="text-muted">
              Чаще всего с <b className="font-semibold text-ink">{key}</b>:
            </p>
            <p className="mt-1 font-serif text-[15px]" lang="en">
              {heads[key].slice(0, 6).map((h, i) => (
                <span key={h.lemma}>
                  {i > 0 && ', '}
                  {h.lemma} <span className="font-sans text-xs text-muted">{h.count}</span>
                </span>
              ))}
            </p>
          </div>
        ))}
      </div>
    </ChartCard>
  );
}

/* ─── Выравнивание: гистограмма alignment_score ─────────────────────────── */

export function AlignmentHistogram({ stats }: { stats: Stats }) {
  const { histogram, low_score_threshold: threshold } = stats.alignment;
  const data = histogram.map((bin) => ({
    key: `${formatScore(bin.from)}–${formatScore(bin.to)}`,
    count: bin.count,
    low: bin.to <= threshold + 1e-9,
  }));
  const total = histogram.reduce((s, b) => s + b.count, 0);

  return (
    <ChartCard
      id="alignment"
      title="Оценка выравнивания (alignment_score)"
      subtitle={`Среднее ${formatScore(stats.alignment.mean)}, медиана ${formatScore(stats.alignment.median)}. Ниже порога ${formatScore(threshold)} — ${stats.alignment.low_count} ${stats.alignment.low_count === 1 ? 'пара' : 'пар'}: их стоит проверить вручную или через LLM.`}
      legend={
        <Legend
          items={[
            { label: 'пары', color: MARK.neutral },
            { label: `ниже порога ${formatScore(threshold)}`, color: MARK.low },
          ]}
        />
      }
      summary={`Гистограмма оценок выравнивания: ${data.map((d) => `${d.key}: ${d.count}`).join('; ')}.`}
      table={
        <DataTable
          caption="Гистограмма alignment_score"
          head={['Интервал', 'Пар', 'Доля']}
          rows={data.map((d) => [d.key, d.count, formatPercent(d.count, total)])}
        />
      }
    >
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 22, right: 4, bottom: 4, left: -18 }}>
          <CartesianGrid vertical={false} stroke={GRID_STROKE} />
          <XAxis
            dataKey="key"
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: GRID_STROKE }}
            tickFormatter={(value: string) => value.split('–')[0] ?? value}
            interval={0}
          />
          <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip
            cursor={CURSOR}
            content={(args: TooltipArgs) => {
              const d = data.find((x) => x.key === activeKey(args));
              if (!d) return null;
              return (
                <TooltipBox
                  title={`alignment_score ${d.key}`}
                  rows={[
                    {
                      label: `пар (${formatPercent(d.count, total)})`,
                      value: formatInt(d.count),
                      color: d.low ? MARK.low : MARK.neutral,
                    },
                  ]}
                  note={d.low ? 'ниже порога — требует проверки' : undefined}
                />
              );
            }}
          />
          <Bar
            dataKey="count"
            fill={MARK.neutral}
            radius={[4, 4, 0, 0]}
            maxBarSize={36}
            stroke={SURFACE}
            strokeWidth={2}
          >
            <LabelList
              dataKey="count"
              position="top"
              style={LABEL_STYLE}
              formatter={(v: unknown) => (typeof v === 'number' && v > 0 ? v : '')}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

/* ─── Сравнение текстов: малые множители по трём явлениям ──────────────── */

const DENSITY: Record<
  Lang,
  {
    key: 'articles_per_100_words' | 'classifiers_per_100_chars' | 'nouns_per_100_words';
    title: string;
    unit: string;
  }
> = {
  en: { key: 'articles_per_100_words', title: 'Артикли', unit: 'на 100 слов EN' },
  zh: { key: 'classifiers_per_100_chars', title: '量词', unit: 'на 100 иероглифов' },
  ru: { key: 'nouns_per_100_words', title: 'Существительные', unit: 'на 100 слов RU' },
};

export function TextDensityChart({ stats, lang }: { stats: Stats; lang: Lang }) {
  const spec = DENSITY[lang];
  const data = stats.texts.map((t) => ({
    key: t.id,
    name: `${t.level} · ${t.title_ru || t.title}`,
    value: t.density[spec.key],
  }));
  return (
    <div>
      <h4 className="text-[15px] font-semibold">
        {spec.title} <span className="font-normal text-muted">{spec.unit}</span>
      </h4>
      <div
        role="img"
        aria-label={`${spec.title} ${spec.unit}: ${data.map((d) => `${d.name} ${d.value}`).join('; ')}.`}
      >
        <ResponsiveContainer width="100%" height={data.length * 30 + 20}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 6, right: 36, bottom: 0, left: 0 }}
          >
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ ...AXIS_TICK, fontSize: 12.5 }}
              tickLine={false}
              axisLine={{ stroke: GRID_STROKE }}
              width={250}
            />
            <Tooltip
              cursor={CURSOR}
              content={(args: TooltipArgs) => {
                const d = data.find((x) => x.name === activeKey(args));
                if (!d) return null;
                return (
                  <TooltipBox
                    title={d.name}
                    rows={[
                      {
                        label: spec.unit,
                        value: d.value.toLocaleString('ru-RU'),
                        color: MARK[lang],
                      },
                    ]}
                  />
                );
              }}
            />
            <Bar dataKey="value" fill={MARK[lang]} radius={[0, 4, 4, 0]} {...BAR}>
              <LabelList
                dataKey="value"
                position="right"
                style={LABEL_STYLE}
                formatter={(v: unknown) => (typeof v === 'number' ? v.toLocaleString('ru-RU') : '')}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
