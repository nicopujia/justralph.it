"""Tests for app.subprocess_env — PATH augmentation for subprocess calls."""

import os
from unittest.mock import patch

from app.subprocess_env import subprocess_env


class TestSubprocessEnv:
    def test_includes_local_bin_in_path(self):
        env = subprocess_env()
        path_dirs = env["PATH"].split(os.pathsep)
        assert os.path.expanduser("~/.local/bin") in path_dirs

    def test_includes_npm_global_bin_in_path(self):
        env = subprocess_env()
        path_dirs = env["PATH"].split(os.pathsep)
        assert os.path.expanduser("~/.npm-global/bin") in path_dirs

    def test_extra_dirs_prepended_not_appended(self):
        env = subprocess_env()
        path = env["PATH"]
        local_bin = os.path.expanduser("~/.local/bin")
        # local_bin should appear before the original PATH entries
        assert path.startswith(local_bin) or path.startswith(os.path.expanduser("~/.npm-global/bin"))

    def test_extra_kwargs_merged(self):
        env = subprocess_env(BEADS_DOLT_SHARED_SERVER="1")
        assert env["BEADS_DOLT_SHARED_SERVER"] == "1"

    def test_extra_kwargs_override_environ(self):
        with patch.dict(os.environ, {"FOO": "original"}):
            env = subprocess_env(FOO="override")
            assert env["FOO"] == "override"

    def test_no_duplicate_dirs_when_already_present(self):
        local_bin = os.path.expanduser("~/.local/bin")
        npm_bin = os.path.expanduser("~/.npm-global/bin")
        fake_path = os.pathsep.join([local_bin, npm_bin, "/usr/bin"])
        with patch.dict(os.environ, {"PATH": fake_path}):
            env = subprocess_env()
            path_dirs = env["PATH"].split(os.pathsep)
            # Each dir should appear exactly once
            assert path_dirs.count(local_bin) == 1
            assert path_dirs.count(npm_bin) == 1

    def test_preserves_existing_env_vars(self):
        with patch.dict(os.environ, {"MY_VAR": "hello"}):
            env = subprocess_env()
            assert env["MY_VAR"] == "hello"
