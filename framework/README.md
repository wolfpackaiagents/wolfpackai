# Wolfpack AI

Wolfpack AI is a Python framework for building production-ready artificial
intelligence agents. It
combines agent execution, tool calling, retrieval-augmented generation (RAG),
memory, human approval flows, guardrails, and OpenTelemetry observability in a
single developer-focused library.

Every agent run can emit structured traces for model calls, tool executions,
token usage, latency, and cost. The optional Wolfpack Agent Management Platform
(AMP) receives those traces and provides an operational interface for
monitoring, governance, evaluation, and agent lifecycle management.

## Install

Wolfpack AI requires Python 3.10 or later.

```bash
pip install wolfpackai
```

The published package is named `wolfpackai`; Python imports remain under the
stable `wolfpack` module.

Install optional integrations as needed:

```bash
pip install "wolfpackai[qdrant]"    # Qdrant vector database
pip install "wolfpackai[pgvector]"  # PostgreSQL vector search
pip install "wolfpackai[knowledge]" # Document readers
pip install "wolfpackai[mcp]"       # Model Context Protocol client
```

## Quick Start

Configure a supported model provider, then create an agent and attach typed
Python functions as tools.

```bash
export OPENAI_API_KEY="..."
```

```python
from wolfpack import Agent, get_model_from_env, tool


@tool
def get_weather(city: str) -> str:
    """Return the current weather for a city.

    Args:
        city: City name.
    """
    return f"{city}: 22 C, cloudy."


agent = Agent(
    name="Weather assistant",
    model=get_model_from_env(),
    tools=[get_weather],
)

result = agent.run("What is the weather in Lisbon?")
print(result.content)
```

## Capabilities

- Agent loop with synchronous execution, asynchronous execution, streaming,
  events, and typed tool calling.
- Model adapters for OpenAI, Anthropic, Google Gemini, Ollama, Groq, and
  OpenAI-compatible providers.
- Knowledge retrieval with chunking, embeddings, and memory, Qdrant, or
  PostgreSQL vector stores.
- Persistent session memory with in-memory and SQLite stores.
- Guardrails for personally identifiable information, prompt injection, and
  tool allowlists.
- Durable human-in-the-loop approvals, including pause and resume workflows.
- Pydantic-based structured output with validation and retry feedback.
- Deterministic workflows with directed acyclic graph execution, conditions,
  and retries.
- Multi-agent teams with delegation, routing, broadcast, and task modes.
- Model Context Protocol client support for external tool servers.
- Evaluation runners, score publishing, scheduled tasks, and channel adapters
  for Telegram, Slack, Discord, and web chat.

## Observability

Wolfpack AI emits OpenTelemetry spans using the generative artificial
intelligence semantic conventions. Set an Agent Management Platform endpoint
and project Application Programming Interface key to send runs to the control
plane:

```bash
export WOLFPACK_AMP_URL="http://localhost:8000"
export WOLFPACK_AMP_API_KEY="pk-...:secret"
```

The Agent Management Platform stores traces and provides dashboards, trace
exploration, session views, approvals, guardrail settings, evaluation scores,
privacy controls, schedules, runtime mesh monitoring, and channel management.

## Development

Clone the repository and install the development dependencies with uv:

```bash
git clone https://github.com/wolfpackaiagents/wolfpackai.git
cd wolfpackai/framework
uv sync --extra test --group dev
pytest
```

Examples are organized by capability in `examples/`, including basic agents,
tools, knowledge retrieval, observability, human approval, workflows, teams,
and Model Context Protocol integrations.

## Author

Created by [Álvaro Brito](https://www.linkedin.com/in/alvarogomes/).

## License

Wolfpack AI is released under the MIT License.
