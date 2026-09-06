import { Link } from "react-router-dom";
import { useState } from "react";
import { useI18n } from "../i18n/context";

export default function ConceptAMPControlPlane() {
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
          <span className="text-white">{t.concepts.ampControlPlane}</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">AMP Control Plane</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          The Agent Management Platform architecture connecting traces, registered runtimes, human approvals,
          quality scores, schedules, provider channels, and governance controls.
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
              <img src="/diagrams/amp-control-plane.png" alt="AMP Control Plane" className="w-full h-auto" onError={() => setFailed(true)} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Capabilities</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Traces", desc: "Ingested and queryable telemetry data with full lifecycle and cost attribution." },
            { title: "Mesh Registry", desc: "Register agents, environments, and replicas. Track health and interactions." },
            { title: "Approvals", desc: "Durable human-in-the-loop approval workflows with audit trail." },
            { title: "Scores & Evals", desc: "Configure scoring rubrics, run evaluations, and track quality over time." },
            { title: "Schedules", desc: "Cron, interval, or at-based task scheduling with policy enforcement." },
            { title: "Channels", desc: "Telegram, Slack, and Discord adapters for agent communication." },
            { title: "Privacy", desc: "PII redaction configuration, LGPD data export and deletion." },
            { title: "Governance", desc: "Role-based permissions, retention policies, and alert rules." },
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