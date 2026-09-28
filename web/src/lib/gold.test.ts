import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import type { Corpus, Pair } from '../data/types';
import {
  addMissed,
  alignmentWindow,
  emptyReview,
  isGoldFile,
  newGoldFile,
  pairStatus,
  progress,
  resizeSample,
  sampleByText,
  samplePairIds,
  setAlignmentVerdict,
  setItemFix,
  setItemVerdict,
  setLangMode,
  staleReviews,
  toggleLink,
  tokenize,
  upsertReview,
} from './gold';
import { CORPUS, PAIR_BOOK, PAIR_TEA } from './testFixtures';

const NOW = '2026-09-28T10:00:00Z';

/** Синтетический корпус: 3 текста по 10, 20 и 30 пар (только id и text_id важны). */
function syntheticCorpus(): Corpus {
  const pairs: Pair[] = [];
  const texts = (
    [
      ['a', 10],
      ['b', 20],
      ['c', 30],
    ] as const
  ).map(([id, n]) => {
    for (let k = 1; k <= n; k += 1) {
      pairs.push({ ...PAIR_BOOK, id: `${id}-${String(k).padStart(3, '0')}`, text_id: id });
    }
    const [base] = CORPUS.texts;
    if (!base) throw new Error('нет текста в фикстуре');
    return { ...base, id, pairs: n };
  });
  return { ...CORPUS, texts, pairs };
}

interface CrossCheck {
  pairs: { id: string; text_id: string }[];
  cases: { seed: number; size: number; expected: string[] }[];
}

describe('выборка для проверки', () => {
  const corpus = syntheticCorpus();

  it('воспроизводится по seed и не содержит повторов', () => {
    const a = samplePairIds(corpus, 12, 7);
    expect(a).toEqual(samplePairIds(corpus, 12, 7));
    expect(new Set(a).size).toBe(12);
    expect(samplePairIds(corpus, 12, 8)).not.toEqual(a);
  });

  it('распределяет пары пропорционально размеру текстов (±1)', () => {
    const ids = samplePairIds(corpus, 12, 2026);
    const counts = sampleByText(corpus, ids).map((r) => r.sampled);
    // 10 : 20 : 30 → 2 : 4 : 6
    expect(counts[0]).toBeGreaterThanOrEqual(1);
    expect(counts[0]).toBeLessThanOrEqual(3);
    expect(counts[1]).toBeGreaterThanOrEqual(3);
    expect(counts[1]).toBeLessThanOrEqual(5);
    expect(counts[2]).toBeGreaterThanOrEqual(5);
    expect(counts[2]).toBeLessThanOrEqual(7);
  });

  it('при увеличении N сохраняет прежнюю выборку', () => {
    const small = samplePairIds(corpus, 10, 99);
    const large = samplePairIds(corpus, 25, 99);
    expect(large.slice(0, 10)).toEqual(small);
  });

  it('совпадает с реализацией на Python (pipeline/gold.py)', () => {
    const raw = readFileSync(
      new URL('../../../pipeline/tests/fixtures/sample_crosscheck.json', import.meta.url),
      'utf-8',
    );
    const data = JSON.parse(raw) as CrossCheck;
    const shared: Corpus = {
      ...CORPUS,
      pairs: data.pairs.map((p) => ({ ...PAIR_BOOK, ...p })),
    };
    for (const c of data.cases) {
      expect(samplePairIds(shared, c.size, c.seed)).toEqual(c.expected);
    }
  });
});

describe('проверка пары', () => {
  it('новая проверка пуста, «всё верно» + выравнивание завершают пару', () => {
    let review = emptyReview(PAIR_BOOK);
    expect(pairStatus(review)).toBe('empty');
    review = setAlignmentVerdict(review, 'zh', 'correct');
    expect(pairStatus(review)).toBe('partial');
    review = setAlignmentVerdict(review, 'ru', 'correct');
    for (const lang of ['en', 'zh', 'ru'] as const)
      review = setLangMode(review, lang, 'all-correct');
    expect(pairStatus(review)).toBe('done');
    expect(review.phenomena.ru.items.every((i) => i.verdict === 'correct')).toBe(true);
  });

  it('при подробной проверке пара не завершена, пока не оценены все пометки', () => {
    let review = setAlignmentVerdict(emptyReview(PAIR_BOOK), 'zh', 'correct');
    review = setAlignmentVerdict(review, 'ru', 'wrong');
    review = setLangMode(review, 'en', 'all-correct');
    review = setLangMode(review, 'zh', 'all-correct');
    review = setItemVerdict(review, 'ru', 0, 'correct');
    expect(pairStatus(review)).toBe('partial');
    review = setItemVerdict(review, 'ru', 1, 'corrected');
    expect(review.phenomena.ru.items[1]?.correction).toEqual({ case: 'accs', lemma: 'книга' });
    review = setItemFix(review, 'ru', 1, { case: 'gent', lemma: 'книга' });
    review = setItemVerdict(review, 'ru', 2, 'wrong');
    expect(pairStatus(review)).toBe('done');
  });

  it('исправление выравнивания начинается с автоматических связей и требует хотя бы одну', () => {
    let review = setAlignmentVerdict(emptyReview(PAIR_BOOK), 'zh', 'corrected');
    expect(review.alignment.zh.links).toEqual([[0, 0]]);
    review = toggleLink(review, 'zh', 0, 1);
    expect(review.alignment.zh.links).toEqual([
      [0, 0],
      [0, 1],
    ]);
    review = toggleLink(toggleLink(review, 'zh', 0, 0), 'zh', 0, 1);
    expect(review.alignment.zh.links).toEqual([]);
    review = setAlignmentVerdict(review, 'ru', 'correct');
    for (const lang of ['en', 'zh', 'ru'] as const)
      review = setLangMode(review, lang, 'all-correct');
    expect(pairStatus(review)).toBe('partial');
  });

  it('пропуск добавляется один раз на позицию и переводит язык в подробный режим', () => {
    let review = emptyReview(PAIR_TEA);
    review = addMissed(review, 'zh', { start: 2, end: 3, text: '了', head: '' });
    review = addMissed(review, 'zh', { start: 2, end: 3, text: '了', head: '茶' });
    expect(review.phenomena.zh.mode).toBe('itemized');
    expect(review.phenomena.zh.missed).toEqual([{ start: 2, end: 3, text: '了', head: '茶' }]);
  });
});

describe('файл gold.json', () => {
  it('сохраняет только начатые пары и считает прогресс по выборке', () => {
    let gold = newGoldFile(CORPUS, { annotator: ' Эксперт ', size: 5, seed: 1 }, NOW);
    expect(gold.sample.size).toBe(2); // не больше пар в корпусе
    expect(gold.annotator).toBe('Эксперт');
    gold = upsertReview(gold, emptyReview(PAIR_BOOK), NOW);
    expect(gold.pairs).toHaveLength(0);
    let review = setAlignmentVerdict(emptyReview(PAIR_BOOK), 'zh', 'correct');
    gold = upsertReview(gold, review, NOW);
    expect(progress(gold)).toEqual({ done: 0, partial: 1, total: 2 });
    review = setAlignmentVerdict(review, 'ru', 'correct');
    for (const lang of ['en', 'zh', 'ru'] as const)
      review = setLangMode(review, lang, 'all-correct');
    gold = upsertReview(gold, review, NOW);
    expect(progress(gold)).toEqual({ done: 1, partial: 0, total: 2 });
    expect(gold.pairs[0]?.reviewed_at).toBe(NOW);
    expect(isGoldFile(JSON.parse(JSON.stringify(gold)))).toBe(true);
  });

  it('увеличение выборки сохраняет прежние пары и проверки', () => {
    const corpus = syntheticCorpus();
    let gold = newGoldFile(corpus, { annotator: '', size: 5, seed: 3 }, NOW);
    const first = gold.sample.pair_ids;
    const pair = corpus.pairs.find((p) => p.id === first[0]);
    if (!pair) throw new Error('пара не найдена');
    gold = upsertReview(gold, setAlignmentVerdict(emptyReview(pair), 'zh', 'correct'), NOW);
    const bigger = resizeSample(gold, corpus, 12, NOW);
    expect(bigger.sample.pair_ids.slice(0, 5)).toEqual(first);
    expect(bigger.pairs).toHaveLength(1);
    expect(resizeSample(gold, corpus, 999, NOW).sample.size).toBe(60);
  });

  it('отклоняет чужие и повреждённые файлы', () => {
    expect(isGoldFile({})).toBe(false);
    expect(isGoldFile({ format: 'corpus-gold', version: 99, sample: { pair_ids: [] } })).toBe(
      false,
    );
    const gold = newGoldFile(CORPUS, { annotator: '', size: 2, seed: 1 }, NOW);
    expect(isGoldFile({ ...gold, pairs: [{ id: 1 }] })).toBe(false);
  });

  it('находит пары, текст которых изменился после пересборки', () => {
    let gold = newGoldFile(CORPUS, { annotator: '', size: 2, seed: 1 }, NOW);
    gold = upsertReview(gold, setAlignmentVerdict(emptyReview(PAIR_BOOK), 'zh', 'wrong'), NOW);
    expect(staleReviews(gold, CORPUS)).toEqual([]);
    const changed: Corpus = {
      ...CORPUS,
      pairs: [{ ...PAIR_BOOK, ru: 'Другой текст.' }, PAIR_TEA],
    };
    expect(staleReviews(gold, changed)).toEqual(['t-001']);
  });
});

describe('вспомогательные функции', () => {
  it('делит текст на слова (EN/RU) и иероглифы (ZH) в кодовых точках', () => {
    expect(tokenize("Don't stop, Anna-Maria!", 'en').map((t) => t.text)).toEqual([
      "Don't",
      'stop',
      'Anna-Maria',
    ]);
    expect(tokenize('一本书。', 'zh')).toEqual([
      { start: 0, end: 1, text: '一' },
      { start: 1, end: 2, text: '本' },
      { start: 2, end: 3, text: '书' },
    ]);
    // Символ вне BMP занимает одну кодовую точку.
    expect(tokenize('𠀋书', 'zh').map((t) => [t.start, t.end])).toEqual([
      [0, 1],
      [1, 2],
    ]);
  });

  it('окно выравнивания включает соседние предложения', () => {
    expect(alignmentWindow(CORPUS, PAIR_BOOK, 'zh')).toEqual({ en: [0, 1], target: [0, 1] });
    expect(alignmentWindow(CORPUS, PAIR_TEA, 'ru')).toEqual({ en: [0, 1], target: [0, 1] });
  });
});
