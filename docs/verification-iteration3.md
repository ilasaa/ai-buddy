# Проверка итерации 3

Дата: 11 ноября 2026. Ветка feature/corporate-actions, база main (0d75bf7).
До начала дерево чистое; main опережала develop на 3 коммита, develop не содержала
дополнительных коммитов. Создание ветки потребовало разрешения записи в .git.
Коммиты, push, merge, reset, clean и удаление volumes не выполнялись.
Документ «Вопросы с вебинара / Авито» в доступных каталогах проекта не найден;
использованы требования из задания.

## Реальные результаты

| Проверка | Результат |
| --- | --- |
| Новая миграция в ai_buddy_test | Применена: e4a81c093bd2 → f517aa920001 |
| pytest -q | 103 passed, 1 skipped, 10.84 s |
| Покрытие backend app | 97,55% строк (1075/1102), порог 80% сохранён |
| ruff check app scripts tests | All checks passed |
| ruff format --check app scripts tests | 52 files already formatted |
| Новая миграция: ruff check / format | Прошли |
| npm run coverage | 47 passed, 5 файлов тестов |
| Покрытие frontend | 99,53% строк, 99,57% statements, 96,95% branches, 100% functions |
| npm run build | tsc + Vite успешно, 1654 modules |
| docker compose config --quiet | Успешно |
| alembic upgrade head --sql | SQL всей цепочки успешно сгенерирован |
| git diff --check | Успешно |

Один пропуск — opt-in test_real_local_e5: RUN_LOCAL_MODEL_TEST не включён.
Настоящие платные запросы LLM не выполнялись. Frontend использует mock HTTP; backend
основного сценария — настоящую отдельную PostgreSQL ai_buddy_test и mock LLM/embeddings.

До запуска PostgreSQL пользователем были неуспешные прогоны из-за недоступности БД.
После запуска обнаружено, что тестовая база уже содержит демокоманду: новые фикстуры
переиспользуют её с транзакционным откатом, не удаляют существующие данные.
Исправлена тестовая подмена пользователя, создававшая отделённый ORM-объект.
Таблица выше отражает последний успешный прогон, а не предыдущие ошибки.

## Проверенные переходы и безопасность

- HTTP подготовка не создаёт заявку; confirm создаёт реальную запись PostgreSQL.
- Параметры JSON в confirm не меняют сохранённый черновик; повтор возвращает тот же номер.
- Отмена, истечение срока, изменение роли/команды, запрет другого проекта/admin.
- Чужие заявки/черновики: intern, чужой mentor, manager другой команды.
- Назначение Jira/Confluence наставнику, GitLab руководителю; отсутствие маршрута.
- Запрет самосогласования, повторного решения и изменения завершённого состояния.
- История created → approved и чтение нового статуса через mock Tool Calling.
- Prompt injection не создаёт заявку без кнопки подтверждения.
- Два независимых PostgreSQL-соединения одновременно подтверждают один UUID:
  оба получают один номер. Другой одинаковый черновик получает 409; в БД одна заявка.
- Известный конфликт Code Review: два разрешённых источника из PostgreSQL,
  детерминированное сообщение о расхождении, LLM не вызывается.
- Ошибка корпоративного адаптера: 503 без внутреннего текста, заявка не создана.
- Авторизация, Origin, X-Requested-With, строгие JSON-аргументы и предел инструментов.
- UI: карточка, подтверждение/отмена, истечение, retry того же UUID, история,
  согласование/отказ со вторым подтверждением, кабинет наставника, ошибки/обновление.

Обычные тесты БД используют ai_buddy_test и откат транзакций. Тест конкуренции создаёт
собственные временные записи с отдельными соединениями, коммитит их для видимости потокам
и удаляет только эти записи в finally. Рабочая БД не мигрировалась и не очищалась.

## Не проверено / не реализовано

Полная Docker-сборка, init-контейнер, контейнерные healthchecks, новая индексация корпуса
в рабочую БД и сохранение данных при перезапуске контейнеров в этой итерации не проверены:
агент не имеет доступа к Docker socket, sudo требует интерактивную аутентификацию.
Пользователь запустил только сервис db. Синтаксис Compose проверен, исходные Dockerfile,
Nginx и конфигурация постоянных volumes сохранены.

Платный DeepSeek со свежим tools-контрактом, реальная E5, визуальная проверка мобильного
браузера/тем и Cloudflare HTTPS требуют ручного smoke. Темы покрываются существующими
UI-тестами, новые компоненты используют существующие стили и переменные темы.
После обновления корпуса необходима калибровка RAG_MIN_SCORE. Статистическую эффективность
на реальных стажёрах не измеряли.

Не реализованы MentorQuestion/сохранённая эскалация, выдача прав в реальных сервисах,
автоматическое переназначение согласующих и универсальное обнаружение противоречий.
Согласование означает только одобрение заявки. Эвристическая маршрутизация инструментов
и выбор функции моделью остаются ограничениями.

## Повторить локально

Из корня проекта:

```bash
sudo docker compose up --build -d
sudo docker compose logs -f init backend
sudo docker compose ps
# Только если ai_buddy_test ещё не существует:
sudo docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" ai_buddy_test'
sudo docker compose run --rm backend python -m scripts.migrate_test
sudo docker compose run --rm backend pytest -q
sudo docker compose run --rm backend ruff check app scripts tests
sudo docker compose run --rm backend ruff format --check app scripts tests
```

Для frontend из frontend/: npm run coverage и npm run build.
Для ручного сквозного показа: [демосценарий](demo-scenario.md).

## Git: изменённые и новые файлы

Все изменения оставлены незакоммиченными. Предлагаемое сообщение будущего коммита:
`feat: add confirmed corporate access requests and mentor approvals`.

- `README.md`
- `backend/alembic/versions/f517aa920001_corporate_actions.py`
- `backend/app/api/access.py`
- `backend/app/api/knowledge.py`
- `backend/app/main.py`
- `backend/app/models/__init__.py`
- `backend/app/models/access.py`
- `backend/app/models/knowledge.py`
- `backend/app/schemas/access.py`
- `backend/app/schemas/assistant.py`
- `backend/app/services/access.py`
- `backend/app/services/assistant.py`
- `backend/app/services/knowledge.py`
- `backend/app/services/llm.py`
- `backend/app/services/rag.py`
- `backend/app/services/tools.py`
- `backend/knowledge/demo/code_review.md`
- `backend/knowledge/demo/code_review_legacy.md`
- `backend/knowledge/demo/jira_confluence_access.md`
- `backend/scripts/seed_demo.py`
- `backend/tests/test_access.py`
- `backend/tests/test_ai_services.py`
- `backend/tests/test_seed.py`
- `docs/cloudflare.md`
- `docs/demo-scenario.md`
- `docs/metrics.md`
- `docs/specs/README.md`
- `docs/specs/access-requests.md`
- `docs/specs/assistant.md`
- `docs/specs/corporate-actions.md`
- `docs/specs/future-tools.md`
- `docs/specs/mentor-workflow.md`
- `docs/specs/permissions.md`
- `docs/verification-iteration3.md`
- `frontend/src/Access.test.tsx`
- `frontend/src/App.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/Assistant.test.tsx`
- `frontend/src/access-api.ts`
- `frontend/src/assistant-api.ts`
- `frontend/src/components/ActionProposals.tsx`
- `frontend/src/components/MentorOverview.tsx`
- `frontend/src/pages/Assistant.tsx`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/Requests.tsx`
- `frontend/src/styles.css`


## Исправление ложного конфликта и непонятных уточнений

Причина: безусловный перехват ответа при любом конфликте найденных RAG-фрагментов,
а также замена полезного уточнения модели сообщением «LLM не вызвала инструмент».
Исправлено разделение поиска инструкций и действий; из инструкции доступа удаляются
посторонние документы, из конфликта — повторные фрагменты и нерелевантные источники.
Текст уточнения сохраняется; неполный tool call вызывает конкретные вопросы, а не список
технических требований. Причина по умолчанию видна в серверном черновике.

Проверены восстановление в том же диалоге после ошибочного ответа Code Review, оформление
без отдельно указанной причины с реальным подтверждением в PostgreSQL, продолжение
короткими ответами, смена темы, отсечение неверного статуса модели и подсказка Jira в UI.
Настоящие платные запросы LLM и пересборка Docker в этом исправлении не выполнялись.

- `backend/tests/test_assistant_routing.py`
