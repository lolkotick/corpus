import type { Lang, Span } from '../data/types';

/**
 * Pipeline хранит позиции в кодовых точках Unicode (как Python), а строки JS —
 * в единицах UTF-16. Для текстов без суррогатных пар (почти всегда) это одно и то же.
 */
export function codePointConverter(text: string): (cp: number) => number {
  if (!/[\uD800-\uDFFF]/.test(text)) return (cp) => cp;
  const map: number[] = [];
  let unit = 0;
  for (const char of text) {
    map.push(unit);
    unit += char.length;
  }
  map.push(unit);
  return (cp) => map[Math.min(cp, map.length - 1)] ?? text.length;
}

export function spanRange(text: string, span: Span): { start: number; end: number } {
  const convert = codePointConverter(text);
  return { start: convert(span.start), end: convert(span.end) };
}

export type MarkKind = 'query' | 'ann' | 'equiv';

export interface MarkRange {
  start: number;
  end: number;
  kind: MarkKind;
  lang: Lang;
  /** Совпадает с выбранным фильтром явления — подсвечивается сильнее. */
  strong?: boolean;
  /** Часть конструкции (определитель или существительное при 量词/артикле). */
  soft?: boolean;
  disputed?: boolean;
  title?: string;
}

export interface TextSegment {
  text: string;
  marks: MarkRange[];
}

/** Разбить текст на отрезки, внутри которых набор подсветок не меняется. */
export function segmentize(text: string, ranges: readonly MarkRange[]): TextSegment[] {
  const valid = ranges.filter((r) => r.end > r.start && r.start >= 0 && r.end <= text.length);
  if (valid.length === 0) return [{ text, marks: [] }];
  const points = new Set<number>([0, text.length]);
  for (const r of valid) {
    points.add(r.start);
    points.add(r.end);
  }
  const sorted = [...points].sort((a, b) => a - b);
  const segments: TextSegment[] = [];
  for (let i = 0; i < sorted.length - 1; i += 1) {
    const start = sorted[i] ?? 0;
    const end = sorted[i + 1] ?? text.length;
    if (end <= start) continue;
    segments.push({
      text: text.slice(start, end),
      marks: valid.filter((r) => r.start <= start && r.end >= end),
    });
  }
  return segments;
}

const HAN = /\p{Script=Han}/u;
const CYRILLIC = /\p{Script=Cyrillic}/u;
const LATIN = /\p{Script=Latin}/u;

export function detectLang(query: string): Lang | null {
  if (HAN.test(query)) return 'zh';
  if (CYRILLIC.test(query)) return 'ru';
  if (LATIN.test(query)) return 'en';
  return null;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** «е» и «ё» в запросе и тексте считаются одной буквой. */
function yoInsensitive(pattern: string): string {
  return pattern.replace(/[еёЕЁ]/gu, '[её]'); // флаг i делает класс нечувствительным к регистру
}

/**
 * Регулярное выражение для поиска.
 * EN/RU: совпадение с начала слова (запрос «книг» найдёт «книга», «книгу»); exact — целое слово.
 * ZH: подстрока (в китайском нет пробелов между словами).
 */
export function queryRegExp(query: string, lang: Lang, exact: boolean): RegExp | null {
  const trimmed = query.trim().replace(/\s+/g, ' ');
  if (!trimmed) return null;
  if (lang === 'zh') {
    if (!HAN.test(trimmed) && !/\d/.test(trimmed)) return null;
    return new RegExp(escapeRegExp(trimmed), 'gu');
  }
  if (HAN.test(trimmed)) return null;
  const body = yoInsensitive(escapeRegExp(trimmed)).replace(/ /g, '\\s+');
  const tail = exact ? '(?![\\p{L}\\p{N}])' : '';
  return new RegExp(`(?<![\\p{L}\\p{N}])${body}${tail}`, 'giu');
}

const WORD_CHAR = /[\p{L}\p{N}'’-]/u;

/**
 * Все совпадения. Если wholeWord, совпадение по началу слова расширяется до конца слова:
 * запрос «книг» подсвечивает «книгу» целиком (и в KWIC ключевым словом становится «книгу»).
 */
export function findAll(
  text: string,
  regexp: RegExp,
  wholeWord = false,
): { start: number; end: number }[] {
  const result: { start: number; end: number }[] = [];
  regexp.lastIndex = 0;
  for (const match of text.matchAll(regexp)) {
    const start = match.index;
    let end = start + match[0].length;
    if (wholeWord) {
      while (end < text.length && WORD_CHAR.test(text.charAt(end))) end += 1;
    }
    if (end > start) result.push({ start, end });
  }
  return result;
}

export function normalizeWord(word: string): string {
  return word.trim().toLocaleLowerCase('ru').replaceAll('ё', 'е');
}
