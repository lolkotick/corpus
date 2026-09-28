import { describe, expect, it } from 'vitest';

import type { Corpus, TatoebaSentence } from '../data/types';
import { compareRegisters, groupByRegister, tatoebaAuthors, unViaOpus } from './sources';
import { CORPUS, PAIR_BOOK as BOOK, PAIR_TEA as TEA } from './testFixtures';

function sentence(id: number, author: string, license = 'CC BY 2.0 FR'): TatoebaSentence {
  return { id, lang: 'eng', author, license, url: `https://tatoeba.org/sentences/show/${id}` };
}

const TEXT = CORPUS.texts[0];
if (!TEXT) throw new Error('нет текста в тестовом корпусе');

const MIXED: Corpus = {
  ...CORPUS,
  texts: [
    { ...TEXT, id: 'un', register: 'официальный', pairs: 1 },
    { ...TEXT, id: 'tatoeba', register: 'бытовой', pairs: 2 },
    { ...TEXT, id: 't', pairs: 3 },
  ],
  pairs: [
    {
      ...BOOK,
      id: 'tatoeba-001',
      origin: {
        source: 'tatoeba',
        en: sentence(1, 'anna'),
        zh: sentence(2, 'li', 'CC0 1.0'),
        ru: sentence(3, ''),
      },
    },
    {
      ...TEA,
      id: 'tatoeba-002',
      origin: {
        source: 'tatoeba',
        en: sentence(1, 'anna'),
        zh: sentence(4, 'anna'),
        ru: sentence(5, 'boris'),
      },
    },
    { ...TEA, id: 'un-001', origin: { source: 'un_corpus', file: 'OPUS UNPC v1.0', line: 7 } },
  ],
};

describe('источники', () => {
  it('группирует тексты по регистрам в заданном порядке', () => {
    const groups = groupByRegister(MIXED);
    expect(groups.map((g) => [g.register, g.pairs])).toEqual([
      ['учебный', 3],
      ['бытовой', 2],
      ['официальный', 1],
    ]);
    expect(compareRegisters('другой', 'официальный')).toBeGreaterThan(0);
  });

  it('считает авторов Tatoeba без повторов предложений', () => {
    const result = tatoebaAuthors(MIXED);
    expect(result.sentences).toBe(5);
    expect(result.cc0).toBe(1);
    expect(result.anonymous).toBe(1);
    expect(result.authors).toEqual([
      { author: 'anna', sentences: 2 },
      { author: 'boris', sentences: 1 },
      { author: 'li', sentences: 1 },
    ]);
  });

  it('распознаёт данные ООН, полученные через OPUS', () => {
    expect(unViaOpus(MIXED)).toBe(true);
    expect(unViaOpus(CORPUS)).toBe(false);
  });
});
