"""Predição Eleições 2026 com outcome declarado e avaliação de acurácia.
Mostra por que o resultado esperado faz (ou não) sentido diante da simulação."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "framework"))

from wolfpack import AIPrediction, get_model_from_env

SEED_PATH = os.path.join(os.path.dirname(__file__), "docker", "seed_eleicoes_2026.md")
AMP_URL = os.environ.get("AMP_URL", "http://localhost:8000")
AMP_API_KEY = os.environ.get("AMP_API_KEY", "pk-wp-dev:dev-secret")

# Outcome declarado — crença do usuário antes da simulação
OUTCOME_DECLARADO = (
    "Lula (PT) vence a eleição presidencial de 2026, derrotando Flávio Bolsonaro (PL) "
    "no segundo turno. Lula mantém a dianteira com vantagem consistente ao longo da "
    "campanha, beneficiado pela base fiel do PT e pela fragmentação da direita."
)

model = get_model_from_env()
predictor = AIPrediction(
    name="eleicoes-2026-outcome",
    model=model,
    auto_create_personas=True,
    persona_count=4,
    debate_rounds=3,
    horizon="2026-10-04",
)

seed_text = open(SEED_PATH).read()
predictor.ingest_seed(text=seed_text)

scenario = (
    "Considerando o cenário eleitoral brasileiro de 2026 com Lula (PT) buscando "
    "reeleição contra Flávio Bolsonaro (PL), crise no STF, Datafolha mostrando "
    "disputa regional acirrada, e terceira via fragmentada (Caiado, Zema, Cury), "
    "quem vencerá a eleição e com qual margem?"
)

print("=" * 60)
print("PREDIÇÃO ELEIÇÕES 2026 — COM OUTCOME DECLARADO")
print("=" * 60)
print(f"\nOutcome declarado:\n{OUTCOME_DECLARADO}\n")
print("Executando simulação multi-agente...\n")

report = predictor.run(scenario, observed_outcome=OUTCOME_DECLARADO)

print("Simulação concluída.\n")
print(f"Acurácia: {report.accuracy_score:.0%}")
print(f"Justificativa: {report.evaluation_reason}\n")

print("O outcome declarado FAZ SENTIDO?")

if report.accuracy_score is not None:
    if report.accuracy_score >= 0.7:
        print("  ✅ SIM — a simulação converge com o resultado esperado.")
    elif report.accuracy_score >= 0.3:
        print("  ⚠️ PARCIALMENTE — a simulação mostra pontos de convergência e divergência.")
    else:
        print("  ❌ NÃO — a simulação contradiz o resultado esperado.")
    print(f"  A simulação acertou {report.accuracy_score:.0%} do que foi declarado.")
else:
    print("  Não foi possível avaliar.")

print(f"\nSincronizando com AMP ({AMP_URL})...")
pred_id = predictor.sync_to_amp(report, AMP_URL, AMP_API_KEY)
if pred_id:
    print(f"OK! ID AMP: {pred_id}")
    print(f"URL: {AMP_URL.replace('8000', '5173')}/predictions/{pred_id}")
    print(f"Status: evaluated | Acurácia: {report.accuracy_score:.0%}")
    if report.evaluation_reason:
        print(f"\nAnálise do avaliador:\n{report.evaluation_reason}")
else:
    print("Falha ao sincronizar")

print("\n" + "=" * 60)
print("Conclusão: a acurácia compara a simulação ao outcome declarado.")
print("Se for alta, o cenário simulado valida a hipótese.")
print("Se for baixa, a simulação sugere que o resultado pode ser diferente.")
print("=" * 60)