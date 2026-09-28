import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';

import { PairAttribution, SourcesLink } from '../components/Attribution';
import { Container } from '../components/Container';
import { DataGate } from '../components/DataGate';
import { ScrollArea } from '../components/ScrollArea';
import { HighlightedText } from '../components/HighlightedText';
import { AlertIcon, ArrowLeftIcon, ArrowRightIcon, SparkIcon } from '../components/icons';
import { EmptyState, LangBadge, LangLabel, ScoreMeter, StatusBadge } from '../components/ui';
import type { CorpusIndex } from '../data/corpusContext';
import type {
  ArticleAnnotation,
  CaseAnnotation,
  ClassifierAnnotation,
  Lang,
  LlmNote,
  Pair,
} from '../data/types';
import {
  alignmentTypeLabel,
  CASES,
  formatScore,
  LANG_INFO,
  LANGS,
  methodLabel,
  NUMBERS,
  PHENOMENA,
  plural,
} from '../lib/labels';
import { annotationMarks } from '../lib/search';
import { cx, LANG_CLASSES } from '../lib/styles';

function Section({ title, children, id }: { title: string; children: ReactNode; id: string }) {
  return (
    <section aria-labelledby={id} className="mt-12">
      <h2 id={id} className="font-serif text-[24px] font-semibold">
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Th({ children }: { children: ReactNode }) {
  return (
    <th
      scope="col"
      className="px-3 py-2 text-left text-xs font-semibold tracking-wide text-muted uppercase"
    >
      {children}
    </th>
  );
}

function Td({ children, className }: { children: ReactNode; className?: string }) {
  return <td className={cx('px-3 py-2.5 align-top', className)}>{children}</td>;
}

function DisputedNote({ note }: { note: string | undefined }) {
  if (!note) return null;
  return (
    <span className="mt-1 flex items-start gap-1 text-xs text-warn">
      <AlertIcon size={13} className="mt-0.5 shrink-0" />
      {note}
    </span>
  );
}

function ArticleTable({ anns }: { anns: ArticleAnnotation[] }) {
  return (
    <table className="w-full text-[15px]">
      <thead className="border-b border-rule">
        <tr>
          <Th>Артикль</Th>
          <Th>Вид</Th>
          <Th>Существительное</Th>
          <Th>Число</Th>
        </tr>
      </thead>
      <tbody className="divide-y divide-rule">
        {anns.map((a) => (
          <tr key={a.id}>
            <Td className="font-serif font-semibold text-en">{a.text}</Td>
            <Td>
              {a.definite ? 'определённый' : 'неопределённый'}
              {a.value === 'an' && a.next && (
                <span className="block text-xs text-muted">
                  «an» перед гласным звуком: {a.next.text}
                </span>
              )}
            </Td>
            <Td className="font-serif">
              {a.head ? a.head.text : '—'}
              <DisputedNote note={a.disputed ? a.note : undefined} />
            </Td>
            <Td>{a.head?.number ? NUMBERS[a.head.number].short : '—'}</Td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ClassifierTable({ anns, data }: { anns: ClassifierAnnotation[]; data: CorpusIndex }) {
  return (
    <table className="w-full text-[15px]">
      <thead className="border-b border-rule">
        <tr>
          <Th>Конструкция</Th>
          <Th>量词</Th>
          <Th>Значение</Th>
        </tr>
      </thead>
      <tbody className="divide-y divide-rule">
        {anns.map((a) => {
          const info = data.classifierByValue.get(a.value);
          return (
            <tr key={a.id}>
              <Td>
                <span lang="zh-Hans" className="text-[17px]">
                  <span className="text-muted">{a.det.text}</span>
                  <span className="font-semibold text-zh">{a.text}</span>
                  {a.head ? a.head.text : <span className="text-muted"> ∅</span>}
                </span>
                <DisputedNote note={a.disputed ? a.note : undefined} />
              </Td>
              <Td>
                <span lang="zh-Hans" className="font-semibold text-zh">
                  {a.value}
                </span>{' '}
                <span className="text-muted">{a.pinyin}</span>
                <span className="block text-xs text-muted">{a.type}</span>
              </Td>
              <Td className="text-muted">{info?.gloss ?? '—'}</Td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function CaseTable({ anns }: { anns: CaseAnnotation[] }) {
  return (
    <table className="w-full text-[15px]">
      <thead className="border-b border-rule">
        <tr>
          <Th>Слово</Th>
          <Th>Лемма</Th>
          <Th>Падеж</Th>
          <Th>Число</Th>
          <Th>Основание</Th>
        </tr>
      </thead>
      <tbody className="divide-y divide-rule">
        {anns.map((a) => (
          <tr key={a.id}>
            <Td className="font-serif font-semibold text-ru">{a.text}</Td>
            <Td className="font-serif">{a.lemma}</Td>
            <Td>
              {CASES[a.case].label}
              {a.ambiguous && a.alternatives && (
                <span className="block text-xs text-warn">
                  или: {a.alternatives.map((c) => CASES[c].short).join(', ')}
                </span>
              )}
            </Td>
            <Td>{NUMBERS[a.number].short}</Td>
            <Td className="text-xs text-muted">
              {a.prep && <span className="block">предлог «{a.prep}»</span>}
              {a.context
                ?.filter((c) => c !== 'предлог')
                .map((c) => (
                  <span key={c} className="block">
                    {c}
                  </span>
                ))}
              <span className="block">уверенность {formatScore(a.confidence)}</span>
            </Td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function LlmBlock({ note }: { note: LlmNote }) {
  const flagged = note.annotations.filter((a) => !a.ok);
  return (
    <div className="rounded-2xl border border-warn/40 bg-warn-tint p-5">
      <p className="flex items-center gap-2 text-sm font-semibold text-warn">
        <SparkIcon size={16} /> Комментарий LLM · {note.model}
        {note.checked_at && <span className="font-normal">· {note.checked_at}</span>}
      </p>
      <p className="mt-2">{note.summary}</p>
      <p className="mt-2 text-sm">
        <b>Выравнивание:</b> {note.alignment_ok ? 'верно' : 'есть замечание'}
        {note.alignment_comment && ` — ${note.alignment_comment}`}
      </p>
      {flagged.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          {flagged.map((a) => (
            <li key={a.id}>
              <span className="font-mono text-xs">{a.id}</span>: <b>{a.suggestion}</b>
              {a.comment && ` — ${a.comment}`}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-muted">
        Это предложение модели. Данные изменяются только после ручной проверки (через CSV).
      </p>
    </div>
  );
}

function sentenceCount(type: string, lang: Lang): number {
  const parts = type.split('-').map(Number);
  return parts[LANGS.indexOf(lang)] ?? 1;
}

function PairContent({ pair, data }: { pair: Pair; data: CorpusIndex }) {
  const text = data.textById.get(pair.text_id);
  const index = data.pairIndex.get(pair.id) ?? 0;
  const prev = data.corpus.pairs[index - 1];
  const next = data.corpus.pairs[index + 1];

  return (
    <Container className="pt-8 sm:pt-12">
      <nav
        aria-label="Навигация по парам"
        className="flex flex-wrap items-center justify-between gap-3 text-sm"
      >
        <Link to={`/search?text=${pair.text_id}`} className="text-muted hover:text-ink">
          ← {text?.title_ru ?? pair.text_id}: все пары текста
        </Link>
        <div className="flex gap-1">
          {prev ? (
            <Link
              to={`/pair/${prev.id}`}
              className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-muted hover:bg-surface hover:text-ink"
              aria-label={`Предыдущая пара ${prev.id}`}
            >
              <ArrowLeftIcon size={16} /> {prev.id}
            </Link>
          ) : null}
          {next ? (
            <Link
              to={`/pair/${next.id}`}
              className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-muted hover:bg-surface hover:text-ink"
              aria-label={`Следующая пара ${next.id}`}
            >
              {next.id} <ArrowRightIcon size={16} />
            </Link>
          ) : null}
        </div>
      </nav>

      <header className="mt-6 flex animate-fade-up flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[13px] tracking-[0.08em] text-muted uppercase">
            {text ? `${text.title} · ${pair.level ?? text.level}` : pair.text_id} · предложение{' '}
            {pair.position}
          </p>
          <h1 className="mt-1 font-serif text-[34px] font-semibold">
            Пара <span className="font-mono text-[28px]">{pair.id}</span>
          </h1>
        </div>
        <StatusBadge status={pair.status} />
      </header>

      <div className="mt-6 grid gap-5 lg:grid-cols-3">
        {LANGS.map((lang) => {
          const ids = new Set(pair.annotations[lang].map((a) => a.id));
          return (
            <article
              key={lang}
              className={cx(
                'relative animate-fade-up overflow-hidden rounded-2xl border border-rule bg-surface p-6',
              )}
              aria-label={LANG_INFO[lang].name}
            >
              <span
                aria-hidden="true"
                className={cx('absolute inset-x-0 top-0 h-[3px]', LANG_CLASSES[lang].bg)}
              />
              <div className="flex items-center justify-between">
                <LangLabel lang={lang} />
                <span className="text-xs text-muted">
                  {sentenceCount(pair.alignment_type, lang)}{' '}
                  {plural(
                    sentenceCount(pair.alignment_type, lang),
                    'предложение',
                    'предложения',
                    'предложений',
                  )}
                </span>
              </div>
              <HighlightedText
                text={pair[lang]}
                lang={lang}
                marks={annotationMarks(pair[lang], lang, pair.annotations[lang], ids, false)}
                className={cx(
                  'mt-3',
                  lang === 'zh' ? 'text-[21px]' : 'font-serif text-[21px] leading-[1.55]',
                )}
              />
            </article>
          );
        })}
      </div>
      <p className="mt-3 text-sm text-muted">
        Подложкой выделено ключевое слово явления, пунктиром — существительное, к которому относится
        артикль или 量词; волнистой линией — спорная разметка. Наведите курсор на выделение, чтобы
        увидеть подсказку.
      </p>

      <Section title="Выравнивание" id="alignment">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-rule bg-surface p-5">
            <p className="text-sm text-muted">Тип соответствия (EN–ZH–RU)</p>
            <p className="mt-1 font-serif text-[30px] font-semibold">
              {alignmentTypeLabel(pair.alignment_type)}
            </p>
            <p className="text-xs text-muted">число предложений в каждом языке</p>
          </div>
          <div className="rounded-2xl border border-rule bg-surface p-5">
            <p className="text-sm text-muted">alignment_score</p>
            <p
              className={cx(
                'mt-1 font-serif text-[30px] font-semibold',
                pair.alignment.low && 'text-danger',
              )}
            >
              {formatScore(pair.alignment_score)}
            </p>
            <p className="text-xs text-muted">
              {pair.alignment.low
                ? `ниже порога ${formatScore(data.corpus.low_score_threshold)} — стоит проверить`
                : 'минимум из двух попарных оценок'}
            </p>
          </div>
          <div className="rounded-2xl border border-rule bg-surface p-5">
            <p className="text-sm text-muted">Попарные оценки</p>
            <dl className="mt-2 space-y-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <dt className="flex items-center gap-1.5">
                  <LangBadge lang="en" />–<LangBadge lang="zh" />
                </dt>
                <dd>
                  <ScoreMeter
                    score={pair.alignment.en_zh}
                    low={pair.alignment.en_zh < data.corpus.low_score_threshold}
                  />
                </dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="flex items-center gap-1.5">
                  <LangBadge lang="en" />–<LangBadge lang="ru" />
                </dt>
                <dd>
                  <ScoreMeter
                    score={pair.alignment.en_ru}
                    low={pair.alignment.en_ru < data.corpus.low_score_threshold}
                  />
                </dd>
              </div>
            </dl>
          </div>
          <div className="rounded-2xl border border-rule bg-surface p-5">
            <p className="text-sm text-muted">Метод</p>
            <p className="mt-1 font-medium">{methodLabel(pair.alignment.method)}</p>
            <p className="mt-1 text-xs text-muted">английский — опорный язык</p>
          </div>
        </div>
        {pair.llm_note && (
          <div className="mt-5">
            <LlmBlock note={pair.llm_note} />
          </div>
        )}
        {pair.comment && (
          <p className="mt-5 rounded-2xl border border-rule bg-surface p-5">
            <b>Комментарий проверяющего:</b> {pair.comment}
          </p>
        )}
      </Section>

      <Section title="Разметка" id="annotations">
        <div className="grid gap-6">
          {LANGS.map((lang) => {
            const anns = pair.annotations[lang];
            return (
              <ScrollArea
                key={lang}
                label={`Разметка: ${PHENOMENA[LANG_INFO[lang].phenomenon].label}`}
                className="rounded-2xl border border-rule bg-surface"
              >
                <div className="flex items-center justify-between gap-2 border-b border-rule px-4 py-3">
                  <h3 className="flex items-center gap-2 font-semibold">
                    <LangBadge lang={lang} /> {PHENOMENA[LANG_INFO[lang].phenomenon].label}
                  </h3>
                  <span className="text-sm text-muted">{anns.length}</span>
                </div>
                {anns.length === 0 ? (
                  <p className="px-4 py-3 text-sm text-muted">
                    В этом предложении явление не найдено.
                  </p>
                ) : lang === 'en' ? (
                  <ArticleTable anns={pair.annotations.en} />
                ) : lang === 'zh' ? (
                  <ClassifierTable anns={pair.annotations.zh} data={data} />
                ) : (
                  <CaseTable anns={pair.annotations.ru} />
                )}
              </ScrollArea>
            );
          })}
        </div>
      </Section>

      {pair.links && pair.links.length > 0 && (
        <Section title="Переводные эквиваленты" id="links">
          <p className="mb-3 max-w-3xl text-[15px] text-muted">
            Существительные, которые, по статистике корпуса, переводят друг друга: коэффициент Дайса
            по совместной встречаемости в парах и «конкурентное связывание» с учётом позиции слова в
            предложении. Это автоматическая оценка, а не словарь.
          </p>
          <ScrollArea
            label="Переводные эквиваленты"
            className="rounded-2xl border border-rule bg-surface"
          >
            <table className="w-full text-[15px]">
              <thead className="border-b border-rule">
                <tr>
                  {LANGS.map((lang) => (
                    <Th key={lang}>
                      <LangBadge lang={lang} />
                    </Th>
                  ))}
                  <Th>Dice</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {pair.links.map((link, i) => (
                  <tr key={i}>
                    {LANGS.map((lang) => {
                      const span = link[lang];
                      return (
                        <Td
                          key={lang}
                          className={cx(
                            lang === 'zh' ? 'text-[16px]' : 'font-serif',
                            !span && 'text-muted',
                          )}
                        >
                          <span lang={LANG_INFO[lang].htmlLang}>
                            {span ? Array.from(pair[lang]).slice(span[0], span[1]).join('') : '—'}
                          </span>
                        </Td>
                      );
                    })}
                    <Td className="font-mono text-xs text-muted">{formatScore(link.score)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </Section>
      )}

      {text && (
        <Section title="Источник" id="source">
          <dl className="grid gap-x-8 gap-y-2 text-[15px] sm:grid-cols-[10rem_1fr]">
            <dt className="text-muted">Текст</dt>
            <dd>
              {text.title} / {text.title_ru}
              {text.title_zh && (
                <span lang="zh-Hans" className="ml-1">
                  / {text.title_zh}
                </span>
              )}
            </dd>
            <dt className="text-muted">Уровень</dt>
            <dd>
              {pair.level ?? text.level}
              {pair.origin ? (
                <span className="text-muted"> — оценка по длине и частотности лексики</span>
              ) : (
                <span className="text-muted"> — уровень текста</span>
              )}
              {pair.difficulty !== undefined && (
                <span className="text-muted">
                  {' '}
                  (сложность {pair.difficulty.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}
                  )
                </span>
              )}
            </dd>
            <dt className="text-muted">Регистр</dt>
            <dd>{text.register ?? 'учебный'}</dd>
            <dt className="text-muted">Тематика</dt>
            <dd>{text.topic}</dd>
            <dt className="text-muted">Источник</dt>
            <dd>{text.source}</dd>
            {text.license && (
              <>
                <dt className="text-muted">Лицензия</dt>
                <dd>{text.license}</dd>
              </>
            )}
            {pair.origin && (
              <>
                <dt className="text-muted">Авторство</dt>
                <dd>
                  <PairAttribution pair={pair} text={text} />
                </dd>
              </>
            )}
          </dl>
          <p className="mt-4 text-sm">
            <SourcesLink />
          </p>
        </Section>
      )}
    </Container>
  );
}

function PairRoute({ data }: { data: CorpusIndex }) {
  const { id = '' } = useParams();
  const pair = data.pairById.get(id);
  if (!pair) {
    return (
      <Container className="pt-16">
        <EmptyState title="Пара не найдена">
          Возможно, корпус был пересобран и нумерация изменилась.{' '}
          <Link to="/search" className="underline">
            Перейти к поиску
          </Link>
        </EmptyState>
      </Container>
    );
  }
  return <PairContent key={pair.id} pair={pair} data={data} />;
}

export function PairPage() {
  return <DataGate>{(data) => <PairRoute data={data} />}</DataGate>;
}
