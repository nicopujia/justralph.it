"""E2E tests for the Ralph Force Stop feature.

Verifies:
1. Force Stop button exists in the DOM but is hidden when Ralph is NOT running
2. Confirmation dialog exists in the DOM with correct warning text
3. Dialog has Cancel and Force Stop buttons
4. Clicking Force Stop button shows the confirmation dialog
5. Clicking Cancel closes the dialog without side effects
6. Clicking Force Stop in the dialog sends POST to the force-stop endpoint

Authentication: Forges a Flask session cookie using the production SECRET_KEY
so Playwright can load auth-gated project pages.
"""

import os

import pytest
from dotenv import load_dotenv
from flask import Flask
from flask.sessions import SecureCookieSessionInterface
from playwright.sync_api import Page, expect

# Load the real .env so we can forge session cookies with the production SECRET_KEY
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)

_SLUG = "salary-calculator-clone-att-2"


def _forge_session_cookie() -> str:
    """Forge a valid Flask session cookie using the production SECRET_KEY.

    This lets Playwright load auth-gated pages without going through
    the GitHub OAuth flow.
    """
    secret_key = os.environ["SECRET_KEY"]
    app = Flask(__name__)
    app.config["SECRET_KEY"] = secret_key
    with app.test_request_context():
        si = SecureCookieSessionInterface()
        s = si.get_signing_serializer(app)
        return s.dumps({"user": "nicopujia", "github_token": "fake-for-e2e"})


@pytest.fixture()
def authed_page(page: Page, base_url: str):
    """A Playwright page with a forged Flask session cookie set."""
    cookie_value = _forge_session_cookie()
    page.context.add_cookies(
        [
            {
                "name": "session",
                "value": cookie_value,
                "url": base_url,
            }
        ]
    )
    return page


# ---------------------------------------------------------------------------
# Test 1: Force Stop button exists but is hidden when Ralph is NOT running
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_force_stop_button_exists_but_hidden(authed_page: Page, base_url: str):
    """The #ralph-force-stop-btn exists in the DOM but has display:none
    when Ralph is not running."""
    authed_page.goto(f"{base_url}/projects/{_SLUG}", wait_until="domcontentloaded")

    btn = authed_page.locator("#ralph-force-stop-btn")
    expect(btn).to_have_count(1)
    expect(btn).to_be_hidden()


# ---------------------------------------------------------------------------
# Test 2: Confirmation dialog exists with correct warning text
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_force_stop_dialog_exists_with_warning_text(authed_page: Page, base_url: str):
    """The #force-stop-dialog exists and contains the expected warning text."""
    authed_page.goto(f"{base_url}/projects/{_SLUG}", wait_until="domcontentloaded")

    dialog = authed_page.locator("#force-stop-dialog")
    expect(dialog).to_have_count(1)

    expected_text = (
        "This will immediately kill Ralph and hard reset the repo to match origin. "
        "Any uncommitted changes will be lost. Are you sure?"
    )
    # Dialog is a <dialog> element — not visible until .showModal() is called,
    # but its inner text is still in the DOM. Use inner_text() directly.
    actual_text = dialog.inner_text()
    assert expected_text in actual_text, f"Expected dialog to contain:\n  {expected_text}\nGot:\n  {actual_text}"


# ---------------------------------------------------------------------------
# Test 3: Dialog has Cancel and Force Stop buttons
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_dialog_has_cancel_and_force_stop_buttons(authed_page: Page, base_url: str):
    """The confirmation dialog contains a Cancel button and a Force Stop button."""
    authed_page.goto(f"{base_url}/projects/{_SLUG}", wait_until="domcontentloaded")

    dialog = authed_page.locator("#force-stop-dialog")

    cancel_btn = dialog.locator("button", has_text="Cancel")
    expect(cancel_btn).to_have_count(1)

    force_stop_btn = dialog.locator("button", has_text="Force Stop")
    expect(force_stop_btn).to_have_count(1)


# ---------------------------------------------------------------------------
# Test 4: Clicking Force Stop button opens the confirmation dialog
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_clicking_force_stop_opens_dialog(authed_page: Page, base_url: str):
    """Clicking #ralph-force-stop-btn opens the confirmation dialog."""
    authed_page.goto(f"{base_url}/projects/{_SLUG}", wait_until="domcontentloaded")

    # Make the force stop button visible (it's hidden because ralph_running=0)
    authed_page.evaluate("document.getElementById('ralph-force-stop-btn').style.display = ''")

    btn = authed_page.locator("#ralph-force-stop-btn")
    btn.click()

    dialog = authed_page.locator("#force-stop-dialog")
    expect(dialog).to_be_visible()


# ---------------------------------------------------------------------------
# Test 5: Clicking Cancel closes the dialog without side effects
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_clicking_cancel_closes_dialog(authed_page: Page, base_url: str):
    """Clicking Cancel in the dialog closes it without sending any request."""
    authed_page.goto(f"{base_url}/projects/{_SLUG}", wait_until="domcontentloaded")

    # Open the dialog
    authed_page.evaluate("document.getElementById('ralph-force-stop-btn').style.display = ''")
    authed_page.locator("#ralph-force-stop-btn").click()

    dialog = authed_page.locator("#force-stop-dialog")
    expect(dialog).to_be_visible()

    # Track network requests to ensure no POST is sent
    requests_made = []
    authed_page.on("request", lambda req: requests_made.append(req))

    # Click Cancel
    dialog.locator("button", has_text="Cancel").click()

    # Dialog should be closed
    expect(dialog).to_be_hidden()

    # No POST to force-stop should have been made
    force_stop_posts = [r for r in requests_made if "force-stop" in r.url and r.method == "POST"]
    assert len(force_stop_posts) == 0, (
        f"Cancel should not trigger a force-stop POST, but {len(force_stop_posts)} were sent"
    )


# ---------------------------------------------------------------------------
# Test 6: Clicking Force Stop in dialog sends POST to force-stop endpoint
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_clicking_force_stop_in_dialog_sends_post(authed_page: Page, base_url: str):
    """Clicking Force Stop in the confirmation dialog sends a POST to
    /projects/<slug>/ralph/force-stop."""
    authed_page.goto(f"{base_url}/projects/{_SLUG}", wait_until="domcontentloaded")

    # Open the dialog
    authed_page.evaluate("document.getElementById('ralph-force-stop-btn').style.display = ''")
    authed_page.locator("#ralph-force-stop-btn").click()

    dialog = authed_page.locator("#force-stop-dialog")
    expect(dialog).to_be_visible()

    # Track network requests
    requests_made = []
    authed_page.on("request", lambda req: requests_made.append(req))

    # Click the Force Stop confirmation button (inside the dialog)
    dialog.locator("button", has_text="Force Stop").click()

    # Wait briefly for the fetch to fire
    authed_page.wait_for_timeout(500)

    # A POST to the force-stop endpoint should have been sent
    force_stop_posts = [r for r in requests_made if "force-stop" in r.url and r.method == "POST"]
    assert len(force_stop_posts) == 1, (
        f"Expected exactly 1 force-stop POST, got {len(force_stop_posts)}. "
        f"All requests: {[(r.method, r.url) for r in requests_made]}"
    )
    assert f"/projects/{_SLUG}/ralph/force-stop" in force_stop_posts[0].url
