/**
 * Генерация упражнений из корпуса: каждое задание — реальное предложение корпуса,
 * в котором пропущен размеченный элемент (артикль, 量词 или форма существительного),
 * а параллельные предложения служат подсказкой.
 */
import type {
  ArticleAnnotation,
  CaseAnnotation,
  ClassifierAnnotation,
  ClassifierInfo,
  Corpus,
  Lang,
  Level,
  Pair,
  Phenomenon,
} from '../data/types';
import { CASES, LANG_INFO, LEVELS, NUMBERS } from './labels';
import { mulberry32, shuffle } from './random';
import { codePointConverter, normalizeWord } from './text';

export { mulberry32, newSeed, shuffle } from './random';

export type ExerciseKind = Phenomenon | 'mixed';

export interface ExerciseSettings {
  kind: ExerciseKind;
  level: Level | '';
  count: number;
}

export const DEFAULT_SETTINGS: ExerciseSettings = { kind: 'article', level: '', count: 10 };
export const COUNTS = [5, 10, 15, 20] as const;

export interface Hint {
  lang: Lang;
  text: string;
}

export interface ExerciseItem {
  /** Стабильный идентификатор: пара + элемент разметки. */
  id: string;
  kind: Phenomenon;
  pairId: string;
  level: Level;
  lang: Lang;
  before: string;
  after: string;
  answer: string;
  /** Варианты ответа (артикли и 量词); пусто — ввод с клавиатуры (падежи). */
  options: string[];
  /** Начальная форма для падежного задания. */
  lemma?: string;
  hints: Hint[];
  explanation: string;
  /** Короткая подпись задания для итогов и ключей. */
  label: string;
}

/* ─── Вспомогательные функции ───────────────────────────────────────────── */

function slice(text: string, start: number, end: number): { before: string; after: string } {
  const convert = codePointConverter(text);
  return { before: text.slice(0, convert(start)), after: text.slice(convert(end)) };
}

function spanText(text: string, span: readonly [number, number] | undefined): string | null {
  if (!span) return null;
  const convert = codePointConverter(text);
  return text.slice(convert(span[0]), convert(span[1]));
}

function hintsFor(pair: Pair, lang: Lang): Hint[] {
  return (['en', 'zh', 'ru'] as const)
    .filter((l) => l !== lang)
    .map((l) => ({ lang: l, text: pair[l] }));
}

/** Переводные эквиваленты слова (по связям pipeline), чтобы сослаться на них в объяснении. */
function linkedWords(
  pair: Pair,
  lang: Lang,
  start: number,
  end: number,
): Partial<Record<Lang, string>> {
  const link = pair.links?.find((l) => {
    const span = l[lang];
    return span !== undefined && span[0] < end && span[1] > start;
  });
  if (!link) return {};
  return {
    en: spanText(pair.en, link.en) ?? undefined,
    zh: spanText(pair.zh, link.zh) ?? undefined,
    ru: spanText(pair.ru, link.ru) ?? undefined,
  };
}

/* ─── EN: артикли ───────────────────────────────────────────────────────── */

function articleExplanation(pair: Pair, ann: ArticleAnnotation): string {
  const head = ann.head?.text ?? '';
  const plural = ann.head?.number === 'plur';
  const next = ann.next?.text ?? head;
  const parts: string[] = [];
  if (ann.value === 'the') {
    parts.push(
      `Определённый артикль the: речь о конкретном «${head}» — он уже упоминался, единственный в своём роде или уточнён контекстом (например, of-фразой или порядковым числительным).`,
    );
    if (plural) parts.push('С существительным во множественном числе a/an невозможен.');
  } else {
    parts.push(
      `Неопределённый артикль: «${head}» — исчисляемое существительное в единственном числе, упоминается впервые или как «один из многих».`,
    );
    parts.push(
      ann.value === 'an'
        ? `Форма an — потому что следующее слово «${next}» начинается с гласного звука.`
        : `Форма a — потому что следующее слово «${next}» начинается с согласного звука.`,
    );
  }
  if (ann.head) {
    const eq = linkedWords(pair, 'en', ann.head.start, ann.head.end);
    const zhAnn = pair.annotations.zh.find(
      (z) => z.head && eq.zh && z.head.text === eq.zh && z.det.text,
    );
    if (eq.ru) parts.push(`В русском артикля нет: «${eq.ru}».`);
    if (zhAnn && ann.value !== 'the' && /^[一]/.test(zhAnn.det.text)) {
      parts.push(
        `В китайском неопределённость передаёт «${zhAnn.det.text}${zhAnn.value}${zhAnn.head?.text ?? ''}» — числительное 一 и счётное слово.`,
      );
    } else if (zhAnn && ann.value === 'the' && /^[这那]/.test(zhAnn.det.text)) {
      parts.push(
        `В китайском определённость передаёт указательное «${zhAnn.det.text}${zhAnn.value}${zhAnn.head?.text ?? ''}».`,
      );
    }
  }
  return parts.join(' ');
}

function articleItems(pair: Pair, level: Level): ExerciseItem[] {
  return pair.annotations.en
    .filter((a) => !a.disputed && a.head !== null)
    .map((ann) => {
      const { before, after } = slice(pair.en, ann.start, ann.end);
      const first = ann.text.charAt(0);
      const capital = first !== first.toLowerCase();
      // Варианты пишутся так же, как ответ: the / The / THE (заголовки документов ООН).
      const allCaps = ann.text.length > 1 && ann.text === ann.text.toUpperCase();
      const options = allCaps
        ? ['A', 'AN', 'THE']
        : capital
          ? ['A', 'An', 'The']
          : ['a', 'an', 'the'];
      return {
        id: `${pair.id}:${ann.id}`,
        kind: 'article',
        pairId: pair.id,
        level,
        lang: 'en',
        before,
        after,
        answer: ann.text,
        options,
        hints: hintsFor(pair, 'en'),
        explanation: articleExplanation(pair, ann),
        label: `${ann.text} ${ann.head?.text ?? ''}`.trim(),
      } satisfies ExerciseItem;
    });
}

/* ─── ZH: счётные слова ─────────────────────────────────────────────────── */

/** «Широкие» 量词 (вид, некоторое количество, группа) грамматичны почти с любым словом. */
const NEVER_DISTRACTORS = new Set(['种', '些', '群', '份']);

/** Для этих 量词 универсальное 个 — явная ошибка, поэтому 个 годится в отвлекающие варианты. */
const GE_IS_WRONG = new Set(
  '本 张 只 条 支 把 杯 瓶 辆 台 棵 朵 双 碗 盏 封 首 头 匹 架 艘 盒 袋 包 斤 公斤 串 锅 箱 壶 盘'.split(
    ' ',
  ),
);

function compatible(noun: string, info: ClassifierInfo): boolean {
  return info.examples.some(
    (ex) => noun === ex || noun.endsWith(ex) || (ex.length >= 2 && noun.startsWith(ex)),
  );
}

export interface ClassifierContext {
  classifiers: readonly ClassifierInfo[];
  /** Какие 量词 встречались с каждым существительным в корпусе. */
  usedWith: ReadonlyMap<string, ReadonlySet<string>>;
  /** Частота 量词 в корпусе — частые чаще становятся отвлекающими вариантами. */
  frequency: ReadonlyMap<string, number>;
}

export function classifierContext(corpus: Corpus): ClassifierContext {
  const usedWith = new Map<string, Set<string>>();
  const frequency = new Map<string, number>();
  for (const pair of corpus.pairs) {
    for (const ann of pair.annotations.zh) {
      frequency.set(ann.value, (frequency.get(ann.value) ?? 0) + 1);
      if (!ann.head) continue;
      const set = usedWith.get(ann.head.text) ?? new Set<string>();
      set.add(ann.value);
      usedWith.set(ann.head.text, set);
    }
  }
  return { classifiers: corpus.classifiers, usedWith, frequency };
}

/** Три отвлекающих 量词, которые с этим существительным точно неверны. */
export function distractors(
  answer: string,
  noun: string,
  ctx: ClassifierContext,
  random: () => number,
): string[] {
  const answerInfo = ctx.classifiers.find((c) => c.value === answer);
  const used = ctx.usedWith.get(noun) ?? new Set<string>();
  const pool = ctx.classifiers.filter((c) => {
    if (c.value === answer || used.has(c.value) || NEVER_DISTRACTORS.has(c.value)) return false;
    if (c.type.startsWith('глагол')) return false;
    if (compatible(noun, c)) return false;
    // Ёмкости взаимозаменяемы (一杯茶 / 一壶茶), поэтому при ответе-мере другие меры не предлагаем.
    if (answerInfo?.type === 'мера' && c.type === 'мера') return false;
    if (c.value === '个' && !GE_IS_WRONG.has(answer)) return false;
    return true;
  });
  // Сначала частые в корпусе (правдоподобные), затем остальные; внутри — случайный порядок.
  const frequent = shuffle(
    pool.filter((c) => (ctx.frequency.get(c.value) ?? 0) >= 2),
    random,
  );
  const rare = shuffle(
    pool.filter((c) => (ctx.frequency.get(c.value) ?? 0) < 2),
    random,
  );
  return [...frequent, ...rare].slice(0, 3).map((c) => c.value);
}

function classifierExplanation(
  ann: ClassifierAnnotation,
  info: ClassifierInfo | undefined,
): string {
  const head = ann.head?.text ?? '';
  const parts = [
    `${ann.value} (${ann.pinyin}) — счётное слово: ${info?.gloss ?? ann.type}.`,
    `В конструкции «${ann.det.text} + ${ann.value} + ${head}» между числительным (или 这/那/每) и существительным обязательно стоит 量词.`,
  ];
  const others = info?.examples.filter((ex) => ex !== head).slice(0, 4) ?? [];
  if (others.length > 0)
    parts.push(`Ещё примеры: ${others.map((ex) => `一${ann.value}${ex}`).join('、')}.`);
  return parts.join(' ');
}

function classifierItems(
  pair: Pair,
  level: Level,
  ctx: ClassifierContext,
  random: () => number,
): ExerciseItem[] {
  const items: ExerciseItem[] = [];
  for (const ann of pair.annotations.zh) {
    if (ann.disputed || !ann.head || ann.elliptical || ann.type.startsWith('глагол')) continue;
    const wrong = distractors(ann.value, ann.head.text, ctx, random);
    if (wrong.length < 3) continue;
    const { before, after } = slice(pair.zh, ann.start, ann.end);
    const info = ctx.classifiers.find((c) => c.value === ann.value);
    items.push({
      id: `${pair.id}:${ann.id}`,
      kind: 'classifier',
      pairId: pair.id,
      level,
      lang: 'zh',
      before,
      after,
      answer: ann.value,
      options: shuffle([ann.value, ...wrong], random),
      hints: hintsFor(pair, 'zh'),
      explanation: classifierExplanation(ann, info),
      label: `${ann.det.text}${ann.value}${ann.head.text}`,
    });
  }
  return items;
}

/* ─── RU: падежи ────────────────────────────────────────────────────────── */

const CONTEXT_REASON: Record<string, string> = {
  числительное: 'после числительного',
  'родительный при существительном': 'зависит от другого существительного (кого? чего?)',
  'родительный после «больше/много»': 'после слов «больше», «много» и т. п.',
  'дополнение при переходном глаголе': 'прямое дополнение при переходном глаголе',
  'подлежащее (согласование с глаголом)': 'подлежащее — отвечает на вопрос «кто? что?»',
  'подлежащее при «есть»': 'подлежащее в конструкции «у кого-то есть…»',
  приложение: 'приложение стоит в том же падеже, что и определяемое слово',
  согласование: 'падеж подтверждается согласованным прилагательным',
};

function caseExplanation(pair: Pair, ann: CaseAnnotation): string {
  const info = CASES[ann.case];
  const parts = [`${info.label} падеж (${info.question}), ${NUMBERS[ann.number].label} число.`];
  if (ann.prep) {
    parts.push(
      `Предлог «${ann.prep}» требует здесь ${info.label.toLowerCase().replace(/ый$/, 'ого')} падежа.`,
    );
  }
  for (const rule of ann.context ?? []) {
    const reason = CONTEXT_REASON[rule];
    if (reason && !(rule === 'согласование' && ann.prep)) parts.push(`Основание: ${reason}.`);
  }
  const eq = linkedWords(pair, 'ru', ann.start, ann.end);
  if (eq.en || eq.zh) {
    parts.push(
      `В переводах: ${[eq.en && `EN «${eq.en}»`, eq.zh && `ZH «${eq.zh}»`].filter(Boolean).join(', ')} — падежного окончания там нет.`,
    );
  }
  return parts.join(' ');
}

function displayLemma(ann: CaseAnnotation): string {
  const first = ann.text.charAt(0);
  return first !== first.toLowerCase()
    ? ann.lemma.charAt(0).toUpperCase() + ann.lemma.slice(1)
    : ann.lemma;
}

export function isTrivialCase(ann: CaseAnnotation): boolean {
  return normalizeWord(ann.text) === normalizeWord(ann.lemma);
}

function caseItems(pair: Pair, level: Level): ExerciseItem[] {
  return pair.annotations.ru
    .filter((a) => !a.ambiguous && !a.disputed && !a.indeclinable)
    .map((ann) => {
      const { before, after } = slice(pair.ru, ann.start, ann.end);
      return {
        id: `${pair.id}:${ann.id}`,
        kind: 'case',
        pairId: pair.id,
        level,
        lang: 'ru',
        before,
        after,
        answer: ann.text,
        options: [],
        lemma: displayLemma(ann),
        hints: hintsFor(pair, 'ru'),
        explanation: caseExplanation(pair, ann),
        label: `${displayLemma(ann)} → ${ann.text}`,
      } satisfies ExerciseItem;
    });
}

/* ─── Сборка набора ─────────────────────────────────────────────────────── */

export function allItems(corpus: Corpus, seed: number): ExerciseItem[] {
  const random = mulberry32(seed ^ 0x5eed);
  const ctx = classifierContext(corpus);
  const levelOf = new Map(corpus.texts.map((t) => [t.id, t.level]));
  const items: ExerciseItem[] = [];
  for (const pair of corpus.pairs) {
    const level = pair.level ?? levelOf.get(pair.text_id) ?? 'A1';
    items.push(
      ...articleItems(pair, level),
      ...classifierItems(pair, level, ctx, random),
      ...caseItems(pair, level),
    );
  }
  return items;
}

/** Набор заданий: не больше одного задания на пару, тривиальные падежи (форма = лемма) — не больше 20 %. */
export function buildExerciseSet(
  corpus: Corpus,
  settings: ExerciseSettings,
  seed: number,
): ExerciseItem[] {
  const random = mulberry32(seed);
  const pool = allItems(corpus, seed).filter(
    (item) =>
      (settings.kind === 'mixed' || item.kind === settings.kind) &&
      (!settings.level || item.level === settings.level),
  );
  const trivialIds = new Set(
    corpus.pairs.flatMap((p) =>
      p.annotations.ru.filter(isTrivialCase).map((a) => `${p.id}:${a.id}`),
    ),
  );
  const maxTrivial = Math.floor(settings.count * 0.2);
  const chosen: ExerciseItem[] = [];
  const usedPairs = new Set<string>();
  let trivial = 0;
  const ordered =
    settings.kind === 'mixed' ? interleave(shuffle(pool, random), random) : shuffle(pool, random);
  for (const item of ordered) {
    if (chosen.length >= settings.count) break;
    if (usedPairs.has(item.pairId)) continue;
    if (trivialIds.has(item.id)) {
      if (trivial >= maxTrivial) continue;
      trivial += 1;
    }
    chosen.push(item);
    usedPairs.add(item.pairId);
  }
  return chosen;
}

/** Для смешанного набора — чередование явлений: артикль, 量词, падеж, … */
function interleave(items: ExerciseItem[], random: () => number): ExerciseItem[] {
  const queues: ExerciseItem[][] = shuffle(
    (['article', 'classifier', 'case'] as const).map((k) => items.filter((i) => i.kind === k)),
    random,
  );
  const result: ExerciseItem[] = [];
  while (queues.some((q) => q.length > 0)) {
    for (const queue of queues) {
      const next = queue.shift();
      if (next) result.push(next);
    }
  }
  return result;
}

export function availableCount(corpus: Corpus, settings: Omit<ExerciseSettings, 'count'>): number {
  return buildExerciseSet(corpus, { ...settings, count: 1000 }, 1).length;
}

/* ─── Проверка ответа ───────────────────────────────────────────────────── */

export function checkAnswer(item: ExerciseItem, value: string): boolean {
  if (item.kind === 'case') {
    const clean = (s: string) => normalizeWord(s).replace(/[^\p{L}-]/gu, '');
    return clean(value) !== '' && clean(value) === clean(item.answer);
  }
  if (item.kind === 'article') return value.toLowerCase() === item.answer.toLowerCase();
  return value === item.answer;
}

export const KIND_LABELS: Record<ExerciseKind, { title: string; task: string; lang?: Lang }> = {
  article: {
    title: 'Артикли',
    task: 'Вставьте артикль a, an или the.',
    lang: 'en',
  },
  classifier: {
    title: 'Счётные слова 量词',
    task: 'Выберите правильное счётное слово.',
    lang: 'zh',
  },
  case: {
    title: 'Падежи',
    task: 'Поставьте слово в скобках в нужную форму.',
    lang: 'ru',
  },
  mixed: { title: 'Все три явления', task: 'Задания на артикли, 量词 и падежи вперемешку.' },
};

export function levelLabel(level: Level | ''): string {
  return level ? `уровень ${level}` : 'все уровни';
}

export function isLevel(value: string): value is Level {
  return (LEVELS as readonly string[]).includes(value);
}

export function langName(lang: Lang): string {
  return LANG_INFO[lang].name;
}

/** Задания набора по сохранённым id (набор воспроизводим: те же seed и корпус). */
export function resolveItems(corpus: Corpus, seed: number, ids: readonly string[]): ExerciseItem[] {
  const byId = new Map(allItems(corpus, seed).map((item) => [item.id, item]));
  return ids.map((id) => byId.get(id)).filter((item): item is ExerciseItem => item !== undefined);
}

/** Параметры адреса версии для печати. */
export function printSearch(
  settings: ExerciseSettings,
  seed: number,
  ids?: readonly string[],
): string {
  const sp = new URLSearchParams({
    kind: settings.kind,
    n: String(settings.count),
    seed: String(seed),
  });
  if (settings.level) sp.set('level', settings.level);
  if (ids && ids.length > 0) sp.set('ids', ids.join(','));
  return sp.toString();
}
