"""Predictive intelligence engine for AgentForce batches and simulations."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any, Dict, List, Optional
from .spec import PoolConfig, TaskItem

logger = logging.getLogger(__name__)


class AIPredictionEngine:
    """Calculates completion forecasts, token/cost estimates, and bottleneck detections."""

    def __init__(
        self,
        amp_url: Optional[str] = None,
        amp_api_key: Optional[str] = None,
        default_latency_per_task_ms: float = 1200.0,
        default_tokens_per_task: int = 350,
        token_cost_per_million: float = 0.60,
    ) -> None:
        self.amp_url = (amp_url or os.environ.get("WOLFPACK_AMP_URL", "")).rstrip("/")
        self.amp_api_key = amp_api_key or os.environ.get("WOLFPACK_AMP_API_KEY", "")
        self.default_latency_per_task_ms = default_latency_per_task_ms
        self.default_tokens_per_task = default_tokens_per_task
        self.token_cost_per_million = token_cost_per_million

    def predict(
        self,
        mission: str,
        tasks: List[TaskItem],
        pools: Dict[str, PoolConfig],
    ) -> Dict[str, Any]:
        """Generates comprehensive execution predictions for a task batch."""
        total_tasks = len(tasks)
        if total_tasks == 0:
            return {
                "predicted_duration_ms": 0.0,
                "predicted_cost": 0.0,
                "predicted_tokens": 0,
                "predicted_success_rate": 1.0,
                "bottlenecks": [],
                "confidence": 1.0,
            }

        # 1. Count tasks per pool
        counts_by_pool: Dict[str, int] = {}
        for t in tasks:
            p_name = getattr(t, "pool", None) or (t.get("pool") if isinstance(t, dict) else "default")
            counts_by_pool[p_name] = counts_by_pool.get(p_name, 0) + 1

        # 2. Analyze concurrency and bottleneck per pool
        bottlenecks: List[Dict[str, Any]] = []
        pool_durations: Dict[str, float] = {}

        for pool_name, task_count in counts_by_pool.items():
            pool_config = pools.get(pool_name)
            # Available worker slots
            workers = len(pool_config.executors) if pool_config else 1
            max_concurrency = pool_config.max_concurrency if pool_config else 2
            effective_capacity = max(1, min(workers * 2, max_concurrency))

            # Number of rounds this pool needs to process its tasks
            rounds = (task_count + effective_capacity - 1) // effective_capacity
            pool_duration = rounds * self.default_latency_per_task_ms
            pool_durations[pool_name] = pool_duration

            # Flag bottleneck if a pool has disproportionately high queue
            if task_count > effective_capacity * 4:
                bottlenecks.append({
                    "pool": pool_name,
                    "queued_tasks": task_count,
                    "effective_concurrency": effective_capacity,
                    "severity": "high" if task_count > effective_capacity * 10 else "medium",
                    "suggestion": f"Add {max(1, (task_count // 4) - workers)} more workers to pool '{pool_name}' to optimize throughput.",
                })

        # Overall predicted duration is dominated by the slowest pool running in parallel
        predicted_duration_ms = max(pool_durations.values()) if pool_durations else self.default_latency_per_task_ms

        # 3. Cost and token estimations
        predicted_tokens = total_tasks * self.default_tokens_per_task
        predicted_cost = (predicted_tokens / 1_000_000.0) * self.token_cost_per_million

        # 4. Success rate projection (mild degradation if bottlenecks exist)
        penalty = min(0.08, len(bottlenecks) * 0.02)
        predicted_success_rate = max(0.90, 0.99 - penalty)

        forecast = {
            "mission": mission,
            "total_tasks": total_tasks,
            "predicted_duration_ms": round(predicted_duration_ms, 2),
            "predicted_cost": round(predicted_cost, 4),
            "predicted_tokens": predicted_tokens,
            "predicted_success_rate": round(predicted_success_rate, 3),
            "bottlenecks": bottlenecks,
            "confidence": 0.95,
        }

        # Optional: Sync to Control Plane /predictions if accessible
        if self.amp_url and self.amp_api_key:
            self._sync_to_amp_predictions(mission, forecast, counts_by_pool)

        return forecast

    def _sync_to_amp_predictions(
        self,
        mission: str,
        forecast: Dict[str, Any],
        counts_by_pool: Dict[str, int],
    ) -> None:
        """Publishes the prediction to AMP Control Plane for governance tracking."""
        try:
            url = f"{self.amp_url}/api/public/predictions"
            payload = json.dumps({
                "name": f"AgentForce: {mission[:60]}",
                "seed_summary": f"Batch of {forecast['total_tasks']} tasks across pools: {list(counts_by_pool.keys())}",
                "scenario_params": forecast,
                "personas": [
                    {"name": pool, "role": f"Executor Pool ({count} tasks)", "bias": "balanced", "expertise": "task execution"}
                    for pool, count in counts_by_pool.items()
                ],
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "X-API-Key": self.amp_api_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                pass
        except Exception as exc:
            logger.debug("Non-fatal AMP prediction registration skipped: %s", exc)
