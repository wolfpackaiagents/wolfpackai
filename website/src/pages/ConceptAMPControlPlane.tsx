import { Link } from "react-router-dom";
import { useState } from "react";

export default function ConceptAMPControlPlane() {
  const [failed, setFailed] = useState(false);

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/" className="hover:text-white">Home</Link>
          <span>/</span>
          <span className="text-amber-400">Concepts</span>
          <span>/</span>
          <span className="text-white">AMP Control Plane</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">AMP Control Plane</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          The Agent Management Platform architecture showing Mesh Registry, Chat API, Channel integrations,
          Scheduler, and Observability services working together.
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
              <img src="/diagrams/amp-control-plane.png" alt="AMP Control Plane" className="w-full h-auto" onError={() => setFailed(true)} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Architecture Overview</h2>
        <div className="space-y-4 text-gray-300 leading-relaxed">
          <p>
            The AMP Control Plane is the centralized management layer for Wolfpack AI agents. It provides
            service discovery, chat infrastructure, channel integrations, scheduling, secrets management,
            and full observability across all deployed agents.
          </p>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Core Services</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Mesh Registry", desc: "Service discovery and agent registry. Agents register with capabilities and find each other dynamically." },
            { title: "Chat API", desc: "REST and SSE interface for multi-turn conversations with streaming responses." },
            { title: "Channels", desc: "Bidirectional bridges to Slack, Discord, and Telegram." },
            { title: "Scheduler", desc: "Cron-based and interval-based autonomous agent execution for monitoring and reporting." },
            { title: "Observability", desc: "Distributed tracing, metrics aggregation, logging, and alerting for all agents." },
            { title: "Secrets Manager", desc: "Encrypted storage for API keys and credentials with rotation policies and audit logging." },
          ].map((service) => (
            <div key={service.title} className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
              <h3 className="font-semibold text-white mb-1">{service.title}</h3>
              <p className="text-sm text-gray-400">{service.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </article>
  );
}