# Frontend Rules (JavaScript + JSDoc)

Apply to: `frontend/src/**/*.{js,jsx}`

## React Rules

**Functional components only (not class)**
```javascript
// GOOD
export function Dashboard() {
  const [state, setState] = useState(...)
  return <div>...</div>
}
```

**Hooks:** useState, useEffect, useCallback, useMemo

**Max file size:** 250 lines

**Keys in lists:** use item.id, NOT index

## JavaScript + JSDoc

**Type all functions with JSDoc:**
```javascript
/**
 * Fetch user reviews
 * @param {string} userId
 * @returns {Promise<Review[]>}
 */
async function fetchReviews(userId) {
  const response = await fetch(`/api/reviews/${userId}`)
  return response.json()
}
```

**No TypeScript** — Use JSDoc only

## TailwindCSS Only

**NO CSS files, NO inline styles**
- Only Tailwind utility classes
- Dark mode: `dark:bg-gray-900`
- Responsive: `sm:`, `md:`, `lg:`, `xl:`

## State Management (Zustand)

```javascript
import { create } from 'zustand'

export const useSettingsStore = create((set) => ({
  apiKeyClaude: '',
  selectedAgents: [],
  updateSettings: (partial) => set((prev) => ({ ...prev, ...partial }))
}))
```

## API Integration

**All API calls through useApi hook:**
```javascript
const { post } = useApi()

async function handleSubmit(data) {
  try {
    const result = await post('/reviews', data)
  } catch (error) {
    setError(error.message)
  }
}
```

## File Organization

```
frontend/src/
├── pages/
│   ├── Dashboard.jsx
│   ├── ReviewDetail.jsx
│   └── Settings.jsx
├── components/
│   ├── FindingsTable.jsx
│   ├── AgentStatus.jsx
│   └── LLMSelector.jsx
├── hooks/
│   ├── useApi.js
│   ├── useSettings.js
│   └── useWebsocket.js
├── store/
│   └── index.js
└── App.jsx
```

## Testing

**Location:** `src/components/__tests__/Component.test.js`

## Naming

**Variables:** camelCase
**Functions:** camelCase
**Components:** PascalCase
**Constants:** UPPER_SNAKE_CASE

## Checklist

- [ ] Functional components (not class)
- [ ] JSDoc types on functions
- [ ] Tailwind only
- [ ] useApi for API calls
- [ ] Loading + error states
- [ ] Mobile responsive
- [ ] Dark mode
- [ ] Tests written
- [ ] NO TypeScript

---

Ready for work. 🚀
