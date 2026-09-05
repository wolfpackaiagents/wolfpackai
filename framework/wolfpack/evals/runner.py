"""Deterministic evaluation primitives for Wolfpack targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Union


ScoreValue = Union[float, str, bool]


@dataclass
class EvalCase:
    """One input, its expected result, and optional AMP trace association."""

    input: Any
    expected: Any = None
    id: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalScore:
    """A named numeric or categorical score produced for an evaluation case."""

    name: str
    value: Union[float, str]
    comment: Optional[str] = None


@dataclass
class EvalResult:
    """The target output and evaluator scores for one case."""

    case: EvalCase
    output: Any
    scores: List[EvalScore]


@dataclass
class EvalReport:
    """Results from a complete evaluation run."""

    results: List[EvalResult]

    @property
    def averages(self) -> Dict[str, float]:
        """Returns the mean for each numeric score."""
        totals: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        for result in self.results:
            for score in result.scores:
                if isinstance(score.value, float):
                    totals[score.name] = totals.get(score.name, 0.0) + score.value
                    counts[score.name] = counts.get(score.name, 0) + 1
        return {name: totals[name] / counts[name] for name in totals}


class Evaluator(Protocol):
    """Produces one score for a target output."""

    def evaluate(self, case: EvalCase, output: Any) -> EvalScore:
        """Evaluates a target output for one case."""


class ScorePublisher(Protocol):
    """Receives scores associated with a trace."""

    def publish(self, trace_id: str, score: EvalScore) -> None:
        """Publishes a score for a trace."""


class CallableEvaluator:
    """Adapts a deterministic function into an evaluator."""

    def __init__(self, name: str, evaluator: Callable[[EvalCase, Any], Union[EvalScore, ScoreValue]]):
        self.name = name
        self._evaluator = evaluator

    def evaluate(self, case: EvalCase, output: Any) -> EvalScore:
        value = self._evaluator(case, output)
        if isinstance(value, EvalScore):
            return value
        if isinstance(value, bool):
            value = float(value)
        if not isinstance(value, (float, str)):
            raise TypeError("Evaluator functions must return EvalScore, float, str, or bool.")
        return EvalScore(name=self.name, value=value)


class EvalRunner:
    """Runs a callable target against cases and deterministic evaluators."""

    def __init__(
        self,
        target: Callable[[Any], Any],
        evaluators: Iterable[Evaluator],
        publisher: Optional[ScorePublisher] = None,
    ):
        self.target = target
        self.evaluators = list(evaluators)
        self.publisher = publisher

    def run(self, cases: Iterable[EvalCase]) -> EvalReport:
        results: List[EvalResult] = []
        for case in cases:
            output = self.target(case.input)
            scores = [evaluator.evaluate(case, output) for evaluator in self.evaluators]
            if self.publisher and case.trace_id:
                for score in scores:
                    self.publisher.publish(case.trace_id, score)
            results.append(EvalResult(case=case, output=output, scores=scores))
        return EvalReport(results=results)
