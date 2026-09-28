import type { ReactNode } from 'react';

import type { CorpusIndex } from '../../data/corpusContext';
import type { Level, NumberCode, Phenomenon, Status } from '../../data/types';
import {
  CASE_ORDER,
  CASES,
  formatScore,
  LEVELS,
  NUMBERS,
  PHENOMENA,
  STATUSES,
} from '../../lib/labels';
import { activeFilterCount, DEFAULT_PARAMS, type SearchParams } from '../../lib/search';
import { cx } from '../../lib/styles';

interface Props {
  data: CorpusIndex;
  params: SearchParams;
  onChange: (patch: Partial<SearchParams>) => void;
}

function Pill({
  label,
  active,
  children,
}: {
  label: string;
  active: boolean;
  children: ReactNode;
}) {
  return (
    <label
      className={cx(
        'inline-flex max-w-full items-center gap-1.5 rounded-full border py-1 pr-1.5 pl-3 text-[13.5px] transition focus-within:ring-2 focus-within:ring-en/40',
        active
          ? 'border-ink/50 bg-surface text-ink'
          : 'border-rule-strong bg-surface text-muted hover:border-ink/30',
      )}
    >
      <span className="shrink-0">{label}:</span>
      {children}
    </label>
  );
}

const selectClass =
  'field-sizing-content min-w-0 max-w-[14rem] truncate rounded-full bg-transparent py-0.5 pr-1 font-medium text-ink outline-none';

function subOptions(data: CorpusIndex, phen: Phenomenon | ''): { value: string; label: string }[] {
  if (phen === 'article') {
    return [
      { value: 'the', label: 'the' },
      { value: 'a', label: 'a' },
      { value: 'an', label: 'an' },
      { value: 'definite', label: 'определённый (the)' },
      { value: 'indefinite', label: 'неопределённый (a / an)' },
    ];
  }
  if (phen === 'classifier') {
    return data.stats.classifiers.map((c) => ({
      value: c.value,
      label: `${c.value} ${c.pinyin} — ${c.count}`,
    }));
  }
  if (phen === 'case') {
    return CASE_ORDER.map((code) => ({ value: code, label: CASES[code].label }));
  }
  return [];
}

export function FilterBar({ data, params, onChange }: Props) {
  const options = subOptions(data, params.phen);
  const count = activeFilterCount(params);
  const subLabel =
    params.phen === 'case' ? 'Падеж' : params.phen === 'classifier' ? '量词' : 'Артикль';

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Pill label="Явление" active={params.phen !== ''}>
        <select
          className={selectClass}
          value={params.phen}
          onChange={(e) => {
            onChange({ phen: e.target.value as Phenomenon | '', sub: '', number: '' });
          }}
        >
          <option value="">все</option>
          {(Object.keys(PHENOMENA) as Phenomenon[]).map((p) => (
            <option key={p} value={p}>
              {PHENOMENA[p].label}
            </option>
          ))}
        </select>
      </Pill>

      {params.phen && (
        <Pill label={subLabel} active={params.sub !== ''}>
          <select
            className={cx(selectClass, params.phen === 'classifier' && 'font-zh')}
            value={params.sub}
            onChange={(e) => {
              onChange({ sub: e.target.value });
            }}
          >
            <option value="">все</option>
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Pill>
      )}

      {params.phen === 'case' && (
        <Pill label="Число" active={params.number !== ''}>
          <select
            className={selectClass}
            value={params.number}
            onChange={(e) => {
              onChange({ number: e.target.value as NumberCode | '' });
            }}
          >
            <option value="">любое</option>
            {(['sing', 'plur'] as const).map((n) => (
              <option key={n} value={n}>
                {NUMBERS[n].label}
              </option>
            ))}
          </select>
        </Pill>
      )}

      <Pill label="Текст" active={params.text !== ''}>
        <select
          className={selectClass}
          value={params.text}
          onChange={(e) => {
            onChange({ text: e.target.value });
          }}
        >
          <option value="">все</option>
          {data.corpus.texts.map((t) => (
            <option key={t.id} value={t.id}>
              {t.title_ru || t.title} ({t.level})
            </option>
          ))}
        </select>
      </Pill>

      <Pill label="Уровень" active={params.level !== ''}>
        <select
          className={selectClass}
          value={params.level}
          onChange={(e) => {
            onChange({ level: e.target.value as Level | '' });
          }}
        >
          <option value="">все</option>
          {LEVELS.filter((l) => data.stats.levels[l]).map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </Pill>

      <Pill label="Статус" active={params.status !== ''}>
        <select
          className={selectClass}
          value={params.status}
          onChange={(e) => {
            onChange({ status: e.target.value as Status | '' });
          }}
        >
          <option value="">любой</option>
          {(Object.keys(STATUSES) as Status[]).map((s) => (
            <option key={s} value={s}>
              {STATUSES[s].label}
            </option>
          ))}
        </select>
      </Pill>

      <details className="group relative">
        <summary
          className={cx(
            'inline-flex cursor-pointer list-none items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13.5px] transition select-none [&::-webkit-details-marker]:hidden',
            params.minScore > 0 || params.maxScore < 1 || params.disputed || params.llm
              ? 'border-ink/50 bg-surface text-ink'
              : 'border-rule-strong bg-surface text-muted hover:border-ink/30',
          )}
        >
          Score {formatScore(params.minScore)}–{formatScore(params.maxScore)}
          {(params.disputed || params.llm) && ' · ещё'}
          <span aria-hidden="true" className="transition group-open:rotate-180">
            ▾
          </span>
        </summary>
        <div className="absolute left-0 z-30 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-rule bg-surface p-4 shadow-soft">
          <fieldset>
            <legend className="text-sm font-semibold">Оценка выравнивания (alignment_score)</legend>
            <p className="mt-1 text-xs text-muted">
              0 — плохое соответствие, 1 — отличное. Порог «низкой» оценки для метода{' '}
              {data.corpus.alignment_method}: {formatScore(data.corpus.low_score_threshold)}.
            </p>
            {(['minScore', 'maxScore'] as const).map((key) => (
              <label
                key={key}
                className="mt-3 grid grid-cols-[2.5rem_1fr_3rem] items-center gap-2 text-sm"
              >
                <span className="text-muted">{key === 'minScore' ? 'от' : 'до'}</span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={params[key]}
                  onChange={(e) => {
                    const value = Number(e.target.value);
                    onChange(
                      key === 'minScore'
                        ? { minScore: Math.min(value, params.maxScore) }
                        : { maxScore: Math.max(value, params.minScore) },
                    );
                  }}
                />
                <span className="text-right font-mono tabular-nums">
                  {formatScore(params[key])}
                </span>
              </label>
            ))}
          </fieldset>
          <div className="mt-4 grid gap-2 border-t border-rule pt-3 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={params.disputed}
                onChange={(e) => {
                  onChange({ disputed: e.target.checked });
                }}
              />
              Только спорная разметка
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={params.llm}
                onChange={(e) => {
                  onChange({ llm: e.target.checked });
                }}
              />
              Только с комментарием LLM
            </label>
          </div>
        </div>
      </details>

      {count > 0 && (
        <button
          type="button"
          className="rounded-full px-3 py-1.5 text-[13.5px] text-muted underline decoration-rule-strong underline-offset-4 hover:text-ink"
          onClick={() => {
            onChange({
              phen: DEFAULT_PARAMS.phen,
              sub: '',
              number: '',
              text: '',
              level: '',
              status: '',
              minScore: 0,
              maxScore: 1,
              disputed: false,
              llm: false,
            });
          }}
        >
          Сбросить фильтры ({count})
        </button>
      )}
    </div>
  );
}
