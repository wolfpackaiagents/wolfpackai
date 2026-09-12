"""Wolfpack AI - Python framework for building AI agents.

It borrows patterns from agno, crewAI, vercel/ai and langfuse after deep analysis.
The framework binds agent execution to observability: every run emits OpenTelemetry
spans with the GenAI semantic convention (`gen_ai.*`).
"""

from wolfpack.agent.agent import Agent
from wolfpack.agent.events import (
    RunStartedEvent,
    RunContentEvent,
    RunStepEvent,
    RunToolEvent,
    RunCompletedEvent,
    RunFailedEvent,
    RunEventType,
    event_type_to_str,
)
from wolfpack.tools.decorator import tool
from wolfpack.tools.factory import create_knowledge_search_tool
from wolfpack.tools.toolkit import Toolkit
from wolfpack.models.utils import get_model, get_model_from_env
from wolfpack.guardrails.base import (
    BaseGuardrail,
    GuardrailResult,
    GuardrailError,
    InputCheckError,
    OutputCheckError,
    PIIGuardrail,
    PromptInjectionGuardrail,
    ToolAllowlistGuardrail,
)
from wolfpack.run.requirement import RunRequirement, RunStatus, UserInputField
from wolfpack.run.approval_store import (
    ApprovalStore,
    MemoryApprovalStore,
    LocalApprovalStore,
    AmpApprovalStore,
    default_store,
)
from wolfpack.memory import InMemorySessionStore, SessionMemory, SessionStore, SQLiteSessionStore
from wolfpack.workflow import Workflow, WorkflowError, WorkflowResult
from wolfpack.team import Team, TeamMode, TeamResult
from wolfpack.mcp import MCPClient
from wolfpack.mesh import MeshIdentity
from wolfpack.evals import AmpScorePublisher, CallableEvaluator, EvalCase, EvalReport, EvalResult, EvalRunner, EvalScore
from wolfpack.schedules import AmpScheduleClient, HttpRuntimeRunner, RuntimeContext, RuntimeDispatch, ScheduleTask, ScheduleTaskRequest, ScheduleToolkit
from wolfpack.channels import AmpWebChatAdapter, ChannelIdentity, DeliveryReceipt, DiscordAdapter, InboundMessage, SlackAdapter, TelegramAdapter, WebChatAdapter
from wolfpack.data import AnalyticsToolkit, AthenaToolkit, BigQueryToolkit, ClickHouseToolkit, DataAccessPolicy, DataPolicyError, DatabricksToolkit, DocumentToolkit, GraphToolkit, KeyValueToolkit, SnowflakeToolkit, SqlToolkit, TrinoToolkit, ingest_rows

__all__ = [
    "Agent",
    "tool",
    "Toolkit",
    "get_model",
    "get_model_from_env",
    "create_knowledge_search_tool",
    # guardrails
    "BaseGuardrail",
    "GuardrailResult",
    "GuardrailError",
    "InputCheckError",
    "OutputCheckError",
    "PIIGuardrail",
    "PromptInjectionGuardrail",
    "ToolAllowlistGuardrail",
    # HITL
    "RunRequirement",
    "RunStatus",
    "UserInputField",
    "ApprovalStore",
    "MemoryApprovalStore",
    "LocalApprovalStore",
    "AmpApprovalStore",
    "default_store",
    # memory
    "SessionMemory",
    "SessionStore",
    "InMemorySessionStore",
    "SQLiteSessionStore",
    # workflows
    "Workflow",
    "WorkflowError",
    "WorkflowResult",
    "Team",
    "TeamMode",
    "TeamResult",
    "MCPClient",
    "MeshIdentity",
    # evaluations
    "AmpScorePublisher",
    "CallableEvaluator",
    "EvalCase",
    "EvalReport",
    "EvalResult",
    "EvalRunner",
    "EvalScore",
    # scheduled tasks
    "AmpScheduleClient",
    "ScheduleTask",
    "ScheduleTaskRequest",
    "ScheduleToolkit",
    "HttpRuntimeRunner",
    "RuntimeContext",
    "RuntimeDispatch",
    # channels
    "ChannelIdentity",
    "InboundMessage",
    "DeliveryReceipt",
    "TelegramAdapter",
    "SlackAdapter",
    "DiscordAdapter",
    "WebChatAdapter",
    "AmpWebChatAdapter",
    # governed data sources
    "AnalyticsToolkit",
    "AthenaToolkit",
    "BigQueryToolkit",
    "ClickHouseToolkit",
    "DataAccessPolicy",
    "DataPolicyError",
    "DatabricksToolkit",
    "DocumentToolkit",
    "GraphToolkit",
    "KeyValueToolkit",
    "SqlToolkit",
    "SnowflakeToolkit",
    "TrinoToolkit",
    "ingest_rows",
    # events
    "RunStartedEvent",
    "RunContentEvent",
    "RunStepEvent",
    "RunToolEvent",
    "RunCompletedEvent",
    "RunFailedEvent",
    "RunEventType",
    "event_type_to_str",
]
