import type { ReactNode } from 'react';

import { cx } from '../lib/styles';

/**
 * Область с горизонтальной прокруткой (широкие таблицы на телефоне).
 * tabIndex и подпись нужны, чтобы прокрутить её можно было с клавиатуры (WCAG 2.1.1).
 */
export function ScrollArea({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div role="region" aria-label={label} tabIndex={0} className={cx('overflow-x-auto', className)}>
      {children}
    </div>
  );
}
