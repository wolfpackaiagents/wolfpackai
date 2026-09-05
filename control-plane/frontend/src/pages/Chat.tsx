import { FormEvent, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import ConfirmationDialog from '../components/ConfirmationDialog'
import ContextCombobox from '../components/ContextCombobox'
import {
  createChatConversation,
  deleteChatConversation,
  fetchChatConversation,
  fetchChatConversations,
  fetchMeshCatalog,
  renameChatConversation,
  startChatRun,
  streamChatRun,
} from '../lib/api'
import type { ChatConversation, ChatMessage, MeshRegistration } from '../lib/types'
import { useScopeStore } from '../stores/context'

export default function Chat() {
  const { t } = useTranslation()
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const registrationId = useScopeStore((state) => state.registrationId)
  const setRegistration = useScopeStore((state) => state.setRegistration)
  const [conversations, setConversations] = useState<ChatConversation[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [registrations, setRegistrations] = useState<MeshRegistration[]>([])
  const [value, setValue] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [traceId, setTraceId] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [warning, setWarning] = useState<string | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [title, setTitle] = useState('')
  const [deleting, setDeleting] = useState<ChatConversation | null>(null)
  const requestId = useRef(0)

  const activeConversation = conversations.find((conversation) => conversation.id === conversationId)

  useEffect(() => {
    let active = true
    Promise.all([fetchChatConversations(), fetchMeshCatalog()])
      .then(([items, catalog]) => {
        if (!active) return
        setConversations(items)
        setRegistrations(catalog.environments.flatMap((environment) => environment.registrations))
      })
      .catch((reason) => active && setError(reason instanceof Error ? reason.message : t('chat.loadFailed')))
    return () => { active = false }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!conversationId) {
      setMessages([])
      setTraceId(null)
      return
    }
    const id = ++requestId.current
    setMessages([])
    setTraceId(null)
    setError(null)
    fetchChatConversation(conversationId)
      .then((conversation) => {
        if (id !== requestId.current) return
        setMessages(conversation.messages ?? [])
        setTraceId([...conversation.messages ?? []].reverse().find((message) => message.trace_id)?.trace_id ?? null)
        setConversations((items) => items.map((item) => item.id === conversation.id ? { ...item, ...conversation } : item))
      })
      .catch((reason) => id === requestId.current && setError(reason instanceof Error ? reason.message : t('chat.loadFailed')))
  }, [conversationId])

  async function newConversation() {
    if (!registrationId || streaming) return
    setError(null)
    try {
      const conversation = await createChatConversation(registrationId)
      setConversations((items) => [conversation, ...items])
      navigate(`/chat/${conversation.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('chat.createFailed'))
    }
  }

  async function saveTitle(event: FormEvent) {
    event.preventDefault()
    if (!activeConversation || !title.trim()) return
    try {
      const updated = await renameChatConversation(activeConversation.id, title.trim())
      setConversations((items) => items.map((item) => item.id === updated.id ? updated : item))
      setRenaming(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('chat.renameFailed'))
    }
  }

  function beginRename(conversation: ChatConversation) {
    if (conversation.id !== conversationId) navigate(`/chat/${conversation.id}`)
    setTitle(conversation.title)
    setRenaming(true)
  }

  async function confirmDelete() {
    if (!deleting) return
    try {
      await deleteChatConversation(deleting.id)
      setConversations((items) => items.filter((item) => item.id !== deleting.id))
      if (conversationId === deleting.id) navigate('/chat')
      setDeleting(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('chat.deleteFailed'))
      setDeleting(null)
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault()
    if (!value.trim() || !registrationId || !conversationId || streaming) return
    const message = value.trim()
    const localMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: message, created_at: new Date().toISOString() }
    setMessages((current) => [...current, localMessage])
    setValue('')
    setStreaming(true)
    setError(null)
    setWarning(null)
    setRunStatus(t('chat.startingRun'))
    try {
      const run = await startChatRun({ conversation_id: conversationId, message })
      setWarning(run.warning ? t('chat.runtimeNotOnline', { status: t(`mesh.health.${run.health_status}`) }) : null)
      const assistantMessage: ChatMessage = { id: run.run_id, role: 'assistant', content: '', created_at: new Date().toISOString(), run_id: run.run_id }
      setMessages((current) => [...current, assistantMessage])
      await streamChatRun(run.run_id, (runEvent) => {
        if (runEvent.type === 'run.status') setRunStatus(runEvent.status ?? t('chat.runningAgent'))
        if (runEvent.type === 'run.started') setRunStatus(t('chat.running'))
        if (runEvent.type === 'run.completed') setRunStatus(t('chat.completed'))
        if (runEvent.type === 'message.delta') {
          setMessages((current) => current.map((item) => item.id === run.run_id ? { ...item, content: `${item.content}${runEvent.content ?? ''}` } : item))
        }
        if (runEvent.type === 'message.completed') {
          setMessages((current) => current.map((item) => item.id === run.run_id ? { ...item, content: runEvent.content ?? item.content, trace_id: runEvent.trace_id ?? null } : item))
          setTraceId(runEvent.trace_id ?? null)
          setRunStatus(t('chat.completed'))
        }
        if (runEvent.type === 'run.failed') {
          setMessages((current) => current.filter((item) => item.id !== run.run_id))
          setError(runEvent.error ?? t('chat.executionFailed'))
          setRunStatus(t('chat.failed'))
        }
      })
      const refreshed = await fetchChatConversation(conversationId)
      setMessages(refreshed.messages ?? [])
      setConversations((items) => items.map((item) => item.id === refreshed.id ? { ...item, ...refreshed } : item))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('chat.executionFailed'))
      setRunStatus(t('chat.failed'))
    } finally {
      setStreaming(false)
    }
  }

  return <section className="chat-console">
    <header>
      <div><p>{t('chat.eyebrow')}</p><h1>{t('chat.title')}</h1><span>{t('chat.subtitle')}</span></div>
      <div className="chat-status"><i /> {registrationId ? t('chat.registeredRuntime').toUpperCase() : t('chat.selectRuntime').toUpperCase()}</div>
    </header>
    <div className="chat-target"><span>{t('chat.targetRegistration')}</span><ContextCombobox label={t('chat.targetRegistration')} value={registrationId} options={registrations.map((registration) => { const supported = !!registration.chat_endpoint; return { value: registration.id, label: `${registration.definition_name} v${registration.definition_version}`, disabled: !supported, healthStatus: registration.health_status, healthLabel: t(`mesh.health.${registration.health_status}`), detail: `${registration.definition_kind === 'team' ? t('mesh.team') : t('mesh.agent')} · ${supported ? registration.environment_slug : t('chat.targetUnsupported')}` } })} emptyLabel={t('layout.noMatchingOptions')} searchable onChange={setRegistration} /><small>{registrationId ? (registrations.find((r) => r.id === registrationId)?.chat_endpoint ? t('chat.targetSelected') : t('chat.targetUnsupported')) : t('chat.targetRequired')}</small></div>
    <div className="chat-layout">
      <aside className="chat-threads">
        <strong>{t('chat.threads').toUpperCase()}</strong>
        <button className="new-thread" disabled={!registrationId || streaming} onClick={newConversation}>+ {t('chat.newConversation')}</button>
        <nav aria-label={t('chat.threads')}>
          {conversations.map((conversation) => <div className={`thread-row${conversation.id === conversationId ? ' is-active' : ''}`} key={conversation.id}>
            <button className="thread-select" onClick={() => navigate(`/chat/${conversation.id}`)}><strong>{conversation.title}</strong><small>{conversation.id === conversationId ? t('chat.currentContext') : new Date(conversation.updated_at).toLocaleDateString()}</small></button>
            <div className="thread-actions"><button aria-label={t('chat.rename')} onClick={() => beginRename(conversation)}>✎</button><button aria-label={t('chat.deleteConversation', { name: conversation.title })} className="thread-delete" onClick={() => setDeleting(conversation)}>×</button></div>
          </div>)}
        </nav>
      </aside>
      <main>
        <div className="chat-conversation-header">
          {activeConversation && !renaming && <div className="chat-title-row"><div><span>{t('chat.currentContext')}</span><h2>{activeConversation.title}</h2></div><button className="chat-rename-action" onClick={() => { setTitle(activeConversation.title); setRenaming(true) }}>✎ {t('chat.rename')}</button></div>}
          {activeConversation && renaming && <form className="chat-rename-form" onSubmit={saveTitle}><label>{t('chat.conversationTitle')}<input aria-label={t('chat.conversationTitle')} autoFocus value={title} onChange={(event) => setTitle(event.target.value)} /></label><button>{t('chat.save')}</button><button type="button" onClick={() => setRenaming(false)}>{t('chat.cancel')}</button></form>}
        </div>
        <div className="chat-messages" aria-live="polite">
          {messages.length ? messages.map((message) => <article key={message.id} className={message.role}><b>{message.role === 'user' ? t('chat.you').toUpperCase() : t('chat.assistant').toUpperCase()}</b><p>{message.content || (streaming ? t('chat.runningAgent') : '')}</p></article>) : <div className="chat-empty"><span>W</span><h2>{!registrationId ? t('chat.chooseAgent') : conversationId ? t('chat.startConversation') : t('chat.selectConversation')}</h2><p>{!registrationId ? t('chat.targetRequired') : conversationId ? t('chat.startHint') : t('chat.selectConversationHint')}</p></div>}
          {error && <div className="mesh-feedback is-error" role="alert">{error}</div>}
          {warning && <div className="mesh-feedback">{warning}</div>}
        </div>
        <form className="chat-composer" onSubmit={send}><textarea value={value} onChange={(event) => setValue(event.target.value)} disabled={!registrationId || !conversationId || streaming} placeholder={!registrationId ? t('chat.selectAgent') : !conversationId ? t('chat.createConversationFirst') : t('chat.messageAgent')} /><button disabled={!registrationId || !conversationId || !value.trim() || streaming}>{streaming ? t('chat.running') : t('chat.send')} <b>↗</b></button></form>
      </main>
      <aside className="run-inspector"><strong>{t('chat.inspector').toUpperCase()}</strong><p>{t('chat.inspectorHint')}</p><div><span>{t('chat.scope')}</span><b>{registrationId ? t('chat.verifiedRegistration') : t('chat.notSelected')}</b></div><div><span>{t('chat.status')}</span><b>{runStatus ?? t('chat.pending')}</b></div><div><span>{t('chat.trace')}</span>{traceId ? <a href={`/traces/${traceId}`}>{traceId.slice(0, 12)}...</a> : <b>{t('chat.pending')}</b>}</div></aside>
    </div>
    {deleting && <ConfirmationDialog title={t('chat.deleteTitle')} description={t('chat.deleteDescription', { name: deleting.title })} cancelLabel={t('chat.cancel')} confirmLabel={t('chat.delete')} onCancel={() => setDeleting(null)} onConfirm={confirmDelete} />}
  </section>
}
