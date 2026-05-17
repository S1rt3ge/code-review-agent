import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useApi } from '@/hooks/useApi.js'
import { useWebsocket } from '@/hooks/useWebsocket.js'
import { FindingsTable } from '@/components/FindingsTable.jsx'
import { AgentStatus } from '@/components/AgentStatus.jsx'
import { StatusBadge } from '@/components/StatusBadge.jsx'

/**
 * @typedef {import('@/components/FindingsTable.jsx').Finding} Finding
 */

/**
 * @typedef {Object} AgentExecution
 * @property {string} id
 * @property {string} agent_name
 * @property {string} status
 * @property {number} tokens_input
 * @property {number} tokens_output
 * @property {number} findings_count
 * @property {string|null} error_message
 * @property {string[]|null} selected_agents
 */

/**
 * @typedef {Object} Review
 * @property {string} id
 * @property {number} github_pr_number
 * @property {string|null} github_pr_title
 * @property {string|null} head_sha
 * @property {string} status
 * @property {string|null} error_message
 * @property {number} total_findings
 * @property {number} tokens_input
 * @property {number} tokens_output
 * @property {string} estimated_cost
 * @property {string|null} lm_used
 * @property {boolean} pr_comment_posted
 * @property {string} created_at
 * @property {string|null} completed_at
 * @property {Finding[]} findings
 * @property {AgentExecution[]} agent_executions
 */

const KNOWN_AGENTS = ['security', 'performance', 'style', 'logic']

const AGENT_EXPLAINERS = {
  security: 'Finds auth, injection, secret exposure, and unsafe trust-boundary patterns.',
  performance: 'Looks for N+1 queries, expensive loops, memory pressure, and scaling risks.',
  style: 'Flags readability, naming, consistency, and maintainability issues.',
  logic: 'Checks boundary cases, null handling, type mismatches, and correctness bugs.',
}

const PASSPORT_VERDICT_CLASSES = {
  READY: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  READY_WITH_RISKS: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  BLOCKED: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
}

const PASSPORT_VERDICT_LABELS = {
  READY: 'Ready',
  READY_WITH_RISKS: 'Ready with risks',
  BLOCKED: 'Blocked',
}

const PASSPORT_GATE_BY_VERDICT = {
  READY: {
    state: 'success',
    description: 'Review Passport READY: evidence covers merge criteria.',
    required_action: 'merge_ready',
  },
  READY_WITH_RISKS: {
    state: 'failure',
    description: 'Review Passport READY_WITH_RISKS: review required before merge.',
    required_action: 'review_risks',
  },
  BLOCKED: {
    state: 'failure',
    description: 'Review Passport BLOCKED: missing required evidence.',
    required_action: 'fix_blockers',
  },
}

/**
 * Format seconds into a human-readable duration string.
 * @param {number} seconds
 * @returns {string}
 */
function formatDuration(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
}

/**
 * Format ISO date to a short readable string.
 * @param {string|null} iso
 * @returns {string}
 */
function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

/**
 * Single metadata row for the review info panel.
 * @param {{ label: string, children: React.ReactNode }} props
 * @returns {React.ReactElement}
 */
function MetaRow({ label, children }) {
  return (
    <div className="flex items-start gap-2 py-2 border-b border-gray-100 dark:border-gray-700 last:border-0">
      <span className="text-xs font-medium text-gray-500 dark:text-gray-400 w-28 shrink-0 pt-0.5">
        {label}
      </span>
      <span className="text-sm text-gray-800 dark:text-gray-200 min-w-0 break-all">{children}</span>
    </div>
  )
}

/**
 * Build a display-only gate state from the existing passport payload.
 * @param {any} passport
 * @returns {any}
 */
function buildPassportGateView(passport) {
  const fallback = {
    state: 'error',
    description: 'Review Passport gate could not map the current verdict.',
    required_action: 'investigate_gate',
  }
  const gate = PASSPORT_GATE_BY_VERDICT[passport?.verdict] ?? fallback
  return {
    ...gate,
    context: 'AI Review Passport Gate',
    verdict: passport?.verdict ?? 'UNKNOWN',
    github_gate_state: passport?.github_gate_state ?? null,
    github_gate_url: passport?.github_gate_url ?? null,
    github_gate_posted_at: passport?.github_gate_posted_at ?? null,
  }
}

/**
 * Explains what the multi-agent review did for non-technical demo viewers.
 * @param {{ agents: string[], lmUsed?: string|null }} props
 * @returns {React.ReactElement}
 */
function AboutReviewPanel({ agents, lmUsed }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
        About This Review
      </h2>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
        The code diff was analyzed by specialized agents, then duplicate findings were grouped and ranked by severity.
      </p>
      <div className="space-y-2">
        {agents.map(agent => (
          <div key={agent} className="rounded-lg bg-gray-50 dark:bg-gray-900 px-3 py-2">
            <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 capitalize">
              {agent}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {AGENT_EXPLAINERS[agent] ?? 'Runs a focused review pass over the pull request diff.'}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">
        Provider: {lmUsed || 'selected automatically from your configured LLM settings'}.
      </p>
    </div>
  )
}

/**
 * Evidence-backed merge readiness panel.
 * @param {{
 *   passport: any,
 *   onGenerate: (payload: any) => Promise<void>,
 *   onDelete: () => Promise<void>,
 *   onCopyMarkdown: () => Promise<string>,
 *   onImportReviewDnaCriteria: () => Promise<any>,
 *   onPostToPr: () => Promise<any>,
 *   onPublishGate: () => Promise<any>
 * }} props
 * @returns {React.ReactElement}
 */
function ReviewPassportPanel({
  passport,
  onGenerate,
  onDelete,
  onCopyMarkdown,
  onImportReviewDnaCriteria,
  onPostToPr,
  onPublishGate,
}) {
  const [mode, setMode] = useState('combined')
  const [specSourceType, setSpecSourceType] = useState('manual')
  const [specRef, setSpecRef] = useState('')
  const [specInput, setSpecInput] = useState('')
  const [codeDiff, setCodeDiff] = useState('')
  const [busy, setBusy] = useState(false)
  const [criteriaBusy, setCriteriaBusy] = useState(false)
  const [error, setError] = useState(null)
  const [copyMessage, setCopyMessage] = useState(null)

  const requiresSpec = mode !== 'anti_ai_slop'
  const specTooLong = specInput.length > 20000
  const diffTooLong = codeDiff.length > 100000
  const canSubmit = !busy && !criteriaBusy && !specTooLong && !diffTooLong && (!requiresSpec || specInput.trim())

  const handleGenerate = async event => {
    event.preventDefault()
    setError(null)
    setCopyMessage(null)
    if (!canSubmit) {
      setError('Acceptance criteria are required for spec-based passport modes.')
      return
    }
    setBusy(true)
    try {
      await onGenerate({
        mode,
        spec_source_type: specSourceType,
        spec_source_ref: specRef.trim() || null,
        spec_input: specInput.trim() || null,
        code_diff: codeDiff.trim() || null,
      })
      setSpecInput('')
      setCodeDiff('')
      setSpecSourceType('manual')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate passport')
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    setError(null)
    setBusy(true)
    try {
      await onDelete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete passport')
    } finally {
      setBusy(false)
    }
  }

  const handleImportReviewDnaCriteria = async () => {
    setError(null)
    setCopyMessage(null)
    setCriteriaBusy(true)
    try {
      const pack = await onImportReviewDnaCriteria()
      setSpecSourceType(pack.spec_source_type || 'review_dna')
      setSpecRef(pack.spec_source_ref || `${pack.title} (${pack.source_profile})`)
      setSpecInput(pack.markdown || '')
      if (mode === 'anti_ai_slop') setMode('combined')
      setCopyMessage('Review DNA criteria loaded.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Review DNA criteria')
    } finally {
      setCriteriaBusy(false)
    }
  }

  const handleCopyQa = async () => {
    if (!passport?.qa_steps?.length || !navigator.clipboard) return
    const text = passport.qa_steps
      .map(step => {
        const command = step.command ? `\nCommand: ${step.command}` : ''
        return `${step.step}. ${step.title}${command}\nExpected: ${step.expected}`
      })
      .join('\n\n')
    await navigator.clipboard.writeText(text)
    setCopyMessage('QA script copied.')
  }

  const handleCopyMarkdown = async () => {
    setError(null)
    setCopyMessage(null)
    if (!navigator.clipboard) {
      setError('Clipboard is unavailable in this browser.')
      return
    }
    setBusy(true)
    try {
      const body = await onCopyMarkdown()
      await navigator.clipboard.writeText(body)
      setCopyMessage('Markdown copied.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to copy Markdown')
    } finally {
      setBusy(false)
    }
  }

  const handlePostToPr = async () => {
    setError(null)
    setCopyMessage(null)
    setBusy(true)
    try {
      await onPostToPr()
      setCopyMessage('Passport posted to PR.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to post passport to PR')
    } finally {
      setBusy(false)
    }
  }

  const handlePublishGate = async () => {
    setError(null)
    setCopyMessage(null)
    setBusy(true)
    try {
      await onPublishGate()
      setCopyMessage('Gate published to GitHub.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish gate')
    } finally {
      setBusy(false)
    }
  }

  const verdictClass = PASSPORT_VERDICT_CLASSES[passport?.verdict] ?? PASSPORT_VERDICT_CLASSES.READY_WITH_RISKS
  const gate = passport ? buildPassportGateView(passport) : null
  const gateState = gate?.github_gate_state ?? gate?.state

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Review Passport</h2>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Merge readiness, evidence, and QA.
          </p>
        </div>
        {passport && (
          <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${verdictClass}`}>
            {PASSPORT_VERDICT_LABELS[passport.verdict] ?? passport.verdict}
          </span>
        )}
      </div>

      {passport ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-lg bg-gray-50 dark:bg-gray-900 px-3 py-2">
              <p className="text-xs text-gray-500 dark:text-gray-400">Confidence</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">{passport.confidence_score}%</p>
            </div>
            <div className="rounded-lg bg-gray-50 dark:bg-gray-900 px-3 py-2">
              <p className="text-xs text-gray-500 dark:text-gray-400">Criteria</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">{passport.coverage_summary?.length ?? 0}</p>
            </div>
            <div className="rounded-lg bg-gray-50 dark:bg-gray-900 px-3 py-2">
              <p className="text-xs text-gray-500 dark:text-gray-400">Signals</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">{passport.anti_slop_signals?.length ?? 0}</p>
            </div>
          </div>

          {gate && (
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-gray-600 dark:text-gray-300">Gate status</p>
                  <p className="mt-1 text-sm text-gray-800 dark:text-gray-200">{gate.description}</p>
                </div>
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
                  gateState === 'success'
                    ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                    : gateState === 'failure'
                      ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                      : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                }`}>
                  {gateState}
                </span>
              </div>
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Action: {gate.required_action.replaceAll('_', ' ')}
                {gate.github_gate_posted_at ? ` · Last published ${formatDate(gate.github_gate_posted_at)}` : ''}
              </p>
            </div>
          )}

          {passport.coverage_summary?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-600 dark:text-gray-300 mb-2">Coverage</p>
              <div className="space-y-2">
                {passport.coverage_summary.map(item => (
                  <div key={item.criterion_id} className="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm text-gray-800 dark:text-gray-200">{item.criterion}</p>
                      <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{item.status}</span>
                    </div>
                    {item.evidence?.[0]?.summary && (
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{item.evidence[0].summary}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {passport.anti_slop_signals?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-600 dark:text-gray-300 mb-2">Anti-AI-Slop Signals</p>
              <div className="space-y-2">
                {passport.anti_slop_signals.map(signal => (
                  <div key={`${signal.type}-${signal.summary}`} className="rounded-lg bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 px-3 py-2">
                    <p className="text-sm font-medium text-amber-800 dark:text-amber-200">{signal.summary}</p>
                    <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">{signal.suggestion}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {passport.qa_steps?.length > 0 && (
            <div>
              <div className="flex items-center justify-between gap-3 mb-2">
                <p className="text-xs font-semibold text-gray-600 dark:text-gray-300">Manual QA Script</p>
                <button
                  type="button"
                  onClick={handleCopyQa}
                  className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline"
                >
                  Copy QA
                </button>
              </div>
              <ol className="space-y-2">
                {passport.qa_steps.map(step => (
                  <li key={step.step} className="rounded-lg bg-gray-50 dark:bg-gray-900 px-3 py-2">
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{step.step}. {step.title}</p>
                    {step.command && <p className="mt-1 font-mono text-xs text-gray-500 dark:text-gray-400">{step.command}</p>}
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{step.expected}</p>
                  </li>
                ))}
              </ol>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleCopyMarkdown}
              disabled={busy}
              className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50"
            >
              Copy Markdown
            </button>
            <button
              type="button"
              onClick={handlePostToPr}
              disabled={busy}
              className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50"
            >
              Post to PR
            </button>
            <button
              type="button"
              onClick={handlePublishGate}
              disabled={busy}
              className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50"
            >
              Publish Gate
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={busy}
              className="text-xs font-medium text-red-600 dark:text-red-400 hover:underline disabled:opacity-50"
            >
              Delete passport
            </button>
            {copyMessage && <span className="text-xs text-green-600 dark:text-green-400">{copyMessage}</span>}
            {passport.github_comment_url && (
              <a
                href={passport.github_comment_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                View PR comment
              </a>
            )}
            {passport.github_gate_url && (
              <a
                href={passport.github_gate_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                View gate status
              </a>
            )}
          </div>
        </div>
      ) : (
        <form onSubmit={handleGenerate} className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {[
              ['combined', 'Combined'],
              ['spec_evidence', 'Spec evidence'],
              ['anti_ai_slop', 'Anti-AI-Slop'],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setMode(value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                  mode === value
                    ? 'bg-blue-600 border-blue-600 text-white'
                    : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={handleImportReviewDnaCriteria}
            disabled={busy || criteriaBusy}
            className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50"
          >
            {criteriaBusy ? 'Loading Review DNA…' : 'Use Review DNA criteria'}
          </button>

          <input
            value={specRef}
            onChange={event => {
              setSpecSourceType('manual')
              setSpecRef(event.target.value)
            }}
            placeholder="Source reference, e.g. Issue #53"
            maxLength={120}
            className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-white"
          />

          <textarea
            value={specInput}
            onChange={event => {
              setSpecSourceType('manual')
              setSpecInput(event.target.value)
            }}
            placeholder="Paste acceptance criteria or issue/spec text"
            rows={5}
            maxLength={20000}
            className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-white"
          />

          <textarea
            value={codeDiff}
            onChange={event => setCodeDiff(event.target.value)}
            placeholder="Optional: paste git diff for older reviews without a stored snapshot"
            rows={4}
            maxLength={100000}
            className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-white"
          />

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className={`text-xs ${specTooLong || diffTooLong ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'}`}>
              Spec {specInput.length}/20000 · Diff {codeDiff.length}/100000
            </p>
            <button
              type="submit"
              disabled={!canSubmit}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {busy ? 'Generating…' : 'Generate passport'}
            </button>
          </div>
        </form>
      )}

      {error && (
        <p className="mt-3 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 px-3 py-2 text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
    </div>
  )
}

/**
 * Review detail page. Shows review metadata, per-agent status, and all findings.
 * Subscribes to WebSocket updates while the review is in "analyzing" state.
 *
 * @returns {React.ReactElement}
 */
export function ReviewDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { get, post, del: delApi, loading } = useApi()

  /** @type {[Review|null, function]} */
  const [review, setReview] = useState(null)
  const [error, setError] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [postingComment, setPostingComment] = useState(false)
  const [commentMsg, setCommentMsg] = useState(null)
  const [passport, setPassport] = useState(null)

  // Live agent statuses from WebSocket (only active while analyzing)
  const wsReviewId = review?.status === 'analyzing' ? id : null
  const { agentStatuses, isConnected, wsError } = useWebsocket(wsReviewId)

  const fetchReview = useCallback(async () => {
    setError(null)
    try {
      const data = await get(`/reviews/${id}`)
      setReview(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load review')
    }
  }, [get, id])

  const fetchPassport = useCallback(async () => {
    try {
      const data = await get(`/reviews/${id}/passport`)
      setPassport(data)
    } catch (err) {
      const message = err instanceof Error ? err.message : ''
      if (!message.toLowerCase().includes('passport not found')) {
        setCommentMsg(`Passport unavailable: ${message || 'unknown error'}`)
      }
      setPassport(null)
    }
  }, [get, id])

  useEffect(() => {
    fetchReview()
    fetchPassport()
  }, [fetchReview, fetchPassport])

  // Poll every 3s while analyzing (WS handles live updates, poll is the fallback)
  useEffect(() => {
    if (review?.status !== 'analyzing') return
    const timer = setInterval(fetchReview, 3000)
    return () => clearInterval(timer)
  }, [review?.status, fetchReview])

  const handleAnalyze = useCallback(async () => {
    setAnalyzing(true)
    try {
      await post(`/reviews/${id}/analyze`, {})
      await fetchReview()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start analysis')
    } finally {
      setAnalyzing(false)
    }
  }, [post, id, fetchReview])

  const handlePostComment = useCallback(async () => {
    setPostingComment(true)
    setCommentMsg(null)
    try {
      await post(`/reviews/${id}/post-comment`, {})
      setCommentMsg('Comment posted to GitHub successfully.')
      await fetchReview()
    } catch (err) {
      setCommentMsg(`Failed: ${err instanceof Error ? err.message : 'unknown error'}`)
    } finally {
      setPostingComment(false)
    }
  }, [post, id, fetchReview])

  const handleGeneratePassport = useCallback(async payload => {
    const data = await post(`/reviews/${id}/passport`, payload)
    setPassport(data)
  }, [post, id])

  const handleDeletePassport = useCallback(async () => {
    await delApi(`/reviews/${id}/passport`)
    setPassport(null)
  }, [delApi, id])

  const handleCopyPassportMarkdown = useCallback(async () => {
    const data = await get(`/reviews/${id}/passport/markdown`)
    return data.body
  }, [get, id])

  const handleImportReviewDnaCriteria = useCallback(async () => {
    return get('/reviews/review-dna/criteria-pack')
  }, [get])

  const handlePostPassportToPr = useCallback(async () => {
    const data = await post(`/reviews/${id}/passport/post-comment`, {})
    setPassport(current => current
      ? {
          ...current,
          github_comment_id: data.comment_id,
          github_comment_url: data.url,
          github_comment_posted_at: data.posted_at,
        }
      : current)
    return data
  }, [post, id])

  const handlePublishPassportGate = useCallback(async () => {
    const data = await post(`/reviews/${id}/passport/gate/publish`, {})
    setPassport(current => current
      ? {
          ...current,
          github_gate_state: data.github_gate_state,
          github_gate_url: data.github_gate_url,
          github_gate_posted_at: data.github_gate_posted_at,
        }
      : current)
    return data
  }, [post, id])

  // Merge DB agent executions with live WS statuses
  const selectedAgents = review?.selected_agents?.length ? review.selected_agents : KNOWN_AGENTS
  const agentStatusList = selectedAgents.map(name => {
    const exec = review?.agent_executions?.find(e => e.agent_name === name)
    const liveStatus = agentStatuses[name]
    return {
      name,
      status: liveStatus ?? exec?.status ?? 'pending',
      tokensIn: exec?.tokens_input ?? 0,
      tokensOut: exec?.tokens_output ?? 0,
      findingsCount: exec?.findings_count ?? 0,
      errorMessage: exec?.error_message ?? null,
    }
  })

  const findings = review?.findings ?? []
  const nonDupFindings = findings.filter(f => !f.is_duplicate).map(f => ({
    id: f.id,
    agentName: f.agent_name,
    severity: f.severity,
    filePath: f.file_path,
    lineNumber: f.line_number,
    message: f.message,
    suggestion: f.suggestion,
  }))

  if (loading && !review) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error && !review) {
    return (
      <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-6">
        <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        <button
          onClick={() => navigate('/')}
          className="mt-4 text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          Back to Dashboard
        </button>
      </div>
    )
  }

  if (!review) return null

  const canAnalyze = review.status === 'pending' || review.status === 'error'
  const isLocalPlayground = review.lm_used === 'local-playground'
  const canComment =
    review.status === 'done' &&
    findings.length > 0 &&
    !review.pr_comment_posted &&
    !isLocalPlayground
  const durationSec =
    review.completed_at && review.created_at
      ? (new Date(review.completed_at) - new Date(review.created_at)) / 1000
      : null

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <button
              onClick={() => navigate('/')}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
              aria-label="Back"
            >
              <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
              </svg>
            </button>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white truncate">
              {review.github_pr_title ?? `PR #${review.github_pr_number}`}
            </h1>
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
            <span className="font-mono">PR #{review.github_pr_number}</span>
            {review.head_sha && (
              <span className="font-mono">{review.head_sha.slice(0, 7)}</span>
            )}
            <StatusBadge status={review.status} />
            {review.status === 'analyzing' && isConnected && (
              <span className="text-xs text-blue-500 dark:text-blue-400">● live</span>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 shrink-0">
          {canAnalyze && (
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {analyzing ? 'Starting…' : review.status === 'error' ? 'Re-analyze' : 'Analyze'}
            </button>
          )}
          {canComment && (
            <button
              onClick={handlePostComment}
              disabled={postingComment}
              className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {postingComment ? 'Posting…' : 'Post GitHub Comment'}
            </button>
          )}
          {review.pr_comment_posted && (
            <span className="text-xs text-green-600 dark:text-green-400 font-medium">
              ✓ Comment posted
            </span>
          )}
        </div>
      </div>

      {/* Comment feedback */}
      {commentMsg && (
        <div className={`rounded-lg px-4 py-3 text-sm ${
          commentMsg.startsWith('Failed')
            ? 'bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
            : 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
        }`}>
          {commentMsg}
        </div>
      )}

      {review.status === 'analyzing' && wsError && (
        <div className="rounded-lg px-4 py-3 text-sm bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
          Live updates unavailable: {wsError}. Polling will continue.
        </div>
      )}

      {/* Error state */}
      {review.status === 'error' && review.error_message && (
        <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-400 space-y-1">
          <p className="font-medium">Analysis did not complete</p>
          <p>{review.error_message}</p>
          <p className="text-xs text-red-600 dark:text-red-300">
            Check repository webhook setup and LLM availability, then run the review again.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: metadata + agent status */}
        <div className="space-y-4">
          {/* Metadata card */}
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Details</h2>
            <MetaRow label="Status"><StatusBadge status={review.status} /></MetaRow>
            <MetaRow label="Findings">{review.total_findings}</MetaRow>
            <MetaRow label="Tokens in">{review.tokens_input.toLocaleString()}</MetaRow>
            <MetaRow label="Tokens out">{review.tokens_output.toLocaleString()}</MetaRow>
            <MetaRow label="Model">{review.lm_used ?? '—'}</MetaRow>
            <MetaRow label="Cost">${Number(review.estimated_cost).toFixed(4)}</MetaRow>
            {durationSec !== null && (
              <MetaRow label="Duration">{formatDuration(durationSec)}</MetaRow>
            )}
            <MetaRow label="Created">{formatDate(review.created_at)}</MetaRow>
            {review.completed_at && (
              <MetaRow label="Completed">{formatDate(review.completed_at)}</MetaRow>
            )}
          </div>

          {/* Agent status card */}
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Agents</h2>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {agentStatusList.map(agent => (
                <AgentStatus
                  key={agent.name}
                  agentName={agent.name}
                  status={agent.status}
                />
              ))}
            </div>
          </div>

          <AboutReviewPanel agents={selectedAgents} lmUsed={review.lm_used} />

          <ReviewPassportPanel
            passport={passport}
            onGenerate={handleGeneratePassport}
            onDelete={handleDeletePassport}
            onCopyMarkdown={handleCopyPassportMarkdown}
            onImportReviewDnaCriteria={handleImportReviewDnaCriteria}
            onPostToPr={handlePostPassportToPr}
            onPublishGate={handlePublishPassportGate}
          />
        </div>

        {/* Right: findings table */}
        <div className="lg:col-span-2">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                Findings
                {nonDupFindings.length > 0 && (
                  <span className="ml-2 px-1.5 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                    {nonDupFindings.length}
                  </span>
                )}
              </h2>
              {findings.length !== nonDupFindings.length && (
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  {findings.length - nonDupFindings.length} duplicates hidden
                </span>
              )}
            </div>
            <FindingsTable findings={nonDupFindings} />
          </div>
        </div>
      </div>
    </div>
  )
}
