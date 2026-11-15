import { describe, expect, it } from 'vitest';

import { emptyReview, pairStatus, setItemVerdict, setLangMode } from './gold';
import {
  alignmentHint,
  alignmentHintLabel,
  applyAlignmentHint,
  applyItemHint,
  applyMissedHint,
  applyRowHint,
  hintLabel,
  isBlind,
  isHintsFile,
  itemHint,
  langSummary,
  markHintsShown,
  missedHints,
  visibleHints,
  type HintsFile,
} from './hints';
import { PAIR_BOOK } from './testFixtures';

/** Синтетические подсказки к паре t-001: падеж «книгу» модель считает ошибкой разметки. */
const HINTS: HintsFile = {
  format: 'corpus-gold-hints',
  version: 1,
  source: 'тестовая модель',
  created_at: '2026-11-15T10:00:00Z',
  blind_pair_ids: ['t-002'],
  pairs: [
    {
      id: 't-001',
      alignment: {
        zh: { verdict: 'correct', note: 'одно предложение — одно предложение' },
        ru: { verdict: 'corrected', links: [[0, 1]] },
      },
      items: {
        en: [{ id: 'en1', verdict: 'correct' }],
        zh: [{ id: 'zh1', verdict: 'correct' }],
        ru: [
          { id: 'ru1', verdict: 'correct' },
          {
            id: 'ru2',
            verdict: 'corrected',
            correction: { case: 'gent', lemma: 'книга' },
            note: 'проверка',
          },
          { id: 'ru3', verdict: null },
        ],
      },
      missed: { zh: [{ start: 2, end: 3, text: '想', head: '', note: 'проверка пропуска' }] },
    },
    { id: 't-002', alignment: { zh: { verdict: 'wrong' } } },
  ],
};

describe('файл подсказок', () => {
  it('распознаёт свой формат и отклоняет чужие файлы', () => {
    expect(isHintsFile(JSON.parse(JSON.stringify(HINTS)))).toBe(true);
    expect(isHintsFile({ ...HINTS, format: 'corpus-gold' })).toBe(false);
    expect(isHintsFile({ ...HINTS, version: 99 })).toBe(false);
    expect(isHintsFile({ ...HINTS, blind_pair_ids: undefined })).toBe(false);
  });

  it('не показывает подсказки для контрольных пар и для пар без записи', () => {
    expect(visibleHints(HINTS, 't-001')?.id).toBe('t-001');
    expect(isBlind(HINTS, 't-002')).toBe(true);
    expect(visibleHints(HINTS, 't-002')).toBeNull();
    expect(visibleHints(HINTS, 't-003')).toBeNull();
    expect(visibleHints(null, 't-001')).toBeNull();
  });
});

describe('подсказки пары', () => {
  const hints = visibleHints(HINTS, 't-001');
  const review = emptyReview(PAIR_BOOK);

  it('подсказка без вердикта не видна; сводка по языку неполная', () => {
    expect(itemHint(hints, 'ru', 'ru3')).toBeNull();
    expect(itemHint(hints, 'ru', 'ru2')?.verdict).toBe('corrected');
    expect(langSummary(hints, review, 'ru')).toBeNull();
    expect(langSummary(hints, review, 'en')).toEqual({ flagged: 0, missed: 0 });
    expect(langSummary(hints, review, 'zh')).toEqual({ flagged: 0, missed: 1 });
  });

  it('подписи называют вердикт и исправление', () => {
    expect(hintLabel('en', { verdict: 'correct' })).toBe('верно');
    expect(
      hintLabel('ru', { verdict: 'corrected', correction: { case: 'gent', lemma: 'книга' } }),
    ).toMatch(/^исправить: падеж .+, лемма книга$/);
    expect(
      hintLabel('zh', { verdict: 'corrected', correction: { classifier: '本', head: '书' } }),
    ).toBe('исправить: счётное слово 本, существительное 书');
    expect(alignmentHintLabel({ verdict: 'corrected', links: [[0, 1]] })).toBe('исправить: 1–2');
    expect(alignmentHintLabel({ verdict: 'wrong' })).toBe('ошибка');
  });

  it('принятие подсказки заполняет вердикт и исправление', () => {
    const zh = alignmentHint(hints, 'zh');
    const ru = alignmentHint(hints, 'ru');
    if (!zh || !ru) throw new Error('нет подсказок выравнивания');
    let next = applyAlignmentHint(applyAlignmentHint(review, 'zh', zh), 'ru', ru);
    expect(next.alignment.zh).toEqual({ verdict: 'correct', links: [] });
    expect(next.alignment.ru).toEqual({ verdict: 'corrected', links: [[0, 1]] });

    const item = itemHint(hints, 'ru', 'ru2');
    if (!item) throw new Error('нет подсказки пометки');
    next = applyItemHint(next, 'ru', 1, item);
    expect(next.phenomena.ru.mode).toBe('itemized');
    expect(next.phenomena.ru.items[1]?.verdict).toBe('corrected');
    expect(next.phenomena.ru.items[1]?.correction).toEqual({ case: 'gent', lemma: 'книга' });
    // Остальные пометки остаются без вердикта: подсказка ничего не заполняет сама.
    expect(next.phenomena.ru.items[0]?.verdict).toBeNull();
  });

  it('предложенный пропуск добавляется один раз и без служебного поля note', () => {
    const [missed] = missedHints(hints, review, 'zh');
    if (!missed) throw new Error('нет подсказки пропуска');
    const next = applyMissedHint(review, 'zh', missed);
    expect(next.phenomena.zh.missed).toEqual([{ start: 2, end: 3, text: '想', head: '' }]);
    expect(missedHints(hints, next, 'zh')).toEqual([]);
  });

  it('клавиша H: строка получает вердикт модели, заголовок явления — режим', () => {
    expect(applyRowHint(review, { kind: 'align', lang: 'zh' }, hints)?.alignment.zh.verdict).toBe(
      'correct',
    );
    expect(applyRowHint(review, { kind: 'lang', lang: 'en' }, hints)?.phenomena.en.mode).toBe(
      'all-correct',
    );
    // Для ZH модель предлагает пропуск — «всё верно» принять нельзя.
    expect(applyRowHint(review, { kind: 'lang', lang: 'zh' }, hints)?.phenomena.zh.mode).toBe(
      'itemized',
    );
    // Для RU модель оценила не все пометки, для третьей пометки подсказки нет.
    expect(applyRowHint(review, { kind: 'lang', lang: 'ru' }, hints)).toBeNull();
    const itemized = setLangMode(review, 'ru', 'itemized');
    expect(applyRowHint(itemized, { kind: 'item', lang: 'ru', index: 2 }, hints)).toBeNull();
    expect(applyRowHint(review, { kind: 'missed', lang: 'zh' }, hints)).toBeNull();
    expect(applyRowHint(review, { kind: 'align', lang: 'zh' }, null)).toBeNull();
  });

  it('пометка «подсказки были на экране» сохраняется и не меняет статус пары', () => {
    const touched = setItemVerdict(review, 'en', 0, 'correct');
    const marked = markHintsShown(touched);
    expect(marked.hints_shown).toBe(true);
    expect(markHintsShown(marked)).toBe(marked);
    expect(pairStatus(marked)).toBe(pairStatus(touched));
    expect(review.hints_shown).toBeUndefined();
  });
});
