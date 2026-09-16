"""22 - Skills: always-active and contextual Agent capabilities.

Run:
    uv run python examples/22_skills/01_skill_basics.py
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, Skill
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message, ToolCall


class RiskDemoModel(BaseModel):
    """Deterministic model that demonstrates contextual skill activation."""

    provider = "demo"
    model_id = "risk-demo"

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, messages, tools=None) -> ModelResponse:
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                message=Message(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="activate-risk",
                            name="activate_skill",
                            arguments='{"name": "risk-analysis"}',
                        )
                    ],
                )
            )
        return ModelResponse(
            message=Message(
                role="assistant",
                content="Risk: high. Probability: medium. Impact: high. Mitigation: add a rollout gate.",
            )
        )


def main() -> None:
    agent = Agent(
        name="project-advisor",
        model=RiskDemoModel(),
        skills=[
            Skill(
                name="clear-writing",
                content="Use concise language and state assumptions explicitly.",
            ),
            Skill(
                name="risk-analysis",
                content="Use a probability by impact matrix. Classify risk as low, medium, high, or critical.",
                context="Activate when the user asks for project or financial risk analysis.",
            ),
        ],
    )

    result = agent.run("What is the delivery risk for this project?")

    print("=== SYSTEM PROMPT ===")
    print(agent.system_prompt)
    print("\n=== TOOL CALLS ===")
    print(result.tool_calls)
    print("\n=== ANSWER ===")
    print(result.content)


if __name__ == "__main__":
    main()
