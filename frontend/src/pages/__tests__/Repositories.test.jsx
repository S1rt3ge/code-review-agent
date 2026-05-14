import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { Repositories } from '../Repositories.jsx'
import { useAuthStore } from '@/store/index.js'

function renderRepositories() {
  return render(<Repositories />)
}

describe('Repositories page', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ token: 'test-token', user: { id: 'u1', email: 'a@b.com', plan: 'free' } })
    vi.stubGlobal('fetch', vi.fn())
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows local webhook tunnel setup guidance', async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ repositories: [], total: 0 }), { status: 200 })
    )

    renderRepositories()

    await waitFor(() => {
      expect(screen.getByText('GitHub Webhook Setup')).toBeInTheDocument()
    })

    expect(screen.getByText(/No paid domain or hosting is required/i)).toBeInTheDocument()
    expect(screen.getByText('cloudflared tunnel --url http://localhost:8000')).toBeInTheDocument()
    expect(screen.getByText('ngrok http 8000')).toBeInTheDocument()
    expect(screen.getByText('Pull request events only.')).toBeInTheDocument()
    expect(screen.getByText(/X-Hub-Signature-256/)).toBeInTheDocument()
  })

  it('copies the webhook secret env var name', async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ repositories: [], total: 0 }), { status: 200 })
    )

    renderRepositories()

    const copySecret = await screen.findByRole('button', {
      name: 'Copy webhook secret env var name',
    })
    fireEvent.click(copySecret)

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('GITHUB_WEBHOOK_SECRET')
    })
  })
})
