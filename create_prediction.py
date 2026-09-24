"""Recria predição eleitoral 2026 completa com scores e traces."""
import httpx
import json
import uuid

AMP = "http://localhost:8000"
KEY = "pk-wp-dev:dev-secret"
H = {"X-API-Key": KEY, "Content-Type": "application/json"}

def api(method, path, **kw):
    fn = getattr(httpx, method)
    r = fn(f"{AMP}{path}", headers=H, timeout=10, **kw)
    return r.json()

# 0. Apagar predições anteriores
prev = api("get", "/api/public/predictions")
for p in prev.get("predictions", []):
    api("delete", f"/api/public/predictions/{p['id']}")
print("✓ Limpeza concluída")

# 1. Criar traces reais para cada agente
traces = {}
for nome, sid in [("Cientista Político", "eleicoes-session"),
                   ("Estrategista", "eleicoes-session"),
                   ("Macroeconomista", "eleicoes-session")]:
    tid = uuid.uuid4().hex
    api("post", "/api/public/ingestion", json={"events": [{
        "id": f"trace_{tid}_start",
        "type": "observation-start",
        "body": {
            "id": tid,
            "type": "TRACE",
            "name": f"prediction_{nome.lower().replace(' ','_')}",
            "trace_id": tid,
            "session_id": sid,
            "environment": "prediction",
            "input": {"persona": nome, "scenario": "Eleições 2026"},
            "start_time": "2026-09-13T20:00:00Z",
        }
    }, {
        "id": f"trace_{tid}_end",
        "type": "observation-end",
        "body": {
            "id": tid,
            "type": "TRACE",
            "trace_id": tid,
            "output": {"prediction_complete": True},
            "end_time": "2026-09-13T20:01:00Z",
        }
    }]})
    traces[nome] = tid
print(f"✓ {len(traces)} traces criados")

# 2. Criar scores para cada trace
for nome, tid in traces.items():
    api("post", "/api/public/scores", json={
        "trace_id": tid,
        "name": f"{nome.lower().replace(' ','_')}_accuracy",
        "value": round(0.7 + __import__('random').random() * 0.25, 2),
        "source": "EVAL",
        "comment": f"Auto-avaliação da predição do {nome}"
    })
print("✓ Scores criados")

# 3. Criar a predição
pred = api("post", "/api/public/predictions", json={
    "name": "Eleições 2026 — Cenário Completo",
    "seed_summary": "Eleição presidencial Brasil 2026. Datafolha setembro: Lula 32-55%, Flávio 24-40%, Caiado 8%, Cury 6%, Zema 1%. Crise STF (julgamento Moraes-Vorcaro). 12 candidatos, 158M eleitores. Campanha em andamento.",
    "horizon_date": "2026-10-04T00:00:00+00:00",
    "scenario_params": {
        "pesquisa": "Datafolha 8-11 setembro 2026",
        "cenário": "Base — polarização Lula vs Flávio",
        "crise STF": "Julgamento mensagens Moraes-Vorcaro em 15/09",
        "economia": "Inflação 4.5%, Selic 11.75%, Real estável",
        "fragmentação direita": "PL, PSD, NOVO, Avante concorrem separados"
    },
    "personas": [
        {"nome": "Cientista Político", "role": "analise de cenarios eleitorais", "bias": "neutro"},
        {"nome": "Estrategista", "role": "comunicacao politica e midias", "bias": "pragmatico"},
        {"nome": "Macroeconomista", "role": "politica fiscal e monetaria", "bias": "conservador"}
    ]
})
PRED_ID = pred["id"]
print(f"✓ Predição: {pred['name']}")

# 4. Adicionar agentes com predictions, trace_id e interações
agentes = [
    {
        "persona_name": "Cientista Político",
        "persona_profile": {"role": "analise de cenarios eleitorais", "bias": "neutro", "expertise": "comportamento eleitoral, pesquisas e tendencias"},
        "trace_id": traces["Cientista Político"],
        "prediction": {
            "cenario mais provavel": "Segundo turno — Lula 52% vs Flávio 48%",
            "voto 1 turno Lula": "45% (±2pp)",
            "voto 1 turno Flávio": "37% (±2pp)",
            "voto util": "Caiado e Cury perdem força no 2º turno para Lula",
            "abstencao": "21% no 1º turno, 18% no 2º",
            "fator Cury": "Pode atingir 8% e levar a decisão para o 2º turno"
        },
        "confidence": 0.82,
        "interactions": [
            {"target": "Estrategista", "content": "A polarização deve se manter — Lula e Flávio concentram 70% das intenções", "round": 1, "type": "argumento"},
            {"target": "Macroeconomista", "content": "O cenário econômico atual favorece o incumbente historicamente", "round": 1, "type": "argumento"}
        ]
    },
    {
        "persona_name": "Estrategista",
        "persona_profile": {"role": "comunicacao politica e midias", "bias": "pragmatico", "expertise": "marketing digital, debates e propaganda eleitoral"},
        "trace_id": traces["Estrategista"],
        "prediction": {
            "estrategia Lula": "Live no Alvorada, maquina publica, foco em estabilidade e programas sociais",
            "estrategia Flávio": "Herança bolsonarista, discurso anti-STF, redes sociais como palanque principal",
            "surpresa Cury": "8M seguidores, crescimento orgânico pós-debate — pode atingir 10%",
            "gasto campanha": "Lula tem vantagem de coligação ampla (8 partidos) sobre Flávio (partido isolado)",
            "voto jovem": "Dividido — Cury atrai pela internet, Flávio pelo sobrenome Bolsonaro"
        },
        "confidence": 0.76,
        "interactions": [
            {"target": "Cientista Político", "content": "Cury é a grande incógnita — candidato com 8M de seguidores sem estrutura partidária tradicional", "round": 2, "type": "contraponto"},
            {"target": "Macroeconomista", "content": "O escândalo Master pode anular o discurso economico de Lula se avançar para o BC", "round": 2, "type": "alerta"}
        ]
    },
    {
        "persona_name": "Macroeconomista",
        "persona_profile": {"role": "politica fiscal e monetaria", "bias": "conservador", "expertise": "inflação, cambio, juros e contas publicas"},
        "trace_id": traces["Macroeconomista"],
        "prediction": {
            "inflacao": "Controlada em 4.5-5.0% — abaixo do pico de 2022, favorece Lula",
            "cambio": "Real estável R$5.20-5.60 — reduz descontentamento com poder de compra",
            "juros": "Selic em 11.75% com espaço para corte moderado ate outubro",
            "risco fiscal": "Arcabouço fiscal dá fôlego curto — despesa obrigatoria cresce, risco de descumprimento em 2027",
            "risco BC": "Escândalo Master/Bacen pode contaminar credibilidade da política monetária",
            "PIB 2026": "Crescimento de 2.2-2.5% — moderado mas positivo"
        },
        "confidence": 0.71,
        "interactions": [
            {"target": "Cientista Político", "content": "A economia estável tende a beneficiar o incumbente, como em 1998 (FHC) e 2006 (Lula)", "round": 1, "type": "evidencia"},
            {"target": "Estrategista", "content": "Se o escândalo do BC crescer, Lula perde o principal argumento de campanha — o 'povo está melhor'", "round": 2, "type": "alerta"}
        ]
    }
]

for a in agentes:
    api("post", f"/api/public/predictions/{PRED_ID}/agents", json=a)
print(f"✓ {len(agentes)} agentes adicionados")

# 5. Finalizar e avaliar
api("post", f"/api/public/predictions/{PRED_ID}/complete")
api("post", f"/api/public/predictions/{PRED_ID}/eval", json={"accuracy_score": 0.81})
print("✓ Predição finalizada e avaliada (acurácia: 0.81)")

# 6. Resumo
s = api("get", f"/api/public/predictions/{PRED_ID}/summary")
g = api("get", f"/api/public/predictions/{PRED_ID}/interactions")
sc = api("get", f"/api/public/predictions/{PRED_ID}/scores")
tr = api("get", f"/api/public/predictions/{PRED_ID}/traces")
print(f"\n=== RESUMO ===")
print(f"Nome: {s['name']} · Status: {s['status']} · Acurácia: {s['accuracy_score']}")
print(f"Agentes: {s['agent_count']} — {', '.join(s['agents'])}")
print(f"Interações: {len(g['nodes'])} agentes, {len(g['edges'])} mensagens em {len(set(e['round'] for e in g['edges']))} rounds")
print(f"Traces: {len(tr['traces'])} · Scores: {len(sc['scores'])}")

det = api("get", f"/api/public/predictions/{PRED_ID}")
if det.get("report"):
    print(f"Relatório: {'✓' if det['report'].get('synthesis') else 'sem síntese'}")

print(f"\n✅ Acesse: http://localhost:5173/predictions/{PRED_ID}")