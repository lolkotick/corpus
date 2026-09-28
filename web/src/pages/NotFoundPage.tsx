import { Link } from 'react-router-dom';

import { Container } from '../components/Container';
import { EmptyState } from '../components/ui';

export function NotFoundPage() {
  return (
    <Container className="pt-16">
      <EmptyState title="Страница не найдена">
        Проверьте адрес или вернитесь{' '}
        <Link to="/" className="underline">
          на главную
        </Link>
        .
      </EmptyState>
    </Container>
  );
}
