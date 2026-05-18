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

const EMPTY_STATS_RESPONSE = {
  total_reviews: 0,
  reviews_today: 0,
  tokens_used_this_month: 0,
  estimated_cost_this_month: 0,
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
      passport: {
        verdict: 'READY_WITH_RISKS',
        confidence_score: 82,
        spec_source_type: 'review_dna',
        generated_at: new Date(Date.now() - 10 * 60_000).toISOString(),
        github_gate_state: 'failure',
      },
    },
    {
      id: 'rev-2',
      github_pr_title: null,
      github_pr_number: 13,
      status: 'pending',
      total_findings: 0,
      created_at: new Date(Date.now() - 5 * 60_000).toISOString(), // 5m ago
      passport: null,
    },
  ],
  total: 2,
}

const EMPTY_REVIEWS_RESPONSE = { reviews: [], total: 0 }

const REVIEWS_WITH_GENERATABLE_PASSPORT = {
  reviews: [
    {
      id: 'rev-dna',
      github_pr_title: 'feat: one click passport',
      github_pr_number: 24,
      status: 'done',
      total_findings: 0,
      created_at: new Date(Date.now() - 15 * 60_000).toISOString(),
      passport: null,
    },
  ],
  total: 1,
}

const SETTINGS_UNCONFIGURED = {
  plan: 'free',
  api_key_claude_set: false,
  api_key_gpt_set: false,
  ollama_enabled: false,
  default_agents: ['security', 'performance', 'style', 'logic'],
  warnings: [],
}

const SETTINGS_WITH_OLLAMA = {
  ...SETTINGS_UNCONFIGURED,
  ollama_enabled: true,
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

  it('shows review passport verdicts in review rows', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(REVIEWS_RESPONSE), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('Review Passport')).toBeInTheDocument()
      expect(screen.getByText('RISKS')).toBeInTheDocument()
      expect(screen.getByText('82%')).toBeInTheDocument()
      expect(screen.getByText('Not generated')).toBeInTheDocument()
    })
  })

  it('generates a Review DNA passport from a review row', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(REVIEWS_WITH_GENERATABLE_PASSPORT), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 'passport-1',
        review_id: 'rev-dna',
        verdict: 'READY',
        confidence_score: 95,
        spec_source_type: 'review_dna',
        generated_at: new Date().toISOString(),
        github_gate_state: null,
      }), { status: 201 }))

    renderDashboard()

    const generateButton = await screen.findByRole('button', {
      name: /generate review dna passport/i,
    })
    fireEvent.click(generateButton)

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/reviews/rev-dna/passport/review-dna',
        expect.objectContaining({ method: 'POST' })
      )
      expect(screen.getByText('READY')).toBeInTheDocument()
      expect(screen.getByText('95%')).toBeInTheDocument()
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
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY_STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(EMPTY_REVIEWS_RESPONSE), { status: 200 })
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ repositories: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(SETTINGS_UNCONFIGURED), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('No reviews yet')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Try demo review' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Paste diff' })).toBeInTheDocument()
    })
  })

  it('shows first-run setup progress from repositories and settings', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY_STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY_REVIEWS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        repositories: [{
          id: 'repo-1',
          github_repo_owner: 'octocat',
          github_repo_name: 'hello-world',
        }]
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(SETTINGS_WITH_OLLAMA), { status: 200 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('Setup progress')).toBeInTheDocument()
      expect(screen.getByText('3/4 complete')).toBeInTheDocument()
      expect(screen.getByText('Account ready')).toBeInTheDocument()
      expect(screen.getByText('Repository connected')).toBeInTheDocument()
      expect(screen.getByText('LLM provider ready')).toBeInTheDocument()
      expect(screen.getByText('Run your first review')).toBeInTheDocument()
    })
  })

  it('keeps onboarding actions usable when setup metadata fails', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY_STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY_REVIEWS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Repository API unavailable' }), { status: 500 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText(/setup progress is temporarily unavailable/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Try demo review' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Paste diff' })).toBeInTheDocument()
    })
  })

  it('starts a local demo review from the empty state', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY_STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY_REVIEWS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ repositories: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(SETTINGS_UNCONFIGURED), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 'demo-review-1',
        status: 'done',
      }), { status: 201 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Try demo review' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Try demo review' }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/reviews/playground/demo',
        expect.objectContaining({ method: 'POST' })
      )
    })
  })

  it('creates a local review from pasted diff without repositories', async () => {
    fetch
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY_STATS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY_REVIEWS_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ repositories: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(SETTINGS_UNCONFIGURED), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ repositories: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 'paste-review-1',
        status: 'done',
      }), { status: 201 }))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Paste diff' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Paste diff' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Paste diff review' })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Title'), {
      target: { value: 'Local paste review' },
    })
    fireEvent.change(screen.getByLabelText('Git diff'), {
      target: {
        value: 'diff --git a/app.py b/app.py\n+++ b/app.py\n@@ -1 +1,2 @@\n+API_KEY = "sk-test"',
      },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Start Review' }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/reviews/playground/diff',
        expect.objectContaining({ method: 'POST' })
      )
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
