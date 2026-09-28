import { Link } from 'react-router-dom';

import {
  AlignmentHistogram,
  ArticleChart,
  CaseChart,
  ClassifierChart,
  TextDensityChart,
} from '../components/charts/StatsCharts';
import { DataTable, StatTile } from '../components/charts/ChartParts';
import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { ScrollArea } from '../components/ScrollArea';
import { PageHeader } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import { formatInt, formatPercent } from '../lib/chartTheme';
import {
  alignmentTypeLabel,
  formatDate,
  formatScore,
  LANGS,
  methodLabel,
  plural,
} from '../lib/labels';

function StatsContent({ stats, corpus, classifierByValue }: CorpusIndex) {
  const t = stats.totals;
  const annotated = t.annotations.article + t.annotations.classifier + t.annotations.case;
  const reviewed = t.status.checked + t.status.corrected;
  const levels = Object.keys(stats.levels);
  const typeRows = Object.entries(stats.alignment.types);

  return (
    <Container className="pt-10 sm:pt-14">
      <PageHeader eyebrow="Статистика корпуса" title="Корпус в цифрах">
        Данные сборки от {formatDate(stats.generated_at)} Под каждым графиком — таблица с теми же
        числами; при наведении на столбец появляется подсказка.
      </PageHeader>

      <section aria-labelledby="totals" className="animate-fade-up">
        <h2 id="totals" className="sr-only">
          Основные показатели
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Троек предложений"
            value={formatInt(t.pairs)}
            detail={`предложений: EN ${t.sentences.en} · ZH ${t.sentences.zh} · RU ${t.sentences.ru}`}
          />
          <StatTile
            label="Текстов"
            value={formatInt(t.texts)}
            detail={`уровни ${levels[0] ?? ''}–${levels.at(-1) ?? ''}`}
          />
          <StatTile
            label="Размеченных явлений"
            value={formatInt(annotated)}
            detail={`спорных: ${t.disputed} (${formatPercent(t.disputed, annotated)})`}
          />
          <StatTile
            label="Проверено вручную"
            value={formatInt(reviewed)}
            detail={`из ${t.pairs} пар · комментариев LLM: ${t.llm_notes}`}
          />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <StatTile
            lang="en"
            label="Артиклей"
            value={formatInt(t.annotations.article)}
            detail={`${formatInt(t.tokens.en)} слов в английской части`}
          />
          <StatTile
            lang="zh"
            label="Конструкций с 量词"
            value={formatInt(t.annotations.classifier)}
            detail={`${t.distinct_classifiers} разных 量词 · ${formatInt(t.tokens.zh)} иероглифов`}
          />
          <StatTile
            lang="ru"
            label="Существительных"
            value={formatInt(t.annotations.case)}
            detail={`неоднозначный падеж: ${t.ambiguous_cases} · ${formatInt(t.tokens.ru)} слов`}
          />
        </div>
      </section>

      <section aria-labelledby="phenomena" className="mt-14">
        <h2 id="phenomena" className="font-serif text-[28px] font-semibold">
          Три явления
        </h2>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <CaseChart stats={stats} />
          <ArticleChart stats={stats} />
          <ClassifierChart stats={stats} classifiers={classifierByValue} />
          <div className="grid content-start gap-5">
            <AlignmentHistogram stats={stats} />
            <div className="rounded-2xl border border-rule bg-surface p-5 sm:p-6">
              <h3 className="text-[17px] font-semibold">Типы соответствий</h3>
              <p className="mt-1 text-sm text-muted">
                Сколько предложений EN–ZH–RU попало в одну тройку. Метод:{' '}
                {methodLabel(stats.alignment.method)}.
              </p>
              <div className="mt-3">
                <DataTable
                  caption="Типы соответствий"
                  head={['Тип EN–ZH–RU', 'Пар', 'Доля']}
                  rows={typeRows.map(([type, count]) => [
                    alignmentTypeLabel(type),
                    count,
                    formatPercent(count, t.pairs),
                  ])}
                />
              </div>
              <p className="mt-3 text-sm">
                <Link
                  to={`/search?max=${stats.alignment.low_score_threshold.toFixed(2)}`}
                  className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
                >
                  Показать пары с низкой оценкой →
                </Link>
              </p>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="texts" className="mt-14">
        <h2 id="texts" className="font-serif text-[28px] font-semibold">
          Сравнение текстов
        </h2>
        <p className="mt-2 max-w-3xl text-muted">
          Плотность явлений нормирована на длину текста, поэтому тексты разного объёма можно
          сравнивать. Каждый график — в цвете своего языка и со своей шкалой.
        </p>
        <div className="mt-5 grid gap-8 rounded-2xl border border-rule bg-surface p-5 sm:p-6">
          {LANGS.map((lang) => (
            <TextDensityChart key={lang} stats={stats} lang={lang} />
          ))}
        </div>
        <ScrollArea
          label="Показатели по текстам"
          className="mt-5 rounded-2xl border border-rule bg-surface p-5 sm:p-6"
        >
          <DataTable
            caption="Показатели по текстам"
            head={[
              'Текст',
              'Уровень',
              'Пар',
              'Слов EN',
              'Иероглифов ZH',
              'Слов RU',
              'Артиклей',
              '量词',
              'Сущ. RU',
              'Средний score',
            ]}
            rows={stats.texts.map((text) => [
              text.title_ru || text.title,
              text.level,
              text.pairs,
              text.words.en,
              text.words.zh,
              text.words.ru,
              text.articles.the + text.articles.a + text.articles.an,
              text.classifiers,
              text.nouns_ru,
              formatScore(text.mean_score),
            ])}
          />
        </ScrollArea>
        <p className="mt-3 text-sm text-muted">
          Всего в корпусе {corpus.texts.length}{' '}
          {plural(corpus.texts.length, 'текст', 'текста', 'текстов')}. Полные данные —{' '}
          <a
            href={`${import.meta.env.BASE_URL}data/stats.json`}
            className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
          >
            stats.json
          </a>
          .
        </p>
      </section>
    </Container>
  );
}

export function StatsPage() {
  return <DataGate>{(data) => <StatsContent {...data} />}</DataGate>;
}
