import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '../stores/auth'
import LanguageSwitcher from '../components/LanguageSwitcher'
import networkImage from '../assets/amp-login-network.webp'

export default function Login() {
  const [key, setKey] = useState('')
  const setStored = useAuthStore((s) => s.setApiKey)
  const navigate = useNavigate()
  const { t } = useTranslation()

  function submit(e: FormEvent) {
    e.preventDefault()
    setStored(key.trim())
    navigate('/')
  }

  return (
    <main className="amp-login">
      <section className="amp-login-hero" aria-hidden="true">
        <img className="amp-login-art" src={networkImage} alt="" />
        <div className="amp-login-brand"><span className="amp-login-mark">W</span> {t('layout.productName')}</div>
        <div className="amp-login-copy">
          <h1>{t('login.heroTitle')}</h1>
          <p>{t('login.heroSubtitle')}</p>
        </div>
      </section>
      <section className="amp-login-panel">
        <div className="amp-login-language"><LanguageSwitcher /></div>
        <form onSubmit={submit} className="amp-login-form">
          <h2>{t('login.title')}</h2>
          <p>{t('login.subtitle')}</p>
          <label htmlFor="api-key">{t('login.apiKeyLabel')}</label>
          <input id="api-key" type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={t('login.placeholder')} autoComplete="current-password" />
          <button type="submit" className="amp-login-submit">{t('login.submit')}</button>
          <p className="text-center text-xs">{t('login.hint')}</p>
        </form>
      </section>
    </main>
  )
}
