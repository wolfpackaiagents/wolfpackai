# Wolfpack AI

Wolfpack AI is a Python framework and operational platform for building,
running, and governing production-ready artificial intelligence agents. The
repository contains the `wolfpackai` package and the Agent Management Platform
(AMP), a control plane for observing and operating agent workloads.

## Repository Structure

```text
framework/     Python package published as wolfpackai
control-plane/ AMP backend and web interface
docker/        Development and production Docker Compose files
website/       Project documentation website
```

## Framework

Install the framework from the Python Package Index:

```bash
pip install wolfpackai
```

The distribution is named `wolfpackai`; imports use the stable `wolfpack`
module.

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

Key capabilities include typed tool calling, retrieval-augmented generation
(RAG), persistent memory, guardrails, human approval flows, structured output,
deterministic workflows, multi-agent teams, evaluation runners, scheduled
tasks, and Model Context Protocol client support.

## Observability and Control Plane

Each agent run emits OpenTelemetry spans for model calls, tool executions,
latency, tokens, and cost. Configure the control plane endpoint and project
Application Programming Interface key to forward those traces to AMP:

```bash
export WOLFPACK_AMP_URL="http://localhost:8000"
export WOLFPACK_AMP_API_KEY="pk-...:secret"
```

AMP provides trace exploration, dashboards, sessions, approvals, evaluations,
guardrails, privacy controls, runtime mesh monitoring, scheduling, and channel
management. The frontend is available in English and Brazilian Portuguese.

## Run Locally

Start the backend infrastructure and application:

```bash
cd control-plane
./run.sh
```

Start the frontend in a separate terminal:

```bash
cd control-plane/frontend
npm install
npm run dev
```

For a complete container deployment, set the required environment variables and
run:

```bash
docker compose -f docker/docker-compose.production.yml up -d
```

## Development

```bash
cd framework
uv sync --extra test --group dev
pytest
```

Examples are organized by capability in `framework/examples/`.

## Author

Created by [Álvaro Brito](https://www.linkedin.com/in/alvarogomes/).

## License

Wolfpack AI is released under the MIT License.
