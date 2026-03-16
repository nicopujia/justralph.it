"""E2E tests verifying SSE connection leak fix.

Acceptance criteria:
1. After creating a project, all pages remain responsive
2. SSE connections do not block other requests
3. Reloading any page loads instantly

Since project pages require GitHub OAuth, we test:
- Public pages load quickly (homepage)
- Rapid reloads don't cause hangs
- SSE connections opened in background threads don't starve the server
- After SSE connections are closed, server responds instantly

Note on SSE timing: The SSE endpoint uses a 15s keepalive, so the first
bytes of response body arrive after ~15s. We open SSE connections in
background threads and test that the server remains responsive while
those threads hold connections.
"""

import socket
import ssl
import threading
import time

import pytest
import requests

# Internal endpoint accessed directly (localhost, no auth required)
_LOCALHOST = "http://localhost:8000"


def _sse_url(slug: str) -> str:
    """Build an SSE URL for the given slug (always localhost)."""
    return f"{_LOCALHOST}/internal/projects/{slug}/events"


def _open_sse_socket(slug: str) -> socket.socket:
    """Open a raw TCP connection to the SSE endpoint.

    This sends the HTTP request and returns immediately without waiting
    for response data — unlike requests.get(stream=True) which blocks
    until the first response bytes arrive.
    """
    sock = socket.create_connection(("localhost", 8000), timeout=5)
    path = f"/internal/projects/{slug}/events"
    request = (
        f"GET {path} HTTP/1.1\r\nHost: localhost:8000\r\nAccept: text/event-stream\r\nConnection: keep-alive\r\n\r\n"
    )
    sock.sendall(request.encode())
    return sock


def _open_sse_in_thread(slug: str, results: dict, index: int):
    """Open an SSE connection in a thread and read until cancelled."""
    try:
        resp = requests.get(_sse_url(slug), stream=True, timeout=(5, 20))
        results[index] = {
            "status": resp.status_code,
            "content_type": resp.headers.get("Content-Type", ""),
            "connected": True,
        }
        # Read to keep connection alive until the response is closed externally
        try:
            for _ in resp.iter_content(chunk_size=64):
                pass
        except Exception:
            pass
        finally:
            resp.close()
    except Exception as e:
        results[index] = {"connected": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Test 1: Homepage loads quickly (basic responsiveness)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_homepage_loads_quickly(page, base_url):
    """Homepage loads within 5 seconds (proves server is responsive)."""
    start = time.monotonic()
    page.goto(base_url, wait_until="domcontentloaded")
    elapsed = time.monotonic() - start
    assert elapsed < 5, f"Homepage took {elapsed:.2f}s to load (expected < 5s)"


# ---------------------------------------------------------------------------
# Test 2: Rapid reloads stay responsive
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_rapid_reloads_stay_responsive(page, base_url):
    """Rapidly reloading the homepage 5 times — each load stays under 5s."""
    page.goto(base_url, wait_until="domcontentloaded")
    for i in range(5):
        start = time.monotonic()
        page.reload(wait_until="domcontentloaded")
        elapsed = time.monotonic() - start
        assert elapsed < 5, f"Reload #{i + 1} took {elapsed:.2f}s (expected < 5s)"


# ---------------------------------------------------------------------------
# Test 3: SSE endpoint accepts connections (raw socket, non-blocking)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_sse_endpoint_accepts_connection():
    """The internal SSE endpoint accepts TCP connections without blocking."""
    sock = _open_sse_socket("test-accept-slug")
    try:
        # Connection was accepted — the server didn't reject it
        # Set a short timeout to read whatever headers are available
        sock.settimeout(1)
        try:
            data = sock.recv(4096)
            # If we got data, check it looks like HTTP
            if data:
                assert b"HTTP/1.1" in data or b"HTTP/1.0" in data
        except socket.timeout:
            # No data yet is fine — the connection was accepted,
            # server just hasn't flushed headers yet (normal for WSGI SSE)
            pass
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# Test 4: Multiple SSE connections don't block the server
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_multiple_sse_connections_dont_block_server():
    """Opening 5+ SSE connections doesn't block other HTTP requests.

    This is the core regression test for the SSE connection leak fix.
    Before the fix, open SSE connections would consume all worker threads
    and block other requests.
    """
    sockets = []

    # Open 5 raw SSE connections (non-blocking from our side)
    for i in range(5):
        sock = _open_sse_socket(f"test-block-{i}")
        sockets.append(sock)

    try:
        # Give the server a moment to accept all connections
        time.sleep(0.5)

        # Now make a regular HTTP request — it must succeed quickly
        start = time.monotonic()
        resp = requests.get(f"{_LOCALHOST}/", timeout=5)
        elapsed = time.monotonic() - start

        assert resp.status_code == 200, f"Homepage returned {resp.status_code}"
        assert elapsed < 5, f"Homepage took {elapsed:.2f}s with 5 SSE connections open (expected < 5s)"
    finally:
        for sock in sockets:
            try:
                sock.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Test 5: SSE connections can be opened and closed cleanly
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_sse_connections_close_cleanly():
    """SSE connections can be opened and closed without leaving leaks."""
    # Open and close 5 SSE connections sequentially
    for i in range(5):
        sock = _open_sse_socket(f"test-clean-{i}")
        # Give server a moment to register the connection
        time.sleep(0.1)
        sock.close()

    # Server should still be responsive after all connections closed
    start = time.monotonic()
    resp = requests.get(f"{_LOCALHOST}/", timeout=5)
    elapsed = time.monotonic() - start

    assert resp.status_code == 200
    assert elapsed < 5, f"Homepage took {elapsed:.2f}s after SSE cleanup (expected < 5s)"


# ---------------------------------------------------------------------------
# Test 6: Server responsive after SSE connections closed (browser test)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_server_responsive_after_sse_cleanup(page, base_url):
    """After opening and closing multiple SSE connections, browser pages load fast."""
    # Open and close 5 SSE connections
    for i in range(5):
        sock = _open_sse_socket(f"test-cleanup-{i}")
        time.sleep(0.1)
        sock.close()

    # Allow server threads to clean up
    time.sleep(0.5)

    # Browser page load must be fast
    start = time.monotonic()
    page.goto(base_url, wait_until="domcontentloaded")
    elapsed = time.monotonic() - start
    assert elapsed < 5, f"Homepage took {elapsed:.2f}s after SSE cleanup (expected < 5s)"


# ---------------------------------------------------------------------------
# Test 7: Concurrent SSE + page loads (the big integration test)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_concurrent_sse_and_page_loads(page, base_url):
    """SSE connections held open don't block browser page loads.

    Opens 5 SSE connections via raw sockets, then verifies Playwright
    can still load and reload the homepage quickly.
    """
    sockets = []

    # Open 5 SSE connections
    for i in range(5):
        sock = _open_sse_socket(f"test-concurrent-{i}")
        sockets.append(sock)

    try:
        # Give server time to accept connections
        time.sleep(0.5)

        # Load homepage in browser — must not hang
        start = time.monotonic()
        page.goto(base_url, wait_until="domcontentloaded", timeout=10000)
        elapsed = time.monotonic() - start
        assert elapsed < 5, f"Page load took {elapsed:.2f}s with 5 active SSE connections (expected < 5s)"

        # Reload — must also be fast
        start = time.monotonic()
        page.reload(wait_until="domcontentloaded", timeout=10000)
        elapsed = time.monotonic() - start
        assert elapsed < 5, f"Reload took {elapsed:.2f}s with 5 active SSE connections (expected < 5s)"
    finally:
        for sock in sockets:
            try:
                sock.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Test 8: SSE endpoint returns valid event-stream (full round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_sse_returns_keepalive():
    """The SSE endpoint sends keepalive comments within 20 seconds.

    This verifies the full SSE round-trip: connect, receive keepalive,
    disconnect cleanly.
    """
    result = {}

    def read_sse():
        try:
            resp = requests.get(
                _sse_url("test-keepalive"),
                stream=True,
                timeout=(5, 20),
            )
            result["status"] = resp.status_code
            result["content_type"] = resp.headers.get("Content-Type", "")
            # Read first chunk (should be keepalive)
            for chunk in resp.iter_content(chunk_size=256):
                result["first_chunk"] = chunk
                break
            resp.close()
            result["done"] = True
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=read_sse)
    t.start()
    # Wait up to 20s for the keepalive (server sends at 15s)
    t.join(timeout=20)

    assert not t.is_alive(), "SSE read thread is still blocking after 20s"
    assert "error" not in result, f"SSE connection error: {result.get('error')}"
    assert result.get("status") == 200
    assert "text/event-stream" in result.get("content_type", "")
    assert result.get("first_chunk") is not None, "No data received from SSE"
    assert b"keepalive" in result["first_chunk"], f"Expected keepalive, got: {result['first_chunk']!r}"
