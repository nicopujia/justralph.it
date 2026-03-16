"""Tests for ralph_template.py — the generic, reusable Ralph loop template.

Tests verify:
- ralph_template.py exists and is a valid Python file
- ralph_template.py is generic (no justralph.it-specific code)
- ralph_template.py contains all essential generic components
- ralph_template.py uses dynamic path resolution
- ralph.py remains the justralph.it-specific version (unchanged)
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RALPH_TEMPLATE = REPO_ROOT / "ralph_template.py"
RALPH_PY = REPO_ROOT / "ralph.py"


def _read(path: Path) -> str:
    return path.read_text()


# ===========================================================================
# Test: ralph_template.py exists
# ===========================================================================


class TestRalphTemplateExists:
    def test_file_exists(self):
        assert RALPH_TEMPLATE.exists(), "ralph_template.py must exist in the repo root"

    def test_file_is_not_empty(self):
        content = _read(RALPH_TEMPLATE)
        assert len(content.strip()) > 0, "ralph_template.py must not be empty"


# ===========================================================================
# Test: ralph_template.py does NOT contain justralph.it-specific code
# ===========================================================================


class TestRalphTemplateIsGeneric:
    """ralph_template.py must be free of justralph.it-specific references."""

    def test_no_app_imports(self):
        """Must not import from the app package (e.g., 'from app.subprocess_env')."""
        content = _read(RALPH_TEMPLATE)
        assert "from app." not in content, (
            "ralph_template.py must not contain 'from app.' imports — it should inline its dependencies"
        )

    def test_no_hardcoded_just_ralph_it_paths(self):
        """Must not contain hardcoded 'just-ralph-it' in path definitions."""
        content = _read(RALPH_TEMPLATE)
        assert "just-ralph-it" not in content, (
            "ralph_template.py must not contain 'just-ralph-it' — paths should be dynamic"
        )

    def test_no_reload_production_function(self):
        """Must not define reload_production() — that's justralph.it-specific."""
        content = _read(RALPH_TEMPLATE)
        assert "def reload_production" not in content, (
            "ralph_template.py must not define reload_production() — that's specific to justralph.it"
        )

    def test_no_service_reference(self):
        """Must not reference 'just-ralph-it.service'."""
        content = _read(RALPH_TEMPLATE)
        assert "just-ralph-it.service" not in content, "ralph_template.py must not reference 'just-ralph-it.service'"


# ===========================================================================
# Test: ralph_template.py contains essential generic components
# ===========================================================================


class TestRalphTemplateHasEssentialComponents:
    """ralph_template.py must contain all the core Ralph loop machinery."""

    def test_has_results_class(self):
        content = _read(RALPH_TEMPLATE)
        assert "class Results" in content, "ralph_template.py must define the Results class"

    def test_has_subprocess_env_function(self):
        """subprocess_env must be inlined (defined locally), not imported."""
        content = _read(RALPH_TEMPLATE)
        assert "def subprocess_env" in content, (
            "ralph_template.py must define subprocess_env() locally (inlined, not imported)"
        )

    def test_has_main_function(self):
        content = _read(RALPH_TEMPLATE)
        assert "def main" in content, "ralph_template.py must define main()"

    def test_has_get_prompt_function(self):
        content = _read(RALPH_TEMPLATE)
        assert "def get_prompt" in content, "ralph_template.py must define get_prompt()"

    def test_has_check_resources_function(self):
        content = _read(RALPH_TEMPLATE)
        assert "def check_resources" in content, "ralph_template.py must define check_resources()"

    def test_has_output_function(self):
        content = _read(RALPH_TEMPLATE)
        assert "def output" in content, "ralph_template.py must define output()"

    def test_has_setup_logging_function(self):
        content = _read(RALPH_TEMPLATE)
        assert "def setup_logging" in content, "ralph_template.py must define setup_logging()"

    def test_has_get_in_progress_issue_function(self):
        content = _read(RALPH_TEMPLATE)
        assert "def get_in_progress_issue" in content, "ralph_template.py must define get_in_progress_issue()"

    def test_has_get_next_ready_issue_function(self):
        content = _read(RALPH_TEMPLATE)
        assert "def get_next_ready_issue" in content, "ralph_template.py must define get_next_ready_issue()"

    def test_has_get_issue_by_id_function(self):
        content = _read(RALPH_TEMPLATE)
        assert "def get_issue_by_id" in content, "ralph_template.py must define get_issue_by_id()"


# ===========================================================================
# Test: ralph_template.py uses dynamic path resolution
# ===========================================================================


class TestRalphTemplateDynamicPaths:
    """ralph_template.py must resolve paths relative to its own location."""

    def test_uses_path_file_for_project_dir(self):
        """PROJECT_DIR must be derived from __file__, not hardcoded."""
        content = _read(RALPH_TEMPLATE)
        assert "Path(__file__)" in content, "ralph_template.py must use Path(__file__) for dynamic path resolution"

    def test_project_dir_assignment(self):
        """PROJECT_DIR should be assigned from Path(__file__).resolve().parent."""
        content = _read(RALPH_TEMPLATE)
        assert "PROJECT_DIR" in content, "ralph_template.py must define PROJECT_DIR"
        # Verify it's derived from __file__
        for line in content.splitlines():
            if line.strip().startswith("PROJECT_DIR"):
                assert "__file__" in line, f"PROJECT_DIR must be derived from __file__, got: {line.strip()}"
                break

    def test_no_path_home_hardcoded_paths(self):
        """Must not use Path.home() / 'projects' / 'just-ralph-it' style paths."""
        content = _read(RALPH_TEMPLATE)
        assert "Path.home()" not in content or "just-ralph-it" not in content, (
            "ralph_template.py must not use Path.home()-based hardcoded paths to just-ralph-it"
        )


# ===========================================================================
# Test: ralph.py STILL contains justralph.it-specific code
# ===========================================================================


class TestRalphPyRemainsSpecific:
    """ralph.py must still be the justralph.it-specific version (not accidentally genericized)."""

    def test_ralph_py_exists(self):
        assert RALPH_PY.exists(), "ralph.py must exist in the repo root"

    def test_ralph_py_imports_from_app(self):
        """ralph.py should still import subprocess_env from app."""
        content = _read(RALPH_PY)
        assert "from app.subprocess_env import subprocess_env" in content, (
            "ralph.py must still import subprocess_env from app.subprocess_env"
        )

    def test_ralph_py_has_reload_production(self):
        """ralph.py should still define reload_production()."""
        content = _read(RALPH_PY)
        assert "def reload_production" in content, "ralph.py must still define reload_production()"

    def test_ralph_py_has_hardcoded_paths(self):
        """ralph.py should still use hardcoded 'just-ralph-it' paths."""
        content = _read(RALPH_PY)
        assert "just-ralph-it" in content, "ralph.py must still contain hardcoded 'just-ralph-it' paths"

    def test_ralph_py_references_service(self):
        """ralph.py should still reference 'just-ralph-it.service'."""
        content = _read(RALPH_PY)
        assert "just-ralph-it.service" in content, (
            "ralph.py must still reference 'just-ralph-it.service' in reload_production()"
        )
