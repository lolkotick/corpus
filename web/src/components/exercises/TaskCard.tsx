import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import type { ExerciseItem } from '../../lib/exercises';
import { KIND_LABELS } from '../../lib/exercises';
import { LANG_INFO } from '../../lib/labels';
import type { AnswerRecord } from '../../lib/progress';
import { buttonClasses, cx } from '../../lib/styles';
import { ArrowRightIcon, CheckIcon, CloseIcon } from '../icons';
import { LangBadge } from '../ui';
import { TaskSentence } from './TaskSentence';

interface Props {
  item: ExerciseItem;
  index: number;
  total: number;
  answer: AnswerRecord | undefined;
  onAnswer: (value: string) => void;
  onNext: () => void;
}

function Blank({ item, answer }: { item: ExerciseItem; answer: AnswerRecord | undefined }) {
  if (!answer) {
    return (
      <span className="mx-1 inline-block min-w-[3.5em] border-b-2 border-dashed border-ink/40 text-center align-baseline">
        <span className="sr-only">пропуск</span>&nbsp;
      </span>
    );
  }
  return (
    <span className="mx-1 inline-flex items-baseline gap-1">
      {!answer.correct && (
        <s className="rounded bg-danger-tint px-1 text-danger decoration-2">
          <span className="sr-only">ваш ответ: </span>
          {answer.value || '—'}
        </s>
      )}
      <b
        className={cx(
          'rounded px-1 font-semibold',
          answer.correct ? 'bg-ru-tint text-ru' : 'bg-en-tint text-en',
        )}
      >
        {item.answer}
      </b>
    </span>
  );
}

export function TaskCard({ item, index, total, answer, onAnswer, onNext }: Props) {
  const [value, setValue] = useState('');
  const [showHint, setShowHint] = useState(false);
  const nextRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const info = KIND_LABELS[item.kind];

  // После ответа фокус переходит на «Далее», перед новым заданием — на поле ввода.
  useEffect(() => {
    if (answer) nextRef.current?.focus();
    else inputRef.current?.focus();
  }, [answer]);

  // Горячие клавиши: 1–4 — варианты ответа, Enter — следующее задание.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (
        event.target instanceof HTMLInputElement ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey
      ) {
        return;
      }
      if (!answer && item.options.length > 0) {
        const option = item.options[Number(event.key) - 1];
        if (option) onAnswer(option);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [answer, item, onAnswer]);

  return (
    <article
      aria-labelledby="task-title"
      className="animate-fade-up rounded-2xl border border-rule bg-surface p-6 shadow-soft sm:p-8"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="task-title" className="flex items-center gap-2 text-sm font-medium text-muted">
          <LangBadge lang={item.lang} />
          Задание {index + 1} из {total} · {info.task}
        </h2>
        <span className="font-mono text-xs text-muted">{item.level}</span>
      </header>

      <div className="mt-6">
        <TaskSentence
          item={item}
          blank={
            item.kind === 'case' && !answer ? (
              <input
                ref={inputRef}
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key !== 'Enter') return;
                  // Иначе то же нажатие Enter «нажмёт» появившуюся кнопку «Далее».
                  e.preventDefault();
                  if (value.trim()) onAnswer(value);
                }}
                aria-label={`Форма слова «${item.lemma ?? ''}»`}
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                className="mx-1 inline-block w-[7.5em] rounded-md border-b-2 border-ink/50 bg-sunken px-2 py-0 font-serif text-[20px] outline-none focus:border-en"
              />
            ) : (
              <Blank item={item} answer={answer} />
            )
          }
        />
      </div>

      {!answer && item.options.length > 0 && (
        <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label="Варианты ответа">
          {item.options.map((option, i) => (
            <button
              key={option}
              type="button"
              onClick={() => {
                onAnswer(option);
              }}
              lang={LANG_INFO[item.lang].htmlLang}
              className={cx(
                'group inline-flex min-w-[4.5rem] items-center justify-center gap-2 rounded-xl border border-rule-strong bg-paper px-4 py-2.5 text-lg transition hover:-translate-y-0.5 hover:border-ink/50 hover:shadow-soft',
                item.lang === 'zh' ? 'text-[22px]' : 'font-serif',
              )}
            >
              <span className="font-sans text-[11px] text-muted" aria-hidden="true">
                {i + 1}
              </span>
              {option}
            </button>
          ))}
        </div>
      )}

      {!answer && item.kind === 'case' && (
        <div className="mt-6">
          <button
            type="button"
            className={buttonClasses.primary}
            disabled={!value.trim()}
            onClick={() => {
              onAnswer(value);
            }}
          >
            Проверить
          </button>
        </div>
      )}

      <div className="mt-6">
        <button
          type="button"
          className="text-sm text-muted underline decoration-rule-strong underline-offset-4 hover:text-ink"
          aria-expanded={showHint || Boolean(answer)}
          aria-controls={`hint-${item.id}`}
          onClick={() => {
            setShowHint((s) => !s);
          }}
        >
          {showHint || answer ? 'Параллельные предложения' : 'Показать подсказку (перевод)'}
        </button>
        {(showHint || answer) && (
          <ul id={`hint-${item.id}`} className="mt-3 animate-fade-in space-y-2">
            {item.hints.map((hint) => (
              <li key={hint.lang} className="flex gap-3">
                <LangBadge lang={hint.lang} className="mt-1.5 shrink-0" />
                <span
                  lang={LANG_INFO[hint.lang].htmlLang}
                  className={hint.lang === 'zh' ? 'text-[17px]' : 'font-serif text-[17px]'}
                >
                  {hint.text}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div aria-live="polite">
        {answer && (
          <div
            className={cx(
              'mt-6 animate-fade-up rounded-xl border p-4',
              answer.correct ? 'border-ru/40 bg-ru-tint' : 'border-danger/40 bg-danger-tint',
            )}
          >
            <p className="flex items-start gap-2 font-semibold">
              {answer.correct ? (
                <>
                  <CheckIcon className="mt-0.5 shrink-0 text-ru" /> <span>Верно!</span>
                </>
              ) : (
                <>
                  <CloseIcon className="mt-0.5 shrink-0 text-danger" />
                  <span>
                    Неверно. Правильный ответ:{' '}
                    <span lang={LANG_INFO[item.lang].htmlLang}>{item.answer}</span>
                  </span>
                </>
              )}
            </p>
            <p className="mt-2 text-[15px] text-ink/90">{item.explanation}</p>
            <p className="mt-2 text-sm">
              <Link
                to={`/pair/${item.pairId}`}
                className="text-muted underline underline-offset-4 hover:text-ink"
              >
                Эта пара в корпусе
              </Link>
            </p>
          </div>
        )}
      </div>

      {answer && (
        <div className="mt-6 flex justify-end">
          <button ref={nextRef} type="button" className={buttonClasses.primary} onClick={onNext}>
            {index + 1 < total ? 'Следующее задание' : 'Итоги'} <ArrowRightIcon size={18} />
          </button>
        </div>
      )}
    </article>
  );
}
