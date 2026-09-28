import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { AlertIcon, ArrowRightIcon, DownloadIcon } from '../components/icons';
import { Kbd } from '../components/review/controls';
import { TaskSentence } from '../components/exercises/TaskSentence';
import { LangBadge, PageHeader } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import type { Phenomenon } from '../data/types';
import { KIND_LABELS } from '../lib/exercises';
import { formatDate, PHENOMENA, plural } from '../lib/labels';
import { buttonClasses, cx } from '../lib/styles';
import {
  attemptScore,
  attemptsToCsv,
  buildTestSets,
  csvFileName,
  loadStore,
  newAttempt,
  recordAnswer,
  saveStore,
  setProfile,
  STAGES,
  type TestAttempt,
  type TestItem,
  type TestSet,
  type TestStage,
  type TestStore,
} from '../lib/testMode';

const KINDS: readonly Phenomenon[] = ['article', 'classifier', 'case'];
const FIELD =
  'w-full rounded-[10px] border border-rule-strong bg-surface px-3 py-2.5 text-[15px] outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-ink/20';

function nowIso(): string {
  return new Date().toISOString();
}

function downloadCsv(attempts: readonly TestAttempt[]): void {
  const blob = new Blob([attemptsToCsv(attempts)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = csvFileName(attempts, nowIso());
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function percent(correct: number, total: number): string {
  return total ? `${String(Math.round((100 * correct) / total))} %` : '—';
}

function StorageNote() {
  return (
    <p className="flex gap-2.5 rounded-xl border border-warn/40 bg-warn-tint p-3.5 text-[14px] text-ink">
      <AlertIcon size={17} className="mt-0.5 shrink-0 text-warn" />
      <span>
        Результаты хранятся <b>только в этом браузере</b> на этом устройстве и никуда не
        отправляются. После теста нажмите «Экспорт результатов (CSV)» и передайте файл
        преподавателю. Очистка данных браузера удалит неэкспортированные результаты.
      </span>
    </p>
  );
}

/* ─── Начало ───────────────────────────────────────────────────────────── */

function StartPanel({
  sets,
  store,
  onStart,
  onExport,
  onDelete,
}: {
  sets: Record<'A' | 'B', TestSet>;
  store: TestStore;
  onStart: (participant: string, stage: TestStage) => void;
  onExport: (attempts: TestAttempt[]) => void;
  onDelete: () => void;
}) {
  const [participant, setParticipant] = useState('');
  const [stage, setStage] = useState<TestStage>('pre');
  const finished = store.attempts.filter((a) => a.finished_at);
  const profiles = { A: setProfile(sets.A), B: setProfile(sets.B) };
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
      <form
        className="grid content-start gap-4 rounded-2xl border border-rule bg-surface p-5 sm:p-7"
        onSubmit={(event) => {
          event.preventDefault();
          if (participant.trim()) onStart(participant, stage);
        }}
      >
        <h2 className="font-serif text-[24px] font-semibold">Начать тест</h2>
        <label className="grid gap-1.5 text-sm font-medium">
          Имя или код участника
          <input
            className={FIELD}
            value={participant}
            required
            maxLength={60}
            onChange={(e) => setParticipant(e.target.value)}
            placeholder="например, S07"
          />
          <span className="text-xs font-normal text-muted">
            Для предтеста и посттеста указывайте один и тот же код.
          </span>
        </label>
        <fieldset className="grid gap-2">
          <legend className="mb-1.5 text-sm font-medium">Этап</legend>
          {(['pre', 'post'] as const).map((s) => (
            <label
              key={s}
              className={cx(
                'flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 transition',
                stage === s ? 'border-ink bg-paper' : 'border-rule hover:border-rule-strong',
              )}
            >
              <input
                type="radio"
                name="stage"
                value={s}
                checked={stage === s}
                onChange={() => setStage(s)}
                className="mt-1 accent-current"
              />
              <span>
                <b className="font-semibold">
                  {STAGES[s].label} — набор {STAGES[s].set}
                </b>
                <span className="block text-[13.5px] text-muted">
                  {STAGES[s].hint}; {sets[STAGES[s].set].items.length} заданий
                </span>
              </span>
            </label>
          ))}
        </fieldset>
        <button
          type="submit"
          disabled={!participant.trim()}
          className={cx(buttonClasses.primary, 'justify-self-start')}
        >
          Начать {STAGES[stage].label.toLowerCase()} <ArrowRightIcon size={16} />
        </button>
        <StorageNote />
      </form>

      <div className="grid content-start gap-5">
        <section className="rounded-2xl border border-rule bg-surface p-5 sm:p-6">
          <h2 className="text-[15px] font-semibold">Как устроен тест</h2>
          <ul className="mt-2 grid gap-1.5 text-[14.5px] text-muted">
            <li>
              Два параллельных набора по {sets.A.items.length} заданий: по 5 на артикли, 量词 и
              падежи. Задания те же, что в упражнениях, но без подсказок и без показа ответа.
            </li>
            <li>
              Наборы подобраны одинаковой сложности (средний уровень текстов:{' '}
              {profiles.A.meanLevel.toFixed(1).replace('.', ',')} и{' '}
              {profiles.B.meanLevel.toFixed(1).replace('.', ',')}) и не повторяют предложений друг
              друга.
            </li>
            <li>
              Записываются ответы, время на каждое задание и ошибки по явлениям. Результаты
              обрабатывает <code className="text-[13px]">pipeline/approbation.py</code>.
            </li>
          </ul>
          <p className="mt-3 text-xs text-muted">
            Наборы: {sets.A.id}, {sets.B.id} (код меняется, если корпус пересобран).
          </p>
        </section>

        <section className="rounded-2xl border border-rule bg-surface p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[15px] font-semibold">Результаты в этом браузере</h2>
            {finished.length > 0 && (
              <button
                type="button"
                className={cx(buttonClasses.ghost, 'px-4 py-2 text-sm')}
                onClick={() => onExport(finished)}
              >
                <DownloadIcon size={15} /> Экспорт результатов (CSV)
              </button>
            )}
          </div>
          {finished.length === 0 ? (
            <p className="mt-2 text-[14px] text-muted">Пока нет завершённых попыток.</p>
          ) : (
            <>
              <table className="mt-3 w-full text-[14px]">
                <caption className="sr-only">Завершённые попытки</caption>
                <thead className="border-b border-rule text-left text-xs text-muted">
                  <tr>
                    <th scope="col" className="py-1.5 font-medium">
                      Участник
                    </th>
                    <th scope="col" className="py-1.5 font-medium">
                      Этап
                    </th>
                    <th scope="col" className="py-1.5 font-medium">
                      Дата
                    </th>
                    <th scope="col" className="py-1.5 text-right font-medium">
                      Результат
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {finished.map((a) => {
                    const s = attemptScore(a);
                    return (
                      <tr key={a.id}>
                        <td className="py-1.5">{a.participant}</td>
                        <td className="py-1.5">{STAGES[a.stage].label}</td>
                        <td className="py-1.5 text-muted">{formatDate(a.started_at)}</td>
                        <td className="py-1.5 text-right tabular-nums">
                          {s.correct}/{s.total} ({percent(s.correct, s.total)})
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <button
                type="button"
                className="mt-3 text-[13px] text-muted underline underline-offset-4 hover:text-danger"
                onClick={onDelete}
              >
                Удалить результаты из браузера…
              </button>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

/* ─── Задание ──────────────────────────────────────────────────────────── */

function TestTask({
  item,
  index,
  total,
  onSubmit,
}: {
  item: TestItem;
  index: number;
  total: number;
  onSubmit: (value: string, ms: number) => void;
}) {
  const [value, setValue] = useState('');
  const shownAt = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const info = KIND_LABELS[item.kind];

  useEffect(() => {
    shownAt.current = performance.now();
    inputRef.current?.focus();
  }, []);

  function submit(answer: string) {
    if (!answer.trim()) return;
    onSubmit(answer, performance.now() - shownAt.current);
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.altKey || event.ctrlKey) return;
      const option = item.options[Number(event.key) - 1];
      if (option) {
        // Иначе цифра попадёт в поле ввода следующего задания, которое получит фокус.
        event.preventDefault();
        submit(option);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  return (
    <section
      aria-labelledby="test-task-title"
      className="rounded-2xl border border-rule bg-surface p-5 shadow-soft sm:p-8"
    >
      <p className="flex items-center gap-2 text-[13.5px] text-muted">
        {info.lang && <LangBadge lang={info.lang} />}
        <span id="test-task-title">
          Задание {index + 1} из {total} · {info.title}
        </span>
      </p>
      <p className="mt-2 text-[15px] text-muted">{info.task}</p>
      <TaskSentence
        item={item}
        className="mt-6"
        blank={
          item.options.length > 0 ? (
            <span className="mx-1 inline-block min-w-[3.5em] border-b-2 border-dashed border-ink/40 text-center">
              <span className="sr-only">пропуск</span>&nbsp;
            </span>
          ) : (
            <span className="mx-1 inline-block">
              <label htmlFor="test-answer" className="sr-only">
                Ответ
              </label>
              <input
                id="test-answer"
                ref={inputRef}
                lang="ru"
                autoComplete="off"
                spellCheck={false}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    submit(value);
                  }
                }}
                className="w-[8.5em] rounded-md border-b-2 border-ink/50 bg-sunken px-2 py-0.5 text-center font-serif text-[22px] outline-none focus-visible:border-ink"
              />
            </span>
          )
        }
      />
      <div className="mt-8 flex flex-wrap items-center gap-2">
        {item.options.length > 0 ? (
          <div role="group" aria-label="Варианты ответа" className="flex flex-wrap gap-2">
            {item.options.map((option, i) => (
              <button
                key={option}
                type="button"
                lang={item.lang === 'zh' ? 'zh-Hans' : 'en'}
                onClick={() => submit(option)}
                className="inline-flex min-w-[4.5rem] items-center justify-center gap-2 rounded-xl border border-rule-strong bg-paper px-4 py-2.5 text-[18px] transition hover:border-ink"
              >
                <Kbd>{i + 1}</Kbd>
                {option}
              </button>
            ))}
          </div>
        ) : (
          <button
            type="button"
            className={buttonClasses.primary}
            disabled={!value.trim()}
            onClick={() => submit(value)}
          >
            Ответить <Kbd className="border-paper/30 bg-transparent text-paper">Enter</Kbd>
          </button>
        )}
      </div>
      <p className="mt-6 text-[13px] text-muted">
        В тесте ответ не показывается и исправить его нельзя — отвечайте так, как считаете верным.
      </p>
    </section>
  );
}

/* ─── Итоги ────────────────────────────────────────────────────────────── */

function Result({
  attempt,
  onExport,
  onDone,
}: {
  attempt: TestAttempt;
  onExport: () => void;
  onDone: () => void;
}) {
  const score = attemptScore(attempt);
  return (
    <section
      aria-labelledby="test-result"
      className="rounded-2xl border border-rule bg-surface p-5 sm:p-8"
    >
      <p className="text-[13.5px] text-muted">
        {attempt.participant} · {STAGES[attempt.stage].label} (набор {STAGES[attempt.stage].set})
      </p>
      <h2 id="test-result" className="mt-1 font-serif text-[30px] font-semibold">
        Тест завершён: {score.correct} из {score.total}
      </h2>
      <p className="mt-1 text-muted">
        {percent(score.correct, score.total)} · время {Math.round(score.seconds)}{' '}
        {plural(Math.round(score.seconds), 'секунда', 'секунды', 'секунд')}
      </p>
      <dl className="mt-6 grid gap-3 sm:grid-cols-3">
        {KINDS.map((kind) => (
          <div key={kind} className="rounded-xl bg-sunken p-4">
            <dt className="text-[13.5px] text-muted">{PHENOMENA[kind].label}</dt>
            <dd className="mt-1 text-[22px] font-semibold tabular-nums">
              {score.byKind[kind].correct}/{score.byKind[kind].total}
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-6 flex flex-wrap gap-3">
        <button type="button" className={buttonClasses.primary} onClick={onExport}>
          <DownloadIcon size={16} /> Экспорт результатов (CSV)
        </button>
        <button type="button" className={buttonClasses.ghost} onClick={onDone}>
          Готово
        </button>
      </div>
      <div className="mt-6">
        <StorageNote />
      </div>
    </section>
  );
}

/* ─── Страница ─────────────────────────────────────────────────────────── */

function TestContent({ data }: { data: CorpusIndex }) {
  const sets = useMemo(() => buildTestSets(data.corpus), [data.corpus]);
  const [store, setStore] = useState<TestStore>(loadStore);
  const [finishedId, setFinishedId] = useState<string | null>(null);

  useEffect(() => {
    saveStore(store);
  }, [store]);

  const active = store.attempts.find((a) => !a.finished_at);
  const activeSet = active ? (active.stage === 'pre' ? sets.A : sets.B) : undefined;
  const setChanged = active && activeSet && active.set_id !== activeSet.id;
  const nextItem = activeSet?.items.find((i) => !active?.answers.some((a) => a.item_id === i.id));
  const finished = store.attempts.find((a) => a.id === finishedId);

  function update(attempt: TestAttempt) {
    setStore((s) => ({ attempts: s.attempts.map((a) => (a.id === attempt.id ? attempt : a)) }));
  }

  let body;
  if (finished) {
    body = (
      <Result
        attempt={finished}
        onExport={() => downloadCsv([finished])}
        onDone={() => setFinishedId(null)}
      />
    );
  } else if (active && activeSet && !setChanged && nextItem) {
    const index = activeSet.items.indexOf(nextItem);
    body = (
      <div className="mx-auto max-w-3xl">
        <div className="mb-4 flex items-center gap-4 text-sm text-muted">
          <div
            className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken"
            role="progressbar"
            aria-label="Выполнено заданий"
            aria-valuemin={0}
            aria-valuemax={activeSet.items.length}
            aria-valuenow={index}
          >
            <div
              className="h-full rounded-full bg-ink transition-[width] duration-500"
              style={{ width: `${String((100 * index) / activeSet.items.length)}%` }}
            />
          </div>
          <span>
            {active.participant} · {STAGES[active.stage].label}
          </span>
          <button
            type="button"
            className="underline underline-offset-4 hover:text-ink"
            onClick={() => {
              if (window.confirm('Прервать тест? Ответы этой попытки будут удалены.')) {
                setStore((s) => ({ attempts: s.attempts.filter((a) => a.id !== active.id) }));
              }
            }}
          >
            Прервать
          </button>
        </div>
        <TestTask
          key={nextItem.id}
          item={nextItem}
          index={index}
          total={activeSet.items.length}
          onSubmit={(value, ms) => {
            let next = recordAnswer(active, nextItem, value, ms);
            if (next.answers.length >= activeSet.items.length) {
              next = { ...next, finished_at: nowIso() };
              setFinishedId(next.id);
            }
            update(next);
          }}
        />
      </div>
    );
  } else {
    body = (
      <>
        {setChanged && (
          <p role="alert" className="mb-5 rounded-xl border border-danger/40 bg-danger-tint p-4">
            Незаконченная попытка ({active.participant}) начата на другой версии набора — корпус
            пересобран. Начните тест заново.{' '}
            <button
              type="button"
              className="underline"
              onClick={() =>
                setStore((s) => ({ attempts: s.attempts.filter((a) => a.id !== active.id) }))
              }
            >
              Удалить незаконченную попытку
            </button>
          </p>
        )}
        <StartPanel
          sets={sets}
          store={store}
          onStart={(participant, stage) => {
            const set = stage === 'pre' ? sets.A : sets.B;
            setStore((s) => ({
              attempts: [
                ...s.attempts.filter((a) => a.finished_at),
                newAttempt(participant, stage, set, nowIso()),
              ],
            }));
          }}
          onExport={downloadCsv}
          onDelete={() => {
            if (
              window.confirm(
                'Удалить все результаты теста из этого браузера? Экспортируйте CSV, если он ещё нужен.',
              )
            ) {
              setStore({ attempts: [] });
            }
          }}
        />
      </>
    );
  }

  return (
    <Container className="pt-10 sm:pt-14">
      <PageHeader eyebrow="Упражнения · апробация" title="Тест: предтест и посттест">
        <p>
          Проверка того, как меняется точность в трёх явлениях после работы с корпусом.{' '}
          <Link to="/exercises" className="underline decoration-rule-strong underline-offset-4">
            Вернуться к тренировке
          </Link>
        </p>
      </PageHeader>
      {body}
    </Container>
  );
}

export function TestPage() {
  return <DataGate>{(data) => <TestContent data={data} />}</DataGate>;
}
