# RAG Tutorial — Умняш

Учебный RAG на материалах школьного учебника: TF-IDF + demo-ответ с источниками.
Pipeline: PDF учебника → документы → чанки → индекс → поиск → ответ.

Прототип контентного ядра для **«Умняша»** — AI-помощника по домашним заданиям для младшей школы. Идея: помощник отвечает **строго по методическим материалам учебника**, а не из «головы» модели, и всегда показывает источник.

**Документы:** [doc/DATA.md](doc/DATA.md) — данные · [doc/00_project_idea.md](doc/00_project_idea.md) — идея · [IMPROVEMENTS.md](IMPROVEMENTS.md) — улучшения · [homework/SUBMISSION.md](homework/SUBMISSION.md) — сдача ДЗ

## Требования

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

## Быстрый старт

```bash
# 1. Окружение
uv venv
uv sync

# 2. (опционально) Пересборка датасета из PDF учебника
#    PDF не входит в репозиторий — положить локально в data/raw/pdf/
uv run python scripts/pdf_to_datasets.py data/raw/pdf/Spotlight_2_TB.pdf

# 3. Сборка индекса (ingest + chunk + TF-IDF)
uv run python scripts/build_index.py

# 4. Запуск UI
uv run streamlit run app/main.py
```

Откройте в браузере: http://localhost:8501

> Готовый `data/raw/datasets.json` уже в репозитории, поэтому шаг 2 можно пропустить и сразу собирать индекс.

## Данные

Источник — книга для учителя УМК **«Английский в фокусе» (Spotlight 2)**: планы уроков, лексика, фонетика, методические указания по пяти модулям. Из PDF извлекается текст, сегментируется по урокам и разделам, очищается от артефактов извлечения.

- 154 документа в `datasets.json`
- ~1317 чанков после нарезки

Сам PDF учебника **не включён в репозиторий** (авторское право); хранится только производный обработанный текст. Подробно — в [doc/DATA.md](doc/DATA.md).

## Demo-вопросы

В sidebar приложения или в поле ввода:

| Вопрос | Ожидание |
|--------|----------|
| **Что такое УМК Английский в фокусе?** | ответ + источник |
| **Как работать с диалогом на уроке?** | ответ + источник |
| **Как используются картинки на уроке?** | ответ + источник |
| Столица Австралии | отказ (нет таких данных в учебнике) |

## Скриншоты

**Ответ с источниками:**

![Ответ с источниками](doc/screenshots/answer.png)

**Отказ на вопрос не по теме:**

![Отказ](doc/screenshots/refusal.png)

> Положите скриншоты в `doc/screenshots/` под именами `answer.png` и `refusal.png`.

## Проверка из консоли

```bash
# Тесты (16 шт.: chunking, retrieval, отказ)
uv run pytest tests/ -v
```

## Структура проекта

```
rag-tutorial/
├── app/
│   ├── config.py       # пути, top_k, размер чанка
│   ├── chunker.py      # нарезка текста на чанки
│   ├── retriever.py    # TF-IDF + cosine top-k
│   ├── generator.py    # demo-ответ + относительный критерий отказа
│   ├── prompts.py      # правила, отказы, пороги (MIN_SCORE, MIN_GAP)
│   └── main.py         # Streamlit UI
├── scripts/
│   ├── pdf_to_datasets.py   # PDF учебника → datasets.json
│   ├── ingest.py
│   └── build_index.py
├── data/
│   ├── raw/datasets.json    # подготовленный корпус (коммитится)
│   ├── raw/pdf/             # PDF учебника (НЕ коммитится)
│   ├── processed/           # documents.jsonl, chunks.jsonl (генерируются)
│   └── index/               # vectorizer.pkl, matrix.npz (генерируются)
├── tests/
│   ├── test_chunking.py
│   ├── test_retrieval.py
│   └── test_refusal.py      # тесты относительного критерия отказа
├── doc/
└── IMPROVEMENTS.md
```

## Пересборка индекса

После изменения `data/raw/datasets.json`:

```bash
uv run python scripts/build_index.py
```

Чтобы пересобрать датасет из другого/дополнительного PDF (скрипт принимает несколько файлов):

```bash
uv run python scripts/pdf_to_datasets.py data/raw/pdf/file1.pdf data/raw/pdf/file2.pdf
uv run python scripts/build_index.py
```

## Реализованное улучшение

**Относительный критерий отказа.** Вместо одного абсолютного порога score решение «ответить или отказать» учитывает и отрыв лучшего фрагмента от среднего по top-k. На длинном методическом тексте частые слова дают ненулевой score почти на любой вопрос, поэтому абсолютного порога недостаточно. Подробно — в [IMPROVEMENTS.md](IMPROVEMENTS.md).

## Ограничения MVP

- Поиск по **словам** (TF-IDF), не по смыслу — синонимы могут не находиться.
- Demo-режим: ответ из найденных чанков, без внешней LLM.
- Индексируется только извлечённый текст учебника.
