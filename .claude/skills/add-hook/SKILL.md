---
name: add-hook
description: Add a new lifecycle hook to the Ralph hooks system. Updates the Hooks ABC, default template, and call site in the runner. Use when extending the hook interface, user mentions "new hook", "lifecycle hook", or "add hook".
---

# Add Hook

Add a new lifecycle hook to the Ralph Loop hooks system.

## When to Use

- Adding a new extension point to the Ralph Loop lifecycle
- User wants custom behavior at a specific point in the iteration cycle
- Extending the hooks interface for new features

## Inputs Needed

1. **Hook name** (e.g., `on_task_retry`, `pre_merge`)
2. **Signature**: Parameters the hook receives
3. **Call site**: Where in the lifecycle this hook fires
4. **Purpose**: What users can do with this hook

## Current Hook Lifecycle

```
pre_loop()          -- Before loop starts
  pre_iter()        -- Before each iteration
    [agent runs]
    on_agent_output() -- When agent produces output
  post_iter()       -- After each iteration
post_loop()         -- After loop ends
```

## Workflow

### Step 1: Add abstract method to Hooks ABC

File: `pkgs/ralph/core/hooks.py`

```python
class Hooks(ABC):
    # ... existing hooks ...

    def on_task_retry(self, task_id: str, attempt: int, reason: str) -> None:
        """Called when a task is retried after failure.

        Args:
            task_id: The task being retried
            attempt: Current retry attempt number
            reason: Why the previous attempt failed
        """
        pass  # Default: no-op
```

**Rules**:
- Use `def` not `async def` (hooks are sync in the current system)
- Default implementation should be a no-op (`pass`)
- Add a concise docstring with parameter descriptions
- Return `None` unless the hook needs to signal something

### Step 2: Add default implementation to template

File: `pkgs/ralph/templates/hooks.py`

```python
class ProjectHooks(Hooks):
    # ... existing implementations ...

    def on_task_retry(self, task_id: str, attempt: int, reason: str) -> None:
        # Custom retry handling (e.g., log, notify, adjust strategy)
        pass
```

### Step 3: Add call site in runner

File: `pkgs/ralph/core/ralphy_runner.py`

Find the right lifecycle point and add:

```python
# In the retry logic section:
self.hooks.on_task_retry(
    task_id=task.id,
    attempt=retry_count,
    reason=str(error),
)
```

**Common call sites**:
- Before iteration: near `self.hooks.pre_iter()` call
- After agent completes: near `self.hooks.on_agent_output()` call
- After iteration: near `self.hooks.post_iter()` call
- On error: in exception handling blocks
- On status change: in `_handle_status()` method

### Step 4: Update existing hooks implementations

Check if `.ralphy/hooks.py` exists in any session directories and needs updating. Usually not needed since the default is a no-op.

### Step 5: Add test

File: `tests/ralph/core/test_hooks.py` (or create if needed)

```python
def test_on_task_retry_called():
    hooks = MockHooks()
    runner = create_test_runner(hooks=hooks)

    # Simulate a retry scenario
    # ...

    assert hooks.on_task_retry_called
    assert hooks.on_task_retry_args == ("task-1", 2, "timeout")
```

## Files Touched

| File | Change |
|------|--------|
| `pkgs/ralph/core/hooks.py` | Add abstract method with docstring |
| `pkgs/ralph/templates/hooks.py` | Add default implementation |
| `pkgs/ralph/core/ralphy_runner.py` | Add call site |
| `tests/ralph/core/test_hooks.py` | Add test |

## Checklist

- [ ] Hook method added to `Hooks` ABC with docstring
- [ ] Default implementation is a no-op (don't break existing users)
- [ ] Call site is at the correct lifecycle point
- [ ] Template hooks.py updated with example implementation
- [ ] Test verifies hook is called with correct arguments

## Related Agents

- **loop_orchestrator**: Owns `hooks.py` and `ralphy_runner.py`
- **integration_tester**: Tests hook lifecycle integration
