import { useState, useEffect, useCallback } from 'react'
import { useApi } from '@/hooks/useApi.js'
import { absoluteApiUrl } from '@/config.js'

/**
 * @typedef {Object} Repository
 * @property {string} id
 * @property {string} github_repo_owner
 * @property {string} github_repo_name
 * @property {string} github_repo_url
 * @property {number|null} github_installation_id
 * @property {boolean} enabled
 * @property {string} created_at
 */

/**
 * Format ISO date to a short locale date string.
 * @param {string} isoDate
 * @returns {string}
 */
function formatDate(isoDate) {
  return new Date(isoDate).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

/**
 * Copyable code block for the webhook URL.
 * @param {{ value: string }} props
 * @returns {React.ReactElement}
 */
function CopyableCode({ value }) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState(null)

  /**
   * Copy text to clipboard and show brief confirmation.
   * @returns {void}
   */
  function handleCopy() {
    setCopyError(null)
    navigator.clipboard.writeText(value)
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1800)
      })
      .catch(() => setCopyError('Copy failed'))
  }

  return (
    <span className="inline-flex items-center gap-2 flex-wrap">
      <code className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 px-2 py-1 rounded font-mono break-all">
        {value}
      </code>
      <button
        type="button"
        onClick={handleCopy}
        className="text-xs text-blue-600 dark:text-blue-400 hover:underline shrink-0"
      >
        {copied ? 'Copied!' : 'Copy'}
      </button>
      {copyError && <span className="text-xs text-red-500">{copyError}</span>}
    </span>
  )
}

/**
 * Informational callout explaining how to configure the GitHub webhook.
 * @returns {React.ReactElement}
 */
function WebhookInfoPanel() {
  const webhookUrl = absoluteApiUrl('/github/webhook')

  return (
    <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-5 space-y-3">
      <h2 className="text-sm font-semibold text-blue-800 dark:text-blue-300">
        GitHub Webhook Setup
      </h2>
      <ul className="space-y-2 text-sm text-blue-700 dark:text-blue-300">
        <li>
          <span className="font-medium">Webhook URL:</span>{' '}
          <CopyableCode value={webhookUrl} />
        </li>
        <li>
          <span className="font-medium">Webhook secret:</span>{' '}
          Use the <code className="text-xs bg-blue-100 dark:bg-blue-900 px-1.5 py-0.5 rounded font-mono">GITHUB_WEBHOOK_SECRET</code> value from your backend environment variables.
        </li>
        <li>
          Add this webhook in your GitHub repo under{' '}
          <strong className="text-blue-800 dark:text-blue-200">Settings &rarr; Webhooks</strong>.
          Select <em>Pull requests</em> events.
        </li>
      </ul>
    </div>
  )
}

/**
 * Inline form to add a new repository.
 * @param {{ onAdded: () => void }} props
 * @returns {React.ReactElement}
 */
function AddRepoForm({ onAdded }) {
  const [owner, setOwner] = useState('')
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)

  const { post } = useApi()

  /**
   * Handle form submission.
   * @param {React.FormEvent<HTMLFormElement>} e
   * @returns {Promise<void>}
   */
  async function handleSubmit(e) {
    e.preventDefault()
    if (!owner.trim() || !name.trim()) return

    setSubmitting(true)
    setFormError(null)
    try {
      await post('/repositories', {
        github_repo_owner: owner.trim(),
        github_repo_name: name.trim()
      })
      setOwner('')
      setName('')
      onAdded()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to add repository'
      setFormError(msg.includes('409') || msg.toLowerCase().includes('already') ? 'Already added' : msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5"
    >
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
        Add Repository
      </h2>
      <div className="flex flex-col sm:flex-row gap-3">
        <label htmlFor="repo-owner" className="sr-only">GitHub owner</label>
        <input
          id="repo-owner"
          type="text"
          placeholder="Owner (e.g. octocat)"
          value={owner}
          onChange={e => setOwner(e.target.value)}
          required
          className="flex-1 px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
        />
        <label htmlFor="repo-name" className="sr-only">Repository name</label>
        <input
          id="repo-name"
          type="text"
          placeholder="Repo name (e.g. my-project)"
          value={name}
          onChange={e => setName(e.target.value)}
          required
          className="flex-1 px-3 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
        />
        <button
          type="submit"
          disabled={submitting}
          className="px-4 py-2 text-sm font-medium rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors shrink-0"
        >
          {submitting ? 'Adding...' : 'Add'}
        </button>
      </div>
      {formError && (
        <p className="mt-2 text-sm text-red-600 dark:text-red-400">{formError}</p>
      )}
    </form>
  )
}

/**
 * Single row in the repositories table.
 * @param {{ repo: Repository, onRefresh: () => void }} props
 * @returns {React.ReactElement}
 */
function RepoRow({ repo, onRefresh }) {
  const [toggling, setToggling] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [rowError, setRowError] = useState(null)

  const { patch, del } = useApi()

  /**
   * Toggle the enabled state of this repository.
   * @returns {Promise<void>}
   */
  async function handleToggle() {
    setToggling(true)
    setRowError(null)
    try {
      await patch(`/repositories/${repo.id}`, { enabled: !repo.enabled })
      await onRefresh()
    } catch (err) {
      setRowError(err instanceof Error ? err.message : 'Failed to update repository')
    } finally {
      setToggling(false)
    }
  }

  /**
   * Delete this repository after confirmation.
   * @returns {Promise<void>}
   */
  async function handleDelete() {
    if (!window.confirm(`Remove ${repo.github_repo_owner}/${repo.github_repo_name}? This cannot be undone.`)) return
    setDeleting(true)
    setRowError(null)
    try {
      await del(`/repositories/${repo.id}`)
      await onRefresh()
    } catch (err) {
      setRowError(err instanceof Error ? err.message : 'Failed to remove repository')
    } finally {
      setDeleting(false)
    }
  }

  const repoFullName = `${repo.github_repo_owner}/${repo.github_repo_name}`
  const repoUrl = repo.github_repo_url || `https://github.com/${repoFullName}`

  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
      <td className="py-3 px-4">
        <a
          href={repoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-blue-600 dark:text-blue-400 hover:underline font-mono text-sm"
        >
          {repoFullName}
        </a>
      </td>
      <td className="py-3 px-4">
        {repo.enabled ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
            Enabled
          </span>
        ) : (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">
            Disabled
          </span>
        )}
      </td>
      <td className="py-3 px-4 text-sm text-gray-500 dark:text-gray-400 font-mono">
        {repo.github_installation_id ?? <span className="text-gray-400 dark:text-gray-600">&mdash;</span>}
      </td>
      <td className="py-3 px-4 text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">
        {formatDate(repo.created_at)}
      </td>
      <td className="py-3 px-4 text-right">
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={handleToggle}
            disabled={toggling}
            className="text-xs px-2.5 py-1 rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-blue-500 hover:text-blue-600 dark:hover:border-blue-400 dark:hover:text-blue-400 disabled:opacity-50 transition-colors"
          >
            {toggling ? '...' : repo.enabled ? 'Disable' : 'Enable'}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="text-xs px-2.5 py-1 rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-red-500 hover:text-red-600 dark:hover:border-red-400 dark:hover:text-red-400 disabled:opacity-50 transition-colors"
          >
            {deleting ? '...' : 'Remove'}
          </button>
        </div>
        {rowError && (
          <p className="mt-1 text-xs text-red-600 dark:text-red-400 text-right">
            {rowError}
          </p>
        )}
      </td>
    </tr>
  )
}

/**
 * Repositories management page.
 * Allows users to list, add, toggle, and remove connected GitHub repositories.
 * @returns {React.ReactElement}
 */
export function Repositories() {
  /** @type {[Repository[], function]} */
  const [repos, setRepos] = useState([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)

  const { get } = useApi()

  const fetchRepos = useCallback(async () => {
    setLoading(true)
    setFetchError(null)
    try {
      const data = await get('/repositories')
      setRepos(Array.isArray(data) ? data : (data.repositories ?? []))
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : 'Failed to load repositories')
    } finally {
      setLoading(false)
    }
  }, [get])

  useEffect(() => {
    fetchRepos()
  }, [fetchRepos])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Repositories</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Manage GitHub repositories connected to the code review agent.
        </p>
      </div>

      <WebhookInfoPanel />

      <AddRepoForm onAdded={fetchRepos} />

      {/* Repository list */}
      {loading ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 flex justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-gray-500 dark:text-gray-400">Loading repositories...</span>
          </div>
        </div>
      ) : fetchError ? (
        <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-4 text-sm text-red-700 dark:text-red-400">
          Failed to load repositories: {fetchError}
        </div>
      ) : repos.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-10 text-center">
          <svg
            className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M9 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-4M9 3l6 6M9 3v6h6"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">No repositories yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
            Add a repository above to start receiving automated code reviews.
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Connected Repositories ({repos.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Repo</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Status</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Installation ID</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Added</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500 dark:text-gray-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {repos.map(repo => (
                  <RepoRow key={repo.id} repo={repo} onRefresh={fetchRepos} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
