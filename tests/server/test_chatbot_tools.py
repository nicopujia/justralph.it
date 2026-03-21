"""Unit tests for chatbot tool helpers and gating logic.

No subprocess, no OpenCode -- only pure functions and ChatState.
"""

import pytest

from server.chatbot import (
    DIMENSIONS,
    TOOL_CONFIGS,
    ChatState,
    _get_phase,
    _total_user_chars,
    _weak_dimensions,
    _conversation_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_with_messages(*user_messages: str) -> ChatState:
    """Build a ChatState with alternating user/assistant messages."""
    msgs: list[dict] = []
    for i, text in enumerate(user_messages):
        msgs.append({"role": "user", "content": text})
        msgs.append({"role": "assistant", "content": f"Response to: {text}"})
    return ChatState(messages=msgs)


def _state_with_confidence(overrides: dict[str, int] | None = None) -> ChatState:
    """Build a ChatState with custom confidence scores."""
    conf = {d: 50 for d in DIMENSIONS}
    if overrides:
        conf.update(overrides)
    return ChatState(
        messages=[
            {"role": "user", "content": "x" * 130},
            {"role": "assistant", "content": "ok"},
        ],
        confidence=conf,
    )


# ---------------------------------------------------------------------------
# _total_user_chars
# ---------------------------------------------------------------------------


class TestTotalUserChars:
    def test_empty(self):
        state = ChatState()
        assert _total_user_chars(state) == 0

    def test_counts_only_user(self):
        state = ChatState(messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there, this is longer"},
            {"role": "user", "content": "world"},
        ])
        assert _total_user_chars(state) == 10  # 5 + 5

    def test_long_messages(self):
        state = ChatState(messages=[
            {"role": "user", "content": "a" * 100},
            {"role": "user", "content": "b" * 50},
        ])
        assert _total_user_chars(state) == 150


# ---------------------------------------------------------------------------
# _weak_dimensions
# ---------------------------------------------------------------------------


class TestWeakDimensions:
    def test_returns_n_weakest(self):
        state = _state_with_confidence({
            "functional": 90,
            "technical_stack": 10,
            "data_model": 20,
            "auth": 30,
            "deployment": 80,
            "testing": 70,
            "edge_cases": 5,
        })
        result = _weak_dimensions(state, n=3)
        # Should contain the 3 lowest: edge_cases(5), technical_stack(10), data_model(20)
        assert "edge_cases (5%)" in result
        assert "technical_stack (10%)" in result
        assert "data_model (20%)" in result

    def test_excludes_irrelevant(self):
        state = _state_with_confidence({"auth": 0, "functional": 90})
        state.relevance["auth"] = 0.1  # below RELEVANCE_CUTOFF
        result = _weak_dimensions(state, n=7)
        assert "auth" not in result

    def test_fewer_than_n(self):
        # If only 2 relevant dims, should return 2 not crash
        state = _state_with_confidence()
        for d in DIMENSIONS:
            state.relevance[d] = 0.0
        state.relevance["functional"] = 1.0
        state.relevance["testing"] = 1.0
        result = _weak_dimensions(state, n=5)
        parts = result.split(", ")
        assert len(parts) == 2


# ---------------------------------------------------------------------------
# _conversation_summary
# ---------------------------------------------------------------------------


class TestConversationSummary:
    def test_empty(self):
        state = ChatState()
        assert _conversation_summary(state) == ""

    def test_formats_roles(self):
        state = ChatState(messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ])
        result = _conversation_summary(state)
        assert "**User:** hello" in result
        assert "**Ralphy:** hi" in result


# ---------------------------------------------------------------------------
# Tool gating
# ---------------------------------------------------------------------------


class TestToolGating:
    def test_brainstorm_below_threshold(self):
        state = _state_with_messages("short")  # < 120 chars
        assert not TOOL_CONFIGS["brainstorm"]["gate"](state)

    def test_brainstorm_above_threshold(self):
        state = _state_with_messages("x" * 130)
        assert TOOL_CONFIGS["brainstorm"]["gate"](state)

    def test_expand_below_threshold(self):
        state = _state_with_messages("tiny")
        assert not TOOL_CONFIGS["expand"]["gate"](state)

    def test_expand_above_threshold(self):
        state = _state_with_messages("y" * 120)
        assert TOOL_CONFIGS["expand"]["gate"](state)

    def test_refine_no_messages(self):
        state = ChatState()
        assert not TOOL_CONFIGS["refine"]["gate"](state)

    def test_refine_with_messages(self):
        state = _state_with_messages("hello")
        assert TOOL_CONFIGS["refine"]["gate"](state)

    def test_architect_phase1(self):
        # 1-3 messages = phase 1
        state = _state_with_messages("a", "b", "c")
        assert _get_phase(state.user_msg_count) == 1
        assert not TOOL_CONFIGS["architect"]["gate"](state)

    def test_architect_phase2(self):
        # 4+ messages = phase 2
        state = _state_with_messages("a", "b", "c", "d")
        assert _get_phase(state.user_msg_count) == 2
        assert TOOL_CONFIGS["architect"]["gate"](state)


# ---------------------------------------------------------------------------
# Tool config structure
# ---------------------------------------------------------------------------


class TestToolConfigs:
    @pytest.mark.parametrize("tool_id", ["brainstorm", "expand", "refine", "architect"])
    def test_has_required_keys(self, tool_id):
        config = TOOL_CONFIGS[tool_id]
        assert "mode" in config
        assert config["mode"] in ("edit", "inject")
        assert "gate" in config
        assert callable(config["gate"])
        assert "gate_reason" in config
        assert isinstance(config["gate_reason"], str)
        assert "system" in config
        assert isinstance(config["system"], str)

    def test_brainstorm_is_inject(self):
        assert TOOL_CONFIGS["brainstorm"]["mode"] == "inject"

    def test_expand_is_inject(self):
        assert TOOL_CONFIGS["expand"]["mode"] == "inject"

    def test_refine_is_edit(self):
        assert TOOL_CONFIGS["refine"]["mode"] == "edit"

    def test_architect_is_inject(self):
        assert TOOL_CONFIGS["architect"]["mode"] == "inject"


# ---------------------------------------------------------------------------
# Tool prompt formatting
# ---------------------------------------------------------------------------


class TestToolPromptFormatting:
    def test_brainstorm_prompt_includes_context(self):
        prompt = TOOL_CONFIGS["brainstorm"]["system"]
        # Should have format placeholders
        assert "{conversation}" in prompt
        assert "{weak_dims}" in prompt

    def test_refine_prompt_includes_original(self):
        prompt = TOOL_CONFIGS["refine"]["system"]
        assert "{original}" in prompt
        assert "{conversation}" in prompt

    def test_architect_prompt_includes_confidence(self):
        prompt = TOOL_CONFIGS["architect"]["system"]
        assert "{confidence_summary}" in prompt
        assert "{weak_dims}" in prompt

    def test_prompts_can_be_formatted(self):
        """All tool prompts should format without errors given the expected kwargs."""
        kwargs = {
            "conversation": "test conversation",
            "weak_dims": "functional (10%), testing (20%)",
            "confidence_summary": "functional: 10%",
            "original": "original text",
        }
        for tool_id, config in TOOL_CONFIGS.items():
            # Should not raise
            result = config["system"].format(**kwargs)
            assert isinstance(result, str)
            assert len(result) > 0
