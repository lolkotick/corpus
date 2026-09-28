/**
 * Режим «Тест» для апробации упражнений: два фиксированных параллельных набора
 * заданий (A — предтест, B — посттест) одинаковой сложности, запись ответов,
 * времени и ошибок, экспорт в CSV для pipeline/approbation.py.
 *
 * Наборы одинаковы у всех участников: они строятся детерминированно по корпусу.
 * Равная сложность: задания каждого явления сортируются по уровню текста и подтипу
 * (the / a / an; 个 или специальное 量词; падеж), соседние по сложности задания
 * образуют пару, одно из пары (по seed) идёт в A, другое — в B. Наборы не
 * пересекаются по предложениям, поэтому посттест не повторяет предтест.
 * Импортированные источники (Tatoeba, ООН) в наборы не входят.
 */
import type { CaseCode, Corpus, Level, Phenomenon } from '../data/types';
import { allItems, checkAnswer, isTrivialCase, type ExerciseItem } from './exercises';
import { LEVELS } from './labels';
import { mulberry32 } from './random';
import { readJson, writeStorage } from './storage';

export const TEST_SEED = 20260901;
export const TEST_PER_KIND = 5;
export const TEST_STORAGE_KEY = 'corpus.test.v1';
const KINDS: readonly Phenomenon[] = ['article', 'classifier', 'case'];

export type TestStage = 'pre' | 'post';

export const STAGES: Record<TestStage, { label: string; set: 'A' | 'B'; hint: string }> = {
  pre: { label: 'Предтест', set: 'A', hint: 'до работы с упражнениями' },
  post: { label: 'Посттест', set: 'B', hint: 'после работы с упражнениями' },
};

export interface TestItem extends ExerciseItem {
  /** Подтип для контроля сложности и анализа ошибок: the/a/an, 个/другое, падеж. */
  subtype: string;
}

export interface TestSet {
  id: string;
  name: 'A' | 'B';
  items: TestItem[];
}

export interface TestAnswer {
  item_id: string;
  kind: Phenomenon;
  level: Level;
  subtype: string;
  correct_answer: string;
  answer: string;
  correct: boolean;
  ms: number;
}

export interface TestAttempt {
  id: string;
  participant: string;
  stage: TestStage;
  set_id: string;
  started_at: string;
  finished_at: string | null;
  answers: TestAnswer[];
}

export interface TestStore {
  attempts: TestAttempt[];
}

/* ─── Наборы ───────────────────────────────────────────────────────────── */

function levelRank(level: Level): number {
  return LEVELS.indexOf(level);
}

function subtypeOf(item: ExerciseItem, cases: ReadonlyMap<string, CaseCode>): string {
  switch (item.kind) {
    case 'article':
      return item.answer.toLowerCase();
    case 'classifier':
      return item.answer === '个' ? '个' : 'специальное';
    case 'case':
      return cases.get(item.id) ?? '';
  }
}

/** FNV-1a: короткий отпечаток состава набора (меняется, если изменился корпус). */
function fingerprint(ids: readonly string[]): string {
  let hash = 0x811c9dc5;
  for (const ch of ids.join('|')) {
    hash ^= ch.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, '0').slice(0, 6);
}

/** Корпус для наборов теста — только учебные тексты: импорт новых данных не должен менять
 *  предтест и посттест, пока идёт апробация. */
export function testCorpus(corpus: Corpus): Corpus {
  return { ...corpus, pairs: corpus.pairs.filter((pair) => !pair.origin) };
}

export function buildTestSets(
  fullCorpus: Corpus,
  perKind = TEST_PER_KIND,
): Record<'A' | 'B', TestSet> {
  const corpus = testCorpus(fullCorpus);
  const random = mulberry32(TEST_SEED);
  const cases = new Map<string, CaseCode>();
  const trivial = new Set<string>();
  for (const pair of corpus.pairs) {
    for (const ann of pair.annotations.ru) {
      cases.set(`${pair.id}:${ann.id}`, ann.case);
      if (isTrivialCase(ann)) trivial.add(`${pair.id}:${ann.id}`);
    }
  }
  const pool: TestItem[] = allItems(corpus, TEST_SEED)
    .filter((item) => !trivial.has(item.id))
    .map((item) => ({ ...item, subtype: subtypeOf(item, cases) }));

  const sets: Record<'A' | 'B', TestItem[]> = { A: [], B: [] };
  const usedPairs = new Set<string>();
  for (const kind of KINDS) {
    const sorted = pool
      .filter((i) => i.kind === kind)
      .sort(
        (a, b) =>
          levelRank(a.level) - levelRank(b.level) ||
          a.subtype.localeCompare(b.subtype) ||
          a.id.localeCompare(b.id),
      );
    // Пары соседних по сложности заданий из разных предложений.
    const matched: [TestItem, TestItem][] = [];
    for (let i = 0; i + 1 < sorted.length; i += 2) {
      const a = sorted[i];
      const b = sorted[i + 1];
      if (a && b && a.pairId !== b.pairId) matched.push([a, b]);
    }
    // Равномерно по шкале сложности: берём пары через равные промежутки.
    const chosen: [TestItem, TestItem][] = [];
    const step = matched.length / perKind;
    const tried = new Set<number>();
    for (let k = 0; k < perKind && chosen.length < perKind; k += 1) {
      for (let j = Math.floor(k * step); j < matched.length; j += 1) {
        const candidate = matched[j];
        if (!candidate || tried.has(j)) continue;
        tried.add(j);
        const [a, b] = candidate;
        if (usedPairs.has(a.pairId) || usedPairs.has(b.pairId)) continue;
        chosen.push(candidate);
        usedPairs.add(a.pairId);
        usedPairs.add(b.pairId);
        break;
      }
    }
    for (const [a, b] of chosen) {
      const flip = random() < 0.5;
      sets.A.push(flip ? a : b);
      sets.B.push(flip ? b : a);
    }
  }
  const order = (items: TestItem[]): TestItem[] => {
    // Чередование явлений: артикль, 量词, падеж, … — в порядке сложности внутри явления.
    const queues = KINDS.map((k) => items.filter((i) => i.kind === k));
    const result: TestItem[] = [];
    while (queues.some((q) => q.length > 0)) {
      for (const q of queues) {
        const next = q.shift();
        if (next) result.push(next);
      }
    }
    return result;
  };
  const make = (name: 'A' | 'B'): TestSet => {
    const items = order(sets[name]);
    return { id: `${name}-${fingerprint(items.map((i) => i.id))}`, name, items };
  };
  return { A: make('A'), B: make('B') };
}

/** Средний уровень и состав набора — чтобы показать, что наборы сопоставимы. */
export function setProfile(set: TestSet): {
  meanLevel: number;
  byKind: Record<Phenomenon, number>;
  subtypes: Record<string, number>;
} {
  const byKind: Record<Phenomenon, number> = { article: 0, classifier: 0, case: 0 };
  const subtypes: Record<string, number> = {};
  let sum = 0;
  for (const item of set.items) {
    byKind[item.kind] += 1;
    subtypes[item.subtype] = (subtypes[item.subtype] ?? 0) + 1;
    sum += levelRank(item.level) + 1;
  }
  return { meanLevel: set.items.length ? sum / set.items.length : 0, byKind, subtypes };
}

/* ─── Ответы и хранение ────────────────────────────────────────────────── */

export function newAttempt(
  participant: string,
  stage: TestStage,
  set: TestSet,
  now: string,
): TestAttempt {
  return {
    id: `${now.replace(/\D/g, '').slice(0, 14)}-${Math.floor(Math.random() * 1e6)
      .toString(36)
      .padStart(4, '0')}`,
    participant: participant.trim(),
    stage,
    set_id: set.id,
    started_at: now,
    finished_at: null,
    answers: [],
  };
}

export function recordAnswer(
  attempt: TestAttempt,
  item: TestItem,
  value: string,
  ms: number,
): TestAttempt {
  return {
    ...attempt,
    answers: [
      ...attempt.answers.filter((a) => a.item_id !== item.id),
      {
        item_id: item.id,
        kind: item.kind,
        level: item.level,
        subtype: item.subtype,
        correct_answer: item.answer,
        answer: value.trim(),
        correct: checkAnswer(item, value),
        ms: Math.max(0, Math.round(ms)),
      },
    ],
  };
}

export function attemptScore(attempt: TestAttempt): {
  correct: number;
  total: number;
  byKind: Record<Phenomenon, { correct: number; total: number }>;
  seconds: number;
} {
  const byKind: Record<Phenomenon, { correct: number; total: number }> = {
    article: { correct: 0, total: 0 },
    classifier: { correct: 0, total: 0 },
    case: { correct: 0, total: 0 },
  };
  let ms = 0;
  for (const a of attempt.answers) {
    byKind[a.kind].total += 1;
    byKind[a.kind].correct += Number(a.correct);
    ms += a.ms;
  }
  const correct = attempt.answers.filter((a) => a.correct).length;
  return { correct, total: attempt.answers.length, byKind, seconds: ms / 1000 };
}

function isStore(value: unknown): value is TestStore {
  return (
    typeof value === 'object' &&
    value !== null &&
    Array.isArray((value as { attempts?: unknown }).attempts)
  );
}

export function loadStore(): TestStore {
  return readJson(TEST_STORAGE_KEY, isStore) ?? { attempts: [] };
}

export function saveStore(store: TestStore): void {
  writeStorage(TEST_STORAGE_KEY, JSON.stringify(store));
}

/* ─── CSV ──────────────────────────────────────────────────────────────── */

export const CSV_COLUMNS = [
  'participant',
  'stage',
  'attempt_id',
  'set_id',
  'started_at',
  'finished_at',
  'task_no',
  'item_id',
  'phenomenon',
  'level',
  'subtype',
  'correct_answer',
  'answer',
  'correct',
  'time_ms',
] as const;

function csvCell(value: string | number): string {
  const text = String(value);
  return /[;"\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/**
 * CSV для pipeline/approbation.py: строка на ответ, разделитель «;», UTF-8 с BOM
 * (корректно открывается в русском Excel). Незаконченные попытки тоже выгружаются
 * (finished_at пустой) — скрипт анализа их отбрасывает.
 */
export function attemptsToCsv(attempts: readonly TestAttempt[]): string {
  const lines = [CSV_COLUMNS.join(';')];
  for (const attempt of attempts) {
    attempt.answers.forEach((a, i) => {
      const row: (string | number)[] = [
        attempt.participant,
        attempt.stage,
        attempt.id,
        attempt.set_id,
        attempt.started_at,
        attempt.finished_at ?? '',
        i + 1,
        a.item_id,
        a.kind,
        a.level,
        a.subtype,
        a.correct_answer,
        a.answer,
        a.correct ? 1 : 0,
        a.ms,
      ];
      lines.push(row.map(csvCell).join(';'));
    });
  }
  return `\uFEFF${lines.join('\r\n')}\r\n`;
}

export function csvFileName(attempts: readonly TestAttempt[], now: string): string {
  const people = [...new Set(attempts.map((a) => a.participant))];
  const who = people.length === 1 ? (people[0] ?? 'участник') : 'участники';
  const safe = who.replace(/[^\p{L}\p{N}_-]+/gu, '_').slice(0, 40) || 'участник';
  return `test_${safe}_${now.slice(0, 10)}.csv`;
}
