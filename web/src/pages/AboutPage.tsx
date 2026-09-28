import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { ScrollArea } from '../components/ScrollArea';
import { AlertIcon, DownloadIcon, ExternalIcon } from '../components/icons';
import { LangBadge, PageHeader } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import { formatDate, formatScore, methodLabel } from '../lib/labels';

const REPO = 'https://github.com/lolkotick/corpus';
const DATA = `${import.meta.env.BASE_URL}data/`;

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <li className="relative grid grid-cols-[2.5rem_1fr] gap-4 pb-8 last:pb-0">
      <span
        aria-hidden="true"
        className="relative z-10 flex size-10 items-center justify-center rounded-full border border-rule-strong bg-surface font-semibold"
      >
        {n}
      </span>
      <div className="pt-1.5">
        <h3 className="text-[17px] font-semibold">{title}</h3>
        <div className="mt-1.5 space-y-2 text-[15.5px] text-ink/85">{children}</div>
      </div>
    </li>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="mt-14">
      <h2 id={id} className="font-serif text-[28px] font-semibold">
        {title}
      </h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function AboutContent({ corpus, stats }: CorpusIndex) {
  const build = stats.build;
  const t = stats.totals;
  const levels = Object.keys(stats.levels);

  return (
    <Container className="pt-10 sm:pt-14">
      <PageHeader eyebrow="О проекте" title="Как устроен учебный параллельный корпус">
        Курсовая работа «Параллельный учебный корпус (английский / китайский / русский) как
        инструмент отработки лексико-грамматических соответствий: проектирование и апробация на
        примере ИИ-ассистированной сборки».
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-3">
        {(
          [
            [
              'en',
              'Артикли',
              'Где английский ставит a, an или the — и что вместо них в китайском и русском.',
            ],
            [
              'zh',
              'Счётные слова 量词',
              'Какое счётное слово требует существительное после числа или 这/那/每.',
            ],
            [
              'ru',
              'Падежи',
              'Какую форму принимает русское существительное там, где в английском и китайском её нет.',
            ],
          ] as const
        ).map(([lang, title, text]) => (
          <div key={lang} className="rounded-2xl border border-rule bg-surface p-5">
            <LangBadge lang={lang} />
            <h2 className="mt-2 font-semibold">{title}</h2>
            <p className="mt-1 text-[14.5px] text-muted">{text}</p>
          </div>
        ))}
      </div>

      <Section id="idea" title="Зачем параллельный корпус">
        <div className="max-w-3xl space-y-3 text-[16.5px]">
          <p>
            Три языка выражают близкие значения разными грамматическими средствами. Английский
            отмечает определённость артиклем. Китайский при счёте обязательно ставит между
            числительным и существительным счётное слово. Русский показывает роль слова в
            предложении падежным окончанием. Для учащегося, у которого родной язык одного типа,
            категории другого языка «невидимы» — отсюда типичные ошибки: пропуск артиклей у
            русскоязычных, «一个书» вместо «一本书», неверные падежные окончания у китайскоязычных.
          </p>
          <p>
            Параллельный корпус показывает одно и то же содержание сразу на трёх языках, поэтому
            соответствия и расхождения видны на живом материале. Разметка связывает каждое явление с
            конкретными словами, а упражнения превращают примеры корпуса в тренировку.
          </p>
        </div>
      </Section>

      <Section id="method" title="Как собран корпус">
        <ol className="relative max-w-3xl before:absolute before:top-5 before:bottom-5 before:left-5 before:w-px before:bg-rule">
          <Step n={1} title="Тексты">
            <p>
              {t.texts} текстов уровней {levels[0]}–{levels.at(-1)} (
              {corpus.texts.map((x) => x.title_ru).join(', ')}). Каждый текст — три файла (en.txt,
              zh.txt, ru.txt) и описание meta.json: название, источник, тематика, уровень.
            </p>
          </Step>
          <Step n={2} title="Сегментация">
            <p>
              Деление на предложения: pysbd для английского, razdel для русского, для китайского —
              правила по знакам 。！？；… с учётом закрывающих кавычек 」”.
            </p>
          </Step>
          <Step n={3} title="Выравнивание">
            <p>
              Английский — опорный язык: пары EN–ZH и EN–RU выравниваются отдельно и объединяются в
              тройки по английским предложениям. Допускаются соответствия 1–1, 1–2 и 2–1. Основной
              метод — LaBSE-эмбеддинги по алгоритму Bertalign, запасной — метод Гейла–Чёрча по длине
              предложений. Этот корпус собран методом: <b>{methodLabel(corpus.alignment_method)}</b>
              .
            </p>
            <p>
              Для каждой тройки записываются тип соответствия и оценка alignment_score (0…1) — по
              более слабой из двух пар. Пары ниже порога {formatScore(corpus.low_score_threshold)}{' '}
              отправляются на проверку.
            </p>
          </Step>
          <Step n={4} title="Разметка">
            <ul className="list-disc space-y-1 pl-5">
              <li>
                <b>EN:</b> артикли и существительное, к которому они относятся (
                {corpus.annotation_methods.en}).
              </li>
              <li>
                <b>ZH:</b> конструкция «числительное / 这 / 那 / 几 / 每 + 量词 + существительное» (
                {corpus.annotation_methods.zh}); список 量词 редактируется в файле.
              </li>
              <li>
                <b>RU:</b> падеж, число и лемма существительных ({corpus.annotation_methods.ru}):
                учитываются предлоги, согласование, числительные и порядок слов; неуверенные случаи
                помечаются как спорные.
              </li>
            </ul>
            <p>Разметка хранится как позиции символов — сам текст не изменяется.</p>
          </Step>
          <Step n={5} title="Переводные эквиваленты">
            <p>
              Существительные трёх языков связываются по статистике совместной встречаемости
              (коэффициент Дайса) с «конкурентным связыванием» и учётом позиции в предложении.
              Благодаря этому поиск подсвечивает перевод найденного слова в других колонках.
            </p>
          </Step>
          <Step n={6} title="Проверка: человек и LLM">
            <p>
              Корпус выгружается в CSV; исправления и статусы (проверено / исправлено) импортируются
              обратно и применяются при каждой пересборке. Необязательный модуль LLM-проверки
              (модель {build?.llm.model ?? 'из конфигурации'}) просматривает пары с низкой оценкой и
              спорную разметку и записывает предложение исправления и комментарий — данные меняет
              только человек.
            </p>
          </Step>
          <Step n={7} title="Экспорт и сайт">
            <p>
              Pipeline сохраняет corpus.json, corpus.csv и stats.json; сайт (React) — статический и
              читает эти файлы. Журнал сборки фиксирует время каждого этапа, предупреждения и число
              правок LLM.
            </p>
          </Step>
        </ol>
      </Section>

      {build && (
        <Section id="build" title="Журнал последней сборки">
          <p className="max-w-3xl text-muted">
            Сборка от {formatDate(stats.generated_at)}, общее время{' '}
            {build.total_seconds.toLocaleString('ru-RU')} с. Полный журнал — в файле{' '}
            <a
              href={`${REPO}/blob/main/logs/build_report.md`}
              className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
            >
              logs/build_report.md
            </a>
            .
          </p>
          <ScrollArea
            label="Этапы сборки"
            className="mt-4 rounded-2xl border border-rule bg-surface"
          >
            <table className="w-full min-w-[34rem] text-[14.5px]">
              <caption className="sr-only">Этапы сборки</caption>
              <thead>
                <tr className="border-b border-rule text-left text-muted">
                  <th scope="col" className="px-4 py-2.5 font-medium">
                    Этап
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium whitespace-nowrap">
                    Время, с
                  </th>
                  <th scope="col" className="px-4 py-2.5 font-medium">
                    Результат
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {build.stages.map((stage) => (
                  <tr key={stage.name}>
                    <td className="px-4 py-2">{stage.name}</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {stage.seconds.toLocaleString('ru-RU', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>
                    <td className="px-4 py-2 text-muted">{stage.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
          <dl className="mt-4 grid gap-3 text-[15px] sm:grid-cols-3">
            <div className="rounded-xl border border-rule bg-surface p-4">
              <dt className="text-sm text-muted">LLM-проверка</dt>
              <dd className="mt-1">
                {build.llm.api ? 'запросы к API' : 'без запросов к API'} · проверено{' '}
                {build.llm.checked} из {build.llm.candidates} кандидатов, предложено правок:{' '}
                {build.llm.suggestions}
              </dd>
            </div>
            <div className="rounded-xl border border-rule bg-surface p-4">
              <dt className="text-sm text-muted">Ручные правки</dt>
              <dd className="mt-1">
                применено {build.manual.applied ?? 0}, удалено пар {build.manual.deleted ?? 0}
              </dd>
            </div>
            <div className="rounded-xl border border-rule bg-surface p-4">
              <dt className="text-sm text-muted">Словарь эквивалентов</dt>
              <dd className="mt-1">
                {build.lexicon.entries ?? 0} пар лемм, {build.lexicon.links ?? 0} связей
              </dd>
            </div>
          </dl>
          {build.warnings.length > 0 && (
            <div className="mt-4 rounded-xl border border-warn/40 bg-warn-tint p-4 text-[14.5px]">
              <p className="flex items-center gap-2 font-semibold text-warn">
                <AlertIcon size={16} /> Предупреждения сборки
              </p>
              <ul className="mt-1 list-disc pl-5">
                {build.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </Section>
      )}

      <Section id="limits" title="Ограничения">
        <ul className="max-w-3xl list-disc space-y-2 pl-5 text-[16px]">
          <li>
            Тексты корпуса составлены и переведены с помощью ИИ для демонстрации метода; перед
            использованием на занятиях их должен проверить преподаватель.
          </li>
          <li>
            Корпус небольшой ({t.pairs} троек), поэтому статистика и словарь эквивалентов
            показательны, но не репрезентативны.
          </li>
          <li>
            Метод Гейла–Чёрча опирается только на длину предложений и хуже справляется со свободными
            переводами, чем LaBSE.
          </li>
          <li>
            Разметка автоматическая. pymorphy3 не видит синтаксиса, поэтому часть падежей определена
            эвристиками ({t.ambiguous_cases} случаев помечены как неоднозначные); jieba ошибается в
            границах слов, поэтому существительное после 量词 ищется по правилам.
          </li>
          <li>
            В упражнениях по падежам засчитывается только форма из корпуса; объяснения строятся по
            правилам и не заменяют преподавателя.
          </li>
        </ul>
      </Section>

      <Section id="tech" title="Технологии и данные">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-rule bg-surface p-5 text-[15px]">
            <h3 className="font-semibold">Pipeline (Python 3.11)</h3>
            <p className="mt-1 text-muted">
              pysbd, razdel, jieba, pymorphy3, spaCy, sentence-transformers (LaBSE, необязательно),
              Anthropic API (необязательно), pytest.
            </p>
          </div>
          <div className="rounded-2xl border border-rule bg-surface p-5 text-[15px]">
            <h3 className="font-semibold">Сайт</h3>
            <p className="mt-1 text-muted">
              React, TypeScript, Vite, Tailwind CSS, Recharts; ESLint, Prettier, Vitest; доступность
              проверяется axe-core; деплой — GitHub Pages.
            </p>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-3 text-[15px]">
          {(['corpus.json', 'corpus.csv', 'stats.json'] as const).map((file) => (
            <a
              key={file}
              href={`${DATA}${file}`}
              download
              className="inline-flex items-center gap-2 rounded-xl border border-rule-strong bg-surface px-4 py-2 hover:border-ink/40"
            >
              <DownloadIcon size={16} /> {file}
            </a>
          ))}
          <a
            href={REPO}
            className="inline-flex items-center gap-2 rounded-xl border border-rule-strong bg-surface px-4 py-2 hover:border-ink/40"
          >
            <ExternalIcon size={16} /> Исходный код на GitHub
          </a>
        </div>
        <p className="mt-6 text-muted">
          Начать работу:{' '}
          <Link to="/search" className="text-ink underline underline-offset-4">
            поиск по корпусу
          </Link>
          ,{' '}
          <Link to="/exercises" className="text-ink underline underline-offset-4">
            упражнения
          </Link>
          ,{' '}
          <Link to="/stats" className="text-ink underline underline-offset-4">
            статистика
          </Link>
          .
        </p>
      </Section>
    </Container>
  );
}

export function AboutPage() {
  return <DataGate>{(data) => <AboutContent {...data} />}</DataGate>;
}
