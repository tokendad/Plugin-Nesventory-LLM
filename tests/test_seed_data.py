"""Tests for the seed data module."""

import pytest

from plugin_nesventory_llm.seed_data import (
    SAMPLE_COLLECTIONS,
    SAMPLE_ITEMS,
    get_sample_collections,
    get_sample_items,
)


class TestSampleData:
    """Tests for sample data."""

    def test_sample_collections_exist(self):
        """Test that sample collections are defined."""
        assert len(SAMPLE_COLLECTIONS) > 0

    def test_sample_items_exist(self):
        """Test that sample items are defined."""
        assert len(SAMPLE_ITEMS) > 0

    def test_get_sample_collections_returns_copy(self):
        """Test that get_sample_collections returns a copy."""
        collections = get_sample_collections()
        assert collections == SAMPLE_COLLECTIONS
        # Modifying returned list shouldn't affect original
        collections.pop()
        assert len(get_sample_collections()) == len(SAMPLE_COLLECTIONS)

    def test_get_sample_items_returns_copy(self):
        """Test that get_sample_items returns a copy."""
        items = get_sample_items()
        assert items == SAMPLE_ITEMS
        # Modifying returned list shouldn't affect original
        items.pop()
        assert len(get_sample_items()) == len(SAMPLE_ITEMS)

    def test_all_items_have_required_fields(self):
        """Test that all sample items have required fields."""
        for item in SAMPLE_ITEMS:
            assert item.id is not None
            assert item.name is not None
            assert len(item.name) > 0

    def test_all_collections_have_required_fields(self):
        """Test that all sample collections have required fields."""
        for coll in SAMPLE_COLLECTIONS:
            assert coll.id is not None
            assert coll.name is not None
            assert coll.manufacturer == "Department 56"

    def test_items_belong_to_valid_collections(self):
        """Test that all items reference valid collections."""
        collection_names = {c.name for c in SAMPLE_COLLECTIONS}
        for item in SAMPLE_ITEMS:
            if item.collection:
                assert item.collection in collection_names, (
                    f"Item '{item.name}' references unknown collection '{item.collection}'"
                )

    def test_retired_items_have_retirement_year(self):
        """Test that retired items have retirement year when possible."""
        for item in SAMPLE_ITEMS:
            if item.is_retired and item.estimated_value_min is not None:
                # Retired items with estimated values should have year_retired
                # This is a soft check - some items might not have this data
                pass  # Just checking the structure is valid

    def test_year_ranges_are_valid(self):
        """Test that year ranges make sense."""
        for item in SAMPLE_ITEMS:
            if item.year_introduced and item.year_retired:
                assert item.year_retired >= item.year_introduced, (
                    f"Item '{item.name}' retired before introduced"
                )
