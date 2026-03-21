---
name: perf-audit
description: Performance profiling and bottleneck identification. Use when optimizing speed, reducing memory usage, finding slow endpoints, or when user mentions "performance", "slow", "bottleneck", "profiling", or "optimize".
---

# Performance Audit

Profile, identify bottlenecks, and implement targeted optimizations.

## When to Use

- API endpoints respond slowly
- Loop iterations take longer than expected
- Memory usage grows over time
- User mentions "slow", "performance", "bottleneck", "optimize"
- Before scaling or deployment

## Workflow

### Step 1: Identify Scope
Determine which subsystem to profile.
- **Server**: Slow API responses, WebSocket lag, chatbot latency
- **Loop**: Long iterations, agent subprocess delays, git operation slowness
- **Client**: Render lag, excessive re-renders, large bundle size
- **Task Store**: Slow YAML reads/writes with many tasks

### Step 2: Profile

**Python (server/loop)**:
```bash
# Quick timing
uv run python -c "import time; start=time.time(); ...; print(time.time()-start)"

# Profile a specific function
uv run python -m cProfile -s cumtime server/main.py

# For async code, check blocking calls in event loop
```

**TypeScript (client)**:
```bash
# Bundle analysis
bun build --analyze

# Check component render counts via React DevTools
```

### Step 3: Analyze
Identify the hot paths.

**Common bottlenecks in this project**:
| Area | Likely Bottleneck | Check |
|------|-------------------|-------|
| Server | Blocking I/O in async endpoints | Look for sync file reads in async handlers |
| Chatbot | OpenCode subprocess latency | Check `chat()` call duration |
| Task Store | YAML parse/write on every operation | Check `list_tasks()` with many tasks |
| Loop | Agent subprocess timeout/retry | Check `process_task()` duration |
| Git ops | Multiple subprocess calls per iteration | Check `_run()` call frequency |
| Client | Unnecessary re-renders | Check useEventReducer dispatch frequency |
| WebSocket | Large payload serialization | Check event payload sizes |

### Step 4: Recommend
Prioritize by impact.
- List optimizations with expected improvement (e.g., "cache YAML parse: ~50ms -> ~1ms per read")
- Consider tradeoffs (caching vs staleness, async vs complexity)
- Flag quick wins vs larger refactors

### Step 5: Implement
Apply the highest-impact fix first.
- Measure before and after
- Keep changes minimal and focused
- Coordinate with python_improver (backend) or typescript_improver (frontend) for larger refactors
- Add a comment noting the optimization and why it matters

## Quick Checks

- **YAML task store**: Is `list_tasks()` called in a loop? Consider caching.
- **Subprocess calls**: Are multiple git commands run sequentially? Consider batching.
- **Event emission**: Is EventBus queue draining fast enough?
- **React renders**: Are components missing useMemo/useCallback for expensive computations?
- **API calls**: Are there N+1 patterns (fetching tasks one by one instead of batch)?
