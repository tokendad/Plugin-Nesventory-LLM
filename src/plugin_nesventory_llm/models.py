"""
Data models for Department 56 Village Collectibles.

These models represent the structure of collectible items from
The Village Chronicler's collections (thevillagechronicler.com).
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ScrapeMode(str, Enum):
    """Scrape mode options."""

    LOCAL = "local"  # Scrape from local mirror files
    REMOTE = "remote"  # Scrape from remote websites
    INTERNET = "internet"  # Search internet with tailored phrases


class VillageItem(BaseModel):
    """Represents a Department 56 village collectible item."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "dept56-56789",
                "name": "Victorian House",
                "item_number": "56.12345",
                "collection": "Dickens Village",
                "category": "Buildings",
                "description": "A beautiful Victorian-style house with detailed architecture",
                "year_introduced": 1995,
                "year_retired": 2005,
                "is_retired": True,
                "estimated_value_min": 50.00,
                "estimated_value_max": 75.00,
                "original_price": 45.00,
                "dimensions": '6.5" x 4" x 5.5"',
                "materials": "Porcelain, hand-painted",
                "notes": "Limited edition of 5000 pieces",
            }
        }
    )

    id: str = Field(..., description="Unique identifier for the item")
    name: str = Field(..., description="Name of the collectible item")
    item_number: Optional[str] = Field(None, description="Official Department 56 item number")
    collection: Optional[str] = Field(None, description="Collection the item belongs to")
    category: Optional[str] = Field(None, description="Category (e.g., buildings, accessories)")
    description: Optional[str] = Field(None, description="Detailed description of the item")
    year_introduced: Optional[int] = Field(None, description="Year the item was first released")
    year_retired: Optional[int] = Field(
        None, description="Year the item was retired (if applicable)"
    )
    is_retired: bool = Field(False, description="Whether the item has been retired")
    estimated_value_min: Optional[float] = Field(None, description="Minimum estimated value in USD")
    estimated_value_max: Optional[float] = Field(None, description="Maximum estimated value in USD")
    original_price: Optional[float] = Field(None, description="Original retail price in USD")
    dimensions: Optional[str] = Field(None, description="Physical dimensions of the item")
    materials: Optional[str] = Field(None, description="Materials used in construction")
    notes: Optional[str] = Field(None, description="Additional notes or special information")
    image_url: Optional[str] = Field(None, description="URL to item image")
    source_url: Optional[str] = Field(None, description="URL where item information was sourced")


class VillageCollection(BaseModel):
    """Represents a collection of village items (e.g., Dickens Village, Snow Village)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "dickens-village",
                "name": "Dickens Village",
                "description": "Victorian-era English village inspired by Charles Dickens works",
                "manufacturer": "Department 56",
                "year_started": 1984,
                "is_active": True,
                "item_count": 500,
            }
        }
    )

    id: str = Field(..., description="Unique identifier for the collection")
    name: str = Field(..., description="Name of the collection")
    description: Optional[str] = Field(None, description="Description of the collection")
    manufacturer: str = Field("Department 56", description="Manufacturer name")
    year_started: Optional[int] = Field(None, description="Year the collection was introduced")
    year_ended: Optional[int] = Field(None, description="Year the collection ended (if applicable)")
    is_active: bool = Field(True, description="Whether the collection is still active")
    item_count: int = Field(0, description="Number of items in the collection")


class ItemQuery(BaseModel):
    """Query model for searching village items."""

    query: str = Field(..., description="Natural language query about village items")
    collection: Optional[str] = Field(None, description="Filter by specific collection")
    category: Optional[str] = Field(None, description="Filter by category")
    min_year: Optional[int] = Field(None, description="Minimum year introduced")
    max_year: Optional[int] = Field(None, description="Maximum year introduced")
    include_retired: bool = Field(True, description="Include retired items in results")
    limit: int = Field(10, description="Maximum number of results to return", ge=1, le=100)


class ItemSearchResult(BaseModel):
    """Result from an item search query."""

    item: VillageItem
    relevance_score: float = Field(..., description="Relevance score (0-1)")
    match_reason: Optional[str] = Field(None, description="Explanation of why this item matched")


class LLMResponse(BaseModel):
    """Response from the LLM service."""

    query: str = Field(..., description="Original query")
    answer: str = Field(..., description="Generated answer")
    sources: list[ItemSearchResult] = Field(
        default_factory=list, description="Source items used to generate the answer"
    )
    confidence: float = Field(..., description="Confidence score (0-1)")


class ImageSearchRequest(BaseModel):
    """Request model for image-based search."""

    collection: Optional[str] = Field(None, description="Filter by specific collection")
    category: Optional[str] = Field(None, description="Filter by category")
    limit: int = Field(10, description="Maximum number of results to return", ge=1, le=100)
    min_confidence: float = Field(0.3, description="Minimum confidence threshold", ge=0.0, le=1.0)


class DetectedObject(BaseModel):
    """Represents an object detected in an image."""

    label: str = Field(..., description="Description/label of the detected object")
    confidence: float = Field(..., description="Detection confidence (0-1)")
    bounding_box: Optional[dict] = Field(None, description="Bounding box coordinates")


class ImageSearchResult(BaseModel):
    """Result from an image-based search."""

    detected_objects: list[DetectedObject] = Field(
        default_factory=list, description="Objects detected in the image"
    )
    matched_items: list[ItemSearchResult] = Field(
        default_factory=list, description="Items matched from detected objects"
    )
    overall_confidence: float = Field(..., description="Overall confidence score (0-1)")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class ConnectionTestResponse(BaseModel):
    """Response from connection test endpoint."""

    status: str = Field(..., description="Overall connection status: 'ok', 'degraded', or 'error'")
    version: str = Field(..., description="Plugin version")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the test")
    checks: dict[str, dict] = Field(
        ...,
        description="Individual component check results with status and optional error details",
    )
    error_codes: list[str] = Field(
        default_factory=list, description="List of error codes if any issues detected"
    )
    message: Optional[str] = Field(None, description="Human-readable status message")


class ScrapeRequest(BaseModel):
    """Request model for scraping data."""

    mode: ScrapeMode = Field(
        ScrapeMode.LOCAL, description="Scrape mode: local, remote, or internet"
    )
    search_terms: Optional[list[str]] = Field(
        None, description="Search terms for internet scraping mode"
    )
