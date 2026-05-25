import { expect, test } from '@playwright/test'

const apiBaseURL = process.env.E2E_API_URL || 'http://localhost:8000'

async function expectNoLocalAuthBlock(page) {
  const body = page.locator('body')
  await expect(body).not.toContainText(/email is not verified|verify your email/i)
}

test.describe('local demo smoke', () => {
  test('user can register, sign in, run a demo review, and generate a passport', async ({ page, request }) => {
    const serverErrors = []
    page.on('response', response => {
      if (response.status() >= 500) {
        serverErrors.push(`${response.status()} ${response.url()}`)
      }
    })
    page.on('pageerror', error => {
      serverErrors.push(`pageerror ${error.message}`)
    })

    const health = await request.get(`${apiBaseURL}/health`)
    expect(health.ok()).toBeTruthy()

    const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const email = `ui-smoke-${stamp}@example.local`
    const password = 'SmokePass123!'

    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Code Review Agent' })).toBeVisible()
    await expectNoLocalAuthBlock(page)

    await page.getByRole('button', { name: 'Create account' }).first().click()
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password', { exact: true }).fill(password)
    await page.getByLabel('Confirm Password').fill(password)
    await page.locator('form').getByRole('button', { name: 'Create account' }).click()

    await expect(page.getByText('Account created. You can sign in now.')).toBeVisible()
    await expectNoLocalAuthBlock(page)

    await page.getByRole('button', { name: 'Go to sign in' }).click()
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password', { exact: true }).fill(password)
    await page.locator('form').getByRole('button', { name: 'Sign in' }).click()

    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
    await expectNoLocalAuthBlock(page)

    await page.getByRole('button', { name: 'Try demo review' }).click()
    await page.waitForURL(/\/reviews\/[0-9a-f-]+$/i)

    await expect(page.getByRole('heading', { name: 'Local demo review' })).toBeVisible()
    await expect(page.getByText('Provider: local-playground.')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Findings' })).toBeVisible()
    await expectNoLocalAuthBlock(page)

    await page.getByRole('button', { name: 'Generate with Review DNA' }).click()
    await expect(page.getByText('Passport generated from Review DNA.')).toBeVisible()
    await expect(page.getByText('Gate status')).toBeVisible()
    await expect(page.getByText(/Review Passport (READY|READY_WITH_RISKS|BLOCKED)/)).toBeVisible()
    await expect(page.getByText('Coverage')).toBeVisible()
    await expect(page.getByText('Manual QA Script')).toBeVisible()
    await expectNoLocalAuthBlock(page)

    expect(serverErrors).toEqual([])
  })
})
