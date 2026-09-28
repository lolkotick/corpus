/** Типы данных, которые генерирует pipeline (web/public/data/*.json). */

export type Lang = 'en' | 'zh' | 'ru';
export type Status = 'auto' | 'checked' | 'corrected';
export type Level = 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';
export type CaseCode = 'nomn' | 'gent' | 'datv' | 'accs' | 'ablt' | 'loct' | 'voct';
export type NumberCode = 'sing' | 'plur';
export type ArticleValue = 'a' | 'an' | 'the';
export type Phenomenon = 'article' | 'classifier' | 'case';

/** Фрагмент текста: позиции в символах (кодовых точках) внутри сегмента. */
export interface Span {
  start: number;
  end: number;
  text: string;
}

interface AnnotationBase extends Span {
  id: string;
  disputed: boolean;
  note?: string;
}

export interface ArticleAnnotation extends AnnotationBase {
  kind: 'article';
  value: ArticleValue;
  definite: boolean;
  head: (Span & { lemma: string; pos: string | null; number: NumberCode | null }) | null;
  next?: Span;
}

export interface ClassifierAnnotation extends AnnotationBase {
  kind: 'classifier';
  value: string;
  pinyin: string;
  type: string;
  det: Span;
  head: Span | null;
  head_method?: string;
  elliptical?: boolean;
}

export interface CaseAnnotation extends AnnotationBase {
  kind: 'case';
  lemma: string;
  case: CaseCode;
  number: NumberCode;
  gender: string | null;
  animacy: string | null;
  confidence: number;
  ambiguous: boolean;
  subcase?: string;
  prep?: string;
  context?: string[];
  alternatives?: CaseCode[];
  indeclinable?: boolean;
}

export type Annotation = ArticleAnnotation | ClassifierAnnotation | CaseAnnotation;

export interface Annotations {
  en: ArticleAnnotation[];
  zh: ClassifierAnnotation[];
  ru: CaseAnnotation[];
}

export interface LlmAnnotationReview {
  id: string;
  ok: boolean;
  suggestion: string;
  comment: string;
}

export interface LlmNote {
  model: string;
  reasons: string[];
  alignment_ok: boolean;
  alignment_comment: string;
  annotations: LlmAnnotationReview[];
  summary: string;
  suggestions: number;
  checked_at: string;
}

/** Связь переводных эквивалентов: позиции одного слова в двух или трёх языках. */
export interface Link {
  en?: [number, number];
  zh?: [number, number];
  ru?: [number, number];
  score: number;
}

export interface Pair {
  id: string;
  text_id: string;
  position: number;
  en: string;
  zh: string;
  ru: string;
  alignment_type: string;
  alignment_score: number;
  alignment: { method: string; en_zh: number; en_ru: number; low: boolean };
  annotations: Annotations;
  links?: Link[];
  status: Status;
  llm_note: LlmNote | null;
  comment: string;
}

export interface TextMeta {
  id: string;
  title: string;
  title_ru: string;
  title_zh: string;
  source: string;
  topic: string;
  level: Level;
  author: string;
  pairs: number;
}

export interface ClassifierInfo {
  value: string;
  pinyin: string;
  type: string;
  gloss: string;
  examples: string[];
}

export interface Corpus {
  version: number;
  generated_at: string;
  alignment_method: string;
  low_score_threshold: number;
  annotation_methods: Record<Lang, string>;
  texts: TextMeta[];
  classifiers: ClassifierInfo[];
  pairs: Pair[];
}

export interface CaseStat {
  case: CaseCode;
  label: string;
  sing: number;
  plur: number;
  ambiguous: number;
}

export interface ClassifierStat {
  value: string;
  pinyin: string;
  gloss: string;
  type: string;
  count: number;
  nouns: { noun: string; count: number }[];
}

export interface TextStat {
  id: string;
  title: string;
  title_ru: string;
  level: Level;
  pairs: number;
  articles: Record<ArticleValue, number>;
  classifiers: number;
  cases: Partial<Record<CaseCode, number>>;
  nouns_ru: number;
  mean_score: number;
  words: Record<Lang, number>;
  density: {
    articles_per_100_words: number;
    classifiers_per_100_chars: number;
    nouns_per_100_words: number;
  };
}

export interface BuildLog {
  total_seconds: number;
  stages: { name: string; seconds: number; detail: string }[];
  warnings: string[];
  manual: { applied?: number; deleted?: number; skipped?: number };
  lexicon: { entries?: number; links?: number };
  llm: {
    model: string;
    api: boolean;
    candidates: number;
    checked: number;
    suggestions: number;
    note: string;
  };
}

export interface Stats {
  generated_at: string;
  build?: BuildLog;
  totals: {
    pairs: number;
    texts: number;
    sentences: Record<Lang, number>;
    tokens: Record<Lang, number>;
    annotations: Record<Phenomenon, number>;
    distinct_classifiers: number;
    ambiguous_cases: number;
    disputed: number;
    status: Record<Status, number>;
    llm_notes: number;
  };
  levels: Partial<Record<Level, number>>;
  articles: {
    counts: Record<ArticleValue, number>;
    top_heads: Record<'the' | 'a/an', { lemma: string; count: number }[]>;
  };
  classifiers: ClassifierStat[];
  classifier_elliptical: number;
  cases: CaseStat[];
  top_lemmas_ru: { lemma: string; count: number }[];
  alignment: {
    method: string;
    low_score_threshold: number;
    low_count: number;
    mean: number;
    median: number;
    types: Record<string, number>;
    histogram: { from: number; to: number; count: number }[];
  };
  texts: TextStat[];
}
