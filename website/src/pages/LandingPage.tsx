import { Link } from "react-router-dom";
import { useState } from "react";
import { useI18n, LangToggle } from "../i18n/context";

const externalLinks = {
  github: "https://github.com/wolfpackaiagents/wolfpackai",
  pypi: "https://pypi.org/project/wolfpackai/",
  docker: "https://hub.docker.com/u/wolfpackaiagents",
};

const useCaseKeys = ["support", "knowledge", "compliance", "scheduled", "research", "quality"] as const;

const useCaseData = {
  support: {
    framework: ["Agent", "SessionMemory", "@tool", "Web chat adapters"],
    operate: ["Sessions", "Traces", "Channels", "Scores"],
    flow: ["Customer message", "Session-aware agent", "Support tools", "Trace and score"],
  },
  knowledge: {
    framework: ["Knowledge", "Embeddings", "Qdrant or PGVector", "Typed search tool"],
    operate: ["Trace Explorer", "Privacy", "Retention", "Cost"],
    flow: ["Source material", "Vector retrieval", "Grounded response", "Governed trace"],
  },
  compliance: {
    framework: ["PII guardrail", "Prompt injection guardrail", "Tool allowlist", "Approvals"],
    operate: ["Approval queue", "Privacy controls", "Audit context", "Alerts"],
    flow: ["Sensitive request", "Guardrail check", "Human decision", "Auditable outcome"],
  },
  scheduled: {
    framework: ["Workflow", "Schedule toolkit", "HTTP runtime runner", "Agent tools"],
    operate: ["Schedules", "Run history", "Policies", "Resilience"],
    flow: ["Schedule trigger", "Registered runtime", "Task execution", "Run history"],
  },
  research: {
    framework: ["Team", "Coordinate mode", "Route mode", "Member tools"],
    operate: ["Nested traces", "Mesh interactions", "Usage", "Cost"],
    flow: ["Research request", "Team delegation", "Member outputs", "Reviewed result"],
  },
  quality: {
    framework: ["EvalRunner", "Callable evaluators", "AmpScorePublisher", "Telemetry"],
    operate: ["Scores", "Evals", "Metrics", "Alert rules"],
    flow: ["Agent run", "Evaluation", "Score evidence", "Operational decision"],
  },
};

function Arrow() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-4 h-4" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function ExternalArrow() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-4 h-4" aria-hidden="true"><path d="M14 5h5v5M19 5l-8 8M19 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export default function LandingPage() {
  const { t } = useI18n();
  const [activeUseCaseId, setActiveUseCaseId] = useState<typeof useCaseKeys[number]>("support");
  const [modalOpen, setModalOpen] = useState(false);
  const activeUseCase = useCaseData[activeUseCaseId];

  return (
    <div className="min-h-screen bg-[#080a0f] text-zinc-100 overflow-hidden selection:bg-amber-300 selection:text-zinc-950">
      <div className="fixed inset-0 pointer-events-none opacity-40 [background-image:linear-gradient(rgba(255,255,255,.035)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.035)_1px,transparent_1px)] [background-size:48px_48px] [mask-image:linear-gradient(to_bottom,black,transparent_62%)]" />
      <div className="relative max-w-7xl mx-auto px-6 lg:px-10">
        <header className="h-20 flex items-center justify-between border-b border-white/10">
          <Link to="/" className="flex items-center gap-3" aria-label="Wolfpack AI home">
            <span className="w-9 h-9 rounded-xl bg-amber-400 text-zinc-950 flex items-center justify-center font-black">W</span>
            <span className="font-semibold tracking-tight">Wolfpack AI</span>
          </Link>
          <nav className="hidden md:flex items-center gap-7 text-sm text-zinc-400">
            <a href="#platform" className="hover:text-white transition-colors">{t.landing.navPlatform}</a>
            <a href="#run-anywhere" className="hover:text-white transition-colors">{t.landing.navDeploy}</a>
            <Link to="/docs" className="hover:text-white transition-colors">{t.landing.navDocs}</Link>
            <LangToggle />
          </nav>
          <a href={externalLinks.github} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm font-medium hover:border-amber-300 hover:text-amber-200 transition-colors">
            {t.landing.github} <ExternalArrow />
          </a>
        </header>

        <main>
          <section className="pt-20 pb-24 lg:pt-28 grid lg:grid-cols-[1.1fr_.9fr] gap-14 items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-amber-300/25 bg-amber-300/10 px-3 py-1 text-xs font-medium uppercase tracking-[.16em] text-amber-200">{t.landing.badge}</div>
              <h1 className="mt-7 max-w-4xl text-5xl md:text-7xl font-semibold tracking-[-.065em] leading-[.92] text-white">{t.landing.hero}<br /><span className="text-amber-300">{t.landing.heroHighlight}</span></h1>
              <p className="mt-7 max-w-xl text-lg md:text-xl leading-relaxed text-zinc-400">{t.landing.subtitle}</p>
              <div className="mt-9 flex flex-wrap gap-3">
                <a href={externalLinks.pypi} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg bg-amber-300 px-5 py-3 font-semibold text-zinc-950 hover:bg-amber-200 transition-colors">{t.landing.install} <Arrow /></a>
                <Link to="/docs" className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-5 py-3 font-semibold text-white hover:bg-white/5 transition-colors">{t.landing.readDocs} <Arrow /></Link>
              </div>
              <p className="mt-5 font-mono text-xs text-zinc-500">{t.landing.pip}</p>
            </div>

            <div className="relative rounded-2xl border border-white/10 bg-[#10131b]/90 shadow-2xl shadow-black/40 p-5 md:p-7">
              <div className="flex items-center justify-between border-b border-white/10 pb-4 text-xs uppercase tracking-[.18em] text-zinc-500"><span>{t.landing.wolfpackRuntime}</span><span className="text-emerald-300">{t.landing.connected}</span></div>
              <div className="mt-6 space-y-3">
                <div className="rounded-xl border border-amber-300/25 bg-amber-300/10 p-4"><div className="text-xs text-amber-200">01 / {t.landing.build}</div><div className="mt-1 font-medium text-white">{t.landing.buildLabel}</div><div className="mt-2 font-mono text-xs text-zinc-400">{t.landing.buildCode}</div></div>
                <div className="ml-8 h-5 border-l border-dashed border-white/20" />
                <div className="rounded-xl border border-white/10 bg-white/[.035] p-4"><div className="text-xs text-zinc-500">02 / {t.landing.run}</div><div className="mt-1 font-medium text-white">{t.landing.runLabel}</div><div className="mt-2 font-mono text-xs text-zinc-400">{t.landing.runCode}</div></div>
                <div className="ml-8 h-5 border-l border-dashed border-white/20" />
                <div className="rounded-xl border border-emerald-300/20 bg-emerald-300/[.06] p-4"><div className="text-xs text-emerald-300">03 / {t.landing.operate}</div><div className="mt-1 font-medium text-white">{t.landing.operateLabel}</div><div className="mt-2 font-mono text-xs text-zinc-400">{t.landing.operateCode}</div></div>
              </div>
            </div>
          </section>

          <section className="py-24 border-y border-white/10">
            <div className="max-w-3xl mx-auto text-center">
              <p className="text-sm font-medium text-amber-200">{t.landing.benchmarkBadge || "BENCHMARK"}</p>
              <h2 className="mt-4 text-4xl md:text-5xl font-semibold tracking-[-.05em] leading-tight text-white">{t.landing.benchmarkTitle || "Wolfpack AI Leads in Multi-Provider Latency"}</h2>
              <p className="mt-5 leading-relaxed text-zinc-400">{t.landing.benchmarkDesc || "Across all three providers (OpenAI, Anthropic, Gemini), Wolfpack AI delivers the fastest tool-agent latency among all frameworks tested."}</p>
              <div className="mt-7 flex justify-center gap-10">
                <div><span className="text-3xl font-bold text-white">3</span><p className="text-sm text-zinc-500">{t.landing.benchmarkProviders || "Cloud Providers"}</p></div>
                <div><span className="text-3xl font-bold text-white">4</span><p className="text-sm text-zinc-500">{t.landing.benchmarkFrameworks || "Competing Frameworks"}</p></div>
                <div><span className="text-3xl font-bold text-green-400">#1</span><p className="text-sm text-zinc-500">{t.landing.benchmarkRank || "Fastest Overall"}</p></div>
              </div>
            </div>
            <div className="mt-12 rounded-2xl border border-white/10 bg-[#0d1017] overflow-hidden cursor-pointer" onClick={() => setModalOpen(true)}>
              <img src="/images/benchmark-banner.png" alt="Wolfpack AI multi-provider latency benchmark" className="w-full h-auto" loading="lazy" />
            </div>
          </section>

          <section id="platform" className="border-y border-white/10 py-5 grid sm:grid-cols-3 gap-4 text-sm text-zinc-400">
            <div><span className="text-white font-medium">{t.landing.oneSdk}</span><span className="block mt-1">{t.landing.oneSdkDesc}</span></div>
            <div><span className="text-white font-medium">{t.landing.oneControlPlane}</span><span className="block mt-1">{t.landing.oneControlPlaneDesc}</span></div>
            <div><span className="text-white font-medium">{t.landing.yourInfra}</span><span className="block mt-1">{t.landing.yourInfraDesc}</span></div>
          </section>

          <section className="py-24 grid lg:grid-cols-[.8fr_1.2fr] gap-10 items-start">
            <div><p className="text-sm font-medium text-amber-200">{t.landing.devSurface}</p><h2 className="mt-4 text-4xl md:text-5xl font-semibold tracking-[-.05em] leading-tight text-white">{t.landing.devSurfaceTitle}</h2></div>
            <div className="rounded-2xl border border-white/10 bg-[#0d1017] overflow-hidden"><div className="flex gap-2 px-5 py-4 border-b border-white/10"><span className="w-2.5 h-2.5 rounded-full bg-rose-300/70" /><span className="w-2.5 h-2.5 rounded-full bg-amber-300/70" /><span className="w-2.5 h-2.5 rounded-full bg-emerald-300/70" /></div><pre className="overflow-x-auto p-6 text-sm leading-7 text-zinc-300"><code><span className="text-violet-300">from</span> wolfpack <span className="text-violet-300">import</span> Agent, get_model_from_env, tool{`\n\n`}<span className="text-amber-200">@tool</span>{`\n`}<span className="text-sky-300">def</span> get_weather(city: <span className="text-emerald-300">str</span>) -&gt; <span className="text-emerald-300">str</span>:{`\n`}    <span className="text-zinc-500">"""Return a weather summary."""</span>{`\n`}    <span className="text-violet-300">return</span> <span className="text-emerald-300">f"{`{city}`}: 22 C, cloudy."</span>{`\n\n`}agent = Agent({`\n`}    name=<span className="text-emerald-300">"weather-assistant"</span>,{`\n`}    model=get_model_from_env(),{`\n`}    tools=[get_weather],{`\n`})</code></pre></div>
          </section>

          <section className="pb-24" aria-labelledby="use-cases-heading">
            <div className="grid lg:grid-cols-[.78fr_1.22fr] gap-10 items-end">
              <div>
                <p className="text-sm font-medium text-amber-200">{t.landing.useCases}</p>
                <h2 id="use-cases-heading" className="mt-4 text-4xl md:text-5xl font-semibold tracking-[-.05em] leading-tight text-white">{t.landing.useCasesTitle}</h2>
              </div>
              <p className="max-w-xl text-zinc-400 leading-relaxed">{t.landing.useCasesDesc}</p>
            </div>

            <div className="mt-10 grid lg:grid-cols-[.9fr_1.1fr] gap-5">
              <div className="grid sm:grid-cols-2 lg:grid-cols-1 gap-2" role="tablist" aria-label="Wolfpack AI use cases">
                {useCaseKeys.map((key) => {
                  const isActive = key === activeUseCaseId;
                  const uc = t.useCases[key];
                  return (
                    <button
                      key={key}
                      type="button"
                      role="tab"
                      aria-selected={isActive}
                      aria-controls="use-case-detail"
                      onClick={() => setActiveUseCaseId(key)}
                      className={`text-left rounded-xl border p-4 transition-all ${isActive ? "border-amber-300/55 bg-amber-300/10" : "border-white/10 bg-white/[.02] hover:border-white/25 hover:bg-white/[.045]"}`}
                    >
                      <span className={`block text-[11px] uppercase tracking-[.16em] ${isActive ? "text-amber-200" : "text-zinc-500"}`}>{uc.label}</span>
                      <span className="mt-2 block font-medium text-white">{uc.title}</span>
                    </button>
                  );
                })}
              </div>

              <div id="use-case-detail" role="tabpanel" className="rounded-2xl border border-white/10 bg-[#10131b] p-6 md:p-8">
                <div className="flex items-start justify-between gap-4"><div><span className="text-xs uppercase tracking-[.16em] text-amber-200">{t.useCases[activeUseCaseId].label}</span><h3 className="mt-3 text-3xl md:text-4xl font-semibold tracking-[-.045em] text-white">{t.useCases[activeUseCaseId].title}</h3></div><span className="hidden sm:flex h-10 w-10 rounded-full border border-amber-300/25 bg-amber-300/10 items-center justify-center text-amber-200"><Arrow /></span></div>
                <p className="mt-5 max-w-2xl leading-relaxed text-zinc-400">{t.useCases[activeUseCaseId].description}</p>

                <div className="mt-8 grid md:grid-cols-2 gap-4">
                  <div className="rounded-xl border border-white/10 bg-black/20 p-4"><p className="text-xs font-medium uppercase tracking-[.14em] text-zinc-500">{t.landing.buildWith}</p><div className="mt-4 flex flex-wrap gap-2">{activeUseCase.framework.map((item) => <span key={item} className="rounded-full bg-white/[.06] px-2.5 py-1 text-xs text-zinc-300">{item}</span>)}</div></div>
                  <div className="rounded-xl border border-white/10 bg-black/20 p-4"><p className="text-xs font-medium uppercase tracking-[.14em] text-zinc-500">{t.landing.operateWith}</p><div className="mt-4 flex flex-wrap gap-2">{activeUseCase.operate.map((item) => <span key={item} className="rounded-full bg-white/[.06] px-2.5 py-1 text-xs text-zinc-300">{item}</span>)}</div></div>
                </div>

                <div className="mt-5 rounded-xl border border-emerald-300/15 bg-emerald-300/[.045] p-4"><p className="text-xs font-medium uppercase tracking-[.14em] text-emerald-300">{t.landing.operationalFlow}</p><div className="mt-4 flex flex-wrap items-center gap-2 text-sm">{activeUseCase.flow.map((step, index) => <span key={step} className="contents"><span className="rounded-md border border-emerald-300/15 bg-emerald-300/[.06] px-3 py-2 text-zinc-200">{step}</span>{index < activeUseCase.flow.length - 1 && <Arrow />}</span>)}</div></div>

                <div className="mt-6 flex flex-wrap gap-4 text-sm"><Link to="/docs" className="inline-flex items-center gap-2 font-medium text-amber-200 hover:text-amber-100">{t.landing.exploreDocs} <Arrow /></Link><Link to="/examples" className="inline-flex items-center gap-2 font-medium text-zinc-300 hover:text-white">{t.landing.viewExamples} <Arrow /></Link></div>
              </div>
            </div>
          </section>

          <section id="run-anywhere" className="pb-24">
            <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-5"><div><p className="text-sm font-medium text-amber-200">{t.landing.fromLocal}</p><h2 className="mt-3 text-4xl md:text-5xl font-semibold tracking-[-.05em] text-white">{t.landing.chooseEntry}</h2></div><Link to="/installation" className="inline-flex items-center gap-2 text-sm font-medium text-amber-200 hover:text-amber-100">{t.landing.deployGuide} <Arrow /></Link></div>
            <div className="mt-10 grid md:grid-cols-3 gap-4">
              <a href={externalLinks.pypi} target="_blank" rel="noreferrer" className="group rounded-2xl border border-white/10 bg-white/[.025] p-6 hover:border-amber-300/50 transition-colors"><div className="text-xs text-zinc-500">PYPI</div><h3 className="mt-9 text-2xl font-medium text-white">{t.landing.installSdk}</h3><p className="mt-3 text-sm leading-relaxed text-zinc-400">{t.landing.installSdkDesc}</p><span className="mt-7 inline-flex items-center gap-2 text-sm text-amber-200">wolfpackai <ExternalArrow /></span></a>
              <a href={externalLinks.docker} target="_blank" rel="noreferrer" className="group rounded-2xl border border-white/10 bg-white/[.025] p-6 hover:border-amber-300/50 transition-colors"><div className="text-xs text-zinc-500">DOCKER HUB</div><h3 className="mt-9 text-2xl font-medium text-white">{t.landing.runPlatform}</h3><p className="mt-3 text-sm leading-relaxed text-zinc-400">{t.landing.runPlatformDesc}</p><span className="mt-7 inline-flex items-center gap-2 text-sm text-amber-200">wolfpackaiagents <ExternalArrow /></span></a>
              <a href={externalLinks.github} target="_blank" rel="noreferrer" className="group rounded-2xl border border-white/10 bg-white/[.025] p-6 hover:border-amber-300/50 transition-colors"><div className="text-xs text-zinc-500">GITHUB</div><h3 className="mt-9 text-2xl font-medium text-white">{t.landing.inspectSource}</h3><p className="mt-3 text-sm leading-relaxed text-zinc-400">{t.landing.inspectSourceDesc}</p><span className="mt-7 inline-flex items-center gap-2 text-sm text-amber-200">{t.landing.openRepository} <ExternalArrow /></span></a>
            </div>
          </section>
        </main>

        <footer className="border-t border-white/10 py-7 flex flex-col sm:flex-row justify-between gap-4 text-sm text-zinc-500"><span>{t.landing.footer}</span><div className="flex gap-5"><Link to="/docs" className="hover:text-white">{t.landing.navDocs}</Link><a href={externalLinks.github} target="_blank" rel="noreferrer" className="hover:text-white">{t.landing.github}</a><a href={externalLinks.pypi} target="_blank" rel="noreferrer" className="hover:text-white">PyPI</a></div></footer>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setModalOpen(false)}>
          <div className="relative max-w-6xl w-full" onClick={(e) => e.stopPropagation()}>
            <button onClick={() => setModalOpen(false)} className="absolute top-4 right-4 w-10 h-10 rounded-full bg-black/60 text-white flex items-center justify-center text-xl hover:bg-black/80 z-10">&times;</button>
            <img src="/images/benchmark-banner.png" alt="Benchmark chart" className="w-full h-auto rounded-2xl shadow-2xl" />
          </div>
        </div>
      )}
    </div>
  );
}