"""Tests for image search functionality."""

import pytest
from io import BytesIO
from PIL import Image

from plugin_nesventory_llm.models import (
    DetectedObject,
    ImageSearchRequest,
    ImageSearchResult,
    VillageItem,
)


class TestImageSearchModels:
    """Tests for image search data models."""

    def test_image_search_request_defaults(self):
        """Test ImageSearchRequest with default values."""
        request = ImageSearchRequest()
        assert request.limit == 10
        assert request.min_confidence == 0.3
        assert request.collection is None
        assert request.category is None

    def test_image_search_request_custom(self):
        """Test ImageSearchRequest with custom values."""
        request = ImageSearchRequest(
            collection="Dickens Village",
            category="Buildings",
            limit=5,
            min_confidence=0.5,
        )
        assert request.collection == "Dickens Village"
        assert request.category == "Buildings"
        assert request.limit == 5
        assert request.min_confidence == 0.5

    def test_detected_object(self):
        """Test DetectedObject model."""
        obj = DetectedObject(
            label="Victorian house with lights",
            confidence=0.85,
            bounding_box={"x": 10, "y": 20, "width": 100, "height": 150},
        )
        assert obj.label == "Victorian house with lights"
        assert obj.confidence == 0.85
        assert obj.bounding_box["x"] == 10

    def test_detected_object_no_bbox(self):
        """Test DetectedObject without bounding box."""
        obj = DetectedObject(label="Christmas village building", confidence=0.75)
        assert obj.label == "Christmas village building"
        assert obj.confidence == 0.75
        assert obj.bounding_box is None

    def test_image_search_result(self):
        """Test ImageSearchResult model."""
        detected = DetectedObject(label="Test object", confidence=0.9)
        result = ImageSearchResult(
            detected_objects=[detected],
            matched_items=[],
            overall_confidence=0.8,
            processing_time_ms=123.45,
        )
        assert len(result.detected_objects) == 1
        assert result.detected_objects[0].label == "Test object"
        assert result.overall_confidence == 0.8
        assert result.processing_time_ms == 123.45


class TestImageSearchService:
    """Tests for ImageSearchService."""

    @pytest.fixture
    def mock_kb(self):
        """Create a mock knowledge base."""
        from unittest.mock import MagicMock
        from plugin_nesventory_llm.models import ItemSearchResult

        kb = MagicMock()
        kb.items = [
            VillageItem(
                id="test-001",
                name="Victorian House",
                collection="Dickens Village",
                category="Buildings",
                description="A beautiful Victorian-style house",
            ),
            VillageItem(
                id="test-002",
                name="Christmas Church",
                collection="Snow Village",
                category="Buildings",
                description="A small white church with steeple",
            ),
        ]

        # Mock search to return items
        def mock_search(query):
            return [
                ItemSearchResult(
                    item=kb.items[0], relevance_score=0.85, match_reason="Test match"
                )
            ]

        kb.search = mock_search
        return kb

    @pytest.fixture
    def sample_image_bytes(self):
        """Create a sample image as bytes."""
        # Create a simple test image
        image = Image.new("RGB", (100, 100), color="red")
        img_bytes = BytesIO()
        image.save(img_bytes, format="PNG")
        return img_bytes.getvalue()

    def test_image_search_service_init(self, mock_kb):
        """Test ImageSearchService initialization."""
        from plugin_nesventory_llm.image_search import ImageSearchService

        service = ImageSearchService(mock_kb)
        assert service.kb == mock_kb
        assert service.vision_model_name == "Salesforce/blip-image-captioning-base"

    def test_load_image_valid(self, mock_kb, sample_image_bytes):
        """Test loading a valid image."""
        from plugin_nesventory_llm.image_search import ImageSearchService

        service = ImageSearchService(mock_kb)
        image = service._load_image(sample_image_bytes)
        assert image.mode == "RGB"
        assert image.size == (100, 100)

    def test_load_image_invalid(self, mock_kb):
        """Test loading invalid image data."""
        from plugin_nesventory_llm.image_search import ImageSearchService

        service = ImageSearchService(mock_kb)
        with pytest.raises(ValueError, match="Invalid image data"):
            service._load_image(b"not an image")

    def test_load_image_converts_to_rgb(self, mock_kb):
        """Test that images are converted to RGB."""
        from plugin_nesventory_llm.image_search import ImageSearchService

        # Create a grayscale image
        image = Image.new("L", (50, 50), color=128)
        img_bytes = BytesIO()
        image.save(img_bytes, format="PNG")

        service = ImageSearchService(mock_kb)
        loaded = service._load_image(img_bytes.getvalue())
        assert loaded.mode == "RGB"

    def test_detect_objects_with_caption(self, mock_kb):
        """Test object detection from caption."""
        from plugin_nesventory_llm.image_search import ImageSearchService

        service = ImageSearchService(mock_kb)
        image = Image.new("RGB", (100, 100))
        caption = "a Victorian house with red roof"

        objects = service._detect_objects(image, caption)
        assert len(objects) == 1
        assert objects[0].label == caption
        assert objects[0].confidence == 0.85

    def test_detect_objects_empty_caption(self, mock_kb):
        """Test object detection with empty caption."""
        from plugin_nesventory_llm.image_search import ImageSearchService

        service = ImageSearchService(mock_kb)
        image = Image.new("RGB", (100, 100))

        objects = service._detect_objects(image, "")
        assert len(objects) == 0


def create_test_image(width=100, height=100, color="blue"):
    """Helper to create a test image."""
    image = Image.new("RGB", (width, height), color=color)
    img_bytes = BytesIO()
    image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()
