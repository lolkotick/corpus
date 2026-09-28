import { useCallback, useEffect, useState } from 'react';

import { readStorage, writeStorage } from './storage';

export type ThemeChoice = 'system' | 'light' | 'dark';
const KEY = 'corpus.theme';

function initialChoice(): ThemeChoice {
  const saved = readStorage(KEY);
  return saved === 'light' || saved === 'dark' ? saved : 'system';
}

function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/** Выбор темы: системная → светлая → тёмная. Итоговая тема нужна графикам. */
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(initialChoice);
  const [systemDark, setSystemDark] = useState(systemPrefersDark);

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      setSystemDark(media.matches);
    };
    media.addEventListener('change', onChange);
    return () => {
      media.removeEventListener('change', onChange);
    };
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (choice === 'system') delete root.dataset.theme;
    else root.dataset.theme = choice;
    writeStorage(KEY, choice === 'system' ? null : choice);
  }, [choice]);

  const cycle = useCallback(() => {
    setChoice((c) => (c === 'system' ? 'light' : c === 'light' ? 'dark' : 'system'));
  }, []);

  const resolved: 'light' | 'dark' = choice === 'system' ? (systemDark ? 'dark' : 'light') : choice;
  return { choice, resolved, setChoice, cycle };
}
