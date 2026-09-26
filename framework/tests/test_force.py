"""Unit tests for the AgentForce mass parallel execution engine."""

import sqlite3
import time
from unittest.mock import MagicMock
import pytest

from wolfpack import Agent, tool
from wolfpack.data import DataAccessPolicy, SqlToolkit
from wolfpack.force import (
    AgentForce,
    ExecutorSpec,
    ForceCompletedEvent,
    ForcePredictionEvent,
    ForceProgressEvent,
    ForceStartedEvent,
    ForceTaskCompletedEvent,
)
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message


class EchoModel(BaseModel):
    """Deterministic model that replies with the last user message or canned answer."""

    def __init__(self, prefix: str = "Processed: ") -> None:
        self.provider = "fake"
        self.model_id = "echo-model"
        self.prefix = prefix
        self.invocations = 0

    def invoke(self, messages, tools=None) -> ModelResponse:
        self.invocations += 1
        user_msgs = [m.get("content") for m in messages if m.get("role") == "user"]
        last_msg = user_msgs[-1] if user_msgs else "ok"
        return ModelResponse(
            message=Message(role="assistant", content=f"{self.prefix}{last_msg[:60]}"),
            usage={"input_tokens": 12, "output_tokens": 8},
        )


def test_agent_force_basic_execution():
    coord_model = EchoModel(prefix="Synthesis: ")
    worker_model = EchoModel(prefix="Handled: ")

    coordinator = Agent(name="Lead", model=coord_model)
    worker_a = Agent(name="WorkerA", model=worker_model)
    worker_b = Agent(name="WorkerB", model=worker_model)

    force = AgentForce(coordinator=coordinator, max_workers=4)
    force.add_executor("exec-1", worker_a, pool="pool_alpha", max_concurrency=2)
    force.add_executor("exec-2", worker_b, pool="pool_beta", max_concurrency=2)

    data = [
        {"id": "t1", "prompt": "Task Alpha 1", "pool": "pool_alpha"},
        {"id": "t2", "prompt": "Task Alpha 2", "pool": "pool_alpha"},
        {"id": "t3", "prompt": "Task Beta 1", "pool": "pool_beta"},
    ]

    result = force.run(mission="Execute batch", data=data)

    assert result.status == "completed"
    assert result.total_tasks == 3
    assert result.completed_tasks == 3
    assert result.failed_tasks == 0
    assert "pool_alpha" in result.pool_summaries
    assert "pool_beta" in result.pool_summaries
    assert result.pool_summaries["pool_alpha"].completed_tasks == 2
    assert result.pool_summaries["pool_beta"].completed_tasks == 1
    assert len(result.tasks) == 3
    assert "Synthesis:" in result.synthesis


def test_agent_force_streaming_progress_and_prediction():
    coord_model = EchoModel(prefix="Synthesis: ")
    worker_model = EchoModel(prefix="Worker reply: ")

    coordinator = Agent(name="Coord", model=coord_model)
    worker = Agent(name="Worker", model=worker_model)

    force = AgentForce(coordinator=coordinator, max_workers=2)
    force.add_executor("w1", worker, pool="default", max_concurrency=2)

    data = [{"id": f"t_{i}", "prompt": f"Item {i}"} for i in range(5)]

    events = list(force.run("Process 5 items", data=data, stream=True))

    started = [e for e in events if isinstance(e, ForceStartedEvent)]
    predictions = [e for e in events if isinstance(e, ForcePredictionEvent)]
    progress = [e for e in events if isinstance(e, ForceProgressEvent)]
    completed_tasks = [e for e in events if isinstance(e, ForceTaskCompletedEvent)]
    force_completed = [e for e in events if isinstance(e, ForceCompletedEvent)]

    assert len(started) == 1
    assert started[0].total_tasks == 5
    assert len(predictions) == 1
    assert predictions[0].predicted_tokens > 0
    assert len(progress) == 5  # 1 per completed task
    assert progress[-1].percent == 100.0
    assert progress[-1].completed == 5
    assert len(completed_tasks) == 5
    assert len(force_completed) == 1
    assert force_completed[0].completed == 5


def test_agent_force_with_sql_toolkit():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE orders (id TEXT, customer TEXT, pool TEXT);")
    conn.execute("INSERT INTO orders VALUES ('ord_1', 'Alice', 'fast_lane');")
    conn.execute("INSERT INTO orders VALUES ('ord_2', 'Bob', 'fast_lane');")
    conn.execute("INSERT INTO orders VALUES ('ord_3', 'Charlie', 'normal_lane');")
    conn.commit()

    policy = DataAccessPolicy(source_id="shop", allowed_tables={"orders"})
    toolkit = SqlToolkit(conn, policy=policy)

    coordinator = Agent(name="Lead", model=EchoModel())
    worker_fast = Agent(name="FastWorker", model=EchoModel("Fast: "))
    worker_normal = Agent(name="NormalWorker", model=EchoModel("Normal: "))

    force = AgentForce(coordinator=coordinator, max_workers=4)
    force.add_executor("wf", worker_fast, pool="fast_lane")
    force.add_executor("wn", worker_normal, pool="normal_lane")

    result = force.run("Process SQL orders", toolkit=toolkit, policy=policy)

    assert result.total_tasks == 3
    assert result.completed_tasks == 3
    assert result.pool_summaries["fast_lane"].completed_tasks == 2
    assert result.pool_summaries["normal_lane"].completed_tasks == 1


def test_agent_force_instagram_proxy_metadata():
    @tool
    def post_instagram(comment_id: str, proxy: str, account: str) -> str:
        return f"OK: posted to {comment_id} via {proxy} as {account}"

    model = EchoModel("IG Handled: ")
    worker_br = Agent(name="InstagramBR", model=model, tools=[post_instagram])

    coordinator = Agent(name="CampaignLead", model=EchoModel("Campaign Synthesis: "))
    force = AgentForce(coordinator=coordinator, max_workers=2)

    force.add_executor(
        name="br-bot-1",
        agent=worker_br,
        pool="instagram_br",
        max_concurrency=2,
        metadata={"proxy": "http://br-proxy:8080", "user": "brand_br"},
    )

    comments = [
        {"id": "c1", "comment": "Adorei a publicação!", "pool": "instagram_br"},
        {"id": "c2", "comment": "Qual o preço?", "pool": "instagram_br"},
    ]

    result = force.run("Responder comentários do Instagram", data=comments)

    assert result.total_tasks == 2
    assert result.completed_tasks == 2
    task1 = result.tasks[0]
    assert task1.metadata.get("proxy") == "http://br-proxy:8080"
    assert task1.metadata.get("user") == "brand_br"
    assert "br-bot-1" == task1.executor_name


def test_agent_force_with_mock_data_source():
    class MockConcept:
        def __init__(self, id: str, title: str, content: str):
            self.id = id
            self.title = title
            self.content = content
            self.tags = ["policy", "guideline"]

    class MockBundle:
        def search(self, query: str, limit: int = 10):
            return [
                MockConcept("c1", "Reembolso", "Diretrizes de reembolso e estorno."),
                MockConcept("c2", "Envio", "Prazos de entrega expressa."),
            ]

    bundle = MockBundle()
    coordinator = Agent(name="Lead", model=EchoModel())
    worker = Agent(name="SupportAgent", model=EchoModel("Support: "))

    force = AgentForce(coordinator=coordinator, max_workers=2)
    force.add_executor("supp-1", worker, pool="default")

    result = force.run("Revisar políticas", data_source=bundle)

    assert result.total_tasks == 2
    assert result.completed_tasks == 2
    assert any("Reembolso" in str(t.description) for t in result.tasks)


def test_agent_force_with_partial_failure():
    class FailingModel(BaseModel):
        def invoke(self, messages, tools=None) -> ModelResponse:
            raise RuntimeError("Temporary network timeout")

    good_worker = Agent(name="GoodWorker", model=EchoModel("Success: "))
    bad_worker = Agent(name="BadWorker", model=FailingModel())
    coordinator = Agent(name="Lead", model=EchoModel())

    force = AgentForce(coordinator=coordinator, max_workers=4)
    force.add_executor("good", good_worker, pool="good_pool")
    force.add_executor("bad", bad_worker, pool="bad_pool")

    tasks = [
        {"id": "g1", "prompt": "Task 1", "pool": "good_pool"},
        {"id": "b1", "prompt": "Task 2", "pool": "bad_pool"},
    ]

    result = force.run("Mixed batch", data=tasks)

    assert result.total_tasks == 2
    assert result.completed_tasks == 1
    assert result.failed_tasks == 1
    assert result.status == "partial"
    assert result.pool_summaries["good_pool"].completed_tasks == 1
    assert result.pool_summaries["bad_pool"].failed_tasks == 1


def test_agent_force_bottleneck_detection():
    coordinator = Agent(name="Lead", model=EchoModel())
    worker = Agent(name="Worker", model=EchoModel())

    force = AgentForce(coordinator=coordinator, max_workers=2)
    force.add_executor("w1", worker, pool="overloaded_pool", max_concurrency=1)

    # 15 tasks for a pool with concurrency 1
    tasks = [{"id": f"t_{i}", "prompt": f"Task {i}", "pool": "overloaded_pool"} for i in range(15)]

    prediction = force.prediction_engine.predict("Check bottlenecks", tasks, force.pools)
    assert len(prediction["bottlenecks"]) > 0
    bottleneck = prediction["bottlenecks"][0]
    assert bottleneck["pool"] == "overloaded_pool"
    assert bottleneck["queued_tasks"] == 15
    assert "suggestion" in bottleneck
