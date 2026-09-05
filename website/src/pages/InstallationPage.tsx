import { Link } from "react-router-dom";
import CodeBlock from "../components/CodeBlock";

export default function InstallationPage() {
  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/" className="hover:text-white">Home</Link>
          <span>/</span>
          <span className="text-amber-400">Getting Started</span>
          <span>/</span>
          <span className="text-white">Installation</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Installation</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          Get started with Wolfpack AI in minutes. Choose the installation method that works best for your use case.
        </p>
      </header>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">Framework Only (pip)</h2>
          <p className="text-gray-400 mb-4">
            Install the core Wolfpack AI framework. Includes the Agent, Tools, Memory, Knowledge, Guardrails,
            and Workflow modules. Works standalone without the AMP control plane.
          </p>
          <CodeBlock
            code="pip install wolfpack"
            language="bash"
            title="Install Wolfpack AI Framework"
          />
          <div className="mt-4 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-2">Requirements</h3>
            <ul className="text-sm text-gray-400 space-y-1">
              <li>• Python 3.10 or higher</li>
              <li>• pip 23.0+</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">Control Plane (AMP) with Docker Compose</h2>
          <p className="text-gray-400 mb-4">
            Deploy the full Wolfpack Agent Management Platform (AMP) including the Mesh Registry, Chat API,
            Channel integrations, Scheduler, and Observability stack using Docker Compose.
          </p>

          <h3 className="text-lg font-semibold text-white mb-3">1. Clone the repository</h3>
          <CodeBlock
            code={`git clone https://github.com/alvaro-brito-products/wolfpack-ai.git
cd wolfpack-ai`}
            language="bash"
            title="Clone Wolfpack AI"
          />

          <h3 className="text-lg font-semibold text-white mt-6 mb-3">2. Start infrastructure</h3>
          <CodeBlock
            code={`# Start infrastructure (postgres, redis, minio, qdrant, prometheus, inngest)
docker compose -f docker/docker-compose.yml up -d

# Start AMP API (uvicorn on :8000)
cd control-plane
./run.sh`}
            language="bash"
            title="Start AMP"
          />

          <h3 className="text-lg font-semibold text-white mt-6 mb-3">3. Start the frontend</h3>
          <CodeBlock
            code={`cd control-plane/frontend
npm install
npm run dev     # http://localhost:5173 (proxies /api to :8000)`}
            language="bash"
            title="AMP Frontend"
          />

          <div className="mt-4 grid md:grid-cols-2 gap-4">
            <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-2">Services Included</h3>
              <ul className="text-sm text-gray-400 space-y-1">
                <li>• AMP API Server (port 8000)</li>
                <li>• PostgreSQL 16 (port 5439)</li>
                <li>• Redis 7 (port 6382)</li>
                <li>• MinIO Object Storage (ports 9000, 9001)</li>
                <li>• Qdrant Vector DB (ports 6333, 6334)</li>
                <li>• Inngest Job Orchestrator (port 8289)</li>
                <li>• Prometheus Metrics (port 9090)</li>
              </ul>
            </div>
            <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-2">Web UI</h3>
              <ul className="text-sm text-gray-400 space-y-1">
                <li>• AMP Frontend (port 5173)</li>
                <li>• Prometheus (port 9090)</li>
                <li>• Inngest Dev Server (port 8289)</li>
                <li>• MinIO Console (port 9001)</li>
              </ul>
            </div>
          </div>

          <h3 className="text-lg font-semibold text-white mt-6 mb-3">4. Verify installation</h3>
          <CodeBlock
            code={`# Check service health
curl http://localhost:8000/health

# View logs
docker compose -f docker/docker-compose.yml logs -f`}
            language="bash"
            title="Verify AMP Deployment"
          />
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">Source Code / Git Clone</h2>
          <p className="text-gray-400 mb-4">
            Clone the repository and install in development mode to contribute, customize, or explore the source code.
          </p>
          <CodeBlock
            code={`# Clone the repository
git clone https://github.com/alvaro-brito-products/wolfpack-ai.git
cd wolfpack-ai

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv/Scripts/activate  # Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install`}
            language="bash"
            title="Development Installation"
          />
          <div className="mt-4 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-2">Project Structure</h3>
            <pre className="text-sm text-gray-400 font-mono mt-2" style={{whiteSpace:"pre",lineHeight:1.5}}>
{`wolfpack-ai/
├── framework/          # Python framework (pip install wolfpack)
│   ├── wolfpack/
│   │   ├── agent/       # Agent loop, events, streaming
│   │   ├── tools/       # @tool decorator, Function, Toolkit
│   │   ├── team/        # Leader-driven team delegation
│   │   ├── memory/      # SessionMemory, SQLite, stores
│   │   ├── knowledge/   # RAG, vector DB, embeddings, readers
│   │   ├── guardrails/  # PII, prompt injection, tool allowlist
│   │   ├── workflow/    # DAG-based workflow engine
│   │   ├── models/      # OpenAI, Anthropic, Google, Ollama
│   │   ├── observer/    # WolfpackObserver, AMP telemetry
│   │   ├── mesh.py      # MeshIdentity for trace attribution
│   │   ├── runtimes/    # Source-owned chat runtime factories
│   │   └── schedules/   # AMP schedule client + toolkit
│   ├── examples/        # 38 runnable example scripts
│   └── tests/           # 91+ unit/integration tests
│
├── control-plane/       # AMP (Agent Management Platform)
│   ├── backend/         # FastAPI server
│   │   ├── app/
│   │   │   ├── routes/   # Chat, Mesh, Channels, Schedules, API
│   │   │   ├── models/   # SQLAlchemy entities
│   │   │   ├── services/ # Ingestion, schedules, cost, vault
│   │   │   └── core/     # Auth, config, database
│   │   ├── alembic/      # 27 migrations
│   │   └── tests/        # 75+ tests
│   ├── frontend/         # React + Vite + TypeScript UI
│   └── examples/         # Team agent server, time test demo
│
├── docker/              # Docker Compose (Postgres, Redis, Inngest)
├── website/             # Documentation site (Vite + React + Tailwind)
└── docs/                # Additional documentation`}</pre>
          </div>
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">Environment Setup</h2>
          <p className="text-gray-400 mb-4">
            Wolfpack AI requires API keys for the LLM providers and services you want to use.
            Set these as environment variables or configure them through the AMP Secrets Manager.
          </p>

          <h3 className="text-lg font-semibold text-white mb-3">Required Keys</h3>
          <div className="overflow-hidden rounded-xl border border-gray-700 mb-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/50">
                  <th className="px-4 py-3 text-left font-medium text-gray-300">Variable</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-300">Provider</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-300">Required</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {[
                  { var: "OPENAI_API_KEY", provider: "OpenAI", required: true },
                  { var: "ANTHROPIC_API_KEY", provider: "Anthropic", required: false },
                  { var: "GOOGLE_API_KEY", provider: "Google Gemini", required: false },
                  { var: "TAVILY_API_KEY", provider: "Tavily Search", required: false },
                  { var: "GITHUB_TOKEN", provider: "GitHub API", required: false },
                  { var: "SLACK_BOT_TOKEN", provider: "Slack Bot", required: false },
                  { var: "DISCORD_BOT_TOKEN", provider: "Discord Bot", required: false },
                  { var: "AMP_API_KEY", provider: "AMP Control Plane", required: false },
                  { var: "AMP_API_URL", provider: "AMP Endpoint", required: false },
                ].map((row) => (
                  <tr key={row.var} className="hover:bg-gray-800/30">
                    <td className="px-4 py-3 font-mono text-amber-400">{row.var}</td>
                    <td className="px-4 py-3 text-gray-300">{row.provider}</td>
                    <td className="px-4 py-3">
                      {row.required ? (
                        <span className="text-green-400">Required</span>
                      ) : (
                        <span className="text-gray-500">Optional</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 className="text-lg font-semibold text-white mb-3">Quick Setup</h3>
          <CodeBlock
            code={`# Create .env file with your keys
echo 'OPENAI_API_KEY=sk-your-key-here' >> .env
echo 'ANTHROPIC_API_KEY=sk-ant-your-key-here' >> .env

# Source it before running agents
export $(grep -v '^#' .env | xargs)`}
            language="bash"
            title="Environment Variables Quick Setup"
          />
        </div>
      </section>
    </article>
  );
}