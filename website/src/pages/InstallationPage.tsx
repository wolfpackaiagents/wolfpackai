import { Link } from "react-router-dom";
import CodeBlock from "../components/CodeBlock";

export default function InstallationPage() {
  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/docs" className="hover:text-white">Documentation</Link>
          <span>/</span>
          <span className="text-amber-400">Getting started</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Installation</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          Install the Python framework from PyPI, run the AMP locally for development, or deploy the complete control plane with the published Docker images.
        </p>
      </header>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">Python framework</h2>
          <p className="text-gray-400 mb-4">The published distribution is <code className="text-amber-400">wolfpackai</code>. Python imports remain under <code className="text-amber-400">wolfpack</code>.</p>
          <CodeBlock code="pip install wolfpackai" language="bash" title="Install wolfpackai" />
          <p className="text-gray-400 mt-5 mb-3">Install optional integrations only when you need them:</p>
          <CodeBlock
            code={`pip install "wolfpackai[qdrant]"
pip install "wolfpackai[pgvector]"
pip install "wolfpackai[knowledge]"
pip install "wolfpackai[mcp]"`}
            language="bash"
            title="Optional integrations"
          />
          <div className="mt-4 p-4 bg-gray-800/50 rounded-xl border border-gray-700 text-sm text-gray-400">
            Requires Python 3.10 or later and a model provider credential such as <code className="text-gray-200">OPENAI_API_KEY</code>, <code className="text-gray-200">ANTHROPIC_API_KEY</code>, or <code className="text-gray-200">GOOGLE_API_KEY</code>.
          </div>
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">Local AMP development</h2>
          <p className="text-gray-400 mb-4">Use this path when developing the framework and Control Plane together. It starts PostgreSQL, Redis, MinIO, Qdrant, Prometheus, and the FastAPI backend.</p>
          <CodeBlock
            code={`git clone https://github.com/wolfpackaiagents/wolfpackai.git
cd wolfpackai/control-plane
./run.sh`}
            language="bash"
            title="Start the backend"
          />
          <CodeBlock
            code={`cd control-plane/frontend
npm install
npm run dev`}
            language="bash"
            title="Start the frontend"
          />
          <p className="text-sm text-gray-400 mt-4">The API is served on port 8000 and the development frontend on port 5173.</p>
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">Production Compose deployment</h2>
          <p className="text-gray-400 mb-4">The production Compose file pulls the published frontend and backend images, starts the optional infrastructure services, and exposes the frontend on port 80.</p>
          <CodeBlock
            code={`git clone https://github.com/wolfpackaiagents/wolfpackai.git
cd wolfpackai

export POSTGRES_PASSWORD="..."
export MINIO_ROOT_USER="..."
export MINIO_ROOT_PASSWORD="..."
export ADMIN_API_KEY="..."
export JWT_SECRET="..."
export PROVIDER_SECRETS_MASTER_KEY="..."

docker compose -f docker/docker-compose.production.yml up -d`}
            language="bash"
            title="Deploy AMP"
          />
          <div className="mt-4 grid md:grid-cols-2 gap-4 text-sm text-gray-400">
            <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700"><strong className="text-gray-200 block mb-2">Published images</strong><code>wolfpackaiagents/wolfpack-amp-backend:0.1.0</code><br /><code>wolfpackaiagents/wolfpack-amp-frontend:0.1.0</code></div>
            <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700"><strong className="text-gray-200 block mb-2">Included services</strong>PostgreSQL, Redis, Redis Exporter, Prometheus, MinIO, Qdrant, Inngest, AMP backend, and AMP frontend.</div>
          </div>
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">Development setup</h2>
          <CodeBlock
            code={`git clone https://github.com/wolfpackaiagents/wolfpackai.git
cd wolfpackai/framework
uv sync --extra test --group dev
uv run pytest`}
            language="bash"
            title="Run framework tests"
          />
        </div>
      </section>
    </article>
  );
}
