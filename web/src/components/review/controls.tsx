import type { ReactNode } from 'react';

import type { Verdict } from '../../lib/gold';
import { VERDICTS } from '../../lib/gold';
import { cx } from '../../lib/styles';
import { CheckIcon } from '../icons';

const SELECTED: Record<Verdict, string> = {
  correct: 'bg-ink text-paper',
  wrong: 'bg-danger-tint text-danger ring-1 ring-danger/60 ring-inset',
  corrected: 'bg-warn-tint text-warn ring-1 ring-warn/60 ring-inset',
};

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cx(
        'inline-flex min-w-[1.4em] items-center justify-center rounded border border-rule-strong bg-sunken px-1 font-mono text-[11px] leading-[1.35] text-muted',
        className,
      )}
    >
      {children}
    </kbd>
  );
}

export interface ChoiceOption<T extends string> {
  value: T;
  label: string;
  key: string;
  tone: Verdict;
}

/** Группа кнопок-переключателей с подсказкой горячей клавиши. */
export function ChoiceButtons<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly ChoiceOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={(event) => {
              event.stopPropagation();
              onChange(option.value);
            }}
            className={cx(
              'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13.5px] font-medium transition',
              active
                ? SELECTED[option.tone]
                : 'text-muted ring-1 ring-rule-strong ring-inset hover:bg-sunken hover:text-ink',
            )}
          >
            {active && option.tone === 'correct' ? (
              <CheckIcon size={14} />
            ) : (
              <Kbd className={active ? 'border-current/30 bg-transparent text-current' : ''}>
                {option.key}
              </Kbd>
            )}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

const VERDICT_OPTIONS: readonly ChoiceOption<Verdict>[] = (
  ['correct', 'wrong', 'corrected'] as const
).map((v) => ({ value: v, label: VERDICTS[v].label, key: VERDICTS[v].key, tone: v }));

export function VerdictButtons({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Verdict | null;
  onChange: (value: Verdict) => void;
}) {
  return (
    <ChoiceButtons label={label} options={VERDICT_OPTIONS} value={value} onChange={onChange} />
  );
}

/** Строка проверки: курсор клавиатуры подсвечивает текущую строку. */
export function ReviewRow({
  rowId,
  focused,
  done,
  onFocus,
  children,
  className,
}: {
  rowId: string;
  focused: boolean;
  done: boolean;
  onFocus: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    // Клик по строке только переносит на неё курсор; сами действия — кнопками внутри.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div
      data-row={rowId}
      onClick={onFocus}
      aria-current={focused ? 'true' : undefined}
      className={cx(
        'relative rounded-xl py-2.5 pr-3 pl-7 transition',
        focused ? 'bg-surface shadow-soft ring-2 ring-ink/25' : 'hover:bg-surface/70',
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cx(
          'absolute top-[1.15rem] left-2.5 size-2 rounded-full',
          done ? 'bg-ink/70' : 'ring-1 ring-rule-strong',
        )}
      />
      <span className="sr-only">{done ? 'оценено. ' : 'не оценено. '}</span>
      {children}
    </div>
  );
}
