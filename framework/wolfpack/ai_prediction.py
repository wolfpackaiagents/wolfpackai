"""Multi-agent prediction engine inspired by MiroFish.

AIPrediction orchestrates multiple persona agents to generate predictions
from seed materials, then synthesizes their outputs into a structured report.

When auto_create_personas is enabled, the engine analyzes seed data via LLM
to generate diverse expert personas appropriate for the prediction context.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from wolfpack.agent.agent import Agent
from wolfpack.memory import InMemorySessionStore


@dataclass
class PredictionReport:
    name: str
    prediction_id: str
    scenario: str
    seed_summary: str | None = None
    horizon: str | None = None
    status: str = "completed"
    individual_predictions: List[Dict[str, Any]] = field(default_factory=list)
    convergences: List[Dict[str, Any]] = field(default_factory=list)
    rounds: List[Dict[str, Any]] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    revisions: List[Dict[str, Any]] = field(default_factory=list)
    scores: List[Dict[str, Any]] = field(default_factory=list)
    synthesis: str = ""
    observed_outcome: str | None = None
    accuracy_score: float | None = None
    evaluation_reason: str | None = None
    raw_team_result: Any = None
    auto_generated_personas: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_PERSONA_GENERATION_PROMPT = """You are a prediction strategist designing a panel of expert agents.

Given the seed context and scenario below, generate {count} diverse expert personas
to analyze this prediction from different angles. Each persona must represent a
distinct perspective, expertise area, and cognitive bias.

Seed context: {seed_context}
Scenario: {scenario}
Prediction horizon: {horizon}

Return exactly {count} personas as a JSON array. Each object must have:
- "name": a realistic expert name
- "role": their area of expertise (e.g., "macroeconomist", "geopolitical analyst", "industry specialist")
- "bias": their cognitive bias (e.g., "optimistic", "pessimistic", "conservative", "contrarian", "technology-optimist", "regulation-focused")
- "expertise": their specific domain knowledge

Make the personas diverse and potentially conflicting — the value comes from their disagreement. Examples of good personas:
{{"name": "Dr. Ana Santos", "role": "macroeconomist", "bias": "conservative", "expertise": "monetary policy and interest rates"}}
{{"name": "Prof. Carlos Mendes", "role": "geopolitical analyst", "bias": "contrarian", "expertise": "international relations and trade policy"}}

Output *only* the JSON array, no other text.

Responda no MESMO IDIOMA dos materiais de seed. Se o seed for em português, retorne nomes, cargos e vieses em português."""


class AIPrediction:
    """Multi-agent prediction engine.

    Pipeline:
        1. ingest_seed() — stores seed materials in a vector Knowledge base.
        2. run(scenario) — broadcasts the scenario to persona agents, collects
           individual predictions, computes convergences, and synthesizes a
           final report.

    When auto_create_personas=True, the engine automatically generates
    personas from the seed context instead of requiring them explicitly.

    Each persona Agent receives its own system prompt with role, bias, and
    expertise. The synthesizer Agent aggregates all perspectives into a
    structured report with convergence analysis.
    """

    def __init__(
        self,
        name: str,
        model: Any,
        personas: Optional[List[Dict[str, str]]] = None,
        horizon: str | None = None,
        knowledge: Any = None,
        telemetry: Any = None,
        max_iterations: int = 10,
        auto_create_personas: bool = False,
        persona_count: int = 4,
        debate_rounds: int = 3,
    ):
        self.name = name
        self.model = model
        self.personas = personas or []
        self.horizon = horizon
        self.knowledge = knowledge
        self.telemetry = telemetry
        self.max_iterations = max_iterations
        self.auto_create_personas = auto_create_personas
        self.persona_count = max(2, min(persona_count, 8))
        self.debate_rounds = max(0, min(debate_rounds, 5))
        self.run_id: str | None = None
        self.prediction_id: str | None = None
        self.auto_generated: bool = False
        self._seed_text: str = ""

    def _extract_seed_context(self) -> str:
        texts = [self._seed_text] if self._seed_text else []
        if self.knowledge:
            try:
                results = self.knowledge.search("main topics entities and key information", limit=5)
                for result in results or []:
                    content = getattr(result, "content", None) or (
                        result if isinstance(result, str) else str(result)
                    )
                    texts.append(str(content)[:500])
            except Exception:
                pass
        if texts:
            return "\n\n".join(texts)[:3000]
        if self.knowledge:
            return "Seed data available in knowledge base."
        return "No seed data available."

    def _generate_personas_from_knowledge(self, scenario: str) -> List[Dict[str, str]]:
        seed_context = self._extract_seed_context()
        prompt = _PERSONA_GENERATION_PROMPT.format(
            count=self.persona_count,
            seed_context=seed_context,
            scenario=scenario,
            horizon=self.horizon or "not specified",
        )
        response = self.model.invoke([{"role": "user", "content": prompt}])
        content = response.message.content or "[]"
        personas = self._parse_persona_json(content)
        if not personas:
            raise ValueError(
                "The model did not return a valid persona panel. "
                "Provide personas explicitly or refine the seed material; "
                "no synthetic persona fallback is used."
            )
        return personas

    def _parse_persona_json(self, content: str) -> List[Dict[str, str]]:
        json_match = re.search(r"\[\s*\{.*\}\s*\]", content, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, list):
                    return [p for p in parsed if p.get("name") and p.get("role")]
            except json.JSONDecodeError:
                pass
        return []

    def _parse_agent_output(self, content: str) -> Dict[str, Any]:
        stripped = content.strip()
        json_match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return {"prediction": stripped}

    def _ensure_personas(self, scenario: str) -> None:
        if self.personas:
            if self.auto_create_personas:
                extra = self._generate_personas_from_knowledge(scenario)
                existing_names = {p.get("name", "").lower() for p in self.personas}
                new = [p for p in extra if p.get("name", "").lower() not in existing_names]
                if new:
                    self.personas.extend(new)
                    self.auto_generated = True
        elif self.auto_create_personas:
            self.personas = self._generate_personas_from_knowledge(scenario)
            self.auto_generated = True

        if not self.personas:
            raise ValueError(
                "No personas configured. Either provide them explicitly or "
                "set auto_create_personas=True with a knowledge base."
            )

    def _build_persona_prompt(self, persona: Dict[str, str]) -> str:
        lines = [f"You are {persona.get('name', 'an analyst')}."]
        role = persona.get("role") or persona.get("expertise")
        if role:
            lines.append(f"Your role: {role}")
        bias = persona.get("bias")
        if bias:
            lines.append(f"Your cognitive bias: {bias}")
        if self.horizon:
            lines.append(f"Prediction horizon: {self.horizon}")
        lines.append(
            "\nYou are participating in a multi-agent prediction exercise. "
            "Given the scenario and seed data, produce a structured prediction "
            "including: your forecast, key drivers, confidence level (0-1), "
            "risks, and warning signs.\n\n"
            "IMPORTANT: Output your prediction as a valid JSON object with keys "
            "as short descriptive names (use_underscores). For example:\n"
            '{"forecast": "Candidate A wins 52%", '
            '"key_drivers": "Economic stability favors incumbent", '
            '"confidence": 0.78, '
            '"risks": "Scandal could shift 3%", '
            '"warning_signs": "Drop in polls below 45%"}\n'
            "Output ONLY the JSON object, no other text.\n\n"
            "IMPORTANT: Responda no MESMO IDIOMA do cenario e dos materiais de seed. "
            "Se o cenario for em portugues, sua previsao deve ser toda em portugues."
        )
        if self.knowledge:
            lines.append(
                "\nYou have access to a knowledge base with seed materials. "
                "Use `search_knowledge` to retrieve relevant information "
                "before making your prediction."
            )
        return "\n".join(lines)

    def _build_critique_prompt(self, author: str, peers: List[Dict[str, Any]], round_number: int) -> str:
        peer_blocks = []
        for peer in peers:
            peer_blocks.append(f"- {peer['persona_name']}: {json.dumps(peer['prediction'], ensure_ascii=False, default=str)}")
        peers_text = "\n".join(peer_blocks)
        return (
            f"SIMULATION CYCLE {round_number} - CRITIQUE. You are {author}. "
            "Read the peer forecasts below and challenge or reinforce them.\n\n"
            f"{peers_text}\n\n"
            "Return a JSON list. Each object must have:\n"
            '- "target": the exact peer name you are addressing\n'
            '- "stance": one of "concorda", "discorda", "parcial"\n'
            '- "argument": one concise sentence with evidence or reasoning\n\n'
            "Address at least one peer. Output ONLY the JSON list.\n"
            "Responda no MESMO IDIOMA das previsoes recebidas."
        )

    def _build_social_entities(self) -> List[Dict[str, Any]]:
        """Create stable simulation actors from the validated persona panel."""
        return [
            {
                "key": f"actor-{index + 1}",
                "name": persona.get("name", f"Agent {index + 1}"),
                "entity_type": "actor",
                "state": {"role": persona.get("role"), "bias": persona.get("bias")},
                "metadata": {"expertise": persona.get("expertise", "")},
            }
            for index, persona in enumerate(self.personas)
        ]

    def _extract_world_graph(self, scenario: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract a bounded domain graph from seed evidence for the simulation world."""
        prompt = (
            "WORLD GRAPH EXTRACTION. Extract only entities and relationships supported by the "
            "seed material below and relevant to the scenario. Do not invent entities, facts, "
            "or relationships. Use the same language as the scenario and seed for type, summary, "
            "and relationship type. Evidence must be a short verbatim quote from the seed. "
            "Return only a JSON object:\n"
            '{"entities":[{"name":"...","type":"...","summary":"..."}],'
            '"relationships":[{"source":"...","target":"...","type":"...","strength":0.0,"evidence":"..."}]}\n\n'
            f"Scenario: {scenario}\nSeed material:\n{self._extract_seed_context()}"
        )
        output = self.model.invoke([{"role": "user", "content": prompt}])
        graph = self._parse_agent_output(output.message.content or "")
        raw_entities = graph.get("entities") if isinstance(graph.get("entities"), list) else []
        entities: List[Dict[str, Any]] = []
        by_name: Dict[str, str] = {}
        for item in raw_entities[:24]:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            entity_type = item.get("type")
            if not isinstance(name, str) or not name.strip() or not isinstance(entity_type, str) or not entity_type.strip():
                continue
            normalized_name = name.strip().casefold()
            if normalized_name in by_name:
                continue
            key = f"context-{len(entities) + 1}"
            by_name[normalized_name] = key
            entities.append({
                "key": key,
                "name": name.strip(),
                "entity_type": entity_type.strip(),
                "state": {"summary": item.get("summary", "")},
                "metadata": {"source": "seed_extraction"},
            })
        raw_relationships = graph.get("relationships") if isinstance(graph.get("relationships"), list) else []
        relationships: List[Dict[str, Any]] = []
        for item in raw_relationships[:64]:
            if not isinstance(item, dict):
                continue
            source = by_name.get(str(item.get("source", "")).strip().casefold())
            target = by_name.get(str(item.get("target", "")).strip().casefold())
            relationship_type = item.get("type")
            if not source or not target or source == target or not isinstance(relationship_type, str) or not relationship_type.strip():
                continue
            try:
                strength = max(0.0, min(float(item.get("strength", 0.5)), 1.0))
            except (TypeError, ValueError):
                strength = 0.5
            attributes = {"strength": strength}
            evidence = item.get("evidence")
            if isinstance(evidence, str) and evidence.strip():
                attributes["evidence"] = evidence.strip()
            relationships.append({
                "source": source,
                "target": target,
                "relationship_type": relationship_type.strip(),
                "attributes": attributes,
            })
        return entities, relationships

    @staticmethod
    def _build_social_relationships(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use a complete directed influence graph so every actor can observe peers."""
        return [
            {
                "source": source["key"],
                "target": target["key"],
                "relationship_type": "influences",
                "attributes": {"strength": 0.5},
            }
            for source in entities
            for target in entities
            if source["key"] != target["key"]
        ]

    def _temporal_event(
        self, scenario: str, round_number: int, completed_rounds: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Inject a bounded, evidence-aware event to advance the social simulation clock."""
        history = json.dumps(completed_rounds[-1:] if completed_rounds else [], ensure_ascii=False, default=str)
        prompt = (
            f"SIMULATION EVENT FOR CYCLE {round_number}. Scenario: {scenario}\n"
            f"Seed evidence: {self._extract_seed_context()[:1200]}\n"
            f"Previous cycle: {history}\n\n"
            "Return only a JSON object with `content` (one plausible new development) and "
            "`impact` (why it changes actors' incentives). Do not invent named sources or numbers. "
            "Use the scenario language."
        )
        parsed = self._parse_agent_output(self.model.invoke([{"role": "user", "content": prompt}]).message.content or "")
        content = parsed.get("content") if isinstance(parsed.get("content"), str) else None
        impact = parsed.get("impact") if isinstance(parsed.get("impact"), str) else ""
        return {
            "event_type": "scenario.injected",
            "round": round_number,
            "content": content or f"Ciclo temporal {round_number}: {scenario}",
            "payload": {"scenario": scenario, "horizon": self.horizon, "impact": impact},
        }

    def _build_revision_prompt(self, author: str, own: Dict[str, Any], received: List[Dict[str, Any]]) -> str:
        critique_text = "\n".join(
            f"- {c['source']} ({c.get('stance', 'parcial')}): {c.get('content', '')}" for c in received
        ) or "- Nenhuma critica recebida."
        return (
            f"REVISE. You are {author}. Your previous forecast was:\n"
            f"{json.dumps(own, ensure_ascii=False, default=str)}\n\n"
            f"Peers said about your forecast:\n{critique_text}\n\n"
            "Produce your revised forecast as a JSON object using the same keys as before, "
            "including an updated numeric \"confidence\" between 0 and 1. "
            "If you keep your position, repeat it and explain briefly in the fields.\n"
            "Output ONLY the JSON object. Responda no MESMO IDIOMA do cenario."
        )

    def _parse_critiques(self, content: str, author: str, valid_targets: set[str], round_number: int) -> List[Dict[str, Any]]:
        match = re.search(r"\[.*\]", content.strip(), re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        critiques: List[Dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            target = item.get("target")
            if target not in valid_targets or target == author:
                continue
            critiques.append({
                "source": author,
                "target": target,
                "stance": item.get("stance", "parcial"),
                "content": item.get("argument", ""),
                "type": item.get("stance", "parcial"),
                "round": round_number,
            })
        return critiques

    def _build_synthesis_prompt(
        self,
        scenario: str,
        predictions: List[Dict[str, Any]],
        rounds: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        preds_text = json.dumps(predictions, indent=2, default=str)
        rounds_text = json.dumps(rounds or [], indent=2, ensure_ascii=False, default=str)
        return (
            f"You are a synthesis analyst. Given the following scenario and "
            f"individual predictions from multiple expert agents, produce a "
            f"unified prediction report.\n\nScenario: {scenario}\n\n"
            f"Initial and final predictions:\n{preds_text}\n\n"
            f"Simulation timeline (critiques and revisions):\n{rounds_text}\n\n"
            "Structure your report with:\n"
            "1. Executive Summary\n"
            "2. Consensus View (areas of agreement)\n"
            "3. Divergent Views (areas of disagreement)\n"
            "4. Most Likely Scenario\n"
            "5. Key Risks and Warning Signs\n"
            "6. Recommended Actions\n\n"
            "Base every conclusion on timeline events and resulting revisions, not on an unsupported "
            "majority vote. For each section, cite the event or agents that contributed.\n\n"
            "IMPORTANT: Responda no MESMO IDIOMA do cenario e das previsoes. "
            "Se o cenario for em portugues, seu relatorio deve ser todo em portugues."
        )

    def _compute_convergences(self, predictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for i, pred_i in enumerate(predictions):
            for j, pred_j in enumerate(predictions):
                if i >= j:
                    continue
                pi = pred_i.get("prediction", {})
                pj = pred_j.get("prediction", {})
                if isinstance(pi, dict) and isinstance(pj, dict):
                    common = set(pi.keys()) & set(pj.keys())
                    if common:
                        match = sum(1 for k in common if pi.get(k) == pj.get(k))
                        rate = match / len(common) if common else 0
                        results.append({
                            "agents": [pred_i["persona_name"], pred_j["persona_name"]],
                            "rate": round(rate, 2),
                            "common_factors": list(common),
                        })
        return sorted(results, key=lambda c: c["rate"], reverse=True)

    def ingest_seed(self, text: str | None = None, path: str | None = None) -> None:
        if path:
            try:
                with open(path) as f:
                    content = f.read()
                self._seed_text = content
            except (FileNotFoundError, IOError):
                return
            if self.knowledge:
                self.knowledge.add_from_path(path)
        if text:
            self._seed_text = text
            if self.knowledge:
                self.knowledge.add_text(text, metadata={"source": "seed", "prediction": self.name})

    def run(self, scenario: str, observed_outcome: str | None = None) -> PredictionReport:
        self._ensure_personas(scenario)
        world_entities, world_relationships = self._extract_world_graph(scenario)
        actor_entities = self._build_social_entities()
        entities = world_entities + actor_entities
        relationships = world_relationships + self._build_social_relationships(actor_entities)
        entity_by_name = {entity["name"]: entity["key"] for entity in actor_entities}

        session_store = InMemorySessionStore()
        persona_agents = []
        for persona in self.personas:
            persona_name = persona.get("name", "analyst")
            agent = Agent(
                name=persona_name,
                model=self.model,
                system=self._build_persona_prompt(persona),
                role=persona.get("role", "analyst"),
                knowledge=self.knowledge,
                telemetry=self.telemetry,
                session_id=f"prediction:{self.name}:{persona_name}",
                session_store=session_store,
                max_iterations=self.max_iterations,
            )
            persona_agents.append(agent)

        enriched_scenario = scenario
        if self.horizon:
            enriched_scenario = f"[Horizon: {self.horizon}] {scenario}"
        if self.knowledge:
            enriched_scenario = (
                f"{enriched_scenario}\n\nSeed data has been loaded into your "
                f"knowledge base. Use `search_knowledge` to access it."
            )

        individual_predictions: List[Dict[str, Any]] = []
        for agent in persona_agents:
            output = agent.run(enriched_scenario)
            parsed = self._parse_agent_output(output.content or "")
            conf = parsed.get("confidence") if isinstance(parsed, dict) else None
            individual_predictions.append({
                "persona_name": agent.name,
                "entity_key": entity_by_name[agent.name],
                "initial_prediction": parsed,
                "prediction": parsed,
                "confidence": conf if isinstance(conf, (int, float)) else None,
                "interactions": [],
                "persona_profile": next(
                    (p for p in self.personas if p.get("name") == agent.name), {}
                ),
            })

        rounds = self._run_debate(persona_agents, individual_predictions, scenario)
        events, revisions = self._simulation_ledger(individual_predictions, rounds)
        convergences = self._compute_convergences(individual_predictions)
        scores = self._compute_debate_scores(individual_predictions, convergences)

        synthesizer = Agent(
            name=f"{self.name}_synthesizer",
            model=self.model,
            system="You synthesize multiple expert predictions into a coherent report. "
                   "Responda no MESMO IDIOMA das previsoes recebidas.",
            telemetry=self.telemetry,
            knowledge=self.knowledge,
            max_iterations=8,
        )
        synthesis_result = synthesizer.run(
            self._build_synthesis_prompt(scenario, individual_predictions, rounds)
        )

        prediction_id = uuid.uuid4().hex[:32]
        self.prediction_id = prediction_id
        self.run_id = prediction_id

        report = PredictionReport(
            name=self.name,
            prediction_id=prediction_id,
            scenario=scenario,
            horizon=self.horizon,
            seed_summary=self._summarize_seed(),
            individual_predictions=individual_predictions,
            convergences=convergences,
            rounds=rounds,
            entities=entities,
            relationships=relationships,
            events=events,
            revisions=revisions,
            scores=scores,
            synthesis=synthesis_result.content or "",
            auto_generated_personas=self.auto_generated,
        )
        if observed_outcome:
            self.evaluate_observed_outcome(report, observed_outcome)
        return report

    def evaluate_observed_outcome(self, report: PredictionReport, observed_outcome: str) -> float:
        """Evaluate a completed forecast against a supplied, independently observed outcome."""
        prompt = f"""OBSERVED OUTCOME EVALUATION. Compare the simulation forecast with the observed outcome.
Do not use agent confidence as accuracy. Score only whether the forecast matches the observed outcome.
Return only JSON: {{"accuracy_score": 0.0, "reason": "..."}}. The score must be from 0 to 1.

Forecast:
{report.synthesis}

Observed outcome:
{observed_outcome}"""
        response = self.model.invoke([{"role": "user", "content": prompt}])
        result = self._parse_agent_output(response.message.content or "")
        try:
            score = float(result["accuracy_score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("The evaluator did not return a valid accuracy_score") from exc
        if not 0 <= score <= 1:
            raise ValueError("The evaluator returned an accuracy_score outside 0 to 1")
        report.observed_outcome = observed_outcome
        report.accuracy_score = score
        report.evaluation_reason = str(result.get("reason", ""))
        return score

    def _run_debate(
        self, agents: List[Any], predictions: List[Dict[str, Any]], scenario: str = ""
    ) -> List[Dict[str, Any]]:
        """Critique and revision rounds; every message becomes a persisted interaction."""
        if self.debate_rounds == 0 or len(predictions) < 2:
            return []

        by_name = {p["persona_name"]: p for p in predictions}
        valid_targets = set(by_name)
        rounds: List[Dict[str, Any]] = []

        for round_number in range(1, self.debate_rounds + 1):
            temporal_event = self._temporal_event(scenario, round_number, rounds)
            round_interactions: List[Dict[str, Any]] = []
            for agent in agents:
                peers = [p for p in predictions if p["persona_name"] != agent.name]
                if not peers:
                    continue
                critique_prompt = (
                    f"Temporal event for this cycle: {temporal_event['content']}\n\n"
                    f"{self._build_critique_prompt(agent.name, peers, round_number)}"
                )
                critique_output = agent.run(critique_prompt)
                critiques = self._parse_critiques(
                    critique_output.content or "", agent.name, valid_targets, round_number
                )
                by_name[agent.name]["interactions"].extend(critiques)
                round_interactions.extend(critiques)

            revisions: List[Dict[str, Any]] = []
            for agent in agents:
                received = [i for i in round_interactions if i["target"] == agent.name]
                entry = by_name[agent.name]
                if not received:
                    continue
                revision_output = agent.run(
                    self._build_revision_prompt(agent.name, entry["prediction"], received)
                )
                revised = self._parse_agent_output(revision_output.content or "")
                if revised:
                    entry["prediction"] = revised
                    conf = revised.get("confidence")
                    if isinstance(conf, (int, float)):
                        entry["confidence"] = conf
                    revisions.append({"persona_name": agent.name, "prediction": revised})

            rounds.append({
                "round": round_number,
                "event": temporal_event,
                "interactions": round_interactions,
                "revisions": revisions,
            })
        return rounds

    @staticmethod
    def _simulation_ledger(
        predictions: List[Dict[str, Any]], rounds: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Flatten cycle output into append-only events and immutable state revisions."""
        events: List[Dict[str, Any]] = []
        revisions: List[Dict[str, Any]] = []
        sequence = 0
        for prediction in predictions:
            revisions.append({
                "entity_key": prediction["entity_key"],
                "round": 0,
                "state": {
                    "prediction": prediction["initial_prediction"],
                    "confidence": prediction["initial_prediction"].get("confidence"),
                    "memory_refs": [],
                },
            })
        for round_ in rounds:
            sequence += 1
            events.append({
                "sequence": sequence,
                "round": round_["round"],
                "event_type": round_["event"]["event_type"],
                "payload": round_["event"]["payload"] | {"content": round_["event"]["content"]},
                "idempotency_key": f"cycle-{round_['round']}-tick",
            })
            for interaction_index, interaction in enumerate(round_["interactions"]):
                sequence += 1
                events.append({
                    "sequence": sequence,
                    "round": round_["round"],
                    "event_type": "interaction.critique",
                    "source": interaction["source"],
                    "target": interaction["target"],
                    "payload": {"stance": interaction["stance"], "content": interaction["content"]},
                    "idempotency_key": f"cycle-{round_['round']}-interaction-{interaction_index}",
                })
            for revision in round_["revisions"]:
                entry = next(item for item in predictions if item["persona_name"] == revision["persona_name"])
                revisions.append({
                    "entity_key": entry["entity_key"],
                    "round": round_["round"],
                    "state": {
                        "prediction": revision["prediction"],
                        "confidence": revision["prediction"].get("confidence"),
                        "memory_refs": [f"cycle-{round_['round']}-tick"],
                    },
                })
        return events, revisions

    def _compute_debate_scores(
        self, predictions: List[Dict[str, Any]], convergences: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        scores: List[Dict[str, Any]] = []
        for entry in predictions:
            initial = entry.get("initial_prediction") or {}
            final = entry.get("prediction") or {}
            shift = 0.0 if initial == final else 1.0
            scores.append({
                "persona_name": entry["persona_name"],
                "name": "debate_opinion_shift",
                "value": shift,
                "comment": "1.0 quando o agente revisou a previsao apos o debate",
            })
            scores.append({
                "persona_name": entry["persona_name"],
                "name": "debate_interaction_volume",
                "value": float(len(entry.get("interactions") or [])),
                "comment": "Numero de criticas emitidas pelo agente",
            })
            confidence = entry.get("confidence")
            if isinstance(confidence, (int, float)):
                scores.append({
                    "persona_name": entry["persona_name"],
                    "name": "debate_final_confidence",
                    "value": float(confidence),
                    "comment": "Confianca declarada apos a revisao",
                })
        if convergences:
            avg = sum(c["rate"] for c in convergences) / len(convergences)
            for entry in predictions:
                scores.append({
                    "persona_name": entry["persona_name"],
                    "name": "debate_panel_convergence",
                    "value": round(avg, 2),
                    "comment": "Convergencia media do painel apos o debate",
                })
        return scores

    def _summarize_seed(self) -> str:
        if self._seed_text:
            return self._seed_text[:500]
        if not self.knowledge:
            return ""
        try:
            results = self.knowledge.search("summary of all seed data", limit=3)
            if results:
                return " ".join(str(r) for r in results)[:500]
        except Exception:
            pass
        return "Seed data available in knowledge base."

    def to_amp_payload(self, report: PredictionReport) -> Dict[str, Any]:
        return {
            "name": report.name,
            "seed_summary": report.seed_summary or (self._seed_text[:800] if self._seed_text else ""),
            "horizon_date": report.horizon,
            "scenario_params": {
                "cenario": report.scenario[:200] if report.scenario else "",
                "horizonte": str(report.horizon or ""),
                "agentes": len(report.individual_predictions),
            },
            "personas": [
                {
                    "nome": p.get("persona_name"),
                    "role": (p.get("persona_profile") or {}).get("role"),
                    "bias": (p.get("persona_profile") or {}).get("bias"),
                }
                for p in report.individual_predictions
            ],
            "report": {
                "synthesis": report.synthesis,
                "observed_outcome": report.observed_outcome,
                "accuracy_score": report.accuracy_score,
                "evaluation_reason": report.evaluation_reason,
                "convergences": report.convergences,
                "predictions": report.individual_predictions,
                "rounds": report.rounds,
                "scores": report.scores,
                "simulation": {
                    "entities": report.entities,
                    "relationships": report.relationships,
                    "events": report.events,
                    "revisions": report.revisions,
                },
                "auto_generated_personas": report.auto_generated_personas,
            },
        }

    def sync_to_amp(self, report: PredictionReport, amp_url: str, api_key: str) -> str | None:
        payload = self.to_amp_payload(report)
        try:
            import httpx
            from datetime import datetime, timezone
            headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{amp_url.rstrip('/')}/api/public/predictions",
                json=payload,
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 201:
                return None
            data = resp.json()
            self.prediction_id = data.get("id")
            pred_id = self.prediction_id
            base_url = amp_url.rstrip("/")
            entity_ids: Dict[str, str] = {}
            for entity in report.entities:
                entity_response = httpx.post(
                    f"{base_url}/api/public/predictions/{pred_id}/entities",
                    json={
                        "entity_type": entity["entity_type"],
                        "name": entity["name"],
                        "state": entity.get("state", {}),
                        "metadata": entity.get("metadata"),
                    }, headers=headers, timeout=10,
                )
                if entity_response.status_code != 201:
                    raise RuntimeError("AMP rejected a simulation entity")
                entity_ids[entity["key"]] = entity_response.json()["id"]
            for relationship in report.relationships:
                relationship_response = httpx.post(
                    f"{base_url}/api/public/predictions/{pred_id}/relationships",
                    json={
                        "source_entity_id": entity_ids[relationship["source"]],
                        "target_entity_id": entity_ids[relationship["target"]],
                        "relationship_type": relationship["relationship_type"],
                        "attributes": relationship.get("attributes", {}),
                    }, headers=headers, timeout=10,
                )
                if relationship_response.status_code != 201:
                    raise RuntimeError("AMP rejected a simulation relationship")
            round_ids: Dict[int, str] = {}
            for round_ in report.rounds:
                round_response = httpx.post(
                    f"{base_url}/api/public/predictions/{pred_id}/rounds",
                    json={"number": round_["round"], "data": {"event": round_.get("event", {})}},
                    headers=headers, timeout=10,
                )
                if round_response.status_code != 201:
                    raise RuntimeError("AMP rejected a simulation round")
                round_ids[round_["round"]] = round_response.json()["id"]
            agent_ids: Dict[str, str] = {}
            for p in report.individual_predictions:
                trace_id = f"pred_{pred_id}_{p.get('persona_name', 'agent')}"[:50].replace(" ", "_").lower()
                now = datetime.now(timezone.utc)
                httpx.post(
                    f"{amp_url.rstrip('/')}/api/public/ingestion",
                    json={"events": [{
                        "id": f"{trace_id}_start",
                        "type": "observation-start",
                        "body": {
                            "id": trace_id, "type": "TRACE",
                            "name": trace_id[:50],
                            "trace_id": trace_id,
                            "input": {"persona": p.get("persona_name")},
                            "start_time": now.isoformat(),
                        }
                    }, {
                        "id": f"{trace_id}_end",
                        "type": "observation-end",
                        "body": {
                            "id": trace_id, "type": "TRACE",
                            "trace_id": trace_id,
                            "output": {"prediction": p.get("prediction")},
                            "end_time": now.isoformat(),
                        }
                    }]},
                    headers=headers, timeout=10,
                )
                agent_payload = {
                    "persona_name": p.get("persona_name", "agent"),
                    "entity_id": entity_ids.get(p.get("entity_key", "")),
                    "persona_profile": p.get("persona_profile", {}),
                    "trace_id": trace_id,
                    "prediction": p.get("prediction"),
                    "confidence": p.get("confidence"),
                    "interactions": p.get("interactions", []),
                }
                agent_response = httpx.post(
                    f"{base_url}/api/public/predictions/{pred_id}/agents",
                    json=agent_payload, headers=headers, timeout=10,
                )
                if agent_response.status_code != 201:
                    raise RuntimeError("AMP rejected a simulation agent")
                agent_ids[p["persona_name"]] = agent_response.json()["id"]
                persona_scores = [
                    score for score in report.scores
                    if score.get("persona_name") == p.get("persona_name")
                ]
                if persona_scores:
                    for _ in range(10):
                        trace_response = httpx.get(
                            f"{amp_url.rstrip('/')}/api/public/traces/{trace_id}",
                            headers=headers, timeout=10,
                        )
                        if trace_response.status_code == 200:
                            break
                        time.sleep(0.2)
                    else:
                        continue
                    for score in persona_scores:
                        httpx.post(
                            f"{amp_url.rstrip('/')}/api/public/scores",
                            json={
                                "trace_id": trace_id,
                                "name": score["name"],
                                "value": round(float(score["value"]), 2),
                                "source": "AUTO_EVAL",
                                "comment": score.get("comment", ""),
                            }, headers=headers, timeout=10,
                        )
            for event in report.events:
                event_payload = dict(event.get("payload", {}))
                if event.get("target"):
                    target = next(
                        (p for p in report.individual_predictions if p["persona_name"] == event["target"]),
                        None,
                    )
                    if target:
                        event_payload["target_entity_id"] = entity_ids.get(target["entity_key"])
                source = next(
                    (p for p in report.individual_predictions if p["persona_name"] == event.get("source")),
                    None,
                )
                event_response = httpx.post(
                    f"{base_url}/api/public/predictions/{pred_id}/events",
                    json={
                        "event_type": event["event_type"],
                        "payload": event_payload,
                        "round_id": round_ids.get(event.get("round")),
                        "entity_id": entity_ids.get(source["entity_key"]) if source else None,
                        "agent_run_id": agent_ids.get(source["persona_name"]) if source else None,
                        "idempotency_key": event["idempotency_key"],
                    }, headers=headers, timeout=10,
                )
                if event_response.status_code != 201:
                    raise RuntimeError("AMP rejected a simulation event")
            for revision in report.revisions:
                revision_response = httpx.post(
                    f"{base_url}/api/public/predictions/{pred_id}/entities/{entity_ids[revision['entity_key']]}/revisions",
                    json={"state": revision["state"] | {"round": revision["round"]}},
                    headers=headers, timeout=10,
                )
                if revision_response.status_code != 201:
                    raise RuntimeError("AMP rejected a simulation revision")
            for round_id in round_ids.values():
                for attempt in range(3):
                    close_response = httpx.post(
                        f"{base_url}/api/public/predictions/{pred_id}/rounds/{round_id}/close",
                        headers=headers, timeout=10,
                    )
                    if close_response.status_code == 200:
                        break
                    if attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                else:
                    raise RuntimeError(
                        f"AMP rejected closing simulation round {round_id}: "
                        f"{close_response.status_code} {close_response.text}"
                    )
            for attempt in range(3):
                complete_response = httpx.post(
                    f"{amp_url.rstrip('/')}/api/public/predictions/{pred_id}/complete",
                    headers=headers, timeout=10,
                )
                if complete_response.status_code in {200, 201}:
                    break
                time.sleep(0.5 * (attempt + 1))
            else:
                raise RuntimeError(f"AMP rejected completing the prediction: {complete_response.status_code} {complete_response.text}")
            if report.accuracy_score is not None:
                for attempt in range(3):
                    evaluation_response = httpx.post(
                        f"{base_url}/api/public/predictions/{pred_id}/eval",
                        json={"accuracy_score": report.accuracy_score},
                        headers=headers, timeout=10,
                    )
                    if evaluation_response.status_code == 200:
                        break
                    time.sleep(0.5 * (attempt + 1))
                else:
                    raise RuntimeError(f"AMP rejected the observed outcome evaluation: {evaluation_response.status_code} {evaluation_response.text}")
            return pred_id
        except Exception as e:
            print(f"sync error: {e}")
        return None
