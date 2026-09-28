# Сравнение методов выравнивания

- Тексты: 6 (my_family, example, letter_xian, market, tea_history, child_language); предложений EN 111, ZH 115, RU 111.
- Условия одинаковы для всех методов: та же сегментация, выравнивание по абзацам, EN — опорный язык, EN–ZH и EN–RU выравниваются отдельно.
- Сравниваются группы предложений в тройках EN–ZH–RU — так, как они попали бы в корпус: граница между группами остаётся, только если её поставили оба попарных выравнивания. Поэтому объединение предложений в одной паре языков отражается и в группах другой.

## Методы и время работы

| Метод | Выполнен | Загрузка, с | Выравнивание, с | Примечание |
|---|---|---:|---:|---:|
| bertalign (LaBSE) | нет | — | — | пакет не установлен (bertalign) |
| LaBSE (алгоритм Bertalign) | нет | — | — | пакет не установлен (sentence_transformers) |
| Гейл–Чёрч | да | 0,00 | 0,01 |  |
| LLM (Claude) | нет | — | — | нет ANTHROPIC_API_KEY в .env — метод пропущен |
| По порядку (базовый) | да | 0,00 | 0,01 |  |

Время зависит от компьютера; для нейросетевых методов «загрузка» включает чтение модели LaBSE. Время LLM включает сетевые запросы (из кэша — почти мгновенно).

Как запустить пропущенные методы:

- **bertalign (LaBSE)**: `pip install -r pipeline/requirements-neural.txt` (≈ 2 ГБ, нужен доступ к huggingface.co); пакет bertalign 2.x — Python ≥ 3.12.
- **LaBSE (алгоритм Bertalign)**: `pip install -r pipeline/requirements-neural.txt` (≈ 2 ГБ, нужен доступ к huggingface.co).
- **LLM**: добавьте `ANTHROPIC_API_KEY=…` в файл `.env` в корне проекта (запросы платные; ответы кэшируются в `data/llm_cache/align/`).

## Качество по эталону

**Метрики не рассчитаны:** файл gold.json не найден. Эталон составляет эксперт в режиме «Проверка» на сайте (см. `data/gold/README.md`).

## Согласие методов между собой

Доля предложений EN, которые два метода отнесли к одинаковой группе (эталон не нужен).

| Пара методов | EN–ZH | EN–RU |
|---|---:|---:|
| Гейл–Чёрч — По порядку (базовый) | 90,1 % (100/111) | 96,4 % (107/111) |

## Показательные расхождения

Отобрано 10: разные тексты и языковые пары, более крупные участки — раньше.

### 1. example, EN–RU, EN 17, 18

- **Гейл–Чёрч**:
  - EN 17–18 ↔ RU 17–18: «At noon Anna felt hungry. Near the library there is a small café.» ↔ «В полдень Анна проголодалась. Рядом с библиотекой есть маленькое кафе.»
- **По порядку (базовый)**:
  - EN 17 ↔ RU 17: «At noon Anna felt hungry.» ↔ «В полдень Анна проголодалась.»
  - EN 18 ↔ RU 18: «Near the library there is a small café.» ↔ «Рядом с библиотекой есть маленькое кафе.»

### 2. example, EN–ZH, EN 17, 18

- **Гейл–Чёрч**:
  - EN 17–18 ↔ ZH 18: «At noon Anna felt hungry. Near the library there is a small café.» ↔ «中午，安娜饿了，正好图书馆附近有一家小咖啡馆。»
- **По порядку (базовый)**:
  - EN 17 ↔ ZH 18: «At noon Anna felt hungry.» ↔ «中午，安娜饿了，正好图书馆附近有一家小咖啡馆。»
  - EN 18 ↔ ZH 19: «Near the library there is a small café.» ↔ «她点了一杯茶和一块苹果派。»

### 3. child_language, EN–ZH, EN 11

- **Гейл–Чёрч**:
  - EN 11 ↔ ZH 11–12: «They do not simply acquire two separate systems; the two languages constantly interact.» ↔ «他们并不是简单地习得两个独立的系统；两种语言一直在相互影响。»
- **По порядку (базовый)**:
  - EN 11 ↔ ZH 11: «They do not simply acquire two separate systems; the two languages constantly interact.» ↔ «他们并不是简单地习得两个独立的系统；»

### 4. letter_xian, EN–ZH, EN 2

- **Гейл–Чёрч**:
  - EN 2 ↔ ZH 2–3: «I am writing to you from Xi'an, an ancient city in the north-west of China.» ↔ «我在西安给你写信。西安是中国西北部的一座古城。»
- **По порядку (базовый)**:
  - EN 2 ↔ ZH 2: «I am writing to you from Xi'an, an ancient city in the north-west of China.» ↔ «我在西安给你写信。»

### 5. example, EN–RU, EN 19, 20

- **Гейл–Чёрч**:
  - EN 19 ↔ RU 19: «She ordered a cup of tea and a piece of apple pie.» ↔ «Она заказала чашку чая и кусок яблочного пирога.»
  - EN 20 ↔ RU 20: «The tea was hot, and the pie was delicious.» ↔ «Чай был горячим, а пирог — очень вкусным.»
- **По порядку (базовый)**:
  - EN 19–20 ↔ RU 19–20: «She ordered a cup of tea and a piece of apple pie. The tea was hot, and the pie was delicious.» ↔ «Она заказала чашку чая и кусок яблочного пирога. Чай был горячим, а пирог — очень вкусным.»

### 6. example, EN–ZH, EN 19, 20

- **Гейл–Чёрч**:
  - EN 19 ↔ ZH 19: «She ordered a cup of tea and a piece of apple pie.» ↔ «她点了一杯茶和一块苹果派。»
  - EN 20 ↔ ZH 20: «The tea was hot, and the pie was delicious.» ↔ «茶很热，派也很好吃。»
- **По порядку (базовый)**:
  - EN 19–20 ↔ ZH 20: «She ordered a cup of tea and a piece of apple pie. The tea was hot, and the pie was delicious.» ↔ «茶很热，派也很好吃。»

### 7. child_language, EN–ZH, EN 12

- **Гейл–Чёрч**:
  - EN 12 ↔ ZH 13–14: «A Russian-speaking child learning English, for example, may at first omit articles, because Russian has no such category, while a Chinese-speaking child may struggle with the case endings of Russian nouns.» ↔ «例如，一个学英语的俄罗斯孩子一开始可能会漏掉冠词，因为俄语里没有这个语法范畴；而一个说汉语的孩子在学俄语时，可能很难掌握名词的格词尾。»
- **По порядку (базовый)**:
  - EN 12 ↔ ZH 12–14: «A Russian-speaking child learning English, for example, may at first omit articles, because Russian has no such category, while a Chinese-speaking child may struggle with the case endings of Russian nouns.» ↔ «两种语言一直在相互影响。例如，一个学英语的俄罗斯孩子一开始可能会漏掉冠词，因为俄语里没有这个语法范畴；而一个说汉语的孩子在学俄语时，可能很难掌握名词的格词尾。»

### 8. letter_xian, EN–ZH, EN 3

- **Гейл–Чёрч**:
  - EN 3 ↔ ZH 4: «I arrived here three days ago with a group of students from our university.» ↔ «三天前，我和我们大学的一群学生来到这里。»
- **По порядку (базовый)**:
  - EN 3 ↔ ZH 3: «I arrived here three days ago with a group of students from our university.» ↔ «西安是中国西北部的一座古城。»

### 9. example, EN–ZH, EN 24

- **Гейл–Чёрч**:
  - EN 24 ↔ ZH 24–25: «"Come again next Saturday," she said.» ↔ «“下个星期六再来吧！”她说。»
- **По порядку (базовый)**:
  - EN 24 ↔ ZH 24: «"Come again next Saturday," she said.» ↔ «“下个星期六再来吧！”»

### 10. letter_xian, EN–ZH, EN 4

- **Гейл–Чёрч**:
  - EN 4 ↔ ZH 5: «We are staying in a hotel near the old city wall.» ↔ «我们住在古城墙附近的一家酒店里。»
- **По порядку (базовый)**:
  - EN 4 ↔ ZH 4–5: «We are staying in a hotel near the old city wall.» ↔ «三天前，我和我们大学的一群学生来到这里。我们住在古城墙附近的一家酒店里。»

## Файлы

- `reports/aligners_time.csv`
- `reports/aligners_time.png`
- `reports/aligners_disagreements.csv`

Пересобрать: `python -m pipeline compare-aligners`.
