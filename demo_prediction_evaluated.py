"""Retrospectiva avaliada: demonstra a avaliação automática no AIPrediction."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "framework"))

from wolfpack import AIPrediction, get_model_from_env


SEED_PATH = os.path.join(os.path.dirname(__file__), "docker", "seed_eleicoes_2022.md")
AMP_URL = os.environ.get("AMP_URL", "http://localhost:8000")
AMP_API_KEY = os.environ.get("AMP_API_KEY", "pk-wp-dev:dev-secret")
OBSERVED_OUTCOME = (
    "Luiz Inácio Lula da Silva venceu o segundo turno de 2022 com 50,90% dos votos válidos; "
    "Jair Bolsonaro recebeu 49,10%."
)


model = get_model_from_env()
predictor = AIPrediction(
    name="eleicoes-2022-retrospectiva",
    model=model,
    auto_create_personas=True,
    persona_count=4,
    debate_rounds=3,
    horizon="2022-10-30",
)
seed_text = open(SEED_PATH).read()
predictor.ingest_seed(text=seed_text)

scenario = (
    "Em 27 de outubro de 2022, antes do segundo turno, qual candidato tem maior "
    "probabilidade de vencer a eleição presidencial brasileira? Aponte um único vencedor."
)
report = predictor.run(scenario, observed_outcome=OBSERVED_OUTCOME)
prediction_id = predictor.sync_to_amp(report, AMP_URL, AMP_API_KEY)
if not prediction_id:
    raise RuntimeError("Não foi possível sincronizar a previsão com o AMP")

print(f"Resultado observado: {OBSERVED_OUTCOME}")
print(f"Acurácia: {report.accuracy_score:.0%}")
print(f"Justificativa: {report.evaluation_reason}")
print(f"URL: {AMP_URL.replace('8000', '5173')}/predictions/{prediction_id}")
