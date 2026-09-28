import type { CaseCode, Lang, Level, NumberCode, Phenomenon, Status } from '../data/types';

export const LANGS: readonly Lang[] = ['en', 'zh', 'ru'];

export const LANG_INFO: Record<
  Lang,
  { short: string; name: string; native: string; htmlLang: string; phenomenon: Phenomenon }
> = {
  en: {
    short: 'EN',
    name: 'Английский',
    native: 'English',
    htmlLang: 'en',
    phenomenon: 'article',
  },
  zh: {
    short: 'ZH',
    name: 'Китайский',
    native: '中文',
    htmlLang: 'zh-Hans',
    phenomenon: 'classifier',
  },
  ru: { short: 'RU', name: 'Русский', native: 'Русский', htmlLang: 'ru', phenomenon: 'case' },
};

export const PHENOMENA: Record<
  Phenomenon,
  { label: string; short: string; lang: Lang; description: string }
> = {
  article: {
    label: 'Артикли',
    short: 'артикль',
    lang: 'en',
    description: 'a / an / the и существительное, к которому относится артикль',
  },
  classifier: {
    label: 'Счётные слова 量词',
    short: '量词',
    lang: 'zh',
    description: 'конструкция «числительное / 这 / 那 / 几 / 每 + 量词 + существительное»',
  },
  case: {
    label: 'Падежи',
    short: 'падеж',
    lang: 'ru',
    description: 'падеж, число и начальная форма каждого существительного',
  },
};

export const CASE_ORDER: readonly CaseCode[] = ['nomn', 'gent', 'datv', 'accs', 'ablt', 'loct'];

export const CASES: Record<CaseCode, { label: string; short: string; question: string }> = {
  nomn: { label: 'Именительный', short: 'им.', question: 'кто? что?' },
  gent: { label: 'Родительный', short: 'род.', question: 'кого? чего?' },
  datv: { label: 'Дательный', short: 'дат.', question: 'кому? чему?' },
  accs: { label: 'Винительный', short: 'вин.', question: 'кого? что?' },
  ablt: { label: 'Творительный', short: 'твор.', question: 'кем? чем?' },
  loct: { label: 'Предложный', short: 'предл.', question: 'о ком? о чём?' },
  voct: { label: 'Звательный', short: 'зв.', question: 'обращение' },
};

export const NUMBERS: Record<NumberCode, { label: string; short: string }> = {
  sing: { label: 'единственное', short: 'ед. ч.' },
  plur: { label: 'множественное', short: 'мн. ч.' },
};

export const STATUSES: Record<Status, { label: string; description: string }> = {
  auto: { label: 'Автоматически', description: 'результат pipeline без ручной проверки' },
  checked: { label: 'Проверено', description: 'пара проверена вручную, ошибок нет' },
  corrected: { label: 'Исправлено', description: 'текст или выравнивание исправлены вручную' },
};

export const LEVELS: readonly Level[] = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

export const ALIGNMENT_METHODS: Record<string, string> = {
  gale_church: 'Гейл–Чёрч (по длине предложений)',
  labse: 'LaBSE (алгоритм Bertalign)',
  bertalign: 'bertalign (LaBSE)',
};

export function methodLabel(method: string): string {
  return method
    .split('+')
    .map((m) => ALIGNMENT_METHODS[m] ?? m)
    .join(' + ');
}

/** «1-2-1» → «1–2–1» (EN–ZH–RU). */
export function alignmentTypeLabel(type: string): string {
  return type.replaceAll('-', '–');
}

export function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

export function formatScore(score: number): string {
  return score.toFixed(2).replace('.', ',');
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}
