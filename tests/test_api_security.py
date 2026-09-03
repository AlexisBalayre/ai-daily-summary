"""Auth and URL guard behaviour of the API."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai_daily.api.server import app
from ai_daily.config import config
from ai_daily.etl.urlcheck import ensure_public_http_url

client = TestClient(app)


def test_mutating_route_open_when_no_token_configured(monkeypatch):
    monkeypatch.setattr(config, "api_token", "")
    response = client.post("/api/v1/sources/test", json={"type": "nope", "name": "x", "config": {}})
    assert response.status_code == 200


def test_mutating_route_requires_bearer_token(monkeypatch):
    monkeypatch.setattr(config, "api_token", "s3cret")
    body = {"type": "nope", "name": "x", "config": {}}

    assert client.post("/api/v1/sources/test", json=body).status_code == 401
    wrong = client.post("/api/v1/sources/test", json=body, headers={"Authorization": "Bearer no"})
    assert wrong.status_code == 401
    ok = client.post("/api/v1/sources/test", json=body, headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200


def test_read_routes_stay_open_with_token(monkeypatch):
    monkeypatch.setattr(config, "api_token", "s3cret")
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "url",
    ["ftp://example.com/x", "file:///etc/passwd", "http://127.0.0.1/", "http://169.254.169.254/"],
)
def test_url_guard_rejects_non_public(url):
    with pytest.raises(ValueError):
        ensure_public_http_url(url)


def test_url_guard_rejects_private_dns_answer():
    with patch(
        "ai_daily.etl.urlcheck.socket.getaddrinfo", return_value=[(0, 0, 0, "", ("10.0.0.5", 80))]
    ):
        with pytest.raises(ValueError):
            ensure_public_http_url("http://intranet.example/")


def test_url_guard_accepts_public_dns_answer():
    with patch(
        "ai_daily.etl.urlcheck.socket.getaddrinfo",
        return_value=[(0, 0, 0, "", ("93.184.216.34", 80))],
    ):
        ensure_public_http_url("https://example.com/feed.xml")


def test_crawler_test_endpoint_refuses_internal_url(monkeypatch):
    monkeypatch.setattr(config, "api_token", "")
    body = {"type": "crawler", "name": "x", "config": {"url": "http://169.254.169.254/latest/"}}
    response = client.post("/api/v1/sources/test", json=body)
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "non-public" in response.json()["message"]


def test_whitelist_rejects_malformed_email(monkeypatch):
    monkeypatch.setattr(config, "api_token", "")
    assert client.post("/api/v1/whitelist", json={"email": "not-an-email"}).status_code == 422
