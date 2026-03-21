---
name: add-event-type
description: Add a new EventType to the Ralph EventBus system. Handles enum addition, emission site, WebSocket broadcast, and client-side handling. Use when you need a new event type, mention "new event", "add event", or "EventType".
---

# Add Event Type

Add a new event to the Ralph EventBus system end-to-end.

## When to Use

- Adding a new type of real-time event to the system
- A new lifecycle point needs to broadcast to the UI
- User mentions "new event type", "add event", "EventType"

## Inputs Needed

1. **Event name** (e.g., `TASK_RETRIED`, `SESSION_EXPIRED`)
2. **Description**: What this event represents
3. **Payload fields**: What data the event carries (e.g., `task_id`, `retry_count`)
4. **Emission site**: Which module/function should emit this event

## Workflow

### Step 1: Add to EventType enum

File: `pkgs/ralph/core/events.py`

```python
class EventType(str, Enum):
    # ... existing types ...
    NEW_EVENT = "new_event"  # Add here
```

### Step 2: Add emission call

Find the function that should emit this event and add:

```python
self._emit(EventType.NEW_EVENT, {
    "task_id": task.id,
    "detail": "relevant data",
})
```

Common emission sites:
- `pkgs/ralph/core/ralphy_runner.py` -- loop lifecycle events
- `pkgs/ralph/core/agent.py` -- agent subprocess events
- `server/sessions.py` -- session lifecycle events
- `server/chatbot.py` -- chatbot state events

### Step 3: Verify WebSocket broadcast

The WebSocket handler in `server/main.py` broadcasts ALL EventBus events generically. Usually **no change needed** here. Verify by reading the WebSocket handler:

```python
# In server/main.py -- the broadcast loop sends all events
# No change needed unless the event needs special handling
```

### Step 4: Add client-side handling

File: `client/src/hooks/useEventReducer.ts`

Add a case to the reducer for the new event type:

```typescript
case "new_event":
  return {
    ...state,
    // Update relevant state based on event payload
  };
```

If the event needs UI display, update the relevant component:
- `StatusBar.tsx` for status events
- `TaskList.tsx` for task events
- `AgentOutput.tsx` for agent events
- `HelpPanel.tsx` for help events

### Step 5: Add test

File: `tests/ralph/core/test_events.py` (or create if needed)

```python
def test_new_event_type_exists():
    assert EventType.NEW_EVENT == "new_event"

def test_new_event_emission(event_bus):
    event_bus.emit(EventType.NEW_EVENT, {"task_id": "test-1"})
    event = event_bus.drain()[0]
    assert event.type == EventType.NEW_EVENT
    assert event.data["task_id"] == "test-1"
```

## Files Touched

| File | Change |
|------|--------|
| `pkgs/ralph/core/events.py` | Add enum member |
| Emission site module | Add `_emit()` call |
| `client/src/hooks/useEventReducer.ts` | Add reducer case |
| `tests/ralph/core/test_events.py` | Add event test |

## Related Agents

- **agent_subprocess**: Owns `events.py`
- **server_websocket**: Owns WebSocket broadcast
- **client_developer**: Owns client components
