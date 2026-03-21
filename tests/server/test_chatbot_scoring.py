"""Unit tests for pure scoring/validation functions in server/chatbot.py.

No subprocess, no OpenCode, no DB calls -- only pure functions and ChatState.
"""

import pytest

from server.chatbot import (
    BASE_WEIGHTS,
    DIMENSIONS,
    EMA_ALPHA,
    MAX_DELTA,
    MIN_DIM_SCORE,
    MIN_QUESTIONS,
    READINESS_THRESHOLD,
    SHORT_MSG_DELTA,
    SHORT_MSG_LEN,
    ChatState,
    _clamp_score,
    _compute_readiness,
    _extract_content,
    _get_phase,
    _is_ready,
    _phase_cap,
    _smooth,
    _strip_code_fences,
)


# ---------------------------------------------------------------------------
# _get_phase
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count,expected", [
    (1, 1),
    (2, 1),
    (3, 1),
    (4, 2),
    (7, 2),
    (8, 3),
    (10, 3),
    (11, 4),
    (50, 4),
])
def test_get_phase(count: int, expected: int):
    assert _get_phase(count) == expected


def test_get_phase_zero_returns_phase_1():
    assert _get_phase(0) == 1


# ---------------------------------------------------------------------------
# _phase_cap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count,expected", [
    (1, 40),
    (3, 40),
    (4, 70),
    (7, 70),
    (8, 90),
    (10, 90),
    (11, 100),
    (100, 100),
])
def test_phase_cap(count: int, expected: int):
    assert _phase_cap(count) == expected


def test_phase_cap_zero_returns_40():
    assert _phase_cap(0) == 40


# ---------------------------------------------------------------------------
# _clamp_score
# ---------------------------------------------------------------------------


def test_clamp_score_enforces_phase_max():
    # prev=30, new=80, phase_max=40, long message (delta=20 allows up to 50)
    # delta allows 50, but phase_max caps at 40 -- phase_max wins
    result = _clamp_score(80, 30, 40, 100)
    assert result == 40


def test_clamp_score_enforces_max_delta_for_long_message():
    # prev=10, max_delta=20, so max allowed is 30
    result = _clamp_score(50, 10, 100, SHORT_MSG_LEN + 1)
    assert result == 10 + MAX_DELTA


def test_clamp_score_enforces_short_msg_delta_for_short_message():
    # prev=10, short_delta=5, so max allowed is 15
    result = _clamp_score(50, 10, 100, SHORT_MSG_LEN - 1)
    assert result == 10 + SHORT_MSG_DELTA


def test_clamp_score_does_not_exceed_100():
    result = _clamp_score(200, 90, 100, 100)
    assert result <= 100


def test_clamp_score_not_below_zero():
    result = _clamp_score(-10, 0, 100, 100)
    assert result == 0


def test_clamp_score_phase_max_and_delta_both_apply():
    # phase_max=40, prev=25, delta=20 -> prev+delta=45 > phase_max=40, so clamped to 40
    result = _clamp_score(80, 25, 40, SHORT_MSG_LEN + 1)
    assert result == 40


def test_clamp_score_small_increase_allowed():
    # prev=10, new=15, within MAX_DELTA and phase_max=100
    result = _clamp_score(15, 10, 100, 100)
    assert result == 15


# ---------------------------------------------------------------------------
# _smooth
# ---------------------------------------------------------------------------


def test_smooth_decreasing_score_returns_new_directly():
    # new <= prev: no EMA smoothing
    result = _smooth(30, 50)
    assert result == 30


def test_smooth_equal_score_returns_new():
    result = _smooth(50, 50)
    assert result == 50


def test_smooth_increasing_score_applies_ema():
    # new=100, prev=0: result = round(0.7*100 + 0.3*0) = 70
    result = _smooth(100, 0)
    assert result == round(EMA_ALPHA * 100 + (1 - EMA_ALPHA) * 0)
    assert result == 70


def test_smooth_increasing_score_ema_formula():
    new, prev = 80, 50
    expected = round(EMA_ALPHA * new + (1 - EMA_ALPHA) * prev)
    assert _smooth(new, prev) == expected


def test_smooth_returns_integer():
    result = _smooth(70, 30)
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# _compute_readiness
# ---------------------------------------------------------------------------


def test_compute_readiness_all_zeros_returns_zero():
    conf = {d: 0 for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}
    assert _compute_readiness(conf, rel) == 0.0


def test_compute_readiness_all_100_returns_100():
    conf = {d: 100 for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}
    result = _compute_readiness(conf, rel)
    assert abs(result - 100.0) < 0.001


def test_compute_readiness_weighted_by_base_weights():
    # Only functional (weight=2.0) matters, everything else is 0
    conf = {d: 0 for d in DIMENSIONS}
    conf["functional"] = 80
    rel = {d: 1.0 for d in DIMENSIONS}
    total_weight = sum(BASE_WEIGHTS.values())
    expected = (80 * BASE_WEIGHTS["functional"]) / total_weight
    result = _compute_readiness(conf, rel)
    assert abs(result - expected) < 0.001


def test_compute_readiness_zero_relevance_excludes_dimension():
    # auth with relevance=0: excluded from both numerator and denominator
    conf = {d: 100 for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}
    rel["auth"] = 0.0
    # Auth is excluded, so readiness still near 100 for the rest
    result = _compute_readiness(conf, rel)
    assert result > 90.0


def test_compute_readiness_empty_denominator_returns_zero():
    conf = {d: 0 for d in DIMENSIONS}
    rel = {d: 0.0 for d in DIMENSIONS}  # all zero relevance -> den=0
    result = _compute_readiness(conf, rel)
    assert result == 0.0


# ---------------------------------------------------------------------------
# _is_ready
# ---------------------------------------------------------------------------


def _make_ready_state() -> ChatState:
    """Construct a ChatState that passes all readiness checks."""
    # Need >= MIN_QUESTIONS user messages
    messages = []
    for i in range(MIN_QUESTIONS):
        messages.append({"role": "user", "content": f"message {i}"})
        messages.append({"role": "assistant", "content": f"response {i}"})
    conf = {d: 90 for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}
    state = ChatState(
        messages=messages,
        confidence=conf,
        relevance=rel,
        weighted_readiness=90.0,
    )
    return state


def test_is_ready_passes_all_conditions():
    state = _make_ready_state()
    assert _is_ready(state) is True


def test_is_ready_false_when_not_enough_questions():
    state = _make_ready_state()
    # Remove messages until user count < MIN_QUESTIONS
    state.messages = state.messages[:2]  # only 1 user message
    assert state.user_msg_count < MIN_QUESTIONS
    assert _is_ready(state) is False


def test_is_ready_false_when_readiness_below_threshold():
    state = _make_ready_state()
    state.weighted_readiness = READINESS_THRESHOLD - 1
    assert _is_ready(state) is False


def test_is_ready_false_when_dim_score_too_low():
    state = _make_ready_state()
    # functional has relevance=1.0 > RELEVANCE_CUTOFF=0.3, so must be >= MIN_DIM_SCORE
    state.confidence["functional"] = MIN_DIM_SCORE - 1
    assert _is_ready(state) is False


def test_is_ready_ignores_low_relevance_dims():
    state = _make_ready_state()
    # auth with low relevance is excluded from the min-score check
    state.confidence["auth"] = 0
    state.relevance["auth"] = 0.1  # <= RELEVANCE_CUTOFF (0.3)
    # Should still be ready because auth is below cutoff
    assert _is_ready(state) is True


def test_is_ready_false_when_multiple_dims_below_min():
    state = _make_ready_state()
    state.confidence["functional"] = 50
    state.confidence["technical_stack"] = 50
    assert _is_ready(state) is False


# ---------------------------------------------------------------------------
# ChatState.user_msg_count
# ---------------------------------------------------------------------------


def test_chat_state_user_msg_count_empty():
    state = ChatState()
    assert state.user_msg_count == 0


def test_chat_state_user_msg_count_counts_only_user_role():
    state = ChatState(messages=[
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "bye"},
    ])
    assert state.user_msg_count == 2


def test_chat_state_user_msg_count_no_user_messages():
    state = ChatState(messages=[
        {"role": "assistant", "content": "hello"},
    ])
    assert state.user_msg_count == 0


# ---------------------------------------------------------------------------
# ChatState.to_dict
# ---------------------------------------------------------------------------


def test_chat_state_to_dict_has_required_keys():
    state = ChatState()
    d = state.to_dict()
    assert "confidence" in d
    assert "relevance" in d
    assert "ready" in d
    assert "weighted_readiness" in d
    assert "question_count" in d
    assert "phase" in d


def test_chat_state_to_dict_weighted_readiness_rounded():
    state = ChatState(weighted_readiness=85.6789)
    d = state.to_dict()
    assert d["weighted_readiness"] == 85.7


def test_chat_state_to_dict_phase_reflects_msg_count():
    state = ChatState(messages=[
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "resp"},
    ])
    d = state.to_dict()
    assert d["question_count"] == 1
    assert d["phase"] == 1  # 1 user message -> phase 1


def test_chat_state_to_dict_ready_reflects_state():
    state = ChatState(ready=True)
    assert state.to_dict()["ready"] is True


# ---------------------------------------------------------------------------
# _strip_code_fences
# ---------------------------------------------------------------------------


def test_strip_code_fences_removes_json_fence():
    text = '```json\n{"key": "value"}\n```'
    result = _strip_code_fences(text)
    assert result == '{"key": "value"}'


def test_strip_code_fences_removes_plain_fence():
    text = '```\n{"key": "value"}\n```'
    result = _strip_code_fences(text)
    assert result == '{"key": "value"}'


def test_strip_code_fences_no_fence_returns_stripped():
    text = '  {"key": "value"}  '
    result = _strip_code_fences(text)
    assert result == '{"key": "value"}'


def test_strip_code_fences_multiline_content():
    text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
    result = _strip_code_fences(text)
    assert '"a": 1' in result
    assert '"b": 2' in result


def test_strip_code_fences_empty_string():
    assert _strip_code_fences("") == ""


# ---------------------------------------------------------------------------
# _extract_content
# ---------------------------------------------------------------------------


def test_extract_content_extracts_text_events():
    import json
    events = [
        json.dumps({"type": "step_start", "data": {}}),
        json.dumps({"type": "text", "part": {"text": "Hello"}}),
        json.dumps({"type": "text", "part": {"text": " world"}}),
        json.dumps({"type": "step_finish", "data": {}}),
    ]
    output = "\n".join(events)
    result = _extract_content(output)
    assert result == "Hello world"


def test_extract_content_ignores_non_text_events():
    import json
    events = [
        json.dumps({"type": "step_start"}),
        json.dumps({"type": "step_finish"}),
    ]
    result = _extract_content("\n".join(events))
    # No text events -- returns original output
    assert result == "\n".join(events)


def test_extract_content_handles_non_json_lines():
    # Raw text line mixed in
    output = "raw response line"
    result = _extract_content(output)
    assert result == "raw response line"


def test_extract_content_skips_empty_text_parts():
    import json
    events = [
        json.dumps({"type": "text", "part": {"text": ""}}),
        json.dumps({"type": "text", "part": {"text": "content"}}),
    ]
    result = _extract_content("\n".join(events))
    assert result == "content"


def test_extract_content_empty_output():
    result = _extract_content("")
    assert result == ""


def test_extract_content_single_text_event():
    import json
    line = json.dumps({"type": "text", "part": {"text": "just this"}})
    assert _extract_content(line) == "just this"


# --- Edge cases (audit additions) ---


def test_clamp_score_prev_above_phase_max():
    # prev=80 already exceeds phase_max=70. new=90 is clamped to 70 by
    # phase_max. Then delta check: 70 <= 80 + MAX_DELTA, so no delta clamp.
    # Score decrease is allowed (no lower-bound on prev), result is 70.
    result = _clamp_score(90, 80, 70, 100)
    assert result == 70


def test_compute_readiness_partial_relevance():
    # Relevance dict omits some dimensions entirely. Missing dims default to
    # 1.0 via .get(d, 1.0), so they are included with full weight.
    conf = {d: 50 for d in DIMENSIONS}
    # Provide relevance for only one dimension
    partial_rel = {"functional": 1.0}
    result = _compute_readiness(conf, partial_rel)
    # All dims at 50 with effective relevance 1.0 -> readiness should be 50.0
    assert abs(result - 50.0) < 0.001


def test_is_ready_at_exact_threshold():
    # weighted_readiness == READINESS_THRESHOLD (85) and all dims at exactly
    # MIN_DIM_SCORE (70). The guards use `< READINESS_THRESHOLD` and
    # `< MIN_DIM_SCORE`, so exact values should pass and return True.
    messages = []
    for i in range(MIN_QUESTIONS):
        messages.append({"role": "user", "content": f"msg {i}"})
        messages.append({"role": "assistant", "content": f"resp {i}"})
    conf = {d: MIN_DIM_SCORE for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}
    state = ChatState(
        messages=messages,
        confidence=conf,
        relevance=rel,
        weighted_readiness=float(READINESS_THRESHOLD),
    )
    assert _is_ready(state) is True
