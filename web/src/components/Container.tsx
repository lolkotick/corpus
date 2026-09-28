import type { ReactNode } from 'react';

import { cx } from '../lib/styles';

export function Container({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx('mx-auto w-full max-w-[1200px] px-4 sm:px-8', className)}>{children}</div>
  );
}
