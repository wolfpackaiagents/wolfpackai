"""FastAPI Team Agent - Time Teste.

Executa um time de 2 agentes especializados:
1. knowledge-specialist: consulta base de conhecimento Markdown
2. procedures-agent: executa procedimentos de suporte

Registra o serviço no AMP como "Time Teste".

Uso:
    uv run python examples/time_teste/server.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wolfpack.agent.agent import Agent
from wolfpack.knowledge.knowledge import Knowledge
from wolfpack.knowledge.readers import MarkdownReader
from wolfpack.models.utils import get_model_from_env
from wolfpack.team import Team
from wolfpack.tools.decorator import tool
from wolfpack.vectordb.base import MemoryVectorDb
from wolfpack.vectordb.embeddings import EmbeddingModel

# ── Config ──────────────────────────────────────────────────────────────────

AMP_URL = os.environ.get("WOLFPACK_AMP_URL", "http://127.0.0.1:8000")
AMP_API_KEY = os.environ.get("WOLFPACK_AMP_API_KEY", "pk-wp-dev:dev-secret")
SERVER_PORT = int(os.environ.get("TEAM_SERVER_PORT", "9020"))
INSTANCE_ID = os.environ.get("TEAM_INSTANCE_ID", "time-teste-1")

BASE_DIR = Path(__file__).parent
KNOWLEDGE_PATH = BASE_DIR / "knowledge_base.md"

from contextlib import asynccontextmanager

# ... (keep imports above)

# ── Lifespan ─────────────────────────────────────────────────────────────────

REGISTRATION_ID: str | None = None
ENVIRONMENT_ID: str = "development"


def _register_in_amp() -> str | None:
    """Registra este runtime no Mesh do AMP e retorna o registration_id."""
    global ENVIRONMENT_ID
    client = httpx.Client(trust_env=False, timeout=10)
    headers = {"X-API-Key": AMP_API_KEY}

    try:
        catalog = client.get(f"{AMP_URL}/api/public/mesh/catalog", headers=headers).json()
    except Exception as e:
        print(f"  ⚠ AMP não acessível ({e}). Pulando registro.")
        return None

    for env in catalog.get("environments", []):
        for reg in env.get("registrations", []):
            if reg["definition_key"] == "time-teste":
                rid = reg["id"]
                ENVIRONMENT_ID = env["id"]
                try:
                    client.patch(f"{AMP_URL}/api/public/mesh/registrations/{rid}", headers=headers, json={
                        "chat_endpoint": "http://127.0.0.1:9020/v1/chat",
                    })
                except Exception:
                    pass
                print(f"  ✓ Registration time-teste encontrada: {rid} ({env['slug']})")
                return rid

    try:
        dev_env = catalog["environments"][0]
        ENVIRONMENT_ID = dev_env["id"]
        print(f"  ✓ Usando environment: {dev_env['slug']} ({dev_env['id']})")

        definition = client.post(f"{AMP_URL}/api/public/mesh/definitions", headers=headers, json={
            "key": "time-teste", "kind": "team", "name": "Time Teste", "version": "1.0.0",
            "description": "Time de suporte com knowledge base e procedimentos",
            "summary": {"team": "Time Teste", "members": ["knowledge-specialist", "procedures-agent"]},
        }).json()
        print(f"  ✓ Definition time-teste criada: {definition['id']}")

        registration = client.post(f"{AMP_URL}/api/public/mesh/registrations", headers=headers, json={
            "environment_id": dev_env["id"], "definition_id": definition["id"],
            "chat_endpoint": "http://127.0.0.1:9020/v1/chat", "tags": ["demo"],
        }).json()
        print(f"  ✓ Registration time-teste criada: {registration['id']}")

        return registration["id"]
    except Exception as e:
        print(f"  ⚠ Erro ao registrar no AMP: {e}")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global REGISTRATION_ID
    print(f"\n{'='*50}")
    print(f"  Time Teste Agent")
    print(f"  Porta: {SERVER_PORT}")
    print(f"  AMP: {AMP_URL}")
    print(f"  Knowledge: {KNOWLEDGE_PATH}")
    print(f"{'='*50}\n")

    REGISTRATION_ID = _register_in_amp()

    if REGISTRATION_ID:
        try:
            client = httpx.Client(trust_env=False, timeout=5)
            r = client.post(
                f"{AMP_URL}/api/public/mesh/registrations/{REGISTRATION_ID}/heartbeat",
                headers={"X-API-Key": AMP_API_KEY},
                json={"instance_id": INSTANCE_ID, "version": "1.0.0", "metadata": {"team": "Time Teste"}},
            )
            if r.status_code == 200:
                print(f"  ✓ Heartbeat enviado para AMP (registration={REGISTRATION_ID})")
            else:
                print(f"  ⚠ Heartbeat falhou: {r.status_code} {r.text}")
        except Exception as e:
            print(f"  ⚠ Erro no heartbeat: {e}")
    else:
        print("  ⚠ Serviço rodando sem registro no AMP")
    yield


app = FastAPI(title="Time Teste - Team Agent", lifespan=lifespan)

class SimpleEmbedding(EmbeddingModel):
    def embed(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            freq = [0.0] * 128
            for ch in text.lower():
                if ord(ch) < 128:
                    freq[ord(ch)] += 1.0
            n = len(text) or 1
            result.append([f / n for f in freq])
        return result


# ── Knowledge Base ──────────────────────────────────────────────────────────

def load_knowledge() -> Knowledge:
    reader = MarkdownReader(chunk_size=500)
    chunks = reader.read_file(str(KNOWLEDGE_PATH))
    vdb = MemoryVectorDb()
    emb = SimpleEmbedding()
    knowledge = Knowledge(vector_db=vdb, embedding_model=emb)
    for chunk in chunks:
        knowledge.add_text(chunk.content, metadata={"source": "knowledge_base", "heading": chunk.metadata.get("heading")})
    print(f"  Knowledge base: {knowledge.count()} chunks carregados")
    for doc in vdb._docs:
        print(f"    - {doc.content[:50]}...")
    return knowledge


# ── Tools dos agentes ───────────────────────────────────────────────────────

@tool
def buscar_produto(consulta: str) -> str:
    """Busca informações de produto na base de conhecimento.
    Args:
        consulta: nome ou código do produto
    Returns:
        informações do produto encontrado
    """
    return f"Produto encontrado: '{consulta}' - R$ 1.299,00 em até 12x sem juros."


@tool
def cancelar_pedido(pedido_id: str) -> str:
    """Cancela um pedido no sistema.
    Args:
        pedido_id: número do pedido
    Returns:
        resultado do cancelamento
    """
    return f"Pedido {pedido_id} cancelado com sucesso. Reembolso em até 10 dias úteis."


@tool
def criar_chamado(assunto: str, descricao: str) -> str:
    """Abre um chamado de suporte.
    Args:
        assunto: título do chamado
        descricao: detalhes do problema
    Returns:
        número do chamado criado
    """
    ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
    return f"Chamado {ticket_id} criado com sucesso. Assunto: {assunto}"


# ── Modelo ──────────────────────────────────────────────────────────────────

def get_model():
    try:
        return get_model_from_env()
    except ValueError:
        print("  ERRO: Nenhum provedor LLM configurado. Defina OPENAI_API_KEY ou ANTHROPIC_API_KEY.")
        raise


# ── API ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    status: str
    output: str
    duration_s: float


@app.post("/v1/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Recebe uma mensagem e executa o time de agentes com telemetria para o AMP."""
    from wolfpack.mesh import MeshIdentity
    from wolfpack.observer.client import WolfpackObserver

    print(f"\n=== Time Teste recebeu: {request.message[:60]}... ===")

    model = get_model()
    knowledge = load_knowledge()
    session_id = f"chat_{uuid.uuid4().hex[:16]}"

    observer = WolfpackObserver(
        AMP_URL, api_key=AMP_API_KEY, session_id=session_id,
        deployment=MeshIdentity(ENVIRONMENT_ID, "development", REGISTRATION_ID or "", "time-teste", "1.0.0", trigger_type="interactive_chat"),
    )

    knowledge_agent = Agent(
        name="knowledge-specialist",
        role="Consultar base de conhecimento sobre produtos, pedidos e devoluções",
        description="Especialista em consultar a base de conhecimento para encontrar informações sobre produtos, pedidos, devoluções e suporte.",
        knowledge=knowledge, model=model, telemetry=observer,
    )

    procedures_agent = Agent(
        name="procedures-agent",
        role="Executar procedimentos operacionais como cancelar pedidos e criar chamados",
        description="Especialista em executar procedimentos de suporte como cancelamento de pedidos e abertura de chamados.",
        tools=[buscar_produto, cancelar_pedido, criar_chamado],
        model=model, telemetry=observer,
    )

    team = Team("Time Teste", [knowledge_agent, procedures_agent], leader_model=model, telemetry=observer)

    print("  Executando time...")
    start = time.time()
    result = team.run(request.message)
    duration = time.time() - start
    print(f"  Concluído em {duration:.2f}s")

    observer.flush()
    print(f"  Telemetria enviada ao AMP")

    return ChatResponse(status="completed", output=result.content, duration_s=round(duration, 2))


@app.post("/v1/heartbeat")
def heartbeat():
    """Registra o runtime como online no Mesh do AMP."""
    return {"instance_id": INSTANCE_ID, "status": "alive"}


if __name__ == "__main__":
    print(f"Iniciando Time Teste na porta {SERVER_PORT}...")
    uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT)