import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from "react";
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
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const languages: { value: Lang; flag: string; label: string }[] = [
    { value: "en", flag: "🇺🇸", label: "English" },
    { value: "pt-BR", flag: "🇧🇷", label: "Português" },
  ];
  const selected = languages.find((language) => language.value === lang)!;

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-2.5 py-1.5 text-xs font-medium text-gray-200 transition-colors hover:border-amber-400/60 hover:text-white"
        aria-label="Select language"
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span aria-hidden="true">{selected.flag}</span>
        <span>{selected.label}</span>
        <svg className="h-3 w-3 text-gray-400" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="m3 4.5 3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-36 overflow-hidden rounded-lg border border-gray-700 bg-gray-900 p-1 shadow-xl" role="listbox" aria-label="Language">
          {languages.map((language) => (
            <button
              key={language.value}
              type="button"
              role="option"
              aria-selected={language.value === lang}
              onClick={() => { setLang(language.value); setOpen(false); }}
              className={`flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs transition-colors ${language.value === lang ? "bg-amber-500/15 text-amber-300" : "text-gray-300 hover:bg-gray-800 hover:text-white"}`}
            >
              <span aria-hidden="true">{language.flag}</span>
              <span>{language.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
