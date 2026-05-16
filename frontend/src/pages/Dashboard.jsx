import { useState, useEffect, useCallback, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApi } from '@/hooks/useApi.js'
import { StatusBadge } from '@/components/StatusBadge.jsx'

/**
 * @typedef {Object} DashboardStats
 * @property {number} total_reviews
 * @property {number} reviews_today
 * @property {number} tokens_used_this_month
 * @property {number} estimated_cost_this_month
 * @property {Object.<string, number>} [findings_by_severity]
 * @property {Object.<string, number>} [findings_by_agent]
 */

/**
 * @typedef {Object} ReviewSummary
 * @property {string} id
 * @property {string|null} github_pr_title
 * @property {number} github_pr_number
 * @property {'pending'|'analyzing'|'done'|'error'} status
 * @property {string|null} [error_message]
 * @property {number} total_findings
 * @property {string} created_at
 */

/**
 * @typedef {Object} Repository
 * @property {string} id
 * @property {string} github_repo_owner
 * @property {string} github_repo_name
 */

/**
 * @typedef {Object} SetupStatus
 * @property {boolean} repositoriesConfigured
 * @property {boolean} llmConfigured
 * @property {boolean} loading
 * @property {string|null} error
 */

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

/**
 * @param {{ label: string, value: string|number, icon: string }} props
 * @returns {React.ReactElement}
 */
function StatCard({ label, value, icon }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-500 dark:text-gray-400">{label}</span>
        <span className="text-xl" aria-hidden="true">{icon}</span>
      </div>
      <div className="text-2xl font-bold text-gray-900 dark:text-white">{value}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------

/** @returns {React.ReactElement} */
function StatsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {[0, 1, 2, 3].map(i => (
        <div
          key={i}
          className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5 animate-pulse"
        >
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24 mb-3" />
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-16" />
        </div>
      ))}
    </div>
  )
}

/** @returns {React.ReactElement} */
function TableSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-32 animate-pulse" />
      </div>
      {[0, 1, 2, 3].map(i => (
        <div key={i} className="p-4 border-b border-gray-100 dark:border-gray-800 animate-pulse">
          <div className="flex items-center gap-4">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-40" />
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-16" />
            <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded-full w-20 ml-auto" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Findings chart
// ---------------------------------------------------------------------------

/** @type {Record<string, string>} */
const SEVERITY_COLORS = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
  info: 'bg-gray-400',
}

/** @type {Record<string, string>} */
const AGENT_COLORS = {
  security: 'bg-purple-500',
  performance: 'bg-cyan-500',
  style: 'bg-green-500',
  logic: 'bg-pink-500',
}

/**
 * A horizontal percentage bar row.
 * @param {{ label: string, count: number, total: number, colorClass: string }} props
 * @returns {React.ReactElement}
 */
function BarRow({ label, count, total, colorClass }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 text-xs text-gray-600 dark:text-gray-400 capitalize shrink-0">
        {label}
      </span>
      <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
        <div
          className={`${colorClass} h-2 rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-xs text-right text-gray-500 dark:text-gray-400 shrink-0">
        {count}
      </span>
    </div>
  )
}

/**
 * Findings breakdown card with severity and agent bars.
 * Only rendered when there is at least one finding.
 * @param {{ stats: DashboardStats }} props
 * @returns {React.ReactElement|null}
 */
function FindingsChart({ stats }) {
  const bySeverity = stats.findings_by_severity ?? {}
  const byAgent = stats.findings_by_agent ?? {}

  const severityTotal = Object.values(bySeverity).reduce((a, b) => a + b, 0)
  const agentTotal = Object.values(byAgent).reduce((a, b) => a + b, 0)

  if (severityTotal === 0 && agentTotal === 0) return null

  const severityOrder = ['critical', 'high', 'medium', 'low', 'info']
  const agentOrder = ['security', 'performance', 'style', 'logic']

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
        Findings Breakdown
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {severityTotal > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
              By Severity
            </p>
            <div className="space-y-2">
              {severityOrder.map(key => (
                <BarRow
                  key={key}
                  label={key}
                  count={bySeverity[key] ?? 0}
                  total={severityTotal}
                  colorClass={SEVERITY_COLORS[key] ?? 'bg-gray-400'}
                />
              ))}
            </div>
          </div>
        )}
        {agentTotal > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
              By Agent
            </p>
            <div className="space-y-2">
              {agentOrder.map(key => (
                <BarRow
                  key={key}
                  label={key}
                  count={byAgent[key] ?? 0}
                  total={agentTotal}
                  colorClass={AGENT_COLORS[key] ?? 'bg-gray-400'}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Review filters
// ---------------------------------------------------------------------------

/** @type {Array<{ value: string, label: string }>} */
const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'analyzing', label: 'Analyzing' },
  { value: 'done', label: 'Done' },
  { value: 'error', label: 'Error' },
]

/**
 * Status filter bar above the reviews table.
 * @param {{ value: string, onChange: function(string): void }} props
 * @returns {React.ReactElement}
 */
function ReviewFilters({ value, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <label
        htmlFor="status-filter"
        className="text-sm text-gray-600 dark:text-gray-400"
      >
        Status:
      </label>
      <select
        id="status-filter"
        value={value}
        onChange={e => onChange(e.target.value)}
        className="text-sm rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 py-1 px-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {STATUS_OPTIONS.map(opt => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}

// ---------------------------------------------------------------------------
// New Review modal
// ---------------------------------------------------------------------------

const ALL_AGENTS = ['security', 'performance', 'style', 'logic']

/**
 * Modal dialog to create and immediately trigger a new review.
 * @param {{ onClose: function(): void, initialMode?: 'pr'|'diff' }} props
 * @returns {React.ReactElement}
 */
function NewReviewModal({ onClose, initialMode = 'pr' }) {
  const navigate = useNavigate()
  const { get, post } = useApi()
  const dialogRef = useRef(null)

  const [mode, setMode] = useState(initialMode)
  /** @type {[Repository[], function]} */
  const [repos, setRepos] = useState([])
  const [reposLoading, setReposLoading] = useState(true)
  const [repoId, setRepoId] = useState('')
  const [prNum, setPrNum] = useState('')
  const [diffTitle, setDiffTitle] = useState('')
  const [codeDiff, setCodeDiff] = useState('')
  const [agents, setAgents] = useState(ALL_AGENTS)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    setReposLoading(true)
    get('/repositories')
      .then(data => {
        const list = Array.isArray(data) ? data : (data.repositories ?? [])
        setRepos(list)
        if (list.length > 0) setRepoId(list[0].id)
      })
      .catch(() => setRepos([]))
      .finally(() => setReposLoading(false))
  }, [get])

  useEffect(() => {
    const firstInput = dialogRef.current?.querySelector('select, input, textarea, button')
    firstInput?.focus()

    const onKeyDown = event => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  function handleBackdropMouseDown(event) {
    if (event.target === event.currentTarget) onClose()
  }

  function handleDialogKeyDown(event) {
    if (event.key !== 'Tab') return
    const focusable = Array.from(
      dialogRef.current?.querySelectorAll('button, input, select, textarea, a[href]') ?? []
    ).filter(el => !el.disabled)
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  /**
   * Toggle an agent checkbox.
   * @param {string} name
   */
  function toggleAgent(name) {
    setAgents(prev =>
      prev.includes(name) ? prev.filter(a => a !== name) : [...prev, name]
    )
  }

  async function handleSubmit() {
    if (agents.length === 0) return
    if (mode === 'pr' && (!repoId || !prNum)) return
    if (mode === 'diff' && !codeDiff.trim()) {
      setError('Paste a git diff before starting the review')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const review = mode === 'diff'
        ? await post('/reviews/playground/diff', {
            title: diffTitle.trim() || 'Pasted diff review',
            code_diff: codeDiff,
            selected_agents: agents,
          })
        : await post('/reviews', {
            repo_id: repoId,
            github_pr_number: Number(prNum),
            selected_agents: agents,
          })
      if (mode === 'pr') {
        await post(`/reviews/${review.id}/analyze`, {})
      }
      navigate(`/reviews/${review.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create review')
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-review-title"
      onMouseDown={handleBackdropMouseDown}
    >
      <div
        ref={dialogRef}
        onKeyDown={handleDialogKeyDown}
        className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md border border-gray-200 dark:border-gray-700"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 id="new-review-title" className="text-base font-semibold text-gray-900 dark:text-white">
            New Review
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-2 rounded-lg bg-gray-100 dark:bg-gray-900 p-1">
            <button
              type="button"
              onClick={() => setMode('pr')}
              className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                mode === 'pr'
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Repository PR
            </button>
            <button
              type="button"
              onClick={() => setMode('diff')}
              className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                mode === 'diff'
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Paste diff review
            </button>
          </div>

          {mode === 'pr' ? (
            <>
              {/* Repository selector */}
              <div>
                <label
                  htmlFor="repo-select"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                >
                  Repository
                </label>
                {reposLoading ? (
                  <div className="h-9 bg-gray-100 dark:bg-gray-700 rounded animate-pulse" />
                ) : repos.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No repositories configured.{' '}
                    <Link to="/repositories" className="text-blue-600 dark:text-blue-400 hover:underline" onClick={onClose}>
                      Add one first.
                    </Link>
                  </p>
                ) : (
                  <select
                    id="repo-select"
                    value={repoId}
                    onChange={e => setRepoId(e.target.value)}
                    className="w-full text-sm rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 py-2 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {repos.map(r => (
                      <option key={r.id} value={r.id}>
                        {r.github_repo_owner}/{r.github_repo_name}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* PR number */}
              <div>
                <label
                  htmlFor="pr-number"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                >
                  PR Number
                </label>
                <input
                  id="pr-number"
                  type="number"
                  min="1"
                  required
                  value={prNum}
                  onChange={e => setPrNum(e.target.value)}
                  placeholder="e.g. 42"
                  className="w-full text-sm rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 py-2 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <label
                  htmlFor="diff-title"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                >
                  Title
                </label>
                <input
                  id="diff-title"
                  type="text"
                  maxLength={160}
                  value={diffTitle}
                  onChange={e => setDiffTitle(e.target.value)}
                  placeholder="Optional review title"
                  className="w-full text-sm rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 py-2 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label
                  htmlFor="code-diff"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                >
                  Git diff
                </label>
                <textarea
                  id="code-diff"
                  value={codeDiff}
                  onChange={e => setCodeDiff(e.target.value)}
                  placeholder="diff --git a/file.py b/file.py"
                  rows={8}
                  className="w-full text-sm font-mono rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 py-2 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
                />
              </div>
            </>
          )}

          {/* Agents */}
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Agents
            </p>
            <div className="grid grid-cols-2 gap-2">
              {ALL_AGENTS.map(name => (
                <label
                  key={name}
                  className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={agents.includes(name)}
                    onChange={() => toggleAgent(name)}
                    className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="capitalize">{name}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Error */}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={
              submitting ||
              agents.length === 0 ||
              (mode === 'pr' && (!repoId || !prNum)) ||
              (mode === 'diff' && !codeDiff.trim())
            }
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:opacity-50"
          >
            {submitting ? 'Starting...' : 'Start Review'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Format ISO date string to a human-readable relative time label.
 * @param {string} isoDate
 * @returns {string}
 */
function formatRelativeTime(isoDate) {
  const diff = Date.now() - new Date(isoDate).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

/**
 * @param {unknown} repositoriesResponse
 * @returns {Repository[]}
 */
function parseRepositories(repositoriesResponse) {
  if (Array.isArray(repositoriesResponse)) return repositoriesResponse
  if (
    repositoriesResponse &&
    typeof repositoriesResponse === 'object' &&
    Array.isArray(repositoriesResponse.repositories)
  ) {
    return repositoriesResponse.repositories
  }
  return []
}

/**
 * @param {{ complete: boolean, index: number }} props
 * @returns {React.ReactElement}
 */
function SetupStepMarker({ complete, index }) {
  const markerClass = complete
    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
    : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'

  return (
    <div className={`flex-shrink-0 w-7 h-7 rounded-full ${markerClass} flex items-center justify-center text-sm font-bold`}>
      {complete ? (
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="M5 10.5l3 3 7-7"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : (
        index
      )}
    </div>
  )
}

/**
 * @param {{ step: { label: string, description: React.ReactNode, complete: boolean }, index: number }} props
 * @returns {React.ReactElement}
 */
function SetupStep({ step, index }) {
  return (
    <div className="px-6 py-5 flex gap-4">
      <SetupStepMarker complete={step.complete} index={index} />
      <div className="min-w-0">
        <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">{step.label}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          {step.description}
        </p>
      </div>
    </div>
  )
}

/**
 * @param {{ stats: DashboardStats|null, setupStatus: SetupStatus }} props
 * @returns {React.ReactElement}
 */
function FirstRunChecklist({ stats, setupStatus }) {
  const hasFirstReview = Number(stats?.total_reviews ?? 0) > 0
  const steps = [
    {
      label: 'Account ready',
      complete: true,
      description: 'You are signed in and can create local reviews.',
    },
    {
      label: setupStatus.repositoriesConfigured ? 'Repository connected' : 'Connect a repository',
      complete: setupStatus.repositoriesConfigured,
      description: setupStatus.repositoriesConfigured ? (
        'A GitHub repository is connected for pull request reviews.'
      ) : (
        <>
          Connect a GitHub repository from{' '}
          <Link to="/repositories" className="text-blue-600 dark:text-blue-400 hover:underline">
            Repositories
          </Link>
          {' '}when you are ready for PR automation.
        </>
      ),
    },
    {
      label: setupStatus.llmConfigured ? 'LLM provider ready' : 'Configure an LLM provider',
      complete: setupStatus.llmConfigured,
      description: setupStatus.llmConfigured ? (
        'Claude, GPT, or local Ollama is available for review analysis.'
      ) : (
        <>
          Add Claude, GPT, or local Ollama in{' '}
          <Link to="/settings" className="text-blue-600 dark:text-blue-400 hover:underline">
            Settings
          </Link>
          {' '}for full analysis.
        </>
      ),
    },
    {
      label: hasFirstReview ? 'First review complete' : 'Run your first review',
      complete: hasFirstReview,
      description: hasFirstReview
        ? 'Your dashboard will show new review activity here.'
        : 'Use the demo review or paste a diff to see findings without GitHub setup.',
    },
  ]
  const completedCount = steps.filter(step => step.complete).length

  return (
    <div>
      <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900/60 border-b border-gray-100 dark:border-gray-700 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Setup progress</h2>
          {setupStatus.error && (
            <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
              Setup progress is temporarily unavailable. You can still start a local review.
            </p>
          )}
        </div>
        <span className="text-xs font-semibold text-gray-600 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full px-3 py-1 self-start sm:self-auto">
          {setupStatus.loading ? 'Checking setup' : `${completedCount}/4 complete`}
        </span>
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {steps.map((step, index) => (
          <SetupStep key={step.label} step={step} index={index + 1} />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------

/**
 * Main dashboard page showing aggregate stats and a recent reviews table.
 * @returns {React.ReactElement}
 */
export function Dashboard() {
  const navigate = useNavigate()
  /** @type {[DashboardStats|null, function]} */
  const [stats, setStats] = useState(null)
  /** @type {[ReviewSummary[], function]} */
  const [reviews, setReviews] = useState([])
  const [statsLoading, setStatsLoading] = useState(true)
  const [reviewsLoading, setReviewsLoading] = useState(true)
  const [statsError, setStatsError] = useState(null)
  const [reviewsError, setReviewsError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [modalMode, setModalMode] = useState(/** @type {'pr'|'diff'} */ ('pr'))
  const [playgroundLoading, setPlaygroundLoading] = useState(false)
  const [playgroundError, setPlaygroundError] = useState(null)
  /** @type {[SetupStatus, function]} */
  const [setupStatus, setSetupStatus] = useState({
    repositoriesConfigured: false,
    llmConfigured: false,
    loading: false,
    error: null,
  })

  const { get, post } = useApi()
  const showFirstRunOnboarding = !reviewsLoading && !reviewsError && reviews.length === 0 && statusFilter === ''

  const fetchStats = useCallback(async () => {
    setStatsLoading(true)
    setStatsError(null)
    try {
      const data = await get('/dashboard/stats')
      setStats(data)
    } catch (err) {
      setStatsError(err instanceof Error ? err.message : 'Failed to load stats')
    } finally {
      setStatsLoading(false)
    }
  }, [get])

  const fetchReviews = useCallback(async (filter) => {
    setReviewsLoading(true)
    setReviewsError(null)
    try {
      const qs = filter ? `&status=${filter}` : ''
      const data = await get(`/reviews?limit=20${qs}`)
      setReviews(data.reviews ?? [])
    } catch (err) {
      setReviewsError(err instanceof Error ? err.message : 'Failed to load reviews')
    } finally {
      setReviewsLoading(false)
    }
  }, [get])

  useEffect(() => {
    fetchStats()
    fetchReviews(statusFilter)
  }, [fetchStats, fetchReviews]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!showFirstRunOnboarding) return undefined

    let cancelled = false

    async function fetchSetupStatus() {
      setSetupStatus(current => ({ ...current, loading: true, error: null }))
      try {
        const repositoriesData = await get('/repositories')
        const settingsData = await get('/settings')
        if (cancelled) return

        const repositories = parseRepositories(repositoriesData)
        setSetupStatus({
          repositoriesConfigured: repositories.length > 0,
          llmConfigured: Boolean(
            settingsData?.api_key_claude_set ||
            settingsData?.api_key_gpt_set ||
            settingsData?.ollama_enabled
          ),
          loading: false,
          error: null,
        })
      } catch (err) {
        if (cancelled) return
        setSetupStatus({
          repositoriesConfigured: false,
          llmConfigured: false,
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load setup status',
        })
      }
    }

    fetchSetupStatus()

    return () => {
      cancelled = true
    }
  }, [showFirstRunOnboarding, get])

  /**
   * Handle status filter change: update state and refetch.
   * @param {string} value
   */
  function handleFilterChange(value) {
    setStatusFilter(value)
    fetchReviews(value)
  }

  function openReviewModal(mode = 'pr') {
    setModalMode(mode)
    setShowModal(true)
  }

  async function handleDemoReview() {
    setPlaygroundLoading(true)
    setPlaygroundError(null)
    try {
      const review = await post('/reviews/playground/demo', {
        selected_agents: ALL_AGENTS,
      })
      navigate(`/reviews/${review.id}`)
    } catch (err) {
      setPlaygroundError(err instanceof Error ? err.message : 'Failed to start demo review')
    } finally {
      setPlaygroundLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Overview of your code review activity
          </p>
        </div>
        <button
          onClick={() => openReviewModal('pr')}
          className="shrink-0 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors"
        >
          New Review
        </button>
      </div>

      {/* Stats row */}
      {statsLoading ? (
        <StatsSkeleton />
      ) : statsError ? (
        <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-4 text-sm text-red-700 dark:text-red-400">
          Failed to load stats: {statsError}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Reviews" value={stats?.total_reviews ?? 0} icon="📊" />
          <StatCard label="Reviews Today" value={stats?.reviews_today ?? 0} icon="📅" />
          <StatCard
            label="Tokens Used"
            value={`${((stats?.tokens_used_this_month ?? 0) / 1000).toFixed(1)}k`}
            icon="🔢"
          />
          <StatCard
            label="Cost This Month"
            value={`$${Number(stats?.estimated_cost_this_month ?? 0).toFixed(2)}`}
            icon="💰"
          />
        </div>
      )}

      {/* Findings chart */}
      {!statsLoading && !statsError && stats && (
        <FindingsChart stats={stats} />
      )}

      {/* Reviews section */}
      {reviewsLoading ? (
        <TableSkeleton />
      ) : reviewsError ? (
        <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-4 text-sm text-red-700 dark:text-red-400">
          Failed to load reviews: {reviewsError}
        </div>
      ) : reviews.length === 0 && statusFilter === '' ? (
        /* Empty state — only shown when not filtering */
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-6 pt-8 pb-6 text-center border-b border-gray-100 dark:border-gray-700">
            <svg className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" viewBox="0 0 48 48" fill="none" aria-hidden="true">
              <rect x="8" y="8" width="32" height="32" rx="4" stroke="currentColor" strokeWidth="2" />
              <path d="M16 20h16M16 28h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <p className="text-base font-semibold text-gray-800 dark:text-gray-200">No reviews yet</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Start with a local review now, then connect GitHub when you are ready.
            </p>
            <div className="mt-5 flex flex-col sm:flex-row justify-center gap-3">
              <button
                type="button"
                onClick={handleDemoReview}
                disabled={playgroundLoading}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
              >
                {playgroundLoading ? 'Creating demo...' : 'Try demo review'}
              </button>
              <button
                type="button"
                onClick={() => openReviewModal('diff')}
                disabled={playgroundLoading}
                className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm font-medium transition-colors disabled:opacity-50"
              >
                Paste diff
              </button>
            </div>
            {playgroundError && (
              <p className="mt-3 text-sm text-red-600 dark:text-red-400">{playgroundError}</p>
            )}
          </div>

          <FirstRunChecklist stats={stats} setupStatus={setupStatus} />
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Recent Reviews
            </h2>
            <ReviewFilters value={statusFilter} onChange={handleFilterChange} />
          </div>
          {reviews.length === 0 ? (
            <p className="px-6 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              No reviews match the selected filter.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-900">
                  <tr>
                    <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Repository</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">PR</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Status</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Findings</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Time</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {reviews.map(review => (
                    <tr
                      key={review.id}
                      className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <span className="font-medium text-gray-800 dark:text-gray-200">
                          {review.github_pr_title ?? `PR #${review.github_pr_number}`}
                        </span>
                        {review.status === 'error' && review.error_message && (
                          <p className="mt-0.5 text-xs text-red-600 dark:text-red-400 truncate max-w-xs">
                            {review.error_message.length > 60
                              ? `${review.error_message.slice(0, 60)}…`
                              : review.error_message}
                          </p>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-gray-600 dark:text-gray-400 font-mono">
                          #{review.github_pr_number}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={review.status} />
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span
                          className={`font-medium ${
                            review.total_findings > 0
                              ? 'text-yellow-600 dark:text-yellow-400'
                              : 'text-green-600 dark:text-green-400'
                          }`}
                        >
                          {review.total_findings}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {formatRelativeTime(review.created_at)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          to={`/reviews/${review.id}`}
                          className="text-blue-600 dark:text-blue-400 hover:underline text-xs font-medium"
                        >
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* New Review modal */}
      {showModal && (
        <NewReviewModal
          initialMode={modalMode}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  )
}
