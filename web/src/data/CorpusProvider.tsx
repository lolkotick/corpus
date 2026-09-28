import { useEffect, useState, type ReactNode } from 'react';

import { buildIndex, CorpusContext, type CorpusState } from './corpusContext';
import { isCorpus, isStats } from './validate';

const DATA_URL = `${import.meta.env.BASE_URL}data/`;

async function fetchJson(name: string): Promise<unknown> {
  const response = await fetch(`${DATA_URL}${name}`, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  return (await response.json()) as unknown;
}

/** Загружает corpus.json и stats.json один раз для всего приложения. */
export function CorpusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<CorpusState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchJson('corpus.json'), fetchJson('stats.json')])
      .then(([corpus, stats]) => {
        if (cancelled) return;
        if (!isCorpus(corpus) || !isStats(stats)) {
          throw new Error('данные повреждены или устарели — пересоберите корпус');
        }
        setState({ status: 'ready', ...buildIndex(corpus, stats) });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : String(error),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <CorpusContext value={state}>{children}</CorpusContext>;
}
