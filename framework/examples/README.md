# Wolfpack Examples

Fully-working, runnable examples for the wolfpack framework. Every script in these
folders has been executed end-to-end against real model providers (OpenAI, Anthropic
and Ollama) using the API keys loaded from `~/.zshrc`.

```
examples/
  01_basic/            # minimal agents, chat with memory, streaming events
  02_tools/            # tool-calling, Toolkit, multi-provider, HITL confirmation
  03_rag/              # Retrieval-Augmented Generation with real embeddings
  04_teams/            # multi-agent orchestration (coming in a later milestone)
   05_observability/    # OTel spans + AMP Control Plane ingestion
   10_privacy/          # PII-safe telemetry with data subject context
   12_hardening/        # production-safe agent flow with local AMP verification
   18_coding_agent/     # bounded filesystem, command, and Git primitives
```

## Prereqs

- Python 3.10+ with `uv` (see the framework `README`).
- At least one provider key sourced from `~/.zshrc`:
  - `OPENAI_API_KEY` (OpenAI: gpt-4o-mini / text-embedding-3-small)
  - `ANTHROPIC_API_KEY` (Claude: claude-haiku-4-5 / claude-sonnet-4-5)
  - `OLLAMA_BASE_URL` (remote Ollama: qwen3-coder / embeddinggemma)

`get_model_from_env()` picks a provider automatically by key availability.

## Running

From inside `framework/`:

```bash
# Make sure the framework venv is up to date
uv sync --extra test

# Basic
uv run python examples/01_basic/01_hello_agent.py
uv run python examples/01_basic/02_chat_with_memory.py
uv run python examples/01_basic/03_stream_events.py

# Tools
uv run python examples/02_tools/01_tool_basics.py
uv run python examples/02_tools/02_toolkit_example.py
uv run python examples/02_tools/03_multi_provider.py "anthropic:claude-haiku-4-5"
uv run python examples/02_tools/04_requires_confirmation.py

# RAG
uv run python examples/03_rag/01_rag_memory.py
uv run python examples/03_rag/02_rag_from_file.py
uv run python examples/03_rag/03_rag_provider_choice.py

# Observability
uv run python examples/05_observability/01_otel_console.py
uv run python examples/05_observability/02_amp_observer.py     # needs AMP at :8200
uv run python examples/05_observability/03_stream_events.py

# Teams: deterministic mesh, tool, and HITL approval telemetry
uv run python examples/07_teams/03_deterministic_telemetry_hitl.py

# Privacy
uv run python examples/10_privacy/01_pii_safe_telemetry.py

# Hardening (self-contained local AMP-like ingestion sink)
uv run python examples/12_hardening/01_production_flow.py

# Coding agent primitives (provider-free)
uv run python examples/18_coding_agent/01_deterministic_primitives.py
```

Most scripts accept an optional CLI argument (e.g. a custom prompt or a model spec).

## Observability flow

`examples/05_observability/02_amp_observer.py` sends every run to the Control Plane:

1. Start the AMP backend (`control-plane/run.sh`) — postgres/redis/qdrant/minio + :8200.
2. Run the example; it streams the trace (steps, LLM calls, tool calls, tokens).
3. Open the Control Plane UI to inspect the span tree per run.

The observer buffers events and never crashes if the backend is down.
