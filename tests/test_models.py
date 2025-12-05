"""Tests for data models."""

import pytest

from plugin_nesventory_llm.models import (
    ItemQuery,
    ItemSearchResult,
    LLMResponse,
    VillageCollection,
    VillageItem,
)


class TestVillageItem:
    """Tests for VillageItem model."""

    def test_create_basic_item(self):
        """Test creating a basic item with required fields."""
        item = VillageItem(id="test-001", name="Test Building")
        assert item.id == "test-001"
        assert item.name == "Test Building"
        assert item.is_retired is False

    def test_create_full_item(self):
        """Test creating an item with all fields."""
        item = VillageItem(
            id="test-002",
            name="Victorian House",
            item_number="56.12345",
            collection="Dickens Village",
            category="Buildings",
            description="A beautiful Victorian house",
            year_introduced=1995,
            year_retired=2005,
            is_retired=True,
            estimated_value_min=50.00,
            estimated_value_max=75.00,
            original_price=45.00,
            dimensions="6.5\" x 4\" x 5.5\"",
            materials="Porcelain, hand-painted",
        )
        assert item.is_retired is True
        assert item.year_retired == 2005
        assert item.estimated_value_min == 50.00

    def test_item_serialization(self):
        """Test that items serialize to dict correctly."""
        item = VillageItem(
            id="test-003",
            name="Test Item",
            collection="Snow Village",
        )
        data = item.model_dump()
        assert data["id"] == "test-003"
        assert data["name"] == "Test Item"
        assert data["collection"] == "Snow Village"


class TestVillageCollection:
    """Tests for VillageCollection model."""

    def test_create_collection(self):
        """Test creating a collection."""
        collection = VillageCollection(
            id="dickens",
            name="Dickens Village",
            description="Victorian-era English village",
            year_started=1984,
        )
        assert collection.id == "dickens"
        assert collection.name == "Dickens Village"
        assert collection.is_active is True
        assert collection.manufacturer == "Department 56"

    def test_retired_collection(self):
        """Test creating a retired collection."""
        collection = VillageCollection(
            id="alpine",
            name="Alpine Village",
            is_active=False,
            year_started=1986,
            year_ended=2005,
        )
        assert collection.is_active is False
        assert collection.year_ended == 2005


class TestItemQuery:
    """Tests for ItemQuery model."""

    def test_basic_query(self):
        """Test creating a basic query."""
        query = ItemQuery(query="Victorian house")
        assert query.query == "Victorian house"
        assert query.limit == 10
        assert query.include_retired is True

    def test_filtered_query(self):
        """Test creating a query with filters."""
        query = ItemQuery(
            query="lighthouse",
            collection="New England Village",
            min_year=1990,
            max_year=2000,
            include_retired=False,
            limit=5,
        )
        assert query.collection == "New England Village"
        assert query.min_year == 1990
        assert query.limit == 5


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_response_with_sources(self):
        """Test creating a response with source items."""
        item = VillageItem(id="test", name="Test Item")
        result = ItemSearchResult(
            item=item,
            relevance_score=0.95,
            match_reason="Name matches",
        )
        response = LLMResponse(
            query="test query",
            answer="Here is the answer",
            sources=[result],
            confidence=0.9,
        )
        assert response.query == "test query"
        assert len(response.sources) == 1
        assert response.confidence == 0.9

    def test_response_no_sources(self):
        """Test creating a response without sources."""
        response = LLMResponse(
            query="unknown item",
            answer="No items found",
            sources=[],
            confidence=0.0,
        )
        assert len(response.sources) == 0
        assert response.confidence == 0.0
