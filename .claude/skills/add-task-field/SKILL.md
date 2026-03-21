---
name: add-task-field
description: Add a new field to the Task dataclass with YAML serialization, API support, and test coverage. Use when extending the task data model, user mentions "new task field", "add field to task", or "extend task".
---

# Add Task Field

Add a new field to the Task dataclass with full serialization and API support.

## When to Use

- Extending the Task model with new metadata
- Adding tracking fields (e.g., estimated_time, tags, assignee)
- User mentions "new task field", "add field", "extend task"

## Inputs Needed

1. **Field name** (snake_case, e.g., `estimated_hours`)
2. **Type** (e.g., `float`, `str`, `list[str]`, `Optional[str]`)
3. **Default value** (e.g., `None`, `0.0`, `[]`)
4. **Optional?** (should it be omitted from YAML when empty?)

## Workflow

### Step 1: Add to Task dataclass

File: `pkgs/tasks/main.py`

```python
@dataclass
class Task:
    id: str
    title: str
    status: TaskStatus
    priority: int
    body: str
    assignee: str
    labels: list[str]
    parent: str | None
    created_at: str
    updated_at: str
    estimated_hours: float = 0.0  # NEW FIELD with default
```

### Step 2: Update `parse()` classmethod

In the `parse()` method, add safe parsing with a default:

```python
@classmethod
def parse(cls, data: dict) -> "Task":
    return cls(
        # ... existing fields ...
        estimated_hours=data.get("estimated_hours", 0.0),  # Safe default
    )
```

### Step 3: Update `to_dict()`

Add the field to serialization, omitting if empty/default:

```python
def to_dict(self) -> dict:
    d = {
        # ... existing fields ...
    }
    if self.estimated_hours:  # Omit if zero/falsy
        d["estimated_hours"] = self.estimated_hours
    return d
```

### Step 4: Update `as_xml()`

Include the field in XML output for agent prompts:

```python
def as_xml(self) -> str:
    parts = [
        # ... existing parts ...
    ]
    if self.estimated_hours:
        parts.append(f"  <estimated_hours>{self.estimated_hours}</estimated_hours>")
    # ...
```

### Step 5: Update server Pydantic models

File: `server/main.py`

Update the request/response models:

```python
class CreateTaskRequest(BaseModel):
    # ... existing fields ...
    estimated_hours: float = 0.0

class UpdateTaskRequest(BaseModel):
    # ... existing fields ...
    estimated_hours: float | None = None

class TaskResponse(BaseModel):
    # ... existing fields ...
    estimated_hours: float
```

### Step 6: Update client TypeScript type

File: `client/src/` (find the Task type definition)

```typescript
interface Task {
  // ... existing fields ...
  estimated_hours: number;
}
```

### Step 7: Add test

File: `tests/tasks/test_main.py`

```python
def test_task_with_new_field():
    task = create_task(title="test", estimated_hours=2.5)
    assert task.estimated_hours == 2.5

    # Test serialization roundtrip
    d = task.to_dict()
    assert d["estimated_hours"] == 2.5
    restored = Task.parse(d)
    assert restored.estimated_hours == 2.5

def test_task_without_new_field_uses_default():
    task = Task.parse({"id": "1", "title": "test", "status": "open", ...})
    assert task.estimated_hours == 0.0

def test_task_xml_includes_new_field():
    task = create_task(title="test", estimated_hours=1.0)
    xml = task.as_xml()
    assert "<estimated_hours>1.0</estimated_hours>" in xml
```

## Files Touched

| File | Change |
|------|--------|
| `pkgs/tasks/main.py` | Dataclass field + parse + to_dict + as_xml |
| `server/main.py` | Pydantic request/response models |
| `client/src/` | TypeScript Task type |
| `tests/tasks/test_main.py` | Serialization roundtrip test |

## Checklist

- [ ] Field added with safe default (won't break existing YAML files)
- [ ] `parse()` uses `.get()` with default (backward compatible)
- [ ] `to_dict()` omits field when empty/default (clean YAML)
- [ ] `as_xml()` includes field when set
- [ ] Pydantic models updated (Create, Update, Response)
- [ ] TypeScript type updated
- [ ] Roundtrip test passes (create -> to_dict -> parse -> assert equal)

## Related Agents

- **task_store**: Owns `pkgs/tasks/main.py`
- **server_websocket**: Owns Pydantic models in `server/main.py`
- **client_developer**: Owns TypeScript types
