# Enhanced Vision Capabilities - Implementation Guide

## Overview

This PR integrates advanced computer vision capabilities into the existing image search functionality, enhancing Department 56 item identification with:

- **YOLOv8** - State-of-the-art object detection with bounding boxes
- **CLIP** - Vision-language model for semantic visual matching
- **Tesseract OCR** - Text extraction from item labels and signage  
- **BLIP** - Image captioning (existing, retained as fallback)

## Changes Made

### 1. Dependencies (`pyproject.toml`)
Added new vision dependencies:
- `ultralytics>=8.0.0` - YOLOv8 for object detection
- `pytesseract>=0.3.10` - Tesseract OCR wrapper
- `faiss-cpu>=1.7.4` - Fast similarity search (optional)

### 2. Enhanced Image Search (`src/plugin_nesventory_llm/image_search.py`)

**New Features:**
- Multi-modal vision pipeline with graceful fallbacks
- YOLO-based object detection with bounding boxes
- CLIP embeddings for visual catalog matching
- Tesseract OCR for text extraction from detected objects
- Configurable feature flags (`use_yolo`, `use_clip`, `use_ocr`)

**Architecture:**
```
Image Upload
    ↓
YOLOv8 Detection (with bounding boxes)
    ↓
├─→ Tesseract OCR (extract text from each detection)
├─→ CLIP Matching (visual similarity against catalog)
└─→ BLIP Fallback (if YOLO unavailable)
    ↓
Merged Results (CLIP scores + text search)
    ↓
JSON Response
```

**Backward Compatibility:**
- All new features are optional with automatic fallbacks
- Existing BLIP-based captioning still works without setup
- API endpoints remain unchanged
- Existing tests pass without modification

### 3. Enhanced Models (`src/plugin_nesventory_llm/models.py`)

Updated `DetectedObject` model:
```python
class DetectedObject(BaseModel):
    label: str  # Description/label
    confidence: float  # Detection confidence (0-1)
    bounding_box: Optional[list[int]]  # NEW: [x1, y1, x2, y2] pixel coordinates
    ocr_text: Optional[str]  # NEW: Extracted text via OCR
    class_name: Optional[str]  # NEW: YOLO class name
```

### 4. CLIP Catalog Builder (`scripts/build_catalog_embeddings.py`)

New script to build CLIP embeddings from catalog:
- Reads CSV with columns: `sku`, `image_path`, `name`
- Computes normalized CLIP embeddings
- Saves to `.npz` file for fast loading
- Supports batch processing and progress tracking

Usage:
```bash
python scripts/build_catalog_embeddings.py \
  --catalog data/catalog.csv \
  --output data/catalog_embeddings.npz
```

### 5. Docker Support (`Dockerfile`)

Added system dependencies:
- `tesseract-ocr` and `tesseract-ocr-eng` - OCR engine
- `libgl1` and `libglib2.0-0` - OpenGL for YOLO

### 6. Documentation (`README.md`)

- Comprehensive Image Search section with setup instructions
- CLIP catalog preparation guide
- System requirements for Tesseract
- Enhanced response format documentation
- Tips for best results

### 7. Example Files

- `data/catalog.csv.example` - Template for catalog CSV format

## Usage

### Basic Usage (No Setup Required)
The enhanced vision features work automatically with existing endpoints. If optional features aren't set up, the system falls back to BLIP captioning:

```bash
curl -X POST http://localhost:8002/search/image \
  -F "file=@photo.jpg" \
  -F "limit=5"
```

### Advanced Usage (With CLIP Matching)

1. **Prepare Catalog CSV:**
```csv
sku,image_path,name
56789,images/56789.jpg,Victorian House with Lights
56790,images/56790.jpg,Christmas Church
```

2. **Build CLIP Embeddings:**
```bash
python scripts/build_catalog_embeddings.py
```

3. **Use Image Search:**
The service automatically uses CLIP for visual matching when embeddings are available.

## Feature Flags

The `ImageSearchService` supports feature flags for controlling behavior:

```python
service = ImageSearchService(
    knowledge_base=kb,
    use_yolo=True,  # Enable YOLOv8 detection
    use_clip=True,  # Enable CLIP matching
    use_ocr=True,   # Enable Tesseract OCR
    catalog_embeddings_path="data/catalog_embeddings.npz"
)
```

## Fallback Behavior

| Feature | Available | Unavailable |
|---------|-----------|-------------|
| **YOLO** | Detects objects with bounding boxes | Falls back to BLIP captioning |
| **CLIP** | Visual similarity matching | Falls back to text-based search |
| **OCR** | Extracts text from detections | Continues without text extraction |
| **FAISS** | Fast similarity search | Falls back to sklearn NearestNeighbors |

## Testing

Existing tests pass without modification due to backward compatibility:
```bash
pytest tests/test_image_search.py -v
```

The enhanced features are tested through:
1. Graceful degradation when dependencies unavailable
2. Lazy loading of models (no startup penalty)
3. Proper error handling and logging

## Performance Considerations

- **First Request**: 5-10 seconds (model loading)
- **Subsequent Requests**: 1-3 seconds per image
- **GPU Acceleration**: Automatic if CUDA available
- **Memory**: ~2GB additional for loaded models

## Migration Path

**For Existing Users:**
1. Update dependencies: `pip install -e .`
2. (Optional) Install Tesseract: `apt-get install tesseract-ocr`
3. (Optional) Build CLIP catalog: `python scripts/build_catalog_embeddings.py`

**For Docker Users:**
1. Rebuild image: `docker build -t nesventory-llm:latest .`
2. Restart container: `docker-compose up -d`
3. Tesseract is pre-installed in container

## Example Response

**With Enhanced Features:**
```json
{
  "detected_objects": [
    {
      "label": "building at position (120, 45)",
      "confidence": 0.87,
      "bounding_box": [120, 45, 380, 290],
      "ocr_text": "Victorian House 1995",
      "class_name": "building"
    }
  ],
  "matched_items": [
    {
      "item": {...},
      "relevance_score": 0.92,
      "match_reason": "CLIP visual similarity: 0.92"
    }
  ],
  "overall_confidence": 0.92,
  "processing_time_ms": 1247.56
}
```

**Fallback Mode (BLIP only):**
```json
{
  "detected_objects": [
    {
      "label": "a Victorian house with red roof and lights",
      "confidence": 0.85,
      "bounding_box": null,
      "ocr_text": null,
      "class_name": null
    }
  ],
  "matched_items": [...],
  "overall_confidence": 0.78,
  "processing_time_ms": 890.23
}
```

## Future Enhancements

Potential improvements for future PRs:
1. Fine-tune YOLO on Department 56 specific dataset
2. Fine-tune CLIP on Department 56 images
3. Add batch processing endpoint
4. Implement result caching with Redis
5. Add confidence threshold tuning interface
6. Support for custom YOLO models

## References

- YOLOv8: https://github.com/ultralytics/ultralytics
- CLIP: https://github.com/openai/CLIP
- Tesseract: https://github.com/tesseract-ocr/tesseract
- BLIP: https://huggingface.co/Salesforce/blip-image-captioning-base
