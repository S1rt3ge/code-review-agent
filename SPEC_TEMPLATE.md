# Feature Specification: Feature Name

## Description

Describe what the feature does, who it is for, and why it matters. Include the user-visible outcome and the system boundary the feature touches.

## User Stories

- As a role, I want to take an action, so that I get a concrete result.
- As a role, I want to recover from a likely failure, so that I can continue without manual database or terminal work.
- As a role, I want to understand the result, so that I can decide what to do next.

## Data Model

List every table, field, type, constraint, foreign key, index, and ownership rule needed by the feature.

```text
table_name
- id: uuid PK
- user_id: uuid FK users(id) NOT NULL
- created_at: timestamptz NOT NULL DEFAULT now()
```

## API

Document each endpoint with method, path, auth requirement, request body, response body, and error codes.

```text
POST /api/resource
Auth: Bearer user JWT
Body: { "field": "value" }
Success: 201 { "id": "uuid" }
Errors: 400 validation error, 401 unauthenticated, 403 forbidden
```

## Screens

List pages/components, visible data, actions, and required states.

- Loading: what the user sees while data is pending.
- Empty: what the user sees with no data.
- Error: what the user sees and how they retry.
- Success: what changes after completion.

## Business Logic

Describe validation rules, state transitions, permissions, defaults, and calculations.

## Edge Cases

- Missing or invalid input.
- Empty data.
- External dependency unavailable.
- Duplicate or repeated action.
- Concurrent requests.
- Large payloads.

## Priority / Dependencies

State priority, rollout order, and dependencies on other modules, migrations, settings, or external services.
