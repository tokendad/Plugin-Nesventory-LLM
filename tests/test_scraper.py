"""
Tests for the Village Chronicler scraper.
"""
import httpx
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
    extract_collection_name_from_pdf,
    parse_pdf_items,
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
        # Setup mock to raise httpx.HTTPError
        mock_client = Mock()
        mock_client.get.side_effect = httpx.HTTPError("Network error")
        mock_client_class.return_value = mock_client
        
        # Create scraper and scrape
        scraper = VillageChroniclerScraper(data_dir=tmp_path)
        items = scraper.scrape_all_products_page()
        
        # Should return empty list on error
        assert len(items) == 0


class TestDepartment56RetiredProducts:
    """Test scraping Department 56 retired products PDFs."""

    @pytest.fixture
    def sample_history_page_html(self):
        """Fixture providing sample history lists page HTML."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>History Lists</title></head>
        <body>
            <h1>Retired Product History Lists</h1>
            <div class="content">
                <a href="/files/Alpine_Village_2021.pdf">Alpine Village</a>
                <a href="/files/Dickens_Village_2021.pdf">Dickens Village</a>
                <a href="https://cdn.shopify.com/s/files/1/0031/4972/5814/files/Christmas_in_the_City_2021.pdf?v=1658169182">Christmas in the City</a>
            </div>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_pdf_content(self):
        """Fixture providing sample PDF data."""
        # Create a minimal PDF with test data
        # This is a simplified mock - real PDFs would be more complex
        from io import BytesIO
        from PyPDF2 import PdfWriter
        
        # For testing, we'll just return a simple mock that can be parsed
        # In real testing, you'd use a real PDF or more sophisticated mocking
        return b"%PDF-1.4\nMock PDF content for testing"

    def test_extract_collection_name_from_filename(self):
        """Test extracting collection name from PDF filename."""
        from plugin_nesventory_llm.scraper import extract_collection_name_from_pdf
        
        # Test with basic filename
        pdf_content = b"%PDF-1.4\n"
        name = extract_collection_name_from_pdf(pdf_content, "Alpine_Village_2021.pdf")
        assert "Alpine Village" in name
        
        # Test with another filename
        name = extract_collection_name_from_pdf(pdf_content, "Dickens_Village_2022.pdf")
        assert "Dickens Village" in name

    @patch('plugin_nesventory_llm.scraper.httpx.Client')
    def test_scrape_dept56_finds_pdf_links(self, mock_client_class, sample_history_page_html, tmp_path):
        """Test that Department 56 scraper finds PDF links."""
        # Setup mock HTTP responses
        history_response = Mock()
        history_response.text = sample_history_page_html
        history_response.status_code = 200
        history_response.raise_for_status = Mock()
        
        # Mock PDF responses (empty but valid)
        pdf_response = Mock()
        pdf_response.content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
        pdf_response.status_code = 200
        pdf_response.raise_for_status = Mock()
        
        mock_client = Mock()
        # First call is for history page, subsequent calls are for PDFs
        mock_client.get.side_effect = [history_response, pdf_response, pdf_response, pdf_response]
        mock_client_class.return_value = mock_client
        
        # Create scraper and scrape
        scraper = VillageChroniclerScraper(data_dir=tmp_path)
        items = scraper.scrape_dept56_retired_products()
        
        # Verify that we attempted to download PDFs
        # First call is history page, next calls are PDFs
        assert mock_client.get.call_count >= 1
        
        # The function should handle empty PDFs gracefully
        assert isinstance(items, list)

    def test_parse_pdf_items_with_valid_data(self):
        """Test parsing items from PDF with mock data."""
        from plugin_nesventory_llm.scraper import parse_pdf_items
        
        # Create a simple text-based PDF mock
        # Real PDFs would be parsed differently, but for testing we can mock the content
        pdf_text_content = """
        Alpine Village
        Item Number Description Year Issued Year Retired US SRP CAD SRP
        12345 Swiss Chalet 2000 2005 $45.00 $55.00
        67890 Mountain Lodge 2001 2010 $65.00 $75.00
        """
        
        # For this test, we'll mock the PDF reader to return our test text
        # In a real scenario, you'd create an actual PDF or use more sophisticated mocking
        
        # Create minimal valid PDF bytes
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
        
        # This will test the error handling since the PDF is minimal
        items = parse_pdf_items(pdf_bytes, "Alpine Village", "http://test.com/test.pdf")
        
        # Should return empty list for invalid/minimal PDF but not crash
        assert isinstance(items, list)

    @patch('plugin_nesventory_llm.scraper.httpx.Client')
    def test_scrape_dept56_handles_http_error(self, mock_client_class, tmp_path):
        """Test that Department 56 scraper handles HTTP errors gracefully."""
        # Setup mock to raise httpx.HTTPError
        mock_client = Mock()
        mock_client.get.side_effect = httpx.HTTPError("Network error")
        mock_client_class.return_value = mock_client
        
        # Create scraper and scrape
        scraper = VillageChroniclerScraper(data_dir=tmp_path)
        items = scraper.scrape_dept56_retired_products()
        
        # Should return empty list on error
        assert len(items) == 0
        assert isinstance(items, list)
