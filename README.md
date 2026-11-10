# AI-buddy — ИИ-наставник для стажёров

Локальный прототип для Авито Hack&Change 2026. Все демонстрационные команды, люди и задачи
синтетические; приложение не является официальным сервисом Авито.

Реализованы вход по email/паролю, выход, персональный кабинет, команда и наставник,
дата старта/день стажировки, список задач, изменение статусов и расчёт прогресса из PostgreSQL.
Роли intern, mentor, manager проверяются сервером. У наставника и руководителя пока минимальный
кабинет своей роли и команды. Добавлены DeepSeek-чат и локальный RAG; для RAG необходима
подготовка pgvector по инструкции ниже. Создание корпоративных заявок пока не подключено.

## Стек и структура

Python 3.14, FastAPI, SQLAlchemy 2.1, PostgreSQL 17, Alembic, Pydantic, pwdlib/Argon2, PyJWT,
Pytest/pytest-cov, OpenAI-совместимый клиент DeepSeek, Sentence Transformers, CPU PyTorch и pgvector.
Frontend: React 19, TypeScript, Vite, React Router, TanStack Query,
Lucide, обычный CSS; Vitest и React Testing Library.

```text
backend/
  app/
    api/          # HTTP: auth, teams, onboarding, assistant, knowledge
    services/     # авторизация, адаптация, LLM, embeddings, RAG, индексация
    models/       # пользователи, команды, задачи, диалоги, документы и векторы
    schemas/      # Pydantic запросы и ответы
    core/         # окружение
    db/           # SQLAlchemy сессии
  alembic/versions/
  scripts/        # seed, миграция тестовой БД, preload, индексация, оценка RAG, smoke
  knowledge/      # 12 синтетических Markdown-инструкций и контрольные вопросы
  tests/
frontend/
  src/
    components/   # layout, карточки, задачи, состояния
    pages/        # login, dashboard/onboarding, assistant, knowledge, заглушки
    api.ts        # единственный HTTP-клиент, типы
    session.ts    # профиль и QueryClient
    App.tsx       # маршруты и защита
    styles.css
  package-lock.json
docs/             # правила доступа, SDD, подготовка pgvector, отчёты и скриншоты
compose.yaml
.env.example
```

## 1. Настройка

Нужны Python 3.14, Node.js 22.12+ (проверено с Node 26), npm и PostgreSQL 17 / Docker Compose.
Все команды ниже выполняются из корня, кроме явно указанных переходов.

```bash
# Только при первой настройке; существующий .env не перезаписывать:
cp -n .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

В `.env` задайте собственные POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, вставьте
сгенерированное значение в JWT_SECRET. Не заменяйте существующий `.env`, если он уже настроен:
добавьте новые параметры вручную. `.env` игнорируется Git. Пароли БД и JWT_SECRET не передавайте
во frontend. COOKIE_SECURE=false допустим только для локального HTTP, при HTTPS — true.
ALLOWED_ORIGINS — JSON-массив точных адресов frontend без завершающего `/`.

## 2. PostgreSQL

Для новой локальной установки Compose использует PostgreSQL 17 с pgvector. Если контейнер
создавался на прежнем образе без расширения, сначала выполните
[переход с резервной копией](docs/pgvector-setup.md); простой запуск ниже предназначен для
новой установки или уже подготовленного сервера. Существующий volume сохраняется.

```bash
docker compose up -d db
```

Если доступ к Docker требует sudo, выполните эту команду самостоятельно:

```bash
sudo docker compose up -d db
```

Не удаляйте volume и не пересоздавайте БД. При существующем volume пароль должен соответствовать
первоначально настроенному пользователю PostgreSQL: изменение `.env` не меняет пароль в БД.
Тестовую БД создайте один раз (если уже есть — пропустите):

```bash
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" ai_buddy_test'
# Если Docker требует sudo:
sudo docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" ai_buddy_test'
```

## 3. Backend и миграции

```bash
cd backend
python3.14 -m venv .venv
source .venv/bin/activate
# Установить CPU PyTorch первым, чтобы не скачивать GPU-зависимости:
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -r requirements.txt
alembic upgrade head
python -m scripts.migrate_test
```

Цепочка миграций:

- `b09d2d5a1a04`: исходные пользователи и команды.
- `c28e67a901af`: password_hash, is_active, created_at и onboarding_tasks.
- `d39f72b8a012`: диалоги, сообщения и учёт попыток обращения к чату.
- `e4a81c093bd2`: расширение vector, документы и фрагменты с VECTOR(384).

Существующие записи сохраняются; старым пользователям пароль автоматически не назначается.
Последняя миграция требует установленного на сервере pgvector и прав CREATE EXTENSION.
`migrate_test` применяет ту же цепочку только к ai_buddy_test.

## 4. Демонстрационные аккаунты

В том же терминале backend:

```bash
# Только для локального прототипа; можно выбрать другой пароль (минимум 12 символов).
DEMO_PASSWORD='Buddy-demo-2026!' python -m scripts.seed_demo
```

| Роль | Email | Пароль при первом seed с командой выше |
| --- | --- | --- |
| Стажёр | intern@ai-buddy.example | Buddy-demo-2026! |
| Наставник | mentor@ai-buddy.example | Buddy-demo-2026! |
| Руководитель | manager@ai-buddy.example | Buddy-demo-2026! |

Пароль передаётся через окружение, хешируется Argon2, в БД и логи открытый пароль не попадает.
Не используйте демонстрационный пароль в production. Повторный seed не дублирует записи,
не меняет пароль и прогресс существующих аккаунтов. Дата старта стажёра — за шесть дней до
первого seed, начальный прогресс 3/7 (43%). Для собственного пароля безопаснее прочитать его
в окружение через `read -rsp 'Демо-пароль: ' DEMO_PASSWORD; export DEMO_PASSWORD`, затем
`python -m scripts.seed_demo` и `unset DEMO_PASSWORD`.

## 5. Запуск

Для полноценного чата перед запуском настройте DEEPSEEK_API_KEY в `.env`, скачайте E5 и
проиндексируйте инструкции по разделу «CPU-модель и индексация» ниже. Сначала должны быть
применены все миграции и выполнен seed. Без DeepSeek доступен кабинет; чат вернёт понятную
ошибку конфигурации. После изменения `.env` перезапустите backend.

Терминал backend из `backend/` с активным окружением:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Второй терминал из корня:

```bash
cd frontend
npm ci
npm run dev
```

Откройте http://localhost:5173 и войдите. `/api` проксируется в backend, cookie остаётся
в одном origin. API-документация: http://127.0.0.1:8000/docs, health: `/health`.
Для ручных POST/PATCH в API требуются Origin и X-Requested-With из раздела безопасности.

## API

| Метод | Путь | Доступ |
| --- | --- | --- |
| GET | /health | Публичный |
| POST | /auth/login | Email/пароль, Origin + custom header |
| GET | /auth/me | Собственный профиль |
| POST | /auth/logout | Удаление cookie, Origin + custom header |
| GET | /teams | Собственная команда |
| GET | /teams/{id} | Собственная команда или 404 |
| GET | /users/me/onboarding | Задачи текущего стажёра + completed/total/percent |
| PATCH | /users/me/onboarding/{id} | Своя задача, тело `{"status":"done"}` |

Состояния задач: todo, in_progress, done. Все текущие задачи доступны владельцу для
самостоятельного изменения. Подробнее: [правила аутентификации и доступа](docs/auth-onboarding.md).

## Тесты, типизация и покрытие

Интеграционные тесты backend подключаются к отдельной `ai_buddy_test` с теми же реквизитами БД.
Unit-тесты индексации используют изолированную SQLite; сервисы LLM подменяются.
Транзакции откатываются после каждого теста; production engine не используется фикстурами.
Сначала создайте тестовую БД и примените миграции, как описано выше.

```bash
cd backend
source .venv/bin/activate
python -m scripts.migrate_test
pytest -q
ruff check app scripts tests
ruff format --check app scripts tests
```

Pytest автоматически измеряет весь `app/`, требует минимум 80% строк и создаёт
`backend/htmlcov/index.html`, `backend/coverage.json`. Успешный отчёт должен превышать 80%.
Существующие тесты моделей сохранены, тест команд адаптирован к обязательной аутентификации.

```bash
cd frontend
npm run coverage
npm run build
```

Vitest измеряет прикладной TypeScript, исключая тесты и файл монтирования main.tsx;
порог 80% строк. HTML: `frontend/coverage/index.html`, JSON: `coverage/coverage-summary.json`.
`npm run build` сначала выполняет строгую TypeScript-проверку, затем Vite production build.
Frontend-тесты используют имитацию HTTP, backend API-тесты — реальный PostgreSQL.
Это не заменяет проверку браузером и полной цепочки HTTP через Vite proxy.

## Следующие итерации

- Расширение ИИ-оценок и разрешённые корпоративные инструменты: [SDD](docs/specs/README.md).
- Кабинеты наставника/руководителя, подтверждаемые задачи, этапы и шаблоны адаптации.
- Интеграции реальных источников знаний и заявок, корпоративный SSO, восстановление пароля.
- Централизованный отзыв JWT, rate limiting и аудит перед production-развёртыванием.

JWT logout удаляет cookie; уже скопированный токен действует до TTL. Интерфейс показывает
ошибки и загрузку, 401 удаляет персональный кэш. ИИ не имитирует выполнение корпоративных действий.

## Результаты первой итерации (до чата и RAG)

Backend: 37 тестов, 99,19% строк; frontend: 24 теста, 98,86% строк.
Миграции, типизация, сборка и реальный браузерный сценарий прошли.
Подробности и скриншоты: [отчёт проверки](docs/verification.md).

## Итерация 2: ИИ-чат, RAG и темы

В `/assistant` теперь настоящий HTTP-чат: DeepSeek генерирует ответы, PostgreSQL хранит
собственные диалоги пользователя. Доступны новый диалог, продолжение истории, быстрые вопросы,
состояния ожидания/ошибок и источники с переходом в `/knowledge/{id}`. Стадия прототипа:
streaming и корпоративные действия не реализованы. Эмодзи убраны; светлая/тёмная тема
переключается кнопкой в верхней панели и на входе. В localStorage сохраняется только тема,
JWT по-прежнему находится в HttpOnly cookie.

### Настройка DeepSeek

Создайте свой ключ в [консоли DeepSeek](https://platform.deepseek.com/api_keys), пополните
небольшой баланс и добавьте ключ только в корневой `.env`:

```dotenv
DEEPSEEK_API_KEY=<ваш ключ, только на backend>
DEEPSEEK_MODEL=deepseek-flash
LLM_MAX_TOKENS=1000
LLM_TIMEOUT_SECONDS=45
CHAT_DAILY_LIMIT=30
CHAT_HISTORY_MESSAGES=8
CHAT_HISTORY_CHARS=12000
```

Не используйте VITE_* для ключей. Настоящие ключи не должны попадать в Git, browser bundle и логи.
Настройки читает существующий Pydantic Settings, значение ключа — SecretStr. Запрос идёт на
официальный https://api.deepseek.com через AsyncOpenAI: thinking отключён, retry=0, ответ
ограничен токенами и тайм-аутом. Параметры проверены по
[официальной документации DeepSeek](https://api-docs.deepseek.com/api/create-chat-completion/).

Квота — попытки за скользящие 24 часа на пользователя; учитываются и ошибочные внешние
попытки. История/фрагменты ограничены, usage сохраняется в chat_messages. Общий денежный
бюджет контролируйте в кабинете DeepSeek: приложение не гарантирует суммарный предел $5
для всех аккаунтов и дней. Автотесты никогда не используют платный API.

### PostgreSQL и pgvector

Перед применением новой vector-миграции выполните
[безопасный переход с резервной копией](docs/pgvector-setup.md). Образ PostgreSQL 17 заменён
на `pgvector/pgvector:pg17-bookworm`, имя и путь постоянного volume сохранены. Не запускайте
`docker compose down -v`. В текущем локальном окружении pgvector уже доступен и документы
проиндексированы. На новой установке всё равно выполните `alembic upgrade head` для основной БД
и `python -m scripts.migrate_test` для тестовой.

### CPU-модель и индексация

Из `backend/` с активным venv:

```bash
# Сначала CPU PyTorch, чтобы не скачивать ненужные GPU-пакеты:
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -r requirements.txt
python -m scripts.preload_embeddings
# Повторно выполните идемпотентный seed по инструкции выше,
# чтобы добавить новую синтетическую команду Analytics для проверки ACL.
python -m scripts.index_knowledge
python -m scripts.evaluate_rag
```

Embedding-модель — [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small),
локальный CPU, 384 измерения, префиксы query:/passage:, L2-нормализация. Кэш в
`.cache/huggingface` игнорируется Git. Загрузка модели явная через preload/index;
backend по умолчанию использует только локальный кэш и загружает модель один раз на процесс.
Первый запуск скачивает несколько сотен мегабайт, GPU не нужен.

Векторы находятся в PostgreSQL `knowledge_chunks.embedding VECTOR(384)`. Используется точный
cosine-поиск с SQL-фильтром public OR team_id=current_user.team_id до LIMIT; это надёжнее
для маленькой демонстрационной базы, чем преждевременный ANN-индекс. top_k по умолчанию 5.
Порог RAG_MIN_SCORE=0.824426 получен на 10 контрольных вопросах синтетической базы; измерения
сохранены в [отчёте](docs/rag-evaluation.txt). После изменения корпуса выполните калибровку
заново и задайте рекомендованный порог в `.env`. Это небольшая проверочная выборка, а не
гарантия качества для произвольного вопроса. Без порога запросы к базе знаний возвращают 503.

Индексация идемпотентна: SHA-256 учитывает содержимое, имя модели и версию chunking (`chunks-v2`).
Название документа сохраняется во фрагментах; короткое вступление объединяется с правилами,
чтобы поиск не возвращал только заголовок с дисклеймером.
Неизменившиеся документы пропускаются без embeddings. Каждый изменённый файл обрабатывается
отдельной транзакцией, старые фрагменты заменяются только после успешного вычисления новых.
Удалённые с диска документы автоматически из БД не удаляются. Одновременно запускайте один
индексатор, иначе уникальный source отменит конфликтующую транзакцию.

### Добавление документов

Добавьте Markdown в `backend/knowledge/`, например:

```markdown
---
title: Название синтетической инструкции
scope: public
---
# Название

Текст инструкции с абзацами и подзаголовками.
```

Для ограничения командой вместо public укажите `scope: team:Backend · Demo` или точное имя
существующей команды. Неизвестная область/команда отклоняется безопасно. Выполните
`python -m scripts.index_knowledge`, затем калибровку. 12 demo-инструкций включают общие,
Backend и закрытый документ Analytics для проверки ACL. Текущий индекс содержит 18 фрагментов.
Инструкции включают примеры заявок, чек-листы Code Review, работу с замечаниями и типовые
ошибки настройки. Все они синтетические и не являются
внутренними регламентами Авито.

### API и проверка реального чата

| Метод | Путь | Назначение |
| --- | --- | --- |
| POST | /assistant/conversations | Создать собственный пустой диалог |
| GET | /assistant/conversations | Список своих диалогов (последние 100) |
| GET | /assistant/conversations/{id} | История; чужая — 404 |
| POST | /assistant/chat | message + необязательный conversation_id |
| GET | /knowledge | Доступные документы |
| GET | /knowledge/{id} | Текст разрешённого документа; чужой — 404 |

После настройки перезапустите backend/frontend и откройте `/assistant`. Вопрос о своих
задачах передаёт актуальные задачи из SQL без RAG. «Где запросить права на репозиторий?»
выполняет локальный semantic search, передаёт найденные разрешённые фрагменты в DeepSeek и
показывает ссылки на документы. В JSON-ответе `rag_used=true`, `message.sources` содержит
document_id, chunk_id, title, source и cosine score. Посмотреть проиндексированные документы
можно в `/knowledge`. Если релевантных документов нет, backend честно отказывает без платного
вызова; если модель/БД недоступна, показывает ошибку вместо фиктивного ответа.

Отдельный smoke-тест настоящего DeepSeek делает **один платный запрос** только по вашей команде:

```bash
python -m scripts.smoke_deepseek --allow-paid-request
```

Этот отдельный скрипт в ходе разработки не запускался. Реальный ответ DeepSeek через чат
подтверждён по сохранённой статистике токенов; тесты и переиндексация платный API не вызывают.
Ввод вопроса в рабочем чате расходует баланс.

### Тесты второй итерации

```bash
cd backend
pytest -q
# Отдельная бесплатная интеграция с уже скачанной E5:
RUN_LOCAL_MODEL_TEST=1 pytest -q -m local_model --no-cov
# После полной миграции тестовой БД — реальный cosine + ACL:
pytest -q -m pgvector --no-cov
```

Обычные тесты подменяют LLM и embedding-провайдер. Чат/авторизация используют ai_buddy_test;
unit-тесты атомарной индексации используют изолированную SQLite. SQL cosine/ACL проверяется
отдельным PostgreSQL-тестом, который явно пропускается, пока нет vector-таблиц.
Порог общего покрытия app/ остаётся 80%. Команды frontend: `npm run coverage`, `npm run build`.
Новые тесты покрывают чат, источники, историю, ошибки, ожидание и смену темы.

Поведение и критерии приёмки: [SDD ассистента](docs/specs/assistant.md),
[будущие инструменты](docs/specs/future-tools.md). Ограничения: эвристическая маршрутизация,
небольшая калибровочная выборка, отсутствие streaming и инструментов выполнения действий,
централизованного денежного лимита и пагинации длинных историй.

Последняя проверка после исправления разбиения: backend **67 passed / 1 skipped**, **98,66% строк**.
Пропущен opt-in local_model, который ранее отдельно прошёл; pgvector-интеграция проходит.
Последняя frontend-проверка: **32 passed**,
**98,70% строк**. Отдельный тест реальной E5: 1 passed.
[Подробный отчёт, ограничения и список новых файлов](docs/verification-iteration2.md).
