"""Unit tests for pure scoring/validation functions in server/chatbot.py.

No subprocess, no OpenCode, no DB calls -- only pure functions and ChatState.
"""

import pytest

from server.chatbot import (
    BASE_WEIGHTS,
    BATCH_BONUS_THRESHOLD,
    DIMENSIONS,
    EMA_ALPHA,
    MAX_DELTA,
    MIN_DIM_SCORE,
    QUESTIONS_PER_DIM_INITIAL,
    QUESTION_REDUCTION_FACTOR,
    READINESS_THRESHOLD,
    RELEVANCE_CUTOFF,
    SHORT_MSG_DELTA,
    SHORT_MSG_LEN,
    ChatState,
    _auto_score_irrelevant,
    _build_question_guidance,
    _clamp_score,
    _compute_readiness,
    _describe_gaps,
    _extract_content,
    _get_phase,
    _is_ready,
    _phase_cap,
    _questions_for_dim,
    _smooth,
    _strip_code_fences,
    _strip_task_content,
)


# ---------------------------------------------------------------------------
# _get_phase
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chars,expected", [
    (50, 1),     # tiny input
    (100, 1),    # boundary
    (101, 2),    # crosses into phase 2
    (350, 2),    # boundary
    (351, 3),    # crosses into phase 3
    (700, 3),    # boundary
    (701, 4),    # full phase
    (5000, 4),
])
def test_get_phase(chars: int, expected: int):
    assert _get_phase(total_chars=chars) == expected


def test_get_phase_zero_chars_returns_phase_1():
    assert _get_phase(total_chars=0) == 1


# ---------------------------------------------------------------------------
# _phase_cap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chars,expected", [
    (50, 65),    # tiny
    (100, 65),   # boundary
    (101, 90),   # moderate
    (350, 90),   # boundary
    (351, 100),  # uncapped
    (700, 100),  # boundary
    (701, 100),  # beyond
    (5000, 100),
])
def test_phase_cap(chars: int, expected: int):
    assert _phase_cap(total_chars=chars) == expected


def test_phase_cap_zero_returns_65():
    assert _phase_cap(total_chars=0) == 65


# ---------------------------------------------------------------------------
# _clamp_score
# ---------------------------------------------------------------------------


def test_clamp_score_enforces_phase_max():
    # phase_max caps the score even if delta allows higher
    result = _clamp_score(80, 30, 40, 100)
    assert result == 40


def test_clamp_score_enforces_max_delta_for_long_message():
    # prev + MAX_DELTA is the ceiling for long messages
    result = _clamp_score(200, 10, 100, SHORT_MSG_LEN + 1)
    assert result == 10 + MAX_DELTA


def test_clamp_score_enforces_short_msg_delta_for_short_message():
    # prev + SHORT_MSG_DELTA is the ceiling for short messages
    result = _clamp_score(200, 10, 100, SHORT_MSG_LEN - 1)
    assert result == 10 + SHORT_MSG_DELTA


def test_clamp_score_does_not_exceed_100():
    result = _clamp_score(200, 90, 100, 100)
    assert result <= 100


def test_clamp_score_not_below_zero():
    result = _clamp_score(-10, 0, 100, 100)
    assert result == 0


def test_clamp_score_phase_max_and_delta_both_apply():
    # phase_max wins when it's lower than prev+delta
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


def test_smooth_first_score_skips_dampening():
    # When prev=0, first real score is used directly (no EMA against zero)
    result = _smooth(100, 0)
    assert result == 100


def test_smooth_increasing_score_applies_ema():
    # When prev > 0, EMA is applied
    result = _smooth(100, 50)
    expected = round(EMA_ALPHA * 100 + (1 - EMA_ALPHA) * 50)
    assert result == expected


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
    # Provide enough content to be meaningful (no min question count anymore)
    messages = [
        {"role": "user", "content": "Build me a full-stack todo app with auth, tests, and deployment."},
        {"role": "assistant", "content": "Got it, let me assess the requirements."},
    ]
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


def test_is_ready_true_even_with_few_messages():
    """Readiness is based on score thresholds, not message count."""
    state = _make_ready_state()
    assert state.user_msg_count == 1
    assert _is_ready(state) is True


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
    messages = [
        {"role": "user", "content": "A detailed project description."},
        {"role": "assistant", "content": "Acknowledged."},
    ]
    conf = {d: MIN_DIM_SCORE for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}
    state = ChatState(
        messages=messages,
        confidence=conf,
        relevance=rel,
        weighted_readiness=float(READINESS_THRESHOLD),
    )
    assert _is_ready(state) is True


# ---------------------------------------------------------------------------
# _questions_for_dim
# ---------------------------------------------------------------------------


def test_questions_for_dim_zero_confidence():
    conf = {d: 0 for d in DIMENSIONS}
    assert _questions_for_dim("functional", conf) == QUESTIONS_PER_DIM_INITIAL


def test_questions_for_dim_high_confidence():
    conf = {d: 90 for d in DIMENSIONS}
    assert _questions_for_dim("functional", conf) == 0


def test_questions_for_dim_medium_confidence():
    conf = {d: 60 for d in DIMENSIONS}
    result = _questions_for_dim("functional", conf)
    expected = max(1, round(QUESTIONS_PER_DIM_INITIAL * (1 - QUESTION_REDUCTION_FACTOR)))
    assert result == expected
    assert result < QUESTIONS_PER_DIM_INITIAL


# ---------------------------------------------------------------------------
# _build_question_guidance
# ---------------------------------------------------------------------------


def test_build_question_guidance_all_zero():
    conf = {d: 0 for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}
    guidance = _build_question_guidance(conf, rel)
    total = QUESTIONS_PER_DIM_INITIAL * len(DIMENSIONS)
    assert f"Total questions this turn: {total}" in guidance


def test_build_question_guidance_skips_irrelevant():
    conf = {d: 0 for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}
    rel["auth"] = 0.0
    guidance = _build_question_guidance(conf, rel)
    assert "auth**: SKIP" in guidance


def test_build_question_guidance_covered_dimensions():
    conf = {d: 95 for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}
    guidance = _build_question_guidance(conf, rel)
    assert "COVERED" in guidance
    assert "Total questions this turn: 0" in guidance


# ---------------------------------------------------------------------------
# _strip_task_content
# ---------------------------------------------------------------------------


def test_strip_task_content_short_list_preserved():
    msg = "Here are 3 things:\n1. First\n2. Second\n3. Third\nDone."
    assert _strip_task_content(msg) == msg


def test_strip_task_content_long_list_collapsed():
    lines = [f"{i}. Task {i} title here" for i in range(1, 12)]
    msg = "Let me list the tasks:\n" + "\n".join(lines) + "\nDone."
    result = _strip_task_content(msg)
    assert "11 tasks generated" in result
    assert "Task 1 title here" not in result


def test_strip_task_content_no_task_lines():
    msg = "This is a normal response with no task list."
    assert _strip_task_content(msg) == msg


def test_strip_task_content_bullet_list_collapsed():
    lines = [f"- **Task {i}**: do something" for i in range(1, 8)]
    msg = "Tasks:\n" + "\n".join(lines)
    result = _strip_task_content(msg)
    assert "7 tasks generated" in result


# ---------------------------------------------------------------------------
# _describe_gaps
# ---------------------------------------------------------------------------


def test_describe_gaps_all_met():
    state = _make_ready_state()
    result = _describe_gaps(state)
    assert result == "almost there"


def test_describe_gaps_low_dimension():
    state = _make_ready_state()
    state.confidence["testing"] = 50
    state.weighted_readiness = 75.0
    result = _describe_gaps(state)
    assert "testing" in result
    assert "50%" in result


def test_describe_gaps_low_readiness():
    state = _make_ready_state()
    state.weighted_readiness = 70.0
    result = _describe_gaps(state)
    assert "overall readiness" in result


# ---------------------------------------------------------------------------
# _auto_score_irrelevant
# ---------------------------------------------------------------------------


def test_auto_score_irrelevant_sets_95():
    state = ChatState()
    state.relevance["auth"] = 0.0
    state.confidence["auth"] = 0
    _auto_score_irrelevant(state)
    assert state.confidence["auth"] == 95


def test_auto_score_irrelevant_skips_relevant():
    state = ChatState()
    state.relevance["functional"] = 1.0
    state.confidence["functional"] = 50
    _auto_score_irrelevant(state)
    assert state.confidence["functional"] == 50


def test_auto_score_irrelevant_skips_already_high():
    state = ChatState()
    state.relevance["auth"] = 0.1
    state.confidence["auth"] = 95
    _auto_score_irrelevant(state)
    assert state.confidence["auth"] == 95


# ---------------------------------------------------------------------------
# _clamp_score batch bonus
# ---------------------------------------------------------------------------


def test_clamp_score_batch_bonus_for_long_messages():
    # Messages > BATCH_BONUS_THRESHOLD get extra delta
    result_short = _clamp_score(95, 0, 100, 100)
    result_batch = _clamp_score(95, 0, 100, BATCH_BONUS_THRESHOLD + 1)
    assert result_batch > result_short


# ---------------------------------------------------------------------------
# Scoring math simulation: 3-turn convergence
# ---------------------------------------------------------------------------


def test_scoring_reaches_readiness_in_3_turns():
    """Simulate 3 chat turns and verify readiness reaches threshold."""
    conf = {d: 0 for d in DIMENSIONS}
    rel = {d: 1.0 for d in DIMENSIONS}

    # Simulate 3 turns of batch answers (each ~600 chars)
    for turn in range(3):
        total_chars = (turn + 1) * 600
        phase_max = _phase_cap(total_chars)
        msg_len = 600

        for d in DIMENSIONS:
            raw = 95  # LLM reports high confidence
            prev = conf[d]
            clamped = _clamp_score(raw, prev, phase_max, msg_len)
            conf[d] = _smooth(clamped, prev)

    readiness = _compute_readiness(conf, rel)
    assert readiness >= READINESS_THRESHOLD, f"Readiness {readiness:.1f}% < {READINESS_THRESHOLD}% after 3 turns"
    for d in DIMENSIONS:
        assert conf[d] >= MIN_DIM_SCORE, f"{d} = {conf[d]} < {MIN_DIM_SCORE} after 3 turns"


# ---------------------------------------------------------------------------
# _generate_tasks_fallback
# ---------------------------------------------------------------------------


class TestGenerateTasksFallback:
    """Tests for the two-step task generation fallback."""

    def test_returns_none_on_subprocess_failure(self):
        from unittest.mock import patch, MagicMock
        from server.chatbot import _generate_tasks_fallback

        state = _make_ready_state()
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "error"

        with patch("server.chatbot.subprocess.run", return_value=mock_result):
            result = _generate_tasks_fallback(state, None, "test-model")
        assert result is None

    def test_returns_none_on_timeout(self):
        import subprocess as sp
        from unittest.mock import patch
        from server.chatbot import _generate_tasks_fallback

        state = _make_ready_state()
        with patch("server.chatbot.subprocess.run", side_effect=sp.TimeoutExpired("cmd", 60)):
            result = _generate_tasks_fallback(state, None, "test-model")
        assert result is None

    def test_returns_none_on_invalid_json(self):
        from unittest.mock import patch, MagicMock
        from server.chatbot import _generate_tasks_fallback

        state = _make_ready_state()
        mock_result = MagicMock()
        mock_result.stdout = '{"type":"text","part":{"text":"not valid json {{{"}}'

        with patch("server.chatbot.subprocess.run", return_value=mock_result):
            result = _generate_tasks_fallback(state, None, "test-model")
        assert result is None

    def test_returns_none_when_tasks_not_list(self):
        import json
        from unittest.mock import patch, MagicMock
        from server.chatbot import _generate_tasks_fallback

        state = _make_ready_state()
        # LLM returns tasks as a string instead of list
        payload = json.dumps({"tasks": "not a list", "project": {}})
        ndjson = json.dumps({"type": "text", "part": {"text": payload}})
        mock_result = MagicMock()
        mock_result.stdout = ndjson

        with patch("server.chatbot.subprocess.run", return_value=mock_result):
            result = _generate_tasks_fallback(state, None, "test-model")
        assert result is None

    def test_returns_parsed_tasks_on_success(self):
        import json
        from unittest.mock import patch, MagicMock
        from server.chatbot import _generate_tasks_fallback

        state = _make_ready_state()
        payload = json.dumps({
            "tasks": [
                {"title": "Setup project", "priority": 1, "parent": None,
                 "acceptance_criteria": ["Project initializes"], "estimated_complexity": "low"},
            ],
            "project": {"name": "test", "language": "Python", "framework": "FastAPI",
                        "description": "Test project"},
        })
        ndjson = json.dumps({"type": "text", "part": {"text": payload}})
        mock_result = MagicMock()
        mock_result.stdout = ndjson

        with patch("server.chatbot.subprocess.run", return_value=mock_result):
            result = _generate_tasks_fallback(state, None, "test-model")
        assert result is not None
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["title"] == "Setup project"
        assert result["project"]["name"] == "test"
