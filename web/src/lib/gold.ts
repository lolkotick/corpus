/**
 * Золотой стандарт: ручная проверка выборки пар и формат файла data/gold/gold.json.
 *
 * Для каждой пары эксперт оценивает выравнивание EN–ZH и EN–RU и каждую
 * автоматическую пометку (артикль, 量词, падеж): верно / ошибка / исправление.
 * Пропущенные автоматикой случаи добавляются отдельно. Позиции хранятся в
 * кодовых точках — как в corpus.json, чтобы pipeline/evaluate.py мог сравнить их
 * с разметкой без преобразований.
 */
import type { CaseCode, Corpus, Lang, Pair } from '../data/types';
import { mulberry32, shuffle } from './random';

export const GOLD_FORMAT = 'corpus-gold';
export const GOLD_VERSION = 1;
export const GOLD_STORAGE_KEY = 'corpus.gold.v1';
export const DEFAULT_SAMPLE_SIZE = 30;
export const DEFAULT_SEED = 2026;

export type Verdict = 'correct' | 'wrong' | 'corrected';
export type TargetLang = 'zh' | 'ru';
export const TARGET_LANGS: readonly TargetLang[] = ['zh', 'ru'];

export const VERDICTS: Record<Verdict, { label: string; key: string }> = {
  correct: { label: 'Верно', key: '1' },
  wrong: { label: 'Ошибка', key: '2' },
  corrected: { label: 'Исправить', key: '3' },
};

/** Фрагмент текста; start/end — в кодовых точках Unicode. */
export interface GoldSpan {
  start: number;
  end: number;
  text: string;
}

export interface AlignmentReview {
  verdict: Verdict | null;
  /** Для исправления: правильные соответствия предложений [номер EN, номер ZH/RU]. */
  links: [number, number][];
}

export type Snapshot =
  | (GoldSpan & { kind: 'article'; value: string; head: GoldSpan | null })
  | (GoldSpan & { kind: 'classifier'; value: string; det: GoldSpan; head: GoldSpan | null })
  | (GoldSpan & { kind: 'case'; lemma: string; case: CaseCode; number: string });

/** Правильный вариант: для артикля — существительное; для 量词 — счётное слово и
 *  существительное; для падежа — падеж и начальная форма. */
export interface Fix {
  head?: string;
  classifier?: string;
  case?: CaseCode;
  lemma?: string;
}

export interface ItemReview {
  id: string;
  /** Автоматическая пометка на момент проверки (снимок). */
  auto: Snapshot;
  verdict: Verdict | null;
  correction: Fix | null;
}

/** Пропущенный автоматикой случай. */
export type MissedItem = GoldSpan & Fix;

export type LangMode = 'all-correct' | 'itemized';

export interface LangReview {
  /** all-correct — все пометки верны и пропусков нет; itemized — проверка по одной. */
  mode: LangMode | null;
  items: ItemReview[];
  missed: MissedItem[];
}

export interface GoldPair {
  id: string;
  text_id: string;
  reviewed_at: string | null;
  /** Текст и номера предложений на момент проверки: evaluate.py сверяет их с корпусом. */
  text: Record<Lang, string>;
  sentences: Record<Lang, number[]>;
  alignment: Record<TargetLang, AlignmentReview>;
  phenomena: Record<Lang, LangReview>;
  comment: string;
}

export interface GoldSample {
  seed: number;
  size: number;
  strategy: 'proportional';
  pair_ids: string[];
}

export interface GoldFile {
  format: typeof GOLD_FORMAT;
  version: number;
  annotator: string;
  created_at: string;
  updated_at: string;
  corpus: { generated_at: string; alignment_method: string };
  sample: GoldSample;
  pairs: GoldPair[];
  /** Только у тестовых файлов: данные выдуманы для проверки кода. */
  synthetic?: boolean;
}

/* ─── Выборка ──────────────────────────────────────────────────────────── */

/**
 * Пропорциональная выборка по текстам. Внутри каждого текста пары перемешиваются
 * (seed), k-я пара текста получает ключ (k + сдвиг) / n; общий список сортируется
 * по ключу. Любые первые N пар списка представляют тексты пропорционально их
 * размеру (±1 пара), а при увеличении N прежняя выборка сохраняется целиком.
 */
export function samplePairIds(corpus: Corpus, size: number, seed: number): string[] {
  const random = mulberry32(seed);
  const byText = new Map<string, string[]>();
  for (const pair of corpus.pairs) {
    const list = byText.get(pair.text_id) ?? [];
    list.push(pair.id);
    byText.set(pair.text_id, list);
  }
  const keyed: { id: string; key: number }[] = [];
  for (const ids of byText.values()) {
    const order = shuffle(ids, random);
    const offset = random();
    order.forEach((id, k) => {
      keyed.push({ id, key: (k + offset) / order.length });
    });
  }
  keyed.sort((a, b) => a.key - b.key || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return keyed.slice(0, Math.max(0, size)).map((k) => k.id);
}

/** Сколько пар выборки приходится на каждый текст (в порядке текстов корпуса). */
export function sampleByText(
  corpus: Corpus,
  ids: readonly string[],
): { textId: string; title: string; sampled: number; total: number }[] {
  const chosen = new Set(ids);
  return corpus.texts.map((t) => {
    const pairs = corpus.pairs.filter((p) => p.text_id === t.id);
    return {
      textId: t.id,
      title: t.title,
      sampled: pairs.filter((p) => chosen.has(p.id)).length,
      total: pairs.length,
    };
  });
}

/* ─── Создание и изменение проверки ────────────────────────────────────── */

export function newGoldFile(
  corpus: Corpus,
  options: { annotator: string; size: number; seed: number },
  now: string,
): GoldFile {
  const size = Math.min(Math.max(1, Math.round(options.size)), corpus.pairs.length);
  return {
    format: GOLD_FORMAT,
    version: GOLD_VERSION,
    annotator: options.annotator.trim(),
    created_at: now,
    updated_at: now,
    corpus: { generated_at: corpus.generated_at, alignment_method: corpus.alignment_method },
    sample: {
      seed: options.seed,
      size,
      strategy: 'proportional',
      pair_ids: samplePairIds(corpus, size, options.seed),
    },
    pairs: [],
  };
}

/**
 * Изменить объём выборки (тот же seed): при увеличении прежние пары остаются в начале
 * списка. Уже сделанные проверки не удаляются, даже если пара выпала из выборки.
 */
export function resizeSample(gold: GoldFile, corpus: Corpus, size: number, now: string): GoldFile {
  const clamped = Math.min(Math.max(1, Math.round(size)), corpus.pairs.length);
  return {
    ...gold,
    updated_at: now,
    sample: {
      ...gold.sample,
      size: clamped,
      pair_ids: samplePairIds(corpus, clamped, gold.sample.seed),
    },
  };
}

function snapshot(pair: Pair, lang: Lang): ItemReview[] {
  switch (lang) {
    case 'en':
      return pair.annotations.en.map((a) => ({
        id: a.id,
        auto: {
          kind: 'article',
          start: a.start,
          end: a.end,
          text: a.text,
          value: a.value,
          head: a.head ? { start: a.head.start, end: a.head.end, text: a.head.text } : null,
        },
        verdict: null,
        correction: null,
      }));
    case 'zh':
      return pair.annotations.zh.map((a) => ({
        id: a.id,
        auto: {
          kind: 'classifier',
          start: a.start,
          end: a.end,
          text: a.text,
          value: a.value,
          det: { start: a.det.start, end: a.det.end, text: a.det.text },
          head: a.head ? { start: a.head.start, end: a.head.end, text: a.head.text } : null,
        },
        verdict: null,
        correction: null,
      }));
    case 'ru':
      return pair.annotations.ru.map((a) => ({
        id: a.id,
        auto: {
          kind: 'case',
          start: a.start,
          end: a.end,
          text: a.text,
          lemma: a.lemma,
          case: a.case,
          number: a.number,
        },
        verdict: null,
        correction: null,
      }));
  }
}

export function emptyReview(pair: Pair): GoldPair {
  return {
    id: pair.id,
    text_id: pair.text_id,
    reviewed_at: null,
    text: { en: pair.en, zh: pair.zh, ru: pair.ru },
    sentences: {
      en: [...pair.sentences.en],
      zh: [...pair.sentences.zh],
      ru: [...pair.sentences.ru],
    },
    alignment: { zh: { verdict: null, links: [] }, ru: { verdict: null, links: [] } },
    phenomena: {
      en: { mode: null, items: snapshot(pair, 'en'), missed: [] },
      zh: { mode: null, items: snapshot(pair, 'zh'), missed: [] },
      ru: { mode: null, items: snapshot(pair, 'ru'), missed: [] },
    },
    comment: '',
  };
}

export function findReview(gold: GoldFile, pairId: string): GoldPair | undefined {
  return gold.pairs.find((p) => p.id === pairId);
}

/** Все связи «предложение EN × предложение ZH/RU» автоматического выравнивания пары. */
export function autoLinks(review: GoldPair, lang: TargetLang): [number, number][] {
  const links: [number, number][] = [];
  for (const e of review.sentences.en) {
    for (const t of review.sentences[lang]) links.push([e, t]);
  }
  return links;
}

export function setAlignmentVerdict(
  review: GoldPair,
  lang: TargetLang,
  verdict: Verdict,
): GoldPair {
  const current = review.alignment[lang];
  const links =
    verdict === 'corrected'
      ? current.links.length > 0
        ? current.links
        : autoLinks(review, lang)
      : [];
  return { ...review, alignment: { ...review.alignment, [lang]: { verdict, links } } };
}

export function toggleLink(
  review: GoldPair,
  lang: TargetLang,
  en: number,
  target: number,
): GoldPair {
  const current = review.alignment[lang];
  const exists = current.links.some(([e, t]) => e === en && t === target);
  const links: [number, number][] = exists
    ? current.links.filter(([e, t]) => !(e === en && t === target))
    : [...current.links, [en, target]];
  links.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return {
    ...review,
    alignment: { ...review.alignment, [lang]: { verdict: 'corrected', links } },
  };
}

function updateLang(review: GoldPair, lang: Lang, next: LangReview): GoldPair {
  return { ...review, phenomena: { ...review.phenomena, [lang]: next } };
}

/** «Всё верно» — все пометки языка верны, пропусков нет; «по одной» — подробная проверка. */
export function setLangMode(review: GoldPair, lang: Lang, mode: LangMode): GoldPair {
  const current = review.phenomena[lang];
  if (mode === 'all-correct') {
    return updateLang(review, lang, {
      mode,
      items: current.items.map((item) => ({ ...item, verdict: 'correct', correction: null })),
      missed: [],
    });
  }
  return updateLang(review, lang, { ...current, mode });
}

export function defaultFix(auto: Snapshot): Fix {
  switch (auto.kind) {
    case 'article':
      return { head: auto.head?.text ?? '' };
    case 'classifier':
      return { classifier: auto.text, head: auto.head?.text ?? '' };
    case 'case':
      return { case: auto.case, lemma: auto.lemma };
  }
}

export function setItemVerdict(
  review: GoldPair,
  lang: Lang,
  index: number,
  verdict: Verdict,
): GoldPair {
  const current = review.phenomena[lang];
  const items = current.items.map((item, i) =>
    i === index
      ? {
          ...item,
          verdict,
          correction: verdict === 'corrected' ? (item.correction ?? defaultFix(item.auto)) : null,
        }
      : item,
  );
  return updateLang(review, lang, { ...current, mode: 'itemized', items });
}

export function setItemFix(review: GoldPair, lang: Lang, index: number, fix: Fix): GoldPair {
  const current = review.phenomena[lang];
  const items = current.items.map((item, i) =>
    i === index ? { ...item, verdict: 'corrected' as const, correction: fix } : item,
  );
  return updateLang(review, lang, { ...current, mode: 'itemized', items });
}

export function defaultMissedFix(lang: Lang, span: GoldSpan): Fix {
  switch (lang) {
    case 'en':
      return { head: '' };
    case 'zh':
      return { head: '' };
    case 'ru':
      return { case: 'nomn', lemma: span.text.toLocaleLowerCase('ru') };
  }
}

export function addMissed(review: GoldPair, lang: Lang, item: MissedItem): GoldPair {
  const current = review.phenomena[lang];
  const missed = [...current.missed.filter((m) => m.start !== item.start), item].sort(
    (a, b) => a.start - b.start,
  );
  return updateLang(review, lang, { ...current, mode: 'itemized', missed });
}

export function updateMissed(review: GoldPair, lang: Lang, index: number, fix: Fix): GoldPair {
  const current = review.phenomena[lang];
  const missed = current.missed.map((m, i) => (i === index ? { ...m, ...fix } : m));
  return updateLang(review, lang, { ...current, missed });
}

export function removeMissed(review: GoldPair, lang: Lang, index: number): GoldPair {
  const current = review.phenomena[lang];
  return updateLang(review, lang, {
    ...current,
    missed: current.missed.filter((_, i) => i !== index),
  });
}

/* ─── Статус и прогресс ────────────────────────────────────────────────── */

export function alignmentDone(a: AlignmentReview): boolean {
  return a.verdict !== null && (a.verdict !== 'corrected' || a.links.length > 0);
}

export function langDone(l: LangReview): boolean {
  if (l.mode === 'all-correct') return true;
  return l.mode === 'itemized' && l.items.every((item) => item.verdict !== null);
}

export type PairStatus = 'empty' | 'partial' | 'done';

export function pairStatus(review: GoldPair | undefined): PairStatus {
  if (!review) return 'empty';
  const parts = [
    ...TARGET_LANGS.map((l) => alignmentDone(review.alignment[l])),
    ...(['en', 'zh', 'ru'] as const).map((l) => langDone(review.phenomena[l])),
  ];
  if (parts.every(Boolean)) return 'done';
  const touched =
    TARGET_LANGS.some((l) => review.alignment[l].verdict !== null) ||
    (['en', 'zh', 'ru'] as const).some((l) => review.phenomena[l].mode !== null) ||
    review.comment.trim() !== '';
  return touched ? 'partial' : 'empty';
}

export function progress(gold: GoldFile): { done: number; partial: number; total: number } {
  const byId = new Map(gold.pairs.map((p) => [p.id, p]));
  let done = 0;
  let partial = 0;
  for (const id of gold.sample.pair_ids) {
    const status = pairStatus(byId.get(id));
    if (status === 'done') done += 1;
    else if (status === 'partial') partial += 1;
  }
  return { done, partial, total: gold.sample.pair_ids.length };
}

/** Сохранить проверку пары в файле (пустая проверка удаляется). */
export function upsertReview(gold: GoldFile, review: GoldPair, now: string): GoldFile {
  const status = pairStatus(review);
  const others = gold.pairs.filter((p) => p.id !== review.id);
  const pairs = status === 'empty' ? others : [...others, { ...review, reviewed_at: now }];
  const order = new Map(gold.sample.pair_ids.map((id, i) => [id, i]));
  pairs.sort(
    (a, b) =>
      (order.get(a.id) ?? Number.MAX_SAFE_INTEGER) - (order.get(b.id) ?? Number.MAX_SAFE_INTEGER) ||
      (a.id < b.id ? -1 : 1),
  );
  return { ...gold, updated_at: now, pairs };
}

/** Пары, проверенные на другой версии текста (после пересборки корпуса текст изменился). */
export function staleReviews(gold: GoldFile, corpus: Corpus): string[] {
  const byId = new Map(corpus.pairs.map((p) => [p.id, p]));
  return gold.pairs
    .filter((r) => {
      const pair = byId.get(r.id);
      return pair?.en !== r.text.en || pair.zh !== r.text.zh || pair.ru !== r.text.ru;
    })
    .map((r) => r.id);
}

/* ─── Окно предложений для исправления выравнивания ────────────────────── */

function around(ids: readonly number[], count: number, anchor: number): number[] {
  if (count === 0) return [];
  const from = ids.length > 0 ? Math.min(...ids) : anchor;
  const to = ids.length > 0 ? Math.max(...ids) : anchor - 1;
  const result: number[] = [];
  for (let i = Math.max(0, from - 1); i <= Math.min(count - 1, to + 1); i += 1) result.push(i);
  return result;
}

/** Предложения пары и по одному соседнему с каждой стороны — для матрицы соответствий. */
export function alignmentWindow(
  corpus: Corpus,
  pair: Pair,
  lang: TargetLang,
): { en: number[]; target: number[] } {
  const text = corpus.texts.find((t) => t.id === pair.text_id);
  if (!text) return { en: pair.sentences.en, target: pair.sentences[lang] };
  // Если во втором языке пара пуста (1–0), окно строится вокруг предыдущей пары.
  let anchor = 0;
  for (const p of corpus.pairs) {
    if (p.text_id !== pair.text_id) continue;
    if (p.id === pair.id) break;
    if (p.sentences[lang].length > 0) anchor = Math.max(...p.sentences[lang]) + 1;
  }
  return {
    en: around(pair.sentences.en, text.sentences.en.length, anchor),
    target: around(pair.sentences[lang], text.sentences[lang].length, anchor),
  };
}

/* ─── Токены для отметки пропусков ─────────────────────────────────────── */

const HAN = /\p{Script=Han}/u;
const WORD = /[\p{L}\p{N}]/u;
const JOINER = /['’-]/u;

/** EN/RU — слова, ZH — отдельные иероглифы. Позиции — в кодовых точках. */
export function tokenize(text: string, lang: Lang): GoldSpan[] {
  const chars = Array.from(text);
  const tokens: GoldSpan[] = [];
  if (lang === 'zh') {
    chars.forEach((ch, i) => {
      if (HAN.test(ch) || /\p{N}/u.test(ch)) tokens.push({ start: i, end: i + 1, text: ch });
    });
    return tokens;
  }
  let i = 0;
  while (i < chars.length) {
    if (!WORD.test(chars[i] ?? '')) {
      i += 1;
      continue;
    }
    let j = i + 1;
    while (
      j < chars.length &&
      (WORD.test(chars[j] ?? '') || (JOINER.test(chars[j] ?? '') && WORD.test(chars[j + 1] ?? '')))
    ) {
      j += 1;
    }
    tokens.push({ start: i, end: j, text: chars.slice(i, j).join('') });
    i = j;
  }
  return tokens;
}

export function spanText(text: string, start: number, end: number): string {
  return Array.from(text).slice(start, end).join('');
}

/* ─── Проверка формы файла при импорте ─────────────────────────────────── */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isLangReview(value: unknown): value is LangReview {
  return (
    isRecord(value) &&
    (value.mode === null || value.mode === 'all-correct' || value.mode === 'itemized') &&
    Array.isArray(value.items) &&
    Array.isArray(value.missed)
  );
}

function isGoldPair(value: unknown): value is GoldPair {
  if (!isRecord(value)) return false;
  const { alignment, phenomena, text, sentences } = value;
  return (
    typeof value.id === 'string' &&
    typeof value.text_id === 'string' &&
    isRecord(text) &&
    isRecord(sentences) &&
    isRecord(alignment) &&
    isRecord(alignment.zh) &&
    isRecord(alignment.ru) &&
    isRecord(phenomena) &&
    isLangReview(phenomena.en) &&
    isLangReview(phenomena.zh) &&
    isLangReview(phenomena.ru)
  );
}

export function isGoldFile(value: unknown): value is GoldFile {
  return (
    isRecord(value) &&
    value.format === GOLD_FORMAT &&
    typeof value.version === 'number' &&
    value.version <= GOLD_VERSION &&
    isRecord(value.sample) &&
    Array.isArray(value.sample.pair_ids) &&
    value.sample.pair_ids.every((id) => typeof id === 'string') &&
    Array.isArray(value.pairs) &&
    value.pairs.every(isGoldPair)
  );
}

export function serializeGold(gold: GoldFile): string {
  return `${JSON.stringify(gold, null, 2)}\n`;
}
