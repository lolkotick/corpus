/**
 * Строки экрана «Проверка»: по ним перемещается курсор (↑/↓), к текущей строке
 * применяются клавиши 1 / 2 / 3. Логика отделена от интерфейса, чтобы её можно
 * было проверить тестами.
 */
import type { Lang } from '../data/types';
import {
  alignmentDone,
  langDone,
  setAlignmentVerdict,
  setItemVerdict,
  setLangMode,
  TARGET_LANGS,
  type GoldPair,
  type TargetLang,
  type Verdict,
} from './gold';

export const REVIEW_LANGS: readonly Lang[] = ['en', 'zh', 'ru'];

export type Row =
  | { kind: 'align'; lang: TargetLang }
  | { kind: 'lang'; lang: Lang }
  | { kind: 'item'; lang: Lang; index: number }
  | { kind: 'missed'; lang: Lang };

export function rowKey(row: Row): string {
  switch (row.kind) {
    case 'align':
      return `align-${row.lang}`;
    case 'lang':
      return `lang-${row.lang}`;
    case 'item':
      return `item-${row.lang}-${String(row.index)}`;
    case 'missed':
      return `missed-${row.lang}`;
  }
}

/** Выравнивание EN–ZH, EN–RU, затем по каждому языку: заголовок явления и (в подробном
 *  режиме) каждая пометка и строка «пропуски». */
export function buildRows(review: GoldPair): Row[] {
  const rows: Row[] = TARGET_LANGS.map((lang) => ({ kind: 'align', lang }));
  for (const lang of REVIEW_LANGS) {
    rows.push({ kind: 'lang', lang });
    const phen = review.phenomena[lang];
    if (phen.mode === 'itemized') {
      phen.items.forEach((_, index) => rows.push({ kind: 'item', lang, index }));
      rows.push({ kind: 'missed', lang });
    }
  }
  return rows;
}

export function rowDone(review: GoldPair, row: Row): boolean {
  switch (row.kind) {
    case 'align':
      return alignmentDone(review.alignment[row.lang]);
    case 'lang':
      return langDone(review.phenomena[row.lang]);
    case 'item':
      return review.phenomena[row.lang].items[row.index]?.verdict != null;
    case 'missed':
      return true;
  }
}

/** Следующая незавершённая строка после from (по кругу не идём); иначе from. */
export function nextOpenRow(review: GoldPair, rows: readonly Row[], from: number): number {
  for (let i = from + 1; i < rows.length; i += 1) {
    const row = rows[i];
    if (row && row.kind !== 'missed' && !rowDone(review, row)) return i;
  }
  return from;
}

/**
 * Клавиши 1 / 2 / 3 для строки. Для заголовка явления: 1 — «всё верно»,
 * 2 и 3 — перейти к проверке по одной.
 */
export function applyKey(review: GoldPair, row: Row, verdict: Verdict): GoldPair {
  switch (row.kind) {
    case 'align':
      return setAlignmentVerdict(review, row.lang, verdict);
    case 'lang':
      return setLangMode(review, row.lang, verdict === 'correct' ? 'all-correct' : 'itemized');
    case 'item':
      return setItemVerdict(review, row.lang, row.index, verdict);
    case 'missed':
      return review;
  }
}

/** «Остальное верно»: всё, что ещё не оценено, отмечается как верное. */
export function acceptRemaining(review: GoldPair): GoldPair {
  let next = review;
  for (const lang of TARGET_LANGS) {
    if (next.alignment[lang].verdict === null) next = setAlignmentVerdict(next, lang, 'correct');
  }
  for (const lang of REVIEW_LANGS) {
    const phen = next.phenomena[lang];
    if (phen.mode === null) {
      next = setLangMode(next, lang, 'all-correct');
    } else if (phen.mode === 'itemized') {
      phen.items.forEach((item, index) => {
        if (item.verdict === null) next = setItemVerdict(next, lang, index, 'correct');
      });
    }
  }
  return next;
}
