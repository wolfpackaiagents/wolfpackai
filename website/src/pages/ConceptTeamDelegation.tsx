import { Link } from "react-router-dom";
import { useState } from "react";
import { useI18n } from "../i18n/context";

export default function ConceptTeamDelegation() {
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
          <span className="text-white">{t.concepts.teamDelegation}</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">Team Delegation Architecture</h1>
        <p className="text-lg text-gray-300 leading-relaxed">
          How the Team leader decomposes tasks and delegates them to specialist agents, with result
          aggregation from independent specialist agents.
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
              <img src="/diagrams/team-delegation.png" alt="Team Delegation Architecture" className="w-full h-auto" onError={() => setFailed(true)} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">How Team Delegation Works</h2>
        <div className="space-y-4 text-gray-300 leading-relaxed">
          <p>
            The Team abstracts multi-agent orchestration behind a single interface. When the agent receives a
            request, the leader decomposes the task and delegates subtasks to the most suitable member agent.
          </p>
          <ol className="space-y-3 list-decimal list-inside">
            <li><strong className="text-white">Receive</strong>: the team receives a request that requires specialist knowledge.</li>
            <li><strong className="text-white">Decompose</strong>: the leader analyzes the request and splits it into subtasks.</li>
            <li><strong className="text-white">Delegate</strong>: each subtask is assigned to the member with the most relevant tools and expertise.</li>
            <li><strong className="text-white">Aggregate</strong>: the leader collects results, resolves conflicts, and produces a final answer.</li>
          </ol>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Delegation Modes</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: "Coordinate", desc: "Leader-driven: the leader decomposes, delegates, and aggregates." },
            { title: "Route", desc: "Direct dispatch: the leader routes the entire request to the best member." },
            { title: "Broadcast", desc: "Parallel fan-out: every member receives the same request independently." },
            { title: "Tasks", desc: "Independent tasks: explicitly constructed subtasks executed by their target member." },
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