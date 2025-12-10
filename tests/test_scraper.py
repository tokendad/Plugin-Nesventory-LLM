"""
Tests for the Village Chronicler scraper.
"""

import pytest

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
        """Fixture providing sample All-ProductList HTML with row1 class."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>All Product List</title></head>
        <body>
            <table style="width: 100%">
                <tr class="row1">
                    <td>A Christmas Carol</td>
                    <td>02862</td>
                    <td>Scrooge & Marley Counting House</td>
                    <td>1995-1998</td>
                    <td><a href="Collections/DV%20A%20Christmas%20Carol.html#02862">A Christmas Carol</a></td>
                </tr>
                <tr class="row1">
                    <td>Dickens Village</td>
                    <td>56.12345</td>
                    <td>Victorian House</td>
                    <td>1990-Present</td>
                    <td><a href="Collections/DV%20Dickens%20Village.html#56.12345">Dickens Village</a></td>
                </tr>
                <tr class="row1">
                    <td>The Stacks</td>
                    <td>56789</td>
                    <td>Town Library</td>
                    <td>2000</td>
                    <td><a href="TheStacks.shtml#56789">The Stacks</a></td>
                </tr>
            </table>
        </body>
        </html>
        """

    def test_scrape_all_products_page(self, sample_html, tmp_path):
        """Test scraping items from the All-ProductList page using local file."""
        # Create a temporary local mirror directory with the HTML file
        local_mirror = tmp_path / "thevillagechronicler.com"
        local_mirror.mkdir()
        html_file = local_mirror / "All-ProductList.shtml.html"
        html_file.write_text(sample_html, encoding="utf-8")

        # Create scraper and scrape
        scraper = VillageChroniclerScraper(data_dir=tmp_path, local_mirror_dir=local_mirror)
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

    def test_scrape_all_creates_collections(self, sample_html, tmp_path):
        """Test that scrape_all creates collections from items."""
        # Create a temporary local mirror directory with the HTML file
        local_mirror = tmp_path / "thevillagechronicler.com"
        local_mirror.mkdir()
        html_file = local_mirror / "All-ProductList.shtml.html"
        html_file.write_text(sample_html, encoding="utf-8")

        # Create scraper and scrape
        scraper = VillageChroniclerScraper(data_dir=tmp_path, local_mirror_dir=local_mirror)
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

    def test_scrape_handles_file_not_found(self, tmp_path):
        """Test that scraper handles missing file gracefully."""
        # Create scraper with non-existent local mirror
        local_mirror = tmp_path / "nonexistent"
        scraper = VillageChroniclerScraper(data_dir=tmp_path, local_mirror_dir=local_mirror)
        items = scraper.scrape_all_products_page()

        # Should return empty list on error
        assert len(items) == 0


class TestPDFParsing:
    """Test PDF parsing functions (for future use when PDFs are added to local mirror)."""

    def test_extract_collection_name_from_filename(self):
        """Test extracting collection name from PDF filename."""

        # Test with basic filename
        pdf_content = b"%PDF-1.4\n"
        name = extract_collection_name_from_pdf(pdf_content, "Alpine_Village_2021.pdf")
        assert "Alpine Village" in name

        # Test with another filename
        name = extract_collection_name_from_pdf(pdf_content, "Dickens_Village_2022.pdf")
        assert "Dickens Village" in name

    def test_parse_pdf_items_with_valid_data(self):
        """Test parsing items from PDF with mock data."""

        # Create minimal valid PDF bytes
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"

        # This will test the error handling since the PDF is minimal
        items = parse_pdf_items(pdf_bytes, "Alpine Village", "test.pdf")

        # Should return empty list for invalid/minimal PDF but not crash
        assert isinstance(items, list)


class TestRetiredPDFsScraping:
    """Test scraping retired products PDFs from local directory."""

    @pytest.fixture
    def sample_html(self):
        """Fixture providing sample All-ProductList HTML with row1 class."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>All Product List</title></head>
        <body>
            <table style="width: 100%">
                <tr class="row1">
                    <td>A Christmas Carol</td>
                    <td>02862</td>
                    <td>Scrooge & Marley Counting House</td>
                    <td>1995-1998</td>
                    <td><a href="Collections/DV%20A%20Christmas%20Carol.html#02862">A Christmas Carol</a></td>
                </tr>
                <tr class="row1">
                    <td>Dickens Village</td>
                    <td>56.12345</td>
                    <td>Victorian House</td>
                    <td>1990-Present</td>
                    <td><a href="Collections/DV%20Dickens%20Village.html#56.12345">Dickens Village</a></td>
                </tr>
                <tr class="row1">
                    <td>The Stacks</td>
                    <td>56789</td>
                    <td>Town Library</td>
                    <td>2000</td>
                    <td><a href="TheStacks.shtml#56789">The Stacks</a></td>
                </tr>
            </table>
        </body>
        </html>
        """

    def test_scrape_retired_pdfs_directory_not_exist(self, tmp_path):
        """Test that scraper handles missing retired PDFs directory gracefully."""
        # Create scraper with non-existent retired PDFs directory
        nonexistent_dir = tmp_path / "nonexistent_pdfs"
        dummy_mirror_dir = tmp_path / "dummy_mirror"
        dummy_mirror_dir.mkdir()
        
        scraper = VillageChroniclerScraper(
            data_dir=tmp_path, 
            local_mirror_dir=dummy_mirror_dir,
            retired_pdfs_dir=nonexistent_dir
        )
        items = scraper.scrape_retired_pdfs()

        # Should return empty list when directory doesn't exist
        assert len(items) == 0

    def test_scrape_retired_pdfs_empty_directory(self, tmp_path):
        """Test that scraper handles empty retired PDFs directory."""
        # Create empty retired PDFs directory
        retired_dir = tmp_path / "retired_pdfs"
        retired_dir.mkdir()
        dummy_mirror_dir = tmp_path / "dummy_mirror"
        dummy_mirror_dir.mkdir()
        
        scraper = VillageChroniclerScraper(
            data_dir=tmp_path,
            local_mirror_dir=dummy_mirror_dir,
            retired_pdfs_dir=retired_dir
        )
        items = scraper.scrape_retired_pdfs()

        # Should return empty list when no PDFs found
        assert len(items) == 0

    def test_scrape_all_includes_retired_pdfs(self, sample_html, tmp_path):
        """Test that scrape_all includes items from both HTML and PDFs."""
        # Create local mirror with HTML file
        local_mirror = tmp_path / "thevillagechronicler.com"
        local_mirror.mkdir()
        html_file = local_mirror / "All-ProductList.shtml.html"
        html_file.write_text(sample_html, encoding="utf-8")

        # Create empty retired PDFs directory (scraper should handle gracefully)
        retired_dir = tmp_path / "retired_pdfs"
        retired_dir.mkdir()

        # Create scraper and scrape
        scraper = VillageChroniclerScraper(
            data_dir=tmp_path,
            local_mirror_dir=local_mirror,
            retired_pdfs_dir=retired_dir
        )
        collections, items = scraper.scrape_all()

        # Should have items from HTML (even if no PDFs)
        assert len(items) >= 3  # From the sample HTML
        assert len(collections) >= 3


class TestScrapeModes:
    """Test different scrape modes."""

    def test_scraper_initializes_with_local_mode(self, tmp_path):
        """Test that scraper initializes with LOCAL mode by default."""
        from plugin_nesventory_llm.models import ScrapeMode
        
        scraper = VillageChroniclerScraper(data_dir=tmp_path)
        assert scraper.mode == ScrapeMode.LOCAL
        assert scraper.client is None

    def test_scraper_initializes_with_remote_mode(self, tmp_path):
        """Test that scraper initializes with REMOTE mode."""
        from plugin_nesventory_llm.models import ScrapeMode
        
        scraper = VillageChroniclerScraper(data_dir=tmp_path, mode=ScrapeMode.REMOTE)
        assert scraper.mode == ScrapeMode.REMOTE

    def test_scraper_initializes_with_internet_mode(self, tmp_path):
        """Test that scraper initializes with INTERNET mode."""
        from plugin_nesventory_llm.models import ScrapeMode
        
        scraper = VillageChroniclerScraper(data_dir=tmp_path, mode=ScrapeMode.INTERNET)
        assert scraper.mode == ScrapeMode.INTERNET

    def test_scraper_creates_http_client_for_remote_mode(self, tmp_path):
        """Test that HTTP client is created when entering context in remote mode."""
        from plugin_nesventory_llm.models import ScrapeMode
        
        scraper = VillageChroniclerScraper(data_dir=tmp_path, mode=ScrapeMode.REMOTE)
        assert scraper.client is None
        
        with scraper:
            assert scraper.client is not None
        
        # Client should be closed after exiting context
        assert scraper.client is None

    def test_scraper_creates_http_client_for_internet_mode(self, tmp_path):
        """Test that HTTP client is created when entering context in internet mode."""
        from plugin_nesventory_llm.models import ScrapeMode
        
        scraper = VillageChroniclerScraper(data_dir=tmp_path, mode=ScrapeMode.INTERNET)
        assert scraper.client is None
        
        with scraper:
            assert scraper.client is not None
        
        # Client should be closed after exiting context
        assert scraper.client is None

    def test_scraper_no_http_client_for_local_mode(self, tmp_path):
        """Test that HTTP client is NOT created for local mode."""
        from plugin_nesventory_llm.models import ScrapeMode
        
        scraper = VillageChroniclerScraper(data_dir=tmp_path, mode=ScrapeMode.LOCAL)
        
        with scraper:
            assert scraper.client is None

    def test_scrape_all_with_internet_mode_uses_default_search_terms(self, tmp_path):
        """Test that scrape_all uses default search terms in internet mode."""
        from plugin_nesventory_llm.models import ScrapeMode
        
        with VillageChroniclerScraper(data_dir=tmp_path, mode=ScrapeMode.INTERNET) as scraper:
            # Should not raise error even without search terms
            collections, items = scraper.scrape_all()
            # Internet search is not fully implemented, so should return empty
            assert isinstance(collections, list)
            assert isinstance(items, list)
