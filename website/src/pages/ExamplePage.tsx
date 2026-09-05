import { useParams, Link } from "react-router-dom";
import { examples } from "../data/examples.generated";
import CodeBlock from "../components/CodeBlock";

export default function ExamplePage() {
  const { exampleId } = useParams<{ exampleId: string }>();
  const example = examples.find((e) => e.id === exampleId);

  if (!example) {
    return (
      <div className="text-center py-20">
        <h2 className="text-2xl font-bold text-white mb-4">Example Not Found</h2>
        <p className="text-gray-400 mb-6">The example "{exampleId}" does not exist.</p>
        <Link to="/docs" className="text-amber-400 hover:text-amber-300">Return to documentation</Link>
      </div>
    );
  }

  const categoryExamples = examples.filter(
    (e) => e.category === example.category && e.id !== example.id
  );

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/docs" className="hover:text-white">Documentation</Link>
          <span>/</span>
          <span className="text-amber-400">Examples</span>
          <span>/</span>
          <span className="text-white">{example.title}</span>
        </div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">{example.title}</h1>
            <span className="inline-block px-3 py-1 rounded-full text-sm font-medium bg-gray-800 text-gray-300 border border-gray-700">
              {example.category}
            </span>
          </div>
        </div>
        <p className="text-lg text-gray-300 leading-relaxed mt-4">{example.description}</p>
      </header>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Code</h2>
        <CodeBlock code={example.code} language={example.language} title={example.title} />
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Step-by-Step</h2>
        <ol className="space-y-4">
          {example.steps.map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex items-center justify-center w-8 h-8 rounded-full bg-amber-500/20 text-amber-400 font-bold text-sm shrink-0">
                {i + 1}
              </span>
              <p className="text-gray-300 pt-1.5">{step}</p>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">Explanation</h2>
        <div className="prose prose-invert prose-gray max-w-none">
          <p className="text-gray-300 leading-relaxed">{example.explanation}</p>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white mb-4">How to Run</h2>
        <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl space-y-3">
          <div>
            <span className="text-sm text-gray-400">Command:</span>
            <pre className="text-sm text-gray-200 font-mono mt-1">{example.command}</pre>
          </div>
          <div>
            <span className="text-sm text-gray-400">Source:</span>
            <pre className="text-sm text-gray-200 font-mono mt-1">{example.sourcePath}</pre>
          </div>
          {example.prerequisites.length > 0 && (
            <div>
              <span className="text-sm text-gray-400">Prerequisites:</span>
              <ul className="text-sm text-gray-200 mt-1 list-disc list-inside">
                {example.prerequisites.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Validation:</span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${example.validationStatus === "passed" ? "text-green-400 bg-green-500/15" : "text-amber-400 bg-amber-500/15"}`}>
              {example.validationStatus === "passed" ? "PASSED" : "NEEDS REPAIR"}
            </span>
            <span className="text-xs text-gray-500">({example.validatedAt})</span>
          </div>
          <div className="text-xs text-gray-500">
            Verification class: {example.verificationClass}
          </div>
        </div>
      </section>

      {example.expectedOutput && (
        <section>
          <h2 className="text-2xl font-bold text-white mb-4">Expected Output</h2>
          <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl">
            <pre className="text-sm text-gray-200 whitespace-pre-wrap font-mono">
              {example.expectedOutput}
            </pre>
          </div>
        </section>
      )}

      {categoryExamples.length > 0 && (
        <section>
          <h2 className="text-xl font-bold text-white mb-3">
            More {example.category} Examples
          </h2>
          <div className="flex flex-wrap gap-2">
            {categoryExamples.map((ex) => (
              <Link
                key={ex.id}
                to={`/examples/${ex.id}`}
                className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-300 hover:text-white hover:border-amber-500/50 transition-all"
              >
                {ex.title}
              </Link>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}
