import type { ReactNode } from 'react';

import type { ExerciseItem } from '../../lib/exercises';
import { LANG_INFO } from '../../lib/labels';
import { cx } from '../../lib/styles';

/** Предложение задания с пропуском: пропуск — отдельный элемент (поле, выбранный ответ или черта). */
export function TaskSentence({
  item,
  blank,
  className,
}: {
  item: ExerciseItem;
  blank: ReactNode;
  className?: string;
}) {
  const zh = item.lang === 'zh';
  return (
    <p
      lang={LANG_INFO[item.lang].htmlLang}
      className={cx(
        zh ? 'text-[22px] leading-[2]' : 'font-serif text-[22px] leading-[1.9]',
        className,
      )}
    >
      {item.before}
      {blank}
      {item.lemma && <span className="text-muted"> ({item.lemma})</span>}
      {item.after}
    </p>
  );
}
