"""21_predictions/01_ai_prediction.py — AIPrediction with deterministic model.

Run from the framework directory:
    uv run python examples/21_predictions/01_ai_prediction.py

This example demonstrates the full AIPrediction flow with a deterministic
model, so it needs no API keys or external services. It covers:
- Persona generation from seed material
- Multi-agent debate with critique rounds
- Social graph extraction with typed entities and evidence
- Observed-outcome evaluation with accuracy scoring
- Prediction report with synthesis, convergences, and scores
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack.ai_prediction import AIPrediction, PredictionReport
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message


class DeterministicPredictionModel(BaseModel):
    """Returns canned responses for each step of the prediction pipeline."""

    provider = "deterministic"
    model_id = "prediction-demo-v1"

    _call_count = 0

    def invoke(self, messages, tools=None):
        content = messages[-1]["content"] if messages else ""
        self.__class__._call_count += 1
        n = self.__class__._call_count

        # Persona generation
        if "PERSONA" in content.upper() and "JSON" in content.upper():
            payload = json.dumps([
                {"name": "Dr. Ana", "role": "economist", "bias": "conservative", "expertise": "macroeconomia"},
                {"name": "Prof. Carlos", "role": "political analyst", "bias": "contrarian", "expertise": "ciencia politica"},
            ])

        # World graph extraction
        elif "WORLD GRAPH" in content.upper():
            payload = json.dumps({
                "entities": [
                    {"name": "Candidato Alfa", "type": "Candidato", "summary": "Atual prefeito, favorito nas pesquisas"},
                    {"name": "Candidato Beta", "type": "Candidato", "summary": "Opositor, crescimento entre jovens"},
                    {"name": "Instituto X", "type": "Instituto de pesquisa", "summary": "Pesquisa mais recente mostra empate tecnico"},
                ],
                "relationships": [
                    {"source": "Candidato Alfa", "target": "Candidato Beta", "type": "Adversario", "strength": 0.8, "evidence": "Pesquisa mostra empate tecnico entre os dois candidatos."},
                    {"source": "Instituto X", "target": "Candidato Alfa", "type": "Resultado de pesquisa", "strength": 0.6, "evidence": "Instituto X divulga pesquisa com empate tecnico."},
                ],
            })

        # Debate rounds (individual prediction)
        elif n == 3:
            payload = json.dumps({
                "prediction": "Candidato Alfa vence com 52% dos votos.",
                "confidence": 0.75,
                "reasoning": "Base fiel e maior tempo de TV.",
            })
        elif n == 4:
            payload = json.dumps({
                "prediction": "Candidato Beta vence com 51% dos votos.",
                "confidence": 0.60,
                "reasoning": "Crescimento entre jovens e rejeicao menor.",
            })

        # Debate critique rounds
        elif "CRITIQUE" in content.upper() or "critique" in content:
            payload = json.dumps({
                "revised_prediction": "Candidato Alfa vence, margem entre 50 e 53%.",
                "confidence": 0.72,
                "reasoning": "Apos debate, mantenho a projecao com ajuste na margem.",
            })

        # Evaluation
        elif "OBSERVED OUTCOME EVALUATION" in content.upper():
            payload = json.dumps({
                "accuracy_score": 1.0,
                "reason": "A previsao de vitoria do Candidato Alfa corresponde ao resultado observado.",
            })

        # Synthesis
        elif "SYNTHESIS" in content.upper() or "synthesis" in content:
            payload = "Previsao consolidada: Candidato Alfa vence a eleicao."
        else:
            payload = "{}"

        return ModelResponse(
            Message(role="assistant", content=payload),
            usage={"input_tokens": 10, "output_tokens": 8},
        )


def main():
    model = DeterministicPredictionModel()
    predictor = AIPrediction(
        name="predicao-eleitoral",
        model=model,
        auto_create_personas=False,
        personas=[
            {"name": "Dr. Ana", "role": "economist", "bias": "conservative", "expertise": "macroeconomia"},
            {"name": "Prof. Carlos", "role": "political analyst", "bias": "contrarian", "expertise": "ciencia politica"},
        ],
        debate_rounds=3,
        horizon="2026-10-04",
    )

    predictor.ingest_seed(
        text=(
            "Eleicao municipal na cidade de Exemplopolis. Pesquisa do Instituto X "
            "divulgada hoje mostra empate tecnico entre o Candidato Alfa (42%) e o "
            "Candidato Beta (41%), margem de erro 3 pp. Alfa e o atual prefeito e "
            "tem maior tempo de TV. Beta cresce entre eleitores jovens."
        )
    )

    scenario = (
        "Cenario: Eleicao municipal em Exemplopolis. Candidato Alfa (atual prefeito) "
        "vs Candidato Beta (opositor). Instituto X mostra empate tecnico. "
        "Quem vence a eleicao? Aponte um unico vencedor."
    )

    observed_outcome = (
        "Candidato Alfa venceu a eleicao municipal de Exemplopolis em 2026 "
        "com 52,3% dos votos validos, contra 47,7% do Candidato Beta."
    )

    report = predictor.run(scenario, observed_outcome=observed_outcome)

    print("=" * 60)
    print("RESULTADO DA PREDICAO")
    print("=" * 60)
    print(f"Previsao: {report.name}")
    print(f"Personas: {len(predictor.personas)}")
    for p in predictor.personas:
        print(f"  - {p['name']}: {p['role']} ({p['bias']})")
    print(f"\nEntidades extraidas do seed: {len(report.entities)}")
    for e in report.entities:
        print(f"  - {e['name']} ({e['entity_type']})")
    print(f"\nRelacoes extraidas: {len(report.relationships)}")
    for r in report.relationships:
        rel = json.dumps(r.get("attributes", {}))
        print(f"  - {r['source']} -> {r['target']}: {r['relationship_type']} {rel}")
    print(f"\nRodadas de debate: {len(report.rounds)}")
    for i, r in enumerate(report.rounds):
        event = r.get("event", r.get("data", {}))
        print(f"  Rodada {i+1}: {event.get('event_type', 'N/A')}")
    print(f"\nEventos da simulacao: {len(report.events)}")
    print(f"Revisoes de estado: {len(report.revisions)}")
    print(f"Scores de debate: {len(report.scores)}")
    print(f"\nAcuracia: {report.accuracy_score:.0%}")
    print(f"Justificativa: {report.evaluation_reason}")
    print(f"\nObservado: {report.observed_outcome}")
    print("=" * 60)
    print("OK: Predicao concluida com avaliacao automatica.")


if __name__ == "__main__":
    main()