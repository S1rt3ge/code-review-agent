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
 * @property {boolean} pr_comment_posted
 * @property {string} created_at
 * @property {string|null} completed_at
 * @property {Finding[]} findings
 * @property {AgentExecution[]} agent_executions
 */

const KNOWN_AGENTS = ['security', 'performance', 'style', 'logic']

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
 * Review detail page. Shows review metadata, per-agent status, and all findings.
 * Subscribes to WebSocket updates while the review is in "analyzing" state.
 *
 * @returns {React.ReactElement}
 */
export function ReviewDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { get, post, loading } = useApi()

  /** @type {[Review|null, function]} */
  const [review, setReview] = useState(null)
  const [error, setError] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [postingComment, setPostingComment] = useState(false)
  const [commentMsg, setCommentMsg] = useState(null)

  // Live agent statuses from WebSocket (only active while analyzing)
  const wsReviewId = review?.status === 'analyzing' ? id : null
  const { agentStatuses, isConnected } = useWebsocket(wsReviewId)

  const fetchReview = useCallback(async () => {
    setError(null)
    try {
      const data = await get(`/reviews/${id}`)
      setReview(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load review')
    }
  }, [get, id])

  useEffect(() => {
    fetchReview()
  }, [fetchReview])

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

  // Merge DB agent executions with live WS statuses
  const agentStatusList = KNOWN_AGENTS.map(name => {
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
  const canComment = review.status === 'done' && findings.length > 0 && !review.pr_comment_posted
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

      {/* Error state */}
      {review.status === 'error' && review.error_message && (
        <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-400">
          <span className="font-medium">Error: </span>{review.error_message}
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
