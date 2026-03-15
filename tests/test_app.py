from app import create_app


def test_app_creates():
    app = create_app()
    assert app is not None


def test_index_returns_200():
    app = create_app()
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_health_returns_ok():
    app = create_app()
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"
