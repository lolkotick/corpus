import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { TaskCard } from '../components/exercises/TaskCard';
import { TaskSentence } from '../components/exercises/TaskSentence';
import { ArrowRightIcon, PrinterIcon } from '../components/icons';
import { LangBadge, PageHeader } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import type { Level } from '../data/types';
import {
  availableCount,
  buildExerciseSet,
  checkAnswer,
  COUNTS,
  DEFAULT_SETTINGS,
  KIND_LABELS,
  levelLabel,
  newSeed,
  printSearch,
  resolveItems,
  type ExerciseItem,
  type ExerciseKind,
  type ExerciseSettings,
} from '../lib/exercises';
import { LEVELS, plural } from '../lib/labels';
import {
  accuracyByKind,
  appendHistory,
  clearHistory,
  loadHistory,
  loadSession,
  saveSession,
  type HistoryEntry,
  type SessionState,
} from '../lib/progress';
import { buttonClasses, cx } from '../lib/styles';

const KINDS: ExerciseKind[] = ['article', 'classifier', 'case', 'mixed'];

function percent(correct: number, total: number): string {
  return total === 0 ? '—' : `${Math.round((100 * correct) / total)} %`;
}

/* ─── Настройки ─────────────────────────────────────────────────────────── */

function Setup({
  data,
  settings,
  onSettings,
  onStart,
  onPrint,
  resumable,
  onResume,
  history,
  onClearHistory,
}: {
  data: CorpusIndex;
  settings: ExerciseSettings;
  onSettings: (s: ExerciseSettings) => void;
  onStart: () => void;
  onPrint: () => void;
  resumable: SessionState | null;
  onResume: () => void;
  history: HistoryEntry[];
  onClearHistory: () => void;
}) {
  const available = useMemo(
    () =>
      Object.fromEntries(
        KINDS.map((kind) => [kind, availableCount(data.corpus, { kind, level: settings.level })]),
      ) as Record<ExerciseKind, number>,
    [data.corpus, settings.level],
  );
  const max = available[settings.kind];
  const count = Math.min(settings.count, max);
  const levels = LEVELS.filter((l) => data.stats.levels[l]);
  const accuracy = accuracyByKind(history);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <form
        className="rounded-2xl border border-rule bg-surface p-6 sm:p-8"
        onSubmit={(e) => {
          e.preventDefault();
          onStart();
        }}
      >
        <fieldset>
          <legend className="text-lg font-semibold">Что тренируем</legend>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {KINDS.map((kind) => {
              const info = KIND_LABELS[kind];
              const checked = settings.kind === kind;
              return (
                <label
                  key={kind}
                  className={cx(
                    'flex cursor-pointer gap-3 rounded-xl border p-4 transition focus-within:ring-2 focus-within:ring-en/40',
                    checked ? 'border-ink/60 bg-paper' : 'border-rule hover:border-ink/30',
                  )}
                >
                  <input
                    type="radio"
                    name="kind"
                    value={kind}
                    checked={checked}
                    onChange={() => {
                      onSettings({ ...settings, kind });
                    }}
                    className="mt-1"
                  />
                  <span>
                    <span className="flex items-center gap-2 font-semibold">
                      {info.lang ? <LangBadge lang={info.lang} /> : null}
                      {info.title}
                    </span>
                    <span className="mt-1 block text-sm text-muted">{info.task}</span>
                    <span className="mt-1 block text-xs text-muted">
                      доступно: {available[kind]}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-semibold">Уровень текстов</span>
            <select
              className="mt-2 block w-full rounded-lg border border-rule-strong bg-paper px-3 py-2"
              value={settings.level}
              onChange={(e) => {
                onSettings({ ...settings, level: e.target.value as Level | '' });
              }}
            >
              <option value="">все уровни</option>
              {levels.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend className="text-sm font-semibold">Число заданий</legend>
            <div className="mt-2 inline-flex rounded-lg bg-sunken p-1" role="group">
              {COUNTS.map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-pressed={settings.count === n}
                  disabled={n > max && COUNTS.some((c) => c < n)}
                  onClick={() => {
                    onSettings({ ...settings, count: n });
                  }}
                  className={cx(
                    'rounded-md px-4 py-1.5 text-sm transition disabled:opacity-40',
                    settings.count === n ? 'bg-surface font-semibold shadow-sm' : 'text-muted',
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
          </fieldset>
        </div>

        {max === 0 ? (
          <p className="mt-6 text-danger">Для этого уровня нет подходящих предложений.</p>
        ) : (
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <button type="submit" className={buttonClasses.primary}>
              Начать: {count} {plural(count, 'задание', 'задания', 'заданий')}{' '}
              <ArrowRightIcon size={18} />
            </button>
            <button type="button" className={buttonClasses.ghost} onClick={onPrint}>
              <PrinterIcon size={18} /> Версия для печати
            </button>
          </div>
        )}
        <p className="mt-4 text-sm text-muted">
          Каждое задание — настоящее предложение корпуса. Подсказка — параллельные предложения на
          двух других языках. Прогресс сохраняется в этом браузере.
        </p>
      </form>

      <aside className="space-y-4">
        {resumable && !resumable.finished && (
          <div className="rounded-2xl border border-en/40 bg-en-tint p-5">
            <p className="font-semibold">Незавершённый набор</p>
            <p className="mt-1 text-sm text-muted">
              {KIND_LABELS[resumable.settings.kind].title}, {levelLabel(resumable.settings.level)}:{' '}
              выполнено {Object.keys(resumable.answers).length} из {resumable.itemIds.length}.
            </p>
            <button
              type="button"
              className={cx(buttonClasses.primary, 'mt-3 w-full')}
              onClick={onResume}
            >
              Продолжить
            </button>
          </div>
        )}
        <div className="rounded-2xl border border-rule bg-surface p-5">
          <h2 className="font-semibold">Ваши результаты</h2>
          {history.length === 0 ? (
            <p className="mt-2 text-sm text-muted">Пока нет завершённых наборов.</p>
          ) : (
            <>
              <dl className="mt-3 space-y-1.5 text-sm">
                {KINDS.filter((k) => accuracy[k].total > 0).map((k) => (
                  <div key={k} className="flex justify-between gap-2">
                    <dt className="text-muted">{KIND_LABELS[k].title}</dt>
                    <dd className="font-semibold tabular-nums">
                      {percent(accuracy[k].correct, accuracy[k].total)}{' '}
                      <span className="font-normal text-muted">
                        ({accuracy[k].correct}/{accuracy[k].total})
                      </span>
                    </dd>
                  </div>
                ))}
              </dl>
              <h3 className="mt-4 text-xs font-semibold tracking-wide text-muted uppercase">
                Последние наборы
              </h3>
              <ul className="mt-2 space-y-1 text-sm">
                {history.slice(0, 5).map((h) => (
                  <li key={h.date} className="flex justify-between gap-2">
                    <span className="truncate text-muted">
                      {new Date(h.date).toLocaleDateString('ru-RU')} · {KIND_LABELS[h.kind].title}
                    </span>
                    <span className="tabular-nums">
                      {h.correct}/{h.total}
                    </span>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="mt-3 text-xs text-muted underline underline-offset-4 hover:text-ink"
                onClick={onClearHistory}
              >
                Очистить историю
              </button>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

/* ─── Итоги ─────────────────────────────────────────────────────────────── */

function Summary({
  items,
  session,
  onRetryMistakes,
  onNew,
  onPrint,
}: {
  items: ExerciseItem[];
  session: SessionState;
  onRetryMistakes: () => void;
  onNew: () => void;
  onPrint: () => void;
}) {
  const correct = items.filter((i) => session.answers[i.id]?.correct).length;
  const ratio = items.length ? correct / items.length : 0;
  const message =
    ratio === 1
      ? 'Отлично — без ошибок!'
      : ratio >= 0.8
        ? 'Хороший результат.'
        : ratio >= 0.5
          ? 'Неплохо, но стоит повторить ошибки.'
          : 'Попробуйте ещё раз — с подсказками будет проще.';
  const mistakes = items.filter((i) => !session.answers[i.id]?.correct);

  return (
    <section aria-labelledby="summary-title" className="animate-fade-up">
      <div className="rounded-2xl border border-rule bg-surface p-6 sm:p-8">
        <h2 id="summary-title" className="text-sm font-medium text-muted">
          Итоги · {KIND_LABELS[session.settings.kind].title}, {levelLabel(session.settings.level)}
        </h2>
        <p className="mt-3 text-[56px] leading-none font-semibold">
          {correct} <span className="text-muted">из {items.length}</span>
        </p>
        <p className="mt-2 text-lg">
          {percent(correct, items.length)} · {message}
        </p>
        <div
          className="mt-4 h-2 overflow-hidden rounded-full bg-sunken"
          role="img"
          aria-label={`Верно ${percent(correct, items.length)}`}
        >
          <div
            className="h-full rounded-full bg-ru"
            style={{ width: `${Math.round(ratio * 100)}%` }}
          />
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          {mistakes.length > 0 && (
            <button type="button" className={buttonClasses.primary} onClick={onRetryMistakes}>
              Повторить ошибки ({mistakes.length})
            </button>
          )}
          <button type="button" className={buttonClasses.ghost} onClick={onNew}>
            Новый набор
          </button>
          <button type="button" className={buttonClasses.ghost} onClick={onPrint}>
            <PrinterIcon size={18} /> Версия для печати
          </button>
        </div>
      </div>

      <ol className="mt-6 space-y-3">
        {items.map((item, i) => {
          const answer = session.answers[item.id];
          return (
            <li
              key={item.id}
              className={cx(
                'rounded-xl border bg-surface p-4',
                answer?.correct ? 'border-rule' : 'border-danger/40',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="font-mono text-xs text-muted">{i + 1}</span>
                <TaskSentence
                  item={item}
                  className="flex-1 !text-[17px]"
                  blank={
                    <b
                      className={cx(
                        'rounded px-1',
                        answer?.correct ? 'bg-ru-tint text-ru' : 'bg-en-tint text-en',
                      )}
                    >
                      {item.answer}
                    </b>
                  }
                />
                <Link
                  to={`/pair/${item.pairId}`}
                  className="shrink-0 text-xs text-muted underline underline-offset-4 hover:text-ink"
                >
                  пара
                </Link>
              </div>
              {!answer?.correct && (
                <p className="mt-2 pl-6 text-sm text-danger">
                  Ваш ответ: {answer && answer.value !== '' ? answer.value : '—'}
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/* ─── Страница ──────────────────────────────────────────────────────────── */

function ExercisesContent({ data }: { data: CorpusIndex }) {
  const navigate = useNavigate();
  const [session, setSession] = useState<SessionState | null>(loadSession);
  const [running, setRunning] = useState(false);
  const [settings, setSettings] = useState<ExerciseSettings>(
    () => loadSession()?.settings ?? DEFAULT_SETTINGS,
  );
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory);

  const items = useMemo(
    () => (session ? resolveItems(data.corpus, session.seed, session.itemIds) : []),
    [data.corpus, session],
  );

  useEffect(() => {
    saveSession(session);
  }, [session]);

  const start = useCallback(
    (next: ExerciseSettings, seed: number, ids?: string[]) => {
      const chosen = ids ?? buildExerciseSet(data.corpus, next, seed).map((i) => i.id);
      setSession({
        settings: next,
        seed,
        itemIds: chosen,
        answers: {},
        index: 0,
        startedAt: new Date().toISOString(),
        finished: false,
      });
      setRunning(true);
    },
    [data.corpus],
  );

  const answer = useCallback(
    (value: string) => {
      setSession((s) => {
        const item = s ? items[s.index] : undefined;
        if (!s || !item || s.answers[item.id]) return s;
        return {
          ...s,
          answers: { ...s.answers, [item.id]: { value, correct: checkAnswer(item, value) } },
        };
      });
    },
    [items],
  );

  const next = useCallback(() => {
    if (!session) return;
    if (session.index + 1 < items.length) {
      setSession({ ...session, index: session.index + 1 });
      return;
    }
    const correct = items.filter((i) => session.answers[i.id]?.correct).length;
    setHistory(
      appendHistory({
        date: new Date().toISOString(),
        kind: session.settings.kind,
        level: session.settings.level,
        total: items.length,
        correct,
      }),
    );
    setSession({ ...session, finished: true });
  }, [items, session]);

  const print = (current: ExerciseSettings, seed: number, ids?: string[]) => {
    void navigate(`/exercises/print?${printSearch(current, seed, ids)}`);
  };

  const current = session ? items[session.index] : undefined;
  const answered = session ? Object.keys(session.answers).length : 0;
  const correct = items.filter((i) => session?.answers[i.id]?.correct).length;

  return (
    <Container className="pt-10 sm:pt-14">
      <PageHeader eyebrow="Упражнения" title="Тренируйте три грамматики на живых примерах">
        Артикли в английском, счётные слова в китайском, падежи в русском — задания собираются из
        предложений корпуса, а параллельный перевод служит подсказкой.
      </PageHeader>

      {running && session && !session.finished && current ? (
        <div className="mx-auto max-w-3xl">
          <div className="mb-4 flex items-center gap-4 text-sm text-muted">
            <div
              className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={items.length}
              aria-valuenow={answered}
              aria-label="Выполнено заданий"
            >
              <div
                className="h-full rounded-full bg-ink transition-[width] duration-500"
                style={{ width: `${(100 * answered) / items.length}%` }}
              />
            </div>
            <span className="tabular-nums">
              верно {correct} из {answered}
            </span>
            <button
              type="button"
              className="underline underline-offset-4 hover:text-ink"
              onClick={() => {
                setRunning(false);
              }}
            >
              Прервать
            </button>
          </div>
          <TaskCard
            key={current.id}
            item={current}
            index={session.index}
            total={items.length}
            answer={session.answers[current.id]}
            onAnswer={answer}
            onNext={next}
          />
        </div>
      ) : running && session?.finished ? (
        <div className="mx-auto max-w-3xl">
          <Summary
            items={items}
            session={session}
            onRetryMistakes={() => {
              const wrong = items.filter((i) => !session.answers[i.id]?.correct).map((i) => i.id);
              start({ ...session.settings, count: wrong.length }, session.seed, wrong);
            }}
            onNew={() => {
              setRunning(false);
              setSession(null);
            }}
            onPrint={() => {
              print(session.settings, session.seed, session.itemIds);
            }}
          />
        </div>
      ) : (
        <Setup
          data={data}
          settings={settings}
          onSettings={setSettings}
          onStart={() => {
            start(settings, newSeed());
          }}
          onPrint={() => {
            print(settings, newSeed());
          }}
          resumable={session}
          onResume={() => {
            setRunning(true);
          }}
          history={history}
          onClearHistory={() => {
            clearHistory();
            setHistory([]);
          }}
        />
      )}
    </Container>
  );
}

export function ExercisesPage() {
  return <DataGate>{(data) => <ExercisesContent data={data} />}</DataGate>;
}
