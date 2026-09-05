"""Framework observability: OpenTelemetry spans with `gen_ai.*` convention.

The framework is not tied to a platform: `Tracker` is a minimal interface
(start_trace/end_trace/start_span/end_span) and implementations can be no-op,
native OTel, or OTLP to a Collector (langfuse, langsmith, or the Wolfpack Control
Plane).

Default implementation: OTel SDK with a `TracerProvider` whose `SpanExporter`
points to a pluggable exporter (the console by default).

For the MVP a `NoopTracker` (zero overhead) and a basic OTel are added when the SDK
is present. We document in `docs/` how to wire your own exporter.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class Tracker(ABC):
    """Observability contract. Implement your own connector (OTel, langfuse, AMP)."""

    @abstractmethod
    def start_trace(self, name: str, run_id: Optional[str] = None) -> Any:
        """Starts the trace of a full run."""

    @abstractmethod
    def end_trace(self, trace: Any, output: Optional[str] = None, usage: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
        """Closes the root trace."""

    @abstractmethod
    def start_span(
        self, kind: str, name: str, span_type: Optional[str] = None, parent: Optional[Any] = None
    ) -> Any:
        """Starts a span (agent_step, llm_call, tool...)."""

    @abstractmethod
    def end_span(
        self,
        span: Any,
        usage: Optional[Dict[str, Any]] = None,
        status: str = "OK",
        error: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        cost: Optional[Any] = None,
    ) -> None:
        """Closes a child span."""


class NoopTracker(Tracker):
    """Tracker that does nothing (default when no tracer is configured)."""

    def start_trace(self, name, run_id=None):
        return None

    def end_trace(self, trace, output=None, usage=None, error=None):
        return None

    def start_span(self, kind, name, **kwargs):
        return None

    def end_span(self, span, usage=None, status="OK", error=None, input=None, output=None, cost=None):
        return None

    def __bool__(self):
        return False


class OTelTracker(Tracker):
    """OTel tracker: emits real spans with the vercel/otel GenAI attributes.

    The root span is an "agent span (operation=wolfpack/agent)". Each step is an
    `agent_step`, each model call an `llm_call` (inference span with
    `gen_ai.operation.name=ai.generateText`), each tool a `tool` span with
    `gen_ai.tool.name` and `gen_ai.tool.call.result`.
    """

    def __init__(self, tracer: Any, service_name: Optional[str] = None):
        self._tracer = tracer
        self._service_name = service_name or "wolfpack-ai"

    def start_trace(self, name, run_id=None):
        return self._tracer.start_span(
            name,
            attributes={
                "wolfpack.run_id": run_id or "",
                "gen_ai.operation.name": "wolfpack.agent",
            },
        )

    def end_trace(self, trace, output=None, usage=None, error=None):
        if trace is None:
            return
        if error:
            trace.record_exception(Exception(error))
            trace.set_attribute("error", True)
        trace.set_attribute("wolfpack.output", str(output or "")[:2000])
        if usage:
            for k, v in usage.items():
                trace.set_attribute(f"wolfpack.usage.{k}", v)
        trace.end()

    def start_span(self, kind, name, **kwargs):
        if kind == "agent_step":
            return self._tracer.start_span("agent_step", attributes={"gen_ai.operation.name": "agent_step"})
        if kind == "llm_call":
            return self._tracer.start_span(
                "llm_call",
                kind="CLIENT",
                attributes={"gen_ai.operation.name": "invokeText", "gen_ai.request.model": name},
            )
        if kind == "tool":
            return self._tracer.start_span(
                f"tool_{name}",
                kind="CLIENT",
                attributes={"gen_ai.tool.name": name, "gen_ai.tool.type": "function"},
            )
        return self._tracer.start_span(name or kind)

    def end_span(self, span, usage=None, status="OK", error=None, input=None, output=None, cost=None):
        if span is None:
            return
        if error:
            span.record_exception(Exception(error))
            span.set_attribute("error", True)
        if usage:
            span.set_attribute("gen_ai.usage.input_tokens", usage.get("input_tokens", 0))
            span.set_attribute("gen_ai.usage.output_tokens", usage.get("output_tokens", 0))
        if input is not None:
            span.set_attribute("wolfpack.input", str(input)[:2000])
        if output is not None:
            span.set_attribute("wolfpack.output", str(output)[:2000])
        if cost is not None:
            reported_cost = cost.to_dict() if hasattr(cost, "to_dict") else cost
            span.set_attribute("wolfpack.cost.amount", reported_cost["amount"])
            span.set_attribute("wolfpack.cost.currency", reported_cost["currency"])
            span.set_attribute("wolfpack.cost.source", reported_cost["source"])
        span.end()


def create_tracker() -> Tracker:
    """Creates the default tracker according to the environment.

    Configuration priority:
      1. WOLFPACK_AMP_URL set -> WolfpackObserver (sends to the Control Plane AMP).
      2. WOLFPACK_TRACER=otel and SDK installed -> OTelTracker (console/OTLP).
      3. fallback NoopTracker (no overhead).
    """
    amp_url = os.environ.get("WOLFPACK_AMP_URL")
    amp_key = os.environ.get("WOLFPACK_AMP_API_KEY")
    if amp_url:
        try:
            from ..observer.client import WolfpackObserver
            return WolfpackObserver(base_url=amp_url, api_key=amp_key)
        except Exception:
            pass
    if os.environ.get("WOLFPACK_TRACER", "").lower() in ("1", "true", "otel"):
        try:
            from opentelemetry import trace as otrace
            from opentelemetry.sdk.trace import TracerProvider, BatchSpanProcessor
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            provider = TracerProvider()
            exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(exporter))
            otrace.set_tracer_provider(provider)
            tracer = otrace.get_tracer(__name__)
            return OTelTracker(tracer)
        except ImportError:
            return NoopTracker()
    return NoopTracker()
