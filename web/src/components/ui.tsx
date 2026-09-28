import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import type { Lang, Status } from '../data/types';
import { formatScore, LANG_INFO, STATUSES } from '../lib/labels';
import { cx, LANG_CLASSES } from '../lib/styles';
import { AlertIcon } from './icons';

export function LangBadge({ lang, className }: { lang: Lang; className?: string }) {
  const c = LANG_CLASSES[lang];
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-md px-1.5 py-0.5 font-sans text-[11px] leading-none font-semibold tracking-wider',
        c.text,
        c.tint,
        className,
      )}
    >
      {LANG_INFO[lang].short}
    </span>
  );
}

/** Подпись колонки языка: цветная черта + название. */
export function LangLabel({ lang, native = true }: { lang: Lang; native?: boolean }) {
  const c = LANG_CLASSES[lang];
  return (
    <span
      className={cx(
        'inline-flex items-center gap-2 text-[11.5px] font-semibold tracking-[0.1em] uppercase',
        c.text,
      )}
    >
      <span aria-hidden="true" className={cx('h-0.5 w-4 rounded-full', c.bg)} />
      {native ? LANG_INFO[lang].native : LANG_INFO[lang].name}
    </span>
  );
}

export function ScoreMeter({ score, low }: { score: number; low: boolean }) {
  return (
    <span className="inline-flex items-center gap-2" title="alignment_score">
      <span
        className="relative h-1.5 w-14 overflow-hidden rounded-full bg-rule"
        role="img"
        aria-label={`Оценка выравнивания ${formatScore(score)}`}
      >
        <span
          className={cx('absolute inset-y-0 left-0 rounded-full', low ? 'bg-danger' : 'bg-ink/60')}
          style={{ width: `${Math.round(score * 100)}%` }}
        />
      </span>
      <span className={cx('font-mono text-xs tabular-nums', low ? 'text-danger' : 'text-muted')}>
        {formatScore(score)}
      </span>
    </span>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  const tone =
    status === 'checked'
      ? 'bg-ru-tint text-ru'
      : status === 'corrected'
        ? 'bg-en-tint text-en'
        : 'bg-sunken text-muted';
  return (
    <span
      className={cx('inline-flex rounded-full px-2 py-0.5 text-xs font-medium', tone)}
      title={STATUSES[status].description}
    >
      {STATUSES[status].label}
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="mb-8 max-w-3xl animate-fade-up">
      {eyebrow && (
        <p className="mb-2 text-[13px] tracking-[0.08em] text-muted uppercase">{eyebrow}</p>
      )}
      <h1 className="font-serif text-[34px] leading-[1.15] font-semibold tracking-[-0.01em] sm:text-[42px]">
        {title}
      </h1>
      {children && <div className="mt-4 text-[17px] text-muted">{children}</div>}
    </header>
  );
}

export function LoadingState({ label = 'Загружаем корпус…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="animate-fade-in py-16">
      <span className="sr-only">{label}</span>
      <div className="grid gap-4" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="grid gap-3 rounded-2xl border border-rule bg-surface p-5 sm:grid-cols-3"
          >
            {[0, 1, 2].map((j) => (
              <div key={j} className="space-y-2">
                <div className="h-3 w-16 animate-pulse rounded bg-sunken" />
                <div className="h-4 animate-pulse rounded bg-sunken" />
                <div className="h-4 w-3/4 animate-pulse rounded bg-sunken" />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="my-12 flex gap-3 rounded-2xl border border-danger/40 bg-danger-tint p-5 text-ink"
    >
      <AlertIcon className="mt-0.5 shrink-0 text-danger" />
      <div>
        <p className="font-semibold">Не удалось загрузить данные корпуса</p>
        <p className="mt-1 text-sm text-muted">
          {message}. Проверьте, что pipeline собрал файлы в <code>web/public/data/</code>, и
          обновите страницу.
        </p>
      </div>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="animate-fade-in rounded-2xl border border-dashed border-rule-strong px-6 py-12 text-center">
      <p className="font-serif text-xl font-semibold">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-muted">{children}</div>}
    </div>
  );
}

export function TextLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="underline decoration-rule-strong underline-offset-4 transition hover:decoration-ink"
    >
      {children}
    </Link>
  );
}
