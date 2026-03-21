"""Unit tests for undo_last_message() in server/chatbot.py.

No subprocess, no OpenCode. Mocks all DB calls and controls _chat_states directly.
"""

import json

import pytest

from server.chatbot import (
    DIMENSIONS,
    ChatState,
    _chat_states,
    undo_last_message,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_chat_states():
    """Isolate each test: clear in-memory chat state before and after."""
    _chat_states.clear()
    yield
    _chat_states.clear()


@pytest.fixture
def mock_db(monkeypatch):
    """Replace all DB calls with no-ops."""
    monkeypatch.setattr("server.chatbot.db.delete_chat_messages", lambda sid: None)
    monkeypatch.setattr("server.chatbot.db.save_chat_message", lambda sid, role, content: None)
    monkeypatch.setattr("server.chatbot.db.save_chat_state", lambda *a, **kw: None)
    monkeypatch.setattr("server.chatbot.db.load_chat_state", lambda sid: None)
    monkeypatch.setattr("server.chatbot.db.load_chat_messages", lambda sid: [])


def _make_assistant_content(confidence: dict | None = None, relevance: dict | None = None) -> str:
    """Build a valid JSON assistant message string."""
    conf = confidence or {d: 50 for d in DIMENSIONS}
    rel = relevance or {d: 1.0 for d in DIMENSIONS}
    return json.dumps({
        "message": "Got it, next question.",
        "confidence": conf,
        "relevance": rel,
        "contradictions": [],
        "ready": False,
    })


def _seed_state(session_id: str, messages: list[dict]) -> ChatState:
    """Insert a ChatState with given messages into _chat_states."""
    state = ChatState(messages=messages)
    _chat_states[session_id] = state
    return state


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------


def test_undo_raises_with_no_messages(mock_db):
    """Empty messages list -> RuntimeError('Nothing to undo')."""
    _seed_state("s1", [])
    with pytest.raises(RuntimeError, match="Nothing to undo"):
        undo_last_message("s1")


def test_undo_raises_with_one_message(mock_db):
    """Single message (only user, no assistant pair) -> RuntimeError."""
    _seed_state("s1", [{"role": "user", "content": "hello"}])
    with pytest.raises(RuntimeError, match="Nothing to undo"):
        undo_last_message("s1")


# ---------------------------------------------------------------------------
# Message removal
# ---------------------------------------------------------------------------


def test_undo_removes_last_pair(mock_db):
    """4 messages (2 user+assistant pairs) -> 2 remain after undo."""
    messages = [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": _make_assistant_content()},
        {"role": "user", "content": "second question"},
        {"role": "assistant", "content": _make_assistant_content()},
    ]
    _seed_state("s1", messages)

    result = undo_last_message("s1")

    state = _chat_states["s1"]
    assert len(state.messages) == 2
    assert result["message_count"] == 2
    assert state.messages[0]["role"] == "user"
    assert state.messages[1]["role"] == "assistant"


def test_undo_with_exactly_two_messages(mock_db):
    """Minimum viable undo: 1 user + 1 assistant -> 0 messages remain."""
    _seed_state("s1", [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": _make_assistant_content()},
    ])

    result = undo_last_message("s1")

    state = _chat_states["s1"]
    assert len(state.messages) == 0
    assert result["message_count"] == 0
    assert result["question_count"] == 0


# ---------------------------------------------------------------------------
# Confidence replay
# ---------------------------------------------------------------------------


def test_undo_resets_and_replays_confidence(mock_db):
    """Confidence after undo reflects replay of remaining msgs, not prior state."""
    first_conf = {d: 30 for d in DIMENSIONS}
    second_conf = {d: 99 for d in DIMENSIONS}  # this pair gets removed

    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": _make_assistant_content(confidence=first_conf)},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": _make_assistant_content(confidence=second_conf)},
    ]
    state = _seed_state("s1", messages)
    # Pre-set high confidence to verify it gets reset, not carried over
    state.confidence = {d: 99 for d in DIMENSIONS}

    result = undo_last_message("s1")

    # After undo, only the first assistant message is replayed.
    # Confidence must be lower than 99 (second pair was removed).
    for dim in DIMENSIONS:
        assert result["confidence"][dim] < 99, (
            f"{dim} confidence should be replayed from first msg only, got {result['confidence'][dim]}"
        )


def test_undo_zeros_confidence_when_no_assistant_messages_remain(mock_db):
    """After removing the only pair, confidence resets to all zeros."""
    _seed_state("s1", [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": _make_assistant_content({d: 60 for d in DIMENSIONS})},
    ])

    result = undo_last_message("s1")

    for dim in DIMENSIONS:
        assert result["confidence"][dim] == 0


# ---------------------------------------------------------------------------
# Return shape
# ---------------------------------------------------------------------------


def test_undo_returns_correct_shape(mock_db):
    """Return dict must have all expected keys."""
    _seed_state("s1", [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": _make_assistant_content()},
    ])

    result = undo_last_message("s1")

    required_keys = {
        "confidence", "relevance", "ready",
        "weighted_readiness", "question_count", "phase", "message_count",
    }
    assert required_keys <= result.keys(), (
        f"Missing keys: {required_keys - result.keys()}"
    )
    assert isinstance(result["confidence"], dict)
    assert isinstance(result["relevance"], dict)
    assert isinstance(result["ready"], bool)
    assert isinstance(result["weighted_readiness"], float)
    assert isinstance(result["question_count"], int)
    assert isinstance(result["phase"], int)
    assert isinstance(result["message_count"], int)


# ---------------------------------------------------------------------------
# Unparseable assistant JSON
# ---------------------------------------------------------------------------


def test_undo_handles_unparseable_assistant_json(mock_db):
    """Malformed assistant JSON is skipped during replay -- no crash."""
    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "not valid json {{{"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": _make_assistant_content()},
    ]
    _seed_state("s1", messages)

    # Should not raise; malformed message is silently skipped
    result = undo_last_message("s1")

    # Only the first assistant msg remains; it was unparseable so confidence stays 0
    assert result["message_count"] == 2
    for dim in DIMENSIONS:
        assert result["confidence"][dim] == 0


def test_undo_skips_contradicted_turns_during_replay(mock_db):
    """Assistant messages with non-empty contradictions are skipped in replay."""
    contradicted_content = json.dumps({
        "message": "contradiction detected",
        "confidence": {d: 80 for d in DIMENSIONS},
        "relevance": {d: 1.0 for d in DIMENSIONS},
        "contradictions": ["You said Python before, now JavaScript."],
        "ready": False,
    })
    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": contradicted_content},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": _make_assistant_content()},
    ]
    _seed_state("s1", messages)

    result = undo_last_message("s1")

    # After removing last pair, only the contradicted turn remains.
    # Contradicted turn is skipped -> confidence stays 0.
    assert result["message_count"] == 2
    for dim in DIMENSIONS:
        assert result["confidence"][dim] == 0


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------


def test_undo_persists_to_db(monkeypatch):
    """Verify delete_chat_messages, save_chat_message, save_chat_state are called."""
    delete_calls: list[str] = []
    save_msg_calls: list[tuple] = []
    save_state_calls: list[tuple] = []

    monkeypatch.setattr(
        "server.chatbot.db.delete_chat_messages",
        lambda sid: delete_calls.append(sid),
    )
    monkeypatch.setattr(
        "server.chatbot.db.save_chat_message",
        lambda sid, role, content: save_msg_calls.append((sid, role, content)),
    )
    monkeypatch.setattr(
        "server.chatbot.db.save_chat_state",
        lambda *a, **kw: save_state_calls.append(a),
    )
    monkeypatch.setattr("server.chatbot.db.load_chat_state", lambda sid: None)
    monkeypatch.setattr("server.chatbot.db.load_chat_messages", lambda sid: [])

    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": _make_assistant_content()},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": _make_assistant_content()},
    ]
    _seed_state("s1", messages)

    undo_last_message("s1")

    # delete_chat_messages called once for session
    assert delete_calls == ["s1"]

    # save_chat_message called once per remaining message (2 remain)
    assert len(save_msg_calls) == 2
    assert all(sid == "s1" for sid, _, _ in save_msg_calls)

    # save_chat_state called at least once
    assert len(save_state_calls) >= 1
    assert save_state_calls[0][0] == "s1"
