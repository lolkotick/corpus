import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import type { Corpus } from '../data/types';
import { isCorpus } from '../data/validate';
import {
  allItems,
  buildExerciseSet,
  checkAnswer,
  classifierContext,
  distractors,
  isTrivialCase,
  mulberry32,
  resolveItems,
  type ExerciseItem,
} from './exercises';

function loadCorpus(): Corpus {
  const raw: unknown = JSON.parse(
    readFileSync(new URL('../../public/data/corpus.json', import.meta.url), 'utf-8'),
  );
  if (!isCorpus(raw)) throw new Error('corpus.json повреждён');
  return raw;
}

const corpus = loadCorpus();
const pairById = new Map(corpus.pairs.map((p) => [p.id, p]));

function sentence(item: ExerciseItem): string {
  return `${item.before}${item.answer}${item.after}`;
}

describe('набор упражнений', () => {
  it('воспроизводится по seed и меняется при другом seed', () => {
    const settings = { kind: 'mixed' as const, level: '' as const, count: 15 };
    const a = buildExerciseSet(corpus, settings, 42).map((i) => i.id);
    const b = buildExerciseSet(corpus, settings, 42).map((i) => i.id);
    const c = buildExerciseSet(corpus, settings, 43).map((i) => i.id);
    expect(a).toEqual(b);
    expect(a).not.toEqual(c);
    expect(a).toHaveLength(15);
  });

  it('учитывает явление, уровень и берёт не больше одного задания на пару', () => {
    const set = buildExerciseSet(corpus, { kind: 'case', level: 'A2', count: 20 }, 7);
    expect(set.every((i) => i.kind === 'case' && i.level === 'A2')).toBe(true);
    expect(new Set(set.map((i) => i.pairId)).size).toBe(set.length);
  });

  it('смешанный набор чередует явления', () => {
    const kinds = buildExerciseSet(corpus, { kind: 'mixed', level: '', count: 9 }, 3).map(
      (i) => i.kind,
    );
    expect(new Set(kinds.slice(0, 3)).size).toBe(3);
  });

  it('тривиальных падежных заданий (форма = лемма) не больше 20 %', () => {
    const set = buildExerciseSet(corpus, { kind: 'case', level: '', count: 20 }, 11);
    const trivial = set.filter((item) => {
      const pair = pairById.get(item.pairId);
      const ann = pair?.annotations.ru.find((a) => `${pair.id}:${a.id}` === item.id);
      return ann ? isTrivialCase(ann) : false;
    });
    expect(trivial.length).toBeLessThanOrEqual(4);
  });

  it('resolveItems восстанавливает задания по id', () => {
    const set = buildExerciseSet(corpus, { kind: 'classifier', level: '', count: 5 }, 5);
    const restored = resolveItems(
      corpus,
      5,
      set.map((i) => i.id),
    );
    expect(restored).toEqual(set);
  });
});

describe('задания', () => {
  const items = allItems(corpus, 1);

  it('пропуск вырезан из настоящего предложения корпуса', () => {
    for (const item of items) {
      expect(pairById.get(item.pairId)?.[item.lang]).toBe(sentence(item));
    }
  });

  it('артикли: варианты a / an / the, ответ среди них', () => {
    const articles = items.filter((i) => i.kind === 'article');
    expect(articles.length).toBeGreaterThan(100);
    for (const item of articles) {
      expect(item.options.map((o) => o.toLowerCase())).toEqual(['a', 'an', 'the']);
      expect(item.options).toContain(item.answer);
    }
  });

  it('量词: четыре разных варианта, ответ среди них', () => {
    const zh = items.filter((i) => i.kind === 'classifier');
    expect(zh.length).toBeGreaterThan(50);
    for (const item of zh) {
      expect(new Set(item.options).size).toBe(4);
      expect(item.options).toContain(item.answer);
    }
  });

  it('отвлекающие 量词 не встречаются с этим существительным в корпусе', () => {
    const ctx = classifierContext(corpus);
    const random = mulberry32(9);
    for (const noun of ['书', '桌子', '茶', '人']) {
      const used = ctx.usedWith.get(noun) ?? new Set<string>();
      const answer = [...used][0] ?? '本';
      for (const wrong of distractors(answer, noun, ctx, random)) {
        expect(used.has(wrong)).toBe(false);
      }
    }
    // 一本书: «部» и «套» тоже возможны с 书 (по списку типичных слов) — их не предлагаем,
    // как и «широкие» 种 / 些, которые грамматичны почти с любым существительным.
    for (let i = 0; i < 20; i += 1) {
      const options = distractors('本', '书', ctx, random);
      expect(options).not.toContain('部');
      expect(options).not.toContain('种');
      expect(options).not.toContain('些');
    }
  });

  it('объяснение содержит правило и ответ', () => {
    const the = items.find((i) => i.kind === 'article' && i.answer.toLowerCase() === 'the');
    expect(the?.explanation).toMatch(/Определённый артикль/);
    const cl = items.find((i) => i.kind === 'classifier');
    expect(cl?.explanation).toContain(cl?.answer ?? '?');
    const ru = items.find((i) => i.kind === 'case' && i.explanation.includes('Предлог'));
    expect(ru?.explanation).toMatch(/падеж/);
  });
});

describe('проверка ответа', () => {
  const caseItem = allItems(corpus, 1).find((i) => i.kind === 'case' && i.answer.includes('ё'));

  it('падеж: регистр, пробелы и ё/е не важны', () => {
    expect(caseItem).toBeDefined();
    if (!caseItem) return;
    expect(checkAnswer(caseItem, `  ${caseItem.answer.toUpperCase()} `)).toBe(true);
    expect(checkAnswer(caseItem, caseItem.answer.replaceAll('ё', 'е'))).toBe(true);
    expect(checkAnswer(caseItem, '')).toBe(false);
    expect(checkAnswer(caseItem, `${caseItem.answer}а`)).toBe(false);
  });

  it('артикль не зависит от регистра, 量词 — точное совпадение', () => {
    const article = allItems(corpus, 1).find((i) => i.kind === 'article' && i.answer === 'The');
    expect(article && checkAnswer(article, 'the')).toBe(true);
    const cl = allItems(corpus, 1).find((i) => i.kind === 'classifier');
    expect(cl && checkAnswer(cl, cl.answer)).toBe(true);
    expect(cl && checkAnswer(cl, cl.options.find((o) => o !== cl.answer) ?? '')).toBe(false);
  });
});
