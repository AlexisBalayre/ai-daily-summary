"""Tests for Source CRUD API endpoints."""

from unittest.mock import MagicMock

import pytest

# Create a test app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_daily.api.routes import get_db, router
from ai_daily.db import Source

app = FastAPI()
app.include_router(router)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def client(mock_db):
    """Create a test client with mocked database."""

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_source():
    """Create a sample source object."""
    source = MagicMock(spec=Source)
    source.id = 1
    source.type = "rss"
    source.name = "Test Feed"
    source.config = {"url": "https://example.com/feed.xml"}
    source.enabled = True
    return source


class TestCreateSource:
    """Tests for POST /sources endpoint."""

    def test_create_source_success(self, client, mock_db):
        """Should create a new source and return 201."""
        # Mock the db.add, db.commit, db.refresh operations
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        def mock_refresh(obj):
            obj.id = 1

        mock_db.refresh = mock_refresh

        response = client.post(
            "/sources",
            json={
                "type": "rss",
                "name": "New Feed",
                "config": {"url": "https://example.com/feed.xml"},
                "enabled": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "rss"
        assert data["name"] == "New Feed"
        assert data["enabled"] is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_source_minimal(self, client, mock_db):
        """Should create source with only required fields."""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        def mock_refresh(obj):
            obj.id = 2

        mock_db.refresh = mock_refresh

        response = client.post(
            "/sources",
            json={
                "type": "crawler",
                "name": "Web Crawler",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "crawler"
        assert data["name"] == "Web Crawler"
        assert data["enabled"] is True  # Default value


class TestDeleteSource:
    """Tests for DELETE /sources/{source_id} endpoint."""

    def test_delete_source_success(self, client, mock_db, sample_source):
        """Should delete source and return 204."""
        mock_db.get.return_value = sample_source
        mock_db.delete = MagicMock()
        mock_db.commit = MagicMock()

        response = client.delete("/sources/1")

        assert response.status_code == 204
        mock_db.get.assert_called_once_with(Source, 1)
        mock_db.delete.assert_called_once_with(sample_source)
        mock_db.commit.assert_called_once()

    def test_delete_source_not_found(self, client, mock_db):
        """Should return 404 when source doesn't exist."""
        mock_db.get.return_value = None

        response = client.delete("/sources/999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Source not found"


class TestToggleSource:
    """Tests for PATCH /sources/{source_id}/toggle endpoint."""

    def test_toggle_source_enable_to_disable(self, client, mock_db, sample_source):
        """Should toggle enabled source to disabled."""
        sample_source.enabled = True
        mock_db.get.return_value = sample_source
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        response = client.patch("/sources/1/toggle")

        assert response.status_code == 200
        assert sample_source.enabled is False
        mock_db.commit.assert_called_once()

    def test_toggle_source_disable_to_enable(self, client, mock_db, sample_source):
        """Should toggle disabled source to enabled."""
        sample_source.enabled = False
        mock_db.get.return_value = sample_source
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        response = client.patch("/sources/1/toggle")

        assert response.status_code == 200
        assert sample_source.enabled is True

    def test_toggle_source_not_found(self, client, mock_db):
        """Should return 404 when source doesn't exist."""
        mock_db.get.return_value = None

        response = client.patch("/sources/999/toggle")

        assert response.status_code == 404
        assert response.json()["detail"] == "Source not found"


class TestGetSource:
    """Tests for GET /sources/{source_id} endpoint."""

    def test_get_source_success(self, client, mock_db, sample_source):
        """Should return source when found."""
        mock_db.get.return_value = sample_source

        response = client.get("/sources/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["type"] == "rss"
        assert data["name"] == "Test Feed"
        assert data["enabled"] is True

    def test_get_source_not_found(self, client, mock_db):
        """Should return 404 when source doesn't exist."""
        mock_db.get.return_value = None

        response = client.get("/sources/999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Source not found"


class TestUpdateSource:
    """Tests for PUT /sources/{source_id} endpoint."""

    def test_update_source_success(self, client, mock_db, sample_source):
        """Should update source and return updated data."""
        mock_db.get.return_value = sample_source
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        response = client.put(
            "/sources/1",
            json={
                "name": "Updated Feed Name",
                "enabled": False,
            },
        )

        assert response.status_code == 200
        assert sample_source.name == "Updated Feed Name"
        assert sample_source.enabled is False

    def test_update_source_not_found(self, client, mock_db):
        """Should return 404 when source doesn't exist."""
        mock_db.get.return_value = None

        response = client.put(
            "/sources/999",
            json={"name": "New Name"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Source not found"
