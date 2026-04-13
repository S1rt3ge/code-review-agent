/**
 * @typedef {'pending'|'running'|'done'|'error'} AgentStatusValue
 */

/** @type {Record<AgentStatusValue, string>} */
const AGENT_LABEL_MAP = {
  security: 'Security',
  performance: 'Performance',
  style: 'Style',
  logic: 'Logic'
}

/**
 * Displays a single agent's name alongside a status indicator icon.
 * Shows an animated spinner for "running", a checkmark for "done",
 * an X for "error", and a muted dot for "pending".
 *
 * @param {{ agentName: string, status: AgentStatusValue }} props
 * @returns {React.ReactElement}
 */
export function AgentStatus({ agentName, status }) {
  const displayName = AGENT_LABEL_MAP[agentName] ?? agentName

  return (
    <div className="flex items-center gap-2 py-1.5">
      {/* Status icon */}
      <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center" aria-hidden="true">
        {status === 'running' && (
          <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        )}
        {status === 'done' && (
          <svg className="w-4 h-4 text-green-500" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
            <path
              d="M5 8l2 2 4-4"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
        {status === 'error' && (
          <svg className="w-4 h-4 text-red-500" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
            <path
              d="M5.5 5.5l5 5M10.5 5.5l-5 5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        )}
        {status === 'pending' && (
          <span className="w-3 h-3 rounded-full bg-gray-300 dark:bg-gray-600" />
        )}
      </span>

      {/* Agent name */}
      <span
        className={`text-sm font-medium ${
          status === 'done'
            ? 'text-green-700 dark:text-green-400'
            : status === 'error'
            ? 'text-red-700 dark:text-red-400'
            : status === 'running'
            ? 'text-blue-700 dark:text-blue-400'
            : 'text-gray-500 dark:text-gray-400'
        }`}
      >
        {displayName}
      </span>

      {/* Status label */}
      <span className="ml-auto text-xs text-gray-400 dark:text-gray-500 capitalize">
        {status}
      </span>
    </div>
  )
}
