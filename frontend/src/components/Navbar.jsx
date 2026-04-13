import { NavLink } from 'react-router-dom'
import { useUiStore } from '@/store/index.js'

/**
 * Navigation link item descriptor.
 * @typedef {Object} NavItem
 * @property {string} to - Route path
 * @property {string} label - Display label
 */

/** @type {NavItem[]} */
const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/settings', label: 'Settings' }
]

/**
 * Top navigation bar with route links and a dark mode toggle.
 * Active link is visually highlighted via React Router's NavLink.
 *
 * @returns {React.ReactElement}
 */
export function Navbar() {
  const darkMode = useUiStore(state => state.darkMode)
  const toggleDarkMode = useUiStore(state => state.toggleDarkMode)

  return (
    <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand */}
          <div className="flex items-center gap-8">
            <span className="text-lg font-bold text-gray-900 dark:text-white tracking-tight">
              Code Review Agent
            </span>

            {/* Navigation links */}
            <nav className="hidden sm:flex items-center gap-1" aria-label="Main navigation">
              {NAV_ITEMS.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-400'
                        : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-white'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Dark mode toggle */}
          <button
            type="button"
            onClick={toggleDarkMode}
            aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            className="p-2 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            {darkMode ? (
              /* Sun icon */
              <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path
                  fillRule="evenodd"
                  d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4.22 1.78a1 1 0 011.42 1.42l-.71.7a1 1 0 11-1.41-1.41l.7-.71zm2.78 5.22a1 1 0 110 2h-1a1 1 0 110-2h1zM4.22 15.78a1 1 0 001.42-1.42l-.71-.7a1 1 0 10-1.41 1.41l.7.71zM10 16a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zm-5.78-1.78a1 1 0 01-1.42-1.42l.71-.7a1 1 0 111.41 1.41l-.7.71zM4 10a1 1 0 110-2H3a1 1 0 110 2h1zm11.78-4.22a1 1 0 00-1.42 1.42l.71.7a1 1 0 101.41-1.41l-.7-.71zM10 6a4 4 0 100 8 4 4 0 000-8z"
                  clipRule="evenodd"
                />
              </svg>
            ) : (
              /* Moon icon */
              <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
              </svg>
            )}
          </button>
        </div>

        {/* Mobile navigation */}
        <nav className="flex sm:hidden items-center gap-1 pb-2" aria-label="Mobile navigation">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-400'
                    : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
