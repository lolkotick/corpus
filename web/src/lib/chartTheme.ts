/** Общие настройки графиков: волосяная сетка, приглушённые подписи, цвета из CSS-токенов. */
export const AXIS_TICK = { fill: 'var(--muted)', fontSize: 12 } as const;
export const GRID_STROKE = 'var(--rule)';
export const CURSOR = { fill: 'var(--sunken)', opacity: 0.6 } as const;
export const SURFACE = 'var(--surface)';
export const MARK = {
  en: 'var(--en-mark)',
  zh: 'var(--zh-mark)',
  ru: 'var(--ru-mark)',
  ru2: 'var(--ru-mark-2)',
  neutral: 'var(--neutral-mark)',
  low: 'var(--low-mark)',
} as const;

export function formatInt(n: number): string {
  return n.toLocaleString('ru-RU');
}

export function formatPercent(part: number, total: number): string {
  if (total === 0) return '0 %';
  return `${((100 * part) / total).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} %`;
}
