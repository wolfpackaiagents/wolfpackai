import { Link } from "react-router-dom";
import { useState } from "react";

export default function ConceptObserverFlow() {
  const [failed, setFailed] = useState(false);

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/docs" className="hover:text-white">Documentation</Link>
          <span>/</span>
          <span className="text-amber-400">Concepts</span>
          <span>/</span>
          <span className="text-white">Observer Flow</span>
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
                <p className="text-sm text-gray-500">Diagram not generated yet</p>
                <p className="text-xs text-gray-600 mt-1">Run <code className="text-amber-400">npm run generate-diagrams</code> to create it</p>
              </div>
            </div>
          ) : (
            <div className="rounded-xl overflow-hidden bg-gray-800">
              <img src="/diagrams/observer-data-flow.png" alt="Observer Data Flow" className="w-full h-auto" onError={() => setFailed(true)} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Data Flow Pipeline</h2>
        <div className="space-y-4 text-gray-300 leading-relaxed">
          <p>
            WolfpackObserver implements the framework Tracker contract. It records agent, model, and tool activity,
            optionally redacts personally identifiable information, and batches events for AMP ingestion.
          </p>
          <ol className="space-y-3 list-decimal list-inside">
            <li><strong className="text-white">Instrumentation</strong>: the tracker receives run, model, tool, and approval events from the framework.</li>
            <li><strong className="text-white">Trace creation</strong>: those events form nested trace and span payloads with timing, inputs, outputs, usage, and cost.</li>
            <li><strong className="text-white">Ingestion</strong>: WolfpackObserver sends its buffered payload to AMP over the public ingestion API.</li>
            <li><strong className="text-white">Storage</strong>: AMP persists traces and related observations in PostgreSQL, with retention and redaction controls.</li>
            <li><strong className="text-white">Operations</strong>: dashboards, trace detail, scores, and alert rules expose the stored evidence.</li>
          </ol>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Captured Data</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Traces", desc: "End-to-end execution traces showing every step of agent reasoning, with hierarchical span structure." },
            { title: "Latency metrics", desc: "Run and span timing support aggregate p50 and p95 views." },
            { title: "Token Usage", desc: "Prompt and completion token counts per model call, aggregated over time." },
            { title: "Error Rates", desc: "Error tracking for model failures, tool exceptions, and guardrail violations." },
            { title: "Tool Usage", desc: "Which tools are called, how often, and their success/failure rates." },
            { title: "Cost Tracking", desc: "Estimated cost per agent run based on token usage and model pricing." },
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
