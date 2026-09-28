import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';

import { useCorpusState } from '../data/corpusContext';
import { formatDate, methodLabel } from '../lib/labels';
import { cx } from '../lib/styles';
import { useTheme, type ThemeChoice } from '../lib/theme';
import { CloseIcon, MenuIcon, MonitorIcon, MoonIcon, SunIcon } from './icons';

const NAV_ITEMS: readonly { to: string; label: string; end?: boolean }[] = [
  { to: '/', label: 'Главная', end: true },
  { to: '/search', label: 'Поиск' },
  { to: '/stats', label: 'Статистика' },
  { to: '/exercises', label: 'Упражнения' },
  { to: '/review', label: 'Проверка' },
  { to: '/sources', label: 'Источники' },
  { to: '/about', label: 'О проекте' },
];

const THEME_LABEL: Record<ThemeChoice, string> = {
  system: 'как в системе',
  light: 'светлая',
  dark: 'тёмная',
};

function ThemeToggle() {
  const { choice, cycle } = useTheme();
  const Icon = choice === 'light' ? SunIcon : choice === 'dark' ? MoonIcon : MonitorIcon;
  return (
    <button
      type="button"
      onClick={cycle}
      className="inline-flex size-10 items-center justify-center rounded-full text-muted transition hover:bg-surface hover:text-ink"
      aria-label={`Тема: ${THEME_LABEL[choice]}. Нажмите, чтобы переключить`}
      title={`Тема: ${THEME_LABEL[choice]}`}
    >
      <Icon />
    </button>
  );
}

function Logo() {
  return (
    <Link to="/" className="group flex items-baseline gap-2.5 rounded-md" aria-label="На главную">
      <span className="inline-flex translate-y-[-2px] gap-1" aria-hidden="true">
        <i className="size-[7px] rounded-full bg-en" />
        <i className="size-[7px] rounded-full bg-zh" />
        <i className="size-[7px] rounded-full bg-ru" />
      </span>
      <span className="font-serif text-[19px] leading-none font-bold">Параллельный корпус</span>
      <span className="hidden text-xs tracking-[0.06em] text-muted sm:inline">
        EN · <span lang="zh-Hans">中文</span> · RU
      </span>
    </Link>
  );
}

function navClass({ isActive }: { isActive: boolean }): string {
  return cx(
    'rounded-lg px-3 py-1.5 text-[14.5px] transition',
    isActive ? 'bg-surface text-ink ring-1 ring-rule' : 'text-muted hover:text-ink',
  );
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const state = useCorpusState();

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-ink px-4 py-2 text-paper focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Перейти к содержанию
      </a>
      <header className="sticky top-0 z-40 border-b border-rule/70 bg-paper/85 backdrop-blur-md print:hidden">
        <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-4 px-4 py-3.5 sm:px-8">
          <Logo />
          <nav aria-label="Основная навигация" className="hidden md:block">
            <ul className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <li key={item.to}>
                  <NavLink to={item.to} end={item.end} className={navClass}>
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <button
              type="button"
              className="inline-flex size-10 items-center justify-center rounded-full text-muted hover:bg-surface hover:text-ink md:hidden"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'}
              onClick={() => {
                setMenuOpen((open) => !open);
              }}
            >
              {menuOpen ? <CloseIcon /> : <MenuIcon />}
            </button>
          </div>
        </div>
        {menuOpen && (
          <nav
            id="mobile-nav"
            aria-label="Основная навигация"
            className="animate-fade-in border-t border-rule px-4 pb-4 md:hidden"
          >
            <ul className="grid gap-1 pt-3">
              {NAV_ITEMS.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={() => {
                      setMenuOpen(false);
                    }}
                    className={({ isActive }) =>
                      cx(
                        'block rounded-lg px-3 py-2.5 text-base',
                        isActive
                          ? 'bg-surface font-medium text-ink ring-1 ring-rule'
                          : 'text-muted',
                      )
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </header>

      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        <div key={location.pathname} className="animate-fade-in">
          <Outlet />
        </div>
      </main>

      <footer className="mt-20 border-t border-rule print:hidden">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-3 px-4 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p>
            Учебный параллельный корпус EN · ZH · RU — курсовая работа по лингвистике.
            {state.status === 'ready' && (
              <>
                {' '}
                Сборка от {formatDate(state.corpus.generated_at)}, выравнивание:{' '}
                {methodLabel(state.corpus.alignment_method)}.
              </>
            )}
          </p>
          <p className="flex shrink-0 gap-4 whitespace-nowrap">
            <Link to="/about" className="hover:text-ink">
              Методика
            </Link>
            <a
              href={`${import.meta.env.BASE_URL}data/corpus.csv`}
              className="hover:text-ink"
              download
            >
              Скачать CSV
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
