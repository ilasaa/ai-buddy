# Проверка второй итерации, 10 ноября 2026

Ветка feature/ai-assistant-rag создана из чистой develop. Коммит, push, merge не выполнялись.

## Что проверено

- Backend: pytest с реальным ai_buddy_test для чата/авторизации и подменённым LLM.
  Индексация проверяется отдельно в SQLite, SQL ACL/cosine — компиляцией PostgreSQL-запроса.
- Frontend: Vitest / React Testing Library, strict TypeScript, production build Vite.
- Ruff check/format и git diff --check.
- E5: модель реально скачана в игнорируемый .cache/huggingface; размерность 384, нормировка
  и превосходство сходства релевантного документа проверены отдельным local_model-тестом.
- Локальная калибровка на 10 вопросах: 6 положительных и 4 отрицательных. Все ожидаемые
  документы положительных вопросов найдены в top 5. Минимальный positive score 0,8369605,
  максимальный negative score 0,8104863; предложен порог 0,823723. Отчёт: rag-evaluation.txt.
- Секрет DeepSeek не обнаружен в отслеживаемых файлах и frontend production bundle.

## Браузер

Chromium, временные серверы на отдельных портах, backend подключён к ai_buddy_test.
Проверены вход, переключение темы на входе, сохранение после входа, тёмный dashboard,
чат, быстрый вопрос, русское сообщение об ошибке и мобильная ширина 390px без переполнения.
POST /assistant/chat был перехвачен браузерным тестом: реального платного запроса не было.
Ошибок JavaScript (pageerror) нет. Эта проверка не подтверждает реальный ответ DeepSeek.

Скриншоты: [светлый чат](screenshots/assistant-light.png),
[тёмный чат](screenshots/assistant-dark.png),
[тёмный кабинет](screenshots/dashboard-dark.png),
[мобильный чат](screenshots/assistant-mobile.png).

## Инфраструктурные ограничения

Существующий PostgreSQL доступен, но pg_available_extensions не содержит vector.
Docker socket запрещён текущему пользователю, интерактивный sudo не запускался.
Изображение в compose изменено на pgvector/pgvector:pg17-bookworm с тем же volume и major 17;
контейнер не заменялся, кластер и volume не удалялись.

Применена только новая chat-миграция d39f72b8a012 к основной и тестовой БД.
Векторная миграция e4a81c093bd2 сгенерирована и проверена в offline SQL, но к серверу
не применялась. Соответственно реальная индексация в PostgreSQL, оператор cosine и
end-to-end PostgreSQL-RAG-DeepSeek в этом окружении не подтверждены.
Интеграционный pgvector-тест явно пропускается до установки расширения и upgrade head.
Безопасные команды — pgvector-setup.md. Модель и индексатор не используют DeepSeek.

Существующие миграции не изменены. Автоматизированные тесты не вызывали DeepSeek,
ручной платный smoke-test не запускался. Ключ читается backend из .env и не выводился.
В локальный .env добавлен только измеренный RAG_MIN_SCORE; содержимое .env не печаталось.

## Итоговые результаты

| Проверка | Результат |
| --- | --- |
| Backend | 65 passed, 2 skipped; 98,65% строк app/ |
| Frontend | 32 passed; 98,70% строк |
| Реальная локальная E5 | 1 passed, отдельный запуск без DeepSeek |
| TypeScript + Vite build | Успешно |
| Ruff check / format, git diff --check | Успешно |
| Chat-миграция | Применена к основной и ai_buddy_test |
| Vector-миграция | Offline SQL проверен; серверное применение заблокировано отсутствием extension |

Два пропуска обычного pytest: opt-in local_model (отдельно успешно запущен) и pgvector
(не запущен до подготовки сервера). Непокрыты некоторые ветки исключений хранилища,
конкурирующей отправки и отдельных краевых случаев; порог 80% не снижался.

## Созданные файлы

- `backend/alembic/versions/d39f72b8a012_assistant_rag.py`
- `backend/alembic/versions/e4a81c093bd2_knowledge_vectors.py`
- `backend/app/api/assistant.py`
- `backend/app/api/knowledge.py`
- `backend/app/models/conversation.py`
- `backend/app/models/knowledge.py`
- `backend/app/schemas/assistant.py`
- `backend/app/services/assistant.py`
- `backend/app/services/embeddings.py`
- `backend/app/services/knowledge.py`
- `backend/app/services/llm.py`
- `backend/app/services/rag.py`
- `backend/knowledge/demo/access_requests.md`
- `backend/knowledge/demo/analytics_private.md`
- `backend/knowledge/demo/code_review.md`
- `backend/knowledge/demo/communication.md`
- `backend/knowledge/demo/development_setup.md`
- `backend/knowledge/demo/first_day.md`
- `backend/knowledge/demo/git_workflow.md`
- `backend/knowledge/demo/gitlab_access.md`
- `backend/knowledge/demo/mentor_meetings.md`
- `backend/knowledge/demo/onboarding.md`
- `backend/knowledge/demo/tasks.md`
- `backend/knowledge/demo/technical_help.md`
- `backend/knowledge/evaluation.json`
- `backend/scripts/evaluate_rag.py`
- `backend/scripts/index_knowledge.py`
- `backend/scripts/preload_embeddings.py`
- `backend/scripts/smoke_deepseek.py`
- `backend/tests/test_ai_services.py`
- `backend/tests/test_assistant_api.py`
- `backend/tests/test_knowledge.py`
- `backend/tests/test_local_model.py`
- `backend/tests/test_pgvector_integration.py`
- `docs/pgvector-setup.md`
- `docs/rag-evaluation.txt`
- `docs/screenshots/assistant-dark.png`
- `docs/screenshots/assistant-light.png`
- `docs/screenshots/assistant-mobile.png`
- `docs/screenshots/dashboard-dark.png`
- `docs/specs/assistant.md`
- `docs/specs/future-tools.md`
- `docs/verification-iteration2.md`
- `frontend/src/Assistant.test.tsx`
- `frontend/src/assistant-api.ts`
- `frontend/src/components/ThemeToggle.tsx`
- `frontend/src/pages/Assistant.tsx`
- `frontend/src/pages/Knowledge.tsx`

## Дополнение: содержательные источники Code Review

По сохранённому ответу подтверждено обращение к DeepSeek: prompt_tokens=727,
completion_tokens=142. Причина слабого ответа — отдельный вводный chunk с заголовком и
дисклеймером проходил порог, а содержательные секции теряли название документа.
Разбиение chunks-v2 сохраняет название в каждом фрагменте и объединяет короткое вступление
с содержанием. Расширены 9 инструкций: Code Review, GitLab, окружение, первый день, Git,
коммуникация, наставник, запросы доступов и этапы адаптации. Добавлены примеры, чек-листы,
работа с замечаниями и типовые ошибки. Системная инструкция разрешает содержательно объяснять
синтетические правила учебной команды, не выдавая их за настоящие регламенты Авито.

12 документов успешно переиндексированы в доступном теперь PostgreSQL/pgvector: 18 фрагментов,
0 ошибок. Повторная локальная калибровка дала RAG_MIN_SCORE=0.824426. Backend-тесты:
67 passed, 1 skipped (opt-in local_model), покрытие 98,66%; pgvector-интеграция теперь проходит.
Новых платных запросов к DeepSeek в ходе исправления не выполнялось.
