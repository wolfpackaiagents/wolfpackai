import { Link } from "react-router-dom";
import { useState } from "react";

export default function ConceptChatArchitecture() {
  const [failed, setFailed] = useState(false);

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/" className="hover:text-white">Home</Link>
          <span>/</span>
          <span className="text-amber-400">Concepts</span>
          <span>/</span>
          <span className="text-white">Chat Architecture</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Chat Architecture</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          End-to-end chat architecture showing how frontend applications connect through AMP Gateway
          to agent runtimes via the Chat API and SSE channels.
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
            The Chat Architecture connects multiple frontend channels (web UI, Slack, Discord, mobile apps)
            to agent runtimes through the AMP Gateway. The Gateway handles authentication, rate limiting,
            session management, and message routing.
          </p>
          <ol className="space-y-3 list-decimal list-inside">
            <li><strong className="text-white">Frontend Channels</strong> &mdash; Users interact through web chat, Slack, Discord, Telegram, or custom UIs.</li>
            <li><strong className="text-white">AMP Gateway</strong> &mdash; Central entry point that authenticates requests, manages sessions, and routes messages.</li>
            <li><strong className="text-white">Chat API</strong> &mdash; REST and SSE interface for sending messages and receiving streaming responses.</li>
            <li><strong className="text-white">Agent Runtime</strong> &mdash; Executes agent reasoning loops, tool calls, and memory operations.</li>
            <li><strong className="text-white">Response Stream</strong> &mdash; Tokens are streamed back in real-time via SSE.</li>
          </ol>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Key Features</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Streaming Responses", desc: "Tokens arrive in real-time as the model generates them for instant user feedback." },
            { title: "Session Management", desc: "Multi-turn conversations with context persistence across messages." },
            { title: "Multi-Channel", desc: "Unified agent accessible from web, Slack, Discord, and Telegram." },
            { title: "Agent Handoff", desc: "Seamless transfer between specialized agents mid-conversation." },
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