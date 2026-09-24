"""Exemplo real de uso do AIPrediction com Wolfpack AI.
Gera previsão sobre as Eleições 2026 usando LLM + auto_create_personas."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "framework"))

from wolfpack import AIPrediction, get_model_from_env

SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "docker", "seed_eleicoes_2026.md")
AMP_URL = "http://localhost:8000"
AMP_API_KEY = "pk-wp-dev:dev-secret"

print("=" * 60)
print("WOLFPACK AI -- AIPrediction Demo")
print("Eleicoes Presidenciais Brasil 2026")
print("=" * 60)

model = get_model_from_env()
print(f"Modelo: {model.provider}:{model.model_id}")

predictor = AIPrediction(
    name="eleicoes-2026-ai",
    model=model,
    auto_create_personas=True,
    persona_count=4,
    horizon="2026-10-04",
    max_iterations=8,
)
print("AIPrediction criado com auto_create_personas=True")

seed_text = open(SEED_PATH).read()
predictor.ingest_seed(text=seed_text[:15000])
print(f"Seed carregado: {len(seed_text)} chars")

print("\nExecutando predicao multi-agente (pode levar 2-5 min)...\n")

scenario = (
    "Cenario: Eleicoes Presidenciais Brasileiras de 2026. "
    "Lula (PT) busca reeleicao contra Flavio Bolsonaro (PL). "
    "Crise no STF com julgamento Moraes-Vorcaro. "
    "Datafolha mostra Lula 32-55% e Flavio 24-40%. "
    "Qual o resultado mais provavel?"
)

report = predictor.run(scenario)

print(f"\n{'='*60}")
print(f"PREDICAO CONCLUIDA!")
print(f"{'='*60}")
print(f"Nome: {report.name}")
print(f"ID: {report.prediction_id}")
print(f"Personas: {len(predictor.personas)}")
for i, p in enumerate(predictor.personas):
    print(f"  {i+1}. {p.get('name')}: {p.get('role')} ({p.get('bias')})")

if report.convergences:
    print(f"\nConvergencias:")
    for c in report.convergences[:5]:
        print(f"  - {c['agents'][0]} x {c['agents'][1]}: {c['rate']:.0%}")

print(f"\nSintese ({len(report.synthesis)} chars):")
print(report.synthesis[:800] + ("..." if len(report.synthesis) > 800 else ""))

print(f"\nSincronizando com AMP ({AMP_URL})...")
pred_id = predictor.sync_to_amp(report, AMP_URL, AMP_API_KEY)
if pred_id:
    print(f"OK! ID AMP: {pred_id}")
    print(f"URL: {AMP_URL.replace('8000', '5173')}/predictions/{pred_id}")
else:
    print("Falha ao sincronizar com AMP")

print(f"\n{'='*60}")
print("Demo concluido!")
print("=" * 60)