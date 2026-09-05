import { expect, test, type Page } from '@playwright/test'

test('team chat sends and receives response via SSE', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear()
    localStorage.setItem('wolfpack_api_key', 'pk-wp-dev:dev-secret')
  })

  // Collect console errors
  const errors: string[] = []
  page.on('pageerror', (err) => errors.push(err.message))
  page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()) })

  // Helper: wait for an API response with a predicate
  async function waitForApi(pathPart: string, method = 'POST') {
    return page.waitForResponse((resp) => resp.url().includes(pathPart) && resp.request().method() === method)
  }

  // 1. Navigate to chat
  await page.goto('/chat')
  await expect(page.getByRole('heading', { name: 'Runtime conversation' })).toBeVisible()

  // 2. Open the target combobox and select the team
  const target = page.getByRole('combobox', { name: 'Registered runtime' })
  await target.click()
  const teamOption = page.getByRole('option', { name: /support-orchestrator/i })
  await expect(teamOption).toBeVisible()
  await teamOption.click()

  // 3. Create a new conversation
  const newConvoBtn = page.getByRole('button', { name: '+ New conversation' })
  await newConvoBtn.click()

  // Wait for the conversation to be created
  const convoResponse = await waitForApi('/api/public/chat/conversations', 'POST')
  const convo = await convoResponse.json()
  console.log(`Created conversation: ${convo.id}`)

  // 4. Verify conversation appears in sidebar
  await expect(page.getByText('New conversation')).toBeVisible()

  // 5. Send a message  const textarea = page.getByRole('textbox', { name: /message/i })
  await textarea.fill('Help me reset my password')

  // Wait for both the run creation and the SSE stream  const runPromise = waitForApi('/api/public/chat/conversations/', 'POST').then(r => r.json())
  const ssePromise = waitForApi('/api/public/chat/runs/', 'GET')

  await page.getByRole('button', { name: 'Send' }).click()

  const run = await runPromise
  console.log(`Created run: ${run.run_id}`)

  // 6. Wait for SSE to complete  await ssePromise

  // 7. Verify messages are displayed
  await page.waitForTimeout(2000)
  const messages = page.locator('.chat-messages article')
  await expect(messages).toHaveCount(2)

  // 8. Verify assistant response has content  const assistant = messages.nth(1)
  await expect(assistant).not.toHaveText('')

  // Report any errors  if (errors.length) {
    console.log('Browser errors:', errors.join('\n'))
    throw new Error(`Chat flow failed: ${errors.join('; ')}`)
  }
})