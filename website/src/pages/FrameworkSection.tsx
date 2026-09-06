import { useParams, Link } from "react-router-dom";
import { frameworkSections } from "../data/framework";
import CodeBlock from "../components/CodeBlock";
import { useI18n } from "../i18n/context";

export default function FrameworkSection() {
  const { t } = useI18n();
  const { sectionId } = useParams<{ sectionId: string }>();
  const section = frameworkSections.find((s) => s.id === sectionId);

  if (!section) {
    return (
      <div className="text-center py-20">
        <h2 className="text-2xl font-bold text-white mb-4">{t.common.notFound}</h2>
        <p className="text-gray-400 mb-6">The framework section "{sectionId}" does not exist.</p>
        <Link to="/docs" className="text-amber-400 hover:text-amber-300">{t.common.returnToDocs}</Link>
      </div>
    );
  }

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/docs" className="hover:text-white">{t.common.documentation}</Link>
          <span>/</span>
          <span className="text-amber-400">{t.layout.framework}</span>
          <span>/</span>
          <span className="text-white">{section.title}</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">{section.title}</h1>
        <p className="text-lg text-gray-300 leading-relaxed">{section.description}</p>
      </header>

      <div className="flex flex-wrap gap-2">
        {frameworkSections.map((s) => (
          <Link
            key={s.id}
            to={`/framework/${s.id}`}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              s.id === section.id
                ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                : "bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700"
            }`}
          >
            {s.title}
          </Link>
        ))}
      </div>

      {section.parameters && section.parameters.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold text-white mb-4">Parameters</h2>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/50">
                  <th className="px-4 py-3 text-left font-medium text-gray-300">Parameter</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-300">Type</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-300">Required</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-300">Default</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-300">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {section.parameters.map((param) => (
                  <tr key={param.name} className="hover:bg-gray-800/30">
                    <td className="px-4 py-3 font-mono text-amber-400">{param.name}</td>
                    <td className="px-4 py-3 font-mono text-gray-400">{param.type}</td>
                    <td className="px-4 py-3">
                      {param.required ? (
                        <span className="text-green-400">Yes</span>
                      ) : (
                        <span className="text-gray-500">No</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-400">{param.default || "-"}</td>
                    <td className="px-4 py-3 text-gray-300">{param.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {section.codeExamples && section.codeExamples.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold text-white mb-4">Code Examples</h2>
          <div className="space-y-6">
            {section.codeExamples.map((example, i) => (
              <div key={i}>
                <h3 className="text-lg font-semibold text-white mb-2">{example.title}</h3>
                {example.description && (
                  <p className="text-sm text-gray-400 mb-3">{example.description}</p>
                )}
                <CodeBlock code={example.code} language={example.language} title={example.title} />
              </div>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}
