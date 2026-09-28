import { describe, expect, it } from 'vitest';

import { emptyReview, pairStatus } from './gold';
import { acceptRemaining, applyKey, buildRows, nextOpenRow, rowKey } from './reviewRows';
import { PAIR_BOOK } from './testFixtures';

describe('строки проверки', () => {
  it('в кратком режиме — выравнивание и три явления', () => {
    const rows = buildRows(emptyReview(PAIR_BOOK)).map(rowKey);
    expect(rows).toEqual(['align-zh', 'align-ru', 'lang-en', 'lang-zh', 'lang-ru']);
  });

  it('клавиша 2 на явлении раскрывает пометки и строку пропусков', () => {
    const review = applyKey(emptyReview(PAIR_BOOK), { kind: 'lang', lang: 'ru' }, 'wrong');
    expect(buildRows(review).map(rowKey).slice(-5)).toEqual([
      'lang-ru',
      'item-ru-0',
      'item-ru-1',
      'item-ru-2',
      'missed-ru',
    ]);
  });

  it('курсор переходит к следующей неоценённой строке', () => {
    let review = emptyReview(PAIR_BOOK);
    review = applyKey(review, { kind: 'align', lang: 'zh' }, 'correct');
    const rows = buildRows(review);
    expect(nextOpenRow(review, rows, 0)).toBe(1);
    review = applyKey(review, { kind: 'align', lang: 'ru' }, 'correct');
    review = applyKey(review, { kind: 'lang', lang: 'en' }, 'correct');
    expect(nextOpenRow(review, buildRows(review), 1)).toBe(3);
  });

  it('«остальное верно» завершает пару, не трогая уже выставленные ошибки', () => {
    let review = applyKey(emptyReview(PAIR_BOOK), { kind: 'align', lang: 'ru' }, 'wrong');
    review = applyKey(review, { kind: 'lang', lang: 'ru' }, 'wrong');
    review = applyKey(review, { kind: 'item', lang: 'ru', index: 1 }, 'wrong');
    review = acceptRemaining(review);
    expect(pairStatus(review)).toBe('done');
    expect(review.alignment.ru.verdict).toBe('wrong');
    expect(review.phenomena.ru.items.map((i) => i.verdict)).toEqual([
      'correct',
      'wrong',
      'correct',
    ]);
  });
});
