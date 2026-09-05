"""Infer JSON schema from type hints + docstring (agno-style pattern).

Supports pydantic/typing hints and Google-style docstrings for parameter
descriptions. "Reserved" parameters (agent, run_context...) are excluded from the
schema because the framework injects them at runtime.
"""

from __future__ import annotations

import inspect
import json
import re
import typing
from typing import Any, Dict, List, Optional, get_args, get_origin

RESERVED_PARAMS = {"agent", "team", "run_context", "fc", "trace", "media", "self"}


def _type_to_json_schema(tp: Any) -> Dict[str, Any]:
    if tp is inspect.Parameter.empty or tp is None:
        return {"type": "string"}
    if tp is str:
        return {"type": "string"}
    if tp is int:
        return {"type": "integer"}
    if tp is float:
        return {"type": "number"}
    if tp is bool:
        return {"type": "boolean"}
    if tp is list or tp is typing.List:
        return {"type": "array", "items": {}}
    if tp is dict or tp is typing.Dict:
        return {"type": "object"}
    origin = get_origin(tp)
    args = get_args(tp)
    if origin in (typing.List, list):
        item = args[0] if args else Any
        return {"type": "array", "items": _type_to_json_schema(item)}
    if origin in (typing.Dict, dict):
        return {"type": "object"}
    if origin in (typing.Union, typing.Optional):
        types = [t for t in args if t is not type(None)]  # noqa: E721
        if not types:
            return {"type": "null"}
        if len(types) == 1:
            return _type_to_json_schema(types[0])
        return {"anyOf": [_type_to_json_schema(t) for t in types]}
    if origin in (typing.Literal,):
        return {"enum": list(args)}
    # Pydantic model
    if hasattr(tp, "model_json_schema"):
        return tp.model_json_schema()
    if origin is None:
        try:
            if issubclass(tp, (str, int, float, bool)):
                if tp is str:
                    return {"type": "string"}
                if tp is int:
                    return {"type": "integer"}
                if tp is float:
                    return {"type": "number"}
                return {"type": "boolean"}
        except TypeError:
            pass
    return {"type": "object"}


def _parse_docstring(doc: str) -> Dict[str, str]:
    """Extract the description of each parameter from a Google-style docstring."""
    descs: Dict[str, str] = {}
    if not doc:
        return descs
    lines = [ln.strip() for ln in doc.splitlines()]
    in_args = False
    for ln in lines:
        if re.match(r"^(Args|Parameters|Arguments):", ln):
            in_args = True
            continue
        if re.match(r"^(Returns|Raises|Example|Examples|Yields):", ln):
            in_args = False
            continue
        if in_args:
            m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\([^)]*\))?:\s*(.*)", ln)
            if m:
                out = m.group(2)
                if out:
                    descs[m.group(1)] = out
    return descs


def get_json_schema(func: Any, name: str, doc: Optional[str] = None) -> Dict[str, Any]:
    """Generate the tool JSON-schema for the model from the callable's signature."""
    sig = inspect.signature(func)
    doc = doc or (inspect.getdoc(func) or "")
    descs = _parse_docstring(doc)
    func_desc = ""
    if doc:
        m = re.search(r"^([^\n]*)", doc)
        if m:
            func_desc = m.group(1).strip()
    properties: Dict[str, Dict[str, Any]] = {}
    required: List[str] = []
    param_types: Dict[str, Any] = {}
    try:
        param_types = typing.get_type_hints(func)
    except (NameError, TypeError):
        if hasattr(func, "__annotations__"):
            param_types = dict(func.__annotations__)
    for pname, param in sig.parameters.items():
        if pname in RESERVED_PARAMS:
            continue
        if pname in ("self", "cls"):
            continue
        tip = get_args(param.annotation)[0] if (
            hasattr(param.annotation, "__origin__") and get_origin(param.annotation) in (typing.Optional,)
        ) else param.annotation
        hint = param_types.get(pname, Any)
        schema = _type_to_json_schema(hint)
        if pname in descs:
            schema["description"] = descs[pname]
        properties[pname] = schema
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {
        "name": name,
        "description": func_desc,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def encode_arguments(**kwargs: Any) -> str:
    return json.dumps(kwargs, default=str)
