from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import settings


@dataclass
class LLMResult:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


def client():
    key = settings.llm_api_key.get_secret_value() or settings.deepseek_api_key.get_secret_value()
    if not key:
        raise HTTPException(503, "LLM не настроена. Обратитесь к администратору.")
    return AsyncOpenAI(
        api_key=key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )


async def complete(messages: list[dict]) -> LLMResult:
    try:
        async with client() as api:
            result = await api.chat.completions.create(
                model=settings.llm_model or settings.deepseek_model,
                messages=messages,
                max_tokens=settings.llm_max_tokens,
                temperature=0.3,
                extra_body=(
                    {"thinking": {"type": "disabled"}}
                    if urlparse(settings.llm_base_url).hostname == "api.deepseek.com"
                    else None
                ),
            )
    except APITimeoutError:
        raise HTTPException(504, "LLM не ответила вовремя. Попробуйте позже.") from None
    except RateLimitError:
        raise HTTPException(429, "Лимит LLM превышен. Попробуйте позже.") from None
    except APIConnectionError:
        raise HTTPException(502, "Не удалось связаться с LLM.") from None
    except APIStatusError:
        raise HTTPException(502, "Сервис LLM временно недоступен.") from None
    if not result.choices or not (result.choices[0].message.content or "").strip():
        raise HTTPException(502, "LLM вернула пустой ответ.")
    usage = result.usage
    return LLMResult(
        result.choices[0].message.content,
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
    )
