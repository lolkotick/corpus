import { useId, useMemo, useState } from 'react';

import type { Corpus } from '../../data/types';
import { DEFAULT_SAMPLE_SIZE, DEFAULT_SEED, sampleByText, samplePairIds } from '../../lib/gold';
import { plural } from '../../lib/labels';
import { buttonClasses, cx } from '../../lib/styles';

const FIELD =
  'w-full rounded-[10px] border border-rule-strong bg-surface px-3 py-2.5 text-[15px] outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-ink/20';

export function SetupPanel({
  corpus,
  onStart,
  onImport,
}: {
  corpus: Corpus;
  onStart: (options: { annotator: string; size: number; seed: number }) => void;
  onImport: () => void;
}) {
  const id = useId();
  const total = corpus.pairs.length;
  const [annotator, setAnnotator] = useState('');
  const [size, setSize] = useState(Math.min(DEFAULT_SAMPLE_SIZE, total));
  const [seed, setSeed] = useState(DEFAULT_SEED);
  const valid = Number.isInteger(size) && size >= 1 && size <= total && Number.isInteger(seed);
  const preview = useMemo(
    () => (valid ? sampleByText(corpus, samplePairIds(corpus, size, seed)) : []),
    [corpus, size, seed, valid],
  );

  return (
    <section
      aria-labelledby={`${id}-title`}
      className="grid gap-8 rounded-2xl border border-rule bg-surface p-5 sm:p-8 lg:grid-cols-[1fr_1fr]"
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (valid) onStart({ annotator, size, seed });
        }}
        className="grid content-start gap-4"
      >
        <h2 id={`${id}-title`} className="font-serif text-[24px] font-semibold">
          Новая выборка
        </h2>
        <label className="grid gap-1.5 text-sm font-medium">
          Эксперт (имя или код)
          <input
            className={FIELD}
            value={annotator}
            autoComplete="name"
            onChange={(e) => setAnnotator(e.target.value)}
            placeholder="например, Глеб"
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-1.5 text-sm font-medium">
            Сколько пар проверить
            <input
              className={FIELD}
              type="number"
              min={1}
              max={total}
              value={Number.isNaN(size) ? '' : size}
              onChange={(e) => setSize(e.target.valueAsNumber)}
            />
            <span className="text-xs font-normal text-muted">из {total} в корпусе</span>
          </label>
          <label className="grid gap-1.5 text-sm font-medium">
            Seed (зерно выборки)
            <input
              className={FIELD}
              type="number"
              min={0}
              value={Number.isNaN(seed) ? '' : seed}
              onChange={(e) => setSeed(e.target.valueAsNumber)}
            />
            <span className="text-xs font-normal text-muted">тот же seed — та же выборка</span>
          </label>
        </div>
        <div className="flex flex-wrap gap-3 pt-1">
          <button type="submit" disabled={!valid} className={buttonClasses.primary}>
            Начать проверку
          </button>
          <button type="button" className={buttonClasses.ghost} onClick={onImport}>
            Продолжить из gold.json
          </button>
        </div>
      </form>

      <div className="grid content-start gap-3">
        <h3 className="text-[15px] font-semibold">Как устроена выборка</h3>
        <p className="text-[14.5px] text-muted">
          Пары отбираются случайно, но пропорционально размеру текстов: каждый текст представлен той
          же долей, что и в корпусе. Список воспроизводится по seed (так же считает{' '}
          <code className="text-[13px]">pipeline/gold.py</code>), а при увеличении объёма прежние
          пары остаются в выборке.
        </p>
        {valid && (
          <table className="w-full text-[14px]">
            <caption className="sr-only">Распределение выборки по текстам</caption>
            <thead className="border-b border-rule text-left text-xs text-muted">
              <tr>
                <th scope="col" className="py-1.5 font-medium">
                  Текст
                </th>
                <th scope="col" className="py-1.5 text-right font-medium">
                  В выборке
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {preview.map((row) => (
                <tr key={row.textId}>
                  <td className="py-1.5">{row.title}</td>
                  <td className="py-1.5 text-right tabular-nums">
                    {row.sampled}{' '}
                    <span className="text-muted">
                      из {row.total} {plural(row.total, 'пары', 'пар', 'пар')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className={cx('rounded-xl bg-sunken p-3 text-[13.5px] text-muted')}>
          Эталон размечает только эксперт. Результаты хранятся в этом браузере; чтобы использовать
          их в отчётах, нажмите «Экспорт gold.json» и сохраните файл как{' '}
          <code className="text-[12.5px]">data/gold/gold.json</code>.
        </p>
      </div>
    </section>
  );
}
