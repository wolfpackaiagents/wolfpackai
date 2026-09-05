"""04 - requires_confirmation: HITL-gated tools.

The `@tool` decorator accepts `requires_confirmation=True`. When the model calls
such a tool, the framework does NOT execute it: `FunctionCall.execute()` short-
circuits and returns a `FunctionExecutionResult` with status `tool_confirmation`
instead of running the destructive side effect.

This is a framework capability intended for human-in-the-loop (HITL) flows: a
production deployment inspects that status and routes the call to a confirmation
gate before anything irreversible happens. Because the tool is not executed, the
result is also not recorded in `output.tool_calls` (only successful calls land
there).

Run:
    uv run python examples/02_tools/04_requires_confirmation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, get_model_from_env, tool
from wolfpack.tools.function import FunctionCall


@tool(requires_confirmation=True)
def send_email(recipient: str, subject: str, body: str) -> str:
    """Sends an email; requires human confirmation before running.

    Args:
        recipient: the email address of the receiver.
        subject: the email subject line.
        body: the email body text.
    """
    # This function is never executed by the agent run: the confirmation gate
    # returns before reaching this point.
    return f"Email sent to {recipient}"


def demonstrate_confirmation_gate() -> None:
    """Show that the framework defers execution of gated tools."""
    func = getattr(send_email, "function")
    call = func.get_function_call("call_1", {"recipient": "bob@example.com", "subject": "Hi", "body": "Hello"})
    result = call.execute()
    print("  FunctionExecutionResult:")
    print(f"    status : {result.status!r}  (expected 'tool_confirmation')")
    print(f"    result : {result.result!r}  (not executed, so no side effect)")

    # NOTE: confirmation gating is a framework capability. A wrapper/agent loop
    # above the framework inspects `status` and decides how to proceed (ask the
    # human, wait for approval, queue for review) before executing for real.


def main() -> None:
    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )

    agent = Agent(
        name="EmailBot",
        model=model,
        role="An assistant that helps draft and send emails",
        goal="Use the email tools whenever the user asks you to contact someone.",
        backstory="A wolfpack agent designed to draft and send email on behalf of the user, always asking for confirmation first.",
        tools=[send_email],
    )

    request = "Send an email to bob@example.com with subject 'Hello' and body 'Hope you are well'."
    print(f"Model: {model.model_id}\nAgent: {agent.id}\n")
    print(f"Prompt: {request}\n")

    print("=== Direct FunctionCall inspection ===")
    print(f"  send_email requires_confirmation = {send_email.function.requires_confirmation}")
    demonstrate_confirmation_gate()
    print()

    output = agent.run(request)

    print("=== AGENT RUN ===")
    print("Final content:")
    print("  ", output.content)
    print()
    print("Executed tool_calls:", output.tool_calls, "(empty means no tool was really executed)")
    print()
    print("=== TOOL MESSAGE IN CONVERSATION ===")
    for msg in output.messages:
        if getattr(msg, "role", None) == "tool":
            print(f"  tool name={msg.name!r} content={msg.content!r}")
    print()
    if output.failed:
        print("Run FAILED:", output.error)
    else:
        print("Run completed. The gated tool never produced a real side effect.")


if __name__ == "__main__":
    main()