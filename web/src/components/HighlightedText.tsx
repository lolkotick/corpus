import { useMemo, type ReactNode } from 'react';

import type { Lang } from '../data/types';
import { LANG_INFO } from '../lib/labels';
import { cx } from '../lib/styles';
import { segmentize, type MarkRange } from '../lib/text';

interface Props {
  text: string;
  lang: Lang;
  marks: readonly MarkRange[];
  className?: string;
  as?: 'p' | 'span' | 'div';
}

/**
 * Текст с подсветкой: совпадения запроса — жёлтым маркером, разметка — цветом языка
 * (подчёркивание; при выбранном фильтре явления — ещё и подложка). Текст не изменяется:
 * подсветка строится по позициям из разметки.
 */
export function HighlightedText({ text, lang, marks, className, as: Tag = 'p' }: Props) {
  const segments = useMemo(() => segmentize(text, marks), [text, marks]);
  return (
    <Tag lang={LANG_INFO[lang].htmlLang} className={className}>
      {segments.map((segment, i) => {
        const ann = segment.marks.filter((m) => m.kind === 'ann');
        const isQuery = segment.marks.some((m) => m.kind === 'query');
        const isEquiv = !isQuery && segment.marks.some((m) => m.kind === 'equiv');
        let node: ReactNode = segment.text;
        if (ann.length > 0) {
          const strong = ann.some((m) => m.strong);
          const soft = ann.every((m) => m.soft);
          const disputed = ann.some((m) => m.disputed);
          const title = ann.find((m) => m.title)?.title;
          node = (
            <span
              className={cx(
                `mark-${lang}`,
                strong && 'mark-strong',
                soft && 'mark-soft',
                disputed && !soft && 'mark-disputed',
              )}
              title={title}
            >
              {node}
            </span>
          );
        }
        if (isQuery) node = <mark className="mark-query">{node}</mark>;
        if (isEquiv) {
          node = (
            <mark className="mark-equiv" title="Вероятный перевод найденного слова">
              {node}
            </mark>
          );
        }
        return <span key={i}>{node}</span>;
      })}
    </Tag>
  );
}
