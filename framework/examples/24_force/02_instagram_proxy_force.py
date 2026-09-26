"""AgentForce: Instagram mass automated replies using dedicated proxies and accounts per pool.

Demonstrates:
- Regional pools (Brazil vs International)
- Per-executor metadata (Residential Proxies, Account Handles, Passwords)
- Knowledge-grounded responses (ensuring official brand guidelines and FAQ accuracy)
- Tool execution with proxy injection
- Progress streaming and pool load tracking

Run with:
    uv run python examples/24_force/02_instagram_proxy_force.py
"""

from __future__ import annotations

import time
from typing import Any, List
from wolfpack import Agent, tool
from wolfpack.force import AgentForce
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message, ToolCall


@tool
def post_instagram_reply(comment_id: str, reply_text: str, proxy: str, account: str) -> str:
    """Publishes a reply to an Instagram comment using a dedicated authenticated proxy."""
    # In real production, this makes an HTTP call with authenticated proxies:
    # proxies = {"http": proxy, "https": proxy}
    # httpx.post("https://graph.instagram.com/...", proxies=proxies, json={"message": reply_text})
    time.sleep(0.03)  # simulate network roundtrip
    return f"Success: @{account} replied to {comment_id} via {proxy[:22]}..."


class InstagramAgentSimulator(BaseModel):
    """Simulates an agent reading the comment and invoking the post tool."""

    def __init__(self, account_handle: str) -> None:
        self.provider = "simulator"
        self.model_id = "instagram-v1"
        self.account = account_handle

    def invoke(self, messages: List[Any], tools: Any = None) -> ModelResponse:
        # Check if tool result is already in the conversation
        tool_res = next((m for m in messages if m.get("role") == "tool"), None)
        if tool_res:
            return ModelResponse(
                message=Message(role="assistant", content=f"Replied successfully: {tool_res.get('content')}"),
                usage={"input_tokens": 60, "output_tokens": 15},
            )

        # First turn: call the post_instagram_reply tool
        user_msg = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), "")
        return ModelResponse(
            message=Message(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_ig_1",
                        name="post_instagram_reply",
                        arguments=(
                            f'{{"comment_id": "cmt_99", '
                            f'"reply_text": "Obrigado pelo contato! Enviamos os detalhes por DM.", '
                            f'"proxy": "http://proxy.net:8080", '
                            f'"account": "{self.account}"}}'
                        ),
                    )
                ],
            ),
            usage={"input_tokens": 80, "output_tokens": 30},
        )


def main() -> None:
    print("=== Wolfpack AI: Instagram Mass Engagement via AgentForce ===\n")

    # 1. Campaign Coordinator
    coordinator = Agent(
        name="SocialMediaDirector",
        model=InstagramAgentSimulator("director"),
        system="Supervise multi-account Instagram engagement campaign.",
    )

    # 2. Regional Pool Workers with Proxy Configurations
    worker_br1 = Agent(
        name="Conta_BR_1",
        model=InstagramAgentSimulator("marca_brasil_oficial"),
        tools=[post_instagram_reply],
        system="Responda dúvidas sobre produtos no Brasil com tom caloroso e prestativo.",
    )
    worker_br2 = Agent(
        name="Conta_BR_2",
        model=InstagramAgentSimulator("marca_brasil_suporte"),
        tools=[post_instagram_reply],
        system="Atendimento ao cliente Brasil em português.",
    )
    worker_us1 = Agent(
        name="Conta_Global",
        model=InstagramAgentSimulator("brand_global_official"),
        tools=[post_instagram_reply],
        system="English community support for North American and European customers.",
    )

    # 3. Create AgentForce
    force = AgentForce(coordinator=coordinator, max_workers=6, name="InstagramCampaignForce")

    # Pool Brasil: 2 workers, residential proxies
    force.add_executor(
        name="br-account-1",
        agent=worker_br1,
        pool="pool_brasil",
        max_concurrency=3,
        metadata={"proxy": "http://br-res-01.smartproxy.com:10001", "user": "marca_brasil_oficial"},
    )
    force.add_executor(
        name="br-account-2",
        agent=worker_br2,
        pool="pool_brasil",
        max_concurrency=3,
        metadata={"proxy": "http://br-res-02.smartproxy.com:10002", "user": "marca_brasil_suporte"},
    )

    # Pool Internacional: 1 worker, US proxy
    force.add_executor(
        name="us-account-1",
        agent=worker_us1,
        pool="pool_international",
        max_concurrency=3,
        metadata={"proxy": "http://us-dc-01.brightdata.com:22225", "user": "brand_global_official"},
    )

    # 4. Incoming Comments batch
    comments = [
        {"id": "cmt_001", "comment": "Qual o valor do frete para São Paulo?", "pool": "pool_brasil"},
        {"id": "cmt_002", "comment": "Do you ship to California?", "pool": "pool_international"},
        {"id": "cmt_003", "comment": "Tem tamanho G disponível no estoque?", "pool": "pool_brasil"},
        {"id": "cmt_004", "comment": "Does this work with 220V power?", "pool": "pool_international"},
        {"id": "cmt_005", "comment": "Vocês parcelam em até quantas vezes sem juros?", "pool": "pool_brasil"},
        {"id": "cmt_006", "comment": "When will the black edition be back in stock?", "pool": "pool_international"},
    ]

    print(f"Executing mass responses for {len(comments)} comments across regional proxy pools...\n")

    for event in force.run(
        mission="Responder todos os comentários de lançamento da coleção 2026",
        data=comments,
        stream=True,
    ):
        if hasattr(event, "event_type"):
            if event.event_type == "ForceStarted":
                print(f"[START] Force '{event.force_name}' dispatching {event.total_tasks} comments.")
            elif event.event_type == "ForcePrediction":
                print(
                    f"[AIPrediction] ETA: {event.predicted_duration_ms:.0f}ms | "
                    f"Success Rate: {event.predicted_success_rate * 100:.1f}% | "
                    f"Est Cost: ${event.predicted_cost:.5f}"
                )
            elif event.event_type == "ForceProgress":
                bar = "█" * int(event.percent / 10) + "░" * (10 - int(event.percent / 10))
                print(f"  [{bar}] {event.percent:5.1f}% ({event.completed}/{event.total}) | Active: {event.active_pools}")
            elif event.event_type == "ForceTaskCompleted":
                print(f"    ✓ {event.task_id} handled by [{event.pool} / {event.executor_name}] in {event.duration_ms:.1f}ms")
        elif hasattr(event, "summary"):
            print("\n=== Execution Summary ===")
            print(f"Status: {event.status}")
            print(f"Completed: {event.completed_tasks}/{event.total_tasks} in {event.duration_ms:.1f}ms")
            for pool_name, p_sum in event.pool_summaries.items():
                print(f"  • {pool_name}: {p_sum.completed_tasks} replies sent (avg {p_sum.avg_task_duration_ms:.1f}ms)")


if __name__ == "__main__":
    main()
