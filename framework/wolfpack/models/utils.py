"""Model resolution utils: parser for the string "provider:model[:model_type]".

Agno style (`_parse_model_string`/`get_model`): creates the correct Model from an
identifier and standard environment keys (OPENAI_API_KEY, ANTHROPIC_API_KEY,
GOOGLE_API_KEY, OLLAMA_BASE_URL...).
"""

from __future__ import annotations

import os
from typing import Any, Optional


def get_model(model: str) -> Any:
    """Resolves 'openai:gpt-4o', 'anthropic:claude-3-5-sonnet', 'google:gemini-...',
    'ollama:qwen2.5' and 'groq:qwen-2.5-32b' to a Model object.
    """
    if isinstance(model, str) and ":" in model:
        provider, model_id = model.split(":", 1)
        return _build(provider.lower(), model_id)
    if isinstance(model, str):
        # infer the provider by prefix
        if model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
            return _build("openai", model)
        if model.startswith("claude"):
            return _build("anthropic", model)
        if model.startswith("gemini"):
            return _build("google", model)
        return _build("openai", model)
    return model


def get_model_from_env(preferred: Optional[str] = None) -> Any:
    """Builds a Model from environment variables, preferring an explicit
    `preferred` spec when given.

    Fallback priority:
      - OPENAI_API_KEY         -> openai:gpt-4o-mini
      - ANTHROPIC_API_KEY      -> anthropic:claude-haiku-4-5
      - GOOGLE_API_KEY         -> google:gemini-2.0-flash
      - OLLAMA_BASE_URL        -> ollama:<OLLAMA_MODEL or qwen3-coder>
    """
    if preferred:
        return get_model(preferred)
    if os.environ.get("OPENAI_API_KEY"):
        return get_model("openai:gpt-4o-mini")
    if os.environ.get("ANTHROPIC_API_KEY"):
        return get_model("anthropic:claude-haiku-4-5")
    if os.environ.get("GOOGLE_API_KEY"):
        return get_model("google:gemini-2.0-flash")
    if os.environ.get("OLLAMA_BASE_URL"):
        model_id = os.environ.get("OLLAMA_MODEL") or "qwen2.5"
        return get_model(f"ollama:{model_id}")
    raise ValueError("No LLM provider configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY or OLLAMA_BASE_URL.")


def _build(provider: str, model_id: str) -> Any:
    if provider == "openai":
        from ..models.base import OpenAILike

        return OpenAILike(id=model_id, provider="openai", api_key=os.environ.get("OPENAI_API_KEY"))
    if provider == "groq":
        from ..models.base import OpenAILike

        return OpenAILike(
            id=model_id,
            provider="groq",
            api_key=os.environ.get("GROQ_API_KEY"),
            base_url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        )
    if provider == "ollama":
        from ..models.base import OpenAILike

        return OpenAILike(
            id=model_id,
            provider="ollama",
            api_key="ollama",
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )
    if provider == "anthropic":
        from ..models.base import AnthropicModel

        return AnthropicModel(id=model_id, api_key=os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "google":
        from ..models.base import GoogleModel

        return GoogleModel(id=model_id, api_key=os.environ.get("GOOGLE_API_KEY"))
    if provider == "openailike":
        from ..models.base import OpenAILike

        return OpenAILike(id=model_id, provider="openailike", api_key=os.environ.get("OPENAI_API_KEY"), base_url=os.environ.get("OPENAI_BASE_URL"))
    raise ValueError(f"Provider desconocido: {provider}")