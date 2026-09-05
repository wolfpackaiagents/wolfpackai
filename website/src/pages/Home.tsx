import { Link } from "react-router-dom";
import { frameworkSections } from "../data/framework";
import { controlPlaneSections } from "../data/control-plane";
import { examples } from "../data/examples.generated";

const categoryNames = [
  "Basic", "Tools", "RAG", "Observability", "Guardrails", "Workflows", "Teams",
  "MCP", "Evals", "Privacy", "Resilience", "Hardening", "Schedules",
  "Personal Agent", "Coding Agent", "Channels",
];

const categoryColors: Record<string, string> = {
  Basic: "from-green-500 to-emerald-600",
  Tools: "from-blue-500 to-cyan-600",
  RAG: "from-purple-500 to-violet-600",
  Observability: "from-violet-500 to-purple-600",
  Guardrails: "from-red-500 to-rose-600",
  Workflows: "from-indigo-500 to-blue-600",
  Teams: "from-orange-500 to-amber-600",
  MCP: "from-teal-500 to-cyan-600",
  Evals: "from-pink-500 to-rose-600",
  Privacy: "from-slate-500 to-gray-600",
  Resilience: "from-cyan-500 to-blue-600",
  Hardening: "from-yellow-500 to-orange-600",
  Schedules: "from-lime-500 to-green-600",
  "Personal Agent": "from-fuchsia-500 to-pink-600",
  "Coding Agent": "from-teal-500 to-cyan-600",
  Channels: "from-yellow-500 to-orange-600",
};

export default function Home() {
  const categories = [...new Set(examples.map((e) => e.category))].sort().map((name) => ({
    name,
    count: examples.filter((e) => e.category === name).length,
    color: categoryColors[name] || "from-gray-500 to-gray-600",
  }));
  return (
    <div className="space-y-16">
      <header className="text-center py-16">
        <div className="w-16 h-16 bg-gradient-to-br from-amber-400 to-orange-600 rounded-2xl flex items-center justify-center font-bold text-2xl mx-auto mb-6">
          W
        </div>
        <h1 className="text-5xl font-bold text-white mb-4 tracking-tight">
          Wolfpack AI
          <span className="ml-3 text-base font-semibold text-amber-400 bg-amber-500/15 px-2.5 py-1 rounded-full align-middle">BETA</span>
        </h1>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto leading-relaxed">
          The open-source framework and control plane for building, deploying, and managing
          autonomous AI agents at scale.
        </p>
        <div className="flex justify-center gap-4 mt-8">
          <Link
            to="/installation"
            className="px-6 py-3 bg-gradient-to-r from-amber-500 to-orange-600 text-white font-medium rounded-xl hover:from-amber-400 hover:to-orange-500 transition-all"
          >
            Get Started
          </Link>
          <Link
            to="/concepts/framework-overview"
            className="px-6 py-3 bg-gray-800 text-gray-200 font-medium rounded-xl hover:bg-gray-700 transition-all border border-gray-700"
          >
            Architecture
          </Link>
        </div>
      </header>

      <section>
        <h2 className="text-2xl font-bold text-white mb-6">Framework</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {frameworkSections.map((section) => (
            <Link
              key={section.id}
              to={`/framework/${section.id}`}
              className="block p-5 bg-gray-900 border border-gray-800 rounded-xl hover:border-amber-500/50 hover:bg-gray-850 transition-all group"
            >
              <h3 className="font-semibold text-white group-hover:text-amber-400 transition-colors mb-2">
                {section.title}
              </h3>
              <p className="text-sm text-gray-400 leading-relaxed line-clamp-3">
                {section.description}
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-6">Control Plane (AMP)</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {controlPlaneSections.map((section) => (
            <Link
              key={section.id}
              to={`/control-plane/${section.id}`}
              className="block p-5 bg-gray-900 border border-gray-800 rounded-xl hover:border-amber-500/50 hover:bg-gray-850 transition-all group"
            >
              <h3 className="font-semibold text-white group-hover:text-amber-400 transition-colors mb-2">
                {section.title}
              </h3>
              <p className="text-sm text-gray-400 leading-relaxed line-clamp-3">
                {section.description}
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-6">
          Examples
          <span className="text-sm font-normal text-gray-400 ml-3">{examples.length} examples across all categories</span>
        </h2>
        <div className="flex flex-wrap gap-3 mb-8">
          {categories.map((cat) => (
            <span
              key={cat.name}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-gradient-to-r ${cat.color} text-white`}
            >
              {cat.name}
              <span className="opacity-80">({cat.count})</span>
            </span>
          ))}
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          {examples.map((example) => (
            <Link
              key={example.id}
              to={`/examples/${example.id}`}
              className="block p-4 bg-gray-900 border border-gray-800 rounded-xl hover:border-amber-500/50 transition-all group"
            >
              <div className="flex items-start justify-between mb-1">
                <h3 className="font-medium text-white group-hover:text-amber-400 transition-colors">
                  {example.title}
                </h3>
                <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400 ml-2 shrink-0">
                  {example.category}
                </span>
              </div>
              <p className="text-sm text-gray-400 line-clamp-2">{example.description}</p>
            </Link>
          ))}
        </div>
      </section>

    </div>
  );
}
