# Backend Rules

Apply these rules to all Python backend code (glob: `backend/**/*.py`)

## Architecture Rules

**async/await:**
- All I/O operations MUST be async (database, HTTP, file)
- FastAPI route handlers MUST be async
- Never use .run_sync() or blocking calls in async context
- Pattern: `async def function_name(...) -> ReturnType:`

**Database:**
- All queries use SQLAlchemy async (AsyncSession)
- Use `await session.execute(stmt)` or `await session.get(Model, id)`
- Never hardcode SQL strings (use ORM)
- RLS policies enforced at database level
- Foreign keys use ON DELETE CASCADE

**LLM Integration:**
- ALL LLM calls go through `llm_router.select(user_settings)`
- Never hardcode provider (Claude/GPT/Ollama choice)
- Token counting for all LLM calls (for billing)
- Timeouts on LLM calls (30 seconds max)
- Fallback if LLM fails (return error, don't crash)

**Error Handling:**
- HTTP endpoints raise HTTPException with status_code + detail
- Internal errors logged with logger (not printed)
- Database errors → 500 with generic message (don't expose internals)
- Webhook signature failures → 401
- Request validation fails → 400

## Type Safety

**Type hints required:**
```python
# GOOD
async def get_user(user_id: str, session: AsyncSession) -> User:
    ...

# BAD - missing types
async def get_user(user_id, session):
    ...
```

**No `any` types:**
- Use specific types or `Unknown` if truly dynamic
- Dataclass typing: use `@dataclass` or Pydantic models
- Dict typing: `dict[str, Any]` not just `dict`

**Pydantic models:**
- All API request/response bodies use Pydantic
- Config: `model_config = ConfigDict(from_attributes=True)` for ORM objects

## Code Organization

**Imports order:**
```python
# 1. Standard library
import asyncio
import json

# 2. Third-party
from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Local
from backend.models import Review
from backend.config import settings
```

**Module structure:**
- Constants at top (API paths, timeouts, limits)
- Classes/types in middle
- Functions at bottom
- Exports at the very end (explicit `__all__`)

**Function max length:** 40 lines
- Longer → refactor into smaller functions
- Each function does ONE thing

## Testing Rules

**Unit test location:** `backend/tests/test_<module>.py`
```python
# Match module structure
# backend/services/github_api.py → backend/tests/test_github_api.py
```

**Test naming:**
```python
def test_verify_github_signature_valid():
    """What it tests: verify_github_signature with valid input."""
    # Arrange
    # Act
    # Assert

def test_verify_github_signature_invalid():
    """What it tests: verify_github_signature with invalid input."""
```

**Mocking LLM calls:**
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_security_agent_finds_injection(mocker):
    # Mock the LLM to return predictable response
    mock_llm = AsyncMock(return_value='{"findings": [{"type": "sql_injection", ...}]}')
    mocker.patch('backend.agents.llm_router.select', return_value=mock_llm)
    
    result = await security_agent(state)
    assert len(result['findings']) > 0
```

## Documentation Rules

**Module docstring (file top):**
```python
"""Module name and purpose.

Classes:
  ClassName: What it does

Functions:
  function_name: What it does
"""
```

**Function docstring:**
```python
async def verify_github_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature (X-Hub-Signature-256).
    
    Args:
        body: Raw request body (bytes)
        signature: X-Hub-Signature-256 header value
        secret: GitHub webhook secret
    
    Returns:
        True if valid, False otherwise
    
    Raises:
        ValueError: If signature format invalid
    """
```

**No docstring needed for:**
- Simple getters/setters
- Obvious test functions
- Private helper functions (_function_name)

## Performance Rules

**Database:**
- Use `.limit(N)` for pagination (default 20, max 100)
- Add indices on frequently queried columns
- Avoid N+1 queries (use select with joins)
- Use lazy=False for relationships in joins

**Caching:**
- Cache LLM responses (don't re-analyze same code)
- Cache GitHub repo settings (loaded once per webhook)
- Redis for session state (if needed later)

**Timeouts:**
- GitHub API calls: 10 seconds
- LLM calls: 30 seconds
- Database queries: 5 seconds
- Webhook processing: must complete in <60 seconds

## Security Rules

**Input validation:**
- All request bodies validated via Pydantic
- GitHub webhook signature verified (HMAC-SHA256)
- File paths sanitized (no path traversal)
- Code strings escaped in PR comments

**Secrets:**
- Never log API keys, passwords, tokens
- Use `settings.anthropic_api_key` from env
- Encrypt stored API keys (Fernet)
- Don't commit .env files

**RLS at database level:**
- All SELECT queries filtered by user_id
- No trusting user_id from JWT alone
- Database policies enforce access control

**Safe SQL:**
- Always parameterized queries (SQLAlchemy handles this)
- Never f-string in SQL
- No SQL injection in generated comments

## Logging

**Pattern:**
```python
import logging
logger = logging.getLogger(__name__)

# In code:
logger.info(f"Processing review {review_id}")
logger.error(f"LLM failed: {error}", exc_info=True)
logger.debug(f"Tokens used: {token_count}")
```

**What to log:**
- API request/response (for debugging)
- LLM calls (model, tokens)
- Database queries (if slow)
- Errors (with context)

**What NOT to log:**
- API keys, secrets
- User passwords
- Full request bodies (too verbose)
- Debug spam (every line)

## Naming Conventions

**Variables:** snake_case
```python
user_id = "123"
max_findings = 100
is_valid = True
```

**Functions:** snake_case, verb first
```python
def verify_signature(...)
def extract_code(...)
def aggregate_results(...)
```

**Classes:** PascalCase
```python
class SecurityAgent:
class FindingsAggregator:
```

**Constants:** UPPER_SNAKE_CASE
```python
MAX_CODE_SIZE = 50000
DEFAULT_TIMEOUT = 30
AGENTS = ["security", "performance", "style", "logic"]
```

## API Endpoint Rules

**Status codes:**
- 200: GET success
- 201: POST success (created)
- 202: Async operation accepted
- 204: DELETE success
- 400: Invalid request (validation)
- 401: Unauthorized (missing/invalid JWT)
- 403: Forbidden (user can't access)
- 404: Not found
- 409: Conflict (duplicate, race condition)
- 500: Server error

**Response format:**
```python
# Success
{ "data": {...}, "status": "ok" }

# Error
{ "detail": "Specific error message", "status": "error" }
```

**Pagination:**
```python
@router.get("/reviews")
async def list_reviews(limit: int = 20, offset: int = 0):
    # Validate limits
    limit = min(limit, 100)  # Cap at 100
    offset = max(offset, 0)  # No negative offset
```
