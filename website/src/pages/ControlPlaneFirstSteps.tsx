import { Link } from "react-router-dom";
import CodeBlock from "../components/CodeBlock";
import { useI18n } from "../i18n/context";
import productionCompose from "../../../docker/docker-compose.production.yml?raw";

const observerExample = `"""End-to-end: a real-model wolfpack agent sends traces to AMP.

WOLFPACK_AMP_URL (default http://localhost:8200) points at the Wolfpack Control
Plane ingestion endpoint. WolfpackObserver implements the Tracker contract and
buffers events; tracker.flush() pushes them to POST /api/public/ingestion.
"""

import os

from wolfpack import Agent, MeshIdentity, get_model_from_env, tool
from wolfpack.observer.client import WolfpackObserver


@tool
def get_weather(city: str) -> str:
    """Gets the weather for a city."""
    return f"Weather in {city}: 22C, partly cloudy."


def main() -> None:
    amp_url = os.environ.get("WOLFPACK_AMP_URL", "http://localhost:8200")
    amp_key = os.environ.get("WOLFPACK_AMP_API_KEY", "pk-wp-dev:dev-secret")
    print(f"sending observations to AMP at {amp_url}")

    tracker = WolfpackObserver(
        base_url=amp_url,
        api_key=amp_key,
        deployment=MeshIdentity(
            os.environ.get("WOLFPACK_ENVIRONMENT_ID", "development"),
            os.environ.get("WOLFPACK_ENVIRONMENT_SLUG", "development"),
            os.environ.get("WOLFPACK_REGISTRATION_ID", "weather-agent"),
            "weather-agent",
            "1.0.0",
            trigger_type="interactive",
        ),
    )

    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit("No API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, or OLLAMA_BASE_URL.")

    agent = Agent(
        name="weather-agent",
        model=model,
        role="Weather assistant",
        goal="Answer weather questions using the get_weather tool.",
        backstory="A wolfpack agent with a weather tool, observed by the AMP control plane.",
        tools=[get_weather],
        telemetry=tracker,
    )
    output = agent.run("What is the weather in Lisbon?")
    print("status:", "ok" if not output.failed else output.error)
    print("answer:", output.content)
    print("tokens:", output.usage)
    tracker.flush()
    print("run_id:", output.run_id)
    print("End-to-end trace sent. Open the Control Plane UI to inspect it.")


if __name__ == "__main__":
    main()`;

export default function ControlPlaneFirstSteps() {
  const { lang, t } = useI18n();
  const pt = lang === "pt-BR";

  return (
    <article className="space-y-8">
      <header>
        <div className="mb-4 flex items-center gap-2 text-sm text-gray-400">
          <Link to="/docs" className="hover:text-white">{t.common.documentation}</Link><span>/</span>
          <span className="text-amber-400">{t.layout.controlPlane}</span><span>/</span>
          <span className="text-white">{pt ? "Primeiros passos" : "First Steps"}</span>
        </div>
        <h1 className="mb-4 text-4xl font-bold text-white">{pt ? "Primeiros passos com AMP" : "First Steps with AMP"}</h1>
        <p className="text-lg leading-relaxed text-gray-300">
          {pt ? "Suba o Control Plane com o Compose de produção e envie o primeiro trace de um agente Wolfpack." : "Start the Control Plane with the production Compose stack and send the first trace from a Wolfpack agent."}
        </p>
      </header>

      <section>
        <h2 className="mb-3 text-2xl font-bold text-white">{pt ? "1. Configure e inicie o AMP" : "1. Configure and start AMP"}</h2>
        <p className="mb-4 leading-relaxed text-gray-400">
          {pt ? "Defina as variáveis obrigatórias e execute o Compose a partir da raiz do repositório. A interface fica disponível em http://localhost e a API em http://localhost:8000." : "Set the required variables and run Compose from the repository root. The UI is available at http://localhost and the API at http://localhost:8000."}
        </p>
        <CodeBlock language="bash" title={pt ? "Iniciar a pilha" : "Start the stack"} code={`export POSTGRES_PASSWORD="change-me"
export MINIO_ROOT_USER="minio"
export MINIO_ROOT_PASSWORD="change-me"
export ADMIN_API_KEY="change-me"
export JWT_SECRET="change-me"
export PROVIDER_SECRETS_MASTER_KEY="change-me"
export INNGEST_SIGNING_KEY="signkey-prod"
export INNGEST_EVENT_KEY="eventkey-prod"

docker compose -f docker/docker-compose.production.yml up -d`} />
      </section>

      <section>
        <h2 className="mb-3 text-2xl font-bold text-white">{pt ? "Compose de produção" : "Production Compose"}</h2>
        <p className="mb-4 text-gray-400">{pt ? "Este é o conteúdo atual de docker/docker-compose.production.yml." : "This is the current docker/docker-compose.production.yml."}</p>
        <CodeBlock language="yaml" title="docker-compose.production.yml" code={productionCompose} />
      </section>

      <section>
        <h2 className="mb-3 text-2xl font-bold text-white">{pt ? "2. Envie traces com WolfpackObserver" : "2. Send traces with WolfpackObserver"}</h2>
        <p className="mb-4 leading-relaxed text-gray-400">
          {pt ? "WolfpackObserver implementa o contrato Tracker, mantém eventos em buffer e os envia para POST /api/public/ingestion ao chamar tracker.flush(). Cada execução vira um trace com as observações de geração e de ferramentas." : "WolfpackObserver implements the Tracker contract, buffers events, and sends them to POST /api/public/ingestion when tracker.flush() runs. Each execution becomes a trace with generation and tool observations."}
        </p>
        <CodeBlock language="python" title="02_amp_observer.py" code={observerExample} />
        <CodeBlock language="bash" title={pt ? "Executar o exemplo" : "Run the example"} code={`cd framework
export WOLFPACK_AMP_URL="http://localhost:8000"
export WOLFPACK_AMP_API_KEY="pk-wp-dev:dev-secret"
uv run python examples/05_observability/02_amp_observer.py`} />
      </section>

      <section>
        <h2 className="mb-3 text-2xl font-bold text-white">{pt ? "3. Abra o Control Plane" : "3. Open the Control Plane"}</h2>
        <p className="mb-4 leading-relaxed text-gray-400">
          {pt ? "Abra a interface depois que a pilha estiver saudável. O trace enviado pelo exemplo aparece em Traces; use Agent Mesh para ver registros, runtimes e interações observadas." : "Open the interface after the stack is healthy. The trace sent by the example appears in Traces; use Agent Mesh to view registrations, runtimes, and observed interactions."}
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          <a href="http://localhost" target="_blank" rel="noreferrer" className="rounded-xl border border-gray-800 bg-gray-900 p-5 transition-colors hover:border-amber-500/50">
            <h3 className="font-semibold text-white">AMP Control Plane</h3>
            <p className="mt-2 text-sm text-gray-400">http://localhost</p>
            <p className="mt-3 text-sm leading-relaxed text-gray-400">{pt ? "Explore Traces, Agent Mesh, aprovações, scores, agendamentos, canais, privacidade e configurações." : "Explore Traces, Agent Mesh, approvals, scores, schedules, channels, privacy, and settings."}</p>
          </a>
          <a href="http://localhost:9090" target="_blank" rel="noreferrer" className="rounded-xl border border-gray-800 bg-gray-900 p-5 transition-colors hover:border-amber-500/50">
            <h3 className="font-semibold text-white">Prometheus</h3>
            <p className="mt-2 text-sm text-gray-400">http://localhost:9090</p>
            <p className="mt-3 text-sm leading-relaxed text-gray-400">{pt ? "Consulte métricas da infraestrutura e da ingestão de telemetria." : "Inspect infrastructure and telemetry ingestion metrics."}</p>
          </a>
          <a href="http://localhost:9001" target="_blank" rel="noreferrer" className="rounded-xl border border-gray-800 bg-gray-900 p-5 transition-colors hover:border-amber-500/50">
            <h3 className="font-semibold text-white">MinIO Console</h3>
            <p className="mt-2 text-sm text-gray-400">http://localhost:9001</p>
            <p className="mt-3 text-sm leading-relaxed text-gray-400">{pt ? "Acesse o armazenamento de objetos usado pela plataforma." : "Access the object storage used by the platform."}</p>
          </a>
          <a href="http://localhost:8289" target="_blank" rel="noreferrer" className="rounded-xl border border-gray-800 bg-gray-900 p-5 transition-colors hover:border-amber-500/50">
            <h3 className="font-semibold text-white">Inngest</h3>
            <p className="mt-2 text-sm text-gray-400">http://localhost:8289</p>
            <p className="mt-3 text-sm leading-relaxed text-gray-400">{pt ? "Acompanhe tarefas assíncronas e execuções agendadas." : "Monitor asynchronous tasks and scheduled executions."}</p>
          </a>
        </div>
      </section>
    </article>
  );
}
