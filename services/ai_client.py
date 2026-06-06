from functools import lru_cache

from openai import AsyncOpenAI

import config


@lru_cache(maxsize=1)
def default_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
        timeout=config.OPENAI_TIMEOUT_SECONDS,
        max_retries=config.OPENAI_MAX_RETRIES,
    )


@lru_cache(maxsize=1)
def chat_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=config.OPENAI_CHAT_API_KEY,
        base_url=config.OPENAI_CHAT_BASE_URL,
        timeout=config.OPENAI_TIMEOUT_SECONDS,
        max_retries=config.OPENAI_MAX_RETRIES,
    )
