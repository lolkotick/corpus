import { lazy, Suspense } from 'react';
import { HashRouter, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout';
import { LoadingState } from './components/ui';
import { CorpusProvider } from './data/CorpusProvider';
import { AboutPage } from './pages/AboutPage';
import { ExercisesPage } from './pages/ExercisesPage';
import { HomePage } from './pages/HomePage';
import { NotFoundPage } from './pages/NotFoundPage';
import { PairPage } from './pages/PairPage';
import { PrintPage } from './pages/PrintPage';
import { ReviewPage } from './pages/ReviewPage';
import { SearchPage } from './pages/SearchPage';
import { SourcesPage } from './pages/SourcesPage';
import { TestPage } from './pages/TestPage';

// Графики (Recharts) нужны только на странице статистики — грузим её отдельным чанком.
const StatsPage = lazy(async () => ({ default: (await import('./pages/StatsPage')).StatsPage }));

/** HashRouter: статический хостинг (GitHub Pages) без серверных перенаправлений. */
export function App() {
  return (
    <CorpusProvider>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="pair/:id" element={<PairPage />} />
            <Route
              path="stats"
              element={
                <Suspense fallback={<LoadingState label="Загружаем графики…" />}>
                  <StatsPage />
                </Suspense>
              }
            />
            <Route path="exercises" element={<ExercisesPage />} />
            <Route path="exercises/print" element={<PrintPage />} />
            <Route path="exercises/test" element={<TestPage />} />
            <Route path="review" element={<ReviewPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </HashRouter>
    </CorpusProvider>
  );
}
