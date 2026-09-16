"""Policy-driven model routing with explicit fallback and cost attribution."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Literal, Optional, Union

from .base import AnthropicModel, BaseModel, GoogleModel, ModelResponse, ModelStreamChunk, OpenAILike

RoutePurpose = Literal["reasoning", "task"]


@dataclass
class ModelSpec:
    """Declarative provider configuration that resolves to a concrete model on demand."""

    provider: str
    model: str
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    base_url_env: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    def build(self) -> BaseModel:
        api_key = self.api_key or (os.environ.get(self.api_key_env) if self.api_key_env else None)
        base_url = self.base_url or (os.environ.get(self.base_url_env) if self.base_url_env else None)
        provider = self.provider.lower()
        if provider == "anthropic":
            return AnthropicModel(
                id=self.model,
                api_key=api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens or 1024,
            )
        if provider in {"google", "gemini"}:
            return GoogleModel(id=self.model, api_key=api_key, temperature=self.temperature)
        return OpenAILike(
            id=self.model,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )


@dataclass
class ModelTarget:
    """A model endpoint and optional USD-equivalent prices per million tokens."""

    model: Union[BaseModel, ModelSpec]
    input_price_per_million: Optional[float] = None
    output_price_per_million: Optional[float] = None

    def __post_init__(self) -> None:
        if isinstance(self.model, ModelSpec):
            self.model = self.model.build()
        if self.input_price_per_million is not None and self.input_price_per_million < 0:
            raise ValueError("input_price_per_million must be non-negative")
        if self.output_price_per_million is not None and self.output_price_per_million < 0:
            raise ValueError("output_price_per_million must be non-negative")

    @property
    def provider(self) -> str:
        return self.model.provider

    @property
    def model_id(self) -> str:
        return self.model.model_id

    def estimated_cost(self, usage: Dict[str, Any]) -> Optional[float]:
        if self.input_price_per_million is None or self.output_price_per_million is None:
            return None
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        return round(
            (input_tokens * self.input_price_per_million + output_tokens * self.output_price_per_million) / 1_000_000,
            10,
        )


@dataclass
class ModelRoute:
    """An ordered primary and fallback chain for one invocation purpose."""

    primary: ModelTarget
    fallbacks: List[ModelTarget] = field(default_factory=list)

    def targets(self) -> Iterable[ModelTarget]:
        return (self.primary, *self.fallbacks)


@dataclass
class ModelPolicy:
    """Routes agent reasoning and simple tasks to compatible model chains."""

    reasoning: ModelRoute
    task: Optional[ModelRoute] = None
    baseline: RoutePurpose = "reasoning"
    name: str = "default"
    version: str = "1"

    def route_for(self, purpose: RoutePurpose) -> ModelRoute:
        if purpose == "task" and self.task is not None:
            return self.task
        return self.reasoning


def _error_type(error: Exception) -> str:
    error_name = type(error).__name__
    if isinstance(error, TimeoutError) or error_name in {"APITimeoutError", "ConnectTimeout", "ReadTimeout"}:
        return "timeout"
    if isinstance(error, (ConnectionError, OSError)) or error_name in {"APIConnectionError", "ConnectError", "NetworkError"}:
        return "transient"
    status_code = getattr(error, "status_code", None)
    if status_code == 429:
        return "rate_limit"
    if isinstance(status_code, int) and status_code >= 500:
        return "transient"
    return "non_retryable"


def _is_retryable(error: Exception) -> bool:
    return _error_type(error) in {"timeout", "transient", "rate_limit"}


class ModelRouter(BaseModel):
    """A BaseModel that selects a configured route and retries compatible fallbacks."""

    provider = "wolfpack"
    model_id = "model-router"

    def __init__(self, policy: ModelPolicy):
        self.policy = policy
        self.last_routing: Optional[Dict[str, Any]] = None

    def invoke(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        purpose: RoutePurpose = "reasoning",
    ) -> ModelResponse:
        route = self.policy.route_for(purpose)
        attempts: List[Dict[str, Any]] = []
        last_error: Optional[Exception] = None

        for index, target in enumerate(route.targets()):
            started = time.perf_counter()
            try:
                response = target.model.invoke(messages, tools=tools)
            except Exception as error:
                error_type = _error_type(error)
                attempts.append(
                    {
                        "index": index,
                        "provider": target.provider,
                        "model": target.model_id,
                        "outcome": "error",
                        "error_type": error_type,
                        "error": str(error),
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    }
                )
                last_error = error
                if not _is_retryable(error):
                    raise
                continue

            reported_cost = response.cost.to_dict() if response.cost else None
            estimated_cost = target.estimated_cost(response.usage)
            attempts.append(
                {
                    "index": index,
                    "provider": target.provider,
                    "model": target.model_id,
                    "outcome": "success",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "usage": dict(response.usage),
                    "cost": reported_cost,
                    "estimated_cost": estimated_cost,
                }
            )
            routing = self._routing_metadata(purpose, target, index, attempts, response)
            response.routing = routing
            self.last_routing = routing
            return response

        assert last_error is not None
        raise last_error

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        purpose: RoutePurpose = "reasoning",
    ) -> Iterable[ModelStreamChunk]:
        # Streaming fallback is intentionally invocation-level: a partial stream cannot
        # safely be resumed by another provider without duplicating output.
        route = self.policy.route_for(purpose)
        attempts: List[Dict[str, Any]] = []
        last_error: Optional[Exception] = None
        for index, target in enumerate(route.targets()):
            started = time.perf_counter()
            emitted = False
            try:
                for chunk in target.model.stream(messages, tools=tools):
                    emitted = True
                    if chunk.response is not None:
                        response = chunk.response
                        attempts.append({
                            "index": index,
                            "provider": target.provider,
                            "model": target.model_id,
                            "outcome": "success",
                            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                            "usage": dict(response.usage),
                            "cost": response.cost.to_dict() if response.cost else None,
                            "estimated_cost": target.estimated_cost(response.usage),
                        })
                        response.routing = self._routing_metadata(purpose, target, index, attempts, response)
                        self.last_routing = response.routing
                    yield chunk
                return
            except Exception as error:
                if emitted or not _is_retryable(error):
                    raise
                attempts.append({
                    "index": index,
                    "provider": target.provider,
                    "model": target.model_id,
                    "outcome": "error",
                    "error_type": _error_type(error),
                    "error": str(error),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                })
                last_error = error
        assert last_error is not None
        raise last_error

    def _routing_metadata(
        self,
        purpose: RoutePurpose,
        selected: ModelTarget,
        fallback_index: int,
        attempts: List[Dict[str, Any]],
        response: ModelResponse,
    ) -> Dict[str, Any]:
        actual_amount: Optional[float] = None
        actual_currency: Optional[str] = None
        actual_source: Optional[str] = None
        if response.cost is not None:
            actual_amount = response.cost.amount
            actual_currency = response.cost.currency
            actual_source = response.cost.source
        else:
            actual_amount = selected.estimated_cost(response.usage)
            actual_currency = "USD" if actual_amount is not None else None
            actual_source = "route_estimated" if actual_amount is not None else None

        baseline = self.policy.route_for(self.policy.baseline).primary
        baseline_amount = baseline.estimated_cost(response.usage)
        savings = None if actual_amount is None or actual_currency != "USD" or baseline_amount is None else round(baseline_amount - actual_amount, 10)
        return {
            "policy": {"name": self.policy.name, "version": self.policy.version},
            "purpose": purpose,
            "selected": {"provider": selected.provider, "model": selected.model_id},
            "fallback_index": fallback_index,
            "attempts": attempts,
            "actual_cost": {"amount": actual_amount, "currency": actual_currency, "source": actual_source} if actual_amount is not None else None,
            "baseline_cost": {
                "amount": baseline_amount,
                "currency": "USD",
                "method": "equivalent_tokens",
                "provider": baseline.provider,
                "model": baseline.model_id,
            } if baseline_amount is not None else None,
            "estimated_savings": {"amount": savings, "currency": "USD", "method": "equivalent_tokens"} if savings is not None else None,
        }
