import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import { App } from './App.jsx'
import './index.css'

if (import.meta.env.VITE_SENTRY_DSN && import.meta.env.MODE !== 'test') {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0.2),
  })
}

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Root element #root not found in DOM')
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
)
