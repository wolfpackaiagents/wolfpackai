"""Model abstraction: the single interface between agent and provider.

The Model is the only place where the tool-calling loop lives: it receives messages
and tools, responds, and if tool calls come back it returns the assistant message
with them so the Agent can execute them and retry. Each invoke emits an OTel
`gen_ai.*` span.
"""

from __future__ import annotations

import abc
import json
import typing
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from ..models.message import Message, ToolCall


@dataclass
class ReportedCost:
    """A charge explicitly included in a provider or gateway response."""

    amount: float
    currency: str
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {"amount": self.amount, "currency": self.currency, "source": self.source}


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _reported_cost(raw: Any, source: str) -> Optional[ReportedCost]:
    """Normalizes only charge values the response explicitly identifies and currencies."""

    for container in (raw, _field(raw, "usage")):
        if container is None:
            continue
        cost = _field(container, "cost")
        if cost is None:
            cost = _field(container, "total_cost")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            amount = cost
            currency = _field(container, "cost_currency") or _field(container, "currency")
        elif cost is not None:
            amount = _field(cost, "amount")
            if amount is None:
                amount = _field(cost, "value")
            if amount is None:
                amount = _field(cost, "cost")
            currency = _field(cost, "currency")
        else:
            continue
        if isinstance(amount, (int, float)) and not isinstance(amount, bool) and isinstance(currency, str) and currency:
            return ReportedCost(amount=float(amount), currency=currency, source=source)
    return None


@dataclass
class ModelResponse:
    message: Message
    usage: Dict[str, Any] = field(default_factory=dict)
    cost: Optional[ReportedCost] = None
    raw: Any = None


@dataclass
class ModelStreamChunk:
    """One incremental provider update, optionally ending with the full response."""

    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    response: Optional[ModelResponse] = None


class BaseModel(abc.ABC):
    """Minimal contract that every provider implements."""

    provider: str = "base"
    model_id: str = ""
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    @abc.abstractmethod
    def invoke(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ModelResponse:
        """Calls the provider (non-streaming). Returns a ModelResponse with the message."""

    async def ainvoke(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ModelResponse:
        return self.invoke(messages, tools)

    def stream(
        self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[ModelStreamChunk]:
        """Streams provider updates; providers without native support fall back to one response."""
        yield ModelStreamChunk(response=self.invoke(messages, tools))


class OpenAILike(BaseModel):
    """Pattern reused from agno: a provider compatible with the OpenAI API.

    Lets you point to OpenAI, Groq, Ollama, Together, Fireworks... by changing
    `base_url` and `api_key`. The broader provider suite of the MVP builds on this
    plus google-genai and anthropic.
    """

    def __init__(
        self,
        id: str,
        provider: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_type: str = "output",
    ):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError('Install "openai>=1.40" to use OpenAI/Groq/Ollama.') from e
        # The OpenAI SDK appends /v1 automatically ONLY when base_url is None.
        # For compatibility servers (Ollama, OpenRouter, Together, ...) the caller
        # usually provides the root host; ensure the /v1 (OpenAI-compatible) path.
        if base_url and not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        kwargs: Dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self.provider = provider
        self.model_id = id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model_type = model_type

    def _compat_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        out = []
        for t in tools:
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
            )
        return out

    def invoke(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ModelResponse:
        resp = self._client.chat.completions.create(
            model=self.model_id,
            messages=messages,  # type: ignore[arg-type]
            tools=self._compat_tools(tools),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        choice = resp.choices[0].message
        tool_calls = None
        if getattr(choice, "tool_calls", None):
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments or "{}",
                )
                for tc in choice.tool_calls
            ]
        content = choice.content
        reasoning = getattr(choice, "reasoning_content", None)
        msg = Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            reasoning_content=reasoning if reasoning else None,
        )
        usage = getattr(resp, "usage", None)
        return ModelResponse(
            message=msg,
            usage={
                "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
            },
            cost=_reported_cost(resp, self.provider),
            raw=resp,
        )

    def stream(
        self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None
    ) -> Iterator[ModelStreamChunk]:
        """Yield OpenAI text deltas and finish with the assembled response."""
        response_stream = self._client.chat.completions.create(
            model=self.model_id,
            messages=messages,  # type: ignore[arg-type]
            tools=self._compat_tools(tools),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_calls: Dict[int, Dict[str, str]] = {}
        usage: Dict[str, Any] = {}
        last_chunk: Any = None

        for chunk in response_stream:
            last_chunk = chunk
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage:
                usage = {
                    "input_tokens": getattr(chunk_usage, "prompt_tokens", 0),
                    "output_tokens": getattr(chunk_usage, "completion_tokens", 0),
                }
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            reasoning = getattr(delta, "reasoning_content", None)
            if text:
                content_parts.append(text)
            if reasoning:
                reasoning_parts.append(reasoning)
            for tool_call in getattr(delta, "tool_calls", None) or []:
                index = tool_call.index
                current = tool_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                if tool_call.id:
                    current["id"] = tool_call.id
                function = tool_call.function
                if function.name:
                    current["name"] = function.name
                if function.arguments:
                    current["arguments"] += function.arguments
            if text or reasoning:
                yield ModelStreamChunk(content=text, reasoning_content=reasoning)

        calls = [
            ToolCall(id=call["id"] or None, name=call["name"], arguments=call["arguments"] or "{}")
            for _, call in sorted(tool_calls.items())
        ]
        yield ModelStreamChunk(
            response=ModelResponse(
                message=Message(
                    role="assistant",
                    content="".join(content_parts) or None,
                    tool_calls=calls or None,
                    reasoning_content="".join(reasoning_parts) or None,
                ),
                usage=usage,
                cost=_reported_cost(last_chunk, self.provider),
                raw=last_chunk,
            )
        )


class AnthropicModel(BaseModel):
    def __init__(
        self,
        id: str,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 1024,
        model_type: str = "output",
    ):
        try:
            import anthropic
        except ImportError as e:
            raise ImportError('Install "anthropic>=0.40" to use Anthropic models.') from e
        self.provider = "anthropic"
        self.model_id = id
        self._client = anthropic.Anthropic(api_key=api_key or "")
        # Anthropic 1.0.0 removed temperature from messages.create params
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model_type = model_type
        self._anthropic = anthropic

    def _server_tools(self, tools):
        if not tools:
            return None
        return [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            }
            for t in tools
        ]

    def _convert_messages(self, messages, system_parts):
        """Convert OpenAI-style messages to Anthropic native format.

        - system messages -> prepended to `system` argument.
        - assistant with tool_calls -> content blocks with `tool_use`.
        - role "tool" -> appended as user message with `tool_result` block.
        Consecutive tool results are merged into a single user message.
        """
        convo = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                system_parts.append(m.get("content", ""))
                continue
            if role == "assistant":
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls", []):
                    # support both OpenAI-style and raw dicts
                    fn = tc.get("function", tc)
                    try:
                        args = json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {})
                    except json.JSONDecodeError:
                        args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id") or fn.get("name"),
                            "name": fn.get("name") or "",
                            "input": args or {},
                        }
                    )
                convo.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
            elif role == "tool":
                result = {
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id") or m.get("name"),
                    "content": m.get("content") or "",
                }
                if convo and convo[-1]["role"] == "user" and isinstance(convo[-1].get("content"), list) and all(
                    isinstance(c, dict) and c.get("type") in ("tool_result",) for c in convo[-1]["content"]
                ):
                    convo[-1]["content"].append(result)
                else:
                    convo.append({"role": "user", "content": [result]})
            else:  # user
                convo.append({"role": "user", "content": m.get("content", "")})
        return convo

    def invoke(self, messages, tools=None):
        system_parts: List[str] = []
        convo = self._convert_messages(messages, system_parts)
        kwargs = {}
        if self.temperature is not None:
            kwargs["extra_body"] = {"temperature": self.temperature}
        server_tools = self._server_tools(tools)
        if server_tools:
            kwargs["tools"] = server_tools
        resp = self._client.messages.create(
            model=self.model_id,
            max_tokens=self.max_tokens,
            system="\n".join(system_parts) if system_parts else None,
            messages=convo,
            **kwargs,
        )
        content = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=json.dumps(block.input))
                )
        usage = getattr(resp, "usage", None)
        return ModelResponse(
            message=Message(
                role="assistant",
                content=content or None,
                tool_calls=tool_calls or None,
            ),
            usage={
                "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
                "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
            },
            cost=_reported_cost(resp, self.provider),
            raw=resp,
        )


class GoogleModel(BaseModel):
    def __init__(
        self,
        id: str,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        model_type: str = "output",
    ):
        try:
            from google import genai
        except ImportError as e:
            raise ImportError('Instalá "google-genai>=0.2" para usar Gemini.') from e
        self.provider = "google"
        self.model_id = id
        self._client = genai.Client(api_key=api_key or "")
        self.temperature = temperature
        self.model_type = model_type

    def invoke(self, messages, tools=None):
        from google.genai import types as gtypes

        system_parts = []
        contents = []
        for m in messages:
            role = m["role"]
            if role == "system":
                system_parts.append(m["content"])
            elif role == "tool":
                fn_name = m.get("name", "")
                result = m.get("content", "")
                if contents and contents[-1].role == "user":
                    parts = list(contents[-1].parts)
                    parts.append(gtypes.Part.from_function_response(name=fn_name, response={"result": result}))
                    contents[-1] = gtypes.Content(role="user", parts=parts)
                else:
                    contents.append(gtypes.Content(
                        role="user",
                        parts=[gtypes.Part.from_function_response(name=fn_name, response={"result": result})]
                    ))
            elif role == "assistant":
                if not m.get("tool_calls"):
                    contents.append(gtypes.Content(role="model", parts=[gtypes.Part(text=m.get("content", ""))]))
            else:
                contents.append(gtypes.Content(role="user", parts=[gtypes.Part(text=m.get("content", ""))]))

        tool_cfg = None
        if tools:
            declarations = []
            for t in tools:
                declarations.append(
                    gtypes.FunctionDeclaration(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                        parameters=t.get("parameters", {"type": "object", "properties": {}}),
                    )
                )
            tool_cfg = [gtypes.Tool(function_declarations=declarations)]

        resp = self._client.models.generate_content(
            model=self.model_id,
            contents=contents,
            config=gtypes.GenerateContentConfig(
                system_instruction="\n".join(system_parts) if system_parts else None,
                temperature=self.temperature,
                tools=tool_cfg,
            ),
        )
        text = ""
        tool_calls = []
        if resp.candidates:
            cand = resp.candidates[0]
            for part in cand.content.parts:
                if part.text:
                    text += part.text
                if part.function_call:
                    fn = part.function_call
                    tool_calls.append(
                        ToolCall(
                            id=getattr(fn, "id", None),
                            name=fn.name,
                            arguments=json.dumps({k: v for k, v in fn.args.items()} if fn.args else {}),
                        )
                    )
        usage = getattr(resp, "usage_metadata", None)
        return ModelResponse(
            message=Message(
                role="assistant",
                content=text or None,
                tool_calls=tool_calls or None,
            ),
            usage={
                "input_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
                "output_tokens": getattr(usage, "candidates_token_count", 0) if usage else 0,
            },
            cost=_reported_cost(resp, self.provider),
            raw=resp,
        )
