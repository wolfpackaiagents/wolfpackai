"""AgentForce: Mass parallel execution orchestrator with pools and predictive intelligence."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Union
from .acquisition import DataSource, normalize_to_tasks
from .dispatcher import ForceDispatcher
from .events import (
    ForceCompletedEvent,
    ForceEvent,
    ForcePredictionEvent,
    ForceProgressEvent,
    ForceStartedEvent,
    ForceTaskCompletedEvent,
)
from .prediction import AIPredictionEngine
from .result import AgentForceResult, PoolSummary
from .spec import ExecutorSpec, PoolConfig, TaskItem, TaskResult


class AgentForce:
    """Orchestrates mass parallel actions with a coordinator agent and executor pools."""

    def __init__(
        self,
        coordinator: Any,  # Coordinator Agent
        *,
        name: str = "AgentForce",
        max_workers: int = 10,
        telemetry: Any = None,
        prediction_enabled: bool = True,
        amp_url: Optional[str] = None,
        amp_api_key: Optional[str] = None,
    ) -> None:
        self.coordinator = coordinator
        self.name = name
        self.max_workers = max_workers
        self.telemetry = telemetry
        self.prediction_enabled = prediction_enabled
        self.pools: Dict[str, PoolConfig] = {}
        self.prediction_engine = AIPredictionEngine(amp_url=amp_url, amp_api_key=amp_api_key)

    def add_executor(
        self,
        name: Union[ExecutorSpec, str, None] = None,
        agent: Optional[Any] = None,
        pool: Optional[str] = None,
        *,
        spec: Optional[ExecutorSpec] = None,
        max_concurrency: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
        policy: Optional[Any] = None,
        knowledge: Optional[Any] = None,
        toolkits: Optional[List[Any]] = None,
    ) -> None:
        """Registers an executor agent into a named pool."""
        target_spec: ExecutorSpec
        if spec is not None:
            target_spec = spec
        elif isinstance(name, ExecutorSpec):
            target_spec = name
        elif isinstance(name, str):
            if agent is None:
                raise ValueError("An agent instance must be provided when passing a name string.")
            pool_name = pool or "default"
            target_spec = ExecutorSpec(
                name=name,
                agent=agent,
                pool=pool_name,
                max_concurrency=max_concurrency,
                metadata=metadata or {},
                policy=policy,
                knowledge=knowledge,
                toolkits=toolkits,
            )
        else:
            raise ValueError("Either an ExecutorSpec or name+agent must be provided.")

        if target_spec.pool not in self.pools:
            self.pools[target_spec.pool] = PoolConfig(name=target_spec.pool, max_concurrency=target_spec.max_concurrency)
        else:
            self.pools[target_spec.pool].max_concurrency = max(
                self.pools[target_spec.pool].max_concurrency, target_spec.max_concurrency
            )

        self.pools[target_spec.pool].add_executor(target_spec)

    def run(
        self,
        mission: str,
        *,
        data: Optional[List[Any]] = None,
        data_source: Optional[Any] = None,
        toolkit: Optional[Any] = None,
        policy: Optional[Any] = None,
        stream: bool = False,
    ) -> Union[AgentForceResult, Iterator[ForceEvent]]:
        """Executes a mass action mission. Returns AgentForceResult or streams ForceEvents."""
        if stream:
            return self._run_stream(
                mission=mission,
                data=data,
                data_source=data_source,
                toolkit=toolkit,
                policy=policy,
            )
        return self._run_sync(
            mission=mission,
            data=data,
            data_source=data_source,
            toolkit=toolkit,
            policy=policy,
        )

    def _run_sync(
        self,
        mission: str,
        *,
        data: Optional[List[Any]] = None,
        data_source: Optional[Any] = None,
        toolkit: Optional[Any] = None,
        policy: Optional[Any] = None,
    ) -> AgentForceResult:
        """Synchronous execution returning the final aggregated AgentForceResult."""
        events: List[ForceEvent] = []
        result: Optional[AgentForceResult] = None

        for item in self._run_stream(
            mission=mission,
            data=data,
            data_source=data_source,
            toolkit=toolkit,
            policy=policy,
        ):
            if isinstance(item, ForceEvent):
                events.append(item)
            elif isinstance(item, AgentForceResult):
                result = item

        if result is not None:
            return result

        return self._build_empty_result(mission)

    def _run_stream(
        self,
        mission: str,
        *,
        data: Optional[List[Any]] = None,
        data_source: Optional[Any] = None,
        toolkit: Optional[Any] = None,
        policy: Optional[Any] = None,
    ) -> Iterator[Any]:
        """Generator yielding ForceEvents in real time and finally yielding the AgentForceResult."""
        t0 = time.monotonic()

        # Step 1: Acquire and normalize data items
        default_pool = next(iter(self.pools.keys()), "default")
        tasks = normalize_to_tasks(
            data=data,
            data_source=data_source,
            toolkit=toolkit,
            policy=policy,
            mission=mission,
            default_pool=default_pool,
        )

        total_tasks = len(tasks)
        pool_counts = {p: sum(1 for t in tasks if t.pool == p) for p in self.pools}

        # Emit ForceStartedEvent
        yield ForceStartedEvent(
            force_name=self.name,
            total_tasks=total_tasks,
            mission=mission,
            pools=pool_counts,
        )

        # Step 2: AIPrediction Engine forecasting
        forecast: Dict[str, Any] = {}
        if self.prediction_enabled and tasks:
            forecast = self.prediction_engine.predict(
                mission=mission,
                tasks=tasks,
                pools=self.pools,
            )
            yield ForcePredictionEvent(
                force_name=self.name,
                predicted_duration_ms=forecast.get("predicted_duration_ms", 0.0),
                predicted_cost=forecast.get("predicted_cost", 0.0),
                predicted_tokens=forecast.get("predicted_tokens", 0),
                predicted_success_rate=forecast.get("predicted_success_rate", 1.0),
                bottlenecks=forecast.get("bottlenecks", []),
                confidence=forecast.get("confidence", 0.95),
            )

        # Step 3: Dispatch tasks concurrently with live progress queue
        event_queue: queue.Queue[ForceEvent] = queue.Queue()
        done_flag = threading.Event()

        def _enqueue_event(ev: ForceEvent) -> None:
            event_queue.put(ev)

        dispatcher = ForceDispatcher(
            pools=self.pools,
            max_workers=self.max_workers,
            emit_callback=_enqueue_event,
            force_name=self.name,
        )

        task_results: List[TaskResult] = []

        def _worker_thread() -> None:
            nonlocal task_results
            try:
                task_results = dispatcher.execute_all(
                    tasks,
                    predicted_duration_ms=forecast.get("predicted_duration_ms", 0.0),
                )
            finally:
                done_flag.set()

        thread = threading.Thread(target=_worker_thread, daemon=True)
        thread.start()

        # Yield progress events as they arrive
        while not done_flag.is_set() or not event_queue.empty():
            try:
                ev = event_queue.get(timeout=0.05)
                yield ev
            except queue.Empty:
                continue

        # Step 4: Synthesize results with the Coordinator
        completed_tasks = [r for r in task_results if r.status == "completed"]
        failed_tasks = [r for r in task_results if r.status == "failed"]
        synthesis = self._synthesize_with_coordinator(mission, task_results)

        total_duration_ms = (time.monotonic() - t0) * 1000.0

        # Build pool summaries
        summaries: Dict[str, PoolSummary] = {}
        for pool_name, pool_cfg in self.pools.items():
            pool_results = [r for r in task_results if r.pool == pool_name]
            p_comp = sum(1 for r in pool_results if r.status == "completed")
            p_fail = sum(1 for r in pool_results if r.status == "failed")
            p_dur = sum(r.duration_ms for r in pool_results)
            p_tok = sum(r.tokens_used for r in pool_results)
            s = PoolSummary(
                pool=pool_name,
                total_tasks=len(pool_results),
                completed_tasks=p_comp,
                failed_tasks=p_fail,
                total_duration_ms=p_dur,
                total_tokens=p_tok,
                active_workers=len(pool_cfg.executors),
            )
            s.compute_averages()
            summaries[pool_name] = s

        # Emit ForceCompletedEvent
        yield ForceCompletedEvent(
            force_name=self.name,
            completed=len(completed_tasks),
            failed=len(failed_tasks),
            total_duration_ms=total_duration_ms,
            synthesis_preview=synthesis[:200] if synthesis else "",
            metrics={
                "total_tasks": total_tasks,
                "completed": len(completed_tasks),
                "failed": len(failed_tasks),
                "duration_ms": total_duration_ms,
                "pools": {p: s.completed_tasks for p, s in summaries.items()},
            },
        )

        status_str = "completed" if len(failed_tasks) == 0 else "partial" if len(completed_tasks) > 0 else "failed"

        final_result = AgentForceResult(
            mission=mission,
            status=status_str,
            synthesis=synthesis,
            tasks=task_results,
            pool_summaries=summaries,
            total_tasks=total_tasks,
            completed_tasks=len(completed_tasks),
            failed_tasks=len(failed_tasks),
            duration_ms=total_duration_ms,
            prediction=forecast,
        )

        yield final_result

    def _synthesize_with_coordinator(self, mission: str, results: List[TaskResult]) -> str:
        """Uses the coordinator agent to generate a consolidated synthesis of the batch."""
        if not self.coordinator or not results:
            return ""

        summary_lines = []
        for r in results[:15]:  # provide representative sample to avoid token bloat
            preview = str(r.output or r.error or "")[:80]
            summary_lines.append(f"- [{r.pool} / {r.executor_name}] Task {r.task_id}: {preview}")

        if len(results) > 15:
            summary_lines.append(f"... and {len(results) - 15} more completed actions.")

        synthesis_prompt = (
            f"Mission: {mission}\n\n"
            f"The execution force completed {len([r for r in results if r.status == 'completed'])} actions "
            f"across pools with {len([r for r in results if r.status == 'failed'])} failures.\n\n"
            f"Sample of executed actions:\n"
            + "\n".join(summary_lines)
            + "\n\nProvide a concise executive summary of the overall outcome and key observations."
        )

        try:
            coord_out = self.coordinator.run(synthesis_prompt)
            return getattr(coord_out, "content", str(coord_out))
        except Exception as exc:
            return f"Completed {len(results)} actions. (Synthesis note: {exc})"

    def _build_empty_result(self, mission: str) -> AgentForceResult:
        return AgentForceResult(
            mission=mission,
            status="completed",
            synthesis="No tasks to execute.",
            total_tasks=0,
            completed_tasks=0,
            failed_tasks=0,
            duration_ms=0.0,
        )
