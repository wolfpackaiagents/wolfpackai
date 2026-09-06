import { useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { frameworkSections } from "../data/framework";
import { controlPlaneSections } from "../data/control-plane";
import { examples } from "../data/examples.generated";
import { useI18n, LangToggle } from "../i18n/context";

const categories = [...new Set(examples.map((e) => e.category))].sort();

const conceptPages = [
  { labelKey: "agentLoop" as const, path: "/concepts/agent-loop" },
  { labelKey: "teamDelegation" as const, path: "/concepts/team-delegation" },
  { labelKey: "chatArchitecture" as const, path: "/concepts/chat-architecture" },
  { labelKey: "observerFlow" as const, path: "/concepts/observer-flow" },
  { labelKey: "ampControlPlane" as const, path: "/concepts/amp-control-plane" },
  { labelKey: "frameworkOverview" as const, path: "/concepts/framework-overview" },
];

export default function Layout() {
  const { t } = useI18n();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const isActive = (path: string) => location.pathname === path;

  const navItems = [
    { label: t.layout.documentation, path: "/docs" },
    { label: t.layout.aboutAuthor, path: "/sobre-o-autor" },
    {
      label: t.layout.gettingStarted,
      path: "/installation",
      children: [
        { label: t.layout.installation, path: "/installation" },
      ],
    },
    {
      label: t.layout.framework,
      path: "/framework/agent",
      children: frameworkSections.map((s) => ({ label: s.title, path: `/framework/${s.id}` })),
    },
    {
      label: t.layout.concepts,
      path: "/concepts/framework-overview",
      children: conceptPages.map((p) => ({ label: t.concepts[p.labelKey], path: p.path })),
    },
    {
      label: t.layout.controlPlane,
      path: "/control-plane/overview",
      children: controlPlaneSections.map((s) => ({ label: s.title, path: `/control-plane/${s.id}` })),
    },
    {
      label: t.layout.examples,
      path: "/examples",
      children: categories.map((cat) => ({
        label: `${cat} (${examples.filter((e) => e.category === cat).length})`,
        path: `/examples/category/${encodeURIComponent(cat)}`,
      })),
    },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950 text-gray-100">
      <button
        className="fixed top-4 left-4 z-50 md:hidden p-2 bg-gray-800 rounded-lg"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label={t.layout.toggleSidebar}
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {sidebarOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-72 bg-gray-900 border-r border-gray-800 overflow-y-auto transition-transform duration-200 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <Link to="/docs" className="flex items-center gap-3 shrink-0">
            <div className="w-8 h-8 bg-gradient-to-br from-amber-400 to-orange-600 rounded-lg flex items-center justify-center font-bold text-sm">
              W
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Wolfpack AI</h1>
              <span className="text-[10px] font-semibold text-amber-400 bg-amber-500/15 px-1.5 py-0.5 rounded-full ml-1">BETA</span>
              <p className="text-xs text-gray-400">{t.layout.developerDoc}</p>
            </div>
          </Link>
          <LangToggle />
        </div>

        <nav className="p-3 space-y-1">
          {navItems.map((item) => (
            <div key={item.path}>
              <Link
                to={item.path}
                onClick={() => setSidebarOpen(false)}
                className={`block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive(item.path) && !item.children
                    ? "bg-amber-500/20 text-amber-400"
                    : "text-gray-300 hover:bg-gray-800 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
              {item.children && (
                <div className="ml-3 mt-1 space-y-0.5 border-l border-gray-800 pl-3">
                  {item.children.map((child) => (
                    <Link
                      key={child.path}
                      to={child.path}
                      onClick={() => setSidebarOpen(false)}
                      className={`block px-3 py-1.5 rounded text-sm transition-colors ${
                        isActive(child.path)
                          ? "bg-amber-500/20 text-amber-400 font-medium"
                          : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
                      }`}
                    >
                      {child.label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
        </nav>
      </aside>

      {sidebarOpen && (
        <div className="fixed inset-0 z-30 bg-black/50 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}