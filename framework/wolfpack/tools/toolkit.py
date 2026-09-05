"""Toolkit: named registry of functions, agno style.

A Toolkit groups several `Function` objects under a name. The Agent accepts tools as
lists of `tool | Function | Toolkit | Callable | dict`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from .function import Function


class Toolkit:
    def __init__(self, name: str = "", functions: List[Function] | None = None):
        self.name = name or self.__class__.__name__
        self.functions: Dict[str, Function] = {}
        self.function_versions: Dict[str, int] = {}
        if functions:
            for f in functions:
                self.register(f)

    def register(self, function: Function | Callable[..., Any] | None = None, name: str | None = None, **kwargs: Any):
        if isinstance(function, str):
            # register(name, entrypoint)
            name, entrypoint = function, kwargs.pop("entrypoint", None) or kwargs.pop("callable", None)
            return self._register_callable(name, entrypoint, kwargs)
        if callable(function):
            return self._register_callable(name or function.__name__, function, kwargs)
        if isinstance(function, Function):
            final = name or function.name
            self.functions[final] = function
            self.function_versions[final] = self.function_versions.get(final, 0) + 1
            return self
        raise TypeError("Toolkit.register espera Function, callable o (name, entrypoint).")

    def _register_callable(self, name: str | None, entrypoint: Callable[..., Any], kwargs: Dict[str, Any]):
        final = name or entrypoint.__name__
        self.functions[final] = Function(
            name=final,
            description=kwargs.pop("description", ""),
            entrypoint=entrypoint,
            requires_confirmation=kwargs.pop("requires_confirmation", False),
            requires_user_input=kwargs.pop("requires_user_input", False),
        )
        return self

    def get_tools(self) -> List[Dict[str, Any]]:
        return [f.get_tool_schema() for f in self.functions.values()]

    def to_dict(self) -> List[Dict[str, Any]]:
        return self.get_tools()

    def as_dict(self) -> Dict[str, Any]:
        return {name: f.get_tool_schema() for name, f in self.functions.items()}