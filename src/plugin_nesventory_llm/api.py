"""
FastAPI server for the NesVentory LLM Plugin.

This provides REST API endpoints for querying the Department 56
village collectibles knowledge base.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__
from .knowledge_base import KnowledgeBase
from .models import ItemQuery, ItemSearchResult, LLMResponse, VillageItem

logger = logging.getLogger(__name__)

# Global knowledge base instance
kb: Optional[KnowledgeBase] = None


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
    global kb

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

    yield

    # Cleanup
    kb = None


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


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check the health status of the plugin."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        items_loaded=len(kb.items) if kb else 0,
        embeddings_ready=kb.embeddings is not None if kb else False,
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
async def identify_item(query: str = Query(..., description="Item name or description to identify")):
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


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app.

    Useful for testing or custom configurations.
    """
    return app
