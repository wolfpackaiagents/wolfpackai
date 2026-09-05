import { Link } from "react-router-dom";
import { useState } from "react";

export default function ConceptAgentLoop() {
  const [failed, setFailed] = useState(false);

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/" className="hover:text-white">Home</Link>
          <span>/</span>
          <span className="text-amber-400">Concepts</span>
          <span>/</span>
          <span className="text-white">Agent Loop</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Agent Loop Architecture</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          The core agent reasoning loop showing how the Model interacts with Tools, Memory, Guardrails,
          and the Observer to process inputs and generate responses.
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
            it enters a reasoning loop that continues until it produces a final answer or reaches
            <code className="text-amber-400"> max_turns</code>.
          </p>
          <ol className="space-y-3 list-decimal list-inside">
            <li><strong className="text-white">Observe</strong> &mdash; The agent receives the user input along with context from Memory and Knowledge.</li>
            <li><strong className="text-white">Reason</strong> &mdash; The Model processes the input, considering available Tools and Guardrails.</li>
            <li><strong className="text-white">Act</strong> &mdash; If the model decides to call tools, they execute in parallel or sequence.</li>
            <li><strong className="text-white">Observe Results</strong> &mdash; Tool outputs are fed back into the reasoning loop.</li>
            <li><strong className="text-white">Repeat or Answer</strong> &mdash; The agent continues until it has enough information to respond.</li>
          </ol>
          <p>
            The Observer monitors every step, collecting traces and metrics for the AMP observability pipeline.
            Guardrails validate inputs and outputs at each stage to enforce safety and compliance.
          </p>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Key Components</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Model", desc: "The LLM that drives reasoning. Supports OpenAI, Anthropic, Google, and any OpenAI-compatible endpoint." },
            { title: "Tools", desc: "Callable functions that extend agent capabilities — web search, code execution, API calls, file I/O, and more." },
            { title: "Memory", desc: "Conversation history and user context that persists across turns and sessions." },
            { title: "Guardrails", desc: "Safety constraints that validate inputs, outputs, and tool calls at each stage of the loop." },
            { title: "Observer", desc: "Telemetry collector that captures traces, metrics, and logs for the AMP observability pipeline." },
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