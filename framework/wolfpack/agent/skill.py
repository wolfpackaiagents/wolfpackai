"""Reusable capability fragments for Agents.

A Skill is a composable prompt fragment that an Agent can load to acquire a
specific capability or persona. Two types:

- Skill: prompt-based skill (inline string or .md file). When ``context`` is
  provided, the skill is listed as available for contextual activation instead
  of being appended unconditionally.
- SkillKnowledge: registers a specialised Knowledge base with a context for
  on-demand search. No prompt content is added, only a search tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union


class Skill:
    """A reusable prompt fragment for an Agent.

    Args:
        name: Unique skill name used in system prompts and telemetry metadata.
        content: Inline prompt text. Required if ``path`` is not given.
        path: Path to a ``.md`` file. The file content becomes the skill prompt.
        context: Description of when the agent should activate this skill.
            When set, the skill is listed as available instead of appended
            unconditionally to the system prompt.

    Usage::

        Skill(name="analyst", content="You are a financial analyst.")
        Skill(name="analyst", path="skills/analyst.md")
        Skill(name="analyst", content="...", context="Use when analysing risk")
    """

    def __init__(
        self,
        name: str,
        content: Optional[str] = None,
        path: Optional[Union[str, "Path"]] = None,
        context: Optional[str] = None,
    ):
        if not name or not name.strip():
            raise ValueError("Skill name must be a non-empty string")
        self.name = name.strip()

        if content is not None:
            self.content = content
        elif path is not None:
            resolved = Path(path).expanduser().resolve()
            if not resolved.exists():
                raise FileNotFoundError(f"Skill file not found: {resolved}")
            self.content = resolved.read_text(encoding="utf-8")
        else:
            raise ValueError("Either content or path must be provided")

        self.context = context

    def __repr__(self) -> str:
        ctx = f", context={self.context!r}" if self.context else ""
        return f"Skill(name={self.name!r}{ctx})"


class SkillKnowledge:
    """A specialised Knowledge base that an Agent can search on demand.

    Unlike ``Skill``, this does not add prompt content. It only registers
    a ``search_knowledge_{name}`` tool with a context description so the agent
    knows when to activate it.

    Args:
        name: Unique name used for the search tool and telemetry metadata.
        knowledge: A ``Knowledge`` instance with the specialised data.
        context: Description of when the agent should use this knowledge.
    """

    def __init__(
        self,
        name: str,
        knowledge: Any,
        context: str,
    ):
        if not name or not name.strip():
            raise ValueError("SkillKnowledge name must be a non-empty string")
        if knowledge is None:
            raise ValueError("SkillKnowledge requires a Knowledge instance")
        if not context or not context.strip():
            raise ValueError("SkillKnowledge context must be a non-empty string")

        self.name = name.strip()
        self.knowledge = knowledge
        self.context = context.strip()

    def __repr__(self) -> str:
        return f"SkillKnowledge(name={self.name!r})"
