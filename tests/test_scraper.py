"""
Tests for the Village Chronicler scraper.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup

from plugin_nesventory_llm.scraper import (
    VillageChroniclerScraper,
    parse_date_range,
    parse_year,
    parse_price,
    clean_text,
    generate_item_id,
)


class TestUtilityFunctions:
    """Test utility functions in the scraper module."""

    def test_parse_date_range_with_end_year(self):
        """Test parsing date range with both start and end year."""
        year_start, year_end = parse_date_range("1995-1998")
        assert year_start == 1995
        assert year_end == 1998

    def test_parse_date_range_with_present(self):
        """Test parsing date range with 'Present' as end."""
        year_start, year_end = parse_date_range("2000-Present")
        assert year_start == 2000
        assert year_end is None

    def test_parse_date_range_single_year(self):
        """Test parsing single year."""
        year_start, year_end = parse_date_range("2005")
        assert year_start == 2005
        assert year_end is None

    def test_parse_date_range_empty(self):
        """Test parsing empty date."""
        year_start, year_end = parse_date_range("")
        assert year_start is None
        assert year_end is None

    def test_parse_year(self):
        """Test parsing year from text."""
        assert parse_year("Released in 1995") == 1995
        assert parse_year("2000-2005") == 2000
        assert parse_year("No year here") is None

    def test_parse_price(self):
        """Test parsing price from text."""
        assert parse_price("$45.00") == 45.0
        assert parse_price("Price: $1,234.56") == 1234.56
        assert parse_price("50") == 50.0
        assert parse_price("No price") is None

    def test_clean_text(self):
        """Test text cleaning."""
        assert clean_text("  Multiple   spaces  ") == "Multiple spaces"
        assert clean_text("Line\nbreaks\ttabs") == "Line breaks tabs"
        assert clean_text("") == ""

    def test_generate_item_id(self):
        """Test item ID generation."""
        id1 = generate_item_id("Victorian House", "56.12345")
        id2 = generate_item_id("Victorian House", "56.12345")
        id3 = generate_item_id("Victorian House", "56.54321")
        
        assert id1 == id2  # Same inputs produce same ID
        assert id1 != id3  # Different inputs produce different IDs
        assert id1.startswith("dept56-")


class TestScraperAllProductsPage:
    """Test scraping the All-ProductList page."""

    @pytest.fixture
    def sample_html(self):
        """Fixture providing sample All-ProductList HTML."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>All Product List</title></head>
        <body>
            <table id="productTable">
                <thead>
                    <tr>
                        <th>Village Collection</th>
                        <th>Item Number</th>
                        <th>Item Description</th>
                        <th>Dates</th>
                        <th>Where Found</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>A Christmas Carol</td>
                        <td>02862</td>
                        <td>Scrooge & Marley Counting House</td>
                        <td>1995-1998</td>
                        <td><a href="Collections/DV%20A%20Christmas%20Carol.html#02862">A Christmas Carol</a></td>
                    </tr>
                    <tr>
                        <td>Dickens Village</td>
                        <td>56.12345</td>
                        <td>Victorian House</td>
                        <td>1990-Present</td>
                        <td><a href="Collections/DV%20Dickens%20Village.html#56.12345">Dickens Village</a></td>
                    </tr>
                    <tr>
                        <td>The Stacks</td>
                        <td>56789</td>
                        <td>Town Library</td>
                        <td>2000</td>
                        <td><a href="TheStacks.shtml#56789">The Stacks</a></td>
                    </tr>
                </tbody>
            </table>
        </body>
        </html>
        """

    @patch('plugin_nesventory_llm.scraper.httpx.Client')
    def test_scrape_all_products_page(self, mock_client_class, sample_html, tmp_path):
        """Test scraping items from the All-ProductList page."""
        # Setup mock HTTP client
        mock_response = Mock()
        mock_response.text = sample_html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Create scraper and scrape
        scraper = VillageChroniclerScraper(data_dir=tmp_path)
        items = scraper.scrape_all_products_page()
        
        # Verify results
        assert len(items) == 3
        
        # Check first item
        item1 = items[0]
        assert item1.name == "Scrooge & Marley Counting House"
        assert item1.collection == "A Christmas Carol"
        assert item1.item_number == "02862"
        assert item1.year_introduced == 1995
        assert item1.year_retired == 1998
        assert item1.is_retired is True
        assert "Collections/DV%20A%20Christmas%20Carol.html" in item1.source_url
        
        # Check second item (active, not retired)
        item2 = items[1]
        assert item2.name == "Victorian House"
        assert item2.collection == "Dickens Village"
        assert item2.year_introduced == 1990
        assert item2.year_retired is None
        assert item2.is_retired is False
        
        # Check third item (single year)
        item3 = items[2]
        assert item3.name == "Town Library"
        assert item3.year_introduced == 2000
        assert item3.year_retired is None

    @patch('plugin_nesventory_llm.scraper.httpx.Client')
    def test_scrape_all_creates_collections(self, mock_client_class, sample_html, tmp_path):
        """Test that scrape_all creates collections from items."""
        # Setup mock
        mock_response = Mock()
        mock_response.text = sample_html
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Create scraper and scrape
        scraper = VillageChroniclerScraper(data_dir=tmp_path)
        collections, items = scraper.scrape_all()
        
        # Verify we got items
        assert len(items) == 3
        
        # Verify collections were created
        assert len(collections) == 3
        collection_names = {c.name for c in collections}
        assert "A Christmas Carol" in collection_names
        assert "Dickens Village" in collection_names
        assert "The Stacks" in collection_names
        
        # Verify item counts
        for collection in collections:
            assert collection.item_count == 1
            assert collection.manufacturer == "Department 56"

    @patch('plugin_nesventory_llm.scraper.httpx.Client')
    def test_scrape_handles_http_error(self, mock_client_class, tmp_path):
        """Test that scraper handles HTTP errors gracefully."""
        import httpx
        
        # Setup mock to raise httpx.HTTPError
        mock_client = Mock()
        mock_client.get.side_effect = httpx.HTTPError("Network error")
        mock_client_class.return_value = mock_client
        
        # Create scraper and scrape
        scraper = VillageChroniclerScraper(data_dir=tmp_path)
        items = scraper.scrape_all_products_page()
        
        # Should return empty list on error
        assert len(items) == 0
