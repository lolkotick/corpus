import { useId, useState } from 'react';

import type { GoldFile, PairStatus } from '../../lib/gold';
import { plural } from '../../lib/labels';
import { buttonClasses, cx } from '../../lib/styles';
import { DownloadIcon } from '../icons';

export function Toolbar({
  gold,
  done,
  partial,
  total,
  maxSize,
  onExport,
  onImport,
  onResize,
  onReset,
}: {
  gold: GoldFile;
  done: number;
  partial: number;
  total: number;
  maxSize: number;
  onExport: () => void;
  onImport: () => void;
  onResize: (size: number) => void;
  onReset: () => void;
}) {
  const id = useId();
  const [size, setSize] = useState(gold.sample.size);
  const percent = total ? Math.round((100 * done) / total) : 0;
  return (
    <section
      aria-label="Ход проверки"
      className="rounded-2xl border border-rule bg-surface p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-[14rem] flex-1">
          <p className="text-[13.5px] text-muted">
            {gold.annotator ? `Эксперт: ${gold.annotator} · ` : ''}выборка {gold.sample.size}{' '}
            {plural(gold.sample.size, 'пара', 'пары', 'пар')}, seed {gold.sample.seed}
          </p>
          <p className="mt-1 text-[15px]">
            Проверено <b className="tabular-nums">{done}</b> из {total}
            {partial > 0 && <span className="text-muted"> · начато {partial}</span>}
          </p>
          <div
            role="progressbar"
            aria-label="Проверено пар"
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={done}
            aria-valuetext={`${String(done)} из ${String(total)}`}
            className="mt-2 h-1.5 overflow-hidden rounded-full bg-sunken"
          >
            <div
              className="h-full rounded-full bg-ink/70"
              style={{ width: `${String(percent)}%` }}
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={cx(buttonClasses.primary, 'py-2.5')} onClick={onExport}>
            <DownloadIcon size={16} /> Экспорт gold.json
          </button>
          <button type="button" className={cx(buttonClasses.ghost, 'py-2.5')} onClick={onImport}>
            Импорт
          </button>
        </div>
      </div>
      <details className="mt-3 border-t border-rule pt-3 text-sm">
        <summary className="cursor-pointer text-muted select-none hover:text-ink">
          Настройки выборки
        </summary>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-[13px] text-muted" htmlFor={`${id}-size`}>
            Объём выборки (тот же seed, проверки сохраняются)
            <input
              id={`${id}-size`}
              type="number"
              min={1}
              max={maxSize}
              value={Number.isNaN(size) ? '' : size}
              onChange={(e) => setSize(e.target.valueAsNumber)}
              className="w-32 rounded-lg border border-rule-strong bg-surface px-2.5 py-1.5 text-[14.5px] text-ink"
            />
          </label>
          <button
            type="button"
            className={cx(buttonClasses.ghost, 'px-4 py-2 text-sm')}
            disabled={!Number.isInteger(size) || size < 1 || size === gold.sample.size}
            onClick={() => onResize(size)}
          >
            Применить
          </button>
          <button
            type="button"
            className={cx(buttonClasses.subtle, 'text-danger hover:text-danger')}
            onClick={onReset}
          >
            Удалить проверку из браузера…
          </button>
        </div>
      </details>
    </section>
  );
}

const STATUS_LABEL: Record<PairStatus, string> = {
  done: 'проверена',
  partial: 'начата',
  empty: 'не начата',
};

/** Номера пар выборки: переход к любой паре, статус виден по заливке. */
export function PairStrip({
  statuses,
  current,
  onSelect,
}: {
  statuses: readonly PairStatus[];
  current: number;
  onSelect: (index: number) => void;
}) {
  return (
    <nav aria-label="Пары выборки" className="mt-4">
      <ol className="flex flex-wrap gap-1.5">
        {statuses.map((status, i) => (
          <li key={i}>
            <button
              type="button"
              onClick={() => onSelect(i)}
              aria-current={i === current ? 'step' : undefined}
              aria-label={`Пара ${String(i + 1)}: ${STATUS_LABEL[status]}`}
              className={cx(
                'size-8 rounded-lg font-mono text-[12.5px] tabular-nums transition',
                status === 'done'
                  ? 'bg-ink/80 text-paper'
                  : status === 'partial'
                    ? 'bg-warn-tint text-warn ring-1 ring-warn/50 ring-inset'
                    : 'bg-surface text-muted ring-1 ring-rule ring-inset hover:text-ink',
                i === current && 'ring-2 ring-ink ring-offset-2 ring-offset-paper',
              )}
            >
              {i + 1}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
