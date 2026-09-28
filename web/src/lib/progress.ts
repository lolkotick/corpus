/** Сохранение прогресса упражнений в localStorage (текущий набор и история результатов). */
import type { Level } from '../data/types';
import type { ExerciseKind, ExerciseSettings } from './exercises';
import { readJson, writeStorage } from './storage';

const SESSION_KEY = 'corpus.exercises.session.v1';
const HISTORY_KEY = 'corpus.exercises.history.v1';
const HISTORY_LIMIT = 50;

export interface AnswerRecord {
  value: string;
  correct: boolean;
}

export interface SessionState {
  settings: ExerciseSettings;
  seed: number;
  itemIds: string[];
  answers: Record<string, AnswerRecord>;
  index: number;
  startedAt: string;
  finished: boolean;
}

export interface HistoryEntry {
  date: string;
  kind: ExerciseKind;
  level: Level | '';
  total: number;
  correct: number;
}

const KINDS = new Set<string>(['article', 'classifier', 'case', 'mixed']);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isSettings(value: unknown): value is ExerciseSettings {
  return (
    isRecord(value) &&
    typeof value.kind === 'string' &&
    KINDS.has(value.kind) &&
    typeof value.level === 'string' &&
    typeof value.count === 'number'
  );
}

function isSession(value: unknown): value is SessionState {
  return (
    isRecord(value) &&
    isSettings(value.settings) &&
    typeof value.seed === 'number' &&
    Array.isArray(value.itemIds) &&
    value.itemIds.every((id) => typeof id === 'string') &&
    isRecord(value.answers) &&
    typeof value.index === 'number' &&
    typeof value.finished === 'boolean'
  );
}

function isHistory(value: unknown): value is HistoryEntry[] {
  return (
    Array.isArray(value) &&
    value.every(
      (e) =>
        isRecord(e) &&
        typeof e.date === 'string' &&
        typeof e.kind === 'string' &&
        KINDS.has(e.kind) &&
        typeof e.total === 'number' &&
        typeof e.correct === 'number',
    )
  );
}

export function loadSession(): SessionState | null {
  return readJson(SESSION_KEY, isSession);
}

export function saveSession(session: SessionState | null): void {
  writeStorage(SESSION_KEY, session ? JSON.stringify(session) : null);
}

export function loadHistory(): HistoryEntry[] {
  return readJson(HISTORY_KEY, isHistory) ?? [];
}

export function appendHistory(entry: HistoryEntry): HistoryEntry[] {
  const history = [entry, ...loadHistory()].slice(0, HISTORY_LIMIT);
  writeStorage(HISTORY_KEY, JSON.stringify(history));
  return history;
}

export function clearHistory(): void {
  writeStorage(HISTORY_KEY, null);
}

/** Точность по явлениям за всю историю (для блока «Ваши результаты»). */
export function accuracyByKind(
  history: readonly HistoryEntry[],
): Record<ExerciseKind, { correct: number; total: number }> {
  const result: Record<ExerciseKind, { correct: number; total: number }> = {
    article: { correct: 0, total: 0 },
    classifier: { correct: 0, total: 0 },
    case: { correct: 0, total: 0 },
    mixed: { correct: 0, total: 0 },
  };
  for (const entry of history) {
    const bucket = result[entry.kind];
    bucket.correct += entry.correct;
    bucket.total += entry.total;
  }
  return result;
}
