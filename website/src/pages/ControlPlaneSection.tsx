import { useParams, Link } from "react-router-dom";
import { useI18n } from "../i18n/context";
import { getControlPlaneSections } from "../i18n/content";

export default function ControlPlaneSection() {
  const { lang, t } = useI18n();
  const { sectionId } = useParams<{ sectionId: string }>();
  const sections = getControlPlaneSections(lang);
  const section = sections.find((s) => s.id === sectionId);

  if (!section) {
    return (
      <div className="text-center py-20">
        <h2 className="text-2xl font-bold text-white mb-4">{t.common.notFound}</h2>
        <p className="text-gray-400 mb-6">The control plane section "{sectionId}" does not exist.</p>
        <Link to="/docs" className="text-amber-400 hover:text-amber-300">{t.common.returnToDocs}</Link>
      </div>
    );
  }

  const screenshot = `/screenshots/${section.id}.png`;

  const hasScreenshot = ["overview", "mesh", "chat", "channels", "schedules", "traces", "approvals", "guardrails", "scores", "resilience", "privacy", "settings", "secrets", "sessions"].includes(section.id);

  return (
    <article className="space-y-8">
      <header>
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
          <Link to="/docs" className="hover:text-white">{t.common.documentation}</Link>
          <span>/</span>
          <span className="text-amber-400">{t.layout.controlPlane}</span>
          <span>/</span>
          <span className="text-white">{section.title}</span>
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">{section.title}</h1>
        <p className="text-lg text-gray-300 leading-relaxed">{section.description}</p>
      </header>

      <div className="flex flex-wrap gap-2">
        {sections.map((s) => (
          <Link
            key={s.id}
            to={`/control-plane/${s.id}`}
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

      {hasScreenshot && (
        <section>
          <h2 className="text-2xl font-bold text-white mb-4">{lang === "pt-BR" ? "Captura de tela" : "Screenshot"}</h2>
          <div className="rounded-xl overflow-hidden border border-gray-800 bg-gray-900/50">
            <img
              src={screenshot}
              alt={lang === "pt-BR" ? `Captura de tela de ${section.title}` : `${section.title} screenshot`}
              className="w-full h-auto object-contain"
              loading="lazy"
            />
          </div>
        </section>
      )}
    </article>
  );
}
