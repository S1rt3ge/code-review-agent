import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { Dashboard } from '../Dashboard.jsx'
import { useAuthStore } from '@/store/index.js'

const STATS_RESPONSE = {
  total_reviews: 42,
  reviews_today: 3,
  tokens_used_this_month: 150000,
  estimated_cost_this_month: 0.45,
}

const REVIEWS_RESPONSE = {
  reviews: [
    {
      id: 'rev-1',
      github_pr_title: 'feat: add login page',
      github_pr_number: 12,
      status: 'done',
      total_findings: 5,
      created_at: new Date(Date.now() - 30 * 60_000).toISOString(), // 30m ago
    },
    {
      id: 'rev-2',
      github_pr_title: null,
      github_pr_number: 13,
      status: 'pending',
      total_findings: 0,
      created_at: new Date(Date.now() - 5 * 60_000).toISOString(), // 5m ago
    },
  ],
  total: 2,
}

const STATS_WITH_FINDINGS = {
  ...STATS_RESPONSE,
  findings_by_severity: {
    critical: 2,
    high: 5,
    medium: 8,
    low: 3,
    info: 1,
  },
  findings_by_agent: {
    security: 4,
    performance: 3,
    style: 6,
    logic: 2,
  },
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  )
}

describe('Dashboard page', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ token: 'test-token', user: { id: 'u1', email: 'a@b.com', plan: 'free' } })
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows loading skeleton before data arrives', () => {
    // Never resolve so loading state persists
    fetch.mockReturnValue(new Promise(() => {}))

    const { container } = renderDashboard()
    // Skeleton cards have animate-pulse
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('shows stats cards after successful load', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(REVIEWS_RESPONSE), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument()       // total_reviews
      expect(screen.getByText('3')).toBeInTheDocument()         // reviews_today
      expect(screen.getByText('150.0k')).toBeInTheDocument()   // tokens
      expect(screen.getByText('$0.45')).toBeInTheDocument()    // cost
    })
  })

  it('shows review rows in the table', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(REVIEWS_RESPONSE), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('feat: add login page')).toBeInTheDocument()
      expect(screen.getByText('#12')).toBeInTheDocument()
    })
  })

  it('falls back to PR number as title when github_pr_title is null', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(REVIEWS_RESPONSE), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('PR #13')).toBeInTheDocument()
    })
  })

  it('shows empty state when there are no reviews', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ reviews: [], total: 0 }), { status: 200 })
      )

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('No reviews yet')).toBeInTheDocument()
    })
  })

  it('shows error banner when stats request fails', async () => {
    fetch
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Unauthorized' }), { status: 401 })
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ reviews: [], total: 0 }), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText(/failed to load stats/i)).toBeInTheDocument()
    })
  })

  it('shows "View" links for each review', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(REVIEWS_RESPONSE), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      const viewLinks = screen.getAllByRole('link', { name: 'View' })
      expect(viewLinks).toHaveLength(2)
      expect(viewLinks[0]).toHaveAttribute('href', '/reviews/rev-1')
    })
  })

  it('shows findings chart when findings_by_severity has data', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_WITH_FINDINGS), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(REVIEWS_RESPONSE), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      // The FindingsChart renders severity label "critical"
      expect(screen.getByText('critical')).toBeInTheDocument()
    })
  })

  it('shows New Review button', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(REVIEWS_RESPONSE), { status: 200 }))

    renderDashboard()

    // Wait for pending state updates to settle to avoid React act() warning noise.
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByRole('button', { name: 'New Review' })).toBeInTheDocument()
  })

  it('renders repository owner/name in New Review selector', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(REVIEWS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        repositories: [{
          id: 'repo-1',
          github_repo_owner: 'octocat',
          github_repo_name: 'hello-world',
        }]
      }), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'New Review' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'New Review' }))

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'octocat/hello-world' })).toBeInTheDocument()
    })
  })
})
