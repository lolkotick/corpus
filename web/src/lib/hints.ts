/**
 * Подсказки ИИ для режима «Проверка» (data/gold/hints.json).
 *
 * Подсказка — предварительный вердикт языковой модели по выравниванию или пометке,
 * с коротким обоснованием. Она ничего не заполняет сама: эксперт видит её рядом со
 * строкой и либо принимает, либо выносит свой вердикт. В gold.json у пары ставится
 * `hints_shown: true`, если при проверке подсказки были на экране, — так
 * pipeline/hints.py отделяет «проверено вслепую» от «проверено с подсказками».
 *
 * Для контрольных пар (blind_pair_ids) подсказки не показываются никогда: по ним
 * считается согласие эксперта с моделью без влияния подсказок.
 */
import type { Lang } from '../data/types';
import {
  addMissed,
  setAlignmentVerdict,
  setItemFix,
  setItemVerdict,
  setLangMode,
  type Fix,
  type GoldPair,
  type GoldSpan,
  type TargetLang,
  type Verdict,
} from './gold';
import { CASES } from './labels';
import type { Row } from './reviewRows';

export const HINTS_FORMAT = 'corpus-gold-hints';
export const HINTS_VERSION = 1;
export const HINTS_STORAGE_KEY = 'corpus.gold.hints.v1';

/** verdict: null — модель эту строку ещё не оценила (заготовка); такая подсказка не видна. */
export interface AlignmentHint {
  verdict: Verdict | null;
  links?: [number, number][];
  note?: string;
}

export interface ItemHint {
  id: string;
  verdict: Verdict | null;
  correction?: Fix | null;
  note?: string;
}

export type MissedHint = GoldSpan & Fix & { note?: string };

export interface PairHints {
  id: string;
  alignment?: Partial<Record<TargetLang, AlignmentHint>>;
  items?: Partial<Record<Lang, ItemHint[]>>;
  missed?: Partial<Record<Lang, MissedHint[]>>;
}

export interface HintsFile {
  format: typeof HINTS_FORMAT;
  version: number;
  /** Кто составил подсказки: название модели и способ. */
  source: string;
  created_at: string;
  /** Контрольные пары: проверяются вслепую, подсказки для них скрыты. */
  blind_pair_ids: string[];
  pairs: PairHints[];
}

const VERDICT_TEXT: Record<Verdict, string> = {
  correct: 'верно',
  wrong: 'ошибка',
  corrected: 'исправить',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isHintsFile(value: unknown): value is HintsFile {
  return (
    isRecord(value) &&
    value.format === HINTS_FORMAT &&
    typeof value.version === 'number' &&
    value.version <= HINTS_VERSION &&
    Array.isArray(value.blind_pair_ids) &&
    value.blind_pair_ids.every((id) => typeof id === 'string') &&
    Array.isArray(value.pairs) &&
    value.pairs.every((p) => isRecord(p) && typeof p.id === 'string')
  );
}

export function isBlind(hints: HintsFile | null, pairId: string): boolean {
  return hints?.blind_pair_ids.includes(pairId) ?? false;
}

/** Подсказки пары, которые можно показывать: для контрольных пар — null. */
export function visibleHints(hints: HintsFile | null, pairId: string): PairHints | null {
  if (!hints || isBlind(hints, pairId)) return null;
  return hints.pairs.find((p) => p.id === pairId) ?? null;
}

export function alignmentHint(hints: PairHints | null, lang: TargetLang): AlignmentHint | null {
  const hint = hints?.alignment?.[lang];
  return hint?.verdict ? hint : null;
}

export function itemHint(hints: PairHints | null, lang: Lang, id: string): ItemHint | null {
  const hint = hints?.items?.[lang]?.find((h) => h.id === id);
  return hint?.verdict ? hint : null;
}

/** Пропуски, которые предлагает модель и которые эксперт ещё не добавил. */
export function missedHints(hints: PairHints | null, review: GoldPair, lang: Lang): MissedHint[] {
  const added = new Set(review.phenomena[lang].missed.map((m) => m.start));
  return (hints?.missed?.[lang] ?? []).filter((m) => !added.has(m.start));
}

/**
 * Сводка по языку: сколько пометок модель считает неверными и сколько пропусков
 * предлагает. null — модель оценила не все пометки пары.
 */
export function langSummary(
  hints: PairHints | null,
  review: GoldPair,
  lang: Lang,
): { flagged: number; missed: number } | null {
  if (!hints) return null;
  const items = review.phenomena[lang].items;
  const found = items.map((item) => itemHint(hints, lang, item.id));
  if (found.some((h) => h === null)) return null;
  if (items.length === 0 && hints.items?.[lang] === undefined && !hints.missed?.[lang]) return null;
  return {
    flagged: found.filter((h) => h?.verdict !== 'correct').length,
    missed: hints.missed?.[lang]?.length ?? 0,
  };
}

function fixText(lang: Lang, fix: Fix | null | undefined): string {
  if (!fix) return '';
  const parts: string[] = [];
  if (lang === 'zh' && fix.classifier) parts.push(`счётное слово ${fix.classifier}`);
  if (lang !== 'ru' && fix.head !== undefined)
    parts.push(fix.head ? `существительное ${fix.head}` : 'без существительного');
  if (lang === 'ru' && fix.case) parts.push(`падеж ${CASES[fix.case].short}`);
  if (lang === 'ru' && fix.lemma) parts.push(`лемма ${fix.lemma}`);
  return parts.join(', ');
}

/** Текст подсказки: «верно», «ошибка» или «исправить: падеж род., лемма книга». */
export function hintLabel(lang: Lang, hint: { verdict: Verdict | null; correction?: Fix | null }) {
  if (!hint.verdict) return '';
  const fix = hint.verdict === 'corrected' ? fixText(lang, hint.correction) : '';
  return fix ? `${VERDICT_TEXT[hint.verdict]}: ${fix}` : VERDICT_TEXT[hint.verdict];
}

export function alignmentHintLabel(hint: AlignmentHint): string {
  if (!hint.verdict) return '';
  if (hint.verdict !== 'corrected' || !hint.links?.length) return VERDICT_TEXT[hint.verdict];
  const links = hint.links.map(([e, t]) => `${String(e + 1)}–${String(t + 1)}`).join(', ');
  return `${VERDICT_TEXT.corrected}: ${links}`;
}

export function applyAlignmentHint(
  review: GoldPair,
  lang: TargetLang,
  hint: AlignmentHint,
): GoldPair {
  if (!hint.verdict) return review;
  const next = setAlignmentVerdict(review, lang, hint.verdict);
  if (hint.verdict !== 'corrected' || !hint.links?.length) return next;
  const links = [...hint.links].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return { ...next, alignment: { ...next.alignment, [lang]: { verdict: 'corrected', links } } };
}

export function applyItemHint(
  review: GoldPair,
  lang: Lang,
  index: number,
  hint: ItemHint,
): GoldPair {
  if (!hint.verdict) return review;
  const next = setItemVerdict(review, lang, index, hint.verdict);
  return hint.verdict === 'corrected' && hint.correction
    ? setItemFix(next, lang, index, hint.correction)
    : next;
}

export function applyMissedHint(review: GoldPair, lang: Lang, hint: MissedHint): GoldPair {
  // Обоснование модели в эталон не переносится: там остаются только данные пометки.
  const item: MissedHint = { ...hint };
  delete item.note;
  return addMissed(review, lang, item);
}

/**
 * Принять подсказку для строки под курсором (клавиша H). Для заголовка явления:
 * если модель считает все пометки верными и пропусков не предлагает — «всё верно»,
 * иначе — переход к проверке по одной. null — подсказки для строки нет.
 */
export function applyRowHint(review: GoldPair, row: Row, hints: PairHints | null): GoldPair | null {
  if (!hints) return null;
  switch (row.kind) {
    case 'align': {
      const hint = alignmentHint(hints, row.lang);
      return hint ? applyAlignmentHint(review, row.lang, hint) : null;
    }
    case 'item': {
      const item = review.phenomena[row.lang].items[row.index];
      const hint = item ? itemHint(hints, row.lang, item.id) : null;
      return hint ? applyItemHint(review, row.lang, row.index, hint) : null;
    }
    case 'lang': {
      const summary = langSummary(hints, review, row.lang);
      if (!summary) return null;
      return setLangMode(
        review,
        row.lang,
        summary.flagged === 0 && summary.missed === 0 ? 'all-correct' : 'itemized',
      );
    }
    case 'missed':
      return null;
  }
}

/** Отметить, что пара проверялась с подсказками на экране. */
export function markHintsShown(review: GoldPair): GoldPair {
  return review.hints_shown ? review : { ...review, hints_shown: true };
}
