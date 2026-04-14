import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '@/hooks/useApi.js'
import { StatusBadge } from '@/components/StatusBadge.jsx'

/**
 * @typedef {Object} DashboardStats
 * @property {number} totalReviews
 * @property {number} reviewsToday
 * @property {number} tokenUsed
 * @property {number} estimatedCost
 */

/**
 * @typedef {Object} ReviewSummary
 * @property {string} id
 * @property {string} repo
 * @property {number} prNumber
 * @property {'pending'|'analyzing'|'done'|'error'} status
 * @property {number} totalFindings
 * @property {string} createdAt
 */

/**
 * Single summary stat card.
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

/**
 * Skeleton placeholder for the stats row while data loads.
 * @returns {React.ReactElement}
 */
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

/**
 * Skeleton placeholder for the reviews table while data loads.
 * @returns {React.ReactElement}
 */
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

  const fetchReviews = useCallback(async () => {
    setReviewsLoading(true)
    setReviewsError(null)
    try {
      const data = await get('/reviews?limit=20')
      setReviews(data.reviews ?? [])
    } catch (err) {
      setReviewsError(err instanceof Error ? err.message : 'Failed to load reviews')
    } finally {
      setReviewsLoading(false)
    }
  }, [get])

  useEffect(() => {
    fetchStats()
    fetchReviews()
  }, [fetchStats, fetchReviews])

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Overview of your code review activity
        </p>
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

      {/* Recent reviews table */}
      {reviewsLoading ? (
        <TableSkeleton />
      ) : reviewsError ? (
        <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-4 text-sm text-red-700 dark:text-red-400">
          Failed to load reviews: {reviewsError}
        </div>
      ) : reviews.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-6 pt-8 pb-4 text-center border-b border-gray-100 dark:border-gray-700">
            <svg className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" viewBox="0 0 48 48" fill="none" aria-hidden="true">
              <rect x="8" y="8" width="32" height="32" rx="4" stroke="currentColor" strokeWidth="2" />
              <path d="M16 20h16M16 28h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <p className="text-base font-semibold text-gray-800 dark:text-gray-200">No reviews yet</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Follow the steps below to get your first automated code review.</p>
          </div>

          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {/* Step 1 */}
            <div className="px-6 py-5 flex gap-4">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400 flex items-center justify-center text-sm font-bold">1</div>
              <div>
                <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">Configure an LLM provider</p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                  Go to <Link to="/settings" className="text-blue-600 dark:text-blue-400 hover:underline">Settings</Link> and add an API key for Claude or GPT, or set up a local Ollama instance.
                </p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="px-6 py-5 flex gap-4">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400 flex items-center justify-center text-sm font-bold">2</div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">Add a GitHub Webhook</p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5 mb-2">
                  In your GitHub repository go to <strong className="text-gray-700 dark:text-gray-300">Settings → Webhooks → Add webhook</strong> and fill in:
                </p>
                <ul className="text-sm text-gray-500 dark:text-gray-400 space-y-1 ml-3 list-disc">
                  <li><span className="font-medium text-gray-700 dark:text-gray-300">Payload URL:</span>{' '}
                    <code className="text-xs bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded font-mono break-all">
                      {window.location.origin}/api/github/webhook
                    </code>
                  </li>
                  <li><span className="font-medium text-gray-700 dark:text-gray-300">Content type:</span> <code className="text-xs bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">application/json</code></li>
                  <li><span className="font-medium text-gray-700 dark:text-gray-300">Events:</span> select <em>Pull requests</em></li>
                </ul>
              </div>
            </div>

            {/* Step 3 */}
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
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Recent Reviews
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">
                    Repository
                  </th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">
                    PR
                  </th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">
                    Status
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500 dark:text-gray-400">
                    Findings
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500 dark:text-gray-400">
                    Time
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500 dark:text-gray-400">
                    Actions
                  </th>
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
        </div>
      )}
    </div>
  )
}
