import { useCallback, useDeferredValue, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { CloseIcon, FilterIcon, SearchIcon } from '../components/icons';
import { FilterBar } from '../components/search/FilterBar';
import { KwicView } from '../components/search/KwicView';
import { ResultsColumns } from '../components/search/ResultsColumns';
import { ShowMore } from '../components/search/ShowMore';
import { EmptyState, PageHeader } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import { plural } from '../lib/labels';
import {
  activeFilterCount,
  buildKwic,
  parseParams,
  runSearch,
  serializeParams,
  type SearchParams,
  type ViewMode,
} from '../lib/search';
import { cx } from '../lib/styles';
import { detectLang } from '../lib/text';

const EXAMPLES = [
  { q: 'книг', hint: 'все формы: книга, книгу, книг' },
  { q: 'the', hint: 'определённый артикль' },
  { q: '本', hint: 'счётное слово для книг' },
  { q: 'чай', hint: 'по лемме' },
  { q: 'a cup of', hint: 'словосочетание' },
];

const MODES: { value: ViewMode; label: string }[] = [
  { value: 'columns', label: 'Колонки' },
  { value: 'kwic', label: 'KWIC' },
];

function SearchContent({ data }: { data: CorpusIndex }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const params = useMemo(() => parseParams(searchParams), [searchParams]);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const update = useCallback(
    (patch: Partial<SearchParams>) => {
      setSearchParams(serializeParams({ ...params, ...patch }), { replace: true });
    },
    [params, setSearchParams],
  );

  const deferred = useDeferredValue(params);
  const results = useMemo(() => runSearch(data.corpus, deferred), [data.corpus, deferred]);
  const kwic = useMemo(
    () => (deferred.mode === 'kwic' ? buildKwic(results, deferred) : []),
    [results, deferred],
  );
  const stale = deferred !== params;
  const queryLang = detectLang(params.q);
  const lemmaUsed = results.some((r) => r.lemmaMatch);
  // Новый запрос или сортировка — снова первые PAGE_SIZE результатов.
  const pageKey = serializeParams(deferred).toString();
  const hasQuery = params.q.trim() !== '';
  const filterCount = activeFilterCount(params);

  return (
    <Container className="pt-10 sm:pt-14">
      <PageHeader eyebrow="Поиск по корпусу" title="Найдите слово на любом из трёх языков">
        Запрос на английском, китайском или русском ищется во всех колонках. Русские существительные
        находятся и по начальной форме: «чай» найдёт «чая» и «чаем».
      </PageHeader>

      <div className="sticky top-[61px] z-20 -mx-4 bg-paper/95 px-4 pt-2 pb-3 backdrop-blur sm:static sm:mx-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-none">
        <form
          role="search"
          className="flex items-center gap-2 rounded-xl border border-rule-strong bg-surface py-1.5 pr-1.5 pl-4 shadow-soft focus-within:border-ink/50"
          onSubmit={(e) => {
            e.preventDefault();
          }}
        >
          <SearchIcon className="shrink-0 text-muted" />
          <label htmlFor="q" className="sr-only">
            Поисковый запрос
          </label>
          <input
            id="q"
            type="search"
            autoComplete="off"
            spellCheck={false}
            placeholder="книга · the · 本 · в библиотеку"
            value={params.q}
            onChange={(e) => {
              update({ q: e.target.value });
            }}
            className="min-w-0 flex-1 bg-transparent py-2 text-[17px] outline-none placeholder:text-muted/70 [&::-webkit-search-cancel-button]:hidden"
          />
          {hasQuery && (
            <button
              type="button"
              className="inline-flex size-9 items-center justify-center rounded-lg text-muted hover:bg-sunken hover:text-ink"
              aria-label="Очистить запрос"
              onClick={() => {
                update({ q: '' });
              }}
            >
              <CloseIcon size={16} />
            </button>
          )}
          <div
            role="group"
            aria-label="Вид результатов"
            className="hidden rounded-[9px] bg-sunken p-[3px] sm:inline-flex"
          >
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                aria-pressed={params.mode === m.value}
                onClick={() => {
                  update({ mode: m.value });
                }}
                className={cx(
                  'rounded-[7px] px-3 py-1.5 text-[13.5px] transition',
                  params.mode === m.value
                    ? 'bg-surface text-ink shadow-sm'
                    : 'text-muted hover:text-ink',
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
        </form>

        <div className="mt-3 flex items-center gap-2 sm:hidden">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-full border border-rule-strong bg-surface px-3 py-1.5 text-[13.5px]"
            aria-expanded={filtersOpen}
            aria-controls="filters"
            onClick={() => {
              setFiltersOpen((o) => !o);
            }}
          >
            <FilterIcon size={15} /> Фильтры{filterCount > 0 && ` · ${filterCount}`}
          </button>
          <div
            role="group"
            aria-label="Вид результатов"
            className="ml-auto inline-flex rounded-[9px] bg-sunken p-[3px]"
          >
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                aria-pressed={params.mode === m.value}
                onClick={() => {
                  update({ mode: m.value });
                }}
                className={cx(
                  'rounded-[7px] px-3 py-1 text-[13px]',
                  params.mode === m.value ? 'bg-surface text-ink shadow-sm' : 'text-muted',
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div id="filters" className={cx('mt-4 sm:block', filtersOpen ? 'block' : 'hidden')}>
        <FilterBar data={data} params={params} onChange={update} />
      </div>

      {!hasQuery && filterCount === 0 && (
        <p className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
          Попробуйте:
          {EXAMPLES.map((ex) => (
            <button
              key={ex.q}
              type="button"
              title={ex.hint}
              className="rounded-md px-1.5 py-0.5 font-medium text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
              onClick={() => {
                update({ q: ex.q });
              }}
            >
              <span lang={detectLang(ex.q) === 'zh' ? 'zh-Hans' : undefined}>{ex.q}</span>
            </button>
          ))}
        </p>
      )}

      <div className="mt-6 mb-2 flex flex-wrap items-baseline justify-between gap-2 text-[13.5px] text-muted">
        <span aria-live="polite" aria-atomic="true">
          {params.mode === 'kwic' && (hasQuery || params.phen)
            ? `${kwic.length} ${plural(kwic.length, 'вхождение', 'вхождения', 'вхождений')} в ${
                results.length
              } ${plural(results.length, 'паре', 'парах', 'парах')}`
            : `${hasQuery || filterCount ? 'Найдено' : 'Всего'} ${results.length} ${plural(
                results.length,
                'пара',
                'пары',
                'пар',
              )}`}
          {hasQuery && queryLang && ` · запрос на языке: ${queryLang.toUpperCase()}`}
          {lemmaUsed && ` · включая формы слова «${params.q.trim()}»`}
        </span>
        {hasQuery && params.mode === 'columns' && (
          <span className="flex w-full flex-wrap gap-x-4 gap-y-1 text-xs sm:order-last">
            <span>
              <mark className="mark-query">совпадение</mark> — найденное слово
            </span>
            <span>
              <mark className="mark-equiv">перевод</mark> — вероятный эквивалент в другом языке (по
              статистике совместной встречаемости в корпусе)
            </span>
          </span>
        )}
        <span className="inline-flex flex-wrap items-center gap-4">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={params.exact}
              onChange={(e) => {
                update({ exact: e.target.checked });
              }}
            />
            целое слово
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={params.showAnn}
              onChange={(e) => {
                update({ showAnn: e.target.checked });
              }}
            />
            показывать разметку
          </label>
        </span>
      </div>

      <div className={cx('transition-opacity', stale && 'opacity-60')}>
        {results.length === 0 ? (
          <EmptyState title="Ничего не найдено">
            Проверьте написание или ослабьте фильтры. Для китайского вводите иероглифы (например,
            <span lang="zh-Hans"> 书</span>), для русского подходит любая форма слова.
          </EmptyState>
        ) : params.mode === 'kwic' ? (
          hasQuery || params.phen ? (
            kwic.length > 0 ? (
              <ShowMore key={pageKey} items={kwic}>
                {(lines) => (
                  <KwicView
                    lines={lines}
                    sort={params.sort}
                    kwicLang={params.kwicLang}
                    onSort={(sort) => {
                      update({ sort });
                    }}
                    onLang={(kwicLang) => {
                      update({ kwicLang });
                    }}
                  />
                )}
              </ShowMore>
            ) : (
              <EmptyState title="Нет вхождений на выбранном языке">
                Выберите другой язык в настройках конкорданса.
              </EmptyState>
            )
          ) : (
            <EmptyState title="Для конкорданса нужен центр">
              Введите запрос или выберите явление в фильтрах — найденное слово окажется в центре
              строки, а контекст слева и справа можно сортировать.
            </EmptyState>
          )
        ) : (
          <ShowMore key={pageKey} items={results}>
            {(visible) => <ResultsColumns results={visible} data={data} />}
          </ShowMore>
        )}
      </div>
    </Container>
  );
}

export function SearchPage() {
  return <DataGate>{(data) => <SearchContent data={data} />}</DataGate>;
}
