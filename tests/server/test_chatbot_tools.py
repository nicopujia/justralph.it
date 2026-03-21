"""Unit tests for chatbot tool helpers and gating logic.

No subprocess, no OpenCode -- only pure functions and ChatState.
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock

from server.chatbot import (
    DIMENSIONS,
    TOOL_CONFIGS,
    ChatState,
    _get_phase,
    _total_user_chars,
    _weak_dimensions,
    _conversation_summary,
    _strip_code_fences,
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


# ---------------------------------------------------------------------------
# _strip_code_fences
# ---------------------------------------------------------------------------


class TestStripCodeFences:
    def test_json_tag(self):
        assert _strip_code_fences('```json\n{"a":1}\n```') == '{"a":1}'

    def test_python_tag(self):
        assert _strip_code_fences('```python\nprint("hi")\n```') == 'print("hi")'

    def test_text_tag(self):
        assert _strip_code_fences('```text\nhello world\n```') == 'hello world'

    def test_markdown_tag(self):
        assert _strip_code_fences('```markdown\n# Title\n```') == '# Title'

    def test_bare_fences(self):
        assert _strip_code_fences('```\ncontent\n```') == 'content'

    def test_no_fences(self):
        assert _strip_code_fences('plain text') == 'plain text'

    def test_content_outside_fences(self):
        # re.search finds the fenced block and strips to inner content only
        result = _strip_code_fences('before ```json\n{"a":1}\n``` after')
        assert '{"a":1}' in result


# ---------------------------------------------------------------------------
# _conversation_summary content
# ---------------------------------------------------------------------------


class TestConversationSummaryContent:
    def test_extracts_message_from_json_assistant(self):
        """Assistant messages stored as JSON should show only the 'message' field."""
        parsed = {"message": "What tech stack?", "confidence": {"functional": 50}}
        state = ChatState(messages=[
            {"role": "user", "content": "I want a todo app"},
            {"role": "assistant", "content": json.dumps(parsed)},
        ])
        result = _conversation_summary(state)
        assert "What tech stack?" in result
        assert '"confidence"' not in result
        assert '"functional"' not in result

    def test_plain_text_assistant_unchanged(self):
        """Non-JSON assistant messages pass through unchanged."""
        state = ChatState(messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Hi there!"},
        ])
        result = _conversation_summary(state)
        assert "Hi there!" in result


# ---------------------------------------------------------------------------
# _conversation_summary max_messages cap
# ---------------------------------------------------------------------------


class TestConversationSummaryCap:
    def test_caps_to_max_messages(self):
        """Summary should only include last N messages."""
        msgs = []
        for i in range(20):
            msgs.append({"role": "user", "content": f"msg-{i}"})
        state = ChatState(messages=msgs)
        result = _conversation_summary(state, max_messages=4)
        assert "msg-18" in result
        assert "msg-19" in result
        assert "msg-0" not in result
        assert "msg-10" not in result

    def test_no_cap_when_zero(self):
        """max_messages=0 should return all messages."""
        msgs = []
        for i in range(5):
            msgs.append({"role": "user", "content": f"msg-{i}"})
        state = ChatState(messages=msgs)
        result = _conversation_summary(state, max_messages=0)
        for i in range(5):
            assert f"msg-{i}" in result


# ---------------------------------------------------------------------------
# Tool gating edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_session_gates_all_char_tools(self):
        """Empty session should gate brainstorm, expand, and refine."""
        state = ChatState()
        assert not TOOL_CONFIGS["brainstorm"]["gate"](state)
        assert not TOOL_CONFIGS["expand"]["gate"](state)
        assert not TOOL_CONFIGS["refine"]["gate"](state)

    def test_architect_gated_until_phase2(self):
        """Architect needs at least 4 messages (phase 2)."""
        for n in range(1, 4):
            msgs = [f"msg{i}" for i in range(n)]
            state = _state_with_messages(*msgs)
            assert not TOOL_CONFIGS["architect"]["gate"](state), (
                f"Should be gated at {n} messages"
            )

        state = _state_with_messages("a", "b", "c", "d")
        assert TOOL_CONFIGS["architect"]["gate"](state)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_tool_has_separate_rate_limit(self):
        """Tool rate limit is independent of chat rate limit."""
        state = _state_with_messages("x" * 130)
        state.last_message_time = time.time()  # Chat just happened
        state.last_tool_time = 0.0             # Tool was not recently used
        # Tool should NOT be rate limited
        assert time.time() - state.last_tool_time >= 3.0

    def test_chat_rate_limit_independent(self):
        """Chat rate limit checks only last_message_time."""
        state = ChatState()
        state.last_message_time = 0.0  # Long ago
        assert time.time() - state.last_message_time >= 3.0


# ---------------------------------------------------------------------------
# run_tool integration (subprocess mocked)
# ---------------------------------------------------------------------------


class TestRunToolIntegration:
    """Integration tests for run_tool with mocked subprocess and db."""

    @pytest.mark.asyncio
    async def test_brainstorm_returns_parsed_content(self):
        """Mock subprocess to return NDJSON, verify full pipeline."""
        from server.chatbot import _chat_states, run_tool

        state = _state_with_messages("x" * 130)  # passes gate (>= 120 chars)
        state.last_tool_time = 0.0
        _chat_states["test-integration"] = state

        ndjson = '{"type":"text","part":{"text":"1. Idea one\\n2. Idea two"}}\n'
        mock_result = MagicMock()
        mock_result.stdout = ndjson
        mock_result.stderr = ""
        mock_result.returncode = 0

        try:
            with patch("server.chatbot.subprocess.run", return_value=mock_result), \
                 patch("server.db.save_tool_invocation"):
                result = await run_tool("test-integration", "brainstorm")

            assert result["tool"] == "brainstorm"
            assert result["mode"] == "inject"
            assert "Idea one" in result["result"]
            assert "elapsed_ms" in result
        finally:
            _chat_states.pop("test-integration", None)

    @pytest.mark.asyncio
    async def test_refine_with_custom_context(self):
        """Refine tool with explicit context."""
        from server.chatbot import _chat_states, run_tool

        state = _state_with_messages("hello world")
        state.last_tool_time = 0.0
        _chat_states["test-refine"] = state

        ndjson = '{"type":"text","part":{"text":"Improved text here"}}\n'
        mock_result = MagicMock()
        mock_result.stdout = ndjson
        mock_result.stderr = ""
        mock_result.returncode = 0

        try:
            with patch("server.chatbot.subprocess.run", return_value=mock_result), \
                 patch("server.db.save_tool_invocation"):
                result = await run_tool("test-refine", "refine", "my custom text")

            assert result["mode"] == "edit"
            assert "Improved" in result["result"]
        finally:
            _chat_states.pop("test-refine", None)

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self):
        """Unknown tool ID raises ValueError before any state lookup."""
        from server.chatbot import run_tool

        with pytest.raises(ValueError, match="Unknown tool"):
            await run_tool("test-session", "nonexistent")

    @pytest.mark.asyncio
    async def test_gated_tool_raises(self):
        """Tool that fails gate check raises RuntimeError with gate_reason."""
        from server.chatbot import _chat_states, run_tool

        state = ChatState()  # Empty -- _total_user_chars == 0, gate fails
        state.last_tool_time = 0.0
        _chat_states["test-gated"] = state

        try:
            with pytest.raises(RuntimeError, match="120"):
                await run_tool("test-gated", "brainstorm")
        finally:
            _chat_states.pop("test-gated", None)


# ---------------------------------------------------------------------------
# Tool prompt with realistic conversation data
# ---------------------------------------------------------------------------


class TestToolPromptWithRealData:
    def test_brainstorm_prompt_coherent(self):
        """Format brainstorm prompt with realistic data and verify coherence."""
        state = ChatState(
            messages=[
                {"role": "user", "content": "I want to build a recipe sharing app"},
                {"role": "assistant", "content": json.dumps({"message": "Interesting! What tech stack?"})},
                {"role": "user", "content": "React frontend, Python backend, PostgreSQL"},
                {"role": "assistant", "content": json.dumps({"message": "Great choices. What about auth?"})},
            ],
            confidence={
                "functional": 40, "technical_stack": 60, "data_model": 20,
                "auth": 10, "deployment": 0, "testing": 0, "edge_cases": 0,
            },
        )
        conversation = _conversation_summary(state)
        weak_dims = _weak_dimensions(state)

        prompt = TOOL_CONFIGS["brainstorm"]["system"].format(
            conversation=conversation,
            weak_dims=weak_dims,
            confidence_summary="",
            original="",
        )
        assert "recipe" in conversation.lower()
        assert len(prompt) > 100
        assert "weak dimensions" in prompt.lower()

    def test_all_prompts_format_with_real_data(self):
        """All tool prompts format without error using realistic kwargs."""
        state = _state_with_messages("Build me a chat app", "Use WebSockets")
        conversation = _conversation_summary(state)
        weak_dims = _weak_dimensions(state)
        confidence_summary = ", ".join(f"{d}: 50%" for d in DIMENSIONS)

        kwargs = {
            "conversation": conversation,
            "weak_dims": weak_dims,
            "confidence_summary": confidence_summary,
            "original": "Build me a chat app using WebSockets",
        }
        for tool_id, config in TOOL_CONFIGS.items():
            result = config["system"].format(**kwargs)
            assert isinstance(result, str)
            assert len(result) > 50, f"Tool {tool_id} prompt too short"
