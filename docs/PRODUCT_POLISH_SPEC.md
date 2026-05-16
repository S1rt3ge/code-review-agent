# Feature Specification: Product Polish Sweep

## Description

Make the MVP feel more intentional during setup and repository management. This
slice focuses on the Repositories page because it is the first place users go
after the dashboard onboarding when they want GitHub PR automation.

## User Stories

- As a new user, I want repository loading to look deliberate, so that the app
  does not feel frozen while setup data is fetched.
- As a user whose repository request fails, I want a direct retry action, so
  that I can recover without refreshing the browser.
- As a mobile evaluator, I want connected repositories to read as cards, so that
  I can manage setup without sideways scrolling.

## Data Model

No database migration is required. The page continues to use the existing
repository response shape:

```text
repository
- id: string
- github_repo_owner: string
- github_repo_name: string
- github_repo_url: string
- github_installation_id: number|null
- enabled: boolean
- created_at: string
```

## API

No new API endpoints are required.

Existing authenticated endpoints:

```text
GET /api/repositories
PATCH /api/repositories/{id}
DELETE /api/repositories/{id}
POST /api/repositories
```

## Screens

Repositories page:

- Loading: show a skeleton list with the same page framing as the loaded state.
- Empty: keep the setup guidance and clarify that local demo reviews still work
  without GitHub repositories.
- Error: show concise failure copy and a retry button.
- Success desktop: keep the existing table.
- Success mobile: show repository cards with status, installation ID, created
  date, and enable/remove actions.

## Business Logic

- Fetch behavior and repository mutations stay unchanged.
- Retry calls the same repository fetch function.
- Toggle and remove actions behave the same from table rows and mobile cards.
- The mobile card layout is a presentational alternative to the desktop table;
  it does not change permissions or request payloads.

## Edge Cases

- Empty repository list remains a usable setup state.
- Fetch failure can be retried repeatedly.
- Repository action failures stay scoped to the affected row/card.
- Missing installation ID displays an empty placeholder.
- Long owner/repository names wrap instead of forcing mobile overflow.

## Priority / Dependencies

Priority: v0.2.0 product polish. Depends only on the existing Repositories page,
API client hook, and repository endpoints.
