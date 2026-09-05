"""`@tool` decorator to define tools easily, agno style.

Usage:

    @tool
    def get_weather(city: str) -> str:
        '''Gets the weather for a city.
        Args:
            city: the city.
        '''
        return f"Weather in {city}: sunny"

    @tool(requires_confirmation=True)
    def delete_user(user_id: int) -> str: ...

Supports sync and async (generator included).
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import typing
from typing import Any, Callable, Dict, Optional

from .function import Function


def tool(
    func: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    requires_confirmation: bool = False,
    requires_user_input: bool = False,
):
    def decorator(f: Callable[..., Any]):
        fname = name or f.__name__
        fdoc = description or f.__doc__ or ""
        fn = Function(
            name=fname,
            description=fdoc,
            entrypoint=f,
            requires_confirmation=requires_confirmation,
            requires_user_input=requires_user_input,
        )

        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any):
            return f(*args, **kwargs)

        wrapper.function = fn  # type: ignore[attr-defined]
        return wrapper

    if func is None:
        return decorator
    return decorator(func)