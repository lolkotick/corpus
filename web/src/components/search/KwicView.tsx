import { Link } from 'react-router-dom';

import type { Lang } from '../../data/types';
import { LANG_INFO, LANGS } from '../../lib/labels';
import type { KwicLine, KwicSort } from '../../lib/search';
import { cx, LANG_CLASSES } from '../../lib/styles';
import { LangBadge } from '../ui';
import { ScrollArea } from '../ScrollArea';

const SORTS: { value: KwicSort; label: string }[] = [
  { value: 'position', label: 'по порядку в корпусе' },
  { value: 'left', label: 'по левому контексту' },
  { value: 'keyword', label: 'по ключевому слову' },
  { value: 'right', label: 'по правому контексту' },
];

interface Props {
  lines: readonly KwicLine[];
  sort: KwicSort;
  kwicLang: Lang | '';
  onSort: (sort: KwicSort) => void;
  onLang: (lang: Lang | '') => void;
}

export function KwicView({ lines, sort, kwicLang, onSort, onLang }: Props) {
  return (
    <section aria-label="Конкорданс (KWIC)">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted">Сортировка:</span>
        <div
          role="group"
          aria-label="Сортировка конкорданса"
          className="inline-flex flex-wrap gap-1"
        >
          {SORTS.map((s) => (
            <button
              key={s.value}
              type="button"
              aria-pressed={sort === s.value}
              onClick={() => {
                onSort(s.value);
              }}
              className={cx(
                'rounded-full px-3 py-1 transition',
                sort === s.value
                  ? 'bg-ink text-paper'
                  : 'text-muted hover:bg-surface hover:text-ink',
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
        <label className="ml-auto inline-flex items-center gap-2">
          <span className="text-muted">Язык:</span>
          <select
            className="rounded-lg border border-rule-strong bg-surface px-2 py-1"
            value={kwicLang}
            onChange={(e) => {
              onLang(e.target.value as Lang | '');
            }}
          >
            <option value="">все</option>
            {LANGS.map((l) => (
              <option key={l} value={l}>
                {LANG_INFO[l].name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <ScrollArea label="Таблица конкорданса" className="rounded-2xl border border-rule bg-surface">
        <table className="w-full min-w-[34rem] border-collapse text-[15px]">
          <caption className="sr-only">
            Ключевое слово в центре, слева и справа — контекст. Ссылка ведёт к полной паре.
          </caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">Язык</th>
              <th scope="col">Левый контекст</th>
              <th scope="col">Ключевое слово</th>
              <th scope="col">Правый контекст</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => {
              const zh = line.lang === 'zh';
              const lang = LANG_INFO[line.lang].htmlLang;
              return (
                <tr
                  key={line.key}
                  className="group border-b border-rule transition-colors last:border-0 even:bg-paper/60 hover:bg-sunken/70"
                >
                  <td className="w-12 py-2 pl-3 align-baseline sm:pl-4">
                    <LangBadge lang={line.lang} />
                  </td>
                  <td
                    lang={lang}
                    className={cx(
                      'w-[46%] max-w-0 py-2 align-baseline text-muted',
                      !zh && 'font-serif',
                    )}
                    title={line.left}
                  >
                    {/* Выравнивание вправо + обрезка слева: ближайший к ключу контекст всегда виден. */}
                    <div className="flex justify-end overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_2.5rem)] whitespace-nowrap">
                      <span>{line.left}</span>
                    </div>
                  </td>
                  <td
                    lang={lang}
                    className={cx(
                      'w-px px-2 py-2 align-baseline font-semibold whitespace-nowrap',
                      LANG_CLASSES[line.lang].text,
                      !zh && 'font-serif',
                    )}
                  >
                    <Link
                      to={`/pair/${line.pair.id}`}
                      className="rounded underline-offset-4 group-hover:underline"
                      title={`Открыть пару ${line.pair.id}`}
                    >
                      {line.keyword}
                    </Link>
                  </td>
                  <td
                    lang={lang}
                    className={cx(
                      'w-[46%] max-w-0 truncate py-2 pr-4 align-baseline text-muted',
                      !zh && 'font-serif',
                    )}
                    title={line.right}
                  >
                    {line.right}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </ScrollArea>
    </section>
  );
}
