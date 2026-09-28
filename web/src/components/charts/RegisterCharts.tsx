import {
  Bar,
  BarChart,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts';

import type { Lang, RegisterStat, Stats } from '../../data/types';
import { AXIS_TICK, CURSOR, formatInt, GRID_STROKE, MARK, SURFACE } from '../../lib/chartTheme';
import { CASES } from '../../lib/labels';
import { ChartCard, DataTable, TooltipBox } from './ChartParts';

const LABEL_STYLE = { fill: 'var(--muted)', fontSize: 12 } as const;
const BAR = { maxBarSize: 26, stroke: SURFACE, strokeWidth: 2 } as const;

function num(value: number, digits = 1): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

/** Показатель по регистрам: горизонтальные столбцы цвета языка, подпись — регистр. */
function RegisterBars({
  data,
  lang,
  unit,
}: {
  data: { name: string; value: number; note: string }[];
  lang: Lang;
  unit: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={data.length * 40 + 16}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
        <XAxis type="number" hide domain={[0, 'dataMax']} />
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
          content={(args: TooltipContentProps) => {
            const d = args.active ? data.find((x) => x.name === String(args.label)) : undefined;
            if (!d) return null;
            return (
              <TooltipBox
                title={`Регистр: ${d.name}`}
                rows={[{ label: unit, value: num(d.value, 2), color: MARK[lang] }]}
                note={d.note}
              />
            );
          }}
        />
        <Bar dataKey="value" fill={MARK[lang]} radius={[0, 4, 4, 0]} {...BAR}>
          <LabelList
            dataKey="value"
            position="right"
            style={LABEL_STYLE}
            formatter={(v: unknown) => (typeof v === 'number' ? num(v) : '')}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ArticleByRegister({ registers }: { registers: RegisterStat[] }) {
  const data = registers.map((r) => ({
    name: r.register,
    value: r.articles.per_100_words,
    note: `${formatInt(r.articles.counts.the + r.articles.counts.a + r.articles.counts.an)} артиклей на ${formatInt(r.words.en)} слов`,
  }));
  return (
    <ChartCard
      id="reg-articles"
      lang="en"
      title="Артикли"
      subtitle="Артиклей на 100 английских слов."
      summary={`Артиклей на 100 слов: ${data.map((d) => `${d.name} ${num(d.value)}`).join('; ')}.`}
      table={
        <DataTable
          caption="Артикли по регистрам"
          head={['Регистр', 'the', 'a', 'an', 'На 100 слов', 'the на 100', 'a/an на 100']}
          rows={registers.map((r) => [
            r.register,
            r.articles.counts.the,
            r.articles.counts.a,
            r.articles.counts.an,
            num(r.articles.per_100_words, 2),
            num(r.articles.per_100_words_by_value.the, 2),
            num(r.articles.per_100_words_by_value.a + r.articles.per_100_words_by_value.an, 2),
          ])}
        />
      }
    >
      <RegisterBars data={data} lang="en" unit="артиклей на 100 слов" />
    </ChartCard>
  );
}

function ClassifierByRegister({ registers }: { registers: RegisterStat[] }) {
  const data = registers.map((r) => ({
    name: r.register,
    value: r.classifiers.per_100_chars,
    note: `${formatInt(r.classifiers.count)} конструкций, ${r.classifiers.distinct} разных 量词`,
  }));
  return (
    <ChartCard
      id="reg-classifiers"
      lang="zh"
      title="Счётные слова 量词"
      subtitle="Конструкций с 量词 на 100 иероглифов."
      summary={`量词 на 100 иероглифов: ${data.map((d) => `${d.name} ${num(d.value)}`).join('; ')}.`}
      table={
        <DataTable
          caption="量词 по регистрам"
          head={['Регистр', 'Конструкций', 'Разных 量词', 'На 100 иероглифов', 'Самые частые']}
          rows={registers.map((r) => [
            r.register,
            r.classifiers.count,
            r.classifiers.distinct,
            num(r.classifiers.per_100_chars, 2),
            r.classifiers.top
              .slice(0, 5)
              .map((c) => `${c.value} ${num(c.share)} %`)
              .join(', ') || '—',
          ])}
        />
      }
    >
      <RegisterBars data={data} lang="zh" unit="量词 на 100 иероглифов" />
    </ChartCard>
  );
}

/** Распределение падежей: строки — регистры, ячейки — доля падежа с оттенком по величине. */
function CaseByRegister({ registers }: { registers: RegisterStat[] }) {
  const codes = casesIn(registers);
  const max = Math.max(1, ...registers.flatMap((r) => r.cases.distribution.map((c) => c.share)));
  return (
    <ChartCard
      id="reg-cases"
      lang="ru"
      title="Падежи существительных"
      subtitle="Доля каждого падежа среди существительных регистра, %. Чем насыщеннее ячейка, тем больше доля."
      className="lg:col-span-2"
      summary={registers
        .map(
          (r) =>
            `${r.register}: ${r.cases.distribution.map((c) => `${c.label} ${num(c.share)} %`).join(', ')}`,
        )
        .join('; ')}
      table={
        <DataTable
          caption="Падежи по регистрам (число существительных)"
          head={['Регистр', ...codes.map((c) => CASES[c].label), 'Всего', 'На 100 слов']}
          rows={registers.map((r) => [
            r.register,
            ...codes.map((c) => r.cases.distribution.find((d) => d.case === c)?.count ?? 0),
            r.cases.nouns,
            num(r.cases.per_100_words),
          ])}
        />
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] border-separate border-spacing-1 text-[13.5px]">
          <thead>
            <tr className="text-muted">
              <th scope="col" className="px-2 py-1 text-left font-medium">
                Регистр
              </th>
              {codes.map((c) => (
                <th key={c} scope="col" className="px-2 py-1 text-right font-medium">
                  {CASES[c].label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {registers.map((r) => (
              <tr key={r.register}>
                <th scope="row" className="px-2 py-1.5 text-left font-medium">
                  {r.register}
                  <span className="block text-[12px] font-normal text-muted">
                    {formatInt(r.cases.nouns)} сущ.
                  </span>
                </th>
                {codes.map((c) => {
                  const share = r.cases.distribution.find((d) => d.case === c)?.share ?? 0;
                  const tint = Math.round((share / max) * 40);
                  return (
                    <td
                      key={c}
                      className="rounded-md px-2 py-1.5 text-right tabular-nums"
                      style={{
                        background: `color-mix(in oklab, var(--ru-mark) ${tint}%, var(--surface))`,
                      }}
                    >
                      {num(share)} %
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartCard>
  );
}

function casesIn(registers: RegisterStat[]) {
  const present = new Set(registers.flatMap((r) => r.cases.distribution.map((c) => c.case)));
  return (Object.keys(CASES) as (keyof typeof CASES)[]).filter((c) => present.has(c));
}

export function RegisterComparison({ stats }: { stats: Stats }) {
  const registers = stats.registers ?? [];
  if (registers.length < 2) {
    return (
      <p className="mt-5 rounded-2xl border border-dashed border-rule-strong p-5 text-muted">
        Сейчас в корпусе один регистр ({registers[0]?.register ?? 'учебный'}). Сравнение появится
        после импорта данных Tatoeba (бытовой регистр) или корпуса ООН (официальный):{' '}
        <code>python -m pipeline import tatoeba</code>, затем <code>python -m pipeline build</code>.
      </p>
    );
  }
  return (
    <>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <ArticleByRegister registers={registers} />
        <ClassifierByRegister registers={registers} />
        <CaseByRegister registers={registers} />
      </div>
      <div className="mt-5 rounded-2xl border border-rule bg-surface p-5 sm:p-6">
        <DataTable
          caption="Объём регистров"
          head={['Регистр', 'Текстов', 'Пар', 'Слов EN', 'Иероглифов ZH', 'Слов RU', 'Сложность']}
          rows={registers.map((r) => [
            r.register,
            r.texts,
            r.pairs,
            r.words.en,
            r.words.zh,
            r.words.ru,
            r.difficulty_mean === null ? '—' : num(r.difficulty_mean, 2),
          ])}
        />
      </div>
    </>
  );
}
