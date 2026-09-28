import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { ArrowLeftIcon, PrinterIcon } from '../components/icons';
import { EmptyState } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import {
  buildExerciseSet,
  DEFAULT_SETTINGS,
  isLevel,
  KIND_LABELS,
  levelLabel,
  resolveItems,
  type ExerciseItem,
  type ExerciseKind,
  type ExerciseSettings,
} from '../lib/exercises';
import { formatDate, LANG_INFO } from '../lib/labels';
import { buttonClasses, cx } from '../lib/styles';

const KINDS = new Set<string>(['article', 'classifier', 'case', 'mixed']);

function readSettings(sp: URLSearchParams): {
  settings: ExerciseSettings;
  seed: number;
  ids: string[];
} {
  const kind = sp.get('kind') ?? '';
  const level = sp.get('level') ?? '';
  const count = Number(sp.get('n'));
  const seed = Number(sp.get('seed'));
  return {
    settings: {
      kind: KINDS.has(kind) ? (kind as ExerciseKind) : DEFAULT_SETTINGS.kind,
      level: isLevel(level) ? level : '',
      count: Number.isFinite(count) && count > 0 ? Math.min(count, 50) : DEFAULT_SETTINGS.count,
    },
    seed: Number.isFinite(seed) ? seed : 1,
    ids: (sp.get('ids') ?? '').split(',').filter(Boolean),
  };
}

const LETTERS = ['А', 'Б', 'В', 'Г'];

function Blank() {
  return (
    <span className="mx-1 inline-block w-[5.5em] border-b border-black align-baseline">
      <span className="sr-only">пропуск</span>&nbsp;
    </span>
  );
}

function PrintTask({ item, n, hints }: { item: ExerciseItem; n: number; hints: boolean }) {
  const zh = item.lang === 'zh';
  return (
    <li className="break-inside-avoid py-3">
      <div className="flex gap-3">
        <span className="w-6 shrink-0 text-right font-semibold">{n}.</span>
        <div className="flex-1">
          <p
            lang={LANG_INFO[item.lang].htmlLang}
            className={cx(zh ? 'text-[18px] leading-[2]' : 'font-serif text-[17px] leading-[1.9]')}
          >
            {item.before}
            <Blank />
            {item.lemma && <span> ({item.lemma})</span>}
            {item.after}
          </p>
          {item.kind === 'article' && <p className="text-sm text-muted">(a / an / the)</p>}
          {item.kind === 'classifier' && (
            <p className="mt-1 flex flex-wrap gap-x-6 text-[17px]" lang="zh-Hans">
              {item.options.map((option, i) => (
                <span key={option}>
                  <span className="font-sans text-sm">{LETTERS[i]})</span> {option}
                </span>
              ))}
            </p>
          )}
          {hints && (
            <div className="mt-1 space-y-0.5 text-[13.5px] text-muted">
              {item.hints.map((h) => (
                <p key={h.lang} lang={LANG_INFO[h.lang].htmlLang}>
                  <span className="font-sans text-[11px] font-semibold">
                    {LANG_INFO[h.lang].short}
                  </span>{' '}
                  {h.text}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

function PrintContent({ data }: { data: CorpusIndex }) {
  const [sp] = useSearchParams();
  const { settings, seed, ids } = useMemo(() => readSettings(sp), [sp]);
  const [hints, setHints] = useState(true);
  const [explanations, setExplanations] = useState(true);
  const items = useMemo(
    () =>
      ids.length > 0
        ? resolveItems(data.corpus, seed, ids)
        : buildExerciseSet(data.corpus, settings, seed),
    [data.corpus, ids, seed, settings],
  );
  const info = KIND_LABELS[settings.kind];

  if (items.length === 0) {
    return (
      <Container className="pt-16">
        <EmptyState title="Нет заданий для печати">
          <Link to="/exercises" className="underline">
            Вернуться к упражнениям
          </Link>
        </EmptyState>
      </Container>
    );
  }

  const instructions =
    settings.kind === 'mixed'
      ? [KIND_LABELS.article.task, KIND_LABELS.classifier.task, KIND_LABELS.case.task]
      : [info.task];

  return (
    <Container className="pt-8 print:max-w-none print:px-0 print:pt-0">
      <div className="mb-8 flex flex-wrap items-center gap-3 rounded-2xl border border-rule bg-surface p-4 print:hidden">
        <Link to="/exercises" className={buttonClasses.subtle}>
          <ArrowLeftIcon size={16} /> К упражнениям
        </Link>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={hints}
            onChange={(e) => {
              setHints(e.target.checked);
            }}
          />
          параллельные предложения
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={explanations}
            onChange={(e) => {
              setExplanations(e.target.checked);
            }}
          />
          объяснения в ключах
        </label>
        <button
          type="button"
          className={cx(buttonClasses.primary, 'ml-auto')}
          onClick={() => {
            window.print();
          }}
        >
          <PrinterIcon size={18} /> Печать
        </button>
      </div>

      <article className="mx-auto max-w-[46rem] bg-surface p-8 text-ink shadow-soft print:max-w-none print:p-0 print:shadow-none">
        <header className="border-b-2 border-black pb-3">
          <p className="text-sm text-muted">Параллельный корпус EN · ZH · RU</p>
          <h1 className="font-serif text-[26px] font-semibold">
            Упражнения: {info.title.toLowerCase()} · {levelLabel(settings.level)}
          </h1>
          <p className="mt-3 flex flex-wrap gap-x-10 gap-y-1 text-sm">
            <span>Имя: ______________________</span>
            <span>Дата: ____________</span>
            <span>Результат: ____ / {items.length}</span>
          </p>
        </header>
        <div className="mt-4 text-[15px]">
          {instructions.map((line) => (
            <p key={line}>{line}</p>
          ))}
          {hints && (
            <p className="text-muted">Под каждым заданием — перевод на два других языка.</p>
          )}
        </div>
        <ol className="mt-2 divide-y divide-rule">
          {items.map((item, i) => (
            <PrintTask key={item.id} item={item} n={i + 1} hints={hints} />
          ))}
        </ol>

        <section className="mt-10 break-before-page border-t-2 border-black pt-4 print:mt-0">
          <h2 className="font-serif text-[22px] font-semibold">Ключи</h2>
          <p className="text-sm text-muted">
            Набор № {seed} от {formatDate(new Date().toISOString())} — для преподавателя.
          </p>
          <ol className="mt-3 space-y-2 text-[15px]">
            {items.map((item, i) => (
              <li key={item.id} className="flex break-inside-avoid gap-3">
                <span className="w-6 shrink-0 text-right font-semibold">{i + 1}.</span>
                <div>
                  <b lang={LANG_INFO[item.lang].htmlLang}>{item.answer}</b>
                  {item.kind === 'classifier' && (
                    <span className="text-muted">
                      {' '}
                      ({LETTERS[item.options.indexOf(item.answer)] ?? ''})
                    </span>
                  )}
                  <span className="text-muted"> · пара {item.pairId}</span>
                  {explanations && <p className="text-[13.5px] text-muted">{item.explanation}</p>}
                </div>
              </li>
            ))}
          </ol>
        </section>
      </article>
    </Container>
  );
}

export function PrintPage() {
  return <DataGate>{(data) => <PrintContent data={data} />}</DataGate>;
}
