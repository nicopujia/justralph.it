"""Tests for the Ralphy system prompt (TDD — written before implementation).

Feature: Adapt Ralphy system prompt for web context.

The system prompt at .opencode/agents/RALPHY.md must:
1. Have show_just_ralph_it_button enabled in frontmatter tools
2. Instruct calling show_just_ralph_it_button when the spec is complete (Phase 4)
3. Instruct calling show_just_ralph_it_button when user says "done" after HUMAN_NEEDED
4. Instruct always running `bd list` for recaps — never from memory
5. Constrain issue modification to open unclaimed issues only (already present)
"""

import os
import re

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROMPT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    ".opencode",
    "agents",
    "RALPHY.md",
)


def _read_prompt():
    """Read the RALPHY.md file and return its full text."""
    with open(PROMPT_PATH) as f:
        return f.read()


def _parse_frontmatter(text):
    """Extract and parse the YAML frontmatter from a markdown file.

    Expects the file to start with '---' and have a closing '---'.
    Returns the parsed YAML as a dict.
    """
    match = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
    assert match, "RALPHY.md must have YAML frontmatter delimited by ---"
    return yaml.safe_load(match.group(1))


def _get_phase4_section(text):
    """Extract the Phase 4 section text from the prompt."""
    # Find Phase 4 heading and grab everything until the next --- or ## heading
    match = re.search(
        r"(## Phase 4.*?)(?=\n---|\n## [^#]|\Z)",
        text,
        re.DOTALL,
    )
    assert match, "RALPHY.md must contain a Phase 4 section"
    return match.group(1)


# ===========================================================================
# Test 1: Frontmatter has show_just_ralph_it_button tool enabled
# ===========================================================================


class TestFrontmatterToolEnabled:
    """The RALPHY.md frontmatter must list show_just_ralph_it_button in tools."""

    def test_show_just_ralph_it_button_in_tools(self):
        """show_just_ralph_it_button is enabled (true) in the tools section."""
        text = _read_prompt()
        fm = _parse_frontmatter(text)
        tools = fm.get("tools", {})
        assert "show_just_ralph_it_button" in tools, "tools section must include show_just_ralph_it_button"
        assert tools["show_just_ralph_it_button"] is True, "show_just_ralph_it_button must be set to true"


# ===========================================================================
# Test 2: Phase 4 instructs calling show_just_ralph_it_button on spec completion
# ===========================================================================


class TestSpecCompleteCallsButton:
    """Phase 4 must instruct Ralphy to call show_just_ralph_it_button when done."""

    def test_phase4_mentions_show_just_ralph_it_button(self):
        """Phase 4 section references calling show_just_ralph_it_button."""
        text = _read_prompt()
        phase4 = _get_phase4_section(text)
        assert "show_just_ralph_it_button" in phase4, (
            "Phase 4 must instruct calling show_just_ralph_it_button when spec is complete"
        )

    def test_phase4_mentions_slug(self):
        """Phase 4 section mentions passing the project slug to the tool."""
        text = _read_prompt()
        phase4 = _get_phase4_section(text)
        assert "slug" in phase4.lower(), "Phase 4 must mention passing the project slug to show_just_ralph_it_button"


# ===========================================================================
# Test 3: HUMAN_NEEDED resume behavior
# ===========================================================================


class TestHumanNeededResume:
    """Prompt must instruct calling show_just_ralph_it_button after HUMAN_NEEDED."""

    def test_prompt_mentions_human_needed(self):
        """Prompt contains instructions about HUMAN_NEEDED stops."""
        text = _read_prompt()
        assert "HUMAN_NEEDED" in text, "Prompt must contain instructions about HUMAN_NEEDED stops"

    def test_prompt_calls_button_on_done_after_human_needed(self):
        """Prompt instructs calling show_just_ralph_it_button when user says 'done'."""
        text = _read_prompt()
        # The prompt should mention both HUMAN_NEEDED and show_just_ralph_it_button
        # in a way that connects "done" -> call the button
        assert "show_just_ralph_it_button" in text, "Prompt must reference show_just_ralph_it_button"
        # Find a section that discusses HUMAN_NEEDED and verify it mentions the button
        # Look for HUMAN_NEEDED context that also references the button tool
        human_needed_pattern = re.search(
            r"HUMAN_NEEDED.*?show_just_ralph_it_button|show_just_ralph_it_button.*?HUMAN_NEEDED",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        assert human_needed_pattern, "Prompt must connect HUMAN_NEEDED stops with calling show_just_ralph_it_button"

    def test_prompt_mentions_done_keyword_for_resume(self):
        """Prompt mentions user saying 'done' to resume after HUMAN_NEEDED."""
        text = _read_prompt()
        # Should mention "done" in context of HUMAN_NEEDED
        lower = text.lower()
        human_idx = lower.find("human_needed")
        assert human_idx != -1, "Must mention HUMAN_NEEDED"
        # "done" should appear in the same section (within 500 chars)
        nearby = lower[max(0, human_idx - 500) : human_idx + 500]
        assert "done" in nearby, "Prompt must mention user saying 'done' near HUMAN_NEEDED instructions"


# ===========================================================================
# Test 4: Always use bd list for recaps
# ===========================================================================


class TestBdListForRecaps:
    """Prompt must instruct always running `bd list` before recapping."""

    def test_prompt_instructs_bd_list_for_recaps(self):
        """Prompt contains instruction to run bd list for recaps."""
        text = _read_prompt()
        assert "bd list" in text, "Prompt must instruct running `bd list` for recaps"

    def test_prompt_forbids_recapping_from_memory(self):
        """Prompt explicitly forbids recapping from memory."""
        text = _read_prompt()
        lower = text.lower()
        assert "never" in lower and "memory" in lower, "Prompt must say to never recap from memory"

    def test_recap_instruction_connects_bd_list_and_memory(self):
        """The recap instruction connects bd list usage with not using memory."""
        text = _read_prompt()
        lower = text.lower()
        # Find the section about recaps — bd list and memory should be nearby
        bd_list_idx = lower.find("bd list")
        assert bd_list_idx != -1, "Must mention bd list"
        nearby = lower[max(0, bd_list_idx - 300) : bd_list_idx + 300]
        assert "memory" in nearby, "Instructions about bd list and not using memory must be in the same section"


# ===========================================================================
# Test 5: Issue modification constraint (already present)
# ===========================================================================


class TestIssueModificationConstraint:
    """Prompt must constrain issue modification to open unclaimed issues only."""

    def test_cannot_modify_in_progress_issues(self):
        """Prompt states Ralphy cannot modify in-progress or claimed issues."""
        text = _read_prompt()
        lower = text.lower()
        # The existing constraint at line 38 mentions "in-progress" and "claimed"
        assert "in-progress" in lower or "in progress" in lower, (
            "Prompt must mention in-progress issues cannot be modified"
        )
        assert "claimed" in lower, "Prompt must mention claimed issues cannot be modified"

    def test_can_only_create_or_update_open_unclaimed(self):
        """Prompt states Ralphy can only create new or update open unclaimed issues."""
        text = _read_prompt()
        # This is the existing text at line 38
        assert "create new beads issues" in text, "Prompt must mention creating new beads issues"
        assert "open and not yet claimed" in text, "Prompt must mention only updating open and not yet claimed issues"
