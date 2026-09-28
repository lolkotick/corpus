import { createContext, useContext } from 'react';

import type { ClassifierInfo, Corpus, Pair, Stats, TextMeta } from './types';

export interface CorpusIndex {
  corpus: Corpus;
  stats: Stats;
  pairById: ReadonlyMap<string, Pair>;
  pairIndex: ReadonlyMap<string, number>;
  textById: ReadonlyMap<string, TextMeta>;
  classifierByValue: ReadonlyMap<string, ClassifierInfo>;
}

export type CorpusState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | ({ status: 'ready' } & CorpusIndex);

export const CorpusContext = createContext<CorpusState>({ status: 'loading' });

export function useCorpusState(): CorpusState {
  return useContext(CorpusContext);
}

export function buildIndex(corpus: Corpus, stats: Stats): CorpusIndex {
  return {
    corpus,
    stats,
    pairById: new Map(corpus.pairs.map((p) => [p.id, p])),
    pairIndex: new Map(corpus.pairs.map((p, i) => [p.id, i])),
    textById: new Map(corpus.texts.map((t) => [t.id, t])),
    classifierByValue: new Map(corpus.classifiers.map((c) => [c.value, c])),
  };
}
