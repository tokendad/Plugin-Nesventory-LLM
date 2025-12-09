"""
FastAPI server for the NesVentory LLM Plugin.

This provides REST API endpoints for querying the Department 56
village collectibles knowledge base.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .knowledge_base import KnowledgeBase
from .models import (
    ConnectionTestResponse,
    ImageSearchRequest,
    ImageSearchResult,
    ItemQuery,
    ItemSearchResult,
    LLMResponse,
    VillageItem,
)

logger = logging.getLogger(__name__)

# Global knowledge base instance
kb: Optional[KnowledgeBase] = None
# Global image search service
image_search_service = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    items_loaded: int
    embeddings_ready: bool


class QueryRequest(BaseModel):
    """Request body for query endpoint."""

    query: str
    collection: Optional[str] = None
    category: Optional[str] = None
    limit: int = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize knowledge base on startup."""
    global kb, image_search_service

    data_dir = Path("data")
    kb = KnowledgeBase(data_dir=data_dir)

    # Try to load existing data
    items_loaded = kb.load_items()
    if items_loaded > 0:
        logger.info(f"Loaded {items_loaded} items from data directory")
        try:
            kb.build_embeddings()
        except Exception as e:
            logger.warning(f"Could not build embeddings on startup: {e}")
    else:
        logger.info("No items found. Use /scrape endpoint to fetch data.")

    # Initialize image search service
    try:
        from .image_search import ImageSearchService

        image_search_service = ImageSearchService(kb)
        logger.info("Image search service initialized")
    except Exception as e:
        logger.warning(f"Could not initialize image search service: {e}")
        image_search_service = None

    yield

    # Cleanup
    kb = None
    image_search_service = None


app = FastAPI(
    title="NesVentory LLM Plugin",
    description="LLM-powered assistant for Department 56 Village Collectibles inventory",
    version=__version__,
    lifespan=lifespan,
)

# Enable CORS for integration with NesVentory frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for the status page
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serve the status page."""
    static_file = Path(__file__).parent / "static" / "index.html"
    if static_file.exists():
        return FileResponse(static_file)
    return {"message": "NesVentory LLM Plugin API", "version": __version__}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check the health status of the plugin."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        items_loaded=len(kb.items) if kb else 0,
        embeddings_ready=kb.embeddings is not None if kb else False,
    )


@app.get("/connection/test", response_model=ConnectionTestResponse)
async def connection_test():
    """Test the connection and status of the LLM plugin.

    This endpoint provides a comprehensive status check for NesVentory integration,
    including the state of all major components and any error conditions.

    Returns:
        ConnectionTestResponse with overall status, individual component checks,
        and any error codes encountered.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    checks = {}
    error_codes = []
    overall_status = "ok"

    # Check 1: Knowledge base initialization
    if kb is None:
        checks["knowledge_base"] = {
            "status": "error",
            "message": "Knowledge base not initialized",
        }
        error_codes.append("KB_NOT_INITIALIZED")
        overall_status = "error"
    else:
        checks["knowledge_base"] = {
            "status": "ok",
            "message": "Knowledge base initialized successfully",
        }

    # Check 2: Items loaded
    if kb and len(kb.items) == 0:
        checks["items"] = {
            "status": "warning",
            "message": "No items loaded in knowledge base",
            "count": 0,
        }
        error_codes.append("NO_ITEMS_LOADED")
        if overall_status == "ok":
            overall_status = "degraded"
    elif kb:
        checks["items"] = {
            "status": "ok",
            "message": f"{len(kb.items)} items loaded",
            "count": len(kb.items),
        }
    else:
        checks["items"] = {
            "status": "error",
            "message": "Cannot check items - knowledge base not initialized",
            "count": 0,
        }

    # Check 3: Embeddings status
    if kb and kb.embeddings is None:
        checks["embeddings"] = {
            "status": "warning",
            "message": "Embeddings not built - semantic search unavailable",
        }
        error_codes.append("EMBEDDINGS_NOT_READY")
        if overall_status == "ok":
            overall_status = "degraded"
    elif kb:
        checks["embeddings"] = {
            "status": "ok",
            "message": "Embeddings built and ready for semantic search",
            "shape": list(kb.embeddings.shape) if kb.embeddings is not None else None,
        }
    else:
        checks["embeddings"] = {
            "status": "error",
            "message": "Cannot check embeddings - knowledge base not initialized",
        }

    # Check 4: Embedding model availability
    if kb:
        try:
            # Try to access the model (this will trigger lazy loading if needed)
            _ = kb.model
            checks["embedding_model"] = {
                "status": "ok",
                "message": f"Embedding model '{kb.model_name}' loaded successfully",
                "model_name": kb.model_name,
            }
        except Exception as e:
            checks["embedding_model"] = {
                "status": "error",
                "message": f"Failed to load embedding model: {str(e)}",
                "model_name": kb.model_name,
            }
            error_codes.append("EMBEDDING_MODEL_ERROR")
            overall_status = "error"
    else:
        checks["embedding_model"] = {
            "status": "error",
            "message": "Cannot check embedding model - knowledge base not initialized",
        }

    # Check 5: Image search service
    if image_search_service is None:
        checks["image_search"] = {
            "status": "warning",
            "message": "Image search service not available",
        }
        error_codes.append("IMAGE_SEARCH_UNAVAILABLE")
        if overall_status == "ok":
            overall_status = "degraded"
    else:
        checks["image_search"] = {
            "status": "ok",
            "message": "Image search service initialized and ready",
        }

    # Create human-readable message
    if overall_status == "ok":
        message = "All systems operational"
    elif overall_status == "degraded":
        message = "System operational with some features unavailable"
    else:
        message = "System has critical errors"

    return ConnectionTestResponse(
        status=overall_status,
        version=__version__,
        timestamp=timestamp,
        checks=checks,
        error_codes=error_codes,
        message=message,
    )


@app.get("/stats")
async def get_stats():
    """Get statistics about the knowledge base."""
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")
    return kb.get_stats()


@app.post("/query", response_model=LLMResponse)
async def query_items(request: QueryRequest):
    """Query the knowledge base with natural language.

    This endpoint uses semantic search to find relevant items and
    generates a natural language response.
    """
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    if not kb.items:
        raise HTTPException(
            status_code=404,
            detail="No items in knowledge base. Use /scrape to fetch data first.",
        )

    return kb.generate_response(request.query, limit=request.limit)


@app.post("/search", response_model=list[ItemSearchResult])
async def search_items(query: ItemQuery):
    """Search for items using semantic similarity.

    Returns a list of matching items with relevance scores.
    """
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    if not kb.items:
        raise HTTPException(
            status_code=404,
            detail="No items in knowledge base. Use /scrape to fetch data first.",
        )

    return kb.search(query)


@app.get("/items", response_model=list[VillageItem])
async def list_items(
    collection: Optional[str] = Query(None, description="Filter by collection"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List all items in the knowledge base with optional filtering."""
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    items = kb.items

    if collection:
        items = [i for i in items if i.collection == collection]

    if category:
        items = [i for i in items if i.category == category]

    return items[offset : offset + limit]


@app.get("/items/{item_id}", response_model=VillageItem)
async def get_item(item_id: str):
    """Get a specific item by ID."""
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    for item in kb.items:
        if item.id == item_id:
            return item

    raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")


@app.post("/scrape")
async def scrape_data():
    """Trigger a scrape of the Village Chronicler website.

    This fetches the latest item data and rebuilds the embeddings.
    """
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    try:
        from .scraper import VillageChroniclerScraper

        with VillageChroniclerScraper(kb.data_dir) as scraper:
            collections, items = scraper.scrape_all()
            scraper.save_data()

        # Reload the knowledge base
        kb.items = items
        kb.build_embeddings(force=True)

        return {
            "status": "success",
            "collections_found": len(collections),
            "items_found": len(items),
        }
    except Exception as e:
        logger.exception("Scraping failed")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@app.post("/build")
async def build_embeddings():
    """Build or rebuild embeddings for the knowledge base.

    This creates the semantic search index for all items.
    """
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    if not kb.items:
        raise HTTPException(
            status_code=404,
            detail="No items in knowledge base. Use /scrape to fetch data first.",
        )

    try:
        embeddings = kb.build_embeddings(force=True)
        return {
            "status": "success",
            "items_count": len(kb.items),
            "shape": list(embeddings.shape) if embeddings is not None else None,
        }
    except Exception as e:
        logger.exception("Building embeddings failed")
        raise HTTPException(status_code=500, detail=f"Building embeddings failed: {str(e)}")


@app.post("/items/add", response_model=VillageItem)
async def add_item(item: VillageItem):
    """Add a new item to the knowledge base.

    This is useful for manually adding items or integrating with NesVentory.
    """
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    # Check for duplicates
    for existing in kb.items:
        if existing.id == item.id:
            raise HTTPException(status_code=409, detail=f"Item already exists: {item.id}")

    kb.add_items([item])
    return item


# NesVentory Integration Endpoints


@app.get("/nesventory/collections")
async def get_nesventory_collections():
    """Get collections formatted for NesVentory integration.

    Returns data in a format compatible with NesVentory's item import.
    """
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    collections = {}
    for item in kb.items:
        coll = item.collection or "Uncategorized"
        if coll not in collections:
            collections[coll] = {"name": coll, "item_count": 0, "items": []}
        collections[coll]["item_count"] += 1
        collections[coll]["items"].append(item.id)

    return list(collections.values())


@app.post("/nesventory/identify")
async def identify_item(
    query: str = Query(..., description="Item name or description to identify")
):
    """Identify an item from user input.

    This endpoint is designed for NesVentory integration - given a user's
    description of an item, it tries to identify the exact Department 56 item.
    """
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    if not kb.items:
        raise HTTPException(status_code=404, detail="No items in knowledge base")

    response = kb.generate_response(query, limit=3)

    if response.sources:
        best_match = response.sources[0]
        return {
            "identified": True,
            "confidence": response.confidence,
            "item": best_match.item,
            "alternatives": [s.item for s in response.sources[1:]],
        }
    else:
        return {"identified": False, "confidence": 0.0, "suggestion": response.answer}


# Image Search Endpoints


@app.post("/search/image", response_model=ImageSearchResult)
async def search_by_image(
    file: UploadFile = File(..., description="Image file containing Department 56 items"),
    collection: Optional[str] = Query(None, description="Filter by collection"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results to return"),
    min_confidence: float = Query(0.3, ge=0.0, le=1.0, description="Minimum confidence threshold"),
):
    """Search for items by uploading an image.

    Upload an image containing one or more Department 56 collectible items.
    The system will detect objects in the image and match them against the
    knowledge base.

    Supported image formats: JPEG, PNG, WebP, BMP
    """
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    if not kb.items:
        raise HTTPException(status_code=404, detail="No items in knowledge base")

    if not image_search_service:
        raise HTTPException(
            status_code=503,
            detail="Image search service not available. Check server logs for details.",
        )

    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, detail=f"Invalid file type: {file.content_type}. Must be an image."
        )

    try:
        # Read image data
        image_data = await file.read()

        # Create search request
        request = ImageSearchRequest(
            collection=collection,
            category=category,
            limit=limit,
            min_confidence=min_confidence,
        )

        # Perform image search
        result = image_search_service.search_by_image(image_data, request)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Image search failed")
        raise HTTPException(status_code=500, detail=f"Image search failed: {str(e)}")


@app.post("/nesventory/identify/image")
async def identify_item_from_image(
    file: UploadFile = File(..., description="Image file containing a Department 56 item"),
):
    """Identify items from an image for NesVentory integration.

    This endpoint is designed for NesVentory integration. Upload an image
    containing Department 56 collectible items, and the system will attempt
    to identify them.

    Returns the best match along with alternatives and detected object descriptions.
    """
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    if not kb.items:
        raise HTTPException(status_code=404, detail="No items in knowledge base")

    if not image_search_service:
        raise HTTPException(
            status_code=503,
            detail="Image search service not available. Check server logs for details.",
        )

    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, detail=f"Invalid file type: {file.content_type}. Must be an image."
        )

    try:
        # Read image data
        image_data = await file.read()

        # Identify items from image
        result = image_search_service.identify_from_image(image_data)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Image identification failed")
        raise HTTPException(status_code=500, detail=f"Image identification failed: {str(e)}")


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app.

    Useful for testing or custom configurations.
    """
    return app
