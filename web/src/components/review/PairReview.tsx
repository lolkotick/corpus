import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import type { CorpusIndex } from '../../data/corpusContext';
import type { Lang, Pair } from '../../data/types';
import {
  addMissed,
  alignmentWindow,
  removeMissed,
  setItemFix,
  toggleLink,
  updateMissed,
  type GoldPair,
  type ItemReview,
  type MissedItem,
  type Snapshot,
  type TargetLang,
} from '../../lib/gold';
import {
  alignmentTypeLabel,
  CASES,
  formatScore,
  LANG_INFO,
  NUMBERS,
  PHENOMENA,
  plural,
} from '../../lib/labels';
import { REVIEW_LANGS, rowDone, rowKey, type Row } from '../../lib/reviewRows';
import { annotationMarks } from '../../lib/search';
import { cx, LANG_CLASSES } from '../../lib/styles';
import { codePointConverter, type MarkRange } from '../../lib/text';
import { HighlightedText } from '../HighlightedText';
import { AlertIcon, ExternalIcon } from '../icons';
import { LangBadge, LangLabel } from '../ui';
import { AlignmentMatrix } from './AlignmentMatrix';
import { ChoiceButtons, Kbd, ReviewRow, VerdictButtons } from './controls';
import { FixForm, MissedPicker } from './FixForm';

export interface PairReviewProps {
  data: CorpusIndex;
  pair: Pair;
  review: GoldPair;
  rows: readonly Row[];
  focus: number;
  editRow: string | null;
  picker: Lang | null;
  onFocus: (index: number) => void;
  onKey: (row: Row, key: '1' | '2' | '3') => void;
  onChange: (review: GoldPair) => void;
  onEditDone: () => void;
  onPicker: (lang: Lang | null) => void;
}

function snapshotLabel(auto: Snapshot): ReactNode {
  switch (auto.kind) {
    case 'article':
      return (
        <>
          <b className="font-semibold text-en">{auto.text}</b>
          <span className="text-muted"> → </span>
          {auto.head ? auto.head.text : <span className="text-muted">нет существительного</span>}
        </>
      );
    case 'classifier':
      return (
        <span lang="zh-Hans" className="font-zh text-[17px]">
          <span className="text-muted">{auto.det.text}</span>
          <b className="font-semibold text-zh">{auto.text}</b>
          <span className="text-muted"> → </span>
          {auto.head ? auto.head.text : <span className="text-muted">∅</span>}
        </span>
      );
    case 'case':
      return (
        <>
          <b className="font-semibold text-ru">{auto.text}</b>
          <span className="text-muted">
            {' '}
            · {CASES[auto.case].label.toLowerCase()},{' '}
            {auto.number === 'plur' ? NUMBERS.plur.short : NUMBERS.sing.short} · {auto.lemma}
          </span>
        </>
      );
  }
}

function missedLabel(lang: Lang, item: MissedItem): string {
  if (lang === 'ru')
    return `${item.text} · ${item.case ? CASES[item.case].short : '?'} · ${item.lemma ?? ''}`;
  return `${item.text}${item.head ? ` → ${item.head}` : ''}`;
}

const ALIGN_TITLE: Record<TargetLang, string> = { zh: 'EN – ZH', ru: 'EN – RU' };

export function PairReview(props: PairReviewProps) {
  const { data, pair, review, rows, focus } = props;
  const text = data.textById.get(pair.text_id);
  const focusedRow = rows[focus];

  const indexOf = (row: Row) => rows.findIndex((r) => rowKey(r) === rowKey(row));
  const rowProps = (row: Row) => {
    const i = indexOf(row);
    return {
      rowId: rowKey(row),
      focused: i === focus,
      done: rowDone(review, row),
      onFocus: () => props.onFocus(i),
    };
  };

  // Подсветка: все пометки языка — слабо, пометка под курсором — сильно; пропуски — жёлтым.
  function marksFor(lang: Lang): MarkRange[] {
    const anns = pair.annotations[lang];
    const strong = new Set<string>();
    if (focusedRow?.kind === 'item' && focusedRow.lang === lang) {
      const id = review.phenomena[lang].items[focusedRow.index]?.id;
      if (id) strong.add(id);
    } else if (focusedRow && focusedRow.kind !== 'align' && focusedRow.lang === lang) {
      anns.forEach((a) => strong.add(a.id));
    }
    const marks = annotationMarks(pair[lang], lang, anns, strong, true);
    const convert = codePointConverter(pair[lang]);
    for (const m of review.phenomena[lang].missed) {
      marks.push({
        start: convert(m.start),
        end: convert(m.end),
        kind: 'query',
        lang,
        title: 'Пропуск, добавленный при проверке',
      });
    }
    return marks;
  }

  return (
    <article aria-labelledby="review-pair-title" className="mt-6">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="review-pair-title" className="font-serif text-[22px] font-semibold">
          {text?.title ?? pair.text_id}
          <span className="ml-2 font-sans text-[14px] font-normal text-muted">
            {text?.level} · пара {pair.position} · {alignmentTypeLabel(pair.alignment_type)} ·
            оценка {formatScore(pair.alignment_score)}
          </span>
        </h2>
        <Link
          to={`/pair/${pair.id}`}
          className="inline-flex items-center gap-1 text-sm text-muted underline decoration-rule-strong underline-offset-4 hover:text-ink"
        >
          Карточка пары <ExternalIcon size={14} />
        </Link>
      </header>

      <div className="mt-4 grid gap-4 rounded-2xl border border-rule bg-surface p-5 md:grid-cols-3">
        {REVIEW_LANGS.map((lang) => (
          <div key={lang}>
            <LangLabel lang={lang} />
            <HighlightedText
              text={pair[lang]}
              lang={lang}
              marks={marksFor(lang)}
              className={cx(
                'mt-2 leading-relaxed',
                lang === 'zh' ? 'font-zh text-[19px]' : 'font-serif text-[18px]',
              )}
            />
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="review-align" className="lg:col-span-2">
          <h3
            id="review-align"
            className="mb-2 text-[13px] font-semibold tracking-[0.08em] text-muted uppercase"
          >
            Выравнивание
          </h3>
          <div className="grid gap-1.5">
            {(['zh', 'ru'] as const).map((lang) => {
              const row: Row = { kind: 'align', lang };
              const a = review.alignment[lang];
              return (
                <ReviewRow key={lang} {...rowProps(row)}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-[15px]">
                      <b className="font-semibold">{ALIGN_TITLE[lang]}</b>
                      <span className="ml-2 text-sm text-muted">
                        автоматически: EN {review.sentences.en.map((i) => i + 1).join(', ')} ↔{' '}
                        {LANG_INFO[lang].short}{' '}
                        {review.sentences[lang].length
                          ? review.sentences[lang].map((i) => i + 1).join(', ')
                          : '—'}{' '}
                        · оценка {formatScore(pair.alignment[lang === 'zh' ? 'en_zh' : 'en_ru'])}
                      </span>
                    </p>
                    <VerdictButtons
                      label={`Выравнивание ${ALIGN_TITLE[lang]}`}
                      value={a.verdict}
                      onChange={(v) =>
                        props.onKey(row, v === 'correct' ? '1' : v === 'wrong' ? '2' : '3')
                      }
                    />
                  </div>
                  {a.verdict === 'corrected' && text && (
                    <AlignmentMatrix
                      text={text}
                      lang={lang}
                      window={alignmentWindow(data.corpus, pair, lang)}
                      own={{ en: review.sentences.en, target: review.sentences[lang] }}
                      links={a.links}
                      onToggle={(e, t) => props.onChange(toggleLink(review, lang, e, t))}
                    />
                  )}
                  {a.verdict === 'corrected' && a.links.length === 0 && (
                    <p className="mt-2 flex items-center gap-1.5 text-[13px] text-warn">
                      <AlertIcon size={14} /> Отметьте хотя бы одно соответствие
                    </p>
                  )}
                </ReviewRow>
              );
            })}
          </div>
        </section>

        {REVIEW_LANGS.map((lang) => (
          <PhenomenonSection key={lang} lang={lang} {...props} rowProps={rowProps} />
        ))}

        <section aria-labelledby="review-comment">
          <h3
            id="review-comment"
            className="mb-2 text-[13px] font-semibold tracking-[0.08em] text-muted uppercase"
          >
            Комментарий
          </h3>
          <label className="sr-only" htmlFor="review-comment-field">
            Комментарий к паре
          </label>
          <textarea
            id="review-comment-field"
            rows={3}
            value={review.comment}
            onChange={(e) => props.onChange({ ...review, comment: e.target.value })}
            placeholder="Необязательно: что заметили в паре"
            className="w-full rounded-xl border border-rule-strong bg-surface px-3 py-2 text-[15px] outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-ink/20"
          />
        </section>
      </div>
    </article>
  );
}

function PhenomenonSection({
  lang,
  pair,
  review,
  editRow,
  picker,
  onKey,
  onChange,
  onEditDone,
  onPicker,
  rowProps,
}: PairReviewProps & {
  lang: Lang;
  rowProps: (row: Row) => {
    rowId: string;
    focused: boolean;
    done: boolean;
    onFocus: () => void;
  };
}) {
  const phen = review.phenomena[lang];
  const info = PHENOMENA[LANG_INFO[lang].phenomenon];
  const headRow: Row = { kind: 'lang', lang };
  const n = phen.items.length;
  const current = pair.annotations[lang];

  return (
    <section aria-labelledby={`review-${lang}`}>
      <h3
        id={`review-${lang}`}
        className={cx(
          'mb-2 flex items-center gap-2 text-[13px] font-semibold tracking-[0.08em] uppercase',
          LANG_CLASSES[lang].text,
        )}
      >
        <LangBadge lang={lang} /> {info.label}
      </h3>
      <div className="grid gap-1.5">
        <ReviewRow {...rowProps(headRow)}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[15px]">
              {n === 0
                ? 'Автоматических пометок нет'
                : `${String(n)} ${plural(n, 'пометка', 'пометки', 'пометок')}`}
              <span className="block text-[13px] text-muted">
                {n === 0 ? 'пропусков тоже нет?' : 'все верны и пропусков нет?'}
              </span>
            </p>
            <ChoiceButtons
              label={info.label}
              value={
                phen.mode === 'all-correct' ? 'all' : phen.mode === 'itemized' ? 'items' : null
              }
              options={[
                { value: 'all', label: 'Всё верно', key: '1', tone: 'correct' },
                {
                  value: 'items',
                  label: n === 0 ? 'Есть пропуск' : 'Проверить по одной',
                  key: '2',
                  tone: 'corrected',
                },
              ]}
              onChange={(v) => onKey(headRow, v === 'all' ? '1' : '2')}
            />
          </div>
        </ReviewRow>

        {phen.mode === 'itemized' &&
          phen.items.map((item: ItemReview, index) => {
            const row: Row = { kind: 'item', lang, index };
            const key = rowKey(row);
            const disputed = current.find((a) => a.id === item.id)?.disputed;
            return (
              <ReviewRow key={item.id} {...rowProps(row)} className="ml-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p lang={LANG_INFO[lang].htmlLang} className="text-[15.5px]">
                    {snapshotLabel(item.auto)}
                    {disputed && (
                      <span
                        lang="ru"
                        className="ml-2 rounded bg-warn-tint px-1.5 py-0.5 text-[11.5px] text-warn"
                      >
                        спорная
                      </span>
                    )}
                  </p>
                  <VerdictButtons
                    label={`Пометка ${item.auto.text}`}
                    value={item.verdict}
                    onChange={(v) => onKey(row, v === 'correct' ? '1' : v === 'wrong' ? '2' : '3')}
                  />
                </div>
                {item.verdict === 'corrected' && item.correction && (
                  <div className="mt-3">
                    <FixForm
                      lang={lang}
                      fix={item.correction}
                      focusFirst={editRow === key}
                      onChange={(fix) => onChange(setItemFix(review, lang, index, fix))}
                      onDone={onEditDone}
                    />
                  </div>
                )}
              </ReviewRow>
            );
          })}

        {phen.mode === 'itemized' && (
          <ReviewRow {...rowProps({ kind: 'missed', lang })} className="ml-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-[14.5px] text-muted">
                Пропуски
                {phen.missed.length > 0 ? `: ${String(phen.missed.length)}` : ' — не добавлены'}
              </p>
              {picker !== lang && (
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onPicker(lang);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13.5px] font-medium text-muted ring-1 ring-rule-strong ring-inset hover:bg-sunken hover:text-ink"
                >
                  <Kbd>Enter</Kbd> Добавить пропуск
                </button>
              )}
            </div>
            {phen.missed.length > 0 && (
              <ul className="mt-2 grid gap-2">
                {phen.missed.map((m, i) => (
                  <li key={m.start} className="rounded-lg bg-query/40 p-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span lang={LANG_INFO[lang].htmlLang} className="text-[15px] font-medium">
                        {missedLabel(lang, m)}
                      </span>
                      <button
                        type="button"
                        className="text-[13px] text-muted underline underline-offset-4 hover:text-danger"
                        onClick={(event) => {
                          event.stopPropagation();
                          onChange(removeMissed(review, lang, i));
                        }}
                      >
                        удалить
                      </button>
                    </div>
                    <div className="mt-2">
                      <FixForm
                        lang={lang}
                        fix={m}
                        showClassifier={false}
                        onChange={(fix) => onChange(updateMissed(review, lang, i, fix))}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {picker === lang && (
              <MissedPicker
                text={pair[lang]}
                lang={lang}
                taken={[...phen.items.map((it) => it.auto), ...phen.missed]}
                onAdd={(item) => {
                  onChange(addMissed(review, lang, item));
                  onPicker(null);
                }}
                onCancel={() => onPicker(null)}
              />
            )}
          </ReviewRow>
        )}
      </div>
    </section>
  );
}
