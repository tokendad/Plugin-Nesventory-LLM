"""
Image search module for Department 56 village collectibles.

This module provides image analysis and object detection capabilities
for identifying collectible items from uploaded images using:
- YOLOv8 for object detection
- CLIP for image embeddings and catalog matching
- Tesseract OCR for text extraction
- BLIP for image captioning (fallback)
"""

import logging
import os
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
DEFAULT_CLIP_MODEL = "openai/clip-vit-base-patch32"
DEFAULT_YOLO_MODEL = "yolov8n.pt"

# Default confidence for caption-based object detection
DEFAULT_DETECTION_CONFIDENCE = 0.85


class ImageSearchService:
    """Service for analyzing images and finding matching collectible items."""

    def __init__(
        self, 
        knowledge_base, 
        vision_model: str = DEFAULT_VISION_MODEL,
        clip_model: str = DEFAULT_CLIP_MODEL,
        yolo_model: str = DEFAULT_YOLO_MODEL,
        use_yolo: bool = True,
        use_clip: bool = True,
        use_ocr: bool = True,
        catalog_embeddings_path: str = "data/catalog_embeddings.npz"
    ):
        """Initialize the image search service.

        Args:
            knowledge_base: KnowledgeBase instance for searching items
            vision_model: Name of the BLIP vision model to use for captioning
            clip_model: Name of the CLIP model to use for embeddings
            yolo_model: Name of the YOLO model to use for detection
            use_yolo: Whether to use YOLO for detection (falls back to BLIP if False)
            use_clip: Whether to use CLIP for matching (uses text search if False)
            use_ocr: Whether to use Tesseract OCR for text extraction
            catalog_embeddings_path: Path to precomputed CLIP catalog embeddings
        """
        self.kb = knowledge_base
        self.vision_model_name = vision_model
        self.clip_model_name = clip_model
        self.yolo_model_name = yolo_model
        self.use_yolo = use_yolo
        self.use_clip = use_clip
        self.use_ocr = use_ocr
        self.catalog_embeddings_path = catalog_embeddings_path
        
        # Lazy-loaded components
        self._vision_model = None
        self._vision_processor = None
        self._yolo_detector = None
        self._clip_model = None
        self._clip_processor = None
        self._clip_embeddings = None
        self._clip_skus = None
        self._clip_names = None
        self._clip_index = None
        self._ocr_available = None

    @property
    def vision_model(self):
        """Lazy load the BLIP vision model."""
        if self._vision_model is None:
            try:
                from transformers import BlipForConditionalGeneration, BlipProcessor

                logger.info(f"Loading BLIP vision model: {self.vision_model_name}")
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
        """Get the BLIP vision processor."""
        if self._vision_processor is None:
            # Trigger lazy loading
            _ = self.vision_model
        return self._vision_processor
    
    @property
    def yolo_detector(self):
        """Lazy load the YOLO detector."""
        if self._yolo_detector is None and self.use_yolo:
            try:
                from ultralytics import YOLO
                logger.info(f"Loading YOLO model: {self.yolo_model_name}")
                
                # Ensure model is downloaded to cache directory
                # If YOLO_CONFIG_DIR is set, ultralytics will use it for model storage
                # Otherwise, construct path in cache directory
                cache_dir = os.environ.get('YOLO_CONFIG_DIR', os.path.expanduser('~/.cache/Ultralytics'))
                model_cache_path = Path(cache_dir) / 'models' / self.yolo_model_name
                
                # Create cache directory if it doesn't exist
                model_cache_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Check if model exists in cache, otherwise YOLO will download it there
                if model_cache_path.exists():
                    logger.info(f"Using cached YOLO model from {model_cache_path}")
                    self._yolo_detector = YOLO(str(model_cache_path))
                else:
                    logger.info(f"Downloading YOLO model to {model_cache_path}")
                    # Download to cache directory
                    self._yolo_detector = YOLO(self.yolo_model_name)
                    # Move downloaded model to cache if it was downloaded to current directory
                    if Path(self.yolo_model_name).exists():
                        Path(self.yolo_model_name).rename(model_cache_path)
                        self._yolo_detector = YOLO(str(model_cache_path))
            except ImportError:
                logger.warning("ultralytics not installed. Falling back to BLIP captioning.")
                self.use_yolo = False
            except Exception as e:
                logger.warning(f"Failed to load YOLO model: {e}. Falling back to BLIP captioning.")
                self.use_yolo = False
        return self._yolo_detector
    
    @property
    def clip_model(self):
        """Lazy load the CLIP model."""
        if self._clip_model is None and self.use_clip:
            try:
                from transformers import CLIPModel, CLIPProcessor
                import torch
                
                logger.info(f"Loading CLIP model: {self.clip_model_name}")
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self._clip_processor = CLIPProcessor.from_pretrained(self.clip_model_name)
                self._clip_model = CLIPModel.from_pretrained(self.clip_model_name).to(self.device)
                
                # Load catalog embeddings if available
                if os.path.exists(self.catalog_embeddings_path):
                    self._load_clip_embeddings()
                else:
                    logger.warning(
                        f"No CLIP catalog embeddings found at {self.catalog_embeddings_path}. "
                        "CLIP matching will be unavailable. "
                        "Run scripts/build_catalog_embeddings.py to create embeddings."
                    )
                    
            except ImportError:
                logger.warning("transformers/torch not installed. CLIP matching unavailable.")
                self.use_clip = False
            except Exception as e:
                logger.warning(f"Failed to initialize CLIP: {e}")
                self.use_clip = False
        return self._clip_model
    
    @property
    def clip_processor(self):
        """Get the CLIP processor."""
        if self._clip_processor is None and self.use_clip:
            # Trigger lazy loading
            _ = self.clip_model
        return self._clip_processor
    
    @property
    def ocr_available(self):
        """Check if Tesseract OCR is available."""
        if self._ocr_available is None and self.use_ocr:
            try:
                import pytesseract
                # Try a simple test to see if tesseract is installed
                pytesseract.get_tesseract_version()
                self._ocr_available = True
                logger.info("Tesseract OCR initialized")
            except Exception as e:
                logger.warning(f"Tesseract OCR not available: {e}")
                self._ocr_available = False
                self.use_ocr = False
        return self._ocr_available
    
    def _load_clip_embeddings(self):
        """Load precomputed CLIP embeddings for catalog matching."""
        try:
            data = np.load(self.catalog_embeddings_path)
            self._clip_embeddings = data['embeddings']
            self._clip_skus = data['skus']
            self._clip_names = data['names']
            
            # Normalize embeddings for cosine similarity
            norms = np.linalg.norm(self._clip_embeddings, axis=1, keepdims=True)
            self._clip_embeddings = self._clip_embeddings / norms
            
            # Try to use FAISS if available, otherwise fall back to sklearn
            try:
                import faiss
                dimension = self._clip_embeddings.shape[1]
                self._clip_index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
                self._clip_index.add(self._clip_embeddings.astype('float32'))
                logger.info(f"Loaded {len(self._clip_skus)} catalog embeddings with FAISS index")
            except ImportError:
                from sklearn.neighbors import NearestNeighbors
                self._clip_index = NearestNeighbors(n_neighbors=10, metric='cosine', algorithm='brute')
                self._clip_index.fit(self._clip_embeddings)
                logger.info(f"Loaded {len(self._clip_skus)} catalog embeddings with sklearn index")
        except Exception as e:
            logger.warning(f"Failed to load CLIP embeddings: {e}")
            self._clip_embeddings = None

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
        """Generate a descriptive caption for the image using BLIP.

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

    def _extract_ocr_text(self, image: Image.Image) -> str:
        """Extract text from image using Tesseract OCR.
        
        Args:
            image: PIL Image object
            
        Returns:
            Extracted text string
        """
        if not self.use_ocr or not self.ocr_available:
            return ""
        
        try:
            import pytesseract
            text = pytesseract.image_to_string(image, lang="eng")
            return text.strip()
        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")
            return ""

    def _detect_with_yolo(self, image: Image.Image) -> list[DetectedObject]:
        """Detect objects using YOLOv8.
        
        Args:
            image: PIL Image object
            
        Returns:
            List of detected objects with bounding boxes
        """
        if not self.use_yolo or self.yolo_detector is None:
            return []
        
        try:
            # Run YOLO inference
            results = self.yolo_detector(image, conf=0.25, verbose=False)
            
            detected_objects = []
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    # Extract box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    class_name = result.names[class_id]
                    
                    # Crop the detection for OCR
                    crop = image.crop((int(x1), int(y1), int(x2), int(y2)))
                    ocr_text = self._extract_ocr_text(crop)
                    
                    detected_objects.append(DetectedObject(
                        label=f"{class_name} at position ({int(x1)}, {int(y1)})",
                        confidence=confidence,
                        bounding_box=[int(x1), int(y1), int(x2), int(y2)],
                        ocr_text=ocr_text if ocr_text else None,
                        class_name=class_name
                    ))
            
            logger.info(f"YOLO detected {len(detected_objects)} objects")
            return detected_objects
            
        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
            return []

    def _detect_objects(self, image: Image.Image, caption: str) -> list[DetectedObject]:
        """Detect objects in the image.

        Uses YOLO if available, otherwise falls back to BLIP captioning.

        Args:
            image: PIL Image object
            caption: Generated caption for the image

        Returns:
            List of detected objects
        """
        # Try YOLO first
        if self.use_yolo:
            yolo_detections = self._detect_with_yolo(image)
            if yolo_detections:
                return yolo_detections
        
        # Fallback to caption-based detection
        if not caption:
            return []

        # Extract OCR from full image as fallback
        ocr_text = self._extract_ocr_text(image)
        
        detected = DetectedObject(
            label=caption,
            confidence=DEFAULT_DETECTION_CONFIDENCE,
            bounding_box=None,
            ocr_text=ocr_text if ocr_text else None,
        )

        return [detected]
    
    def _compute_clip_embedding(self, image: Image.Image) -> Optional[np.ndarray]:
        """Compute CLIP image embedding.
        
        Args:
            image: PIL Image object
            
        Returns:
            Normalized CLIP embedding array or None
        """
        if not self.use_clip or self._clip_model is None:
            return None
        
        try:
            import torch
            
            inputs = self.clip_processor(images=image, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                image_features = self._clip_model.get_image_features(**inputs)
                # Normalize for cosine similarity
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            return image_features.cpu().numpy()[0]
        except Exception as e:
            logger.warning(f"CLIP embedding computation failed: {e}")
            return None
    
    def _match_with_clip(self, crop_image: Image.Image, top_k: int = 5) -> list[dict]:
        """Match a crop against catalog using CLIP embeddings.
        
        Args:
            crop_image: PIL Image of detected object
            top_k: Number of top matches to return
            
        Returns:
            List of matches with sku, name, and score
        """
        if not self.use_clip or self._clip_embeddings is None:
            return []
        
        # Compute embedding for the crop
        query_embedding = self._compute_clip_embedding(crop_image)
        if query_embedding is None:
            return []
        
        try:
            # Search for nearest neighbors
            if hasattr(self._clip_index, 'search'):  # FAISS
                scores, indices = self._clip_index.search(
                    query_embedding.reshape(1, -1).astype('float32'),
                    min(top_k, len(self._clip_skus))
                )
                scores = scores[0]
                indices = indices[0]
            else:  # sklearn
                distances, indices = self._clip_index.kneighbors(
                    query_embedding.reshape(1, -1),
                    n_neighbors=min(top_k, len(self._clip_skus))
                )
                # Convert distances to similarity scores
                scores = 1.0 - distances[0]
                indices = indices[0]
            
            # Build result list
            matches = []
            for idx, score in zip(indices, scores):
                matches.append({
                    'sku': str(self._clip_skus[idx]),
                    'name': str(self._clip_names[idx]),
                    'score': float(score)
                })
            
            return matches
        except Exception as e:
            logger.warning(f"CLIP matching failed: {e}")
            return []

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

        # Generate caption describing the image (always useful for context)
        caption = self._generate_caption(image)

        # Detect objects (YOLO or caption-based)
        detected_objects = self._detect_objects(image, caption)

        # Search for items matching the detected objects
        matched_items = []
        overall_confidence = 0.0

        if detected_objects:
            # Try CLIP matching first if available
            if self.use_clip and self._clip_embeddings is not None:
                # For each detected object, get CLIP matches
                all_clip_matches = []
                for obj in detected_objects:
                    # Get crop if available
                    if obj.bounding_box:
                        x1, y1, x2, y2 = obj.bounding_box
                        crop = image.crop((x1, y1, x2, y2))
                    else:
                        crop = image
                    
                    clip_matches = self._match_with_clip(crop, top_k=request.limit)
                    all_clip_matches.extend(clip_matches)
                
                # Convert CLIP matches to ItemSearchResult format
                # For now, we'll search KB by SKU to get full item details
                seen_skus = set()
                for match in all_clip_matches:
                    if match['sku'] not in seen_skus and match['score'] >= request.min_confidence:
                        seen_skus.add(match['sku'])
                        # Try to find item in KB by SKU/name
                        query = ItemQuery(
                            query=match['name'],
                            limit=1
                        )
                        kb_results = self.kb.search(query)
                        if kb_results:
                            # Use CLIP score instead of text relevance score
                            result = kb_results[0]
                            result.relevance_score = match['score']
                            result.match_reason = f"CLIP visual similarity: {match['score']:.2f}"
                            matched_items.append(result)
                        
                        if len(matched_items) >= request.limit:
                            break
            
            # Fallback to text-based search if CLIP didn't find enough matches
            if len(matched_items) < request.limit and caption:
                query = ItemQuery(
                    query=caption,
                    collection=request.collection,
                    category=request.category,
                    limit=request.limit - len(matched_items),
                )

                search_results = self.kb.search(query)

                # Filter by minimum confidence and avoid duplicates
                seen_item_ids = {item.item.id for item in matched_items}
                for result in search_results:
                    if result.relevance_score >= request.min_confidence and result.item.id not in seen_item_ids:
                        matched_items.append(result)
                        seen_item_ids.add(result.item.id)

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
