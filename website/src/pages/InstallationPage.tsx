import { Link } from "react-router-dom";
import CodeBlock from "../components/CodeBlock";
import { useI18n } from "../i18n/context";

export default function InstallationPage() {
  const { t } = useI18n();
  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/docs" className="hover:text-white">{t.common.documentation}</Link>
          <span>/</span>
          <span className="text-amber-400">{t.layout.gettingStarted}</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">{t.installation.title}</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          {t.installation.subtitle}
        </p>
      </header>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">{t.installation.pythonFramework}</h2>
          <p className="text-gray-400 mb-4">The published distribution is <code className="text-amber-400">wolfpackai</code>. Python imports remain under <code className="text-amber-400">wolfpack</code>.</p>
          <CodeBlock code="pip install wolfpackai" language="bash" title={t.installation.pipInstall} />
          <p className="text-gray-400 mt-5 mb-3">{t.installation.optionalIntegrations}:</p>
          <CodeBlock
            code={`pip install "wolfpackai[qdrant]"
pip install "wolfpackai[pgvector]"
pip install "wolfpackai[knowledge]"
pip install "wolfpackai[mcp]"`}
            language="bash"
            title={t.installation.optionalIntegrations}
          />
          <div className="mt-4 p-4 bg-gray-800/50 rounded-xl border border-gray-700 text-sm text-gray-400">
            {t.installation.requiresPython} <code className="text-gray-200">OPENAI_API_KEY</code>, <code className="text-gray-200">ANTHROPIC_API_KEY</code>, or <code className="text-gray-200">GOOGLE_API_KEY</code>.
          </div>
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">{t.installation.localAmp}</h2>
          <p className="text-gray-400 mb-4">{t.installation.localAmpDesc}</p>
          <CodeBlock
            code={`git clone https://github.com/wolfpackaiagents/wolfpackai.git
cd wolfpackai/control-plane
./run.sh`}
            language="bash"
            title={t.installation.startBackend}
          />
          <CodeBlock
            code={`cd control-plane/frontend
npm install
npm run dev`}
            language="bash"
            title={t.installation.startFrontend}
          />
          <p className="text-sm text-gray-400 mt-4">{t.installation.apiServed}</p>
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">{t.installation.productionDeploy}</h2>
          <p className="text-gray-400 mb-4">{t.installation.productionDesc}</p>
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
            title={t.installation.deployAmp}
          />
          <div className="mt-4 grid md:grid-cols-2 gap-4 text-sm text-gray-400">
            <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700"><strong className="text-gray-200 block mb-2">{t.installation.publishedImages}</strong><code>wolfpackaiagents/wolfpack-amp-backend:0.1.1</code><br /><code>wolfpackaiagents/wolfpack-amp-frontend:0.1.0</code></div>
            <div className="p-4 bg-gray-800/50 rounded-xl border border-gray-700"><strong className="text-gray-200 block mb-2">{t.installation.includedServices}</strong>PostgreSQL, Redis, Redis Exporter, Prometheus, MinIO, Qdrant, Inngest, AMP backend, and AMP frontend.</div>
          </div>
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white mb-4">{t.installation.devSetup}</h2>
          <CodeBlock
            code={`git clone https://github.com/wolfpackaiagents/wolfpackai.git
cd wolfpackai/framework
uv sync --extra test --group dev
uv run pytest`}
            language="bash"
            title={t.installation.runTests}
          />
        </div>
      </section>
    </article>
  );
}