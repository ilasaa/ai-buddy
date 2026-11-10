# AI-buddy — ИИ-наставник для стажёров

Локальный прототип для Авито Hack&Change 2026. Все демонстрационные команды, люди и задачи
синтетические; приложение не является официальным сервисом Авито.

Реализованы вход по email/паролю, выход, персональный кабинет, команда и наставник,
дата старта/день стажировки, список задач, изменение статусов и расчёт прогресса из PostgreSQL.
Роли intern, mentor, manager проверяются сервером. У наставника и руководителя пока минимальный
кабинет своей роли и команды. ИИ-чат, RAG, заявки и база знаний пока не подключены.

## Стек и структура

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
    pages/        # login, dashboard/onboarding, заглушки
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

Нужны Python 3.14, Node.js 22.12+ (проверено с Node 26), npm и PostgreSQL 17 / Docker Compose.
Все команды ниже выполняются из корня, кроме явно указанных переходов.

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

В `.env` задайте собственные POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, вставьте
сгенерированное значение в JWT_SECRET. Не заменяйте существующий `.env`, если он уже настроен:
добавьте новые параметры вручную. `.env` игнорируется Git. Пароли БД и JWT_SECRET не передавайте
во frontend. COOKIE_SECURE=false допустим только для локального HTTP, при HTTPS — true.
ALLOWED_ORIGINS — JSON-массив точных адресов frontend без завершающего `/`.

## 2. PostgreSQL

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

Vitest измеряет прикладной TypeScript, исключая тесты и файл монтирования main.tsx;
порог 80% строк. HTML: `frontend/coverage/index.html`, JSON: `coverage/coverage-summary.json`.
`npm run build` сначала выполняет строгую TypeScript-проверку, затем Vite production build.
Frontend-тесты используют имитацию HTTP, backend API-тесты — реальный PostgreSQL.
Это не заменяет проверку браузером и полной цепочки HTTP через Vite proxy.

## Следующие итерации

- ИИ-чат, RAG и разрешённые корпоративные инструменты: [место для SDD](docs/specs/README.md).
- Кабинеты наставника/руководителя, подтверждаемые задачи, этапы и шаблоны адаптации.
- Реальные заявки и база знаний, корпоративный SSO, восстановление пароля.
- Централизованный отзыв JWT, rate limiting и аудит перед production-развёртыванием.

JWT logout удаляет cookie; уже скопированный токен действует до TTL. Интерфейс показывает
ошибки и загрузку, 401 удаляет персональный кэш. Чат и интеграции не имитируются.

## Результаты текущей проверки

Backend: 37 тестов, 99,19% строк; frontend: 24 теста, 98,86% строк.
Миграции, типизация, сборка и реальный браузерный сценарий прошли.
Подробности и скриншоты: [отчёт проверки](docs/verification.md).
