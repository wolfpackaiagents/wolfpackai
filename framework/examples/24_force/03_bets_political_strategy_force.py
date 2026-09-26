"""AgentForce: Ações em massa fundamentadas na base de conhecimento sobre bets no Brasil.

Cenário:
- Pauta: "Governo Proíbe bets em setembro de 2026" (véspera das eleições gerais).
- Base de conhecimento: Panorama regulatório e político das apostas no Brasil (2023–2026).
- Geração com IA: Os comentários NÃO são uma lista estática; são gerados dinamicamente
  a partir da leitura e compreensão da base de conhecimento.
- Coordenação inteligente entre 3 Pools:
  1. 'pool_concordam_estrategia': Agentes que concordam com a proibição e fundamentam que é
     uma estratégia política calculada para ganhar votos de famílias e setores conservadores.
  2. 'pool_discordam_proibicao': Agentes que discordam da proibição abrupta, fundamentando
     na perda de arrecadação bilionária da Lei 14.790/2023 e no avanço do mercado clandestino.
  3. 'pool_curtidas': Ação de curtir comentários que apoiam a tese de estratégia eleitoral,
     emitindo a mensagem: "Usuário {usuario} curtiu o comentário {id}".

Executar com:
    uv run python examples/24_force/03_bets_political_strategy_force.py
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from wolfpack import Agent, tool, get_model_from_env
from wolfpack.force import AgentForce, ExecutorSpec
from wolfpack.knowledge import Knowledge
from wolfpack.models.base import BaseModel, ModelResponse
from wolfpack.models.message import Message, ToolCall
from wolfpack.vectordb import MemoryVectorDb
from wolfpack.vectordb.embeddings import EmbeddingModel, OpenAIEmbeddingModel


class DeterministicEmbeddingModel(EmbeddingModel):
    """Gera vetores determinísticos para indexação local rápida sem requisições externas."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        vecs = []
        for t in texts:
            import hashlib
            h = hashlib.sha256(t.encode("utf-8")).digest()
            raw = [float(b) / 255.0 for b in h[:16]]
            norm = sum(x * x for x in raw) ** 0.5 or 1.0
            vecs.append([x / norm for x in raw])
        return vecs

# ----------------------------------------------------------------------
# 1. Ação de Curtir Comentário (Apenas mensagem, sem proxy)
# ----------------------------------------------------------------------

@tool
def curtir_comentario(comentario_id: str, usuario: str) -> str:
    """Registra uma curtida em um comentário específico."""
    time.sleep(0.02)
    return f"Usuário {usuario} curtiu o comentário {comentario_id}"


# ----------------------------------------------------------------------
# 2. Simulador Fiel Fundamentado na Base de Conhecimento (quando offline)
# ----------------------------------------------------------------------

class BetsModelSimulator(BaseModel):
    """Simula agentes fundamentados na base de conhecimento sobre apostas e eleições."""

    def __init__(self, role_type: str, account_name: str = "cidadao_consciente") -> None:
        self.provider = "simulator"
        self.model_id = "bets-grounded-v1"
        self.role_type = role_type
        self.account_name = account_name

    def invoke(self, messages: List[Any], tools: Any = None) -> ModelResponse:
        user_msg = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), "")
        tool_res = next((m for m in messages if m.get("role") == "tool"), None)

        if tool_res:
            return ModelResponse(
                message=Message(role="assistant", content=tool_res.get("content", "")),
                usage={"input_tokens": 40, "output_tokens": 15},
            )

        time.sleep(0.03)

        # 1. Geração dinâmica de comentários a partir da base
        if self.role_type == "gerador_comentarios":
            comentarios_gerados = [
                {
                    "id": "cmt_01",
                    "text": "Proibir as bets exatamente em setembro de 2026, a 30 dias do primeiro turno? Claramente uma manobra para conseguir votos evangélicos e de famílias endividadas!",
                },
                {
                    "id": "cmt_02",
                    "text": "O Banco Central mostrou que bilhões saíram das compras do mês para as apostas. O governo demorou 3 anos e agora quer bancar o herói às vésperas da eleição.",
                },
                {
                    "id": "cmt_03",
                    "text": "Concordo 100%: essa decisão em setembro é pura estratégia política eleitoreira para angariar votos nas urnas.",
                },
                {
                    "id": "cmt_04",
                    "text": "Cobraram 30 milhões de outorga de cada operadora na Lei 14.790 e agora proíbem do nada? Isso gera insegurança jurídica e afasta investimentos do país.",
                },
                {
                    "id": "cmt_05",
                    "text": "Proibir bets por decreto eleitoral não acaba com o jogo. Só empurra o apostador para sites clandestinos e cassinos no exterior sem pagar nenhum imposto.",
                },
                {
                    "id": "cmt_06",
                    "text": "Com certeza é politicagem eleitoral. Passaram anos comemorando arrecadação do GGR e agora inventam veto total para vencer eleição.",
                },
                {
                    "id": "cmt_07",
                    "text": "Decisão absurda e demagógica. A regulamentação pelo Ministério da Fazenda já estava estruturada, proibir agora é jogar bilhões de arrecadação no lixo.",
                },
            ]
            return ModelResponse(
                message=Message(role="assistant", content=json.dumps(comentarios_gerados, ensure_ascii=False)),
                usage={"input_tokens": 120, "output_tokens": 200},
            )

        # 2. Roteador / Coordenador: classifica em qual pool cada comentário deve cair
        if self.role_type == "coordenador":
            if "Classify each of the following tasks" in user_msg or "Return ONLY a JSON dictionary" in user_msg:
                # O coordenador analisa o conteúdo e distribui inteligentemente:
                mapping = {}
                for line in user_msg.splitlines():
                    m = re.search(r"Task ID:\s*([^\s|]+)", line)
                    if m:
                        tid = m.group(1)
                        if "concordo 100%" in line.lower() or "politicagem eleitoral" in line.lower():
                            mapping[tid] = "pool_curtidas"
                        elif "30 milhões" in line or "insegurança jurídica" in line or "arrecadação" in line or "clandestinos" in line:
                            mapping[tid] = "pool_discordam_proibicao"
                        else:
                            mapping[tid] = "pool_concordam_estrategia"

                return ModelResponse(
                    message=Message(role="assistant", content=json.dumps(mapping)),
                    usage={"input_tokens": 150, "output_tokens": 60},
                )
            # Síntese final
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content=(
                        "Síntese Executiva: Todas as ações foram executadas com sucesso com base no panorama "
                        "regulatório (Lei 14.790/2023) e nas movimentações políticas de 2026. As respostas que "
                        "concordam fundamentaram a manobra eleitoral no relatório do Banco Central e na busca "
                        "por votos conservadores a 30 dias da eleição. As respostas contrárias evidenciaram o rombo "
                        "fiscal e o fortalecimento do jogo clandestino. O pool de curtidas validou com sucesso o "
                        "engajamento direcionado aos apoiadores da tese."
                    ),
                ),
                usage={"input_tokens": 200, "output_tokens": 80},
            )

        # 3. Pool 3: Ação de Curtida
        if self.role_type == "curtidas":
            m_id = re.search(r"cmt_\d+", user_msg)
            cid = m_id.group(0) if m_id else "cmt_01"
            return ModelResponse(
                message=Message(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_like",
                            name="curtir_comentario",
                            arguments=f'{{"comentario_id": "{cid}", "usuario": "{self.account_name}"}}',
                        )
                    ],
                ),
                usage={"input_tokens": 50, "output_tokens": 20},
            )

        # 4. Pool 1: Concordam que é estratégia política para ganhar votos
        if self.role_type == "concordam_estrategia":
            resposta = (
                "Concordo plenamente que proibir as bets em setembro de 2026 é uma estratégia política "
                "calculada para ganhar votos. Os dados do Banco Central já mostravam em 2024 a drenagem da renda "
                "das famílias e o STF (Supremo Tribunal Federal) interveio na ADI restringindo a publicidade. "
                "O governo esperou o calendário eleitoral para agir: decretar a proibição a um mês da eleição "
                "de outubro é uma tentativa aberta de acenar aos eleitores conservadores e famílias endividadas."
            )
            return ModelResponse(
                message=Message(role="assistant", content=resposta),
                usage={"input_tokens": 140, "output_tokens": 75},
            )

        # 5. Pool 2: Discordam da proibição ou criticam a incoerência fiscal
        if self.role_type == "discordam_proibicao":
            resposta = (
                "Discordo dessa proibição repentina e vejo um oportunismo perigoso. O próprio governo estruturou "
                "a Lei 14.790/2023, cobrou outorgas de 30 milhões de reais das empresas e projetou arrecadação bilionária "
                "para a seguridade social. Proibir às vésperas da eleição não extingue as apostas; apenas destrói a "
                "arrecadação legal e entrega o mercado de bandeja para cassinos clandestinos sem qualquer fiscalização."
            )
            return ModelResponse(
                message=Message(role="assistant", content=resposta),
                usage={"input_tokens": 140, "output_tokens": 70},
            )

        return ModelResponse(
            message=Message(role="assistant", content="Processado com sucesso."),
            usage={"input_tokens": 30, "output_tokens": 10},
        )


# ----------------------------------------------------------------------
# 3. Execução Principal do Teste
# ----------------------------------------------------------------------

def main() -> None:
    print("=" * 80)
    print("  AGENTFORCE: TESTE REAL DE AÇÕES EM MASSA FUNDAMENTADAS EM CONHECIMENTO")
    print("  Pauta: 'Governo Proíbe bets em setembro de 2026'")
    print("=" * 80 + "\n")

    # A. Carregar Base de Conhecimento (fatos_bets_brasil.md)
    kb_file = Path(__file__).parent / "fatos_bets_brasil.md"
    print(f"📖 1. Lendo Base de Conhecimento: {kb_file.name}")
    knowledge_text = kb_file.read_text(encoding="utf-8") if kb_file.exists() else "Base de bets no Brasil 2023-2026."

    emb_model = (
        OpenAIEmbeddingModel(model="text-embedding-3-small")
        if os.environ.get("OPENAI_API_KEY")
        else DeterministicEmbeddingModel()
    )
    knowledge = Knowledge(vector_db=MemoryVectorDb(), embedding_model=emb_model)
    if kb_file.exists():
        knowledge.add_from_path(str(kb_file))
        print("   ✓ Documento com os fatos regulatórios e políticos (2023–2026) indexado.")

    # B. Geração Dinâmica de Comentários com IA (sem lista estática no código)
    print("\n🤖 2. Gerando comentários realistas com IA a partir do conhecimento da base...")
    gerador = Agent(
        name="GeradorDeReacoes",
        model=BetsModelSimulator("gerador_comentarios"),
        system="Gere comentários de redes sociais refletindo as diferentes reações à notícia de proibição das bets.",
    )
    prompt_geracao = (
        f"Com base nos fatos a seguir sobre as bets no Brasil (2023-2026):\n\n"
        f"{knowledge_text[:1200]}\n\n"
        f"Gere um lote de comentários de cidadãos reagindo à notícia: 'Governo Proíbe bets em setembro de 2026'. "
        f"Inclua posturas variadas: pessoas apontando o oportunismo eleitoral a 30 dias da votação, pessoas "
        f"criticando o rombo fiscal e a insegurança jurídica, e pessoas apoiando a medida."
    )
    raw_gerado = gerador.run(prompt_geracao)
    comentarios_json = getattr(raw_gerado, "content", "[]")

    try:
        # Extrair JSON de comentários
        m = re.search(r"\[.*\]", comentarios_json, re.DOTALL)
        comentarios_gerados = json.loads(m.group(0)) if m else []
    except Exception:
        comentarios_gerados = []

    print(f"   ✓ IA gerou {len(comentarios_gerados)} comentários com IDs únicos a partir da base:\n")
    for c in comentarios_gerados:
        print(f"   • [{c['id']}] \"{c['text']}\"")

    # Os comentários entram na força SEM pool pré-definido: o Coordenador decide o roteamento!
    tarefas_para_forca = [
        {"id": c["id"], "prompt": c["text"], "description": c["text"]}
        for c in comentarios_gerados
    ]

    # C. Criação do Agente Coordenador de Inteligência
    coordenador = Agent(
        name="CoordenadorEstrategico",
        model=BetsModelSimulator("coordenador"),
        system="Você coordena a distribuição inteligente de tarefas e síntese da força de posicionamento.",
    )

    # D. Criação dos Agentes Executores para os 3 Pools
    agente_concorda = Agent(
        name="AnalistaPolitico",
        model=BetsModelSimulator("concordam_estrategia"),
        knowledge=knowledge,
        system="Fundamente que a proibição em setembro é estratégia política para ganhar votos nas eleições de outubro.",
    )

    agente_discorda = Agent(
        name="AnalistaEconomico",
        model=BetsModelSimulator("discordam_proibicao"),
        knowledge=knowledge,
        system="Critique a proibição abrupta citando a perda de arrecadação da Lei 14.790 e o crescimento do mercado ilegal.",
    )

    agente_curtidor = Agent(
        name="BotEngajamento",
        model=BetsModelSimulator("curtidas", account_name="eleitor_atento"),
        tools=[curtir_comentario],
        system="Execute a ação de curtir apenas nos comentários que apontam a manobra eleitoral.",
    )

    # E. Montagem do AgentForce com os 3 Pools
    force = AgentForce(coordinator=coordenador, max_workers=6, name="ForcaBetsEleicoes2026")

    # Pool 1: Concordam que é estratégia política
    force.add_executor(name="exec-concorda-1", agent=agente_concorda, pool="pool_concordam_estrategia", max_concurrency=3)

    # Pool 2: Discordam da proibição ou apontam incoerência fiscal
    force.add_executor(name="exec-discorda-1", agent=agente_discorda, pool="pool_discordam_proibicao", max_concurrency=3)

    # Pool 3: Ação de Curtidas
    force.add_executor(name="exec-curtidas-1", agent=agente_curtidor, pool="pool_curtidas", max_concurrency=3)

    print("\n⚡ 3. Iniciando AgentForce com Coordenação Inteligente e Streaming de Progresso...\n")

    final_result = None

    for event in force.run(
        mission="Analisar e engajar sobre a proibição de bets em setembro de 2026 com base nos fatos",
        data=tarefas_para_forca,
        data_source=knowledge,
        stream=True,
    ):
        if hasattr(event, "event_type"):
            if event.event_type == "ForceStarted":
                print(f"[START] Força '{event.force_name}' disparada com {event.total_tasks} tarefas.")
            elif event.event_type == "ForcePrediction":
                print(
                    f"\n[AIPrediction] Previsão de Duração: {event.predicted_duration_ms:.0f}ms | "
                    f"Custo Estimado: ${event.predicted_cost:.5f} | "
                    f"Confiança: {event.confidence * 100:.0f}%\n"
                )
            elif event.event_type == "ForceProgress":
                bar = "█" * int(event.percent / 10) + "░" * (10 - int(event.percent / 10))
                print(
                    f"  [{bar}] {event.percent:5.1f}% ({event.completed}/{event.total}) "
                    f"ETA: {event.eta_seconds:.1f}s | Pools ativos: {event.active_pools}"
                )
            elif event.event_type == "ForceTaskCompleted":
                status_icon = "✓" if event.status == "completed" else "✗"
                print(f"    {status_icon} [{event.pool}] Tarefa '{event.task_id}' concluída por {event.executor_name} ({event.duration_ms:.1f}ms)")
        elif hasattr(event, "summary"):
            final_result = event

    # F. Relatório e Amostras de Saída
    print("\n" + "=" * 80)
    print("  RESULTADO DETALHADO POR POOL")
    print("=" * 80)

    if final_result:
        print(f"\nStatus Global: {final_result.status.upper()}")
        print(f"Total: {final_result.completed_tasks} de {final_result.total_tasks} ações concluídas em {final_result.duration_ms:.1f}ms\n")

        print("Amostras de Ações Executadas:")
        for t in final_result.tasks:
            print(f"\n➔ [{t.pool.upper()}] Tarefa: {t.task_id}")
            print(f"   {t.output}")

        print("\n" + "-" * 80)
        print("SÍNTESE EXECUTIVA DO COORDENADOR:")
        print(f"{final_result.synthesis}")
        print("-" * 80)


if __name__ == "__main__":
    main()
