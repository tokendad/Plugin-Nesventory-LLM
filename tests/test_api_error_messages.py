"""Tests for improved API error messages, especially for image endpoints."""

import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from plugin_nesventory_llm.api import app


def create_test_image(width=100, height=100, color="blue", format="PNG"):
    """Helper to create a test image as bytes."""
    image = Image.new("RGB", (width, height), color=color)
    img_bytes = io.BytesIO()
    image.save(img_bytes, format=format)
    img_bytes.seek(0)
    return img_bytes


class TestImageEndpointErrorMessages:
    """Tests for improved error messages in image API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_search_image_invalid_file_type(self, client):
        """Test that /search/image returns structured error for invalid file type."""
        # Create a non-image file
        file_content = b"This is not an image"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        
        response = client.post("/search/image", files=files)
        
        # Should return 400 for invalid file type
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        
        # Check structured error format
        assert isinstance(detail, dict)
        assert detail["error"] == "Invalid file type"
        assert detail["error_code"] == "INVALID_FILE_TYPE"
        assert "file_info" in detail
        assert detail["file_info"]["content_type"] == "text/plain"
        assert detail["file_info"]["filename"] == "test.txt"
        assert "suggestions" in detail
        assert len(detail["suggestions"]) > 0

    def test_search_image_empty_file(self, client):
        """Test that /search/image returns structured error for empty file."""
        # Create an empty file
        files = {"file": ("empty.png", io.BytesIO(b""), "image/png")}
        
        response = client.post("/search/image", files=files)
        
        # Should return 400 for empty file
        assert response.status_code == 400
        
        data = response.json()
        detail = data["detail"]
        
        # Check structured error format
        assert isinstance(detail, dict)
        assert detail["error"] == "Empty file"
        assert detail["error_code"] == "EMPTY_FILE"
        assert "file_info" in detail
        assert detail["file_info"]["size_bytes"] == 0
        assert "suggestions" in detail

    def test_search_image_corrupted_image(self, client):
        """Test that /search/image returns structured error for corrupted image."""
        # Create a file with image mime type but invalid data
        invalid_image_data = b"\x89PNG\r\n\x1a\n" + b"corrupted data"
        files = {"file": ("corrupted.png", io.BytesIO(invalid_image_data), "image/png")}
        
        response = client.post("/search/image", files=files)
        
        # Should return 400 for invalid image data
        assert response.status_code == 400
        
        data = response.json()
        detail = data["detail"]
        
        # Check structured error format
        assert isinstance(detail, dict)
        assert detail["error"] == "Invalid image data"
        assert detail["error_code"] == "INVALID_IMAGE_DATA"
        assert "file_info" in detail
        assert "suggestions" in detail

    def test_search_image_service_unavailable(self, client):
        """Test that /search/image returns structured error when service unavailable."""
        # This test checks the error structure when image search service is not initialized
        # The service may or may not be available depending on test environment
        response = client.post(
            "/search/image",
            files={"file": ("test.png", create_test_image(), "image/png")}
        )
        
        # If service is unavailable, should return 503 with structured error
        # If available but KB empty, should return 404
        # If fully operational, may return 200
        if response.status_code == 503:
            data = response.json()
            detail = data["detail"]
            
            if isinstance(detail, dict):
                # Check structured error format
                assert "error" in detail
                assert "error_code" in detail
                # Could be KB_NOT_INITIALIZED or IMAGE_SEARCH_SERVICE_UNAVAILABLE
                assert detail["error_code"] in ["KB_NOT_INITIALIZED", "IMAGE_SEARCH_SERVICE_UNAVAILABLE"]
                if detail["error_code"] == "IMAGE_SEARCH_SERVICE_UNAVAILABLE":
                    assert "suggestions" in detail

    def test_identify_image_invalid_file_type(self, client):
        """Test that /nesventory/identify/image returns structured error for invalid file type."""
        # Create a non-image file
        file_content = b"This is not an image"
        files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
        
        response = client.post("/nesventory/identify/image", files=files)
        
        # Should return 400 for invalid file type
        assert response.status_code == 400
        
        data = response.json()
        detail = data["detail"]
        
        # Check structured error format
        assert isinstance(detail, dict)
        assert detail["error"] == "Invalid file type"
        assert detail["error_code"] == "INVALID_FILE_TYPE"
        assert "file_info" in detail
        assert "suggestions" in detail

    def test_identify_image_empty_file(self, client):
        """Test that /nesventory/identify/image returns structured error for empty file."""
        files = {"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")}
        
        response = client.post("/nesventory/identify/image", files=files)
        
        # Should return 400 for empty file
        assert response.status_code == 400
        
        data = response.json()
        detail = data["detail"]
        
        # Check structured error format
        assert isinstance(detail, dict)
        assert detail["error"] == "Empty file"
        assert detail["error_code"] == "EMPTY_FILE"


class TestConsistentErrorStructure:
    """Tests to ensure all endpoints use consistent error structure."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_kb_not_initialized_errors_consistent(self, client):
        """Test that all KB_NOT_INITIALIZED errors have consistent structure."""
        # Test a few endpoints that could return KB_NOT_INITIALIZED
        endpoints = [
            ("GET", "/stats"),
            ("POST", "/query", {"query": "test"}),
            ("POST", "/search", {"query": "test"}),
            ("GET", "/items/test-id"),
        ]
        
        for method, path, *args in endpoints:
            json_data = args[0] if args else None
            
            if method == "POST" and json_data:
                response = client.post(path, json=json_data)
            elif method == "POST":
                response = client.post(path)
            else:
                response = client.get(path)
            
            # Should return 503 or 404 (depending on KB state)
            if response.status_code == 503:
                data = response.json()
                detail = data.get("detail")
                
                # If it's a dict, check for consistent structure
                if isinstance(detail, dict):
                    assert "error" in detail, f"Missing 'error' in {method} {path}"
                    assert "message" in detail, f"Missing 'message' in {method} {path}"
                    assert "error_code" in detail, f"Missing 'error_code' in {method} {path}"
                    
                    if detail["error_code"] == "KB_NOT_INITIALIZED":
                        assert detail["error"] == "Service unavailable"

    def test_database_empty_errors_consistent(self, client):
        """Test that all database empty errors have consistent structure."""
        # These endpoints should all return consistent empty database errors
        endpoints = [
            ("POST", "/query", {"query": "test"}),
            ("POST", "/search", {"query": "test"}),
            ("POST", "/build"),
            ("POST", "/nesventory/identify?query=test"),
            ("GET", "/items/test-id"),
        ]
        
        for method, path, *args in endpoints:
            json_data = args[0] if args else None
            
            if method == "POST" and json_data:
                response = client.post(path, json=json_data)
            elif method == "POST":
                response = client.post(path)
            else:
                response = client.get(path)
            
            # Should return 404 or 503
            if response.status_code == 404:
                data = response.json()
                detail = data.get("detail")
                
                # Check consistent structure for database empty errors
                if isinstance(detail, dict) and detail.get("error") == "Database empty":
                    assert "message" in detail
                    assert "items_loaded" in detail
                    assert detail["items_loaded"] == 0


class TestErrorSuggestions:
    """Tests that error messages include helpful suggestions."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_image_errors_have_suggestions(self, client):
        """Test that image endpoint errors include actionable suggestions."""
        # Test invalid file type
        files = {"file": ("test.txt", io.BytesIO(b"test"), "text/plain")}
        response = client.post("/search/image", files=files)
        
        if response.status_code == 400:
            detail = response.json()["detail"]
            if isinstance(detail, dict):
                assert "suggestions" in detail
                assert isinstance(detail["suggestions"], list)
                assert len(detail["suggestions"]) > 0
                # Suggestions should be strings
                for suggestion in detail["suggestions"]:
                    assert isinstance(suggestion, str)
                    assert len(suggestion) > 0
