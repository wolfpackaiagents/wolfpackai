"""Small deterministic DAG workflow runner for Wolfpack."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class WorkflowError(RuntimeError):
    pass


@dataclass
class WorkflowResult:
    state: Dict[str, Any]
    outputs: Dict[str, Any]
    skipped: List[str] = field(default_factory=list)


@dataclass
class _Step:
    name: str
    handler: Callable[[Dict[str, Any]], Any]
    depends_on: List[str]
    retries: int
    condition: Optional[Callable[[Dict[str, Any]], bool]]


class Workflow:
    """Executes named steps in dependency order with optional retry and routing."""

    def __init__(self, name: str):
        self.name = name
        self._steps: Dict[str, _Step] = {}

    def add_step(
        self,
        name: str,
        handler: Callable[[Dict[str, Any]], Any],
        *,
        depends_on: Optional[List[str]] = None,
        retries: int = 0,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> "Workflow":
        if name in self._steps:
            raise WorkflowError(f"Step '{name}' already exists.")
        if retries < 0:
            raise WorkflowError("retries must be zero or greater.")
        self._steps[name] = _Step(name, handler, depends_on or [], retries, condition)
        return self

    def run(self, initial_state: Optional[Dict[str, Any]] = None) -> WorkflowResult:
        state = dict(initial_state or {})
        outputs: Dict[str, Any] = {}
        skipped: List[str] = []
        pending = dict(self._steps)
        while pending:
            ready = [step for step in pending.values() if all(dep in outputs or dep in skipped for dep in step.depends_on)]
            if not ready:
                missing = {name: step.depends_on for name, step in pending.items()}
                raise WorkflowError(f"Workflow has cyclic or missing dependencies: {missing}")
            for step in ready:
                del pending[step.name]
                if step.condition and not step.condition(state):
                    skipped.append(step.name)
                    continue
                for attempt in range(step.retries + 1):
                    try:
                        result = step.handler(state)
                        outputs[step.name] = result
                        state[step.name] = result
                        break
                    except Exception as error:
                        if attempt == step.retries:
                            raise WorkflowError(f"Step '{step.name}' failed after {attempt + 1} attempt(s): {error}") from error
        return WorkflowResult(state=state, outputs=outputs, skipped=skipped)
