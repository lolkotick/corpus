import type { TextMeta } from '../../data/types';
import type { TargetLang } from '../../lib/gold';
import { LANG_INFO } from '../../lib/labels';
import { cx, LANG_CLASSES } from '../../lib/styles';
import { ScrollArea } from '../ScrollArea';

interface Props {
  text: TextMeta;
  lang: TargetLang;
  window: { en: number[]; target: number[] };
  /** Предложения пары (выделяются в окне). */
  own: { en: number[]; target: number[] };
  links: readonly [number, number][];
  onToggle: (en: number, target: number) => void;
}

/**
 * Матрица соответствий: строки — предложения EN, столбцы — ZH/RU (пара и по одному
 * соседнему предложению). Отмеченная клетка — эти два предложения переводят друг друга.
 */
export function AlignmentMatrix({ text, lang, window, own, links, onToggle }: Props) {
  const linked = new Set(links.map(([e, t]) => `${String(e)}:${String(t)}`));
  const short = LANG_INFO[lang].short;
  const c = LANG_CLASSES[lang];
  return (
    <div className="mt-3 rounded-xl border border-rule bg-paper p-3 sm:p-4">
      <p className="text-[13px] text-muted">
        Отметьте клетки, где предложения соответствуют друг другу. Показаны предложения пары и
        соседние; номера — по порядку в тексте.
      </p>
      <ScrollArea label={`Матрица соответствий EN–${short}`} className="mt-3">
        <table className="border-separate border-spacing-1 text-[13.5px]">
          <thead>
            <tr>
              <th scope="col" className="sr-only">
                Предложение EN
              </th>
              {window.target.map((t) => (
                <th
                  key={t}
                  scope="col"
                  className={cx(
                    'px-1 text-center font-mono text-xs font-medium',
                    own.target.includes(t) ? c.text : 'text-muted',
                  )}
                >
                  {short} {t + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {window.en.map((e) => (
              <tr key={e}>
                <th
                  scope="row"
                  className={cx(
                    'max-w-[22rem] py-1 pr-3 text-left align-middle font-normal',
                    own.en.includes(e) ? 'text-ink' : 'text-muted',
                  )}
                >
                  <span className="mr-1.5 font-mono text-xs text-en">EN {e + 1}</span>
                  <span lang="en" className="line-clamp-2">
                    {text.sentences.en[e]}
                  </span>
                </th>
                {window.target.map((t) => {
                  const on = linked.has(`${String(e)}:${String(t)}`);
                  return (
                    <td key={t} className="text-center">
                      <button
                        type="button"
                        aria-pressed={on}
                        aria-label={`Соответствие EN ${String(e + 1)} и ${short} ${String(t + 1)}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onToggle(e, t);
                        }}
                        className={cx(
                          'size-9 rounded-lg text-base transition',
                          on
                            ? cx(c.bg, 'text-paper')
                            : 'bg-surface ring-1 ring-rule-strong ring-inset hover:bg-sunken',
                        )}
                      >
                        {on ? '●' : ''}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollArea>
      <ol className="mt-3 grid gap-1 text-[14px]">
        {window.target.map((t) => (
          <li key={t} className={own.target.includes(t) ? 'text-ink' : 'text-muted'}>
            <span className={cx('mr-1.5 font-mono text-xs', c.text)}>
              {short} {t + 1}
            </span>
            <span lang={LANG_INFO[lang].htmlLang}>{text.sentences[lang][t]}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
