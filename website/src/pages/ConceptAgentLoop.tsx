import { Link } from "react-router-dom";
import { useState } from "react";
import { useI18n } from "../i18n/context";

export default function ConceptAgentLoop() {
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
          <span className="text-white">{t.concepts.agentLoop}</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Agent Loop Architecture</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          The core execution loop showing how a model uses typed tools, optional knowledge, session memory,
          guardrails, and telemetry to process a request.
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
              <img src="/diagrams/agent-loop.png" alt="Agent Loop Architecture" className="w-full h-auto" onError={() => setFailed(true)} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">How It Works</h2>
        <div className="space-y-4 text-gray-300 leading-relaxed">
          <p>
            The Agent Loop is the fundamental execution model in Wolfpack AI. When an agent receives input,
            it continues until it produces a final answer or reaches
            <code className="text-amber-400"> max_iterations</code>.
          </p>
          <ol className="space-y-3 list-decimal list-inside">
            <li><strong className="text-white">Prepare</strong>: the agent applies configured input hooks and resolves optional session context.</li>
            <li><strong className="text-white">Invoke</strong>: the model receives the request and available tool schemas.</li>
            <li><strong className="text-white">Execute</strong>: requested tools run and their results are added to the conversation.</li>
            <li><strong className="text-white">Repeat or answer</strong>: the loop continues until the model returns content or reaches the configured limit.</li>
          </ol>
          <p>
            A Tracker can monitor every step. WolfpackObserver sends the resulting trace data to AMP, while the built-in guardrails can mask personally identifiable information, block prompt injection, and restrict tools.
          </p>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Key Components</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Model", desc: "The LLM that drives reasoning. Supports OpenAI, Anthropic, Google, and any OpenAI-compatible endpoint." },
            { title: "Tools", desc: "Callable Python functions exposed through @tool or Toolkit." },
            { title: "Memory", desc: "SessionMemory persists multi-turn history through a configured session store." },
            { title: "Guardrails", desc: "PII masking, prompt injection checks, tool allowlists, and custom hooks." },
            { title: "Telemetry", desc: "Tracker implementations capture spans; WolfpackObserver forwards them to AMP." },
            { title: "Knowledge", desc: "RAG system that retrieves relevant documents to ground the model's responses in factual data." },
          ].map((comp) => (
            <div key={comp.title} className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
              <h3 className="font-semibold text-white mb-1">{comp.title}</h3>
              <p className="text-sm text-gray-400">{comp.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </article>
  );
}