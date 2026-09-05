import { Link } from "react-router-dom";
import { useState } from "react";

export default function ConceptFrameworkOverview() {
  const [failed, setFailed] = useState(false);

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/docs" className="hover:text-white">Documentation</Link>
          <span>/</span>
          <span className="text-amber-400">Concepts</span>
          <span>/</span>
          <span className="text-white">Framework Overview</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Framework Overview</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          Complete Wolfpack AI framework showing all major components: Agent, Tools, Team, Memory,
          Knowledge, Guardrails, Workflow, and Observability.
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
              <img src="/diagrams/framework-overview.png" alt="Framework Overview" className="w-full h-auto" onError={() => setFailed(true)} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Framework Components</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Agent", desc: "Core execution loop that combines a model, typed tools, optional knowledge, session memory, guardrails, and telemetry." },
            { title: "Tools", desc: "Typed Python functions exposed with @tool and reusable Toolkit groups." },
            { title: "Team", desc: "Leader-driven or deterministic multi-agent orchestration with coordinate, route, broadcast, and tasks modes." },
            { title: "Memory", desc: "Session context persisted through in-memory or SQLite session stores." },
            { title: "Knowledge", desc: "Document and text retrieval through Knowledge, embeddings, and a configured vector database." },
            { title: "Guardrails", desc: "PII masking, prompt injection checks, tool allowlists, custom hooks, and durable approvals." },
            { title: "Workflow", desc: "Deterministic dependency-aware steps with retry and conditional execution." },
            { title: "Observability", desc: "OpenTelemetry-style tracing and WolfpackObserver ingestion into AMP." },
          ].map((comp) => (
            <div key={comp.title} className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
              <h3 className="font-semibold text-white mb-1">{comp.title}</h3>
              <p className="text-sm text-gray-400">{comp.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Ecosystem</h2>
        <div className="space-y-4 text-gray-300 leading-relaxed">
          <p>
            Wolfpack AI is organized into two main layers:
          </p>
          <ul className="space-y-3">
            <li>
              <strong className="text-white">Framework</strong>: the Python library (<code className="text-amber-400">pip install wolfpackai</code>) that provides agents, typed tools, teams, memory, knowledge, guardrails, workflows, and AMP telemetry.
            </li>
            <li>
              <strong className="text-white">Control Plane (AMP)</strong> &mdash; The management platform deployed via Docker Compose that adds Mesh Registry, Chat API, Channels, Scheduler, Secrets, and Observability on top of the framework.
            </li>
          </ul>
        </div>
      </section>
    </article>
  );
}
