import { Link } from 'react-router-dom';

import { Container } from '../components/Container';
import { EmptyState } from '../components/ui';

/** Временная страница для разделов, которые появятся в следующих этапах (PR3–PR5). */
export function ComingSoonPage({ title }: { title: string }) {
  return (
    <Container className="pt-16">
      <EmptyState title={`${title}: раздел в разработке`}>
        Он появится в одном из следующих этапов проекта. Пока можно{' '}
        <Link to="/search" className="underline">
          искать по корпусу
        </Link>
        .
      </EmptyState>
    </Container>
  );
}
