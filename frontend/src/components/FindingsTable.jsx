import { useMemo } from 'react'

/**
 * @typedef {'critical'|'high'|'medium'|'low'|'info'} Severity
 */

/**
 * @typedef {Object} Finding
 * @property {string} id
 * @property {string} agentName
 * @property {Severity} severity
 * @property {string} filePath
 * @property {number} lineNumber
 * @property {string} message
 * @property {string} [suggestion]
 */

/** @type {Record<Severity, number>} */
const SEVERITY_ORDER = { critical: 0, high: 1, warning: 1, medium: 2, low: 3, info: 4 }

/** @type {Record<Severity, string>} */
const SEVERITY_BADGE_CLASSES = {
  critical: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  high:     'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  medium:   'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  low:      'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  info:     'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
}

/**
 * Truncate a file path to the last two path segments for compact display.
 * @param {string} filePath
 * @returns {string}
 */
function truncatePath(filePath) {
  const parts = filePath.replace(/\\/g, '/').split('/')
  return parts.length > 2 ? `.../${parts.slice(-2).join('/')}` : filePath
}

/**
 * Table displaying code review findings sorted by severity (critical first).
 * Supports click-to-select and shows an empty state when there are no findings.
 *
 * @param {{ findings: Finding[], onSelectFinding?: (finding: Finding) => void }} props
 * @returns {React.ReactElement}
 */
export function FindingsTable({ findings, onSelectFinding }) {
  const sorted = useMemo(
    () =>
      [...findings].sort(
        (a, b) =>
          (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99)
      ),
    [findings]
  )

  if (findings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <svg
          className="w-12 h-12 text-green-400 mb-3"
          viewBox="0 0 48 48"
          fill="none"
          aria-hidden="true"
        >
          <circle cx="24" cy="24" r="22" stroke="currentColor" strokeWidth="2" />
          <path
            d="M14 24l7 7 13-14"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <p className="text-base font-medium text-gray-700 dark:text-gray-300">No findings</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          No issues detected. Great code!
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
          <tr>
            <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">
              Severity
            </th>
            <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">
              Agent
            </th>
            <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400">
              File
            </th>
            <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">
              Line
            </th>
            <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400">
              Message
            </th>
            <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400">
              Suggestion
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {sorted.map(finding => (
            <tr
              key={finding.id}
              onClick={() => onSelectFinding?.(finding)}
              className={`transition-colors ${
                onSelectFinding
                  ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800'
                  : ''
              }`}
            >
              <td className="py-3 px-4 whitespace-nowrap">
                <span
                  className={`inline-block px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${
                    SEVERITY_BADGE_CLASSES[finding.severity] ?? ''
                  }`}
                >
                  {finding.severity}
                </span>
              </td>
              <td className="py-3 px-4 whitespace-nowrap">
                <span className="text-xs font-mono text-gray-600 dark:text-gray-400">
                  {finding.agentName}
                </span>
              </td>
              <td className="py-3 px-4">
                <span
                  className="text-xs font-mono text-gray-600 dark:text-gray-400"
                  title={finding.filePath}
                >
                  {truncatePath(finding.filePath)}
                </span>
              </td>
              <td className="py-3 px-4 whitespace-nowrap">
                <span className="text-xs font-mono text-gray-500 dark:text-gray-500">
                  {finding.lineNumber}
                </span>
              </td>
              <td className="py-3 px-4">
                <span className="text-sm text-gray-800 dark:text-gray-200">
                  {finding.message}
                </span>
              </td>
              <td className="py-3 px-4">
                {finding.suggestion ? (
                  <span className="text-xs text-gray-500 dark:text-gray-400 italic">
                    {finding.suggestion}
                  </span>
                ) : (
                  <span className="text-xs text-gray-300 dark:text-gray-600">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
