# Сравнение методов выравнивания

- Тексты: 8 (my_family, tatoeba, example, letter_xian, market, tea_history, child_language, un_corpus); предложений EN 2637, ZH 2667, RU 2685.
- Условия одинаковы для всех методов: та же сегментация, выравнивание по абзацам, EN — опорный язык, EN–ZH и EN–RU выравниваются отдельно.
- Сравниваются группы предложений в тройках EN–ZH–RU — так, как они попали бы в корпус: граница между группами остаётся, только если её поставили оба попарных выравнивания. Поэтому объединение предложений в одной паре языков отражается и в группах другой.

## Методы и время работы

| Метод | Выполнен | Загрузка, с | Выравнивание, с | Примечание |
|---|---|---:|---:|---|
| bertalign (LaBSE) | нет | — | — | пакет не установлен (bertalign) |
| LaBSE (алгоритм Bertalign) | нет | — | — | пакет не установлен (sentence_transformers) |
| Гейл–Чёрч | да | 0,00 | 0,20 |  |
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
| Гейл–Чёрч — По порядку (базовый) | 99,0 % (2610/2637) | 99,2 % (2617/2637) |

## Показательные расхождения

Отобрано 10: разные тексты и языковые пары, более крупные участки — раньше.

### 1. un_corpus, EN–RU, EN 1238, 1239, 1240, 1241

- **Гейл–Чёрч**:
  - EN 1238 ↔ RU ∅: «He claims to be a victim of violations by Togo of articles 1, paragraphs 1 and 2; 2, paragraph 3» ↔ «∅»
  - EN 1239 ↔ RU ∅: «(a),» ↔ «∅»
  - EN 1240–1241 ↔ RU 1247: «(b) and (c); 7; 9, paragraphs 1, 2, 3 and 5; 10, paragraph 1; 12, paragraph 4; and 17, paragraphs 1 and 2, of the International Covenant on Civil and Political Rights.» ↔ «Он заявляет, что является жертвой нарушения Того пунктов 1 и 2 статьи 1; пунктов 3a, b и c статьи 2; статьи 7; пунктов 1, 2, 3 и 5 статьи 9; пункта 1 статьи 10; пункта 4 статьи 12; пунктов 1 и 2 статьи 17 Международного…»
- **По порядку (базовый)**:
  - EN 1238–1241 ↔ RU 1247: «He claims to be a victim of violations by Togo of articles 1, paragraphs 1 and 2; 2, paragraph 3 (a), (b) and (c); 7; 9, paragraphs 1, 2, 3 and 5; 10, paragraph 1; 12, paragraph 4; and 17, paragraphs 1 and 2, of the Int…» ↔ «Он заявляет, что является жертвой нарушения Того пунктов 1 и 2 статьи 1; пунктов 3a, b и c статьи 2; статьи 7; пунктов 1, 2, 3 и 5 статьи 9; пункта 1 статьи 10; пункта 4 статьи 12; пунктов 1 и 2 статьи 17 Международного…»

### 2. un_corpus, EN–ZH, EN 1238, 1239, 1240, 1241

- **Гейл–Чёрч**:
  - EN 1238 ↔ ZH ∅: «He claims to be a victim of violations by Togo of articles 1, paragraphs 1 and 2; 2, paragraph 3» ↔ «∅»
  - EN 1239 ↔ ZH ∅: «(a),» ↔ «∅»
  - EN 1240–1241 ↔ ZH 1255: «(b) and (c); 7; 9, paragraphs 1, 2, 3 and 5; 10, paragraph 1; 12, paragraph 4; and 17, paragraphs 1 and 2, of the International Covenant on Civil and Political Rights.» ↔ «他称他是多哥侵犯《公民权利和政治权利国际盟约》第1条第1款和第2款、第2条第3款(a)项、(b)项和(c)项、第7条、第9条第1、第2、第3和第5款、第10条第1款、第12条第4款、第17条第1和第2款行为的受害者。»
- **По порядку (базовый)**:
  - EN 1238–1241 ↔ ZH 1255: «He claims to be a victim of violations by Togo of articles 1, paragraphs 1 and 2; 2, paragraph 3 (a), (b) and (c); 7; 9, paragraphs 1, 2, 3 and 5; 10, paragraph 1; 12, paragraph 4; and 17, paragraphs 1 and 2, of the Int…» ↔ «他称他是多哥侵犯《公民权利和政治权利国际盟约》第1条第1款和第2款、第2条第3款(a)项、(b)项和(c)项、第7条、第9条第1、第2、第3和第5款、第10条第1款、第12条第4款、第17条第1和第2款行为的受害者。»

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

### 9. un_corpus, EN–RU, EN 129, 130, 131

- **Гейл–Чёрч**:
  - EN 129 ↔ RU ∅: «The research activities are largely concentrated in» ↔ «∅»
  - EN 130–131 ↔ RU 132: «(a) the Institute for Space Flight Technology and Nuclear Reactor Technology of the Technical University of Braunschweig (IfRR/TUBS) and (b) the Research Establishment for Applied Science of Wachtberg-Werthhoven (FGAN).» ↔ «Научные исследования сосредоточены в основном в а) Технологическом институте космических полетов и ядерных реакторов Технического университета Брауншвейга (ИФРР/ТУБС) и b) Центре прикладных научных исследований Вахтберг…»
- **По порядку (базовый)**:
  - EN 129–131 ↔ RU 132: «The research activities are largely concentrated in (a) the Institute for Space Flight Technology and Nuclear Reactor Technology of the Technical University of Braunschweig (IfRR/TUBS) and (b) the Research Establishment…» ↔ «Научные исследования сосредоточены в основном в а) Технологическом институте космических полетов и ядерных реакторов Технического университета Брауншвейга (ИФРР/ТУБС) и b) Центре прикладных научных исследований Вахтберг…»

### 10. un_corpus, EN–ZH, EN 129, 130, 131

- **Гейл–Чёрч**:
  - EN 129 ↔ ZH ∅: «The research activities are largely concentrated in» ↔ «∅»
  - EN 130–131 ↔ ZH 134: «(a) the Institute for Space Flight Technology and Nuclear Reactor Technology of the Technical University of Braunschweig (IfRR/TUBS) and (b) the Research Establishment for Applied Science of Wachtberg-Werthhoven (FGAN).» ↔ «这些研究活动主要都集中在(a)不伦瑞克技术大学的航天技术和核反应堆技术研究所和(b)Wachtberg-Werthhoven应用科学研究所。»
- **По порядку (базовый)**:
  - EN 129–131 ↔ ZH 134: «The research activities are largely concentrated in (a) the Institute for Space Flight Technology and Nuclear Reactor Technology of the Technical University of Braunschweig (IfRR/TUBS) and (b) the Research Establishment…» ↔ «这些研究活动主要都集中在(a)不伦瑞克技术大学的航天技术和核反应堆技术研究所和(b)Wachtberg-Werthhoven应用科学研究所。»

## Файлы

- `reports/aligners_time.csv`
- `reports/aligners_time.png`
- `reports/aligners_disagreements.csv`

Пересобрать: `python -m pipeline compare-aligners`.
