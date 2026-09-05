"""Guardrails: input/output validation hooks for the agent.

Borrows the unified guardrail/eval-hook pipeline from agno (pre_hooks/post_hooks)
and the guardrail result shape from crewAI (`{ success, result?, error? }`).

A guardrail runs synchronously so it can abort an invalid input/output (raise
`InputCheckError` / `OutputCheckError`). Non-blocking hooks run in the background.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple


class GuardrailError(Exception):
    """Base for guardrail failures."""


class InputCheckError(GuardrailError):
    """Raised by an input guardrail to abort a run before the model is called."""


class OutputCheckError(GuardrailError):
    """Raised by an output guardrail to reject a model response."""


class GuardrailResult:
    def __init__(self, success: bool, result: Any = None, error: Optional[str] = None):
        self.success = success
        self.result = result
        self.error = error

    @classmethod
    def ok(cls, result: Any = None) -> "GuardrailResult":
        return cls(True, result)

    @classmethod
    def fail(cls, error: str) -> "GuardrailResult":
        return cls(False, None, error)

    def to_dict(self) -> Dict[str, Any]:
        return {"success": self.success, "result": self.result, "error": self.error}


class BaseGuardrail(ABC):
    """A guardrail that inspects the raw user input or the final output."""

    @abstractmethod
    def check(self, run_input: Any) -> GuardrailResult:
        """Inspect input/output. Return GuardrailResult. Raise to abort."""

    async def acheck(self, run_input: Any) -> GuardrailResult:
        return self.check(run_input)


# Convenience type for hook functions
HookFunc = Any  # callable(run_input) -> Any|GuardrailResult


class PIIGuardrail(BaseGuardrail):
    """Detects and masks/removes personally identifiable information.

    Supports two modes:
      - mask:  replace PII with a placeholder (default, non-reversible at rest)
      - block: reject the input entirely if PII is present (missing base legal basis)

    Data minimization / LGPD-GDPR: masking happens BEFORE the payload is sent to
    the model and before it is persisted, so PII does not leak to providers or logs.
    """

    EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    PHONE_RE = re.compile(r"\+?\d[\d\s.\-()]{8,}\d")
    SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){15,16}\d\b")

    def __init__(self, mode: str = "mask", block_list: bool = True, placeholder: str = "[PII_REDACTED]"):
        self.mode = mode  # 'mask' | 'block'
        self.block = block_list and mode == "block"
        self.placeholder = placeholder

    def _mask(self, text: str) -> str:
        out = self.PHONE_RE.sub(self.placeholder, text)
        out = self.SSN_RE.sub(self.placeholder, out)
        out = self.EMAIL_RE.sub(self.placeholder, out)
        out = self.CREDIT_CARD_RE.sub(self.placeholder, out)
        return out

    def check(self, run_input: Any) -> GuardrailResult:
        text = str(run_input) if not isinstance(run_input, dict) else str(run_input)
        masked = self._mask(text)
        found_pii = masked != text
        if self.block and found_pii:
            return GuardrailResult.fail("PII detected and blocked before the request.")
        # Return the masked copy so the caller can replace the input.
        return GuardrailResult.ok(masked)


class PromptInjectionGuardrail(BaseGuardrail):
    """Detects common prompt-injection / jailbreak patterns in user input.

    This is a heuristic guard, not a full security boundary. Real deployments pair
    it with an LLM-based classifier and strict tool allowlists.
    """

    PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I),
        re.compile(r"disregard\s+(the\s+)?(above|previous|instructions)", re.I),
        re.compile(r"jailbreak", re.I),
        re.compile(r"system\s+prompt", re.I),
        re.compile(r"you\s+are\s+now\s+an?", re.I),
        re.compile(r"forget\s+your\s+(instructions|role|prompt)", re.I),
        re.compile(r"\bdevil\s+avocado\b", re.I),
    ]

    def check(self, run_input: Any) -> GuardrailResult:
        text = str(run_input)
        for pattern in self.PATTERNS:
            if pattern.search(text):
                return GuardrailResult.fail("Prompt-injection pattern detected.")
        return GuardrailResult.ok()


class ToolAllowlistGuardrail(BaseGuardrail):
    """Enforces the set of tools an agent is allowed to invoke in a run.

    This is authorization at the tool boundary, NOT the prompt (per LGPD best
    practice: never rely only on the model being polite). Define an allowlist of
    tool names; any tool call outside the list is rejected before execution.
    """

    def __init__(self, allowed: Optional[list] = None, deny: Optional[list] = None):
        self.allowed = set(allowed or [])
        self.deny = set(deny or [])

    def check_tool(self, tool_name: str) -> Optional[GuardrailResult]:
        if tool_name in self.deny:
            return GuardrailResult.fail(f"Tool '{tool_name}' is blocked by policy.")
        if self.allowed and tool_name not in self.allowed:
            return GuardrailResult.fail(f"Tool '{tool_name}' is not in the allowlist.")
        return None

    def check(self, run_input: Any) -> GuardrailResult:
        # The run_input for a tool call is a dict with 'tool_name'.
        if isinstance(run_input, dict) and run_input.get("tool_name"):
            res = self.check_tool(run_input["tool_name"])
            if res:
                return res
        return GuardrailResult.ok()


class OutputSchemaGuardrail(BaseGuardrail):
    """Validates that final output parses to a Pydantic model."""

    def __init__(self, model: Any, on_error: str = "retry"):
        self.model = model
        self.on_error = on_error

    def check(self, run_input: Any) -> GuardrailResult:
        try:
            parsed = self.model.model_validate_json(run_input) if isinstance(run_input, str) else self.model(**run_input)
            return GuardrailResult.ok(parsed)
        except Exception as e:
            if self.on_error == "block":
                raise OutputCheckError(str(e)) from e
            return GuardrailResult.fail(str(e))