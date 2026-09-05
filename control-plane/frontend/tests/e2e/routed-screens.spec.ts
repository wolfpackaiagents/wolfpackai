import { expect, test } from '@playwright/test'

const apiKeys: Record<string, string> = {
  'all routed screens render against the seeded control plane': 'pk-wp-e2e-1:e2e-secret',
  'seeded operational metrics and content are visible': 'pk-wp-e2e-2:e2e-secret',
  'Portuguese locale applies to all localized policy and operations screens': 'pk-wp-e2e-3:e2e-secret',
  'custom comboboxes expose listbox options and update controlled values': 'pk-wp-e2e-4:e2e-secret',
  'privacy custom patterns validate inline and governance roles use structured controls': 'pk-wp-e2e-5:e2e-secret',
  'destructive confirmations are accessible and dismiss without side effects': 'pk-wp-e2e-6:e2e-secret',
  'schedules expose lifecycle actions and trace-linked history': 'pk-wp-e2e-7:e2e-secret',
  'schedule execution instructions are validated and preserved in the ledger': 'pk-wp-e2e-6:e2e-secret',
  'channels bind database vault secrets and preserve connection controls': 'pk-wp-e2e-8:e2e-secret',
  'channel guide modal opens from credential field and shows provider instructions': 'pk-wp-e2e-8:e2e-secret',
}

test.beforeEach(async ({ page, context }, testInfo) => {
  const apiKey = apiKeys[testInfo.title]
  if (!apiKey) throw new Error(`No e2e API key configured for ${testInfo.title}`)
  await context.clearCookies()
  await page.addInitScript((key) => {
    localStorage.clear()
    localStorage.setItem('wolfpack_api_key', key)
  }, apiKey)
})

test('all routed screens render against the seeded control plane', async ({ page }) => {
  const routes = [
    ['/', 'Operational command center'],
    ['/traces', 'Execution ledger'],
    ['/sessions', 'Conversation sessions'],
    ['/approvals', 'Approvals'],
    ['/guardrails', 'Guardrails'],
    ['/scores', 'Quality intelligence'],
    ['/privacy', 'Privacy is an'],
    ['/resilience', 'Resilience'],
    ['/mesh', 'Operate every agent'],
    ['/chat', 'Runtime conversation'],
    ['/schedules', 'Schedules'],
    ['/channels', 'Channel connections'],
    ['/settings', 'Configure the'],
  ] as const

  for (const [route, heading] of routes) {
    await page.goto(route)
    await expect(page.getByRole('heading', { name: heading, level: 1 })).toBeVisible()
  }
})

test('seeded operational metrics and content are visible', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Throughput', { exact: true })).toBeVisible()
  await expect(page.getByText('total observed runs', { exact: true })).toBeVisible()
  await expect(page.getByText('Provider-reported cost', { exact: true })).toBeVisible()
  await expect(page.getByText(/cost coverage:/).or(page.getByText('coverage unknown'))).toBeVisible()
  await expect(page.getByText('Guardrail alerts', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Active schedules', { exact: true }).first()).toBeVisible()

  await page.goto('/traces')
  await expect(page.getByText('demo_weather_trace_lisbon', { exact: true })).toBeVisible()

  await page.goto('/traces/demo_weather_trace_lisbon')
  await expect(page.getByRole('heading', { name: 'weather-response' })).toBeVisible()

  await page.goto('/sessions')
  await expect(page.getByText('weather-ops-session-2026-08-23', { exact: true })).toBeVisible()

  await page.goto('/sessions/weather-ops-session-2026-08-23')
  await expect(page.getByRole('heading', { name: 'Conversation timeline' })).toBeVisible()
  await expect(page.getByText(/What is the weather in Lisbon/)).toBeVisible()

  await page.goto('/approvals')
  await expect(page.getByText('send_storm_notification', { exact: true })).toBeVisible()

  await page.goto('/guardrails')
  await expect(page.getByText('External weather notification was blocked by the execution policy.', { exact: true })).toBeVisible()

  await page.goto('/scores')
  await expect(page.getByText('weather_response_accuracy', { exact: true }).first()).toBeVisible()

  await page.goto('/resilience')
  await expect(page.getByText('Weather guardrail violations', { exact: true })).toBeVisible()

  await page.goto('/mesh')
  await expect(page.getByText('Weather Operations', { exact: true }).first()).toBeVisible()
})

test('Portuguese locale applies to all localized policy and operations screens', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('wolfpack_lang', 'pt-BR'))

  await page.goto('/scores')
  await expect(page.getByRole('heading', { name: 'Inteligência de qualidade' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Período' })).toBeVisible()
  await expect(page.locator('select')).toHaveCount(0)

  await page.goto('/approvals')
  await expect(page.getByRole('heading', { name: 'Aprovações' })).toBeVisible()
  await expect(page.getByText('Solicitações de decisão', { exact: true })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Status da fila' })).toBeVisible()

  const privacyReady = page.waitForResponse((response) =>
    response.url().includes('/api/public/privacy/config') && response.request().method() === 'GET' && response.ok(),
  )
  await page.goto('/privacy')
  await privacyReady
  await expect(page.getByRole('heading', { name: 'Privacidade é um' })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'Ativar redação' })).toBeVisible()
  await expect(page.getByText('Histórico de solicitações do titular', { exact: true })).toBeVisible()

  await page.goto('/resilience')
  await expect(page.getByRole('heading', { name: 'Resiliência' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Reconhecer' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Resolver' }).first()).toBeVisible()
  await expect(page.getByText('Regras de alerta', { exact: true })).toBeVisible()

  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'Configure o' })).toBeVisible()
  await expect(page.getByText('Credencial do plano de controle', { exact: true })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'Permissão de Escrever para Editor' })).toBeVisible()
})

test('custom comboboxes expose listbox options and update controlled values', async ({ page }) => {
  await page.goto('/')
  const range = page.getByRole('combobox', { name: 'Time range' })
  await range.click()
  await expect(page.getByRole('listbox', { name: 'Time range' })).toBeVisible()
  await page.getByRole('option', { name: 'Last 7 days' }).click()
  await expect(range).toHaveValue('Last 7 days')
  await expect(page.getByRole('listbox', { name: 'Time range' })).toHaveCount(0)
})

test('privacy custom patterns validate inline and governance roles use structured controls', async ({ page }) => {
  const settingsReady = page.waitForResponse((response) =>
    response.url().includes('/api/public/privacy/config') && response.request().method() === 'GET' && response.ok(),
  )
  await page.goto('/privacy')
  await settingsReady
  const redaction = page.getByRole('checkbox', { name: 'Enable redaction' })
  await expect(redaction).toBeEnabled()
  await redaction.check()
  await expect(redaction).toBeChecked()
  await page.getByRole('button', { name: 'Add pattern' }).click()
  const pattern = page.getByRole('textbox', { name: 'Pattern' })
  await expect(pattern).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByText('Enter a regular expression.')).toBeVisible()
  await pattern.fill('[')
  await expect(page.getByText('This is not a valid regular expression.')).toBeVisible()
  await pattern.fill('ACCT-[0-9]{8}')
  await expect(pattern).toHaveAttribute('aria-invalid', 'false')
  await page.getByRole('button', { name: 'Remove pattern 1' }).click()

  await page.goto('/settings')
  const editorWrite = page.getByRole('checkbox', { name: 'Write permission for Editor' })
  await expect(editorWrite).toBeChecked()
  await editorWrite.uncheck()
  await expect(editorWrite).not.toBeChecked()
})

test('destructive confirmations are accessible and dismiss without side effects', async ({ page }) => {
  const settingsReady = page.waitForResponse((response) =>
    response.url().includes('/api/public/privacy/config') && response.request().method() === 'GET' && response.ok(),
  )
  await page.goto('/privacy')
  await settingsReady

  await page.getByRole('textbox', { name: 'User ID' }).fill('subject-to-delete')
  const deleteButton = page.getByRole('button', { name: 'Delete data' })
  await deleteButton.click()

  const dialog = page.getByRole('alertdialog', { name: 'Confirm destructive action' })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('Permanently delete all data for subject-to-delete? This cannot be undone.')
  await expect(dialog).toHaveAttribute('aria-modal', 'true')
  await expect(page.getByRole('button', { name: 'Cancel' })).toBeFocused()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(deleteButton).toBeFocused()

  await deleteButton.click()
  await page.locator('.confirmation-backdrop').click({ position: { x: 2, y: 2 } })
  await expect(dialog).toBeHidden()
})

test('schedules expose lifecycle actions and trace-linked history', async ({ page }) => {
  await page.goto('/schedules')
  await expect(page.getByRole('heading', { name: 'Schedules' }).first()).toBeVisible()
  await expect(page.getByText('Weather briefing', { exact: true }).first()).toBeVisible()
  await page.locator('.schedule-row').filter({ hasText: 'Weather briefing' }).click()
  await expect(page.getByRole('heading', { name: 'Run history' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'weather-operations' })).toHaveAttribute('href', '/traces/demo_weather_trace_lisbon')
  await page.locator('.schedule-row').filter({ hasText: 'Weather briefing' }).getByRole('button', { name: 'Pause' }).click()
  await expect(page.locator('.schedule-row').filter({ hasText: 'Weather briefing' }).getByRole('button', { name: 'Resume' })).toBeVisible()
})

test('schedule execution instructions are validated and preserved in the ledger', async ({ page }) => {
  await page.goto('/schedules')
  await page.locator('article', { hasText: 'Weather briefing' }).getByRole('button', { name: 'Edit' }).click()
  const dialog = page.getByRole('form', { name: 'Edit' })
  const instruction = dialog.getByRole('textbox', { name: 'Execution instruction' })
  await instruction.fill(' ')
  await dialog.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(dialog.getByText('Enter an execution instruction.')).toBeVisible()
  await instruction.fill('Prepare a concise weather briefing for operations.')
  await dialog.getByRole('textbox', { name: 'Structured parameters' }).fill('[]')
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(dialog.getByText('Structured parameters must be a valid JSON object.')).toBeVisible()
  await dialog.getByRole('textbox', { name: 'Structured parameters' }).fill('{"region":"Lisbon"}')
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(page.locator('.schedule-instruction').getByText('Prepare a concise weather briefing for operations.', { exact: true })).toBeVisible()
})

test('channels bind database vault secrets and preserve connection controls', async ({ page }) => {
  await page.goto('/channels')
  await expect(page.getByRole('heading', { name: 'Channel connections' })).toBeVisible()
  await expect(page.getByText('Weather operations bot', { exact: true })).toBeVisible()
  await expect(page.getByText('Delivered', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Configure' }).click()
  const dialog = page.getByRole('form', { name: 'Configure' })
  await expect(dialog.getByText('Channel credentials are encrypted in this project database vault.')).toBeVisible()
  await expect(dialog.getByRole('combobox', { name: 'Bot token vault secret' })).toBeVisible()
  await expect(dialog.getByRole('textbox', { name: 'Bot token reference' })).toHaveCount(0)
  const botToken = dialog.getByRole('group', { name: 'Bot token' })
  const webhookSecret = dialog.getByRole('group', { name: 'Webhook secret' })
  await botToken.getByRole('button', { name: 'Create vault secret' }).click()
  await dialog.getByRole('textbox', { name: 'Bot token secret name' }).fill('weather-bot-token')
  await dialog.getByLabel('Bot token secret value').fill('initial-bot-token')
  await botToken.getByRole('button', { name: 'Save vault secret' }).click()
  await webhookSecret.getByRole('button', { name: 'Create vault secret' }).click()
  await dialog.getByRole('textbox', { name: 'Webhook secret secret name' }).fill('weather-webhook-secret')
  await dialog.getByLabel('Webhook secret secret value').fill('initial-webhook-secret')
  await webhookSecret.getByRole('button', { name: 'Save vault secret' }).click()
  await expect(dialog.getByText('Selected registration: Development / Weather Operations v1.0.0')).toBeVisible()
  await expect(dialog.getByRole('group', { name: 'Bot token' }).getByRole('button', { name: 'Provider setup guide' })).toBeVisible()
  const saveConnection = page.waitForResponse((response) => response.url().includes('/api/public/channels/connections/') && response.request().method() === 'PATCH' && response.ok())
  await dialog.getByRole('button', { name: 'Save', exact: true }).click()
  const connectionUpdate = await saveConnection
  const savedRefs = connectionUpdate.request().postDataJSON().secret_refs as Record<string, string>
  expect(savedRefs.bot_token).toMatch(/^[a-f0-9]{32}$/)
  expect(savedRefs.webhook_secret).toMatch(/^[a-f0-9]{32}$/)
  await expect(page.getByText('initial-bot-token', { exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: 'Configure' }).click()
  const rotationDialog = page.getByRole('form', { name: 'Configure' })
  await rotationDialog.getByRole('group', { name: 'Bot token' }).getByRole('button', { name: 'Rotate vault secret' }).click()
  await rotationDialog.getByLabel('Bot token replacement value').fill('rotated-bot-token')
  await rotationDialog.getByRole('group', { name: 'Bot token' }).getByRole('button', { name: 'Save rotation' }).click()
  await expect(rotationDialog.getByText('rotated-bot-token', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Cancel' }).click()

  await page.getByRole('button', { name: 'Disable' }).click()
  await expect(page.getByRole('button', { name: 'Enable' })).toBeVisible()
  await page.getByRole('button', { name: 'Enable' }).click()

  await page.getByRole('button', { name: 'Delete' }).click()
  const deleteDialog = page.getByRole('alertdialog', { name: 'Delete channel connection' })
  await expect(deleteDialog).toContainText('Existing delivery receipts are retained for audit history.')
  await page.getByRole('button', { name: 'Cancel' }).click()
})

test('channel guide modal opens from credential field and shows provider instructions', async ({ page }) => {
  await page.goto('/channels')
  await expect(page.getByRole('heading', { name: 'Channel connections' })).toBeVisible()
  await page.getByRole('button', { name: 'Configure' }).click()
  const dialog = page.getByRole('form', { name: 'Configure' })
  const guideButton = dialog.getByRole('group', { name: 'Bot token' }).getByRole('button', { name: 'Provider setup guide' })
  await expect(guideButton).toBeVisible()
  await guideButton.click()
  const guideDialog = page.getByRole('dialog', { name: 'Provider setup guide' })
  await expect(guideDialog).toBeVisible()
  await expect(guideDialog.getByText('/api/public/channels/telegram/webhook')).toBeVisible()
  await expect(guideDialog.getByText(/BotFather/)).toBeVisible()
  await guideDialog.getByRole('button', { name: 'Back' }).click()
  await expect(guideDialog).toBeHidden()
})
