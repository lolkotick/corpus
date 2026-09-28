import type { Corpus, Stats } from './types';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/** Минимальная проверка формы данных: защищает от устаревшего (версия < 2) или битого JSON. */
export function isCorpus(value: unknown): value is Corpus {
  return (
    isRecord(value) &&
    typeof value.version === 'number' &&
    value.version >= 2 &&
    Array.isArray(value.pairs) &&
    Array.isArray(value.texts) &&
    Array.isArray(value.classifiers)
  );
}

export function isStats(value: unknown): value is Stats {
  return isRecord(value) && isRecord(value.totals) && Array.isArray(value.texts);
}
