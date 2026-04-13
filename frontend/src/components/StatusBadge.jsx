/**
 * @typedef {'pending'|'analyzing'|'done'|'error'} ReviewStatus
 */

/** @type {Record<string, string>} */
const STATUS_CLASSES = {
  pending: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  analyzing: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  done: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  error: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
}

/** @type {Record<string, string>} */
const STATUS_LABELS = {
  pending: 'Pending',
  analyzing: 'Analyzing',
  done: 'Done',
  error: 'Error'
}

/**
 * Colored status badge with optional animated spinner for "analyzing" state.
 *
 * @param {{ status: string, className?: string }} props
 * @returns {React.ReactElement}
 */
export function StatusBadge({ status, className = '' }) {
  const colorClass = STATUS_CLASSES[status] ?? STATUS_CLASSES.pending
  const label = STATUS_LABELS[status] ?? status

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${colorClass} ${className}`}
    >
      {status === 'analyzing' && (
        <span
          className="w-2.5 h-2.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
          aria-hidden="true"
        />
      )}
      {status === 'done' && (
        <svg
          className="w-3 h-3"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M2 6l3 3 5-5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
      {status === 'error' && (
        <svg
          className="w-3 h-3"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M3 3l6 6M9 3l-6 6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      )}
      {label}
    </span>
  )
}
