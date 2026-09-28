import type { ReactNode } from 'react';

import type { Lang } from '../../data/types';
import { cx } from '../../lib/styles';
import { LangBadge } from '../ui';

export function ChartCard({
  id,
  lang,
  title,
  subtitle,
  legend,
  summary,
  children,
  table,
  className,
}: {
  id: string;
  lang?: Lang;
  title: string;
  subtitle?: ReactNode;
  legend?: ReactNode;
  /** Текстовое описание графика для скринридеров. */
  summary: string;
  children: ReactNode;
  table: ReactNode;
  className?: string;
}) {
  return (
    <section
      aria-labelledby={`${id}-title`}
      className={cx('rounded-2xl border border-rule bg-surface p-5 sm:p-6', className)}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 id={`${id}-title`} className="flex items-center gap-2 text-[17px] font-semibold">
            {lang && <LangBadge lang={lang} />}
            {title}
          </h3>
          {subtitle && <p className="mt-1 max-w-prose text-sm text-muted">{subtitle}</p>}
        </div>
        {legend}
      </header>
      <figure className="mt-4">
        <div role="img" aria-label={summary}>
          {children}
        </div>
      </figure>
      <details className="group mt-3 border-t border-rule pt-3 text-sm">
        <summary className="cursor-pointer text-muted select-none hover:text-ink">
          Таблица данных
        </summary>
        <div className="mt-3 overflow-x-auto">{table}</div>
      </details>
    </section>
  );
}

/** Легенда: образец метки (прямоугольник для столбцов) + подпись цветом текста. */
export function Legend({ items }: { items: { label: string; color: string; line?: boolean }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted" aria-label="Легенда">
      {items.map((item) => (
        <li key={item.label} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={item.line ? 'h-0.5 w-4 rounded-full' : 'size-2.5 rounded-[3px]'}
            style={{ background: item.color }}
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

/** Подсказка: значение — главное (жирное), подпись ряда — вторична; ключ — короткая линия. */
export function TooltipBox({
  title,
  rows,
  note,
}: {
  title: ReactNode;
  rows: TooltipRow[];
  note?: ReactNode;
}) {
  return (
    <div className="max-w-[16rem] rounded-xl border border-rule bg-surface px-3 py-2.5 text-[13px] shadow-soft">
      <p className="mb-1.5 font-medium text-ink">{title}</p>
      <ul className="space-y-1">
        {rows.map((row) => (
          <li key={row.label} className="flex items-center gap-2">
            {row.color && (
              <span
                aria-hidden="true"
                className="h-0.5 w-3 rounded-full"
                style={{ background: row.color }}
              />
            )}
            <b className="font-semibold text-ink tabular-nums">{row.value}</b>
            <span className="text-muted">{row.label}</span>
          </li>
        ))}
      </ul>
      {note && <p className="mt-1.5 border-t border-rule pt-1.5 text-muted">{note}</p>}
    </div>
  );
}

export function DataTable({
  caption,
  head,
  rows,
}: {
  caption: string;
  head: string[];
  rows: (string | number)[][];
}) {
  return (
    <table className="w-full min-w-[20rem] text-left text-[13.5px]">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-rule text-muted">
          {head.map((h, i) => (
            <th
              key={h}
              scope="col"
              className={cx('py-1.5 pr-4 font-medium', i > 0 && 'text-right')}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-rule">
        {rows.map((row) => (
          <tr key={String(row[0])}>
            {row.map((cell, i) => (
              <td key={i} className={cx('py-1.5 pr-4', i > 0 && 'text-right tabular-nums')}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function StatTile({
  label,
  value,
  detail,
  lang,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  lang?: Lang;
}) {
  return (
    <div className="rounded-2xl border border-rule bg-surface p-5">
      <p className="flex items-center gap-2 text-[13.5px] text-muted">
        {lang && <LangBadge lang={lang} />}
        {label}
      </p>
      <p className="mt-2 text-[32px] leading-none font-semibold">{value}</p>
      {detail && <p className="mt-2 text-[13px] text-muted">{detail}</p>}
    </div>
  );
}
