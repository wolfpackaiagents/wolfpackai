import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import en from "./en";
import ptBR from "./ptBR";
import type { Translations } from "./en";

type Lang = "en" | "pt-BR";

interface I18nContextType {
  lang: Lang;
  t: Translations;
  setLang: (lang: Lang) => void;
}

const I18nContext = createContext<I18nContextType | null>(null);

const translations: Record<Lang, Translations> = { en, "pt-BR": ptBR };

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const stored = localStorage.getItem("wolfpack-lang") as Lang | null;
    if (stored === "en" || stored === "pt-BR") return stored;
    return navigator.language.startsWith("pt") ? "pt-BR" : "en";
  });

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    localStorage.setItem("wolfpack-lang", next);
  }, []);

  return (
    <I18nContext.Provider value={{ lang, t: translations[lang], setLang }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

export function LangToggle() {
  const { lang, setLang } = useI18n();
  return (
    <button
      onClick={() => setLang(lang === "en" ? "pt-BR" : "en")}
      className="text-[11px] font-medium uppercase tracking-[.12em] text-zinc-500 hover:text-zinc-300 transition-colors"
      aria-label={lang === "en" ? "Switch to Portuguese" : "Mudar para Inglês"}
    >
      {lang === "en" ? "PT" : "EN"}
    </button>
  );
}