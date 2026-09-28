import { Link } from 'react-router-dom';

import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { HighlightedText } from '../components/HighlightedText';
import { ArrowRightIcon } from '../components/icons';
import { LangBadge, LangLabel } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import type { Pair, Phenomenon } from '../data/types';
import { LANGS, PHENOMENA, plural } from '../lib/labels';
import { annotationMarks } from '../lib/search';
import { buttonClasses, cx, LANG_CLASSES } from '../lib/styles';

/** Пара для витрины: во всех трёх языках есть разметка, соответствие 1–1–1, короткий текст. */
function showcasePair(pairs: readonly Pair[]): Pair | undefined {
  const candidates = pairs.filter(
    (p) =>
      p.alignment_type === '1-1-1' &&
      p.annotations.en.length >= 2 &&
      p.annotations.zh.length >= 2 &&
      p.annotations.ru.length >= 2 &&
      p.en.length < 90,
  );
  return candidates.find((p) => p.en.includes('cup of tea')) ?? candidates[0] ?? pairs[0];
}

const PHENOMENON_EXAMPLES: Record<Phenomenon, string> = {
  article: 'a book · an umbrella · the river',
  classifier: '一本书 · 两张桌子 · 那只狗',
  case: 'в библиотеку · у реки · с мамой',
};

function Showcase({ pair }: { pair: Pair }) {
  return (
    <figure className="animate-fade-up rounded-2xl border border-rule bg-surface p-6 shadow-soft [animation-delay:120ms] sm:p-7">
      <div className="grid gap-6 md:grid-cols-3 md:gap-7">
        {LANGS.map((lang) => {
          const ids = new Set(pair.annotations[lang].map((a) => a.id));
          return (
            <div key={lang}>
              <LangLabel lang={lang} />
              <HighlightedText
                text={pair[lang]}
                lang={lang}
                marks={annotationMarks(pair[lang], lang, pair.annotations[lang], ids, false)}
                className={cx(
                  'mt-2.5',
                  lang === 'zh' ? 'text-[18px]' : 'font-serif text-[19px] leading-[1.55]',
                )}
              />
            </div>
          );
        })}
      </div>
      <figcaption className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-rule pt-4 text-sm text-muted">
        <span>
          Цветом отмечены артикль, счётное слово 量词 и существительные с падежной разметкой.
        </span>
        <Link
          to={`/pair/${pair.id}`}
          className="inline-flex items-center gap-1 font-medium text-ink"
        >
          Разбор пары <ArrowRightIcon size={16} />
        </Link>
      </figcaption>
    </figure>
  );
}

function HomeContent({ corpus, stats }: CorpusIndex) {
  const pair = showcasePair(corpus.pairs);
  const annotated =
    stats.totals.annotations.article +
    stats.totals.annotations.classifier +
    stats.totals.annotations.case;
  const levels = Object.keys(stats.levels);
  const levelRange = levels.length > 1 ? `${levels[0] ?? ''}–${levels.at(-1) ?? ''}` : levels[0];
  const numbers = [
    {
      value: stats.totals.pairs,
      label: plural(
        stats.totals.pairs,
        'тройка предложений',
        'тройки предложений',
        'троек предложений',
      ),
    },
    {
      value: stats.totals.texts,
      label: `${plural(stats.totals.texts, 'текст', 'текста', 'текстов')}, уровни ${levelRange ?? ''}`,
    },
    { value: stats.totals.distinct_classifiers, label: 'разных счётных слов 量词' },
    { value: annotated, label: 'размеченных явлений' },
  ];

  return (
    <>
      <Container className="pt-14 pb-10 sm:pt-20">
        <div className="max-w-[980px] animate-fade-up">
          <p className="text-[13px] tracking-[0.08em] text-muted uppercase">
            Учебный корпус · английский · китайский · русский
          </p>
          <h1 className="mt-4 font-serif text-[38px] leading-[1.1] font-semibold tracking-[-0.01em] sm:text-[52px]">
            Одно предложение — три языка и{' '}
            <span className="bg-[linear-gradient(transparent_62%,var(--zh-tint)_0)]">
              три грамматики
            </span>
          </h1>
          <p className="mt-5 max-w-[62ch] text-[18.5px] text-muted">
            Сравнивайте, как английский выражает определённость артиклем, китайский считает предметы
            с помощью счётного слова, а русский показывает роль слова падежом. Каждое явление
            размечено, найдено в параллельных предложениях и превращено в упражнения.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/search" className={buttonClasses.primary}>
              Искать в корпусе <ArrowRightIcon size={18} />
            </Link>
            <Link to="/exercises" className={buttonClasses.ghost}>
              Упражнения
            </Link>
          </div>
        </div>
      </Container>

      <Container>{pair && <Showcase pair={pair} />}</Container>

      <Container>
        <dl className="mt-12 grid grid-cols-2 border-t border-rule md:grid-cols-4">
          {numbers.map((n) => (
            <div key={n.label} className="py-6 pr-4">
              <dd className="font-serif text-[40px] leading-none font-semibold tabular-nums">
                {n.value}
              </dd>
              <dt className="mt-2 text-[13.5px] text-muted">{n.label}</dt>
            </div>
          ))}
        </dl>
      </Container>

      <Container className="mt-10">
        <h2 className="sr-only">Три явления</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {(Object.keys(PHENOMENA) as Phenomenon[]).map((phen) => {
            const info = PHENOMENA[phen];
            const c = LANG_CLASSES[info.lang];
            return (
              <Link
                key={phen}
                to={`/search?phen=${phen}`}
                className="group relative overflow-hidden rounded-2xl border border-rule bg-surface p-6 transition hover:-translate-y-0.5 hover:shadow-soft"
              >
                <span
                  aria-hidden="true"
                  className={cx('absolute inset-y-0 left-0 w-[3px]', c.bg)}
                />
                <LangBadge lang={info.lang} />
                <h3 className="mt-3 text-[17px] font-semibold">{info.label}</h3>
                <p className="mt-1.5 text-[14.5px] text-muted">{info.description}</p>
                <p
                  className={cx('mt-4 text-[15px]', info.lang === 'zh' ? '' : 'font-serif', c.text)}
                  lang={info.lang === 'zh' ? 'zh-Hans' : info.lang}
                >
                  {PHENOMENON_EXAMPLES[phen]}
                </p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-ink/80 group-hover:text-ink">
                  {stats.totals.annotations[phen]} в корпусе <ArrowRightIcon size={15} />
                </span>
              </Link>
            );
          })}
        </div>
      </Container>

      <Container className="mt-16">
        <div className="flex items-end justify-between gap-4">
          <h2 className="font-serif text-[28px] font-semibold">Тексты корпуса</h2>
          <Link to="/stats" className="text-sm text-muted hover:text-ink">
            Статистика по текстам →
          </Link>
        </div>
        <ul className="mt-5 divide-y divide-rule border-y border-rule">
          {corpus.texts.map((text) => (
            <li key={text.id}>
              <Link
                to={`/search?text=${text.id}`}
                className="grid grid-cols-[3rem_1fr_auto] items-baseline gap-4 py-4 transition hover:bg-surface/60 sm:grid-cols-[3.5rem_1fr_1fr_auto]"
              >
                <span className="font-mono text-sm text-muted">{text.level}</span>
                <span>
                  <span className="font-serif text-[17px] font-semibold">{text.title_ru}</span>
                  <span className="block text-sm text-muted sm:hidden">{text.title}</span>
                </span>
                <span className="hidden text-muted sm:block">
                  <span className="font-serif">{text.title}</span>
                  {text.title_zh && (
                    <span lang="zh-Hans" className="ml-3 text-[15px]">
                      {text.title_zh}
                    </span>
                  )}
                </span>
                <span className="text-sm text-muted tabular-nums">
                  {text.pairs} {plural(text.pairs, 'пара', 'пары', 'пар')}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Container>
    </>
  );
}

export function HomePage() {
  return <DataGate>{(data) => <HomeContent {...data} />}</DataGate>;
}
