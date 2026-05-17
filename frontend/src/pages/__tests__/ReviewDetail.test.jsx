import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

const PASSPORT_RESPONSE = {
  id: 'passport-1',
  review_id: 'review-1',
  user_id: 'user-1',
  mode: 'combined',
  spec_source_type: 'manual',
  spec_source_ref: 'Issue #53',
  spec_input: '- User can run local demo',
  spec_digest: 'digest',
  verdict: 'READY_WITH_RISKS',
  confidence_score: 78,
  coverage_summary: [
    {
      criterion_id: 'AC-1',
      criterion: 'User can run local demo',
      status: 'covered',
      evidence: [{ summary: 'Added line matches the acceptance criterion.' }],
    },
  ],
  anti_slop_signals: [
    {
      type: 'missing_tests',
      severity: 'medium',
      summary: 'Application code changed without matching test changes',
      suggestion: 'Add focused tests for the changed application behavior.',
      evidence: ['frontend/src/pages/ReviewDetail.jsx'],
    },
  ],
  qa_steps: [
    {
      step: 1,
      title: 'Run local stack',
      command: 'docker compose up --build',
      expected: 'Frontend is available at http://localhost:5173',
    },
  ],
  missing_evidence: [],
  github_comment_id: null,
  github_comment_url: null,
  github_comment_posted_at: null,
  github_gate_state: null,
  github_gate_url: null,
  github_gate_posted_at: null,
  generated_at: '2026-04-27T10:02:00Z',
  created_at: '2026-04-27T10:02:00Z',
  updated_at: '2026-04-27T10:02:00Z',
}

function passportNotFoundResponse() {
  return new Response(
    JSON.stringify({ detail: 'Review passport not found' }),
    { status: 404 }
  )
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
    fetch.mockResolvedValueOnce(passportNotFoundResponse())

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
    fetch.mockResolvedValueOnce(passportNotFoundResponse())

    renderReviewDetail()

    await waitFor(() => {
      expect(screen.getByText('Analysis did not complete')).toBeInTheDocument()
    })

    expect(screen.getByText('All selected analysis agents failed')).toBeInTheDocument()
    expect(screen.getByText(/Check repository webhook setup and LLM availability/i)).toBeInTheDocument()
  })

  it('renders an existing review passport', async () => {
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(REVIEW_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(PASSPORT_RESPONSE), { status: 200 }))

    renderReviewDetail()

    await waitFor(() => {
      expect(screen.getByText('Review Passport')).toBeInTheDocument()
    })

    expect(screen.getByText('Ready with risks')).toBeInTheDocument()
    expect(screen.getByText('User can run local demo')).toBeInTheDocument()
    expect(screen.getByText('Application code changed without matching test changes')).toBeInTheDocument()
    expect(screen.getByText('docker compose up --build')).toBeInTheDocument()
  })

  it('generates a review passport from acceptance criteria', async () => {
    const user = userEvent.setup()
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(REVIEW_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(passportNotFoundResponse())
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(PASSPORT_RESPONSE), { status: 200 }))

    renderReviewDetail()

    await screen.findByRole('button', { name: /generate passport/i })

    await user.type(screen.getByPlaceholderText(/source reference/i), 'Issue #53')
    await user.type(screen.getByPlaceholderText(/acceptance criteria/i), '- User can run local demo')
    await user.type(screen.getByPlaceholderText(/paste git diff/i), '+ docker compose up --build')
    await user.click(screen.getByRole('button', { name: /generate passport/i }))

    await waitFor(() => {
      expect(screen.getByText('Ready with risks')).toBeInTheDocument()
    })

    expect(fetch).toHaveBeenCalledTimes(3)
    const [, requestOptions] = fetch.mock.calls[2]
    expect(requestOptions.method).toBe('POST')
    expect(JSON.parse(requestOptions.body)).toEqual({
      mode: 'combined',
      spec_source_type: 'manual',
      spec_source_ref: 'Issue #53',
      spec_input: '- User can run local demo',
      code_diff: '+ docker compose up --build',
    })
  })

  it('imports Review DNA criteria into the passport form', async () => {
    const user = userEvent.setup()
    const criteriaMarkdown = '# Review DNA Criteria Pack\n\n- [ ] AC-1: Spec-first evidence exists'
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(REVIEW_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(passportNotFoundResponse())
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({
      title: 'Review DNA Criteria Pack',
      source_profile: 'code-review-agent',
      spec_source_type: 'review_dna',
      spec_source_ref: 'Review DNA Criteria Pack (code-review-agent)',
      markdown: criteriaMarkdown,
      criteria: [],
    }), { status: 200 }))

    renderReviewDetail()

    await screen.findByRole('button', { name: /generate passport/i })
    await user.click(screen.getByRole('button', { name: /use review dna criteria/i }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/acceptance criteria/i).value).toContain(
        'AC-1: Spec-first evidence exists'
      )
    })
    expect(screen.getByPlaceholderText(/source reference/i).value).toBe(
      'Review DNA Criteria Pack (code-review-agent)'
    )
    expect(fetch.mock.calls[2][0]).toContain('/reviews/review-dna/criteria-pack')
    expect(fetch.mock.calls[2][1].method).toBe('GET')
  })

  it('generates a review passport directly from Review DNA', async () => {
    const user = userEvent.setup()
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(REVIEW_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(passportNotFoundResponse())
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({
      ...PASSPORT_RESPONSE,
      spec_source_type: 'review_dna',
      spec_source_ref: 'Review DNA Criteria Pack (code-review-agent)',
      spec_input: '# Review DNA Criteria Pack\n\n- [ ] AC-1: Spec-first evidence exists',
    }), { status: 200 }))

    renderReviewDetail()

    await screen.findByRole('button', { name: /generate passport/i })
    await user.click(screen.getByRole('button', { name: /generate with review dna/i }))

    expect(await screen.findByText('Ready with risks')).toBeInTheDocument()
    expect(fetch.mock.calls[2][0]).toContain('/reviews/review-1/passport/review-dna')
    expect(fetch.mock.calls[2][1].method).toBe('POST')
  })

  it('copies and deletes an existing review passport', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(REVIEW_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(PASSPORT_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(new Response(null, { status: 204 }))

    renderReviewDetail()

    await screen.findByText('Ready with risks')

    await user.click(screen.getByRole('button', { name: /copy qa/i }))
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('docker compose up --build'))
    expect(screen.getByText('QA script copied.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /delete passport/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /generate passport/i })).toBeInTheDocument()
    })

    const [, requestOptions] = fetch.mock.calls[2]
    expect(requestOptions.method).toBe('DELETE')
  })

  it('copies passport markdown and posts the passport to a PR', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(REVIEW_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(PASSPORT_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ body: '## Review Passport\nREADY_WITH_RISKS' }), { status: 200 }))
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({
      comment_id: 456,
      url: 'https://github.com/test/repo/issues/42#issuecomment-456',
      posted_at: '2026-04-27T10:05:00Z',
    }), { status: 200 }))

    renderReviewDetail()

    await screen.findByText('Ready with risks')

    await user.click(screen.getByRole('button', { name: /copy markdown/i }))
    expect(writeText).toHaveBeenCalledWith('## Review Passport\nREADY_WITH_RISKS')
    expect(screen.getByText('Markdown copied.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /post to pr/i }))
    expect(await screen.findByText(/Passport posted to PR/i)).toBeInTheDocument()

    const [, markdownRequest] = fetch.mock.calls[2]
    const [, postRequest] = fetch.mock.calls[3]
    expect(markdownRequest.method).toBe('GET')
    expect(postRequest.method).toBe('POST')
    expect(fetch.mock.calls[2][0]).toContain('/reviews/review-1/passport/markdown')
    expect(fetch.mock.calls[3][0]).toContain('/reviews/review-1/passport/post-comment')
  })

  it('publishes the review passport gate as a commit status', async () => {
    const user = userEvent.setup()
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(REVIEW_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(PASSPORT_RESPONSE), { status: 200 }))
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({
      context: 'AI Review Passport Gate',
      verdict: 'READY_WITH_RISKS',
      state: 'failure',
      description: 'Review Passport READY_WITH_RISKS: review required before merge.',
      required_action: 'review_risks',
      github_gate_state: 'failure',
      github_gate_url: 'https://api.github.com/repos/test/repo/statuses/abcdef123456',
      github_gate_posted_at: '2026-04-27T10:06:00Z',
    }), { status: 200 }))

    renderReviewDetail()

    await screen.findByText('Ready with risks')
    expect(screen.getByText(/Gate status/i)).toBeInTheDocument()
    expect(screen.getByText(/failure/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /publish gate/i }))

    expect(await screen.findByText(/Gate published to GitHub/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /view gate status/i })).toHaveAttribute(
      'href',
      'https://api.github.com/repos/test/repo/statuses/abcdef123456'
    )
    const [, gateRequest] = fetch.mock.calls[2]
    expect(gateRequest.method).toBe('POST')
    expect(fetch.mock.calls[2][0]).toContain('/reviews/review-1/passport/gate/publish')
  })
})
