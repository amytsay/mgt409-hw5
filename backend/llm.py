"""The one model every agent uses: gpt-6-luna, called through Portkey with PORTKEY_API_KEY."""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

import settings

# Same settings for every agent: a cap on each reply's length (gpt-6-luna is a reasoning model, so no temperature).
MODEL_SETTINGS = {"max_tokens": 2000}


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey (OpenAI-compatible gateway). The key is read from the environment, never logged."""
    client = AsyncOpenAI(
        api_key="unused-portkey-auth-in-headers",
        base_url=settings.PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": settings.portkey_api_key(), "x-portkey-provider": "openai"},
        max_retries=2,
        timeout=90,
    )
    return OpenAIResponsesModel(settings.MODEL_NAME, provider=OpenAIProvider(openai_client=client))
