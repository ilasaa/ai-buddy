> Архив предыдущих итераций. Инструкции и результаты могут быть устаревшими. Актуальное состояние — в корневом README.

# AI-buddy — ИИ-наставник для стажёров

Прототип для Авито Hack&Change 2026: помогает разобраться в инструкциях и пройти сценарий
оформления доступа. Все команды, сотрудники и регламенты синтетические, не данные Авито.

Реализованы авторизация, роли, задачи адаптации и прогресс, команда/наставник, история чата,
RAG с проверкой доступа, Tool Calling, серверные черновики, подтверждение/отмена, заявки Jira,
Confluence и GitLab, согласование, история событий, текущий статус и кабинет наставника/руководителя.
Согласование заявки **не означает выдачу доступа** в реальной корпоративной системе.

## Запуск на Ubuntu

Python 3.14, FastAPI, SQLAlchemy 2.1, PostgreSQL 17, Alembic, Pydantic, pwdlib/Argon2, PyJWT,
Pytest/pytest-cov. Frontend: React 19, TypeScript, Vite, React Router, TanStack Query,
Lucide, обычный CSS; Vitest и React Testing Library.

```text
backend/
  app/
    api/          # HTTP: auth, teams, onboarding
    services/     # аутентификация, область доступа, прогресс и смена статуса
    models/       # User, Team, OnboardingTask
    schemas/      # Pydantic запросы и ответы
    core/         # окружение
    db/           # SQLAlchemy сессии
  alembic/versions/
  scripts/        # seed_demo, migrate_test
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
docs/             # правила доступа и место для будущих SDD
compose.yaml
.env.example
```

## 1. Настройка
Нужны Docker Engine и Compose plugin. Из корня проекта при первой установке:

```bash
# Только если .env ещё нет:
cp -n .env.example .env
# Отредактируйте .env перед запуском:
nano .env
sudo docker compose up --build -d
sudo docker compose logs -f init backend
```

В `.env` задайте POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, JWT_SECRET (от 32 символов),
DEMO_PASSWORD (от 12 символов) и ключ LLM. Не публикуйте этот файл. Существующий `.env` не заменяйте.
Откройте http://localhost:5173. Init ждёт PostgreSQL, применяет Alembic, идемпотентно создаёт
демопользователей, скачивает CPU embedding-модель и индексирует инструкции. Первый запуск требует
интернета, достаточного места для PyTorch и модели. CUDA/GPU не нужны.

PostgreSQL 17 с pgvector использует прежний postgres_data; embedding_cache хранит модель.
Повторный seed не меняет пароли существующих аккаунтов и не дублирует задачи.
Не используйте `docker compose down -v` и не удаляйте volumes.

```bash
sudo docker compose ps
sudo docker compose restart backend frontend  # сохранение заявок и истории
sudo docker compose down                     # остановка с сохранением volumes
```

При обновлении кода повторите `sudo docker compose up --build -d`: новая миграция создаёт таблицы
заявок, существующие данные сохраняются. Docker-запуск этой итерации в среде разработки
не проверен: доступ к сокету запрещён, sudo требует интерактивную аутентификацию.

## LLM и расходы

```dotenv
LLM_API_KEY=ваш-ключ
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
```

Поддерживается OpenAI-совместимый Chat Completions с function tools. Сохраняются старые
DEEPSEEK_API_KEY/DEEPSEEK_MODEL: общий ключ имеет приоритет, модель берётся из LLM_MODEL,
иначе из DEEPSEEK_MODEL. Ассистент проверяет обе схемы конфигурации. Ключ только в backend.
Другой провайдер должен принимать max_tokens, temperature, tools и tool_choice; при несовместимости
возвращается 503, текст не превращается в исполняемую команду. Контракт DeepSeek:
https://api-docs.deepseek.com/guides/tool_calls/.

Один LLM-запрос на сообщение, максимум 4 инструмента и один черновик, без циклов.
Лимиты по умолчанию: 30 сообщений/сутки/пользователь, 1000 выходных токенов, тайм-аут 45 секунд,
история 8 сообщений / 12000 символов. Неудачные запросы учитываются в лимите; без ключа — нет.
Общий денежный лимит на аккаунт провайдера не реализован. Автотесты используют mock LLM.

После изменения окружения:

```bash
sudo docker compose up -d --no-deps --force-recreate backend
```

## Архитектура

React/TypeScript → Nginx `/api` → FastAPI → сервисы прав и корпоративных действий → PostgreSQL.
LLM выбирает разрешённую функцию и аргументы; backend определяет владельца, команду и согласующего.
`CorporateAccessAdapter` заменяем; текущий `DemoCorporateAccessAdapter` сохраняет реальные записи
в общей транзакции SQLAlchemy. Модель не получает SQL или произвольный HTTP.

Инструменты: create_access_request (только подготовка), get_access_request_status,
list_my_access_requests, get_my_onboarding_tasks (существующая модель задач).
Сервис, проект и права уточняются обычными словами. Причина по умолчанию — «Работа над
задачами стажировки»; пользователь видит её перед подтверждением. Посторонний конфликт
Code Review не блокирует заявки. Параметры, номер и статус отображаются из backend. Чат и `/requests` позволяют увидеть результат.
Карточки черновиков сохраняются на сервере и восстанавливаются при открытии диалога.

Черновик действует 10 минут, привязан к владельцу и команде; confirm принимает UUID,
использует серверные параметры и повторно проверяет права. Advisory lock и блокировка строки
защищают конкурирующие подтверждения, unique proposal_id — повторное исполнение.
Повтор confirm возвращает ту же заявку. Другая pending/approved заявка с теми же параметрами
доступа даёт 409. После потери связи повторяют подтверждение того же черновика.

Новые таблицы: action_proposals, access_requests, access_request_events.
Миграция `f517aa920001` после `e4a81c093bd2`; также добавляет метаданные документов.
Старые миграции не изменены.

## Права и демоаккаунты

| Аккаунт | Доступ |
| --- | --- |
| intern@ai-buddy.example | Собственные заявки, задачи, диалоги и черновики |
| mentor@ai-buddy.example | Закреплённые стажёры своей команды; согласование Jira/Confluence |
| manager@ai-buddy.example | Своя команда при реальном назначении руководителем; согласование GitLab |

Начальный пароль — DEMO_PASSWORD; если не задан, Docker-init использует `Buddy-demo-2026!`.
Перед публичным доступом замените стандартные пароли. Новое значение DEMO_PASSWORD
не меняет существующие пароли: обновите их отдельно через доверенную серверную процедуру
или используйте изначально уникальный пароль на новой демоустановке.

В демополитике разрешены только Backend · Demo, проект BACKEND, read/write. Jira/Confluence
назначаются закреплённому активному наставнику, GitLab — фактическому руководителю.
Без согласующего заявка pending с пометкой «ожидает маршрутизации». Автосогласования нет.
Смена связей блокирует старого согласующего; автоматическое переназначение не реализовано.

JWT хранится в HttpOnly cookie. Все изменения требуют авторизации, разрешённого Origin
и X-Requested-With. Чужие объекты скрыты 404. Роль не даёт доступа к чужой команде.
Документы и история считаются недоверенными: prompt injection не может вызвать confirm.

## RAG

Локальная `intfloat/multilingual-e5-small`, 384 измерения, CPU, query/passsage-префиксы,
pgvector cosine-поиск. ACL применяется до LIMIT. Нужен настроенный RAG_MIN_SCORE;
его надо перекалибровать после обновления корпуса. Прежнее значение не доказывает качество
новых инструкций Jira/Confluence. Подробности: [pgvector](docs/pgvector-setup.md).

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
sudo docker compose run --rm init python -m scripts.evaluate_rag
# Перенесите рекомендованный порог в .env и пересоздайте backend.
```

Markdown в backend/knowledge содержит title, scope, необязательные reviewed_on, conflict_group, rule.
Дата загрузки в БД не считается датой актуализации. Нет подтверждённой даты — UI сообщает об этом.
Известное расхождение Code Review (один/два согласующих) расширяет выдачу доступными вариантами;
backend сообщает о конфликте со ссылками и предлагает уточнить у наставника. Универсального
детектора всех противоречий нет. Новые документы индексируются init, неизменившиеся пропускаются.
Если embedding недоступен, обычный RAG возвращает ошибку; инструменты доступа остаются доступны
с явной серверной политикой и без вымышленных инструкций.

## Проверки

Backend: локальное окружение backend/.venv или backend-образ; только отдельная БД ai_buddy_test.
Создайте её один раз, используя настроенного POSTGRES_USER (существующую не пересоздавайте):

```bash
sudo docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" ai_buddy_test'
sudo docker compose run --rm backend python -m scripts.migrate_test
sudo docker compose run --rm backend pytest -q
sudo docker compose run --rm backend ruff check app scripts tests
sudo docker compose run --rm backend ruff format --check app scripts tests
```

Основной POSTGRES_DB не должен называться ai_buddy_test. Фикстуры работают в транзакциях
отдельной тестовой БД с откатом; рабочую БД тесты не очищают. Тесты переходов заявок используют
PostgreSQL и mock LLM; проверяют подтверждение, роли, события, статусы и injection.

```bash
cd backend
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m scripts.migrate_test
```

Новая миграция `c28e67a901af` следует за неизменённой `b09d2d5a1a04`.
Добавляет users.password_hash (nullable), is_active, created_at и onboarding_tasks с индексом
по user_id, FK и CHECK. Существующие записи сохраняются; старым пользователям пароль
автоматически не назначается. `migrate_test` использует только ai_buddy_test.

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

Терминал backend из `backend/` с активным окружением:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Второй терминал из корня:
Frontend (Node.js и зависимости для разработки; приложение по-прежнему запускается через Compose):

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

Тесты backend всегда подключаются к отдельной `ai_buddy_test` с теми же реквизитами БД.
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

Пороги покрытия 80% сохранены. Реальные результаты текущей итерации и недоступные проверки:
[отчёт проверки](docs/verification-iteration3.md). Исторические отчёты предыдущих итераций
не подтверждают текущую версию.

## Демонстрация и спецификации

- Расширение ИИ-оценок и разрешённые корпоративные инструменты: [SDD](docs/specs/README.md).
- Кабинеты наставника/руководителя, подтверждаемые задачи, этапы и шаблоны адаптации.
- Реальные заявки и база знаний, корпоративный SSO, восстановление пароля.
- Централизованный отзыв JWT, rate limiting и аудит перед production-развёртыванием.
[Пошаговое демо](docs/demo-scenario.md), [Tool Calling и подтверждения](docs/specs/corporate-actions.md),
[заявки](docs/specs/access-requests.md), [права](docs/specs/permissions.md),
[наставник и аналитика](docs/specs/mentor-workflow.md), [ассистент](docs/specs/assistant.md),
[методика оценки эффекта](docs/metrics.md), [Cloudflare Quick Tunnel](docs/cloudflare.md).

Минимальная аналитика: реальное число видимых заявок и их состояний, завершённые задачи
и процент адаптации. Нет вымышленных процентов экономии времени.

## Ограничения и следующие шаги

Не реализованы выдача реальных прав, реальная Jira/Confluence, автоматическое переназначение,
сохранённая передача вопросов наставнику (MentorQuestion), денежный лимит провайдера,
streaming и универсальное обнаружение противоречий. Эвристическая маршрутизация и выбор
инструмента моделью могут потребовать повторного уточнения. Списки демо не рассчитаны на большой
объём данных; полноценная пагинация — следующий этап. При перезагрузке чат требует выбора диалога.

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
`docker compose down -v`. В текущем окружении extension пока не установлен, поэтому
`e4a81c093bd2` не применялась. Миграция чата `d39f72b8a012` уже применена.

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

Индексация идемпотентна: SHA-256 учитывает содержимое, имя модели и версию chunking.
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
Backend и закрытый документ Analytics для проверки ACL. Все они синтетические и не являются
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

В ходе разработки он не запускался. Ввод вопроса в рабочем чате также расходует баланс.

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

Итог второй итерации: backend 65 passed / 2 skipped, 98,65% строк; frontend 32 passed,
98,70% строк. Отдельный тест реальной E5: 1 passed.
[Подробный отчёт, ограничения и список новых файлов](docs/verification-iteration2.md).
Перед хакатоном: проверить полный Compose на доступном Docker, перекалибровать
RAG, выполнить ручное демо с ключом организаторов, проверить мобильный браузер и HTTPS,
затем добавить подтверждаемую эскалацию наставнику и пилотное измерение эффекта.
