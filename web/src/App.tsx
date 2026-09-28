import { HashRouter, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout';
import { CorpusProvider } from './data/CorpusProvider';
import { ComingSoonPage } from './pages/ComingSoonPage';
import { HomePage } from './pages/HomePage';
import { NotFoundPage } from './pages/NotFoundPage';
import { PairPage } from './pages/PairPage';
import { SearchPage } from './pages/SearchPage';

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
            <Route path="stats" element={<ComingSoonPage title="Статистика" />} />
            <Route path="exercises" element={<ComingSoonPage title="Упражнения" />} />
            <Route path="about" element={<ComingSoonPage title="О проекте" />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </HashRouter>
    </CorpusProvider>
  );
}
