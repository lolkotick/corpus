import { Link } from 'react-router-dom';

import type { Pair, TextMeta } from '../data/types';
import { LANG_INFO, LANGS } from '../lib/labels';

const LINK = 'underline decoration-rule-strong underline-offset-4 hover:decoration-ink';

/** Указание авторства тройки из импортированного источника (требование лицензии). */
export function PairAttribution({ pair, text }: { pair: Pair; text: TextMeta }) {
  const origin = pair.origin;
  if (!origin) return null;
  if (origin.source === 'tatoeba') {
    return (
      <div>
        <p>
          Предложения из{' '}
          <a href="https://tatoeba.org" className={LINK}>
            Tatoeba
          </a>
          :
        </p>
        <ul className="mt-1 space-y-1">
          {LANGS.map((lang) => {
            const s = origin[lang];
            return (
              <li key={lang}>
                <span className="text-muted">{LANG_INFO[lang].short}:</span>{' '}
                <a href={s.url} className={LINK}>
                  №{s.id}
                </a>
                , автор {s.author ? <b className="font-medium">{s.author}</b> : 'не указан'},{' '}
                {s.license}
              </li>
            );
          })}
        </ul>
      </div>
    );
  }
  return (
    <p>
      Источник — Организация Объединённых Наций,{' '}
      <a href={text.source_url ?? 'https://www.un.org/dgacm/en/content/uncorpus'} className={LINK}>
        Параллельный корпус ООН v1.0
      </a>
      ; {origin.file}, строка {origin.line}
      {origin.line_en_ru ? ` (EN–ZH) и ${origin.line_en_ru} (EN–RU)` : ''}.
    </p>
  );
}

export function SourcesLink() {
  return (
    <Link to="/sources" className={LINK}>
      Источники и лицензии →
    </Link>
  );
}
