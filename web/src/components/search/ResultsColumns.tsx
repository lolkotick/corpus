import { Link } from 'react-router-dom';

import type { CorpusIndex } from '../../data/corpusContext';
import { alignmentTypeLabel, LANG_INFO, LANGS } from '../../lib/labels';
import type { SearchResult } from '../../lib/search';
import { cx, LANG_CLASSES } from '../../lib/styles';
import { HighlightedText } from '../HighlightedText';
import { SparkIcon } from '../icons';
import { LangLabel, ScoreMeter, StatusBadge } from '../ui';

const textClass = {
  en: 'font-serif text-[16.5px] leading-[1.6]',
  zh: 'text-[16px]',
  ru: 'font-serif text-[16.5px] leading-[1.6]',
} as const;

function PairMeta({ result, data }: { result: SearchResult; data: CorpusIndex }) {
  const { pair } = result;
  const text = data.textById.get(pair.text_id);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted md:block md:space-y-1.5">
      <Link
        to={`/pair/${pair.id}`}
        className="font-mono text-[12.5px] text-ink/80 underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
        aria-label={`Пара ${pair.id}: подробный разбор`}
      >
        {pair.id}
      </Link>
      <span className="block" title="Тип соответствия EN–ZH–RU">
        {alignmentTypeLabel(pair.alignment_type)}
        {text && <span className="ml-1.5">· {text.level}</span>}
      </span>
      <ScoreMeter score={pair.alignment_score} low={pair.alignment.low} />
      {pair.status !== 'auto' && <StatusBadge status={pair.status} />}
      {pair.llm_note && (
        <span className="inline-flex items-center gap-1 text-warn" title={pair.llm_note.summary}>
          <SparkIcon size={13} /> LLM
        </span>
      )}
    </div>
  );
}

export function ResultsColumns({
  results,
  data,
}: {
  results: readonly SearchResult[];
  data: CorpusIndex;
}) {
  return (
    <div>
      <div
        aria-hidden="true"
        className="sticky top-[61px] z-10 hidden grid-cols-[7.5rem_repeat(3,minmax(0,1fr))] gap-7 border-b border-rule bg-paper/95 py-2.5 backdrop-blur md:grid"
      >
        <span className="text-[11.5px] font-semibold tracking-[0.1em] text-muted uppercase">
          Пара
        </span>
        {LANGS.map((lang) => (
          <LangLabel key={lang} lang={lang} />
        ))}
      </div>
      <ol className="divide-y divide-rule" aria-label="Найденные пары">
        {results.map((result) => (
          <li
            key={result.pair.id}
            className="grid gap-3 py-5 md:grid-cols-[7.5rem_repeat(3,minmax(0,1fr))] md:gap-7"
          >
            <PairMeta result={result} data={data} />
            {LANGS.map((lang) => (
              <div key={lang} className="grid grid-cols-[2rem_1fr] gap-2 md:block">
                <span
                  className={cx(
                    'pt-1 text-[11px] font-semibold tracking-wider md:hidden',
                    LANG_CLASSES[lang].text,
                  )}
                  aria-hidden="true"
                >
                  {LANG_INFO[lang].short}
                </span>
                <HighlightedText
                  text={result.pair[lang]}
                  lang={lang}
                  marks={result.marks[lang]}
                  className={textClass[lang]}
                />
              </div>
            ))}
          </li>
        ))}
      </ol>
    </div>
  );
}
