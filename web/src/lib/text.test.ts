import { describe, expect, it } from 'vitest';

import type { Lang } from '../data/types';
import { codePointConverter, detectLang, findAll, queryRegExp, segmentize } from './text';

function must(query: string, lang: Lang, exact = false): RegExp {
  const re = queryRegExp(query, lang, exact);
  if (!re) throw new Error(`нет регулярного выражения для «${query}»`);
  return re;
}

describe('queryRegExp', () => {
  it('ищет с начала слова и расширяет совпадение до конца слова', () => {
    const text = 'Она купила книгу, а не учебник-книжку.';
    const hits = findAll(text, must('книг', 'ru'), true).map((h) => text.slice(h.start, h.end));
    expect(hits).toEqual(['книгу']);
  });

  it('не находит запрос внутри слова', () => {
    const re = must('he', 'en', false);
    expect(findAll('The hen and the cat', re)).toEqual([{ start: 4, end: 6 }]);
  });

  it('режим «целое слово»', () => {
    const re = must('book', 'en', true);
    expect(findAll('a book, two books', re)).toEqual([{ start: 2, end: 6 }]);
  });

  it('е и ё не различаются, регистр не важен', () => {
    const re = must('ещё', 'ru', false);
    expect(findAll('Ещё раз и еще раз', re)).toHaveLength(2);
  });

  it('китайский — поиск подстроки, латиница в ZH не ищется', () => {
    expect(findAll('三本书和一本书', must('本书', 'zh', false))).toHaveLength(2);
    expect(queryRegExp('book', 'zh', false)).toBeNull();
    expect(queryRegExp('书', 'en', false)).toBeNull();
  });

  it('спецсимволы экранируются', () => {
    expect(() => queryRegExp('a (b', 'en', false)).not.toThrow();
  });
});

describe('detectLang', () => {
  it('определяет письменность запроса', () => {
    expect(detectLang('книга')).toBe('ru');
    expect(detectLang('本')).toBe('zh');
    expect(detectLang('the')).toBe('en');
    expect(detectLang('123')).toBeNull();
  });
});

describe('segmentize', () => {
  it('делит текст на отрезки с одинаковой подсветкой', () => {
    const segments = segmentize('abcdef', [
      { start: 1, end: 4, kind: 'query', lang: 'en' },
      { start: 3, end: 5, kind: 'ann', lang: 'en' },
    ]);
    expect(segments.map((s) => [s.text, s.marks.length])).toEqual([
      ['a', 0],
      ['bc', 1],
      ['d', 2],
      ['e', 1],
      ['f', 0],
    ]);
  });

  it('игнорирует некорректные диапазоны', () => {
    expect(segmentize('abc', [{ start: 2, end: 9, kind: 'query', lang: 'en' }])).toEqual([
      { text: 'abc', marks: [] },
    ]);
  });
});

describe('codePointConverter', () => {
  it('переводит позиции кодовых точек в UTF-16 при суррогатных парах', () => {
    const convert = codePointConverter('𠀀书');
    expect(convert(1)).toBe(2);
    expect(convert(2)).toBe(3);
    expect(codePointConverter('书')(1)).toBe(1);
  });
});
