import { Link } from "react-router-dom";
import { useState } from "react";

export default function ConceptTeamDelegation() {
  const [failed, setFailed] = useState(false);

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/" className="hover:text-white">Home</Link>
          <span>/</span>
          <span className="text-amber-400">Concepts</span>
          <span>/</span>
          <span className="text-white">Team Delegation</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Team Delegation Architecture</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          How the Team leader decomposes tasks and delegates them to specialist agents, with result
          aggregation and shared memory across all members.
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
              <img src="/diagrams/team-delegation.png" alt="Team Delegation Architecture" className="w-full h-auto" onError={() => setFailed(true)} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">How It Works</h2>
        <div className="space-y-4 text-gray-300 leading-relaxed">
          <p>
            Teams enable hierarchical multi-agent collaboration. A <strong className="text-white">Team</strong> consists of a leader Agent
            and one or more specialist member Agents. The leader receives the user's request, decomposes it into
            subtasks, and delegates each subtask to the most qualified member.
          </p>
          <ol className="space-y-3 list-decimal list-inside">
            <li><strong className="text-white">Task Decomposition</strong> &mdash; The leader analyzes the request and breaks it into discrete subtasks.</li>
            <li><strong className="text-white">Agent Selection</strong> &mdash; The leader selects the best member for each subtask based on their tools and instructions.</li>
            <li><strong className="text-white">Delegation</strong> &mdash; Each member receives their subtask with relevant context from shared memory.</li>
            <li><strong className="text-white">Execution</strong> &mdash; Members execute their assigned work, using their specialized tools and knowledge.</li>
            <li><strong className="text-white">Result Aggregation</strong> &mdash; The leader collects all outputs and synthesizes them into a final response.</li>
          </ol>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Delegation Modes</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Auto", desc: "The leader dynamically decides which member handles each subtask based on capabilities." },
            { title: "Round Robin", desc: "Subtasks are assigned sequentially to members in a fixed order." },
            { title: "Broadcast", desc: "All members receive the same task simultaneously. Used for consensus and voting." },
            { title: "Consensus", desc: "Members debate and reach agreement over multiple rounds before producing a final answer." },
          ].map((mode) => (
            <div key={mode.title} className="p-4 bg-gray-800/50 rounded-xl border border-gray-700">
              <h3 className="font-semibold text-white mb-1">{mode.title}</h3>
              <p className="text-sm text-gray-400">{mode.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </article>
  );
}