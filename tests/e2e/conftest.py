import pytest


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the running app. Overridden by --base-url CLI flag."""
    return "http://localhost:8000"
