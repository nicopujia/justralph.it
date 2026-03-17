"""Tests for ralph.agent."""

from unittest.mock import patch, MagicMock

import pytest

import bd
from ralph.agent import Agent


@pytest.fixture
def issue():
    return bd.Issue(id="test-1", title="test issue")


@pytest.fixture
def prompt_file(tmp_path):
    f = tmp_path / "PROMPT.md"
    f.write_text("Work on {self.issue.id}.")
    return f


@pytest.fixture
def agent(issue, prompt_file):
    return Agent(issue=issue, model="test-model", prompt_file=prompt_file)


def _mock_popen(mock, stdout_lines):
    """Wire up a mock Popen with given stdout lines."""
    proc = MagicMock()
    proc.stdout = stdout_lines
    proc.wait.return_value = 0
    proc.__enter__ = lambda s: s
    proc.__exit__ = MagicMock(return_value=False)
    mock.return_value = proc


class TestGetattr:
    def test_status_returns_instruction_string(self, agent):
        result = agent.DONE
        assert "<status>" in result
        assert "COMPLETED ASSIGNED ISSUE" in result
        assert agent.status == Agent.Status.DONE

    def test_invalid_status_raises(self, agent):
        with pytest.raises(KeyError):
            _ = agent.NONEXISTENT


class TestRun:
    @patch("ralph.agent.subprocess.Popen")
    def test_parses_status_from_last_line(self, mock_popen, agent):
        _mock_popen(mock_popen, [
            "working...\n",
            "<status>COMPLETED ASSIGNED ISSUE</status>\n",
        ])
        lines = list(agent.run())
        assert len(lines) == 2
        assert agent.status == Agent.Status.DONE

    @patch("ralph.agent.subprocess.Popen")
    def test_no_output_falls_back_to_idle(self, mock_popen, agent):
        _mock_popen(mock_popen, iter([]))
        list(agent.run())
        assert agent.status == Agent.Status.IDLE

    @patch("ralph.agent.subprocess.Popen")
    def test_invalid_xml_falls_back_to_idle(self, mock_popen, agent):
        _mock_popen(mock_popen, ["not xml\n"])
        list(agent.run())
        assert agent.status == Agent.Status.IDLE

    @patch("ralph.agent.subprocess.Popen")
    def test_unknown_status_falls_back_to_idle(self, mock_popen, agent):
        _mock_popen(mock_popen, ["<status>GARBAGE</status>\n"])
        list(agent.run())
        assert agent.status == Agent.Status.IDLE

    @patch("ralph.agent.subprocess.Popen")
    def test_prompt_includes_issue_id(self, mock_popen, agent):
        _mock_popen(mock_popen, ["<status>COMPLETED ASSIGNED ISSUE</status>\n"])
        list(agent.run())
        prompt_arg = mock_popen.call_args[0][0][2]
        assert "test-1" in prompt_arg
