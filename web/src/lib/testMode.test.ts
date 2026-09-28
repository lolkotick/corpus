import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import type { Corpus } from '../data/types';
import { isCorpus } from '../data/validate';
import {
  attemptScore,
  attemptsToCsv,
  buildTestSets,
  CSV_COLUMNS,
  csvFileName,
  newAttempt,
  recordAnswer,
  setProfile,
} from './testMode';

function loadCorpus(): Corpus {
  const raw: unknown = JSON.parse(
    readFileSync(new URL('../../public/data/corpus.json', import.meta.url), 'utf-8'),
  );
  if (!isCorpus(raw)) throw new Error('corpus.json повреждён');
  return raw;
}

const corpus = loadCorpus();
const sets = buildTestSets(corpus);

describe('наборы теста', () => {
  it('по 5 заданий на явление в каждом наборе, одинаковые при каждом построении', () => {
    for (const set of [sets.A, sets.B]) {
      expect(setProfile(set).byKind).toEqual({ article: 5, classifier: 5, case: 5 });
    }
    const again = buildTestSets(corpus);
    expect(again.A.items.map((i) => i.id)).toEqual(sets.A.items.map((i) => i.id));
    expect(again.A.id).toBe(sets.A.id);
    expect(sets.A.id).toMatch(/^A-[0-9a-f]{6}$/);
  });

  it('наборы не пересекаются по предложениям и сопоставимы по уровню', () => {
    const pairsA = new Set(sets.A.items.map((i) => i.pairId));
    const pairsB = new Set(sets.B.items.map((i) => i.pairId));
    expect(pairsA.size).toBe(sets.A.items.length);
    expect([...pairsA].filter((p) => pairsB.has(p))).toEqual([]);
    const diff = Math.abs(setProfile(sets.A).meanLevel - setProfile(sets.B).meanLevel);
    expect(diff).toBeLessThanOrEqual(0.5);
  });

  it('явления чередуются', () => {
    expect(sets.A.items.slice(0, 3).map((i) => i.kind)).toEqual(['article', 'classifier', 'case']);
  });
});

describe('ответы и CSV', () => {
  const now = '2026-09-28T10:00:00.000Z';

  it('засчитывает ответ, время и баллы по явлениям', () => {
    let attempt = newAttempt(' Участник 1 ', 'pre', sets.A, now);
    expect(attempt.participant).toBe('Участник 1');
    const [first, second] = sets.A.items;
    if (!first || !second) throw new Error('пустой набор');
    attempt = recordAnswer(attempt, first, first.answer, 4200.4);
    attempt = recordAnswer(attempt, second, 'неверно', 1000);
    const score = attemptScore(attempt);
    expect(score.correct).toBe(1);
    expect(score.total).toBe(2);
    expect(score.seconds).toBeCloseTo(5.2);
    expect(attempt.answers[0]?.ms).toBe(4200);
  });

  it('CSV: BOM, «;», экранирование и строка на ответ', () => {
    let attempt = newAttempt('Анна; "А"', 'post', sets.B, now);
    const item = sets.B.items[0];
    if (!item) throw new Error('пустой набор');
    attempt = recordAnswer(attempt, item, 'the', 900);
    attempt = { ...attempt, finished_at: now };
    const csv = attemptsToCsv([attempt]);
    expect(csv.startsWith('﻿')).toBe(true);
    const lines = csv.slice(1).trimEnd().split('\r\n');
    expect(lines[0]).toBe(CSV_COLUMNS.join(';'));
    expect(lines).toHaveLength(2);
    expect(lines[1]?.startsWith('"Анна; ""А""";post;')).toBe(true);
    expect(csvFileName([attempt], now)).toBe('test_Анна_А__2026-09-28.csv');
  });
});

describe('наборы теста и импортированные данные', () => {
  it('строятся только по учебным текстам', () => {
    const raw: unknown = JSON.parse(
      readFileSync(new URL('../../public/data/corpus.json', import.meta.url), 'utf-8'),
    );
    if (!isCorpus(raw)) throw new Error('corpus.json повреждён');
    const imported = new Set(raw.pairs.filter((p) => p.origin).map((p) => p.id));
    const sets = buildTestSets(raw);
    const pairIds = [...sets.A.items, ...sets.B.items].map((i) => i.pairId);
    expect(pairIds.some((id) => imported.has(id))).toBe(false);
    // Добавление импортированных пар не меняет наборы.
    const textbookOnly = { ...raw, pairs: raw.pairs.filter((p) => !p.origin) };
    expect(buildTestSets(textbookOnly).A.items.map((i) => i.id)).toEqual(
      sets.A.items.map((i) => i.id),
    );
  });
});
