# Золотой стандарт (`data/gold/gold.json`)

Здесь хранится эталонная разметка — выборка пар, которую **эксперт проверил вручную** в
режиме «Проверка» на сайте корпуса. Файл не генерируется автоматически: pipeline только
читает его (`python -m pipeline evaluate`). Пока файла нет, отчёты сообщают, что данных нет.

## Как получить файл

1. Откройте сайт → «Проверка», задайте объём выборки и seed, разметьте пары.
2. Нажмите «Экспорт gold.json» и сохраните файл в эту папку под именем `gold.json`.
3. Запустите `python -m pipeline evaluate` — отчёт появится в `reports/evaluation.md`.

Продолжить работу на другом компьютере: «Импорт» на той же странице загружает файл обратно.

## Выборка

Пары отбираются пропорционально размеру текстов: внутри каждого текста пары перемешиваются
генератором mulberry32 с заданным seed, k-я пара текста получает ключ (k + сдвиг) / n, и
общий список сортируется по ключу. Первые N пар — выборка. Алгоритм одинаков в
`web/src/lib/gold.ts` и `pipeline/gold.py` (совпадение проверяется тестами на общем файле
`pipeline/tests/fixtures/sample_crosscheck.json`).

## Формат (версия 1)

```jsonc
{
  "format": "corpus-gold",
  "version": 1,
  "annotator": "имя или код эксперта",
  "created_at": "…", "updated_at": "…",
  "corpus": { "generated_at": "…", "alignment_method": "gale_church" }, // сборка, по которой проверяли
  "sample": { "seed": 2026, "size": 30, "strategy": "proportional", "pair_ids": ["…"] },
  "pairs": [{
    "id": "my_family-011", "text_id": "my_family", "reviewed_at": "…",
    "text": { "en": "…", "zh": "…", "ru": "…" },        // снимок текста: evaluate.py сверяет его с корпусом
    "sentences": { "en": [10], "zh": [10, 11], "ru": [10] }, // автоматическое выравнивание (номера предложений)
    "alignment": {
      "zh": { "verdict": "correct" },                           // верно
      "ru": { "verdict": "corrected", "links": [[10, 10]] }    // исправлено: пары [EN, RU]
    },                                                          // "wrong" — ошибка без исправления
    "phenomena": {
      "en": { "mode": "all-correct", "items": [ … ], "missed": [] },
      "zh": { "mode": "itemized", "items": [
        { "id": "zh1", "auto": { … снимок пометки … }, "verdict": "corrected",
          "correction": { "classifier": "本", "head": "书" } }
      ], "missed": [ { "start": 5, "end": 6, "text": "张", "head": "椅子" } ] },
      "ru": { "mode": "itemized", "items": [
        { "id": "ru2", "auto": { … }, "verdict": "corrected",
          "correction": { "case": "gent", "lemma": "книга" } }
      ], "missed": [] }
    },
    "comment": ""
  }]
}
```

- Позиции `start`/`end` — в кодовых точках Unicode, как в `corpus.json`.
- `mode: "all-correct"` — все пометки языка верны и пропусков нет (клавиша 1 в интерфейсе).
- Пара учитывается в оценке, только если проверена полностью. Если после пересборки корпуса
  текст пары изменился, пара считается устаревшей и в расчёт не входит.
- Тестовые файлы в `pipeline/tests/fixtures/` помечены `"synthetic": true` — это выдуманные
  данные для проверки кода, а не эталон.
