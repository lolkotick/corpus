import type { Corpus, TextMeta } from '../data/types';

export const DEFAULT_REGISTER = 'учебный';
export const REGISTER_ORDER = ['учебный', 'бытовой', 'официальный'] as const;

export function registerOf(text: Pick<TextMeta, 'register'> | undefined): string {
  // Пустая строка в meta.json тоже означает «регистр не указан».
  const register = text?.register?.trim();
  return register === undefined || register === '' ? DEFAULT_REGISTER : register;
}

export function compareRegisters(a: string, b: string): number {
  const ia = (REGISTER_ORDER as readonly string[]).indexOf(a);
  const ib = (REGISTER_ORDER as readonly string[]).indexOf(b);
  return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b, 'ru');
}

export interface SourceGroup {
  register: string;
  texts: TextMeta[];
  pairs: number;
}

/** Тексты корпуса по регистрам (учебный → бытовой → официальный). */
export function groupByRegister(corpus: Corpus): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();
  for (const text of corpus.texts) {
    const register = registerOf(text);
    const group = groups.get(register) ?? { register, texts: [], pairs: 0 };
    group.texts.push(text);
    group.pairs += text.pairs;
    groups.set(register, group);
  }
  return [...groups.values()].sort((a, b) => compareRegisters(a.register, b.register));
}

export interface AuthorCount {
  author: string;
  sentences: number;
}

/** Авторы предложений Tatoeba (для указания авторства по CC BY 2.0 FR). */
export function tatoebaAuthors(corpus: Corpus): {
  authors: AuthorCount[];
  sentences: number;
  cc0: number;
  anonymous: number;
} {
  const counts = new Map<string, number>();
  let sentences = 0;
  let cc0 = 0;
  let anonymous = 0;
  const seen = new Set<number>();
  for (const pair of corpus.pairs) {
    const origin = pair.origin;
    if (origin?.source !== 'tatoeba') continue;
    for (const s of [origin.en, origin.zh, origin.ru]) {
      // Одна тройка может разбиться на несколько пар — предложение считаем один раз.
      if (seen.has(s.id)) continue;
      seen.add(s.id);
      sentences += 1;
      if (s.license.startsWith('CC0')) cc0 += 1;
      if (!s.author) {
        anonymous += 1;
        continue;
      }
      counts.set(s.author, (counts.get(s.author) ?? 0) + 1);
    }
  }
  const authors = [...counts.entries()]
    .map(([author, n]) => ({ author, sentences: n }))
    .sort((a, b) => b.sentences - a.sentences || a.author.localeCompare(b.author));
  return { authors, sentences, cc0, anonymous };
}

/** Получены ли данные ООН через OPUS (тогда OPUS просит сослаться и на свою статью). */
export function unViaOpus(corpus: Corpus): boolean {
  return corpus.pairs.some(
    (p) => p.origin?.source === 'un_corpus' && p.origin.file.includes('OPUS'),
  );
}
