import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';

import type { CaseCode, Lang } from '../../data/types';
import { defaultMissedFix, spanText, tokenize, type Fix, type GoldSpan } from '../../lib/gold';
import { CASE_ORDER, CASES, LANG_INFO } from '../../lib/labels';
import { buttonClasses, cx, LANG_CLASSES } from '../../lib/styles';

const FIELD =
  'w-full rounded-lg border border-rule-strong bg-surface px-2.5 py-1.5 text-[14.5px] outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-ink/20';

function isCase(value: string): value is CaseCode {
  return (CASE_ORDER as readonly string[]).includes(value);
}

/**
 * Поля правильного варианта. Enter в поле — готово (курсор идёт дальше), Esc — выйти из поля.
 */
export function FixForm({
  lang,
  fix,
  onChange,
  onDone,
  focusFirst = false,
  showClassifier = true,
}: {
  lang: Lang;
  fix: Fix;
  onChange: (fix: Fix) => void;
  onDone?: () => void;
  focusFirst?: boolean;
  showClassifier?: boolean;
}) {
  const id = useId();
  const firstRef = useRef<HTMLInputElement & HTMLSelectElement>(null);

  useEffect(() => {
    if (focusFirst) firstRef.current?.focus();
  }, [focusFirst]);

  function onKey(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Enter') {
      event.preventDefault();
      (event.target as HTMLElement).blur();
      onDone?.();
    } else if (event.key === 'Escape') {
      (event.target as HTMLElement).blur();
    }
  }

  if (lang === 'ru') {
    return (
      <div className="grid gap-2 sm:grid-cols-[12rem_1fr]">
        <label className="grid gap-1 text-[13px] text-muted">
          Падеж
          <select
            ref={firstRef}
            className={FIELD}
            value={fix.case ?? 'nomn'}
            onKeyDown={onKey}
            onChange={(event) => {
              const value = event.target.value;
              if (isCase(value)) onChange({ ...fix, case: value });
            }}
          >
            {CASE_ORDER.map((c) => (
              <option key={c} value={c}>
                {CASES[c].label} ({CASES[c].question})
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-[13px] text-muted">
          Начальная форма (лемма)
          <input
            className={FIELD}
            lang="ru"
            value={fix.lemma ?? ''}
            onKeyDown={onKey}
            onChange={(event) => onChange({ ...fix, lemma: event.target.value })}
          />
        </label>
      </div>
    );
  }

  const headLabel = lang === 'en' ? 'Существительное-вершина' : 'Существительное при 量词';
  return (
    <div className={cx('grid gap-2', lang === 'zh' && showClassifier && 'sm:grid-cols-[8rem_1fr]')}>
      {lang === 'zh' && showClassifier && (
        <label className="grid gap-1 text-[13px] text-muted" htmlFor={`${id}-cl`}>
          <span>
            Счётное слово <span lang="zh-Hans">量词</span>
          </span>
          <input
            id={`${id}-cl`}
            ref={firstRef}
            className={FIELD}
            lang="zh-Hans"
            value={fix.classifier ?? ''}
            onKeyDown={onKey}
            onChange={(event) => onChange({ ...fix, classifier: event.target.value })}
          />
        </label>
      )}
      <label className="grid gap-1 text-[13px] text-muted">
        <span>
          {headLabel}
          <span className="ml-1 text-xs">(пусто — существительного нет)</span>
        </span>
        <input
          ref={lang === 'zh' && showClassifier ? undefined : firstRef}
          className={FIELD}
          lang={LANG_INFO[lang].htmlLang}
          value={fix.head ?? ''}
          onKeyDown={onKey}
          onChange={(event) => onChange({ ...fix, head: event.target.value })}
        />
      </label>
    </div>
  );
}

/**
 * Отметка пропуска: щелчок по слову (EN/RU) или иероглифу (ZH) выбирает начало,
 * щелчок с Shift расширяет выделение. Слова, уже размеченные автоматически, недоступны.
 */
export function MissedPicker({
  text,
  lang,
  taken,
  onAdd,
  onCancel,
}: {
  text: string;
  lang: Lang;
  taken: readonly GoldSpan[];
  onAdd: (item: GoldSpan & Fix) => void;
  onCancel: () => void;
}) {
  const tokens = tokenize(text, lang);
  const [range, setRange] = useState<{ start: number; end: number } | null>(null);
  const [fix, setFix] = useState<Fix>({});
  const c = LANG_CLASSES[lang];
  const chars = Array.from(text);

  const isTaken = (t: GoldSpan) => taken.some((s) => t.start < s.end && s.start < t.end);

  function pick(token: GoldSpan, extend: boolean) {
    const next =
      extend && range
        ? { start: Math.min(range.start, token.start), end: Math.max(range.end, token.end) }
        : { start: token.start, end: token.end };
    setRange(next);
    setFix(defaultMissedFix(lang, { ...next, text: spanText(text, next.start, next.end) }));
  }

  // Текст между токенами выводится как есть, чтобы предложение читалось целиком.
  const parts: { token?: GoldSpan; text: string; key: number }[] = [];
  let pos = 0;
  for (const token of tokens) {
    if (token.start > pos) parts.push({ text: chars.slice(pos, token.start).join(''), key: pos });
    parts.push({ token, text: token.text, key: token.start });
    pos = token.end;
  }
  if (pos < chars.length) parts.push({ text: chars.slice(pos).join(''), key: pos });

  const selected = range ? { ...range, text: spanText(text, range.start, range.end) } : null;
  return (
    <div className="mt-2 rounded-xl border border-rule bg-paper p-3">
      <p className="text-[13px] text-muted">
        Выберите {lang === 'zh' ? 'иероглиф' : 'слово'}, которое автоматика пропустила
        {lang === 'zh' ? ' (Shift + щелчок — несколько иероглифов)' : ''}.
      </p>
      <p
        lang={LANG_INFO[lang].htmlLang}
        className={cx('mt-2 leading-9', lang === 'zh' ? 'font-zh text-[19px]' : 'text-[17px]')}
      >
        {parts.map((part) => {
          const token = part.token;
          if (!token) return <span key={`t${String(part.key)}`}>{part.text}</span>;
          const off = isTaken(token);
          const on = !!range && token.start >= range.start && token.end <= range.end;
          return (
            <button
              key={`b${String(part.key)}`}
              type="button"
              disabled={off}
              aria-pressed={on}
              title={off ? 'уже размечено автоматически' : undefined}
              onClick={(event) => {
                event.stopPropagation();
                pick(token, event.shiftKey);
              }}
              className={cx(
                'rounded px-0.5 transition',
                on
                  ? cx(c.bg, 'text-paper')
                  : off
                    ? 'cursor-not-allowed opacity-45'
                    : 'hover:bg-sunken',
                !on &&
                  !off &&
                  'underline decoration-rule-strong decoration-dotted underline-offset-4',
              )}
            >
              {part.text}
            </button>
          );
        })}
      </p>
      {selected && (
        <div className="mt-3 grid gap-3">
          <p className="text-[14px]">
            Выбрано:{' '}
            <b lang={LANG_INFO[lang].htmlLang} className={c.text}>
              {selected.text}
            </b>
          </p>
          <FixForm lang={lang} fix={fix} onChange={setFix} showClassifier={false} focusFirst />
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!selected}
          className={cx(buttonClasses.primary, 'px-4 py-2 text-sm')}
          onClick={(event) => {
            event.stopPropagation();
            if (selected) onAdd({ ...selected, ...fix });
          }}
        >
          Добавить пропуск
        </button>
        <button
          type="button"
          className={buttonClasses.subtle}
          onClick={(event) => {
            event.stopPropagation();
            onCancel();
          }}
        >
          Отмена
        </button>
      </div>
    </div>
  );
}
