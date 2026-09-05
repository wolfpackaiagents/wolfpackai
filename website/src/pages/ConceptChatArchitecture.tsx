import { Link } from "react-router-dom";
import { useState } from "react";

export default function ConceptChatArchitecture() {
  const [failed, setFailed] = useState(false);

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/docs" className="hover:text-white">Documentation</Link>
          <span>/</span>
          <span className="text-amber-400">Concepts</span>
          <span>/</span>
          <span className="text-white">Chat Architecture</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Chat Architecture</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          End-to-end chat architecture showing how the AMP web interface dispatches persistent conversations
          to registered runtimes through the Chat API.
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
              <img src="/diagrams/chat-architecture.png" alt="Chat Architecture" className="w-full h-auto" onError={() => setFailed(true)} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Architecture Overview</h2>
        <div className="space-y-4 text-gray-300 leading-relaxed">
          <p>
            AMP Chat stores conversations and targets an enabled Mesh registration with a configured chat endpoint.
            It authenticates requests with a project API key and keeps a stable session identifier across turns.
          </p>
          <ol className="space-y-3 list-decimal list-inside">
            <li><strong className="text-white">Conversation</strong>: the web client creates or selects a persistent conversation.</li>
            <li><strong className="text-white">Registration</strong>: AMP verifies the selected runtime is enabled and has a chat endpoint.</li>
            <li><strong className="text-white">Dispatch</strong>: the backend posts the request to that endpoint.</li>
            <li><strong className="text-white">Run events</strong>: Server-Sent Events expose lifecycle and final-result events for the chat run.</li>
          </ol>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Key Features</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Run events", desc: "The interface consumes Server-Sent Events for run state and the completed result." },
            { title: "Session Management", desc: "Multi-turn conversations with context persistence across messages." },
            { title: "Registered runtimes", desc: "Conversations target enabled agent or team registrations with a chat endpoint." },
            { title: "Trace links", desc: "The run inspector links conversation activity to its trace context." },
          ].map((feat) => (
            <div key={feat.title} className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
              <h3 className="font-semibold text-white mb-1">{feat.title}</h3>
              <p className="text-sm text-gray-400">{feat.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </article>
  );
}
