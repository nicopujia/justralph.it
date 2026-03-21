---
name: extend-chatbot
description: Add or modify chatbot dimensions, scoring logic, phase caps, or readiness calculation in the Ralphy chatbot. Use when changing requirement extraction behavior, user mentions "chatbot dimension", "confidence scoring", "readiness", or "phase cap".
---

# Extend Chatbot

Modify the Ralphy chatbot's requirement extraction and confidence scoring system.

## When to Use

- Adding a new requirement dimension (e.g., "scalability", "monitoring")
- Adjusting dimension weights or readiness threshold
- Modifying phase progression caps
- Changing the chatbot's personality or response format
- User mentions "chatbot dimension", "confidence", "readiness", "phase cap"

## Inputs Needed

1. **What to change**: New dimension, weight adjustment, phase cap, threshold, or personality
2. **Rationale**: Why this change improves readiness assessment
3. **Expected impact**: How this affects the "Just Ralph It" trigger point

## Current System Overview

File: `server/chatbot.py`

```
DIMENSIONS = ["functional", "technical_stack", "data_model", "auth",
              "deployment", "testing", "edge_cases"]

BASE_WEIGHTS = {dim: weight for dim, weight in ...}  # Per-dimension importance

Readiness threshold: 85% weighted readiness
EMA smoothing: alpha parameter controls convergence speed
Phase caps: 4 phases based on message count limit max confidence
```

## Workflow

### Adding a New Dimension

#### Step 1: Add to DIMENSIONS list

```python
DIMENSIONS = [
    "functional", "technical_stack", "data_model", "auth",
    "deployment", "testing", "edge_cases",
    "scalability",  # NEW
]
```

#### Step 2: Add base weight

```python
BASE_WEIGHTS = {
    # ... existing weights ...
    "scalability": 0.08,  # Relative importance (all weights should sum to ~1.0)
}
```

Rebalance existing weights so they sum to approximately 1.0.

#### Step 3: Update SYSTEM_PROMPT

Add instructions for the new dimension in the chatbot's system prompt:

```python
SYSTEM_PROMPT = """
...
- scalability: How many users/requests must the system handle? Growth expectations?
...
"""
```

#### Step 4: Update client confidence display

File: `client/src/components/ChatPanel.tsx`

Add the new dimension to the confidence meter visualization:
- Add label and color for the new dimension
- Ensure the meter renders the new dimension bar

#### Step 5: Test

```python
def test_new_dimension_scoring():
    state = ChatState()
    # Simulate a message that covers the new dimension
    state = update_scores(state, {"scalability": 75})
    assert state.scores["scalability"] == 75
    assert "scalability" in state.readiness_breakdown
```

### Adjusting Weights

1. Modify `BASE_WEIGHTS` values
2. Ensure weights sum to ~1.0
3. Test that readiness threshold behavior doesn't change dramatically
4. Document why the weight was changed (in a code comment)

### Modifying Phase Caps

1. Find the phase cap logic (based on message count thresholds)
2. Adjust the cap values or message count boundaries
3. Test that early messages can't reach 100% confidence
4. Test that sufficient messages can reach the threshold

### Changing Readiness Threshold

1. Find the threshold constant (currently 85%)
2. Adjust carefully -- lower = start too early, higher = frustrate users
3. Test with representative conversation flows
4. Document the change rationale

## Files Touched

| File | Change |
|------|--------|
| `server/chatbot.py` | DIMENSIONS, BASE_WEIGHTS, SYSTEM_PROMPT, scoring logic |
| `client/src/components/ChatPanel.tsx` | Confidence meter display |
| `tests/` | Scoring behavior tests |

## Checklist

- [ ] Weights sum to approximately 1.0 after changes
- [ ] SYSTEM_PROMPT instructs the chatbot about new dimensions
- [ ] Phase caps still prevent premature high confidence
- [ ] Client confidence meter displays all dimensions
- [ ] Scoring functions still return values in 0-100 range
- [ ] Readiness threshold behavior tested with sample conversations

## Related Agents

- **chatbot_engine**: Owns `server/chatbot.py` (primary agent for this work)
- **client_developer**: Owns confidence meter UI
- **unit_tester**: Tests scoring logic
