import type {
  Annotation,
  Corpus,
  Lang,
  Level,
  NumberCode,
  Pair,
  Phenomenon,
  Status,
} from '../data/types';
import { LANGS, LEVELS, PHENOMENA } from './labels';
import {
  codePointConverter,
  detectLang,
  findAll,
  normalizeWord,
  queryRegExp,
  type MarkRange,
} from './text';

export type ViewMode = 'columns' | 'kwic';
export type KwicSort = 'position' | 'left' | 'right' | 'keyword';

export interface SearchParams {
  q: string;
  exact: boolean;
  phen: Phenomenon | '';
  /** Конкретное значение явления: the / a / an / definite / indefinite, 量词, код падежа. */
  sub: string;
  number: NumberCode | '';
  text: string;
  level: Level | '';
  status: Status | '';
  minScore: number;
  maxScore: number;
  disputed: boolean;
  llm: boolean;
  mode: ViewMode;
  sort: KwicSort;
  kwicLang: Lang | '';
  showAnn: boolean;
}

export const DEFAULT_PARAMS: SearchParams = {
  q: '',
  exact: false,
  phen: '',
  sub: '',
  number: '',
  text: '',
  level: '',
  status: '',
  minScore: 0,
  maxScore: 1,
  disputed: false,
  llm: false,
  mode: 'columns',
  sort: 'position',
  kwicLang: '',
  showAnn: true,
};

const PHENOMENON_VALUES = new Set<string>(Object.keys(PHENOMENA));
const STATUS_VALUES = new Set<string>(['auto', 'checked', 'corrected']);
const SORT_VALUES = new Set<string>(['position', 'left', 'right', 'keyword']);

function clampScore(raw: string | null, fallback: number): number {
  if (raw === null || raw === '') return fallback;
  const value = Number(raw.replace(',', '.'));
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : fallback;
}

function isLang(value: string | null): value is Lang {
  return value === 'en' || value === 'zh' || value === 'ru';
}

export function parseParams(sp: URLSearchParams): SearchParams {
  const phen = sp.get('phen') ?? '';
  const level = sp.get('level') ?? '';
  const status = sp.get('status') ?? '';
  const sort = sp.get('sort') ?? '';
  const num = sp.get('num') ?? '';
  const kl = sp.get('kl');
  return {
    q: sp.get('q') ?? '',
    exact: sp.get('exact') === '1',
    phen: PHENOMENON_VALUES.has(phen) ? (phen as Phenomenon) : '',
    sub: sp.get('sub') ?? '',
    number: num === 'sing' || num === 'plur' ? num : '',
    text: sp.get('text') ?? '',
    level: (LEVELS as readonly string[]).includes(level) ? (level as Level) : '',
    status: STATUS_VALUES.has(status) ? (status as Status) : '',
    minScore: clampScore(sp.get('min'), 0),
    maxScore: clampScore(sp.get('max'), 1),
    disputed: sp.get('disp') === '1',
    llm: sp.get('llm') === '1',
    mode: sp.get('mode') === 'kwic' ? 'kwic' : 'columns',
    sort: SORT_VALUES.has(sort) ? (sort as KwicSort) : 'position',
    kwicLang: isLang(kl) ? kl : '',
    showAnn: sp.get('ann') !== '0',
  };
}

export function serializeParams(p: SearchParams): URLSearchParams {
  const sp = new URLSearchParams();
  if (p.q) sp.set('q', p.q);
  if (p.exact) sp.set('exact', '1');
  if (p.phen) sp.set('phen', p.phen);
  if (p.phen && p.sub) sp.set('sub', p.sub);
  if (p.phen === 'case' && p.number) sp.set('num', p.number);
  if (p.text) sp.set('text', p.text);
  if (p.level) sp.set('level', p.level);
  if (p.status) sp.set('status', p.status);
  if (p.minScore > 0) sp.set('min', p.minScore.toFixed(2));
  if (p.maxScore < 1) sp.set('max', p.maxScore.toFixed(2));
  if (p.disputed) sp.set('disp', '1');
  if (p.llm) sp.set('llm', '1');
  if (p.mode !== 'columns') sp.set('mode', p.mode);
  if (p.sort !== 'position') sp.set('sort', p.sort);
  if (p.kwicLang) sp.set('kl', p.kwicLang);
  if (!p.showAnn) sp.set('ann', '0');
  return sp;
}

/** Сколько фильтров (кроме запроса и режима отображения) отличаются от умолчаний. */
export function activeFilterCount(p: SearchParams): number {
  return [
    p.phen !== '',
    p.text !== '',
    p.level !== '',
    p.status !== '',
    p.minScore > 0 || p.maxScore < 1,
    p.disputed,
    p.llm,
  ].filter(Boolean).length;
}

export function annotationsOf(pair: Pair, lang: Lang): Annotation[] {
  return pair.annotations[lang];
}

/** Подходит ли элемент разметки под выбранное явление и значение. */
export function matchesPhenomenon(ann: Annotation, p: SearchParams): boolean {
  switch (ann.kind) {
    case 'article':
      if (p.phen !== 'article') return false;
      if (!p.sub) return true;
      if (p.sub === 'definite') return ann.definite;
      if (p.sub === 'indefinite') return !ann.definite;
      return ann.value === p.sub;
    case 'classifier':
      return p.phen === 'classifier' && (!p.sub || ann.value === p.sub);
    case 'case':
      return (
        p.phen === 'case' &&
        (!p.sub || ann.case === p.sub) &&
        (!p.number || ann.number === p.number)
      );
  }
}

export interface Hit {
  start: number;
  end: number;
}

export interface SearchResult {
  pair: Pair;
  /** Совпадения запроса (UTF-16) по языкам. */
  query: Record<Lang, Hit[]>;
  /** Элементы разметки, подходящие под фильтр явления (UTF-16). */
  phenomenon: Record<Lang, Hit[]>;
  marks: Record<Lang, MarkRange[]>;
  lemmaMatch: boolean;
}

function emptyByLang<T>(): Record<Lang, T[]> {
  return { en: [], zh: [], ru: [] };
}

/** Подсветка разметки: ключевое слово явления + (слабее) его определитель и существительное. */
export function annotationMarks(
  text: string,
  lang: Lang,
  anns: readonly Annotation[],
  strongIds: ReadonlySet<string>,
  includeWeak: boolean,
): MarkRange[] {
  const convert = codePointConverter(text);
  const marks: MarkRange[] = [];
  for (const ann of anns) {
    const strong = strongIds.has(ann.id);
    if (!strong && !includeWeak) continue;
    marks.push({
      start: convert(ann.start),
      end: convert(ann.end),
      kind: 'ann',
      lang,
      strong,
      disputed: ann.disputed,
      title: annotationTitle(ann),
    });
    if (strong && ann.kind !== 'case' && ann.head) {
      marks.push({
        start: convert(ann.head.start),
        end: convert(ann.head.end),
        kind: 'ann',
        lang,
        soft: true,
      });
    }
  }
  return marks;
}

export function annotationTitle(ann: Annotation): string {
  switch (ann.kind) {
    case 'article':
      return `${ann.definite ? 'Определённый' : 'Неопределённый'} артикль «${ann.value}»${
        ann.head ? ` → ${ann.head.text}` : ''
      }`;
    case 'classifier':
      return `量词 ${ann.value} (${ann.pinyin})${ann.head ? ` → ${ann.head.text}` : ' — без существительного'}`;
    case 'case':
      return `${ann.lemma}: ${caseTitle(ann.case)}, ${ann.number === 'sing' ? 'ед. ч.' : 'мн. ч.'}${
        ann.ambiguous ? ' (неоднозначно)' : ''
      }`;
  }
}

function caseTitle(code: string): string {
  const map: Record<string, string> = {
    nomn: 'именительный',
    gent: 'родительный',
    datv: 'дательный',
    accs: 'винительный',
    ablt: 'творительный',
    loct: 'предложный',
    voct: 'звательный',
  };
  return `${map[code] ?? code} падеж`;
}

/**
 * Переводные эквиваленты найденных слов: если совпадение запроса попадает на слово,
 * связанное (по статистике корпуса) со словами других языков, те тоже подсвечиваются.
 */
export function equivalentHits(pair: Pair, query: Record<Lang, Hit[]>): Record<Lang, Hit[]> {
  const result = emptyByLang<Hit>();
  if (!pair.links || !LANGS.some((l) => query[l].length > 0)) return result;
  const converters = {
    en: codePointConverter(pair.en),
    zh: codePointConverter(pair.zh),
    ru: codePointConverter(pair.ru),
  };
  for (const link of pair.links) {
    const matched = LANGS.some((lang) => {
      const span = link[lang];
      if (!span) return false;
      const start = converters[lang](span[0]);
      const end = converters[lang](span[1]);
      return query[lang].some((h) => h.start < end && h.end > start);
    });
    if (!matched) continue;
    for (const lang of LANGS) {
      const span = link[lang];
      if (!span) continue;
      const hit = { start: converters[lang](span[0]), end: converters[lang](span[1]) };
      const overlapsQuery = query[lang].some((h) => h.start < hit.end && h.end > hit.start);
      if (!overlapsQuery) result[lang].push(hit);
    }
  }
  return result;
}

export function runSearch(corpus: Corpus, p: SearchParams): SearchResult[] {
  const q = p.q.trim();
  const levelOf = new Map(corpus.texts.map((t) => [t.id, t.level]));
  const regexps: Record<Lang, RegExp | null> = {
    en: q ? queryRegExp(q, 'en', p.exact) : null,
    zh: q ? queryRegExp(q, 'zh', p.exact) : null,
    ru: q ? queryRegExp(q, 'ru', p.exact) : null,
  };
  const lemma = q && detectLang(q) === 'ru' && !q.includes(' ') ? normalizeWord(q) : '';
  const results: SearchResult[] = [];

  for (const pair of corpus.pairs) {
    if (p.text && pair.text_id !== p.text) continue;
    if (p.level && levelOf.get(pair.text_id) !== p.level) continue;
    if (p.status && pair.status !== p.status) continue;
    if (pair.alignment_score < p.minScore - 1e-9 || pair.alignment_score > p.maxScore + 1e-9) {
      continue;
    }
    if (p.llm && !pair.llm_note) continue;
    if (p.disputed && !LANGS.some((l) => pair.annotations[l].some((a) => a.disputed))) continue;

    const strongIds = new Set<string>();
    const phenomenon = emptyByLang<Hit>();
    if (p.phen) {
      const lang = PHENOMENA[p.phen].lang;
      const text = pair[lang];
      const convert = codePointConverter(text);
      for (const ann of pair.annotations[lang]) {
        if (!matchesPhenomenon(ann, p)) continue;
        if (p.disputed && !ann.disputed) continue;
        strongIds.add(ann.id);
        phenomenon[lang].push({ start: convert(ann.start), end: convert(ann.end) });
      }
      if (strongIds.size === 0) continue;
    }

    const query = emptyByLang<Hit>();
    let lemmaMatch = false;
    if (q) {
      for (const lang of LANGS) {
        const regexp = regexps[lang];
        if (regexp) query[lang] = findAll(pair[lang], regexp, lang !== 'zh');
      }
      if (lemma) {
        const convert = codePointConverter(pair.ru);
        for (const ann of pair.annotations.ru) {
          if (normalizeWord(ann.lemma) !== lemma) continue;
          const hit = { start: convert(ann.start), end: convert(ann.end) };
          if (!query.ru.some((h) => h.start === hit.start)) {
            query.ru.push(hit);
            lemmaMatch = true;
          }
        }
        query.ru.sort((a, b) => a.start - b.start);
      }
      if (!LANGS.some((lang) => query[lang].length > 0)) continue;
    }

    const equivalents = equivalentHits(pair, query);
    const marks = emptyByLang<MarkRange>();
    for (const lang of LANGS) {
      marks[lang] = [
        ...annotationMarks(pair[lang], lang, pair.annotations[lang], strongIds, p.showAnn),
        ...equivalents[lang].map((h) => ({ ...h, kind: 'equiv' as const, lang })),
        ...query[lang].map((h) => ({ ...h, kind: 'query' as const, lang })),
      ];
    }
    results.push({ pair, query, phenomenon, marks, lemmaMatch });
  }
  return results;
}

export interface KwicLine {
  key: string;
  pair: Pair;
  lang: Lang;
  left: string;
  keyword: string;
  right: string;
  offset: number;
}

const CONTEXT_CHARS: Record<Lang, number> = { en: 64, zh: 22, ru: 64 };

function trimLeft(text: string, lang: Lang): string {
  const limit = CONTEXT_CHARS[lang];
  if (text.length <= limit) return text;
  let cut = text.slice(text.length - limit);
  if (lang !== 'zh') {
    const space = cut.indexOf(' ');
    if (space > 0 && space < 16) cut = cut.slice(space + 1);
  }
  return `…${cut}`;
}

function trimRight(text: string, lang: Lang): string {
  const limit = CONTEXT_CHARS[lang];
  if (text.length <= limit) return text;
  let cut = text.slice(0, limit);
  if (lang !== 'zh') {
    const space = cut.lastIndexOf(' ');
    if (space > limit - 16) cut = cut.slice(0, space);
  }
  return `${cut}…`;
}

export function buildKwic(results: readonly SearchResult[], p: SearchParams): KwicLine[] {
  const lines: KwicLine[] = [];
  const useQuery = p.q.trim() !== '';
  for (const result of results) {
    for (const lang of LANGS) {
      if (p.kwicLang && lang !== p.kwicLang) continue;
      const hits = useQuery ? result.query[lang] : result.phenomenon[lang];
      const text = result.pair[lang];
      for (const hit of hits) {
        lines.push({
          key: `${result.pair.id}-${lang}-${hit.start}`,
          pair: result.pair,
          lang,
          left: trimLeft(text.slice(0, hit.start), lang),
          keyword: text.slice(hit.start, hit.end),
          right: trimRight(text.slice(hit.end), lang),
          offset: hit.start,
        });
      }
    }
  }
  return sortKwic(lines, p.sort);
}

const COLLATORS: Record<Lang, Intl.Collator> = {
  en: new Intl.Collator('en', { sensitivity: 'base', ignorePunctuation: true }),
  ru: new Intl.Collator('ru', { sensitivity: 'base', ignorePunctuation: true }),
  zh: new Intl.Collator('zh-Hans-u-co-pinyin', { ignorePunctuation: true }),
};

/** Ключ сортировки по левому контексту: слова справа налево (ближайшее к ключу — первым). */
export function leftKey(left: string, lang: Lang): string {
  const clean = left.replace(/^…/, '').trim();
  if (lang === 'zh') return Array.from(clean).reverse().join(''); // иероглифы — по одному
  return clean
    .split(/\s+/)
    .map((w) => w.replace(/[^\p{L}\p{N}'-]/gu, ''))
    .filter(Boolean)
    .reverse()
    .join(' ');
}

export function rightKey(right: string): string {
  return right.replace(/^[\s\p{P}]+/u, '').trim();
}

export function sortKwic(lines: KwicLine[], sort: KwicSort): KwicLine[] {
  const byLang = (a: KwicLine, b: KwicLine) => LANGS.indexOf(a.lang) - LANGS.indexOf(b.lang);
  const position = (a: KwicLine, b: KwicLine) =>
    a.pair.id.localeCompare(b.pair.id) || a.offset - b.offset;
  const sorted = [...lines];
  sorted.sort((a, b) => {
    const lang = byLang(a, b);
    if (lang !== 0 || sort === 'position') return lang || position(a, b);
    const collator = COLLATORS[a.lang];
    let cmp = 0;
    if (sort === 'left') cmp = collator.compare(leftKey(a.left, a.lang), leftKey(b.left, b.lang));
    if (sort === 'right') cmp = collator.compare(rightKey(a.right), rightKey(b.right));
    if (sort === 'keyword') {
      cmp =
        collator.compare(a.keyword, b.keyword) ||
        collator.compare(rightKey(a.right), rightKey(b.right));
    }
    return cmp || position(a, b);
  });
  return sorted;
}
