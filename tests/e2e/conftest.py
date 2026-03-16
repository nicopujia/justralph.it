import pytest


@pytest.fixture(scope="session")
def base_url(request):
    """Base URL for the running app. Overridden by --base-url CLI flag."""
    # Support pytest-base-url plugin's --base-url option
    config_url = request.config.getoption("base_url", default=None)
    if config_url:
        return config_url
    return "http://localhost:8000"
