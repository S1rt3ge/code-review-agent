import '@testing-library/jest-dom'

// Suppress React Router v6 future-flag deprecation warnings in test output
const originalWarn = console.warn.bind(console)
console.warn = (...args) => {
  if (typeof args[0] === 'string' && args[0].includes('React Router Future Flag Warning')) return
  originalWarn(...args)
}
