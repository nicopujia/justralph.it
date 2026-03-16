import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_homepage_title(page: Page, base_url: str):
    """Smoke test: homepage loads with correct title."""
    page.goto(base_url)
    expect(page).to_have_title("justralph.it")


@pytest.mark.e2e
def test_homepage_has_h1(page: Page, base_url: str):
    """Smoke test: homepage contains 'justralph.it' in an h1."""
    page.goto(base_url)
    h1 = page.locator("h1")
    expect(h1).to_contain_text("justralph.it")
