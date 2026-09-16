"""Tests for the AIPrediction multi-agent prediction engine."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from wolfpack.ai_prediction import AIPrediction, PredictionReport


class FakeModel:
    provider = "test"
    model_id = "test-model"

    def invoke(self, messages, tools=None):
        from wolfpack.models.message import Message
        content = messages[-1]["content"] if messages else "ok"
        return type("Resp", (), {"message": Message(role="assistant", content=f"prediction for: {content[:50]}"), "usage": {"input_tokens": 10, "output_tokens": 5} })()

    def stream(self, messages, tools=None):
        yield type("Chunk", (), {"content": "chunk", "response": None})()


class FakeModelWithPersonas(FakeModel):
    """Returns JSON personas when asked to generate them."""
    def invoke(self, messages, tools=None):
        content = messages[-1]["content"] if messages else "ok"
        if "persona" in content.lower() and "JSON" in content:
            json_content = json.dumps([
                {"name": "Dr. Ana", "role": "economist", "bias": "conservative", "expertise": "monetary policy"},
                {"name": "Prof. Carlos", "role": "geopolitical analyst", "bias": "contrarian", "expertise": "trade policy"},
                {"name": "Marina Silva", "role": "industry specialist", "bias": "optimistic", "expertise": "technology markets"},
            ])
        else:
            json_content = f"prediction for: {content[:50]}"
        from wolfpack.models.message import Message
        return type("Resp", (), {"message": Message(role="assistant", content=json_content), "usage": {"input_tokens": 10, "output_tokens": 5} })()


class FakeModelWithWorldGraph(FakeModel):
    def invoke(self, messages, tools=None):
        from wolfpack.models.message import Message
        content = messages[-1]["content"] if messages else ""
        payload = json.dumps({
            "entities": [
                {"name": "Lula", "type": "pessoa", "summary": "Presidente e candidato"},
                {"name": "PT", "type": "partido", "summary": "Partido de Lula"},
            ],
            "relationships": [
                {"source": "Lula", "target": "PT", "type": "filiado_a", "strength": 0.9, "evidence": "Lula e o PT disputam"},
            ],
        }) if "WORLD GRAPH" in content else "{}"
        return type("Resp", (), {"message": Message(role="assistant", content=payload), "usage": {}})()


class FakeModelWithEvaluation(FakeModel):
    def invoke(self, messages, tools=None):
        from wolfpack.models.message import Message
        content = messages[-1]["content"] if messages else ""
        payload = '{"accuracy_score": 1.0, "reason": "O vencedor previsto corresponde ao resultado observado."}' if "OBSERVED OUTCOME EVALUATION" in content else "{}"
        return type("Resp", (), {"message": Message(role="assistant", content=payload), "usage": {}})()


def test_ai_prediction_requires_personas():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "ana", "role": "analyst"}])
    assert pred.name == "test"
    assert len(pred.personas) == 1


def test_ai_prediction_raises_without_personas():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[])
    with pytest.raises(ValueError, match="No personas configured"):
        pred.run("test scenario")


def test_ai_prediction_raises_without_personas_and_no_auto():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model)
    with pytest.raises(ValueError, match="No personas configured"):
        pred.run("test scenario")


def test_ai_prediction_auto_create_personas_generates_from_knowledge():
    knowledge = MagicMock()
    knowledge.search.return_value = ["economic data shows growth trends"]
    model = FakeModelWithPersonas()
    pred = AIPrediction(name="test", model=model, auto_create_personas=True, knowledge=knowledge)
    pred.run("Will the economy grow?")
    assert len(pred.personas) == 3
    assert any("Ana" in p.get("name", "") for p in pred.personas)
    assert pred.auto_generated


def test_ai_prediction_extracts_typed_world_graph_from_seed_and_scenario():
    pred = AIPrediction(name="test", model=FakeModelWithWorldGraph(), personas=[{"name": "Ana", "role": "analista"}])
    pred.ingest_seed(text="Lula e o PT disputam a eleicao.")

    entities, relationships = pred._extract_world_graph("Quem vence a eleicao?")

    assert [entity["name"] for entity in entities] == ["Lula", "PT"]
    assert relationships == [{
        "source": entities[0]["key"], "target": entities[1]["key"],
        "relationship_type": "filiado_a", "attributes": {"strength": 0.9, "evidence": "Lula e o PT disputam"},
    }]


def test_ai_prediction_evaluates_observed_outcome_and_records_audit_fields():
    predictor = AIPrediction(name="test", model=FakeModelWithEvaluation(), personas=[{"name": "Ana", "role": "analista"}])
    report = PredictionReport(name="test", prediction_id="prediction", scenario="cenário", synthesis="Lula vence.")

    score = predictor.evaluate_observed_outcome(report, "Lula venceu a eleição.")

    assert score == 1.0
    assert report.accuracy_score == 1.0
    assert report.observed_outcome == "Lula venceu a eleição."
    assert report.evaluation_reason == "O vencedor previsto corresponde ao resultado observado."


def test_persona_generation_uses_scenario_ingested_seed_and_knowledge():
    knowledge = MagicMock()
    knowledge.search.return_value = ["Pesquisa indica que emprego e inflacao definem o voto."]
    model = FakeModelWithPersonas()
    model.invoke = MagicMock(wraps=model.invoke)
    pred = AIPrediction(name="test", model=model, auto_create_personas=True, knowledge=knowledge)
    pred.ingest_seed(text="O candidato A tem vantagem entre jovens urbanos.")

    pred._generate_personas_from_knowledge("Quem vence a eleicao diante da alta inflacao?")

    prompt = model.invoke.call_args.args[0][-1]["content"]
    assert "Quem vence a eleicao diante da alta inflacao?" in prompt
    assert "vantagem entre jovens urbanos" in prompt
    assert "emprego e inflacao definem o voto" in prompt


def test_ai_prediction_auto_create_personas_augments_existing():
    knowledge = MagicMock()
    knowledge.search.return_value = ["market data"]
    model = FakeModelWithPersonas()
    pred = AIPrediction(
        name="test", model=model,
        personas=[{"name": "Custom Expert", "role": "analyst", "bias": "neutral", "expertise": "markets"}],
        auto_create_personas=True, knowledge=knowledge,
    )
    pred.run("test scenario")
    # Should have custom + auto-generated (without name overlap)
    names = [p.get("name", "") for p in pred.personas]
    assert "Custom Expert" in names
    assert len(pred.personas) >= 4


def test_ai_prediction_raises_when_persona_generation_returns_nothing():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, auto_create_personas=True)
    with pytest.raises(ValueError, match="persona"):
        pred.run("test scenario")


def test_ai_prediction_has_no_persona_fallback():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    assert not hasattr(pred, "_fallback_personas")


def test_ai_prediction_extract_seed_context():
    knowledge = MagicMock()
    knowledge.search.return_value = ["doc1 about economics", "doc2 about policy"]
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}], knowledge=knowledge)
    ctx = pred._extract_seed_context()
    assert "doc1" in ctx
    assert "doc2" in ctx


def test_ai_prediction_extract_seed_context_no_knowledge():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    assert pred._extract_seed_context() == "No seed data available."


def test_ai_prediction_extract_seed_context_error():
    knowledge = MagicMock()
    knowledge.search.side_effect = Exception("fail")
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}], knowledge=knowledge)
    assert "Seed data available" in pred._extract_seed_context()


def test_ai_prediction_parse_persona_json_valid():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    content = '[{"name": "Ana", "role": "economist", "bias": "conservative", "expertise": "policy"}]'
    parsed = pred._parse_persona_json(content)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "Ana"


def test_ai_prediction_parse_persona_json_with_markdown_wrapper():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    content = 'Some text\n```json\n[{"name": "Ana", "role": "economist"}]\n```\nmore text'
    parsed = pred._parse_persona_json(content)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "Ana"


def test_ai_prediction_parse_persona_json_invalid():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    parsed = pred._parse_persona_json("not json at all")
    assert parsed == []


def test_ai_prediction_parse_persona_json_empty():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    parsed = pred._parse_persona_json("[]")
    assert parsed == []


def test_ai_prediction_rejects_partial_persona_payload():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    assert pred._parse_persona_json('[{"name": "Ana"}]') == []


def test_ai_prediction_persona_count_clamp():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}], persona_count=1)
    assert pred.persona_count == 2
    pred2 = AIPrediction(name="test", model=model, personas=[{"name": "a"}], persona_count=10)
    assert pred2.persona_count == 8


def test_ai_prediction_auto_generated_flag_in_report():
    knowledge = MagicMock()
    knowledge.search.return_value = ["seed data"]
    model = FakeModelWithPersonas()
    pred = AIPrediction(name="test", model=model, auto_create_personas=True, knowledge=knowledge)
    report = pred.run("test scenario")
    assert report.auto_generated_personas


def test_ai_prediction_report_auto_generated_flag_false_by_default():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a", "role": "analyst"}])
    report = pred.run("test scenario")
    assert not report.auto_generated_personas


def test_ai_prediction_build_persona_prompt():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[], horizon="2026-10-01")
    prompt = pred._build_persona_prompt({"name": "Ana", "role": "economist", "bias": "conservative"})
    assert "Ana" in prompt
    assert "economist" in prompt
    assert "conservative" in prompt
    assert "2026-10-01" in prompt


def test_ai_prediction_compute_convergences():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[])
    predictions = [
        {"persona_name": "A", "prediction": {"a": "x", "b": "y"}},
        {"persona_name": "B", "prediction": {"a": "x", "b": "z"}},
    ]
    c = pred._compute_convergences(predictions)
    assert len(c) == 1
    assert c[0]["rate"] == 0.5
    assert c[0]["agents"] == ["A", "B"]


def test_ai_prediction_compute_convergences_full_match():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[])
    predictions = [
        {"persona_name": "A", "prediction": {"a": "x", "b": "y"}},
        {"persona_name": "B", "prediction": {"a": "x", "b": "y"}},
    ]
    c = pred._compute_convergences(predictions)
    assert len(c) == 1
    assert c[0]["rate"] == 1.0


def test_ai_prediction_compute_convergences_no_match():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[])
    predictions = [
        {"persona_name": "A", "prediction": {"a": "x"}},
        {"persona_name": "B", "prediction": {"b": "y"}},
    ]
    c = pred._compute_convergences(predictions)
    assert len(c) == 0


def test_ai_prediction_compute_convergences_non_dict():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[])
    predictions = [
        {"persona_name": "A", "prediction": "string prediction"},
        {"persona_name": "B", "prediction": {"a": "x"}},
    ]
    c = pred._compute_convergences(predictions)
    assert len(c) == 0


def test_ai_prediction_ingest_seed_text():
    knowledge = MagicMock()
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}], knowledge=knowledge)
    pred.ingest_seed(text="economic data shows growth")
    knowledge.add_text.assert_called_once_with(
        "economic data shows growth",
        metadata={"source": "seed", "prediction": "test"},
    )


def test_ai_prediction_ingest_seed_path(tmp_path):
    knowledge = MagicMock()
    seed_file = tmp_path / "report.md"
    seed_file.write_text("conteudo do relatorio")
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}], knowledge=knowledge)
    pred.ingest_seed(path=str(seed_file))
    knowledge.add_from_path.assert_called_once_with(str(seed_file))
    assert pred._seed_text == "conteudo do relatorio"


def test_ai_prediction_to_amp_payload():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"nome": "a", "role": "analyst"}], horizon="2026-10-01")
    report = PredictionReport(
        name="test",
        prediction_id="abc123",
        scenario="SELIC at 15%",
        horizon="2026-10-01",
        seed_summary="economic data",
        individual_predictions=[{"persona_name": "A", "prediction": "up", "persona_profile": {"role": "analyst"}}],
        convergences=[{"agents": ["A", "B"], "rate": 0.8}],
        synthesis="Consensus: growth",
        auto_generated_personas=True,
    )
    payload = pred.to_amp_payload(report)
    assert payload["name"] == "test"
    assert payload["horizon_date"] == "2026-10-01"
    assert len(payload["personas"]) == 1
    assert payload["report"]["synthesis"] == "Consensus: growth"
    assert payload["report"]["auto_generated_personas"] is True


def test_ai_prediction_sync_to_amp_success():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    report = PredictionReport(name="test", prediction_id="abc", scenario="test")
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": "amp-123"}
        result = pred.sync_to_amp(report, "http://localhost:8000", "api-key")
        assert result == "amp-123"
        assert pred.prediction_id == "amp-123"


def test_ai_prediction_sync_to_amp_does_not_mark_convergence_as_accuracy():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    report = PredictionReport(
        name="test",
        prediction_id="abc",
        scenario="test",
        scores=[{"persona_name": "a", "name": "debate_panel_convergence", "value": 0.8}],
    )
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": "amp-123"}
        pred.sync_to_amp(report, "http://localhost:8000", "api-key")
    assert not any(call.args[0].endswith("/eval") for call in mock_post.call_args_list)


def test_ai_prediction_sync_to_amp_failure():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    report = PredictionReport(name="test", prediction_id="abc", scenario="test")
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 400
        result = pred.sync_to_amp(report, "http://localhost:8000", "api-key")
        assert result is None


def test_ai_prediction_sync_to_amp_connection_error():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    report = PredictionReport(name="test", prediction_id="abc", scenario="test")
    with patch("httpx.post", side_effect=Exception("connection refused")):
        result = pred.sync_to_amp(report, "http://localhost:8000", "api-key")
        assert result is None


def test_prediction_report_dataclass():
    report = PredictionReport(
        name="test",
        prediction_id="abc",
        scenario="SELIC rise",
        seed_summary="Economic report",
        horizon="2026-Q4",
    )
    assert report.name == "test"
    assert report.prediction_id == "abc"
    assert report.scenario == "SELIC rise"
    assert report.seed_summary == "Economic report"
    assert report.horizon == "2026-Q4"
    assert report.status == "completed"


def test_prediction_report_defaults():
    report = PredictionReport(name="x", prediction_id="y", scenario="z")
    assert report.individual_predictions == []
    assert report.convergences == []
    assert report.synthesis == ""
    assert report.status == "completed"
    assert not report.auto_generated_personas


def test_ai_prediction_build_synthesis_prompt():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[])
    prompt = pred._build_synthesis_prompt("test scenario", [
        {"persona_name": "A", "prediction": {"outcome": "up"}},
    ])
    assert "test scenario" in prompt
    assert "Executive Summary" in prompt
    assert "Consensus View" in prompt


def test_ai_prediction_summarize_seed_with_knowledge():
    knowledge = MagicMock()
    knowledge.search.return_value = ["doc1 summary", "doc2 summary"]
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}], knowledge=knowledge)
    summary = pred._summarize_seed()
    assert "doc1 summary" in summary


def test_ai_prediction_summarize_seed_no_knowledge():
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}])
    assert pred._summarize_seed() == ""


def test_ai_prediction_summarize_seed_error():
    knowledge = MagicMock()
    knowledge.search.side_effect = Exception("search failed")
    model = FakeModel()
    pred = AIPrediction(name="test", model=model, personas=[{"name": "a"}], knowledge=knowledge)
    assert pred._summarize_seed() == "Seed data available in knowledge base."

class DebateModel(FakeModel):
    """Scripted model that answers persona generation, forecast, critique and revision."""

    def __init__(self):
        self.prompts: list[str] = []

    def invoke(self, messages, tools=None):
        from wolfpack.models.message import Message

        content = ""
        for message in messages:
            if message.get("role") == "system":
                content = message.get("content") or content
        user_content = messages[-1].get("content") or ""
        self.prompts.append(user_content)
        joined = f"{content}\n{user_content}"

        if "persona" in joined.lower() and "JSON array" in joined:
            payload = json.dumps([
                {"name": "Ana", "role": "economista", "bias": "otimista", "expertise": "macro"},
                {"name": "Bruno", "role": "cientista politico", "bias": "cetico", "expertise": "eleicoes"},
            ])
        elif "CRITIQUE" in joined:
            author = "Ana" if "You are Ana." in content else "Bruno"
            target = "Bruno" if author == "Ana" else "Ana"
            payload = json.dumps([
                {"target": target, "stance": "discorda", "argument": f"{author} contesta {target}"}
            ])
        elif "REVISE" in joined:
            payload = json.dumps({"forecast": "revisado", "confidence": 0.8})
        elif "synthesis analyst" in joined or "sintese" in joined.lower():
            payload = "# Relatorio\n\n## Consenso\n**Ana** e **Bruno** convergem."
        else:
            payload = json.dumps({"forecast": "inicial", "confidence": 0.6})

        return type("Resp", (), {
            "message": Message(role="assistant", content=payload),
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })()


def test_ai_prediction_runs_debate_rounds():
    pred = AIPrediction(name="debate", model=DebateModel(), auto_create_personas=True, debate_rounds=1)
    report = pred.run("Cenario eleitoral")
    assert report.rounds
    assert report.rounds[0]["round"] == 1


def test_ai_prediction_builds_replayable_social_simulation_ledger():
    pred = AIPrediction(name="debate", model=DebateModel(), auto_create_personas=True, debate_rounds=1)
    report = pred.run("Cenario eleitoral")

    assert len(report.entities) == 2
    assert len(report.relationships) == 2
    assert report.events[0]["event_type"] == "scenario.injected"
    assert report.events[0]["round"] == 1
    assert len(report.revisions) >= len(report.entities)
    assert report.rounds[0]["event"]["event_type"] == "scenario.injected"


def test_ai_prediction_records_interactions_between_agents():
    pred = AIPrediction(name="debate", model=DebateModel(), auto_create_personas=True, debate_rounds=1)
    report = pred.run("Cenario eleitoral")
    interactions = [i for p in report.individual_predictions for i in p["interactions"]]
    assert interactions
    assert {i["target"] for i in interactions} <= {"Ana", "Bruno"}
    assert all(i["round"] >= 1 for i in interactions)


def test_ai_prediction_keeps_initial_and_revised_predictions():
    pred = AIPrediction(name="debate", model=DebateModel(), auto_create_personas=True, debate_rounds=1)
    report = pred.run("Cenario eleitoral")
    first = report.individual_predictions[0]
    assert first["initial_prediction"]["forecast"] == "inicial"
    assert first["prediction"]["forecast"] == "revisado"
    assert first["confidence"] == 0.8


def test_ai_prediction_debate_scores_reflect_opinion_shift():
    pred = AIPrediction(name="debate", model=DebateModel(), auto_create_personas=True, debate_rounds=1)
    report = pred.run("Cenario eleitoral")
    names = {s["name"] for s in report.scores}
    assert "debate_opinion_shift" in names
    assert "debate_interaction_volume" in names


def test_ai_prediction_debate_rounds_zero_skips_interaction():
    pred = AIPrediction(name="debate", model=DebateModel(), auto_create_personas=True, debate_rounds=0)
    report = pred.run("Cenario eleitoral")
    assert report.rounds == []
    assert all(p["interactions"] == [] for p in report.individual_predictions)
