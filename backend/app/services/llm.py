from dataclasses import dataclass, field
from urllib.parse import urlparse

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import settings


@dataclass
class LLMResult:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    proposal_ids: list[str] = field(default_factory=list)


def client():
    key = settings.effective_llm_key
    if not key:
        raise HTTPException(503, "DeepSeek не настроен. Обратитесь к администратору.")
    return AsyncOpenAI(
        api_key=key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )


async def complete(messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
    try:
        async with client() as api:
            result = await api.chat.completions.create(
                model=settings.effective_llm_model,
                messages=messages,
                **({"tools": tools, "tool_choice": "auto"} if tools else {}),
                max_tokens=settings.llm_max_tokens,
                temperature=0.3,
                extra_body={"thinking": {"type": "disabled"}}
                if urlparse(settings.llm_base_url).hostname == "api.deepseek.com"
                else None,
            )
    except APITimeoutError:
        raise HTTPException(504, "DeepSeek не ответил вовремя. Попробуйте позже.") from None
    except RateLimitError:
        raise HTTPException(429, "Лимит DeepSeek превышен. Попробуйте позже.") from None
    except APIConnectionError:
        raise HTTPException(502, "Не удалось связаться с DeepSeek.") from None
    except APIStatusError:
        raise HTTPException(
            503, "LLM недоступна или не поддерживает настроенный формат инструментов."
        ) from None
    if not result.choices or not (
        (result.choices[0].message.content or "").strip() or result.choices[0].message.tool_calls
    ):
        raise HTTPException(502, "LLM вернула пустой ответ.")
    usage = result.usage
    return LLMResult(
        result.choices[0].message.content or "",
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
        [
            {"id": call.id, "name": call.function.name, "arguments": call.function.arguments}
            for call in (result.choices[0].message.tool_calls or [])
        ],
    )
