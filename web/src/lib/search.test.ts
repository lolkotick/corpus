import { describe, expect, it } from 'vitest';

import {
  buildKwic,
  DEFAULT_PARAMS,
  leftKey,
  parseParams,
  runSearch,
  serializeParams,
  type SearchParams,
} from './search';
import { CORPUS } from './testFixtures';

function search(patch: Partial<SearchParams>) {
  return runSearch(CORPUS, { ...DEFAULT_PARAMS, ...patch });
}

describe('параметры в адресной строке', () => {
  it('сериализуются и читаются обратно без потерь', () => {
    const params: SearchParams = {
      ...DEFAULT_PARAMS,
      q: 'книга',
      phen: 'case',
      sub: 'gent',
      number: 'plur',
      minScore: 0.3,
      mode: 'kwic',
      sort: 'left',
      kwicLang: 'ru',
      showAnn: false,
    };
    expect(parseParams(serializeParams(params))).toEqual(params);
  });

  it('значения по умолчанию не попадают в адрес, мусор игнорируется', () => {
    expect(serializeParams(DEFAULT_PARAMS).toString()).toBe('');
    const parsed = parseParams(new URLSearchParams('phen=xxx&min=abc&level=Z9&mode=grid'));
    expect(parsed).toEqual(DEFAULT_PARAMS);
  });
});

describe('runSearch', () => {
  it('без запроса и фильтров возвращает все пары', () => {
    expect(search({})).toHaveLength(2);
  });

  it('находит русское слово по лемме и подсвечивает переводы', () => {
    const [result] = search({ q: 'книга' });
    expect(result?.pair.id).toBe('t-001');
    expect(result?.lemmaMatch).toBe(true);
    const equiv = (lang: 'en' | 'zh') =>
      result?.marks[lang]
        .filter((m) => m.kind === 'equiv')
        .map((m) => result.pair[lang].slice(m.start, m.end));
    expect(equiv('en')).toEqual(['book']);
    expect(equiv('zh')).toEqual(['书']);
  });

  it('фильтр явления и конкретного значения', () => {
    expect(search({ phen: 'article', sub: 'definite' }).map((r) => r.pair.id)).toEqual(['t-002']);
    expect(search({ phen: 'classifier', sub: '本' }).map((r) => r.pair.id)).toEqual(['t-001']);
    expect(search({ phen: 'case', sub: 'loct' }).map((r) => r.pair.id)).toEqual(['t-001']);
    expect(search({ phen: 'case', sub: 'gent' })).toHaveLength(0);
  });

  it('фильтры статуса, оценки выравнивания и спорной разметки', () => {
    expect(search({ status: 'checked' }).map((r) => r.pair.id)).toEqual(['t-002']);
    expect(search({ minScore: 0.5 }).map((r) => r.pair.id)).toEqual(['t-001']);
    expect(search({ maxScore: 0.3 }).map((r) => r.pair.id)).toEqual(['t-002']);
    expect(search({ disputed: true }).map((r) => r.pair.id)).toEqual(['t-002']);
  });
});

describe('KWIC', () => {
  it('ставит найденное слово в центр строки', () => {
    const params = { ...DEFAULT_PARAMS, q: 'книг', mode: 'kwic' as const };
    const lines = buildKwic(runSearch(CORPUS, params), params);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toMatchObject({ lang: 'ru', left: 'Анна хотела найти ', keyword: 'книгу' });
  });

  it('без запроса центрирует элементы выбранного явления', () => {
    const params = { ...DEFAULT_PARAMS, phen: 'article' as const, mode: 'kwic' as const };
    const lines = buildKwic(runSearch(CORPUS, params), params);
    expect(lines.map((l) => l.keyword)).toEqual(['a', 'the']);
  });

  it('ключ левого контекста читается справа налево', () => {
    expect(leftKey('…Она взяла две ', 'ru')).toBe('две взяла Она');
    expect(leftKey('她点了一', 'zh')).toBe('一了点她');
  });
});
