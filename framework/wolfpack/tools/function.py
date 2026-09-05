"""Function and FunctionCall: the framework's typed tool.

A `Function` wraps a callable, infers its JSON schema and exposes it to the model.
`FunctionCall` executes the function with validated/preprocessed JSON args and returns
a `FunctionExecutionResult` which the model loop turns into a `tool` message.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import typing
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from .json_schema import get_json_schema


@dataclass
class FunctionExecutionResult:
    status: str  # success | error | requires_confirmation | requires_user_input
    result: Any = None
    error: Optional[str] = None
    updated_session_state: Optional[Dict[str, Any]] = None


class Function:
    def __init__(
        self,
        name: str,
        description: str,
        entrypoint: Callable[..., Any],
        parameters: Optional[Dict[str, Any]] = None,
        requires_confirmation: bool = False,
        requires_user_input: bool = False,
        name_suggestion: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.entrypoint = entrypoint
        self.parameters = parameters or get_schema_from_callable(entrypoint, name, description)
        self.requires_confirmation = requires_confirmation
        self.requires_user_input = requires_user_input

    @property
    def is_async(self) -> bool:
        return inspect.iscoroutinefunction(self.entrypoint) or (
            hasattr(self.entrypoint, "__wrapped__") and inspect.iscoroutinefunction(self.entrypoint.__wrapped__)
        )

    def get_tool_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters.get("parameters", self.parameters),
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.get_tool_schema()

    def get_function_call(self, call_id: str, arguments: Union[str, Dict[str, Any]]) -> "FunctionCall":
        if isinstance(arguments, str):
            if not arguments.strip():
                raise ValueError(f"Tool '{self.name}': empty arguments")
            try:
                args = json.loads(arguments)
            except json.JSONDecodeError as e:
                raise ValueError(f"Tool '{self.name}': invalid JSON arguments: {e}")
        else:
            args = arguments or {}
        return FunctionCall(call_id=call_id, func=self, arguments=args)


class FunctionCall:
    def __init__(
        self,
        func: Function,
        call_id: str,
        arguments: Dict[str, Any],
        agent: Any = None,
        run_context: Any = None,
    ):
        self.func = func
        self.call_id = call_id
        self.arguments = arguments
        self.agent = agent
        self.run_context = run_context

    def _build_kwargs(self) -> Dict[str, Any]:
        kwargs = dict(self.arguments)
        sig = inspect.signature(self.func.entrypoint)
        for pname in sig.parameters:
            if pname == "agent" and "agent" not in kwargs:
                kwargs["agent"] = self.agent
            if pname == "run_context" and "run_context" not in kwargs:
                kwargs["run_context"] = self.run_context
        return kwargs

    def execute(self) -> FunctionExecutionResult:
        if self.func.requires_confirmation:
            return FunctionExecutionResult(status="tool_confirmation", result=None)
        if self.func.requires_user_input:
            return FunctionExecutionResult(status="requires_user_input", result=None)
        kwargs = self._build_kwargs()
        try:
            if self.func.is_async:
                # We can't run async inside sync; delegate to a loop.
                result = self._run_async(self.func.entrypoint, kwargs)
            else:
                result = self.func.entrypoint(**kwargs)
            return FunctionExecutionResult(status="success", result=result)
        except Exception as e:
            return FunctionExecutionResult(status="error", error=str(e))

    def _run_async(self, fn: Callable[..., Any], kwargs: Dict[str, Any]) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(fn(**kwargs))
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: asyncio.run(fn(**kwargs)))
            return future.result()

    async def aexecute(self) -> FunctionExecutionResult:
        if self.func.requires_confirmation:
            return FunctionExecutionResult(status="tool_confirmation", result=None)
        if self.func.requires_user_input:
            return FunctionExecutionResult(status="requires_user_input", result=None)
        kwargs = self._build_kwargs()
        try:
            if self.func.is_async:
                result = await self.func.entrypoint(**kwargs)
            else:
                result = self.func.entrypoint(**kwargs)
            return FunctionExecutionResult(status="success", result=result)
        except Exception as e:
            return FunctionExecutionResult(status="error", error=str(e))


def get_schema_from_callable(fn: Callable[..., Any], name: str, description: str) -> Dict[str, Any]:
    return get_json_schema(fn, name, description)