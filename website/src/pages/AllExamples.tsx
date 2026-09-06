import { Link } from "react-router-dom";
import { examples } from "../data/examples.generated";
import { useI18n } from "../i18n/context";

const categories = [...new Set(examples.map((e) => e.category))].sort();

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

export default function AllExamples() {
  return (
    <div className="space-y-12">
      <header>
        <h1 className="text-3xl font-bold text-white mb-2">Examples</h1>
        <p className="text-gray-400">
          Browse through {examples.length} examples organized by category. Each example includes complete code,
          step-by-step instructions, and expected output.
        </p>
      </header>

      {categories.map((cat) => {
        const filtered = examples.filter((e) => e.category === cat);
        const color = categoryColors[cat] || "from-gray-500 to-gray-600";
        return (
          <section key={cat}>
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-3 h-3 rounded-full bg-gradient-to-br ${color}`} />
              <Link
                to={`/examples/category/${encodeURIComponent(cat)}`}
                className="text-xl font-semibold text-white hover:text-amber-400 transition-colors"
              >
                {cat}
              </Link>
              <span className="text-sm text-gray-500">({filtered.length})</span>
            </div>
            <div className="grid md:grid-cols-2 gap-3">
              {filtered.map((ex) => (
                <Link
                  key={ex.id}
                  to={`/examples/${ex.id}`}
                  className="block p-4 rounded-xl border border-gray-800 bg-gray-900/50 hover:border-amber-500/50 hover:bg-gray-800/80 transition-all group"
                >
                  <h4 className="font-medium text-white group-hover:text-amber-400 transition-colors">{ex.title}</h4>
                  <p className="text-sm text-gray-400 mt-1 line-clamp-2">{ex.description}</p>
                </Link>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
