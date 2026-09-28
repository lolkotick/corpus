# Сравнение методов выравнивания

- Тексты: 8 (my_family, tatoeba, example, letter_xian, market, un_corpus, tea_history, child_language); предложений EN 2692, ZH 2654, RU 2663.
- Условия одинаковы для всех методов: та же сегментация, выравнивание по абзацам, EN — опорный язык, EN–ZH и EN–RU выравниваются отдельно.
- Сравниваются группы предложений в тройках EN–ZH–RU — так, как они попали бы в корпус: граница между группами остаётся, только если её поставили оба попарных выравнивания. Поэтому объединение предложений в одной паре языков отражается и в группах другой.

## Методы и время работы

| Метод | Выполнен | Загрузка, с | Выравнивание, с | Примечание |
|---|---|---:|---:|---|
| bertalign (LaBSE) | нет | — | — | пакет не установлен (bertalign) |
| LaBSE (алгоритм Bertalign) | нет | — | — | пакет не установлен (sentence_transformers) |
| Гейл–Чёрч | да | 0,00 | 0,21 |  |
| По порядку (базовый) | да | 0,00 | 0,04 |  |

Время зависит от компьютера; для нейросетевых методов «загрузка» включает чтение модели LaBSE. Время LLM включает сетевые запросы (из кэша — почти мгновенно).

Как запустить пропущенные методы:

- **bertalign (LaBSE)**: `pip install -r pipeline/requirements-neural.txt` (≈ 2 ГБ, нужен доступ к huggingface.co); пакет bertalign 2.x — Python ≥ 3.12.
- **LaBSE (алгоритм Bertalign)**: `pip install -r pipeline/requirements-neural.txt` (≈ 2 ГБ, нужен доступ к huggingface.co).

## Качество по эталону

**Метрики не рассчитаны:** файл gold.json не найден. Эталон составляет эксперт в режиме «Проверка» на сайте (см. `data/gold/README.md`).

## Согласие методов между собой

Доля предложений EN, которые два метода отнесли к одинаковой группе (эталон не нужен).

| Пара методов | EN–ZH | EN–RU |
|---|---:|---:|
| Гейл–Чёрч — По порядку (базовый) | 97,9 % (2636/2692) | 98,2 % (2643/2692) |

## Показательные расхождения

Отобрано 10: разные тексты и языковые пары, более крупные участки — раньше.

### 1. tatoeba, EN–RU, EN 95, 96, 97

- **Гейл–Чёрч**:
  - EN 95–96 ↔ RU 95: «I'd like a doll, a new bicycle.... .» ↔ «Я хочу куклу, новый велосипед... и мир во всём мире!»
  - EN 97 ↔ RU ∅: «and peace on earth!» ↔ «∅»
- **По порядку (базовый)**:
  - EN 95–97 ↔ RU 95: «I'd like a doll, a new bicycle.... . and peace on earth!» ↔ «Я хочу куклу, новый велосипед... и мир во всём мире!»

### 2. tatoeba, EN–ZH, EN 95, 96, 97

- **Гейл–Чёрч**:
  - EN 95–96 ↔ ZH 95: «I'd like a doll, a new bicycle.... .» ↔ «我想要一个洋娃娃，一辆新自行车……»
  - EN 97 ↔ ZH 96: «and peace on earth!» ↔ «以及世界和平。»
- **По порядку (базовый)**:
  - EN 95–97 ↔ ZH 95–96: «I'd like a doll, a new bicycle.... . and peace on earth!» ↔ «我想要一个洋娃娃，一辆新自行车……以及世界和平。»

### 3. un_corpus, EN–RU, EN 258, 259, 260

- **Гейл–Чёрч**:
  - EN 258–259 ↔ RU 259: «See chap. VII.» ↔ «См. главу VII.]»
  - EN 260 ↔ RU ∅: «]» ↔ «∅»
- **По порядку (базовый)**:
  - EN 258–260 ↔ RU 259: «See chap. VII. ]» ↔ «См. главу VII.]»

### 4. un_corpus, EN–ZH, EN 258, 259, 260

- **Гейл–Чёрч**:
  - EN 258–259 ↔ ZH 257: «See chap. VII.» ↔ «见第七章。»
  - EN 260 ↔ ZH 258: «]» ↔ «]»
- **По порядку (базовый)**:
  - EN 258–260 ↔ ZH 257–258: «See chap. VII. ]» ↔ «见第七章。]»

### 5. example, EN–RU, EN 17, 18

- **Гейл–Чёрч**:
  - EN 17–18 ↔ RU 17–18: «At noon Anna felt hungry. Near the library there is a small café.» ↔ «В полдень Анна проголодалась. Рядом с библиотекой есть маленькое кафе.»
- **По порядку (базовый)**:
  - EN 17 ↔ RU 17: «At noon Anna felt hungry.» ↔ «В полдень Анна проголодалась.»
  - EN 18 ↔ RU 18: «Near the library there is a small café.» ↔ «Рядом с библиотекой есть маленькое кафе.»

### 6. example, EN–ZH, EN 17, 18

- **Гейл–Чёрч**:
  - EN 17–18 ↔ ZH 18: «At noon Anna felt hungry. Near the library there is a small café.» ↔ «中午，安娜饿了，正好图书馆附近有一家小咖啡馆。»
- **По порядку (базовый)**:
  - EN 17 ↔ ZH 18: «At noon Anna felt hungry.» ↔ «中午，安娜饿了，正好图书馆附近有一家小咖啡馆。»
  - EN 18 ↔ ZH 19: «Near the library there is a small café.» ↔ «她点了一杯茶和一块苹果派。»

### 7. child_language, EN–ZH, EN 11

- **Гейл–Чёрч**:
  - EN 11 ↔ ZH 11–12: «They do not simply acquire two separate systems; the two languages constantly interact.» ↔ «他们并不是简单地习得两个独立的系统；两种语言一直在相互影响。»
- **По порядку (базовый)**:
  - EN 11 ↔ ZH 11: «They do not simply acquire two separate systems; the two languages constantly interact.» ↔ «他们并不是简单地习得两个独立的系统；»

### 8. letter_xian, EN–ZH, EN 2

- **Гейл–Чёрч**:
  - EN 2 ↔ ZH 2–3: «I am writing to you from Xi'an, an ancient city in the north-west of China.» ↔ «我在西安给你写信。西安是中国西北部的一座古城。»
- **По порядку (базовый)**:
  - EN 2 ↔ ZH 2: «I am writing to you from Xi'an, an ancient city in the north-west of China.» ↔ «我在西安给你写信。»

### 9. un_corpus, EN–RU, EN 266, 267, 268

- **Гейл–Чёрч**:
  - EN 266–267 ↔ RU 265: «See chap. V.» ↔ «Cм. главу V.]»
  - EN 268 ↔ RU ∅: «]» ↔ «∅»
- **По порядку (базовый)**:
  - EN 266–268 ↔ RU 265: «See chap. V. ]» ↔ «Cм. главу V.]»

### 10. un_corpus, EN–ZH, EN 266, 267, 268

- **Гейл–Чёрч**:
  - EN 266–267 ↔ ZH 264: «See chap. V.» ↔ «见第五章。»
  - EN 268 ↔ ZH 265: «]» ↔ «]»
- **По порядку (базовый)**:
  - EN 266–268 ↔ ZH 264–265: «See chap. V. ]» ↔ «见第五章。]»

## Файлы

- `reports/aligners_time.csv`
- `reports/aligners_time.png`
- `reports/aligners_disagreements.csv`

Пересобрать: `python -m pipeline compare-aligners`.
