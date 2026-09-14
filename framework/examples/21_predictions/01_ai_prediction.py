"""21_predictions/01_ai_prediction.py — AIPrediction with auto personas and outcome evaluation.

Run from the framework directory:
    uv run python examples/21_predictions/01_ai_prediction.py

This example uses a deterministic model so no API keys are needed.
It demonstrates:
- Markdown seed ingestion
- Auto-generated personas from the seed
- Multi-agent prediction with debate rounds
- World graph extraction with typed entities and evidence
- Observed-outcome evaluation with accuracy score
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack.ai_prediction import AIPrediction, PredictionReport
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message

SEED_MD = """
# Previsao: Loteamento Novo Horizonte

## Contexto

A cidade de Nova Esperanca vai leiloar uma area de 50 hectares na zona
norte para loteamento urbano. Duas construtoras disputam o terreno:
a Construtora Alvorada e a Construtora Novo Rumo.

## Dados

- Area total: 50 hectares
- Projecao de unidades: 1.200 lotes
- Investimento inicial estimado: R$ 80 milhoes
- Retorno esperado em 5 anos: R$ 200 milhoes
- Alvorada: maior porte, mais experiente, proposta de R$ 45 milhoes
- Novo Rumo: menor porte, proposta de R$ 42 milhoes, financiamento inovador

## Historico

A Alvorada ja venceu 3 leiloes municipais nos ultimos 5 anos. A Novo Rumo
venceu 1 leilao, mas tem boa reputacao no mercado.
"""

SCENARIO = (
    "Cenario: Leilao do loteamento Novo Horizonte em Nova Esperanca. "
    "Construtora Alvorada (proposta R$ 45 mi) vs Construtora Novo Rumo "
    "(proposta R$ 42 mi). Qual construtora vence o leilao?"
)

OBSERVED_OUTCOME = (
    "A Construtora Alvorada venceu o leilao do loteamento Novo Horizonte "
    "com a proposta de R$ 45 milhoes, confirmando seu historico de "
    "vitorias em leiloes municipais."
)


class DeterministicPredictionModel(BaseModel):
    provider = "deterministic"
    model_id = "prediction-demo-v1"
    _call_count = 0

    def invoke(self, messages, tools=None):
        content = messages[-1]["content"] if messages else ""
        self.__class__._call_count += 1
        n = self.__class__._call_count

        if "persona" in content.lower() and "json" in content.lower():
            payload = json.dumps([
                {"name": "Dra. Marcia", "role": "analista de mercado imobiliario", "bias": "conservadora", "expertise": "loteamentos e financiamento urbano"},
                {"name": "Dr. Renato", "role": "especialista em licitacoes publicas", "bias": "pragmatico", "expertise": "leiloes e contratos municipais"},
            ])

        elif "world graph" in content.lower():
            payload = json.dumps({
                "entities": [
                    {"name": "Construtora Alvorada", "type": "Empresa", "summary": "Maior porte, proposta de R$ 45 mi"},
                    {"name": "Construtora Novo Rumo", "type": "Empresa", "summary": "Menor porte, proposta de R$ 42 mi"},
                    {"name": "Prefeitura de Nova Esperanca", "type": "Orgao publico", "summary": "Realiza o leilao do loteamento"},
                ],
                "relationships": [
                    {"source": "Construtora Alvorada", "target": "Construtora Novo Rumo", "type": "Concorrente", "strength": 0.7, "evidence": "Disputam o mesmo loteamento de 50 hectares."},
                    {"source": "Construtora Alvorada", "target": "Prefeitura de Nova Esperanca", "type": "Proponente", "strength": 0.8, "evidence": "Alvorada ofereceu R$ 45 mi pelo terreno."},
                    {"source": "Construtora Novo Rumo", "target": "Prefeitura de Nova Esperanca", "type": "Proponente", "strength": 0.6, "evidence": "Novo Rumo ofereceu R$ 42 mi."},
                ],
            })

        elif "observed outcome evaluation" in content.lower():
            payload = json.dumps({
                "accuracy_score": 1.0,
                "reason": "A previsao de vitoria da Construtora Alvorada corresponde ao resultado observado.",
            })

        elif "synthesis" in content.lower():
            payload = "Previsao: Construtora Alvorada vence o leilao do Novo Horizonte."

        else:
            payload = json.dumps({
                "prediction": "Construtora Alvorada vence o leilao.",
                "confidence": 0.75,
                "reasoning": "Proposta mais alta e historico favoravel.",
            })

        return ModelResponse(Message(role="assistant", content=payload), usage={"input_tokens": 10, "output_tokens": 5})


def main():
    model = DeterministicPredictionModel()
    predictor = AIPrediction(
        name="leilao-novo-horizonte",
        model=model,
        auto_create_personas=True,
        persona_count=2,
        debate_rounds=2,
        horizon="2026-12-15",
    )
    predictor.ingest_seed(text=SEED_MD)

    report = predictor.run(SCENARIO, observed_outcome=OBSERVED_OUTCOME)

    status = "\u2705" if report.accuracy_score == 1.0 else "\u274c"

    print("=" * 60)
    print("PREDICAO: LOTEAMENTO NOVO HORIZONTE")
    print("=" * 60)
    print(f"Personas auto-geradas: {len(predictor.personas)}")
    for p in predictor.personas:
        print(f"  - {p['name']}: {p['role']} ({p['bias']})")
    print(f"\nEntidades extraidas do seed: {len(report.entities)}")
    for e in report.entities:
        src = e.get("metadata", {}).get("source", "")
        print(f"  - {e['name']} ({e['entity_type']}) [{src}]")
    print(f"\nRelacoes extraidas:")
    for r in report.relationships:
        ev = r.get("attributes", {}).get("evidence", "")
        print(f"  - {r['source']} -> {r['target']}: {r['relationship_type']}")
        if ev:
            print(f"    Evidencia: \"{ev}\"")
    print(f"\nResultado:")
    print(f"  Acuracia: {report.accuracy_score:.0%} {status}")
    print(f"  Justificativa: {report.evaluation_reason}")

    print(f"\n--- RELATORIO SINTETIZADO ---")
    print(report.synthesis[:1200] if report.synthesis else "(vazio)")
    if len(report.synthesis) > 1200:
        print("... (truncado)")

    print(f"\n--- ITERACOES DO DEBATE ({len(report.rounds)} rodadas) ---")
    for i, r in enumerate(report.rounds):
        event = r.get("event", r.get("data", {}))
        etype = event.get("event_type", "N/A")
        content = event.get("content", "")
        print(f"\nRodada {i+1} [{etype}]:")
        print(f"  {content[:600]}")
        if len(content) > 600:
            print("  ...")

    print("=" * 60)
    print("OK: Exemplo concluido sem dependencia de API externa.")


if __name__ == "__main__":
    main()