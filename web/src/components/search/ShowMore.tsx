import { useState, type ReactNode } from 'react';

import { plural } from '../../lib/labels';
import { buttonClasses } from '../../lib/styles';

export const PAGE_SIZE = 50;

/** Показывает первые PAGE_SIZE элементов и кнопку «Показать ещё» (большой корпус — тысячи пар).
 *  Сбрасывается при новом запросе через key у родителя. */
export function ShowMore<T>({
  items,
  children,
}: {
  items: readonly T[];
  children: (visible: readonly T[]) => ReactNode;
}) {
  const [limit, setLimit] = useState(PAGE_SIZE);
  const shown = Math.min(limit, items.length);
  const rest = items.length - shown;
  return (
    <>
      {children(items.slice(0, shown))}
      {rest > 0 && (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            className={buttonClasses.ghost}
            onClick={() => {
              setLimit(shown + PAGE_SIZE);
            }}
          >
            Показать ещё {Math.min(PAGE_SIZE, rest)}
          </button>
          <span className="text-sm text-muted" aria-live="polite">
            показано {shown} из {items.length}{' '}
            {plural(items.length, 'результата', 'результатов', 'результатов')}
          </span>
        </div>
      )}
    </>
  );
}
