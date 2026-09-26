"""Parallel task dispatcher and pool execution engine."""

from __future__ import annotations

import concurrent.futures
import threading
import time
from typing import Any, Callable, Dict, List, Optional
from .events import ForceProgressEvent, ForceTaskCompletedEvent
from .spec import ExecutorSpec, PoolConfig, TaskItem, TaskResult


class ForceDispatcher:
    """Dispatches batches of TaskItems to pool executors using ThreadPoolExecutor."""

    def __init__(
        self,
        pools: Dict[str, PoolConfig],
        max_workers: int = 10,
        emit_callback: Optional[Callable[[Any], None]] = None,
        force_name: str = "AgentForce",
    ) -> None:
        self.pools = pools
        self.max_workers = max_workers
        self.emit = emit_callback or (lambda _: None)
        self.force_name = force_name
        self._pool_locks: Dict[str, threading.Semaphore] = {
            name: threading.Semaphore(config.max_concurrency)
            for name, config in pools.items()
        }
        self._round_robin_indices: Dict[str, int] = {name: 0 for name in pools}
        self._index_lock = threading.Lock()

    def execute_all(
        self,
        tasks: List[TaskItem],
        predicted_duration_ms: float = 0.0,
    ) -> List[TaskResult]:
        """Executes all tasks concurrently in parallel pools, emitting progress updates."""
        total_tasks = len(tasks)
        if total_tasks == 0:
            return []

        results: List[TaskResult] = []
        completed_count = 0
        active_pools: Dict[str, int] = {p: 0 for p in self.pools}
        progress_lock = threading.Lock()
        start_time = time.monotonic()

        def _run_single_task(task: TaskItem) -> TaskResult:
            nonlocal completed_count
            pool_name = task.pool
            pool_config = self.pools.get(pool_name)

            # Fallback if pool is unknown: pick first available pool or dummy
            if not pool_config or not pool_config.executors:
                first_pool = next(iter(self.pools.values()), None)
                if not first_pool or not first_pool.executors:
                    return TaskResult(
                        task_id=task.id,
                        pool=pool_name,
                        executor_name="unassigned",
                        status="failed",
                        error=f"No executors configured for pool '{pool_name}'",
                    )
                pool_config = first_pool
                pool_name = first_pool.name

            # Acquire per-pool concurrency semaphore
            sem = self._pool_locks.get(pool_name)
            if sem:
                sem.acquire()

            with progress_lock:
                active_pools[pool_name] = active_pools.get(pool_name, 0) + 1

            # Select executor round-robin within pool
            with self._index_lock:
                idx = self._round_robin_indices[pool_name] % len(pool_config.executors)
                self._round_robin_indices[pool_name] = idx + 1
                executor_spec = pool_config.executors[idx]

            task_start = time.monotonic()
            task_result: TaskResult

            try:
                task_result = self._dispatch_to_executor(executor_spec, task)
            except Exception as exc:
                task_result = TaskResult(
                    task_id=task.id,
                    pool=pool_name,
                    executor_name=executor_spec.name,
                    status="failed",
                    error=str(exc),
                    duration_ms=(time.monotonic() - task_start) * 1000.0,
                )
            finally:
                if sem:
                    sem.release()
                with progress_lock:
                    active_pools[pool_name] = max(0, active_pools.get(pool_name, 1) - 1)
                    completed_count += 1
                    elapsed_s = time.monotonic() - start_time
                    avg_per_task = elapsed_s / completed_count
                    remaining_tasks = total_tasks - completed_count
                    eta_seconds = remaining_tasks * avg_per_task
                    percent = (completed_count / total_tasks) * 100.0

                    # 1. Emit Task Completed event
                    output_str = str(task_result.output or "")[:120]
                    self.emit(
                        ForceTaskCompletedEvent(
                            force_name=self.force_name,
                            task_id=task.id,
                            pool=pool_name,
                            executor_name=executor_spec.name,
                            status=task_result.status,
                            duration_ms=task_result.duration_ms,
                            output_preview=output_str,
                            error=task_result.error,
                        )
                    )

                    # 2. Emit Progress update for UI progress bar
                    self.emit(
                        ForceProgressEvent(
                            force_name=self.force_name,
                            completed=completed_count,
                            total=total_tasks,
                            percent=percent,
                            active_pools=dict(active_pools),
                            eta_seconds=eta_seconds,
                            latest_task_id=task.id,
                            latest_pool=pool_name,
                        )
                    )

            return task_result

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(_run_single_task, t) for t in tasks]
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    results.append(
                        TaskResult(
                            task_id="unknown",
                            pool="unknown",
                            executor_name="thread_error",
                            status="failed",
                            error=str(exc),
                        )
                    )

        # Restore original task order
        result_by_id = {r.task_id: r for r in results}
        ordered_results = [result_by_id.get(t.id, TaskResult(t.id, t.pool, "unknown", "failed")) for t in tasks]
        return ordered_results

    def _dispatch_to_executor(self, spec: ExecutorSpec, task: TaskItem) -> TaskResult:
        """Executes an individual agent with task input and executor metadata."""
        agent = spec.agent
        t0 = time.monotonic()

        # Build prompt from task input and metadata
        prompt_content: str
        if isinstance(task.input, str):
            prompt_content = task.input
        elif isinstance(task.input, dict):
            # If task input dict has a dedicated prompt/comment/message field
            text = task.input.get("message") or task.input.get("prompt") or task.input.get("comment") or task.input.get("content")
            if text:
                prompt_content = str(text)
            else:
                prompt_content = f"Process item: {task.input}"
        else:
            prompt_content = str(task.input)

        # If executor has metadata (such as proxy, account, credentials), format guidance
        context_extra = []
        if spec.metadata:
            if "proxy" in spec.metadata:
                context_extra.append(f"Proxy: {spec.metadata['proxy']}")
            if "user" in spec.metadata:
                context_extra.append(f"User: {spec.metadata['user']}")

        if context_extra:
            prompt_content += f"\n[Executor Context: {', '.join(context_extra)}]"

        # Execute agent
        agent_output = agent.run(prompt_content)
        duration_ms = (time.monotonic() - t0) * 1000.0

        # Handle RunOutput or raw result
        content = getattr(agent_output, "content", str(agent_output))
        agent_status = getattr(agent_output, "status", None)
        agent_error = getattr(agent_output, "error", None)

        if agent_status == "failed" or agent_error:
            status = "failed"
            error_msg = str(agent_error) if agent_error else "Agent execution failed"
        elif getattr(agent_output, "is_paused", False):
            status = "paused"
            error_msg = None
        else:
            status = "completed"
            error_msg = None

        usage = getattr(agent_output, "usage", {}) or {}
        tokens = usage.get("total_tokens", 0) or (usage.get("input_tokens", 0) + usage.get("output_tokens", 0))

        return TaskResult(
            task_id=task.id,
            pool=spec.pool,
            executor_name=spec.name,
            status=status,
            output=content,
            error=error_msg,
            description=task.description,
            duration_ms=duration_ms,
            tokens_used=tokens,
            metadata=dict(spec.metadata),
        )
