# Сравнение методов выравнивания

- Тексты: 8 (my_family, tatoeba, example, letter_xian, market, tea_history, child_language, un_corpus); предложений EN 2641, ZH 2665, RU 2803.
- Условия одинаковы для всех методов: та же сегментация, выравнивание по абзацам, EN — опорный язык, EN–ZH и EN–RU выравниваются отдельно.
- Сравниваются группы предложений в тройках EN–ZH–RU — так, как они попали бы в корпус: граница между группами остаётся, только если её поставили оба попарных выравнивания. Поэтому объединение предложений в одной паре языков отражается и в группах другой.

## Методы и время работы

| Метод | Выполнен | Загрузка, с | Выравнивание, с | Примечание |
|---|---|---:|---:|---|
| bertalign (LaBSE) | нет | — | — | пакет не установлен (bertalign) |
| LaBSE (алгоритм Bertalign) | нет | — | — | пакет не установлен (sentence_transformers) |
| Гейл–Чёрч | да | 0,00 | 0,17 |  |
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
| Гейл–Чёрч — По порядку (базовый) | 99,2 % (2620/2641) | 99,5 % (2627/2641) |

## Показательные расхождения

Отобрано 10: разные тексты и языковые пары, более крупные участки — раньше.

### 1. un_corpus, EN–RU, EN 1183, 1184, 1185, 1186

- **Гейл–Чёрч**:
  - EN 1183 ↔ RU ∅: «This would allow» ↔ «∅»
  - EN 1184 ↔ RU ∅: «(a) the exchange of database information in a structured way,» ↔ «∅»
  - EN 1185–1186 ↔ RU 1292: «(b) independent use of hardware, software and communications media, and (c) easy downloading into the recipients own database and the automation of much of this process.» ↔ «Это должно было позволить a) осуществлять обмен структурированной информацией, содержащейся в базах данных, b) обеспечивать независимое использование аппаратных средств, программного обеспечения и средств связи и c) упр…»
- **По порядку (базовый)**:
  - EN 1183–1186 ↔ RU 1292: «This would allow (a) the exchange of database information in a structured way, (b) independent use of hardware, software and communications media, and (c) easy downloading into the recipients own database and the automa…» ↔ «Это должно было позволить a) осуществлять обмен структурированной информацией, содержащейся в базах данных, b) обеспечивать независимое использование аппаратных средств, программного обеспечения и средств связи и c) упр…»

### 2. un_corpus, EN–ZH, EN 1183, 1184, 1185, 1186

- **Гейл–Чёрч**:
  - EN 1183 ↔ ZH ∅: «This would allow» ↔ «∅»
  - EN 1184 ↔ ZH ∅: «(a) the exchange of database information in a structured way,» ↔ «∅»
  - EN 1185–1186 ↔ ZH 1201: «(b) independent use of hardware, software and communications media, and (c) easy downloading into the recipients own database and the automation of much of this process.» ↔ «这样做就能够(a) 以结构化方式交换数据库信息，(b) 独立使用硬件、软件和通信媒体，(c) 很容易将信息下装到接受者自己的数据库中，并使这一过程大部分实现自动化。»
- **По порядку (базовый)**:
  - EN 1183–1186 ↔ ZH 1201: «This would allow (a) the exchange of database information in a structured way, (b) independent use of hardware, software and communications media, and (c) easy downloading into the recipients own database and the automa…» ↔ «这样做就能够(a) 以结构化方式交换数据库信息，(b) 独立使用硬件、软件和通信媒体，(c) 很容易将信息下装到接受者自己的数据库中，并使这一过程大部分实现自动化。»

### 3. tatoeba, EN–RU, EN 95, 96, 97

- **Гейл–Чёрч**:
  - EN 95–96 ↔ RU 95: «I'd like a doll, a new bicycle.... .» ↔ «Я хочу куклу, новый велосипед... и мир во всём мире!»
  - EN 97 ↔ RU ∅: «and peace on earth!» ↔ «∅»
- **По порядку (базовый)**:
  - EN 95–97 ↔ RU 95: «I'd like a doll, a new bicycle.... . and peace on earth!» ↔ «Я хочу куклу, новый велосипед... и мир во всём мире!»

### 4. tatoeba, EN–ZH, EN 95, 96, 97

- **Гейл–Чёрч**:
  - EN 95–96 ↔ ZH 95: «I'd like a doll, a new bicycle.... .» ↔ «我想要一个洋娃娃，一辆新自行车……»
  - EN 97 ↔ ZH 96: «and peace on earth!» ↔ «以及世界和平。»
- **По порядку (базовый)**:
  - EN 95–97 ↔ ZH 95–96: «I'd like a doll, a new bicycle.... . and peace on earth!» ↔ «我想要一个洋娃娃，一辆新自行车……以及世界和平。»

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

### 9. un_corpus, EN–RU, EN 1049, 1050, 1051

- **Гейл–Чёрч**:
  - EN 1049–1050 ↔ RU 1133–1136: «Source: Adapted from J. D. Hawkins, M. W. Arthur and R. F. Catalano, &quot; Preventing substance abuse &quot; , Crime and Justice: A Review of Research, vol. 19, M. Tonry and D. Farrington, eds.» ↔ «Источник: На основе J.D. Hawkins, M.W. Arthur and R.F. Catalano, &quot; Preventing substance abuse &quot; , Crime and Justice: A Review of Research, vol. 19, M. Tonry and D. Farrington, eds.»
  - EN 1051 ↔ RU 1137–1138: «(Chicago, University of Chicago Press, 1995), table 1, pp. 371-379.» ↔ «(Chicago, University of Chicago Press, 1995), table 1, pp. 371-379.»
- **По порядку (базовый)**:
  - EN 1049–1051 ↔ RU 1133–1138: «Source: Adapted from J. D. Hawkins, M. W. Arthur and R. F. Catalano, &quot; Preventing substance abuse &quot; , Crime and Justice: A Review of Research, vol. 19, M. Tonry and D. Farrington, eds. (Chicago, University of …» ↔ «Источник: На основе J.D. Hawkins, M.W. Arthur and R.F. Catalano, &quot; Preventing substance abuse &quot; , Crime and Justice: A Review of Research, vol. 19, M. Tonry and D. Farrington, eds. (Chicago, University of Chic…»

### 10. un_corpus, EN–ZH, EN 1049, 1050, 1051

- **Гейл–Чёрч**:
  - EN 1049–1050 ↔ ZH 1069: «Source: Adapted from J. D. Hawkins, M. W. Arthur and R. F. Catalano, &quot; Preventing substance abuse &quot; , Crime and Justice: A Review of Research, vol. 19, M. Tonry and D. Farrington, eds.» ↔ «来源：摘自：Hawking,Arthur和Catalano,， &quot; 预防药物滥用 &quot; ，载于《犯罪和司法：调 查概述》，第19卷，编辑Tonry和Farrington（芝加哥：芝加哥大学出版社，1995年），表1，第371－379页。»
  - EN 1051 ↔ ZH ∅: «(Chicago, University of Chicago Press, 1995), table 1, pp. 371-379.» ↔ «∅»
- **По порядку (базовый)**:
  - EN 1049–1051 ↔ ZH 1069: «Source: Adapted from J. D. Hawkins, M. W. Arthur and R. F. Catalano, &quot; Preventing substance abuse &quot; , Crime and Justice: A Review of Research, vol. 19, M. Tonry and D. Farrington, eds. (Chicago, University of …» ↔ «来源：摘自：Hawking,Arthur和Catalano,， &quot; 预防药物滥用 &quot; ，载于《犯罪和司法：调 查概述》，第19卷，编辑Tonry和Farrington（芝加哥：芝加哥大学出版社，1995年），表1，第371－379页。»

## Файлы

- `reports/aligners_time.csv`
- `reports/aligners_time.png`
- `reports/aligners_disagreements.csv`

Пересобрать: `python -m pipeline compare-aligners`.
