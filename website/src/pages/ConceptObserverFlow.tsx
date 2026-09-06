import { Link } from "react-router-dom";
import { useState } from "react";
import { useI18n } from "../i18n/context";

export default function ConceptObserverFlow() {
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/docs" className="hover:text-white">{t.common.documentation}</Link>
          <span>/</span>
          <span className="text-amber-400">{t.layout.concepts}</span>
          <span>/</span>
          <span className="text-white">{t.concepts.observerFlow}</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Observer Data Flow</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          How WolfpackObserver collects agent telemetry and forwards buffered trace data to the AMP ingestion pipeline.
        </p>
      </header>

      <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="p-6">
          {failed ? (
            <div className="flex items-center justify-center h-64 bg-gray-800/50 rounded-xl border border-dashed border-gray-700">
              <div className="text-center">
                <svg className="w-12 h-12 text-gray-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p className="text-sm text-gray-500">{t.concepts.comingSoon}</p>
                <p className="text-xs text-gray-600 mt-1">{t.concepts.runCommand} <code className="text-amber-400">npm run generate-diagrams</code></p>
              </div>
            </div>
          ) : (
            <div className="rounded-xl overflow-hidden bg-gray-800">
              <img src="/diagrams/observer-flow.png" alt="Observer Data Flow" className="w-full h-auto" onError={() => setFailed(true)} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">How the Observer Works</h2>
        <div className="space-y-4 text-gray-300 leading-relaxed">
          <p>
            WolfpackObserver implements the Tracker contract and is injected into the agent at construction
            time. It buffers events and sends them to the AMP ingestion endpoint.
          </p>
          <ol className="space-y-3 list-decimal list-inside">
            <li><strong className="text-white">Capture</strong>: the agent emits start/end events for traces, spans, and tool calls.</li>
            <li><strong className="text-white">Buffer</strong>: events are batched in memory up to the configured batch size.</li>
            <li><strong className="text-white">Flush</strong>: when the batch is full, events are sent to the AMP ingestion endpoint.</li>
            <li><strong className="text-white">Retry</strong>: if the flush fails, the observer retries up to 3 times with backoff.</li>
          </ol>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Key Features</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "PII Redaction", desc: "Personally identifiable information can be masked before leaving the agent process." },
            { title: "Mesh Support", desc: "MeshIdentity propagation for multi-agent interaction tracking." },
            { title: "Batched Flush", desc: "Configurable batch size to balance latency and throughput." },
            { title: "Resilient", desc: "Retries with exponential backoff; failures are logged but never block the agent." },
          ].map((item) => (
            <div key={item.title} className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
              <h3 className="font-semibold text-white mb-1">{item.title}</h3>
              <p className="text-sm text-gray-400">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </article>
  );
}