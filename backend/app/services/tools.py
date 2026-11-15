"""Allowlisted tool dispatch; tools can prepare, never confirm, mutations."""

import re

from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.access import AccessArguments, AccessDraftArguments, EmptyArguments, RequestId
from app.services import access
from app.services.onboarding import overview

CONTRACTS = {
    **{
        name: (EmptyArguments, description)
        for name, description in {
            "get_my_adaptation_plan": "Прочитать собственный план и историю согласования из PostgreSQL",
            "get_my_goals": "Прочитать цели и критерии собственного плана",
            "get_my_progress": "Получить подтверждённый прогресс",
            "get_next_steps": "Получить рекомендации следующих шагов по данным приложения",
            "get_my_team_objectives": "Прочитать OKR своей команды",
        }.items()
    },
    "create_access_request": (
        AccessDraftArguments,
        "Подготовить черновик доступа или уточнить недостающие поля. Передавай известные из слов пользователя сервис, проект и права, неизвестные пропусти. Для прав используй read (просмотр) или write (редактирование). Причина необязательна: по умолчанию работа над задачами стажировки; пользователь увидит её перед подтверждением. Не создаёт заявку.",
    ),
    "get_access_request_status": (
        RequestId,
        "Получить текущий статус доступной заявки по номеру из БД.",
    ),
    "list_my_access_requests": (
        EmptyArguments,
        "Получить свои заявки из БД, в том числе когда номер неизвестен.",
    ),
    "get_my_onboarding_tasks": (
        EmptyArguments,
        "Получить актуальные собственные задачи адаптации.",
    ),
}
DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema.model_json_schema(),
        },
    }
    for name, (schema, description) in CONTRACTS.items()
]


def dispatch(db, user, name, arguments):
    if name not in CONTRACTS:
        raise HTTPException(400, "Неизвестный инструмент")
    try:
        args = CONTRACTS[name][0].model_validate_json(arguments)
    except ValidationError as error:
        if name == "create_access_request":
            fields = {item["loc"][0] for item in error.errors() if item["loc"]}
            if "permission" in fields:
                return {
                    "error": "Какие права нужны: просмотр или редактирование? Повышенные права в демо недоступны."
                }
            if "resource" in fields:
                return {"error": "К какому сервису нужен доступ: Jira, Confluence или GitLab?"}
            if "project_key" in fields:
                return {
                    "error": "Уточните код проекта. В демонстрационной команде доступен проект BACKEND."
                }
        return {
            "error": "Не получилось разобрать запрос. Уточните, пожалуйста, что нужно сделать. Для статуса можно написать: «Покажи мои заявки»."
        }
    if name == "create_access_request":
        missing = [
            field
            for field in ("resource", "project_key", "permission")
            if getattr(args, field) is None
        ]
        if missing:
            questions = {
                "resource": "К какому сервису нужен доступ: Jira, Confluence или GitLab?",
                "project_key": "К какому проекту нужен доступ? В демонстрационной команде доступен BACKEND.",
                "permission": "Какие права нужны: просмотр или редактирование?",
            }
            return {"error": "\n".join(questions[field] for field in missing)}
        args = AccessArguments(
            **(
                args.model_dump()
                | {"justification": args.justification or "Работа над задачами стажировки"}
            )
        )
        item = access.prepare(db, user, args)
        return {
            "proposal_id": item.id,
            "parameters": item.parameters,
            "expires_at": item.expires_at.isoformat(),
            "message": "Подготовлен черновик. Заявка НЕ создана. Нажмите «Подтвердить создание» в карточке.",
        }
    if name == "get_access_request_status":
        return access.serialize(access.get_request(db, user, args.request_id))
    if name == "list_my_access_requests":
        return {"requests": access.requests(db, user, own=True)}
    if user.role != "intern":
        return {"error": "Задачи адаптации доступны стажёрам"}
    if name != "get_my_onboarding_tasks":
        from app.services.adaptation import detail

        return {"adaptation": detail(db, user.id)}
    return overview(db, user.id).model_dump(mode="json")


async def run(db, user, messages):
    from app.services import llm

    result = await llm.complete(messages, tools=DEFINITIONS)
    if not result.tool_calls:
        last = messages[-1]["content"]
        # Preserve useful clarification from the model. Never present an unverified
        # status/number or a successful mutation as a tool result.
        status_question = re.search(r"статус|что с .*заяв|мои заяв|моей заяв", last, re.I)
        unverified = re.search(
            r"№\s*\d|заявк[^\n.!?]{0,100}(создан|отправлен|согласован|одобрен|отклонен)|доступ[^\n.!?]{0,50}(выдан|предоставлен)",
            result.content,
            re.I,
        )
        if status_question:
            result.content = "Сейчас не удалось проверить статус заявки. Откройте раздел «Мои заявки» — там актуальные данные. Можно также повторить: «Покажи мои заявки»."
        elif unverified:
            result.content = "Заявка ещё не создана. Я помогу подготовить её: укажите сервис, проект и права — просмотр или редактирование. Затем проверьте карточку и нажмите «Подтвердить создание». Операция не выполнена."
        elif re.search(r"созда|оформ|подготов", last, re.I) and not re.search(
            r"\?|уточн|укаж|выбер", result.content, re.I
        ):
            result.content = "Давайте подготовим заявку. Напишите, к какому сервису и проекту нужен доступ и какие права нужны: просмотр или редактирование. Например: «Jira, BACKEND, редактирование». Причину «Работа над задачами стажировки» добавлю в черновик — вы сможете проверить её перед подтверждением."
        return result
    # One bounded selection pass, at most four calls. No recursive LLM execution.
    if len(result.tool_calls) > 4:
        raise HTTPException(502, "LLM превысила лимит инструментов. Уточните запрос")
    if sum(call["name"] == "create_access_request" for call in result.tool_calls) > 1:
        raise HTTPException(502, "За сообщение можно подготовить только одну заявку")
    outputs = []
    for call in result.tool_calls:
        try:
            value = dispatch(db, user, call["name"], call["arguments"])
        except HTTPException as error:
            value = {"error": error.detail}
        outputs.append(value)
        if "proposal_id" in value:
            result.proposal_ids.append(value["proposal_id"])
    # Render verified backend results directly: model cannot invent request IDs/statuses.
    result.content = "\n\n".join(render(value) for value in outputs)
    return result


def render(value):
    if "adaptation" in value:
        data = value["adaptation"]
        plan = data["plan"]
        lines = (
            [
                f"План: {plan['title']} · версия {plan['version']} · {plan['status']}",
                f"Ожидания наставника: {plan['expectations']}",
            ]
            if plan
            else ["План пока не создан. Обсудите его с наставником."]
        )
        lines += [f"Цель: {g['title']}. Критерии: {g['success_criteria']}" for g in data["goals"]]
        lines += [
            f"OKR команды: {o['title']}. Ключевые результаты: {', '.join(o['key_results'])}"
            for o in data["objectives"]
        ]
        lines += data["next_steps"]
        return "\n".join(lines)
    if "error" in value:
        return value["error"]
    if "proposal_id" in value:
        return "Черновик подготовлен. Проверьте параметры в карточке и нажмите «Подтвердить создание». До подтверждения заявка не создаётся."
    if "requests" in value:
        return "\n\n".join(render(item) for item in value["requests"]) or "У вас пока нет заявок."
    if "status" in value:
        statuses = {
            "pending": "ожидает согласования",
            "approved": "согласована (доступ ещё не выдан)",
            "rejected": "отклонена",
        }
        return (
            f"Заявка №{value['id']}: {value['resource'].upper()} · {value['project_key']} · "
            f"{'редактирование' if value['permission'] == 'write' else 'просмотр'}. "
            f"Статус: {statuses[value['status']]}."
            + (
                " Ожидает маршрутизации: согласующий не назначен."
                if value["routing"] == "awaiting_routing"
                else ""
            )
        )
    return f"Задачи адаптации: выполнено {value['completed']} из {value['total']}.\n" + "\n".join(
        f"• {task['title']}: {task['status']}" for task in value["tasks"]
    )
