"""HITL with a real model: pause before a sensitive tool, then approve and resume.

This example runs against a real LLM (auto-picked provider). The agent has an
`email` tool flagged `requires_confirmation=True`; when the model calls it, the
run PAUSES instead of executing. We then resolve the approval via the store and
`continue_run()`.

Resume is local (SQLite by default). Set `WOLFPACK_AMP_URL` to also publish the
approval to the Control Plane.

    uv run python examples/06_hitl_guardrails/01_hitl_approve.py "Send an email to john@acme.com"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, RunStatus, get_model_from_env, tool
from wolfpack.run.approval_store import default_store


@tool(requires_confirmation=True)
def send_email(to: str, subject: str, body: str) -> str:
    """Sends an email (requires human approval before executing).

    Args:
        to: recipient address.
        subject: the subject line.
        body: the message body.
    """
    return f"EMAIL SENT to {to}"


def main() -> None:
    prompt = " ".join(sys.argv[1:]) or "Send an email to john@acme.com about the Q3 report."
    store = default_store()
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )
    agent = Agent(
        name="Secretary",
        model=get_model_from_env(),
        role="A careful assistant that never sends email without approval",
        goal="When the user asks to send an email, you MUST call the send_email tool (which waits for approval) rather than drafting a reply.",
        backstory="Every email send is a privileged action that pauses for a human to approve.",
        tools=[send_email],
        approval_store=store,
    )

    print("=" * 60)
    print("HITL - PIANO BEFORE SENDING EMAIL")
    print("=" * 60)
    out = agent.run(prompt)

    if out.is_paused:
        print(f"Run paused: {out.run_id}")
        for r in out.active_requirements:
            print(f"  approval: {r.approval_id}")
            print(f"  tool    : {r.tool_name} -> {r.tool_arguments}")
            print(f"  gate    : {r.requirement}")
            # simulate a human approving via the store
            store.resolve(out.run_id, r.approval_id, "approve", resolved_by="human@example")
        print("\nApproving and resuming...")
        resume = agent.continue_run(out.run_id)
        print("\nRESUMED -> status:", resume.status)
        print("answer:", resume.content)
        status = RunStatus.COMPLETED if resume.status == RunStatus.COMPLETED.value else "?"
        print("completed:", status)
    else:
        print("The model did not request the gated tool. Run finished directly:")
        print(out.content)


if __name__ == "__main__":
    main()