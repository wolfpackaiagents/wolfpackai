import { useTranslation } from 'react-i18next'
import { LANGUAGES, setLanguage, type LanguageCode } from '../i18n'
import ContextCombobox from './ContextCombobox'

export default function LanguageSwitcher() {
  const { i18n } = useTranslation()

  return (
    <ContextCombobox
      value={i18n.language}
      onChange={(value) => setLanguage(value as LanguageCode)}
      options={LANGUAGES.map((language) => ({ value: language.code, label: language.label }))}
      label={i18n.t('nav.lang')}
      className="language-switcher"
    />
  )
}
