import { useState, useEffect, useCallback } from 'react'
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
 * @property {string} owner
 * @property {string} name
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
 * @param {{ onClose: function(): void }} props
 * @returns {React.ReactElement}
 */
function NewReviewModal({ onClose }) {
  const navigate = useNavigate()
  const { get, post } = useApi()

  /** @type {[Repository[], function]} */
  const [repos, setRepos] = useState([])
  const [reposLoading, setReposLoading] = useState(true)
  const [repoId, setRepoId] = useState('')
  const [prNum, setPrNum] = useState('')
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
    if (!repoId || !prNum || agents.length === 0) return
    setSubmitting(true)
    setError(null)
    try {
      const review = await post('/reviews', {
        repo_id: repoId,
        github_pr_number: Number(prNum),
        selected_agents: agents,
      })
      await post(`/reviews/${review.id}/analyze`, {})
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
      aria-label="New Review"
    >
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md border border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
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
                    {r.owner}/{r.name}
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
            disabled={submitting || !repoId || !prNum || agents.length === 0}
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

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------

/**
 * Main dashboard page showing aggregate stats and a recent reviews table.
 * @returns {React.ReactElement}
 */
export function Dashboard() {
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

  const { get } = useApi()

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

  /**
   * Handle status filter change: update state and refetch.
   * @param {string} value
   */
  function handleFilterChange(value) {
    setStatusFilter(value)
    fetchReviews(value)
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
          onClick={() => setShowModal(true)}
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
          <div className="px-6 pt-8 pb-4 text-center border-b border-gray-100 dark:border-gray-700">
            <svg className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" viewBox="0 0 48 48" fill="none" aria-hidden="true">
              <rect x="8" y="8" width="32" height="32" rx="4" stroke="currentColor" strokeWidth="2" />
              <path d="M16 20h16M16 28h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <p className="text-base font-semibold text-gray-800 dark:text-gray-200">No reviews yet</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Follow the steps below to get your first automated code review.
            </p>
          </div>

          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            <div className="px-6 py-5 flex gap-4">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400 flex items-center justify-center text-sm font-bold">1</div>
              <div>
                <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">Configure an LLM provider</p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                  Go to{' '}
                  <Link to="/settings" className="text-blue-600 dark:text-blue-400 hover:underline">Settings</Link>
                  {' '}and add an API key for Claude or GPT, or set up a local Ollama instance.
                </p>
              </div>
            </div>
            <div className="px-6 py-5 flex gap-4">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400 flex items-center justify-center text-sm font-bold">2</div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">Add your repository</p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                  Go to the{' '}
                  <a href="/repositories" className="text-blue-600 dark:text-blue-400 hover:underline">
                    Add your repository
                  </a>
                  {' '}page to connect a GitHub repo and get the webhook URL to configure in GitHub.
                </p>
              </div>
            </div>
            <div className="px-6 py-5 flex gap-4">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400 flex items-center justify-center text-sm font-bold">3</div>
              <div>
                <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">Open a Pull Request</p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                  Create or update a PR in the connected repository. The agent will automatically analyze it and post a comment with findings.
                </p>
              </div>
            </div>
          </div>
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
                      className="hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
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
      {showModal && <NewReviewModal onClose={() => setShowModal(false)} />}
    </div>
  )
}
