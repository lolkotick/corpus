import type { ReactNode } from 'react';

import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { DownloadIcon, ExternalIcon } from '../components/icons';
import { ScrollArea } from '../components/ScrollArea';
import { PageHeader } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import { formatInt } from '../lib/chartTheme';
import { plural } from '../lib/labels';
import { groupByRegister, tatoebaAuthors, unViaOpus } from '../lib/sources';

const DATA = `${import.meta.env.BASE_URL}data/`;
const REPO = 'https://github.com/lolkotick/corpus';
/** Когда условия лицензий сверялись с официальными страницами. */
const CHECKED_AT = '28 сентября 2026 г.';
const LINK = 'underline decoration-rule-strong underline-offset-4 hover:decoration-ink';

function Ext({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} className={`${LINK} inline-flex items-center gap-1`}>
      {children}
      <ExternalIcon size={13} className="shrink-0 text-muted" />
    </a>
  );
}

function Card({
  id,
  title,
  badge,
  children,
}: {
  id: string;
  title: string;
  badge?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="rounded-2xl border border-rule bg-surface p-5 sm:p-7">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={id} className="font-serif text-[26px] font-semibold">
          {title}
        </h2>
        {badge && (
          <span className="rounded-full border border-rule px-2.5 py-0.5 text-[13px] text-muted">
            {badge}
          </span>
        )}
      </header>
      <div className="mt-4 space-y-3 text-[15.5px] text-ink/85">{children}</div>
    </section>
  );
}

function Terms({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-[11rem_1fr]">
      {rows.map(([term, value]) => (
        <div key={term} className="contents">
          <dt className="text-muted">{term}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function SourcesContent({ corpus }: CorpusIndex) {
  const groups = groupByRegister(corpus);
  const tatoebaText = corpus.texts.find((t) => t.id === 'tatoeba');
  const unText = corpus.texts.find((t) => t.id === 'un_corpus');
  const authors = tatoebaAuthors(corpus);
  const viaOpus = unViaOpus(corpus);
  const projectTexts = corpus.texts.filter((t) => t.id !== 'tatoeba' && t.id !== 'un_corpus');

  return (
    <Container className="pt-10 sm:pt-14">
      <PageHeader eyebrow="Источники" title="Откуда данные и как их можно использовать">
        Для каждого источника указаны лицензия и то, как её условия выполняются в корпусе. Условия
        сверены с официальными страницами {CHECKED_AT}; перед публикацией работы проверьте, не
        изменились ли они.
      </PageHeader>

      <section aria-labelledby="registers" className="mb-10">
        <h2 id="registers" className="sr-only">
          Состав корпуса
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {groups.map((g) => (
            <div key={g.register} className="rounded-2xl border border-rule bg-surface p-5">
              <p className="text-[13.5px] text-muted">Регистр: {g.register}</p>
              <p className="mt-2 text-[28px] leading-none font-semibold">
                {formatInt(g.pairs)}{' '}
                <span className="text-[15px] font-normal text-muted">
                  {plural(g.pairs, 'пара', 'пары', 'пар')}
                </span>
              </p>
              <p className="mt-2 text-[13px] text-muted">
                {g.texts.map((t) => t.title_ru || t.title).join(' · ')}
              </p>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-6">
        <Card id="src-tatoeba" title="Tatoeba" badge="бытовой регистр">
          <p>
            <Ext href="https://tatoeba.org">Tatoeba</Ext> — открытая база предложений и их
            переводов, которую пополняют участники. В корпус берутся тройки: английское предложение
            с прямыми переводами на китайский (только упрощённые иероглифы) и на русский; фильтры —
            длина, повторы и хотя бы одно из трёх изучаемых явлений.
          </p>
          <Terms
            rows={[
              [
                'Лицензия',
                <>
                  <Ext href="https://creativecommons.org/licenses/by/2.0/fr/">CC BY 2.0 FR</Ext> (по
                  умолчанию); часть предложений доступна также под{' '}
                  <Ext href="https://creativecommons.org/publicdomain/zero/1.0/">CC0 1.0</Ext>.
                </>,
              ],
              [
                'Требование',
                'Использовать, изменять и распространять предложение можно при условии, что указано имя его автора (условие BY).',
              ],
              [
                'Как выполняется',
                'У каждой пары сохранены номер каждого предложения на tatoeba.org, имя автора и лицензия; они показаны в карточке пары и собраны в attribution.csv.',
              ],
              [
                'Официально',
                <span key="t" className="flex flex-wrap gap-x-4">
                  <Ext href="https://tatoeba.org/terms_of_use">Условия использования</Ext>
                  <Ext href="https://tatoeba.org/downloads">Выгрузки</Ext>
                </span>,
              ],
            ]}
          />
          {tatoebaText ? (
            <div>
              <p>
                В корпусе {formatInt(tatoebaText.pairs)}{' '}
                {plural(tatoebaText.pairs, 'пара', 'пары', 'пар')} из Tatoeba:{' '}
                {formatInt(authors.sentences)}{' '}
                {plural(authors.sentences, 'предложение', 'предложения', 'предложений')} от{' '}
                {formatInt(authors.authors.length)}{' '}
                {plural(authors.authors.length, 'автора', 'авторов', 'авторов')}; под CC0 1.0 —{' '}
                {formatInt(authors.cc0)}
                {authors.anonymous > 0 && `, автор не указан в выгрузке — ${authors.anonymous}`}.
              </p>
              <details className="mt-2 border-t border-rule pt-2 text-sm">
                <summary className="cursor-pointer text-muted select-none hover:text-ink">
                  Авторы предложений
                </summary>
                <ScrollArea label="Авторы предложений Tatoeba" className="mt-2 max-h-72">
                  <p className="leading-relaxed">
                    {authors.authors.map((a) => `${a.author} (${a.sentences})`).join(', ')}
                  </p>
                </ScrollArea>
              </details>
            </div>
          ) : (
            <p className="text-muted">
              Данные Tatoeba ещё не импортированы: <code>python -m pipeline import tatoeba</code>.
            </p>
          )}
        </Card>

        <Card id="src-un" title="Параллельный корпус ООН v1.0" badge="официальный регистр">
          <p>
            <Ext href="https://www.un.org/dgacm/en/content/uncorpus">
              United Nations Parallel Corpus v1.0
            </Ext>{' '}
            — официальные отчёты и другие парламентские документы ООН 1990–2014 годов на шести
            официальных языках. В корпус берётся ограниченный фрагмент (по умолчанию 2000 троек) с
            теми же фильтрами, что и для Tatoeba.
          </p>
          <Terms
            rows={[
              ['Статус', 'Документы ООН, входящие в корпус, находятся в общественном достоянии.'],
              [
                'Требования',
                <ul key="req" className="list-disc space-y-1 pl-5">
                  <li>указывать Организацию Объединённых Наций как источник информации;</li>
                  <li>
                    при упоминании корпуса ссылаться на статью: Ziemski M., Junczys-Dowmunt M.,
                    Pouliquen B. The United Nations Parallel Corpus v1.0 // LREC 2016. Portorož,
                    2016. P. 3530–3534;
                  </li>
                  <li>корпус предоставляется без каких-либо гарантий.</li>
                </ul>,
              ],
              [
                'Как выполняется',
                'Источник и ссылка на статью указаны в описании текста и в карточке каждой пары; для пары сохранены файл и номер строки.',
              ],
              [
                'Официально',
                <span key="u" className="flex flex-wrap gap-x-4">
                  <Ext href="https://www.un.org/dgacm/en/content/uncorpus">Страница корпуса</Ext>
                  <Ext href="https://www.un.org/dgacm/en/content/uncorpus/download">Загрузка</Ext>
                  <Ext href="https://aclanthology.org/L16-1561/">Статья LREC 2016</Ext>
                </span>,
              ],
            ]}
          />
          {viaOpus && (
            <p>
              Фрагмент получен из попарных выгрузок этого корпуса на{' '}
              <Ext href="https://opus.nlpl.eu/UNPC/corpus/version/UNPC">OPUS (UNPC v1.0)</Ext>; OPUS
              просит также ссылаться на статью: Tiedemann J. Parallel Data, Tools and Interfaces in
              OPUS // LREC 2012.
            </p>
          )}
          {!unText && (
            <p className="text-muted">
              Данные ООН ещё не импортированы: <code>python -m pipeline import un</code> (как
              положить файлы вручную — в README).
            </p>
          )}
        </Card>

        <Card id="src-project" title="Учебные тексты проекта" badge="учебный регистр">
          <p>
            {projectTexts.length}{' '}
            {plural(
              projectTexts.length,
              'текст составлен',
              'текста составлены',
              'текстов составлены',
            )}{' '}
            для корпуса с помощью ИИ; переводы требуют проверки преподавателем. Источник каждого
            текста — в карточке пары.
          </p>
          <Terms
            rows={[
              [
                'Лицензия',
                <>
                  <Ext href={`${REPO}/blob/main/LICENSE`}>MIT</Ext>, © 2026 Лебедев Глеб Романович —
                  вместе с кодом проекта (pipeline и сайт).
                </>,
              ],
              ['Требование', 'В копиях сохранять уведомление об авторском праве и текст лицензии.'],
              [
                'Не распространяется',
                'на предложения Tatoeba и документы ООН: для них действуют условия, указанные выше, в том числе в файлах corpus.json, corpus.csv и attribution.csv.',
              ],
            ]}
          />
        </Card>

        <Card id="src-tools" title="Ресурсы, использованные при импорте">
          <Terms
            rows={[
              [
                'wordfreq',
                <>
                  частотности слов для оценки сложности:{' '}
                  <Ext href="https://github.com/rspeer/wordfreq">код — Apache 2.0</Ext>, данные о
                  частотности — CC BY-SA 4.0 (по сведениям пакета).
                </>,
              ],
              [
                'OpenCC',
                <>
                  проверка упрощённых иероглифов (opencc-python-reimplemented, лицензия Apache 2.0).
                </>,
              ],
            ]}
          />
        </Card>
      </div>

      <p className="mt-8 flex flex-wrap items-center gap-2 text-sm">
        <DownloadIcon size={16} className="text-muted" />
        <a href={`${DATA}attribution.csv`} className={LINK} download>
          attribution.csv
        </a>
        <span className="text-muted">
          — авторство каждого импортированного предложения (пара, язык, номер, автор, лицензия,
          ссылка).
        </span>
      </p>
    </Container>
  );
}

export function SourcesPage() {
  return <DataGate>{(data) => <SourcesContent {...data} />}</DataGate>;
}
