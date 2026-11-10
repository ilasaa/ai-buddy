# Безопасный переход PostgreSQL 17 на образ с pgvector

Текущий compose сохраняет прежний сервис db, container_name, PostgreSQL major 17,
порт и volume postgres_data:/var/lib/postgresql/data. Меняется только образ:
pgvector/pgvector:pg17-bookworm. Файлы расширения должны находиться внутри сервера БД;
установка Python-пакета pgvector сама по себе их не добавляет.

В текущем окружении Docker socket недоступен без полномочий. Контейнер не останавливался,
volume и существующий кластер не удалялись. Смена образа требует короткого простоя:
выполните команды самостоятельно в согласованное время. Если Docker работает без sudo,
уберите sudo. Никогда не используйте down -v.

## 1. Проверить сервер и подготовить резервную копию

Из корня проекта (данные дампа могут быть чувствительными; храним вне Git):

```bash
mkdir -p .cache/backups
sudo docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SHOW server_version;"'
sudo docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > .cache/backups/ai_buddy_before_pgvector.dump
# Проверить, что дамп непустой и читается:
test -s .cache/backups/ai_buddy_before_pgvector.dump
sudo docker compose exec -T db pg_restore -l < .cache/backups/ai_buddy_before_pgvector.dump
```

Сохраните резервную копию тестовой БД, если в ней есть нужные данные:

```bash
sudo docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d ai_buddy_test -Fc' > .cache/backups/ai_buddy_test_before_pgvector.dump
```

Сначала убедитесь, что текущая основная версия — 17 и используется тот же volume. Для другой
основной версии остановитесь и подготовьте отдельный план миграции: эти команды для неё не подходят.

## 2. Загрузить образ и согласованно заменить контейнер

```bash
sudo docker compose pull db
# Команда заменяет контейнер сервиса db с тем же постоянным volume; будет короткий простой.
sudo docker compose up -d --no-deps db
sudo docker compose ps
sudo docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT name, default_version FROM pg_available_extensions WHERE name = '\''vector'\'';"'
```

Не удаляйте контейнер/volume вручную. При неожиданном состоянии остановитесь и исследуйте
журнал сервера; не инициализируйте базу заново. Если БД находится вне Compose, попросите
администратора установить pgvector для её PostgreSQL 17 — замена локального образа не изменит
удалённый сервер.

## 3. Применить миграции

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
python -m scripts.migrate_test
alembic check
```

`d39f72b8a012` создаёт только таблицы диалогов и квоты; она уже применена в текущем окружении.
`e4a81c093bd2` сначала выполняет CREATE EXTENSION IF NOT EXISTS vector, затем создаёт документы
и VECTOR(384)-фрагменты. Нужны права установки extension; при отсутствии прав попросите
администратора выполнить CREATE EXTENSION IF NOT EXISTS vector в обеих БД и повторите миграции.
Если extension недоступен, миграция завершается ошибкой в транзакции, данные не пересоздаются.
