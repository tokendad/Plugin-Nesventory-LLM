"""
Data scraper for The Village Chronicler website and Department 56 retired products.

This module scrapes collectible item information from local mirror files in:
- Village/thevillagechronicler.com/All-ProductList.shtml.html
- Village/retiredproducts.department56.com/*.pdf

The scraper parses:
1. The All-ProductList page which contains a table with:
   - Village collection name
   - Item number
   - Item description
   - Dates (manufacturing date range)
   - Where found (links to individual collection pages)

2. Retired products PDF files which contain:
   - Item numbers
   - Detailed descriptions
   - Year issued
   - Year retired  
   - US and Canadian suggested retail prices

Note: Both sources are stored locally in the repository.
"""

import hashlib
import io
import json
import logging
import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .models import VillageCollection, VillageItem

logger = logging.getLogger(__name__)

# Default local mirror directory (relative to repository root)
DEFAULT_LOCAL_MIRROR = Path("Village/thevillagechronicler.com")
DEFAULT_RETIRED_PDFS_DIR = Path("Village/retiredproducts.department56.com")

# Table parsing constants
MIN_PRODUCT_TABLE_COLUMNS = 5
HEADER_CELL_INDICATORS = ["village collection", "collection", "name"]


def generate_item_id(name: str, item_number: Optional[str] = None) -> str:
    """Generate a unique ID for an item based on its name and item number."""
    source = f"{name}-{item_number}" if item_number else name
    return f"dept56-{hashlib.md5(source.encode()).hexdigest()[:8]}"


def parse_year(text: str) -> Optional[int]:
    """Extract a year from text."""
    match = re.search(r"\b(19[89]\d|20[0-2]\d)\b", text)
    return int(match.group(1)) if match else None


def parse_date_range(text: str) -> tuple[Optional[int], Optional[int]]:
    """Extract year range from text like '1995-1998' or '2000-Present'.

    Returns:
        Tuple of (year_introduced, year_retired)
    """
    if not text:
        return None, None

    # Match patterns like "1995-1998", "1995-Present", "1995"
    match = re.search(r"(\d{4})\s*-\s*(\d{4}|Present)", text, re.IGNORECASE)
    if match:
        year_start = int(match.group(1))
        year_end_str = match.group(2)
        year_end = None if year_end_str.lower() == "present" else int(year_end_str)
        return year_start, year_end

    # Single year only
    match = re.search(r"\b(19[89]\d|20[0-2]\d)\b", text)
    if match:
        year = int(match.group(1))
        return year, None

    return None, None


def parse_price(text: str) -> Optional[float]:
    """Extract a price from text."""
    match = re.search(r"\$?([\d,]+(?:\.\d{2})?)", text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    return text.strip()


def parse_pdf_items(pdf_content: bytes, collection_name: str, source_url: str) -> list[VillageItem]:
    """Parse Department 56 PDF file to extract item information.

    PDFs contain columns:
    - Item Number
    - Description
    - Year Issued
    - Year Retired
    - US SRP (suggested retail price)
    - CAD SRP (Canadian suggested retail price)

    Args:
        pdf_content: PDF file content as bytes
        collection_name: Collection name extracted from PDF header or filename
        source_url: URL of the PDF for attribution

    Returns:
        List of VillageItem objects
    """
    items = []

    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_content))
        logger.info(
            f"Parsing PDF with {len(pdf_reader.pages)} pages for collection: {collection_name}"
        )

        for page_num, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            if not text:
                continue

            # Split into lines
            lines = text.split("\n")

            # Look for lines that appear to be item data
            # Format: Item Number | Description | Year Issued | Year Retired | US SRP | CAD SRP
            for line in lines:
                line = line.strip()
                if not line or len(line) < 10:
                    continue

                # Skip header/footer lines
                if any(
                    header in line.lower()
                    for header in [
                        "item number",
                        "description",
                        "year issued",
                        "year retired",
                        "srp",
                        "page",
                        "department 56",
                    ]
                ):
                    continue

                # Skip collection name lines (often in header)
                if collection_name.lower() in line.lower() and len(line) < 100:
                    continue

                # Try multiple regex patterns to match different PDF formats
                # Pattern 1: Full format with all fields
                item_match = re.match(
                    r"^(\S+)\s+(.+?)\s+(\d{4})\s+(\d{4}|\-)\s+\$?([\d,]+(?:\.\d+)?)\s+\$?([\d,]+(?:\.\d+)?).*$",
                    line,
                )

                # Pattern 2: Without prices at end
                if not item_match:
                    item_match = re.match(r"^(\S+)\s+(.+?)\s+(\d{4})\s+(\d{4}|\-).*$", line)

                # Pattern 3: Simpler format - just item number, description and years
                if not item_match:
                    item_match = re.match(r"^(\d+)\s+(.+?)\s+(\d{4})(?:\s+(\d{4}|\-))?.*$", line)

                if item_match:
                    groups = item_match.groups()
                    item_number = groups[0]
                    description = clean_text(groups[1])
                    year_issued = groups[2] if len(groups) > 2 else None
                    year_retired = groups[3] if len(groups) > 3 else None
                    us_srp = groups[4] if len(groups) > 4 else None
                    # Note: groups[5] would be cad_srp but we don't use it currently

                    # Skip if description is too short (likely not a real item)
                    if not description or len(description) < 3:
                        continue

                    # Parse years
                    try:
                        year_introduced = int(year_issued) if year_issued else None
                    except (ValueError, TypeError):
                        year_introduced = None

                    try:
                        year_retired_int = (
                            int(year_retired) if year_retired and year_retired != "-" else None
                        )
                    except (ValueError, TypeError):
                        year_retired_int = None

                    # Parse US price
                    original_price = None
                    if us_srp:
                        try:
                            original_price = (
                                float(us_srp.replace(",", "").replace("$", "")) if us_srp else None
                            )
                        except (ValueError, TypeError):
                            original_price = None

                    # Create item
                    item = VillageItem(
                        id=generate_item_id(description, item_number),
                        name=description,
                        item_number=item_number,
                        collection=collection_name,
                        year_introduced=year_introduced,
                        year_retired=year_retired_int,
                        is_retired=True,  # All items on retired products site are retired
                        original_price=original_price,
                        source_url=source_url,
                    )
                    items.append(item)

    except Exception as e:
        logger.error(f"Error parsing PDF for {collection_name}: {e}")

    logger.info(f"Extracted {len(items)} items from PDF for {collection_name}")
    return items


def extract_collection_name_from_pdf(pdf_content: bytes, filename: str) -> str:
    """Extract collection name from PDF header or filename.

    Args:
        pdf_content: PDF file content as bytes
        filename: PDF filename (e.g., "Alpine_Village_2021.pdf")

    Returns:
        Collection name
    """
    # First try to extract from filename
    # Format: "Alpine_Village_2021.pdf" -> "Alpine Village"
    name_from_file = filename.replace(".pdf", "").replace("_", " ")
    # Remove year pattern from the end
    name_from_file = re.sub(r"\s+\d{4}$", "", name_from_file)

    # Try to extract from PDF content (first page header)
    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_content))
        if len(pdf_reader.pages) > 0:
            first_page = pdf_reader.pages[0].extract_text()
            lines = first_page.split("\n")[:5]  # Check first few lines
            for line in lines:
                line = line.strip()
                # Look for collection-like names (capitalized, reasonable length)
                if len(line) > 5 and len(line) < 50 and any(c.isupper() for c in line):
                    # Avoid header labels
                    if not any(
                        keyword in line.lower()
                        for keyword in ["item number", "description", "year", "srp", "page"]
                    ):
                        return clean_text(line)
    except Exception as e:
        logger.debug(f"Could not extract collection name from PDF content: {e}")

    return clean_text(name_from_file)


class VillageChroniclerScraper:
    """Scraper for The Village Chronicler local mirror files."""

    def __init__(self, data_dir: Path | str = "data", local_mirror_dir: Path | str | None = None, retired_pdfs_dir: Path | str | None = None):
        """Initialize the scraper.

        Args:
            data_dir: Directory to store scraped data
            local_mirror_dir: Path to local mirror of thevillagechronicler.com.
                             Defaults to "Village/thevillagechronicler.com" if not provided.
            retired_pdfs_dir: Path to local retired products PDFs directory.
                             Defaults to "Village/retiredproducts.department56.com" if not provided.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Set local mirror directory
        if local_mirror_dir:
            self.local_mirror_dir = Path(local_mirror_dir)
        else:
            self.local_mirror_dir = DEFAULT_LOCAL_MIRROR

        # Set retired PDFs directory
        if retired_pdfs_dir:
            self.retired_pdfs_dir = Path(retired_pdfs_dir)
        else:
            self.retired_pdfs_dir = DEFAULT_RETIRED_PDFS_DIR

        # Validate that the local mirror directory exists
        if not self.local_mirror_dir.exists():
            logger.warning(f"Local mirror directory does not exist: {self.local_mirror_dir}")

        # Validate that the retired PDFs directory exists
        if not self.retired_pdfs_dir.exists():
            logger.warning(f"Retired PDFs directory does not exist: {self.retired_pdfs_dir}")

        self.collections: list[VillageCollection] = []
        self.items: list[VillageItem] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def scrape_all_products_page(self) -> list[VillageItem]:
        """Scrape the All-ProductList page from local file to get all items.

        This page contains a table with all products including:
        - Village collection
        - Item Number
        - Item Description
        - Dates (year range)
        - Where found (link to collection detail page)

        Returns:
            List of VillageItem objects
        """
        local_file = self.local_mirror_dir / "All-ProductList.shtml.html"
        logger.info(f"Reading all products page from local file: {local_file}")

        try:
            with open(local_file, "r", encoding="utf-8") as f:
                html_content = f.read()
        except (FileNotFoundError, IOError) as e:
            logger.error(f"Failed to read local file {local_file}: {e}")
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        items = []

        # Find the main product table - look for table with rows that have class="row1"
        table = None
        tables = soup.find_all("table")
        for t in tables:
            # Check if this table has product rows (with class="row1")
            if t.find("tr", class_="row1"):
                table = t
                break

        if not table:
            logger.warning("Could not find product table with row1 class in All-ProductList page")
            return []

        # Get all data rows with class="row1" (product rows)
        data_rows = table.find_all("tr", class_="row1")

        logger.info(f"Found {len(data_rows)} product rows in table")

        # Parse each row
        for row in data_rows:
            cells = row.find_all(["td", "th"])

            # Expected columns: Collection, Item Number, Description, Dates, Where Found
            if len(cells) < MIN_PRODUCT_TABLE_COLUMNS:
                continue

            collection_name = clean_text(cells[0].get_text())
            item_number = clean_text(cells[1].get_text())
            description = clean_text(cells[2].get_text())
            dates = clean_text(cells[3].get_text())

            # Extract detail page URL from "Where Found" column (stored as local file reference)
            where_found_cell = cells[4]
            detail_link = where_found_cell.find("a")
            detail_url = detail_link.get("href") if detail_link else None

            # Skip rows without essential data
            if not description or not collection_name:
                continue

            # Parse date range
            year_introduced, year_retired = parse_date_range(dates)

            # Create item
            item = VillageItem(
                id=generate_item_id(description, item_number),
                name=description,
                item_number=item_number if item_number else None,
                collection=collection_name,
                year_introduced=year_introduced,
                year_retired=year_retired,
                is_retired=year_retired is not None,
                source_url=detail_url if detail_url else "All-ProductList.shtml.html",
            )

            items.append(item)

        logger.info(f"Scraped {len(items)} items from All-ProductList page")
        return items

    def scrape_retired_pdfs(self) -> list[VillageItem]:
        """Scrape retired products from local PDF files.

        Reads PDF files from the local retired products directory
        and extracts item information from each PDF.

        Returns:
            List of VillageItem objects
        """
        logger.info(f"Scraping retired products PDFs from: {self.retired_pdfs_dir}")
        
        if not self.retired_pdfs_dir.exists():
            logger.warning(f"Retired PDFs directory does not exist: {self.retired_pdfs_dir}")
            return []

        all_items = []
        
        # Find all PDF files in the directory
        pdf_files = list(self.retired_pdfs_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files")

        for pdf_file in pdf_files:
            try:
                # Read PDF content
                with open(pdf_file, "rb") as f:
                    pdf_content = f.read()

                # Extract collection name from filename
                collection_name = extract_collection_name_from_pdf(pdf_content, pdf_file.name)

                # Parse items from PDF
                items = parse_pdf_items(pdf_content, collection_name, pdf_file.name)
                all_items.extend(items)

            except Exception as e:
                logger.error(f"Error processing PDF {pdf_file.name}: {e}")
                continue

        logger.info(f"Scraped {len(all_items)} items from {len(pdf_files)} PDF files")
        return all_items

    def scrape_all(self) -> tuple[list[VillageCollection], list[VillageItem]]:
        """Scrape all collections and items from local mirror files.

        Reads data from:
        1. The All-ProductList page from Village Chronicler mirror
        2. Retired products PDFs from local directory

        Returns:
            Tuple of (collections, items)
        """
        logger.info("Starting scrape from local Village Chronicler mirror and retired PDFs")

        # Scrape all items from the All-ProductList page
        self.items = self.scrape_all_products_page()

        # Scrape retired products from PDF files
        retired_items = self.scrape_retired_pdfs()
        self.items.extend(retired_items)

        # Build collections from the items
        collections_dict = {}
        for item in self.items:
            if item.collection and item.collection not in collections_dict:
                collections_dict[item.collection] = VillageCollection(
                    id=hashlib.md5(item.collection.encode()).hexdigest()[:8],
                    name=item.collection,
                    manufacturer="Department 56",
                    item_count=0,
                )

        # Count items per collection
        for item in self.items:
            if item.collection and item.collection in collections_dict:
                collections_dict[item.collection].item_count += 1

        self.collections = list(collections_dict.values())

        logger.info(
            f"Scrape complete: {len(self.collections)} collections, {len(self.items)} items"
        )
        return self.collections, self.items

    def save_data(self) -> Path:
        """Save scraped data to JSON files.

        Returns:
            Path to the saved items file
        """
        items_file = self.data_dir / "village_items.json"
        collections_file = self.data_dir / "village_collections.json"

        with open(items_file, "w", encoding="utf-8") as f:
            json.dump([item.model_dump() for item in self.items], f, indent=2)

        with open(collections_file, "w", encoding="utf-8") as f:
            json.dump([coll.model_dump() for coll in self.collections], f, indent=2)

        logger.info(f"Saved {len(self.items)} items to {items_file}")
        logger.info(f"Saved {len(self.collections)} collections to {collections_file}")

        return items_file

    def load_data(self) -> tuple[list[VillageCollection], list[VillageItem]]:
        """Load previously scraped data from JSON files.

        Returns:
            Tuple of (collections, items)
        """
        items_file = self.data_dir / "village_items.json"
        collections_file = self.data_dir / "village_collections.json"

        if items_file.exists():
            with open(items_file, "r", encoding="utf-8") as f:
                self.items = [VillageItem(**item) for item in json.load(f)]

        if collections_file.exists():
            with open(collections_file, "r", encoding="utf-8") as f:
                self.collections = [VillageCollection(**coll) for coll in json.load(f)]

        logger.info(f"Loaded {len(self.items)} items and {len(self.collections)} collections")
        return self.collections, self.items


def scrape_and_save(data_dir: str = "data") -> Path:
    """Convenience function to scrape and save all data.

    Args:
        data_dir: Directory to store data

    Returns:
        Path to saved items file
    """
    with VillageChroniclerScraper(data_dir) as scraper:
        scraper.scrape_all()
        return scraper.save_data()
