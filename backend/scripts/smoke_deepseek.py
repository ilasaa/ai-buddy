"""Manual paid API smoke test. Never invoked by pytest or indexing."""

import argparse
import asyncio

from app.services.llm import complete


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-paid-request", action="store_true")
    args = parser.parse_args()
    if not args.allow_paid_request:
        parser.error("Для одного платного запроса нужен --allow-paid-request")
    result = await complete(
        [
            {"role": "system", "content": "Ответь по-русски кратко, без эмодзи."},
            {
                "role": "user",
                "content": "Одним предложением: чем ИИ-наставник может помочь стажёру?",
            },
        ]
    )
    print(result.content)
    print(f"Токены: вход {result.prompt_tokens}, выход {result.completion_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
