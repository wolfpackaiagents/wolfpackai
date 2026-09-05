import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '../stores/auth'
import LanguageSwitcher from '../components/LanguageSwitcher'

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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="absolute top-4 right-4">
          <LanguageSwitcher />
        </div>
        <div className="mb-8 text-center">
          <div className="inline-block w-3 h-3 rounded-full bg-orange-500 mb-3" />
          <h1 className="text-2xl font-semibold">
            Wolfpack <span className="text-orange-400">AMP</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">{t('login.subtitle')}</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1">
              {t('login.apiKeyLabel')}
            </label>
            <input
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder={t('login.placeholder')}
              className="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-sm outline-none focus:border-orange-500"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-lg bg-orange-600 hover:bg-orange-500 py-2 text-sm font-medium"
          >
            {t('login.submit')}
          </button>
          <p className="text-xs text-slate-600 text-center">{t('login.hint')}</p>
        </form>
      </div>
    </div>
  )
}