import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { Repositories } from '../Repositories.jsx'
import { useAuthStore } from '@/store/index.js'

function renderRepositories() {
  return render(<Repositories />)
}

const REPOSITORY_FIXTURE = {
  id: 'repo-1',
  github_repo_owner: 'octocat',
  github_repo_name: 'hello-world',
  github_repo_url: 'https://github.com/octocat/hello-world',
  github_installation_id: 123456,
  enabled: true,
  created_at: '2026-05-15T09:00:00Z',
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

  it('shows a skeleton while repositories are loading', () => {
    fetch.mockReturnValue(new Promise(() => {}))

    const { container } = renderRepositories()

    expect(screen.getByRole('status', { name: 'Loading repositories' })).toBeInTheDocument()
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('shows a retry action when repository loading fails', async () => {
    fetch
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Database unavailable' }), { status: 500 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ repositories: [REPOSITORY_FIXTURE] }), { status: 200 })
      )

    renderRepositories()

    const retry = await screen.findByRole('button', { name: 'Try again' })
    expect(screen.getByText(/repositories could not load/i)).toBeInTheDocument()

    fireEvent.click(retry)

    await waitFor(() => {
      expect(screen.getByText('Connected Repositories (1)')).toBeInTheDocument()
    })
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('renders connected repositories as mobile-friendly cards', async () => {
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ repositories: [REPOSITORY_FIXTURE] }), { status: 200 })
    )

    renderRepositories()

    const cardList = await screen.findByTestId('repository-card-list')
    expect(cardList).toHaveTextContent('octocat/hello-world')
    expect(cardList).toHaveTextContent('Installation ID')
    expect(cardList).toHaveTextContent('123456')
    expect(screen.getByRole('button', { name: 'Disable octocat/hello-world' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove octocat/hello-world' })).toBeInTheDocument()
  })
})
