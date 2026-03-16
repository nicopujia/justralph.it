import pytest
from app import create_app


class TestHSTSHeader:
    """Test that HSTS headers are added to all responses."""

    def test_hsts_header_present_on_home_page(self):
        """HSTS header should be present on GET / response."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test-secret-for-hsts"})
        client = app.test_client()
        response = client.get("/")
        assert "Strict-Transport-Security" in response.headers
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    def test_hsts_header_present_on_health_endpoint(self):
        """HSTS header should be present on GET /health response."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test-secret-for-hsts"})
        client = app.test_client()
        response = client.get("/health")
        assert "Strict-Transport-Security" in response.headers
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


class TestHTTPSRedirect:
    """Test that HTTP requests redirect to HTTPS."""

    def test_http_x_forwarded_proto_redirects_to_https(self):
        """Request with X-Forwarded-Proto: http should redirect to HTTPS."""
        # Note: This test intentionally does NOT use TESTING=True so we can test the redirect
        app = create_app({"SECRET_KEY": "test-secret-for-hsts"})
        client = app.test_client()
        response = client.get("/", headers={"X-Forwarded-Proto": "http"}, follow_redirects=False)
        assert response.status_code == 301
        assert response.headers["Location"].startswith("https://")

    def test_https_x_forwarded_proto_no_redirect(self):
        """Request with X-Forwarded-Proto: https should not redirect."""
        app = create_app({"TESTING": True, "SECRET_KEY": "test-secret-for-hsts"})
        client = app.test_client()
        response = client.get("/", headers={"X-Forwarded-Proto": "https"})
        assert response.status_code == 200
