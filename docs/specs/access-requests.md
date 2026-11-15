# Заявки и состояния

Таблицы: action_proposals, access_requests, access_request_events.
Новая миграция f517aa920001 после e4a81c093bd2 также добавляет document_metadata документам.
Старые миграции не изменены. Миграция не удаляет данные при upgrade.

Состояния черновика: prepared → confirmed или cancelled; истечение определяется expires_at.
Состояния заявки: pending → approved или rejected. Обратные и повторные переходы дают 409.
Отдельный routing=awaiting_routing вычисляется при отсутствии approver_id; это pending,
а не автоматическое одобрение. Интерфейс рекомендует обратиться к руководителю.
Автоматическое переназначение и выдача прав не реализованы.

GET /access-requests — видимые заявки; GET /access-requests/{id} — поля и история событий.
POST /assistant/actions/prepare — проверка и черновик; GET /assistant/actions — собственные
черновики, включая состояние и диалог; POST /assistant/actions/{uuid}/confirm или /cancel.
POST /access-requests/{id}/approve или /reject — комментарий до 1000 символов.
Изменить поля существующей заявки через API нельзя. Номер выдаёт последовательность PostgreSQL.
Пустые списки допустимы. Frontend опрашивает состояние каждые 10 секунд и обновляет запросы
после действий через TanStack Query. Детали доступны по /requests?id=номер.

Контракт адаптера CorporateAccessAdapter.create принимает проверенного пользователя и серверный
черновик. DemoCorporateAccessAdapter пишет заявку и событие в общей транзакции caller.
При ошибке commit не выполняется, состояние откатывается. В production-адаптере необходимо
сохранить эти гарантии и добавить поддержку внешней идемпотентности.
