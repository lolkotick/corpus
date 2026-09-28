import type { Lang } from '../data/types';

/** Классы цвета языка: текст, подложка, рамка, заливка. Один источник для всего интерфейса. */
export const LANG_CLASSES: Record<
  Lang,
  { text: string; tint: string; border: string; bg: string }
> = {
  en: { text: 'text-en', tint: 'bg-en-tint', border: 'border-en', bg: 'bg-en' },
  zh: { text: 'text-zh', tint: 'bg-zh-tint', border: 'border-zh', bg: 'bg-zh' },
  ru: { text: 'text-ru', tint: 'bg-ru-tint', border: 'border-ru', bg: 'bg-ru' },
};

/** CSS-переменные языков для SVG и графиков: mark — заливка меток, color — текст. */
export const LANG_VARS: Record<Lang, { color: string; tint: string; mark: string }> = {
  en: { color: 'var(--en)', tint: 'var(--en-tint)', mark: 'var(--en-mark)' },
  zh: { color: 'var(--zh)', tint: 'var(--zh-tint)', mark: 'var(--zh-mark)' },
  ru: { color: 'var(--ru)', tint: 'var(--ru-tint)', mark: 'var(--ru-mark)' },
};

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}

export const buttonClasses = {
  primary:
    'inline-flex items-center justify-center gap-2 rounded-[10px] bg-ink px-5 py-3 font-semibold text-paper transition hover:opacity-90 active:translate-y-px disabled:opacity-50',
  ghost:
    'inline-flex items-center justify-center gap-2 rounded-[10px] px-5 py-3 font-semibold text-ink ring-1 ring-rule-strong ring-inset transition hover:bg-surface active:translate-y-px disabled:opacity-50',
  subtle:
    'inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-muted transition hover:bg-surface hover:text-ink',
  chip: 'inline-flex items-center gap-1.5 rounded-full border border-rule-strong bg-surface px-3 py-1.5 text-[13.5px] transition hover:border-ink/40',
};
