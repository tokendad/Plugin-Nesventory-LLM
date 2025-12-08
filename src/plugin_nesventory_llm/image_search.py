"""
Image search module for Department 56 village collectibles.

This module provides image analysis and object detection capabilities
for identifying collectible items from uploaded images.
"""

import logging
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from .models import DetectedObject, ImageSearchRequest, ImageSearchResult, ItemQuery, ItemSearchResult

logger = logging.getLogger(__name__)

# Default vision model for image captioning and object detection
DEFAULT_VISION_MODEL = "Salesforce/blip-image-captioning-base"

# Default confidence for caption-based object detection
DEFAULT_DETECTION_CONFIDENCE = 0.85


class ImageSearchService:
    """Service for analyzing images and finding matching collectible items."""

    def __init__(self, knowledge_base, vision_model: str = DEFAULT_VISION_MODEL):
        """Initialize the image search service.

        Args:
            knowledge_base: KnowledgeBase instance for searching items
            vision_model: Name of the vision model to use
        """
        self.kb = knowledge_base
        self.vision_model_name = vision_model
        self._vision_model = None
        self._vision_processor = None

    @property
    def vision_model(self):
        """Lazy load the vision model."""
        if self._vision_model is None:
            try:
                from transformers import BlipForConditionalGeneration, BlipProcessor

                logger.info(f"Loading vision model: {self.vision_model_name}")
                self._vision_processor = BlipProcessor.from_pretrained(self.vision_model_name)
                self._vision_model = BlipForConditionalGeneration.from_pretrained(
                    self.vision_model_name
                )
            except ImportError as e:
                logger.error("transformers not installed. Install with: pip install transformers")
                raise ImportError(
                    "transformers package is required for image search. "
                    "Install with: pip install transformers torch"
                ) from e
        return self._vision_model

    @property
    def vision_processor(self):
        """Get the vision processor."""
        if self._vision_processor is None:
            # Trigger lazy loading
            _ = self.vision_model
        return self._vision_processor

    def _load_image(self, image_data: bytes) -> Image.Image:
        """Load and preprocess an image from bytes.

        Args:
            image_data: Raw image bytes

        Returns:
            PIL Image object
        """
        try:
            image = Image.open(BytesIO(image_data))
            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")
            return image
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            raise ValueError(f"Invalid image data: {e}")

    def _generate_caption(self, image: Image.Image) -> str:
        """Generate a descriptive caption for the image.

        Args:
            image: PIL Image object

        Returns:
            Caption string describing the image content
        """
        try:
            # Prepare image for the model
            inputs = self.vision_processor(image, return_tensors="pt")

            # Generate caption
            output = self.vision_model.generate(**inputs, max_length=50)
            caption = self.vision_processor.decode(output[0], skip_special_tokens=True)

            logger.info(f"Generated caption: {caption}")
            return caption
        except Exception as e:
            logger.error(f"Failed to generate caption: {e}")
            return ""

    def _detect_objects(self, image: Image.Image, caption: str) -> list[DetectedObject]:
        """Detect objects in the image.

        For the initial implementation, we use image captioning to detect objects.
        The caption provides a description of the items in the image.

        Args:
            image: PIL Image object
            caption: Generated caption for the image

        Returns:
            List of detected objects
        """
        # For now, we treat the entire caption as a single detected object
        # In a more advanced implementation, this could use object detection models
        # to identify multiple objects with bounding boxes
        
        if not caption:
            return []

        # Extract key terms that might indicate collectible items
        detected = DetectedObject(
            label=caption,
            confidence=DEFAULT_DETECTION_CONFIDENCE,
            bounding_box=None,  # Future: add actual bounding boxes with object detection
        )

        return [detected]

    def search_by_image(
        self, image_data: bytes, request: ImageSearchRequest
    ) -> ImageSearchResult:
        """Search for items matching objects detected in an image.

        Args:
            image_data: Raw image bytes
            request: Search request parameters

        Returns:
            ImageSearchResult with detected objects and matched items
        """
        start_time = time.time()

        # Load and process the image
        image = self._load_image(image_data)

        # Generate caption describing the image
        caption = self._generate_caption(image)

        # Detect objects from the caption
        detected_objects = self._detect_objects(image, caption)

        # Search for items matching the detected objects
        matched_items = []
        overall_confidence = 0.0

        if detected_objects and caption:
            # Use the caption as a query to search the knowledge base
            query = ItemQuery(
                query=caption,
                collection=request.collection,
                category=request.category,
                limit=request.limit,
            )

            search_results = self.kb.search(query)

            # Filter by minimum confidence
            matched_items = [
                result
                for result in search_results
                if result.relevance_score >= request.min_confidence
            ]

            if matched_items:
                overall_confidence = sum(r.relevance_score for r in matched_items) / len(
                    matched_items
                )

        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        return ImageSearchResult(
            detected_objects=detected_objects,
            matched_items=matched_items,
            overall_confidence=overall_confidence,
            processing_time_ms=processing_time,
        )

    def identify_from_image(self, image_data: bytes) -> dict:
        """Identify items from an image for NesVentory integration.

        This is a simplified interface that returns the best match.

        Args:
            image_data: Raw image bytes

        Returns:
            Dictionary with identification results
        """
        request = ImageSearchRequest(limit=5, min_confidence=0.3)
        result = self.search_by_image(image_data, request)

        if result.matched_items:
            best_match = result.matched_items[0]
            return {
                "identified": True,
                "confidence": best_match.relevance_score,
                "item": best_match.item,
                "detected_objects": [obj.label for obj in result.detected_objects],
                "alternatives": [match.item for match in result.matched_items[1:]],
            }
        else:
            detected_labels = [obj.label for obj in result.detected_objects]
            return {
                "identified": False,
                "confidence": 0.0,
                "detected_objects": detected_labels,
                "suggestion": "Could not identify any matching Department 56 items from the image.",
            }
