import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { examples } from "../data/examples.generated";
import { useI18n } from "../i18n/context";
import { getCategoryLabel, getLocalizedExample } from "../i18n/content";

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
  SQLToolkit: "from-sky-500 to-blue-600",
};

export default function CategoryPage() {
  const { lang } = useI18n();
  const { categoryName } = useParams();
  const decoded = decodeURIComponent(categoryName || "");
  const [selectedDatabase, setSelectedDatabase] = useState<string | null>(null);
  const categoryExamples = examples.filter((e) => e.category === decoded);
  const databases = [...new Set(categoryExamples.flatMap((example) => example.databases ?? []))].sort();
  const filtered = selectedDatabase
    ? categoryExamples.filter((example) => example.databases?.includes(selectedDatabase))
    : categoryExamples;
  const color = categoryColors[decoded] || "from-gray-500 to-gray-600";

  return (
    <div className="space-y-8">
      <header>
        <div className="flex items-center gap-3 mb-2">
          <Link to="/examples" className="text-sm text-amber-400 hover:text-amber-300 transition-colors">
             ← {lang === "pt-BR" ? "Todos os exemplos" : "All Examples"}
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full bg-gradient-to-br ${color}`} />
           <h1 className="text-3xl font-bold text-white">{getCategoryLabel(decoded, lang)}</h1>
          <span className="text-sm text-gray-400 bg-gray-800 px-2 py-0.5 rounded-full">
             {filtered.length} {lang === "pt-BR" ? "exemplo" : "example"}{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>
      </header>

      {databases.length > 0 && (
        <section className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-400 mr-1">{lang === "pt-BR" ? "Banco:" : "Database:"}</span>
          <button
            onClick={() => setSelectedDatabase(null)}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${selectedDatabase === null ? "bg-amber-500 text-gray-950 font-medium" : "bg-gray-800 text-gray-300 hover:bg-gray-700"}`}
          >
            {lang === "pt-BR" ? "Todos" : "All"}
          </button>
          {databases.map((database) => (
            <button
              key={database}
              onClick={() => setSelectedDatabase(database)}
              className={`px-3 py-1.5 rounded-full text-sm transition-colors ${selectedDatabase === database ? "bg-amber-500 text-gray-950 font-medium" : "bg-gray-800 text-gray-300 hover:bg-gray-700"}`}
            >
              {database}
            </button>
          ))}
        </section>
      )}

      <div className="grid gap-4">
         {filtered.map((sourceExample) => {
           const example = getLocalizedExample(sourceExample, lang);
           return (
          <Link
            key={example.id}
            to={`/examples/${example.id}`}
            className="block p-5 rounded-xl border border-gray-800 bg-gray-900 hover:border-amber-500/50 hover:bg-gray-800/80 transition-all group"
          >
            <h3 className="text-lg font-semibold text-white group-hover:text-amber-400 transition-colors">
              {example.title}
            </h3>
            <p className="text-sm text-gray-400 mt-1 line-clamp-2">{example.description}</p>
             <div className="flex items-center gap-2 mt-3">
               <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">{example.language}</span>
               {example.databases?.map((database) => (
                 <span key={database} className="text-xs text-sky-300 bg-sky-500/10 px-2 py-0.5 rounded">{database}</span>
               ))}
               {example.validationStatus === "not-verified" && (
                 <span className="text-xs font-semibold text-amber-300 bg-amber-500/15 px-2 py-0.5 rounded">BETA</span>
               )}
               <span className="text-xs text-amber-500/70 group-hover:text-amber-400 transition-colors">
               {lang === "pt-BR" ? "Ver detalhes" : "View details"} →
              </span>
            </div>
         </Link>
           );
         })}
      </div>
    </div>
  );
}
