import type { ReactNode } from 'react';

import { useCorpusState, type CorpusIndex } from '../data/corpusContext';
import { ErrorState, LoadingState } from './ui';

/** Показывает загрузку/ошибку, а когда данные готовы — отрисовывает страницу. */
export function DataGate({ children }: { children: (data: CorpusIndex) => ReactNode }) {
  const state = useCorpusState();
  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') return <ErrorState message={state.message} />;
  return <>{children(state)}</>;
}
