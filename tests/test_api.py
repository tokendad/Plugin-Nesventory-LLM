"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from plugin_nesventory_llm.api import app
from plugin_nesventory_llm.models import ConnectionTestResponse


class TestConnectionTest:
    """Tests for the connection test endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_connection_test_endpoint_exists(self, client):
        """Test that the connection test endpoint exists and returns 200."""
        response = client.get("/connection/test")
        assert response.status_code == 200

    def test_connection_test_response_structure(self, client):
        """Test that the connection test returns the expected structure."""
        response = client.get("/connection/test")
        assert response.status_code == 200

        data = response.json()

        # Check required fields
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "checks" in data
        assert "error_codes" in data
        assert "message" in data

        # Validate status values
        assert data["status"] in ["ok", "degraded", "error"]

        # Validate checks is a dict
        assert isinstance(data["checks"], dict)

        # Validate error_codes is a list
        assert isinstance(data["error_codes"], list)

    def test_connection_test_includes_component_checks(self, client):
        """Test that connection test includes checks for key components."""
        response = client.get("/connection/test")
        assert response.status_code == 200

        data = response.json()
        checks = data["checks"]

        # Verify expected component checks exist
        expected_components = [
            "knowledge_base",
            "items",
            "embeddings",
            "embedding_model",
            "image_search",
        ]

        for component in expected_components:
            assert component in checks, f"Missing check for {component}"
            assert "status" in checks[component]
            assert "message" in checks[component]

    def test_connection_test_validates_against_model(self, client):
        """Test that the response validates against the ConnectionTestResponse model."""
        response = client.get("/connection/test")
        assert response.status_code == 200

        data = response.json()

        # This will raise a validation error if the response doesn't match
        connection_response = ConnectionTestResponse(**data)

        assert connection_response.status in ["ok", "degraded", "error"]
        assert connection_response.version is not None
        assert connection_response.timestamp is not None

    def test_connection_test_timestamp_format(self, client):
        """Test that timestamp is in ISO 8601 format."""
        response = client.get("/connection/test")
        assert response.status_code == 200

        data = response.json()
        timestamp = data["timestamp"]

        # Check that timestamp ends with Z (UTC)
        assert timestamp.endswith("Z")

        # Check that timestamp can be parsed (basic validation)
        from datetime import datetime

        # Remove the Z and parse
        datetime.fromisoformat(timestamp.rstrip("Z"))

    def test_connection_test_error_codes_format(self, client):
        """Test that error codes are properly formatted."""
        response = client.get("/connection/test")
        assert response.status_code == 200

        data = response.json()
        error_codes = data["error_codes"]

        # All error codes should be strings
        for code in error_codes:
            assert isinstance(code, str)
            # Error codes should be uppercase with underscores (e.g., 'NO_ITEMS_LOADED')
            assert code.replace("_", "").isupper(), f"Error code '{code}' is not properly formatted"


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_health_endpoint_exists(self, client):
        """Test that the health endpoint exists."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client):
        """Test that health endpoint returns expected fields."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "items_loaded" in data
        assert "embeddings_ready" in data
