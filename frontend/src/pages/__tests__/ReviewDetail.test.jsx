import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ReviewDetail } from '../ReviewDetail.jsx'
import { useAuthStore } from '@/store/index.js'

const REVIEW_RESPONSE = {
  id: 'review-1',
  user_id: 'user-1',
  repo_id: 'repo-1',
  github_pr_number: 42,
  github_pr_title: 'Improve checkout validation',
  head_sha: 'abcdef123456',
  status: 'done',
  error_message: null,
  selected_agents: ['security', 'performance', 'style', 'logic'],
  lm_used: 'ollama:qwen2.5-coder:7b',
  total_findings: 1,
  tokens_input: 1200,
  tokens_output: 300,
  estimated_cost: '0.0000',
  pr_comment_posted: false,
  created_at: '2026-04-27T10:00:00Z',
  completed_at: '2026-04-27T10:02:00Z',
  findings: [
    {
      id: 'finding-1',
      review_id: 'review-1',
      agent_name: 'security',
      finding_type: 'auth_bypass',
      severity: 'critical',
      file_path: 'app/api/oauth.py',
      line_number: 88,
      message: 'Callback token validation accepts unsigned JWTs.',
      suggestion: 'Verify token signatures.',
      is_duplicate: false,
      created_at: '2026-04-27T10:02:00Z',
    },
  ],
  agent_executions: [
    { id: 'exec-1', review_id: 'review-1', agent_name: 'security', status: 'done', tokens_input: 300, tokens_output: 80, findings_count: 1, error_message: null },
    { id: 'exec-2', review_id: 'review-1', agent_name: 'performance', status: 'done', tokens_input: 300, tokens_output: 70, findings_count: 0, error_message: null },
    { id: 'exec-3', review_id: 'review-1', agent_name: 'style', status: 'done', tokens_input: 300, tokens_output: 70, findings_count: 0, error_message: null },
    { id: 'exec-4', review_id: 'review-1', agent_name: 'logic', status: 'done', tokens_input: 300, tokens_output: 80, findings_count: 0, error_message: null },
  ],
}

function renderReviewDetail() {
  return render(
    <MemoryRouter initialEntries={['/reviews/review-1']}>
      <Routes>
        <Route path="/reviews/:id" element={<ReviewDetail />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ReviewDetail page', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ token: 'test-token', user: { id: 'u1', email: 'a@b.com', plan: 'free' } })
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('explains what the review agents do', async () => {
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(REVIEW_RESPONSE), { status: 200 }))

    renderReviewDetail()

    await waitFor(() => {
      expect(screen.getByText('About This Review')).toBeInTheDocument()
    })

    expect(screen.getByText(/specialized agents/i)).toBeInTheDocument()
    expect(screen.getByText(/Finds auth, injection, secret exposure/i)).toBeInTheDocument()
    expect(screen.getByText(/Looks for N\+1 queries/i)).toBeInTheDocument()
    expect(screen.getByText(/Provider: ollama:qwen2.5-coder:7b/i)).toBeInTheDocument()
  })

  it('shows actionable copy for failed analysis', async () => {
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({
      ...REVIEW_RESPONSE,
      status: 'error',
      error_message: 'All selected analysis agents failed',
      findings: [],
      total_findings: 0,
    }), { status: 200 }))

    renderReviewDetail()

    await waitFor(() => {
      expect(screen.getByText('Analysis did not complete')).toBeInTheDocument()
    })

    expect(screen.getByText('All selected analysis agents failed')).toBeInTheDocument()
    expect(screen.getByText(/Check repository webhook setup and LLM availability/i)).toBeInTheDocument()
  })
})
