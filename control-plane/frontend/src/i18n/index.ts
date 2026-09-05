import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import ptBR from './ptBR.json'

export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'pt-BR', label: 'Português' },
] as const

export type LanguageCode = (typeof LANGUAGES)[number]['code']

const STORAGE_KEY = 'wolfpack_lang'

function detectLanguage(): LanguageCode {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'en' || stored === 'pt-BR') return stored
  const nav = (navigator.language || 'en').toLowerCase()
  return nav.startsWith('pt') ? 'pt-BR' : 'en'
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    'pt-BR': { translation: ptBR },
  },
  lng: detectLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export function setLanguage(code: LanguageCode): void {
  localStorage.setItem(STORAGE_KEY, code)
  void i18n.changeLanguage(code)
}

export default i18n