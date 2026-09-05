"""The Agent: the central abstraction of the framework.

Borrows patterns from agno (run/arun contract), crewAI (role/goal/backstory prompt)
and vercel (step loop). The run pipeline:

    [pre_hooks/guardrails] -> system + user -> model.invoke() -> tool loops ->
    [approval gate / HITL pause] -> [post_hooks] -> output_schema validation/retry

Capabilities built-in:
  - Tool calling loop with per-step/span telemetry.
  - Human-in-the-loop: tools flagged `requires_confirmation` / `requires_user_input`
    pause the run; requirements are persisted via an ApprovalStore (local SQLite by
    default, AMP optional). `agent.continue_run()` resumes after resolution.
  - Guardrails: `pre_hooks` / `post_hooks` (BaseGuardrail runs synchronously,
    non-guardrail hooks in background), PII masking, prompt-injection shield.
  - Structured output: `output_schema` (Pydantic) with post-generation parse +
    optional retry via feedback.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Union

from ..guardrails.base import BaseGuardrail, GuardrailError, GuardrailResult, InputCheckError, OutputCheckError, PIIGuardrail
from ..memory import SessionMemory, SessionStore, SQLiteSessionStore
from ..models.base import BaseModel
from ..models.message import Message, ToolCall
from ..models.response import RunOutput
from ..run.approval_store import ApprovalStore, default_store
from ..run.requirement import RunRequirement, RunStatus
from ..tools.function import Function, FunctionCall
from ..tools.toolkit import Toolkit
from .events import (
    BaseRunEvent,
    RunCompletedEvent,
    RunContentEvent,
    RunFailedEvent,
    RunStartedEvent,
    RunStepEvent,
    RunToolEvent,
)

MAX_STRUCTURED_RETRIES = 3


def _extract_function(obj: Any) -> Optional[Function]:
    if isinstance(obj, Function):
        return obj
    fn = getattr(obj, "function", None)
    if isinstance(fn, Function):
        return fn
    if callable(obj):
        return Function(
            name=getattr(obj, "__name__", "anon"),
            description=getattr(obj, "__doc__", "") or "",
            entrypoint=obj,
        )
    return None


def _normalize_tools(tools: Sequence[Any]) -> Dict[str, Function]:
    out: Dict[str, Function] = {}
    for t in tools or []:
        if isinstance(t, Toolkit):
            out.update(t.functions)
        else:
            fn = _extract_function(t)
            if fn is not None:
                out[fn.name] = fn
    return out


def _merge_usage(dst: Dict[str, int], src: Dict[str, Any]) -> None:
    for k, v in (src or {}).items():
        try:
            dst[k] = dst.get(k, 0) + int(v or 0)
        except (TypeError, ValueError):
            pass


def _json_dumps(data: Any) -> str:
    import json

    return json.dumps(data, default=str)


def _message_from_dict(data: Dict[str, Any]) -> Message:
    """Rebuild a Message from the provider-shaped payload stored in a checkpoint."""
    values = dict(data)
    raw_calls = values.pop("tool_calls", [])
    calls = [
        ToolCall(
            id=call.get("id"),
            name=call.get("name") or call.get("function", {}).get("name"),
            arguments=call.get("arguments") or call.get("function", {}).get("arguments", "{}"),
        )
        for call in raw_calls
    ]
    return Message(**values, tool_calls=calls)


@dataclass
class Agent:
    name: str
    model: BaseModel
    system: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None
    backstory: Optional[str] = None
    tools: List[Any] = field(default_factory=list)
    knowledge: Any = None
    telemetry: Any = None
    pre_hooks: List[Any] = field(default_factory=list)
    post_hooks: List[Any] = field(default_factory=list)
    pii_guardrail: Optional[Union[bool, PIIGuardrail]] = False
    prompt_injection_guardrail: bool = False
    tool_allowlist: Optional[List[str]] = None
    output_schema: Optional[Any] = None
    structured_retries: int = MAX_STRUCTURED_RETRIES
    approval_store: Optional[ApprovalStore] = None
    session_id: Optional[str] = None
    session_store: Optional[SessionStore] = None
    disable_hitl: bool = False
    max_iterations: int = field(default=20)
    description: Optional[str] = None
    instructions: Optional[List[str]] = None

    def __post_init__(self):
        self.id = "agent_" + uuid.uuid4().hex[:8]
        self.run_id = "run_" + uuid.uuid4().hex
        self._tool_map = _normalize_tools(self.tools)
        if self.knowledge is not None:
            from ..tools.factory import create_knowledge_search_tool
            k_tool = create_knowledge_search_tool(self.knowledge)
            self._tool_map[k_tool.name] = k_tool
        self._resolved_store = None
        self._last_run_output: Optional[RunOutput] = None
        self._apply_guardrail_defaults()

    def _apply_guardrail_defaults(self) -> None:
        hooks: List[Any] = []
        if self.pii_guardrail is True:
            self.pii_guardrail = PIIGuardrail(mode="mask")
        if isinstance(self.pii_guardrail, PIIGuardrail) and self.pii_guardrail not in self.pre_hooks:
            hooks.append(self.pii_guardrail)
        if self.prompt_injection_guardrail:
            from ..guardrails.base import PromptInjectionGuardrail

            if not any(isinstance(h, PromptInjectionGuardrail) for h in self.pre_hooks):
                hooks.append(PromptInjectionGuardrail())
        if self.tool_allowlist:
            from ..guardrails.base import ToolAllowlistGuardrail

            hooks.append(ToolAllowlistGuardrail(allowed=self.tool_allowlist))
        self.pre_hooks = list(self.pre_hooks) + hooks

    @property
    def store(self) -> ApprovalStore:
        if self._resolved_store is None:
            self._resolved_store = self.approval_store or default_store()
        return self._resolved_store

    @property
    def system_prompt(self) -> str:
        parts: List[str] = []
        if self.system:
            parts.append(self.system)
        else:
            lines: List[str] = []
            if self.role:
                lines.append(f"Your role is: {self.role}")
            if self.goal:
                lines.append(f"Your goal is: {self.goal}")
            if self.backstory:
                lines.append(f"Context: {self.backstory}")
            lines.append(
                "You are an AI agent built with wolfpack. Respond precisely and use "
                "the available tools when they help with the task."
            )
            parts.append("\n".join(lines))
        if self.instructions:
            parts.append("Instructions:\n" + "\n".join(f"- {i}" for i in self.instructions))
        if self._tool_map:
            names = ", ".join(self._tool_map.keys())
            parts.append(f"Tools available: {names}. Their arguments must be passed as JSON.")
        if self.output_schema is not None:
            try:
                schema_json = self.output_schema.model_json_schema()
                parts.append(f"Your final reply MUST be valid JSON matching this schema: {schema_json}.")
            except Exception:
                parts.append("Your final reply MUST be valid JSON.")
        return "\n\n".join(parts)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [f.get_tool_schema() for f in self._tool_map.values()]

    def _build_conversation(
        self, message: Optional[Union[str, List[Dict[str, Any]]]], messages: Optional[List[Dict[str, Any]]]
    ) -> List[Message]:
        if messages is not None:
            return [Message(**m) for m in messages]
        return [Message(role="user", content=str(message))]

    # ------------------------------------------------------------ hooks/guardrails

    def _run_pre_hooks(self, run_input: Any) -> Any:
        """Run guardrails synchronously; PII mask may replace the input."""
        current = run_input
        for hook in self.pre_hooks:
            if isinstance(hook, BaseGuardrail):
                result = hook.check(current)
                if not result.success:
                    raise InputCheckError(result.error or "Input blocked by guardrail.")
                if result.result is not None and isinstance(hook, PIIGuardrail) and hook.mode == "mask":
                    current = result.result  # masked input replaces the payload
            elif callable(hook):
                res = hook(current)
                if isinstance(res, GuardrailResult) and not res.success:
                    raise InputCheckError(res.error or "Input blocked by hook.")
                if res is not None and not isinstance(res, GuardrailResult) and callable(hook).__name__ == "PIIHook":
                    pass
        return current

    def _run_post_hooks(self, output: Any) -> Any:
        for hook in self.post_hooks:
            if isinstance(hook, BaseGuardrail):
                result = hook.check(output)
                if not result.success:
                    raise OutputCheckError(result.error or "Output blocked by guardrail.")
                if result.result is not None and isinstance(hook, PIIGuardrail) and hook.mode == "mask":
                    output = result.result
            elif callable(hook):
                hook(output)
        return output

    def _enforce_tool_policy(self, tool_name: str) -> None:
        """Tool allowlist authorization at the execution boundary (not the prompt)."""
        if self.tool_allowlist is None:
            return
        if tool_name not in self.tool_allowlist:
            raise InputCheckError(f"Tool '{tool_name}' is not in the allowlist.")

    # ------------------------------------------------------------ run sync

    def run(
        self,
        message: Optional[Union[str, List[Dict[str, Any]]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        *,
        stream: bool = False,
    ) -> Union[RunOutput, Iterator[BaseRunEvent]]:
        self.run_id = "run_" + uuid.uuid4().hex
        incoming = self._build_conversation(message, messages)
        user_text = "\n".join(m.get_text() for m in incoming if m.role == "user")
        try:
            masked = self._run_pre_hooks(user_text)
            if masked != user_text:
                for item in incoming:
                    if item.role == "user":
                        item.content = masked
        except InputCheckError:
            pass  # full rejection still happens inside _run_sync
        session = self._get_session()
        convo = list(session.messages) + incoming if session is not None else incoming
        if session is not None:
            for item in incoming:
                if item.role == "user":
                    session.add_message(item)
            self.session_store.save(session)
        if stream:
            return self._stream(convo)
        output = self._run_sync(convo)
        self._save_session_output(session, output)
        return output

    def _get_session(self) -> Optional[SessionMemory]:
        if not self.session_id:
            return None
        if self.session_store is None:
            self.session_store = SQLiteSessionStore()
        return self.session_store.get_or_create(self.session_id)

    def _save_session_output(self, session: Optional[SessionMemory], output: RunOutput) -> None:
        if session is None or output.is_paused or output.failed or not output.content:
            return
        session.add_assistant_message(output.content)
        self.session_store.save(session)

    def _run_sync(self, convo: List[Message], emit: Optional[Callable[[BaseRunEvent], None]] = None) -> RunOutput:
        trace = self.telemetry.start_trace(self.name, run_id=self.run_id) if self.telemetry else None
        usage: Dict[str, int] = {}
        calls: List[Dict[str, Any]] = []
        all_msgs: List[Message] = []
        requirements: List[RunRequirement] = []

        # Pre-hooks/guardrails on the user input (masks PII before the model sees it).
        try:
            masked = self._run_pre_hooks("\n".join(m.get_text() for m in convo))
            if masked != "\n".join(m.get_text() for m in convo):
                convo = [Message(role="user", content=masked)]
        except InputCheckError as e:
            if self.telemetry and trace:
                self.telemetry.end_trace(trace, error=str(e))
            failed_out = RunOutput(run_id=self.run_id, messages=all_msgs, status=RunStatus.ERROR.value, failed=True, error=str(e))
            self._last_run_output = failed_out
            return failed_out

        payload: List[Dict[str, Any]] = [
            Message(role="system", content=self.system_prompt).to_dict()
        ] + [m.to_dict() for m in convo]
        trace_input = [m.to_dict() for m in convo]

        tool_map = self._tool_map
        schemas = self.get_tool_schemas() if tool_map else None
        final_content: Optional[str] = None
        paused: bool = False
        paused_idx: Optional[int] = None

        try:
            for _ in range(self.max_iterations):
                step_input = list(payload)
                step_span = self.telemetry.start_span("agent_step", self.name) if self.telemetry else None
                lc_span = self.telemetry.start_span("llm_call", self.model.model_id, parent=step_span) if self.telemetry else None
                try:
                    resp = self.model.invoke(payload, tools=schemas)
                except Exception as error:
                    if self.telemetry and lc_span:
                        self.telemetry.end_span(lc_span, input=step_input, error=str(error), status="ERROR")
                    if self.telemetry and step_span:
                        self.telemetry.end_span(step_span, input=step_input, error=str(error), status="ERROR")
                    raise
                _merge_usage(usage, resp.usage)
                if self.telemetry:
                    if lc_span:
                        self.telemetry.end_span(lc_span, input=step_input, output=resp.message.to_dict(), usage=resp.usage, cost=getattr(resp, "cost", None))

                assistant = resp.message
                all_msgs.append(assistant)
                step_output: Dict[str, Any] = {"response": assistant.to_dict(), "tools": []}

                if emit:
                    emit(RunContentEvent(run_id=self.run_id, agent_id=self.id, name=self.name, content=assistant.get_text(), reasoning_content=assistant.reasoning_content))

                if not assistant.tool_calls:
                    final_content = assistant.get_text()
                    if self.telemetry and step_span:
                        self.telemetry.end_span(step_span, input=step_input, output=step_output)
                    break

                payload.append(assistant.to_dict())

                for tc in assistant.tool_calls:
                    fn = tool_map.get(tc.name)
                    if fn is None:
                        payload.append(
                            Message(role="tool", tool_call_id=tc.id, name=tc.name, content=f"Error: tool '{tc.name}' does not exist.").to_dict()
                        )
                        continue
                    # Tool authorization at the boundary (allowlist).
                    try:
                        self._enforce_tool_policy(tc.name)
                    except InputCheckError as be:
                        payload.append(Message(role="tool", tool_call_id=tc.id, name=tc.name, content=f"Error: {be}").to_dict())
                        continue

                    t1 = time.time()
                    tool_span = self.telemetry.start_span("tool", fn.name, parent=step_span) if self.telemetry else None

                    # ---- HITL gate: pause the run instead of executing ----
                    if (fn.requires_confirmation or fn.requires_user_input) and not self.disable_hitl:
                        requirement = RunRequirement(
                            run_id=self.run_id,
                            tool_call_id=tc.id or tc.name,
                            tool_name=fn.name,
                            tool_arguments=dict(fc.arguments) if (fc := self._make_fc(fn, tc)) else {},
                            requirement="confirmation" if fn.requires_confirmation else "user_input",
                            approval_id=f"apr_{uuid.uuid4().hex[:12]}",
                            user_input_schema=[{"name": "value", "type": "text", "description": "Value requested by the tool."}] if fn.requires_user_input else None,
                        )
                        self.store.create_requirement(requirement)
                        requirements.append(requirement)
                        paused = True
                        paused_idx = len(all_msgs)
                        if self.telemetry and tool_span:
                            self.telemetry.end_span(tool_span, input=requirement.tool_arguments, output="awaiting approval", status="PAUSED")
                        step_output["tools"].append({"name": fn.name, "arguments": requirement.tool_arguments, "output": "awaiting approval"})
                        if emit:
                            emit(RunToolEvent(run_id=self.run_id, agent_id=self.id, name=fn.name, tool_name=fn.name, tool_arguments=None, error=f"awaiting approval: {requirement.approval_id}"))
                        payload.append(
                            Message(role="tool", tool_call_id=tc.id, name=fn.name, content=f"[pending approval {requirement.approval_id}]").to_dict()
                        )
                        self.store.save_checkpoint(self.run_id, payload)
                        break

                    try:
                        fc = fn.get_function_call(tc.id or tc.name, tc.arguments)
                        result = fc.execute()
                    except ValueError as ve:
                        payload.append(
                            Message(role="tool", tool_call_id=tc.id, name=tc.name, content=f"Error: {ve}").to_dict()
                        )
                        if self.telemetry and tool_span:
                            self.telemetry.end_span(tool_span, input=tc.arguments, error=str(ve), status="ERROR")
                        step_output["tools"].append({"name": fn.name, "arguments": tc.arguments, "error": str(ve)})
                        if emit:
                            emit(RunToolEvent(run_id=self.run_id, agent_id=self.id, name=fn.name, tool_name=fn.name, tool_arguments=tc.arguments, error=str(ve)))
                        continue
                    dur = (time.time() - t1) * 1000
                    if result.status == "success":
                        payload.append(Message(role="tool", tool_call_id=tc.id, name=fn.name, content=str(result.result)).to_dict())
                        calls.append({"name": fn.name, "arguments": fc.arguments})
                        if self.telemetry and tool_span:
                            self.telemetry.end_span(tool_span, input=fc.arguments, output=result.result, status="OK")
                        step_output["tools"].append({"name": fn.name, "arguments": fc.arguments, "output": result.result})
                        if emit:
                            emit(RunToolEvent(run_id=self.run_id, agent_id=self.id, name=fn.name, tool_name=fn.name, tool_arguments=fc.arguments, result=result.result, duration_ms=dur))
                    else:
                        payload.append(Message(role="tool", tool_call_id=tc.id, name=fn.name, content=f"Error: {result.error}").to_dict())
                        if self.telemetry and tool_span:
                            self.telemetry.end_span(tool_span, input=fc.arguments, error=result.error, status="ERROR")
                        step_output["tools"].append({"name": fn.name, "arguments": fc.arguments, "error": result.error})
                        if emit:
                            emit(RunToolEvent(run_id=self.run_id, agent_id=self.id, name=fn.name, tool_name=fn.name, tool_arguments=fc.arguments, error=result.error, duration_ms=dur))

                if emit and not paused:
                    emit(RunStepEvent(run_id=self.run_id, agent_id=self.id, name=self.name, tool_calls=[tc.to_dict() for tc in assistant.tool_calls]))

                if self.telemetry and step_span:
                    self.telemetry.end_span(step_span, input=step_input, output=step_output, status="PAUSED" if paused else "OK")

                if paused:
                    break

            content = next(
                (m.get_text() for m in reversed(all_msgs) if m.role == "assistant" and not m.tool_calls),
                None,
            ) or final_content

            # ---- structured output validation/retry ----
            if self.output_schema is not None and content and not paused:
                content, all_msgs = self._validate_structured(content, all_msgs, payload, usage)

            # ---- post hooks ----
            if content is not None:
                try:
                    content = self._run_post_hooks(content)
                except (OutputCheckError, GuardrailError) as e:
                    if self.telemetry and trace:
                        self.telemetry.end_trace(trace, error=str(e))
                    self._last_run_output = RunOutput(run_id=self.run_id, messages=all_msgs, status=RunStatus.ERROR.value, failed=True, error=str(e))
                    return self._last_run_output

            status = RunStatus.PAUSED.value if paused else RunStatus.COMPLETED.value
            output = RunOutput(
                run_id=self.run_id,
                content=content,
                messages=all_msgs,
                tool_calls=calls,
                usage=usage,
                status=status,
                requirements=requirements,
                is_paused=paused,
                paused_at_message_index=paused_idx,
            )
            if self.telemetry and trace:
                self.telemetry.end_trace(trace, input=trace_input, output=content, usage=usage)
            self._last_run_output = output
            return output
        except Exception as e:
            if self.telemetry and trace:
                self.telemetry.end_trace(trace, error=str(e))
            self._last_run_output = RunOutput(run_id=self.run_id, messages=all_msgs, usage=usage, status=RunStatus.ERROR.value, failed=True, error=str(e))
            return self._last_run_output

    def _make_fc(self, fn: Function, tc: Any) -> Optional[FunctionCall]:
        try:
            return fn.get_function_call(tc.id or tc.name, tc.arguments)
        except Exception:
            return None

    def _validate_structured(self, content: str, all_msgs: List[Message], payload: List[Dict[str, Any]], usage: Dict[str, int]) -> tuple:
        """Parse content against the output_schema; retry with feedback on failure."""
        erro: str = "output did not conform to the required JSON schema"
        parsed = None
        for attempt in range(self.structured_retries):
            try:
                import json as _json

                data = _json.loads(content) if isinstance(content, str) else content
                parsed = self.output_schema.model_validate(data)
                break
            except Exception as e:
                erro = str(e)
                if attempt < self.structured_retries - 1:
                    # append feedback as a user message so the model retries
                    feedback = {
                        "role": "user",
                        "content": f"The previous output did not validate: {erro}. Reply ONLY with valid JSON matching the schema.",
                    }
                    payload.append(feedback)
                    all_msgs.append(Message(**feedback))
                    retry_input = list(payload)
                    lc_span = self.telemetry.start_span("llm_call", self.model.model_id) if self.telemetry else None
                    try:
                        resp = self.model.invoke(payload, tools=self.get_tool_schemas() if self._tool_map else None)
                    except Exception as error:
                        if self.telemetry and lc_span:
                            self.telemetry.end_span(lc_span, input=retry_input, error=str(error), status="ERROR")
                        raise
                    _merge_usage(usage, resp.usage)
                    if self.telemetry and lc_span:
                        self.telemetry.end_span(
                            lc_span,
                            input=retry_input,
                            output=resp.message.to_dict(),
                            usage=resp.usage,
                            cost=getattr(resp, "cost", None),
                        )
                    content = resp.message.get_text()
                    all_msgs.append(resp.message)
        if parsed is not None:
            # present as JSON string in the final content
            import json as _json

            content = _json.dumps(parsed.model_dump())
        return content, all_msgs

    # ------------------------------------------------------------ HITL continue

    def continue_run(self, run_id: Optional[str] = None) -> RunOutput:
        """Resumes a paused run: loads pending requirements, applies resolutions
        from the store, and continues with the approved gated tools EXECUTED.

        Approach (agno-style): the run paused after a gated tool call. To resume:
          1. If any requirement is still pending -> stays paused.
          2. Otherwise execute the approved gated tool(s) for real (HITL bypassed
             for this continuation ONLY), append their results as tool messages,
             and let the model finish the task.
        """
        rid = run_id or self.run_id
        reqs = self.store.get_requirements(rid)
        if not reqs:
            raise ValueError(f"No persisted requirements for run {rid}")

        pending = [r for r in reqs if r.is_pending()]
        if pending:
            out = RunOutput(run_id=rid, status=RunStatus.PAUSED.value, is_paused=True, requirements=reqs)
            self._last_run_output = out
            return out

        checkpoint = self.store.get_checkpoint(rid)
        if checkpoint is None:
            raise ValueError(f"No paused run checkpoint for run {rid}")

        # Replace each pending result in the original provider-valid payload.
        # The preceding assistant tool_call remains intact, satisfying providers
        # that require tool results to immediately follow a declared tool call.
        results: Dict[str, str] = {}
        for r in reqs:
            fns = self._tool_map.get(r.tool_name)
            if r.requirement == "user_input":
                results[r.tool_call_id] = f"[user input provided] {r.user_input}"
                continue
            if r.requirement == "feedback":
                results[r.tool_call_id] = f"[feedback provided] {r.feedback}"
                continue
            if r.requirement == "external_execution":
                results[r.tool_call_id] = f"[external execution result] {r.external_execution_result}"
                continue
            if r.requirement == "confirmation":
                if r.confirmation is not True:
                    results[r.tool_call_id] = f"[rejected by human] tool not executed: {r.confirmation_note or ''}"
                    continue
                if fns is None:
                    results[r.tool_call_id] = "[approved by human] tool not found in agent."
                    continue
                try:
                    requires_confirmation = fns.requires_confirmation
                    requires_user_input = fns.requires_user_input
                    fns.requires_confirmation = False
                    fns.requires_user_input = False
                    fc = fns.get_function_call(r.tool_call_id, r.tool_arguments)
                    res = fc.execute()
                    content = res.result if res.status == "success" else f"Error: {res.error}"
                    results[r.tool_call_id] = f"[approved by human] {content}"
                except Exception as e:
                    results[r.tool_call_id] = f"[approved by human] execution failed: {e}"
                finally:
                    fns.requires_confirmation = requires_confirmation
                    fns.requires_user_input = requires_user_input

        restored_payload = []
        for message in checkpoint:
            restored = dict(message)
            if restored.get("role") == "tool" and restored.get("tool_call_id") in results:
                restored["content"] = results[restored["tool_call_id"]]
            restored_payload.append(restored)
        # _run_sync owns the system prompt, so restore all original messages after it.
        convo = [_message_from_dict(message) for message in restored_payload[1:]]

        # Disable HITL for the continuation so re-invoking the same gated tool
        # executes instead of pausing again. Restored afterwards.
        prev_flag = self.disable_hitl
        self.disable_hitl = True
        try:
            resumed = self._run_sync(convo)
        finally:
            self.disable_hitl = prev_flag
        resumed.run_id = rid
        resumed.requirements = reqs
        if resumed.is_paused:
            resumed.status = RunStatus.PAUSED.value
        self._last_run_output = resumed
        self._save_session_output(self._get_session(), resumed)
        return resumed

    # ------------------------------------------------------------ streaming
    def _stream(self, convo: List[Message]) -> Iterator[BaseRunEvent]:
        trace = self.telemetry.start_trace(self.name, run_id=self.run_id) if self.telemetry else None
        yield RunStartedEvent(run_id=self.run_id, agent_id=self.id, run_input="\n".join(m.get_text() for m in convo))
        usage: Dict[str, int] = {}
        calls: List[Dict[str, Any]] = []
        all_msgs: List[Message] = []
        requirements: List[RunRequirement] = []
        session = self._get_session()

        try:
            masked = self._run_pre_hooks("\n".join(message.get_text() for message in convo))
            if masked != "\n".join(message.get_text() for message in convo):
                convo = [Message(role="user", content=masked)]
            payload = [Message(role="system", content=self.system_prompt).to_dict()] + [message.to_dict() for message in convo]
            trace_input = [message.to_dict() for message in convo]
            schemas = self.get_tool_schemas() if self._tool_map else None
            paused = False

            for _ in range(self.max_iterations):
                step_input = list(payload)
                step_span = self.telemetry.start_span("agent_step", self.name) if self.telemetry else None
                lc_span = self.telemetry.start_span("llm_call", self.model.model_id, parent=step_span) if self.telemetry else None
                response = None
                streamed_content = ""
                for chunk in self.model.stream(payload, tools=schemas):
                    if chunk.content:
                        streamed_content += chunk.content
                        yield RunContentEvent(run_id=self.run_id, agent_id=self.id, name=self.name, content=chunk.content, reasoning_content=chunk.reasoning_content)
                    if chunk.response is not None:
                        response = chunk.response
                if response is None:
                    if self.telemetry and lc_span:
                        self.telemetry.end_span(lc_span, input=step_input, error="Model stream ended without a final response.", status="ERROR")
                    if self.telemetry and step_span:
                        self.telemetry.end_span(step_span, input=step_input, error="Model stream ended without a final response.", status="ERROR")
                    raise RuntimeError("Model stream ended without a final response.")
                _merge_usage(usage, response.usage)
                assistant = response.message
                all_msgs.append(assistant)
                step_output: Dict[str, Any] = {"response": assistant.to_dict(), "tools": []}
                if self.telemetry and lc_span:
                    self.telemetry.end_span(lc_span, input=step_input, output=assistant.to_dict(), usage=response.usage, cost=getattr(response, "cost", None))
                assistant_content = assistant.get_text()
                if assistant_content and not streamed_content:
                    yield RunContentEvent(run_id=self.run_id, agent_id=self.id, name=self.name, content=assistant_content, reasoning_content=assistant.reasoning_content)
                if not assistant.tool_calls:
                    if self.telemetry and step_span:
                        self.telemetry.end_span(step_span, input=step_input, output=step_output)
                    break

                payload.append(assistant.to_dict())
                for tool_call in assistant.tool_calls:
                    function = self._tool_map.get(tool_call.name)
                    if function is None:
                        payload.append(Message(role="tool", tool_call_id=tool_call.id, name=tool_call.name, content=f"Error: tool '{tool_call.name}' does not exist.").to_dict())
                        continue
                    self._enforce_tool_policy(tool_call.name)
                    tool_span = self.telemetry.start_span("tool", function.name, parent=step_span) if self.telemetry else None
                    if (function.requires_confirmation or function.requires_user_input) and not self.disable_hitl:
                        requirement = RunRequirement(
                            run_id=self.run_id,
                            tool_call_id=tool_call.id or tool_call.name,
                            tool_name=function.name,
                            tool_arguments=dict(fc.arguments) if (fc := self._make_fc(function, tool_call)) else {},
                            requirement="confirmation" if function.requires_confirmation else "user_input",
                            approval_id=f"apr_{uuid.uuid4().hex[:12]}",
                        )
                        self.store.create_requirement(requirement)
                        requirements.append(requirement)
                        payload.append(Message(role="tool", tool_call_id=tool_call.id, name=function.name, content=f"[pending approval {requirement.approval_id}]").to_dict())
                        self.store.save_checkpoint(self.run_id, payload)
                        paused = True
                        if self.telemetry and tool_span:
                            self.telemetry.end_span(tool_span, input=requirement.tool_arguments, output="awaiting approval", status="PAUSED")
                        step_output["tools"].append({"name": function.name, "arguments": requirement.tool_arguments, "output": "awaiting approval"})
                        yield RunToolEvent(run_id=self.run_id, agent_id=self.id, name=function.name, tool_name=function.name, error=f"awaiting approval: {requirement.approval_id}")
                        break
                    started = time.time()
                    try:
                        function_call = function.get_function_call(tool_call.id or tool_call.name, tool_call.arguments)
                        result = function_call.execute()
                    except ValueError as ve:
                        payload.append(Message(role="tool", tool_call_id=tool_call.id, name=function.name, content=f"Error: {ve}").to_dict())
                        if self.telemetry and tool_span:
                            self.telemetry.end_span(tool_span, input=tool_call.arguments, error=str(ve), status="ERROR")
                        step_output["tools"].append({"name": function.name, "arguments": tool_call.arguments, "error": str(ve)})
                        yield RunToolEvent(run_id=self.run_id, agent_id=self.id, name=function.name, tool_name=function.name, tool_arguments=tool_call.arguments, error=str(ve))
                        continue
                    duration_ms = (time.time() - started) * 1000
                    if result.status == "success":
                        payload.append(Message(role="tool", tool_call_id=tool_call.id, name=function.name, content=str(result.result)).to_dict())
                        calls.append({"name": function.name, "arguments": function_call.arguments})
                        if self.telemetry and tool_span:
                            self.telemetry.end_span(tool_span, input=function_call.arguments, output=result.result)
                        step_output["tools"].append({"name": function.name, "arguments": function_call.arguments, "output": result.result})
                        yield RunToolEvent(run_id=self.run_id, agent_id=self.id, name=function.name, tool_name=function.name, tool_arguments=function_call.arguments, result=result.result, duration_ms=duration_ms)
                    else:
                        payload.append(Message(role="tool", tool_call_id=tool_call.id, name=function.name, content=f"Error: {result.error}").to_dict())
                        if self.telemetry and tool_span:
                            self.telemetry.end_span(tool_span, input=function_call.arguments, error=result.error, status="ERROR")
                        step_output["tools"].append({"name": function.name, "arguments": function_call.arguments, "error": result.error})
                        yield RunToolEvent(run_id=self.run_id, agent_id=self.id, name=function.name, tool_name=function.name, tool_arguments=function_call.arguments, error=result.error, duration_ms=duration_ms)
                yield RunStepEvent(run_id=self.run_id, agent_id=self.id, name=self.name, tool_calls=[call.to_dict() for call in assistant.tool_calls])
                if self.telemetry and step_span:
                    self.telemetry.end_span(step_span, input=step_input, output=step_output, status="PAUSED" if paused else "OK")
                if paused:
                    break

            content = next((message.get_text() for message in reversed(all_msgs) if message.role == "assistant" and not message.tool_calls), None)
            if self.output_schema is not None and content and not paused:
                content, all_msgs = self._validate_structured(content, all_msgs, payload, usage)
            if content is not None and not paused:
                content = self._run_post_hooks(content)
            output = RunOutput(run_id=self.run_id, content=content, messages=all_msgs, tool_calls=calls, usage=usage, status=RunStatus.PAUSED.value if paused else RunStatus.COMPLETED.value, requirements=requirements, is_paused=paused)
            self._last_run_output = output
            self._save_session_output(session, output)
            if self.telemetry and trace:
                self.telemetry.end_trace(trace, input=trace_input, output=content, usage=usage)
            if paused:
                yield RunStepEvent(run_id=self.run_id, agent_id=self.id, name=self.name, messages=[requirement.to_dict() for requirement in requirements])
            yield RunStepEvent(run_id=self.run_id, messages=[message.to_dict() for message in output.messages])
            yield RunCompletedEvent(run_id=self.run_id, output=output.to_dict(), metrics={"usage": output.usage, "status": output.status})
        except Exception as error:
            if self.telemetry and trace:
                self.telemetry.end_trace(trace, error=str(error))
            self._last_run_output = RunOutput(run_id=self.run_id, messages=all_msgs, usage=usage, status=RunStatus.ERROR.value, failed=True, error=str(error))
            yield RunFailedEvent(run_id=self.run_id, error=str(error))
