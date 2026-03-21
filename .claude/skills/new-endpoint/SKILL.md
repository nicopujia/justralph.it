---
name: new-endpoint
description: Scaffold a new FastAPI endpoint with Pydantic validation, error handling, tests, and client-side fetch. Use when adding a new API route, user mentions "new endpoint", "add route", or "API endpoint".
---

# New Endpoint

Scaffold a complete FastAPI endpoint with validation, error handling, tests, and client integration.

## When to Use

- Adding a new REST API endpoint to the server
- User mentions "new endpoint", "add route", "API endpoint"
- Extending the API surface for new features

## Inputs Needed

1. **HTTP method**: GET, POST, PATCH, DELETE
2. **Path**: e.g., `/api/sessions/{session_id}/logs`
3. **Request model**: Fields and types for the request body (if POST/PATCH)
4. **Response model**: Fields and types for the response
5. **Business logic**: What the endpoint does

## Workflow

### Step 1: Define Pydantic models

Add request/response models to `server/main.py` (near the top with other models):

```python
class CreateLogRequest(BaseModel):
    level: str
    message: str
    context: dict | None = None

class LogResponse(BaseModel):
    id: str
    level: str
    message: str
    created_at: str
```

### Step 2: Write the endpoint

Add the endpoint function to `server/main.py`:

```python
@app.post("/api/sessions/{session_id}/logs", response_model=LogResponse)
async def create_log(session_id: str, req: CreateLogRequest):
    session = _require_session(session_id)  # Reuse existing helper
    # Business logic here
    return LogResponse(...)
```

**Patterns to follow**:
- Use `_require_session(session_id)` for session-scoped endpoints
- Raise `HTTPException(status_code=404)` for not-found
- Raise `HTTPException(status_code=400)` for validation errors
- Return proper status codes: 201 for creation, 200 for retrieval, 204 for deletion

### Step 3: Add test

Create or update test file in `tests/`:

```python
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

def test_create_log():
    # First create a session
    session = client.post("/api/sessions", json={"prompt": "test"}).json()
    session_id = session["id"]

    # Test the new endpoint
    response = client.post(
        f"/api/sessions/{session_id}/logs",
        json={"level": "info", "message": "test log"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["level"] == "info"

def test_create_log_invalid_session():
    response = client.post(
        "/api/sessions/nonexistent/logs",
        json={"level": "info", "message": "test"}
    )
    assert response.status_code == 404
```

### Step 4: Add client-side fetch

Add a fetch function in the relevant hook or create a new one:

```typescript
// In client/src/hooks/ or client/src/lib/
const API_URL = config.API_URL;

export async function createLog(sessionId: string, level: string, message: string) {
  const response = await fetch(`${API_URL}/api/sessions/${sessionId}/logs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ level, message }),
  });
  if (!response.ok) throw new Error(`Failed: ${response.status}`);
  return response.json();
}
```

### Step 5: Verify

```bash
# Run server
uv run uvicorn server.main:app --reload

# Test endpoint
curl -X POST http://localhost:8000/api/sessions/{id}/logs \
  -H "Content-Type: application/json" \
  -d '{"level": "info", "message": "test"}'

# Run tests
uv run pytest tests/ -k "test_create_log" -v
```

## Files Touched

| File | Change |
|------|--------|
| `server/main.py` | Pydantic models + endpoint function |
| `tests/test_*.py` | TestClient tests |
| `client/src/hooks/*.ts` or `client/src/lib/*.ts` | Fetch function |

## Checklist

- [ ] Pydantic model validates all inputs
- [ ] `_require_session` used for session-scoped endpoints
- [ ] Proper HTTP status codes (201, 200, 204, 400, 404)
- [ ] Error responses don't leak internal details
- [ ] Test covers happy path and error cases
- [ ] Client fetch handles errors gracefully
