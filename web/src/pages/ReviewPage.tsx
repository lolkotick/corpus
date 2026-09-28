import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { ArrowLeftIcon, ArrowRightIcon, CheckIcon } from '../components/icons';
import { Kbd } from '../components/review/controls';
import { PairReview } from '../components/review/PairReview';
import { SetupPanel } from '../components/review/SetupPanel';
import { PairStrip, Toolbar } from '../components/review/Toolbar';
import { PageHeader } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import type { Lang } from '../data/types';
import {
  emptyReview,
  findReview,
  GOLD_STORAGE_KEY,
  isGoldFile,
  newGoldFile,
  pairStatus,
  progress,
  resizeSample,
  serializeGold,
  staleReviews,
  upsertReview,
  type GoldFile,
  type GoldPair,
  type Verdict,
} from '../lib/gold';
import { plural } from '../lib/labels';
import {
  acceptRemaining,
  applyKey,
  buildRows,
  nextOpenRow,
  rowKey,
  type Row,
} from '../lib/reviewRows';
import { readJson, writeStorage } from '../lib/storage';
import { buttonClasses, cx } from '../lib/styles';

const KEY_VERDICT: Record<'1' | '2' | '3', Verdict> = {
  '1': 'correct',
  '2': 'wrong',
  '3': 'corrected',
};

function now(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function isEditable(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    (target instanceof HTMLElement && target.isContentEditable)
  );
}

function download(name: string, content: string): void {
  const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

const HOTKEYS: readonly [string[], string][] = [
  [['1'], 'верно (для явления — «всё верно»)'],
  [['2'], 'ошибка (для явления — проверить по одной)'],
  [['3'], 'исправить: матрица соответствий или поля правильного варианта'],
  [['↓', 'J'], 'следующая строка'],
  [['↑', 'K'], 'предыдущая строка'],
  [['A'], 'остальное в паре верно'],
  [['Enter'], 'добавить пропуск (на строке «Пропуски») · в поле — готово'],
  [['→'], 'следующая пара'],
  [['←'], 'предыдущая пара'],
  [['Esc'], 'выйти из поля ввода'],
  [['?'], 'показать или скрыть эту справку'],
];

function HotkeyHelp({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <details
      open={open}
      onToggle={(event) => {
        if ((event.target as HTMLDetailsElement).open !== open) onToggle();
      }}
      className="mt-8 rounded-2xl border border-rule bg-surface p-4 text-sm sm:p-5"
    >
      <summary className="cursor-pointer font-medium select-none">
        Горячие клавиши <Kbd>?</Kbd>
      </summary>
      <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {HOTKEYS.map(([keys, label]) => (
          <div key={label} className="flex items-baseline gap-3">
            <dt className="flex w-20 shrink-0 gap-1">
              {keys.map((k) => (
                <Kbd key={k}>{k}</Kbd>
              ))}
            </dt>
            <dd className="text-muted">{label}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-muted">
        Буквенные клавиши работают и в русской раскладке. В полях ввода клавиши не перехватываются.
      </p>
    </details>
  );
}

function ReviewContent({ data }: { data: CorpusIndex }) {
  const { corpus } = data;
  const [gold, setGold] = useState<GoldFile | null>(() => readJson(GOLD_STORAGE_KEY, isGoldFile));
  const [params, setParams] = useSearchParams();
  const [focus, setFocus] = useState(0);
  const [editRow, setEditRow] = useState<string | null>(null);
  const [picker, setPicker] = useState<Lang | null>(null);
  const [help, setHelp] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    writeStorage(GOLD_STORAGE_KEY, gold ? JSON.stringify(gold) : null);
  }, [gold]);

  const sample = useMemo(() => gold?.sample.pair_ids ?? [], [gold]);
  const statuses = useMemo(
    () => sample.map((id) => pairStatus(gold ? findReview(gold, id) : undefined)),
    [gold, sample],
  );
  const firstOpen = Math.max(
    0,
    statuses.findIndex((s) => s !== 'done'),
  );
  const requested = Number(params.get('n'));
  const index =
    Number.isInteger(requested) && requested >= 1 && requested <= sample.length
      ? requested - 1
      : firstOpen;
  const pairId = sample[index];
  const pair = pairId ? data.pairById.get(pairId) : undefined;
  const review: GoldPair | undefined =
    gold && pair ? (findReview(gold, pair.id) ?? emptyReview(pair)) : undefined;
  const rows = useMemo(() => (review ? buildRows(review) : []), [review]);

  const goTo = useCallback(
    (i: number) => {
      if (i < 0 || i >= sample.length) return;
      setParams({ n: String(i + 1) }, { replace: true });
      setEditRow(null);
      setPicker(null);
    },
    [sample.length, setParams],
  );

  // Новая пара — курсор на первую неоценённую строку (состояние меняется во время
  // рендера, как рекомендует React для производных от props значений).
  const [focusPair, setFocusPair] = useState<string | undefined>(undefined);
  if (review && focusPair !== pairId) {
    setFocusPair(pairId);
    setFocus(Math.max(0, nextOpenRow(review, rows, -1)));
  }

  // Прокрутка к строке под курсором — только после действий с клавиатуры,
  // чтобы при открытии страницы был виден заголовок.
  const scrollRequested = useRef(false);
  useEffect(() => {
    const row = rows[focus];
    if (!row || !scrollRequested.current) return;
    scrollRequested.current = false;
    document
      .querySelector(`[data-row="${rowKey(row)}"]`)
      ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [focus, rows]);

  const save = useCallback((next: GoldPair) => {
    setGold((g) => (g ? upsertReview(g, next, now()) : g));
  }, []);

  const handleKey = useCallback(
    (row: Row, key: '1' | '2' | '3') => {
      if (!review) return;
      const next = applyKey(review, row, KEY_VERDICT[key]);
      save(next);
      const nextRows = buildRows(next);
      const at = nextRows.findIndex((r) => rowKey(r) === rowKey(row));
      if (key === '3' && row.kind !== 'lang') {
        setFocus(at);
        setEditRow(row.kind === 'item' ? rowKey(row) : null);
      } else {
        setFocus(nextOpenRow(next, nextRows, at));
      }
    },
    [review, save],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!review || event.ctrlKey || event.metaKey || event.altKey) return;
      if (isEditable(event.target)) return;
      if (event.target instanceof HTMLButtonElement && (event.key === 'Enter' || event.key === ' '))
        return;
      const row = rows[focus];
      scrollRequested.current = true;
      const digit = /^(?:Digit|Numpad)([123])$/.exec(event.code)?.[1];
      if (digit === '1' || digit === '2' || digit === '3') {
        if (row && row.kind !== 'missed') handleKey(row, digit);
      } else if (event.code === 'ArrowDown' || event.code === 'KeyJ') {
        setFocus((f) => Math.min(rows.length - 1, f + 1));
      } else if (event.code === 'ArrowUp' || event.code === 'KeyK') {
        setFocus((f) => Math.max(0, f - 1));
      } else if (event.code === 'ArrowRight') {
        goTo(index + 1);
      } else if (event.code === 'ArrowLeft') {
        goTo(index - 1);
      } else if (event.code === 'KeyA') {
        save(acceptRemaining(review));
      } else if (event.key === 'Enter' && row?.kind === 'missed') {
        setPicker(row.lang);
      } else if (event.key === '?' || (event.code === 'Slash' && event.shiftKey)) {
        setHelp((h) => !h);
      } else if (event.key === 'Escape') {
        setPicker(null);
        setEditRow(null);
      } else {
        return;
      }
      event.preventDefault();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [review, rows, focus, handleKey, goTo, index, save]);

  function importFile(file: File) {
    void file.text().then((raw) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        setNotice('Файл не читается как JSON — импорт отменён.');
        return;
      }
      if (!isGoldFile(parsed)) {
        setNotice('Это не файл эталона (gold.json) или его версия не поддерживается.');
        return;
      }
      if (
        gold &&
        gold.pairs.length > 0 &&
        !window.confirm('Заменить текущую проверку в браузере содержимым файла?')
      ) {
        return;
      }
      setGold(parsed);
      setParams({}, { replace: true });
      const stale = staleReviews(parsed, corpus);
      setNotice(
        `Загружено: ${String(parsed.pairs.length)} ${plural(parsed.pairs.length, 'пара', 'пары', 'пар')}.` +
          (stale.length
            ? ` Внимание: текст ${String(stale.length)} ${plural(stale.length, 'пары', 'пар', 'пар')} изменился после пересборки корпуса — их нужно проверить заново (${stale.join(', ')}).`
            : ''),
      );
    });
  }

  const fileInput = (
    <input
      ref={fileRef}
      type="file"
      accept="application/json,.json"
      className="sr-only"
      tabIndex={-1}
      aria-hidden="true"
      onChange={(event) => {
        const file = event.target.files?.[0];
        if (file) importFile(file);
        event.target.value = '';
      }}
    />
  );

  const header = (
    <PageHeader eyebrow="Золотой стандарт" title="Проверка разметки">
      <p>
        Пары выборки показываются по одной. Оцените выравнивание и каждую автоматическую пометку:
        верно, ошибка или исправление. Результат — файл <code>gold.json</code>, по которому{' '}
        <code>pipeline/evaluate.py</code> считает точность, полноту и F1.
      </p>
    </PageHeader>
  );

  const noticeBox = notice && (
    <p role="status" className="mb-4 rounded-xl border border-rule bg-sunken p-3 text-[14.5px]">
      {notice}{' '}
      <button type="button" className="ml-1 text-muted underline" onClick={() => setNotice(null)}>
        скрыть
      </button>
    </p>
  );

  if (!gold) {
    return (
      <Container className="pt-10 sm:pt-14">
        {header}
        {noticeBox}
        <SetupPanel
          corpus={corpus}
          onStart={(options) => {
            setGold(newGoldFile(corpus, options, now()));
            setParams({}, { replace: true });
          }}
          onImport={() => fileRef.current?.click()}
        />
        {fileInput}
      </Container>
    );
  }

  const { done, partial, total } = progress(gold);
  const status = statuses[index];
  return (
    <Container className="pt-10 sm:pt-14">
      {header}
      {noticeBox}
      <Toolbar
        key={gold.sample.size}
        gold={gold}
        done={done}
        partial={partial}
        total={total}
        maxSize={corpus.pairs.length}
        onExport={() => download('gold.json', serializeGold(gold))}
        onImport={() => fileRef.current?.click()}
        onResize={(size) => setGold(resizeSample(gold, corpus, size, now()))}
        onReset={() => {
          if (
            window.confirm(
              'Удалить проверку из этого браузера? Если файл gold.json не экспортирован, результаты пропадут.',
            )
          ) {
            setGold(null);
            setParams({}, { replace: true });
          }
        }}
      />
      {fileInput}
      <PairStrip statuses={statuses} current={index} onSelect={goTo} />

      {pair && review ? (
        <>
          <p aria-live="polite" className="sr-only">
            Пара {index + 1} из {sample.length}
          </p>
          <PairReview
            data={data}
            pair={pair}
            review={review}
            rows={rows}
            focus={focus}
            editRow={editRow}
            picker={picker}
            onFocus={setFocus}
            onKey={handleKey}
            onChange={save}
            onEditDone={() => {
              setEditRow(null);
              setFocus((f) => nextOpenRow(review, rows, f));
            }}
            onPicker={setPicker}
          />
          <nav
            aria-label="Переход между парами"
            className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-6"
          >
            <button
              type="button"
              className={buttonClasses.ghost}
              disabled={index === 0}
              onClick={() => goTo(index - 1)}
            >
              <ArrowLeftIcon size={16} /> Предыдущая <Kbd>←</Kbd>
            </button>
            <p className="text-sm text-muted">
              {status === 'done' ? (
                <span className="inline-flex items-center gap-1 text-ink">
                  <CheckIcon size={15} /> пара проверена
                </span>
              ) : (
                <>
                  <Kbd>A</Kbd> — остальное верно
                </>
              )}
            </p>
            <button
              type="button"
              className={cx(status === 'done' ? buttonClasses.primary : buttonClasses.ghost)}
              disabled={index >= sample.length - 1}
              onClick={() => goTo(index + 1)}
            >
              Следующая{' '}
              <Kbd className={status === 'done' ? 'border-paper/30 bg-transparent text-paper' : ''}>
                →
              </Kbd>
              <ArrowRightIcon size={16} />
            </button>
          </nav>
        </>
      ) : (
        <p className="mt-6 rounded-xl border border-danger/40 bg-danger-tint p-4">
          Пары {pairId} нет в текущем корпусе (корпус пересобран). Выберите другую пару или начните
          новую выборку.
        </p>
      )}
      <HotkeyHelp open={help} onToggle={() => setHelp((h) => !h)} />
    </Container>
  );
}

export function ReviewPage() {
  return <DataGate>{(data) => <ReviewContent data={data} />}</DataGate>;
}
