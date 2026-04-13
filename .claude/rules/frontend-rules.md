# Frontend Rules

Apply these rules to all React/TypeScript code (glob: `frontend/src/**/*.{ts,tsx}`)

## React Rules

**Functional components only:**
```typescript
// GOOD
export function Dashboard() {
  const [state, setState] = useState(...)
  return <div>...</div>
}

// BAD - class components
class Dashboard extends React.Component {
  ...
}
```

**Hooks usage:**
- useState for local state
- useEffect for side effects
- useCallback for stable callbacks
- useMemo for expensive computations
- Custom hooks for reusable logic

**Max component file size:** 250 lines
- Longer → extract smaller components
- Each component does ONE thing

**Props:**
```typescript
// GOOD - interface for props
interface CardProps {
  title: string
  count: number
  onClick?: (id: string) => void
}

export function Card({ title, count, onClick }: CardProps) {
  return <div onClick={() => onClick?.(title)}>...</div>
}

// BAD - no typing
export function Card(props) {
  ...
}
```

**Keys in lists:**
```typescript
// GOOD
{items.map(item => <Item key={item.id} {...item} />)}

// BAD
{items.map((item, index) => <Item key={index} {...item} />)}
```

**Conditional rendering:**
```typescript
// GOOD
{isLoading && <Spinner />}
{error && <ErrorMessage error={error} />}
{data && <DataDisplay data={data} />}

// BAD
{isLoading === true ? <Spinner /> : <div></div>}
{data !== null && data !== undefined ? <DataDisplay data={data} /> : <Empty />}
```

## TypeScript Rules

**Strict mode enabled** in tsconfig.json:
```json
{
  "strict": true,
  "strictNullChecks": true,
  "strictFunctionTypes": true
}
```

**Type all functions:**
```typescript
// GOOD
async function fetchReviews(userId: string): Promise<Review[]> {
  ...
}

// BAD
async function fetchReviews(userId) {
  ...
}
```

**Union types for options:**
```typescript
// GOOD
type Severity = 'critical' | 'warning' | 'info'

interface Finding {
  severity: Severity
}

// BAD
interface Finding {
  severity: string
}
```

**Use unknown, not any:**
```typescript
// GOOD
function parse(data: unknown): ParsedData {
  if (typeof data === 'object' && data !== null) {
    return data as ParsedData
  }
  throw new Error('Invalid data')
}

// BAD
function parse(data: any): any {
  return data
}
```

**Generics for reusable utilities:**
```typescript
// GOOD
function useApi<T>(endpoint: string): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  ...
  return { data, loading, error }
}

// BAD
function useApi(endpoint: string): any {
  ...
}
```

## Styling Rules

**TailwindCSS ONLY**
- No CSS files (./styles.css is banned)
- No inline styles (<div style={{color: 'red'}}>)
- No CSS-in-JS (styled-components, etc.)
- Only Tailwind utility classes

**Dark mode:**
```typescript
// GOOD - dark: prefix for dark mode
<div className="bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
  Content
</div>

// BAD - separate CSS file
// .dark .content { color: white; }
```

**Responsive design:**
```typescript
// GOOD - mobile-first
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {items.map(item => <Card key={item.id} {...item} />)}
</div>

// BAD - missing responsive
<div className="grid grid-cols-3 gap-4">
  ...
</div>
```

**Class composition:**
```typescript
// GOOD - compose classes
const cardClass = "rounded-lg border shadow-sm p-4 dark:border-gray-700"
<div className={cardClass}>...</div>

// BAD - inline long class strings
<div className="rounded-lg border border-gray-200 shadow-sm p-4 dark:border-gray-700 dark:bg-gray-800">...</div>
```

**Tailwind classes only:**
```
Allowed: p-4, m-2, bg-white, text-gray-900, flex, grid, etc.
Banned: custom-padding, my-special-class, etc.
```

## State Management

**Zustand stores:**
```typescript
// GOOD - clear, typed store
interface SettingsStore {
  apiKeyClaude: string
  selectedAgents: string[]
  updateKey: (key: string) => void
}

export const useSettingsStore = create<SettingsStore>(set => ({
  apiKeyClaude: '',
  selectedAgents: [],
  updateKey: (key) => set({ apiKeyClaude: key })
}))

// Usage in component
const { apiKeyClaude, updateKey } = useSettingsStore()
```

**Separation:**
- Global state (settings, auth) → Zustand store
- Local state (form inputs, UI toggles) → useState
- Derived state → useMemo

**No Redux/Redux Toolkit**
- Zustand simpler for this project
- Overkill for small state

## API Integration

**All API calls through useApi hook:**
```typescript
// GOOD
const { get, post } = useApi()

async function handleSubmit(data: FormData) {
  try {
    const result = await post('/reviews', data)
    setSuccess(true)
  } catch (error) {
    setError(error.message)
  }
}

// BAD - direct fetch
const response = await fetch('/api/reviews', {
  method: 'POST',
  body: JSON.stringify(data)
})
```

**Loading + error states:**
```typescript
const [loading, setLoading] = useState(false)
const [error, setError] = useState<string | null>(null)

useEffect(() => {
  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get('/reviews')
      setData(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }
  load()
}, [api])

if (loading) return <Spinner />
if (error) return <ErrorMessage message={error} />
return <ReviewList reviews={data} />
```

## File Organization

**Pages (top-level routes):**
```
frontend/src/pages/
├── Dashboard.tsx      # Main dashboard
├── ReviewDetail.tsx   # Single review view
└── Settings.tsx       # User settings
```

**Components (reusable):**
```
frontend/src/components/
├── FindingsTable.tsx     # Tabular display
├── AgentStatus.tsx       # Status indicator
├── LLMSelector.tsx       # Radio buttons
├── ApiKeyInput.tsx       # Form input
├── ResultCard.tsx        # Single finding
├── LoadingSpinner.tsx    # Loading state
└── ErrorMessage.tsx      # Error display
```

**Hooks (logic):**
```
frontend/src/hooks/
├── useApi.ts          # API wrapper
├── useSettings.ts     # Settings hook
├── useWebsocket.ts    # WebSocket connection
└── useFetch.ts        # Generic data fetching
```

**Store:**
```
frontend/src/store/
└── index.ts           # All Zustand stores
```

**Types:**
```
frontend/src/types/
└── index.ts           # All TypeScript interfaces/types
```

## Testing

**Component test location:** `src/components/__tests__/Component.test.tsx`

**Test file naming:**
```typescript
// Component
export function Dashboard() { ... }
// Test
describe('Dashboard', () => { ... })
```

**Mocking fetch:**
```typescript
import { beforeEach, vi } from 'vitest'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ data: [] })
    })
  ))
})
```

**Snapshot tests for components:**
```typescript
it('should match snapshot', () => {
  const { container } = render(<Card title="Test" />)
  expect(container).toMatchSnapshot()
})
```

## Accessibility

**Semantic HTML:**
```typescript
// GOOD
<button onClick={handleClick}>Save</button>
<a href="/reviews">Go to reviews</a>

// BAD
<div onClick={handleClick}>Save</div>
<div onClick={() => navigate('/reviews')}>Go to reviews</div>
```

**Alt text for images:**
```typescript
// GOOD
<img src="icon.svg" alt="Security alert icon" />

// BAD
<img src="icon.svg" />
```

**ARIA labels for icons/buttons:**
```typescript
// GOOD
<button aria-label="Close dialog" onClick={onClose}>✕</button>

// BAD
<button onClick={onClose}>✕</button>
```

**Color contrast:**
- Foreground/background should have 4.5:1 contrast for text
- Tailwind colors (text-gray-900, dark:text-white) usually safe

## Naming Conventions

**Variables:** camelCase
```typescript
const userName = "alex"
const isActive = true
const maxRetries = 3
```

**Functions:** camelCase
```typescript
function getUserSettings() { ... }
const fetchReviews = async () => { ... }
```

**Components:** PascalCase
```typescript
function Dashboard() { ... }
export function FindingsTable(props) { ... }
```

**Constants:** UPPER_SNAKE_CASE (if truly constant)
```typescript
const MAX_RETRIES = 3
const API_BASE_URL = "http://localhost:8000"
```

**Boolean variables:** prefix with is/has/can
```typescript
const isLoading = true
const hasError = false
const canEditReview = true
```

## Performance

**Memoization:**
```typescript
// GOOD - memoize expensive computation
const sortedFindings = useMemo(() => {
  return [...findings].sort((a, b) => 
    severityOrder[a.severity] - severityOrder[b.severity]
  )
}, [findings])

// GOOD - stable callback
const handleSelectFinding = useCallback((finding: Finding) => {
  onSelect(finding)
}, [onSelect])
```

**Lazy loading:**
```typescript
// GOOD - code splitting
const Settings = lazy(() => import('./pages/Settings'))

function App() {
  return (
    <Suspense fallback={<LoadingPage />}>
      <Routes>
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Suspense>
  )
}
```

**No unnecessary renders:**
- Don't pass object literals as props ({theme: {dark: true}})
- Extract to constants or useMemo
- Memoize list items if expensive

## Imports

**Import order:**
```typescript
// 1. React
import { useState, useEffect } from 'react'

// 2. Third-party
import { create } from 'zustand'
import { render, screen } from '@testing-library/react'

// 3. Local
import { useApi } from '@/hooks/useApi'
import { FindingsTable } from '@/components/FindingsTable'
import type { Review } from '@/types'
```

**Named vs default imports:**
```typescript
// GOOD - named (easier to refactor)
import { useApi, useSettings } from '@/hooks'

// BAD - default when multiple exports
import useApi from '@/hooks/useApi'
```
