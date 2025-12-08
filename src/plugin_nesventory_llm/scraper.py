"""
Data scraper for The Village Chronicler website and Department 56 retired products.

This module scrapes collectible item information from:
- https://thevillagechronicler.com/All-ProductList.shtml
- https://retiredproducts.department56.com/pages/history-lists

The scraper parses the All-ProductList page which contains a table with:
- Village collection name
- Item number
- Item description  
- Dates (manufacturing date range)
- Where found (links to individual collection pages)

The Department 56 retired products scraper downloads PDFs with:
- Item Number
- Description
- Year Issued
- Year Retired
- US SRP (suggested retail price)
- CAD SRP (Canadian suggested retail price)
"""

import hashlib
import io
import json
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

from .models import VillageCollection, VillageItem

logger = logging.getLogger(__name__)

# Base URL for the Village Chronicler
BASE_URL = "https://thevillagechronicler.com"
COLLECTIONS_URL = f"{BASE_URL}/TheCollections.shtml"
ALL_PRODUCTS_URL = f"{BASE_URL}/All-ProductList.shtml"

# Department 56 retired products
DEPT56_RETIRED_BASE_URL = "https://retiredproducts.department56.com"
DEPT56_HISTORY_LISTS_URL = f"{DEPT56_RETIRED_BASE_URL}/pages/history-lists"

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
        logger.info(f"Parsing PDF with {len(pdf_reader.pages)} pages for collection: {collection_name}")
        
        for page_num, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            if not text:
                continue
                
            # Split into lines
            lines = text.split('\n')
            
            # Look for lines that appear to be item data
            # Format: Item Number | Description | Year Issued | Year Retired | US SRP | CAD SRP
            for line in lines:
                line = line.strip()
                if not line or len(line) < 10:
                    continue
                
                # Skip header/footer lines
                if any(header in line.lower() for header in ['item number', 'description', 'year issued', 'year retired', 'srp', 'page', 'department 56']):
                    continue
                    
                # Skip collection name lines (often in header)
                if collection_name.lower() in line.lower() and len(line) < 100:
                    continue
                
                # Try multiple regex patterns to match different PDF formats
                # Pattern 1: Full format with all fields
                item_match = re.match(r'^(\S+)\s+(.+?)\s+(\d{4})\s+(\d{4}|\-)\s+\$?([\d,]+(?:\.\d+)?)\s+\$?([\d,]+(?:\.\d+)?).*$', line)
                
                # Pattern 2: Without prices at end
                if not item_match:
                    item_match = re.match(r'^(\S+)\s+(.+?)\s+(\d{4})\s+(\d{4}|\-).*$', line)
                    
                # Pattern 3: Simpler format - just item number, description and years
                if not item_match:
                    item_match = re.match(r'^(\d+)\s+(.+?)\s+(\d{4})(?:\s+(\d{4}|\-))?.*$', line)
                
                if item_match:
                    groups = item_match.groups()
                    item_number = groups[0]
                    description = clean_text(groups[1])
                    year_issued = groups[2] if len(groups) > 2 else None
                    year_retired = groups[3] if len(groups) > 3 else None
                    us_srp = groups[4] if len(groups) > 4 else None
                    cad_srp = groups[5] if len(groups) > 5 else None
                    
                    # Skip if description is too short (likely not a real item)
                    if not description or len(description) < 3:
                        continue
                    
                    # Parse years
                    try:
                        year_introduced = int(year_issued) if year_issued else None
                    except (ValueError, TypeError):
                        year_introduced = None
                    
                    try:
                        year_retired_int = int(year_retired) if year_retired and year_retired != '-' else None
                    except (ValueError, TypeError):
                        year_retired_int = None
                    
                    # Parse US price
                    original_price = None
                    if us_srp:
                        try:
                            original_price = float(us_srp.replace(',', '').replace('$', '')) if us_srp else None
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
    name_from_file = filename.replace('.pdf', '').replace('_', ' ')
    # Remove year pattern from the end
    name_from_file = re.sub(r'\s+\d{4}$', '', name_from_file)
    
    # Try to extract from PDF content (first page header)
    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_content))
        if len(pdf_reader.pages) > 0:
            first_page = pdf_reader.pages[0].extract_text()
            lines = first_page.split('\n')[:5]  # Check first few lines
            for line in lines:
                line = line.strip()
                # Look for collection-like names (capitalized, reasonable length)
                if len(line) > 5 and len(line) < 50 and any(c.isupper() for c in line):
                    # Avoid header labels
                    if not any(keyword in line.lower() for keyword in ['item number', 'description', 'year', 'srp', 'page']):
                        return clean_text(line)
    except Exception as e:
        logger.debug(f"Could not extract collection name from PDF content: {e}")
    
    return clean_text(name_from_file)


class VillageChroniclerScraper:
    """Scraper for The Village Chronicler website."""

    def __init__(self, data_dir: Path | str = "data"):
        """Initialize the scraper.

        Args:
            data_dir: Directory to store scraped data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "NesVentory-LLM-Plugin/0.1.0 (Inventory Research Bot)"
            },
        )
        self.collections: list[VillageCollection] = []
        self.items: list[VillageItem] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    def scrape_collections_page(self) -> list[dict]:
        """Scrape the main collections page to get collection links.

        Returns:
            List of collection info dictionaries with name and URL
        """
        logger.info(f"Fetching collections page: {COLLECTIONS_URL}")

        try:
            response = self.client.get(COLLECTIONS_URL)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch collections page: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        collections = []

        # Find collection links - look for common patterns on village collector sites
        # This is a flexible approach that works with various HTML structures
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = clean_text(link.get_text())

            # Skip empty or navigation links
            if not text or len(text) < 3:
                continue

            # Look for collection-related links
            if any(
                keyword in href.lower()
                for keyword in ["collection", "village", "dept", "dickens", "snow"]
            ):
                full_url = urljoin(BASE_URL, href)
                collections.append({"name": text, "url": full_url})

        logger.info(f"Found {len(collections)} potential collection links")
        return collections

    def scrape_all_products_page(self) -> list[VillageItem]:
        """Scrape the All-ProductList page to get all items.
        
        This page contains a table with all products including:
        - Village collection
        - Item Number
        - Item Description
        - Dates (year range)
        - Where found (link to collection detail page)
        
        Returns:
            List of VillageItem objects
        """
        logger.info(f"Fetching all products page: {ALL_PRODUCTS_URL}")
        
        try:
            response = self.client.get(ALL_PRODUCTS_URL)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch all products page: {e}")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        
        # Find the main product table
        table = soup.find("table", id="productTable")
        if not table:
            # Fallback: find the first table with enough columns
            tables = soup.find_all("table")
            for t in tables:
                sample_row = t.find("tr")
                if sample_row and len(sample_row.find_all(["td", "th"])) >= MIN_PRODUCT_TABLE_COLUMNS:
                    table = t
                    break
        
        if not table:
            logger.warning("Could not find product table in All-ProductList page")
            return []
        
        # Get all data rows (skip header if present)
        rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")
        
        # Filter out header rows
        data_rows = []
        for row in rows:
            cells = row.find_all(["td", "th"])
            if cells:
                # Skip if this looks like a header row
                first_cell_text = cells[0].get_text().strip().lower()
                if first_cell_text not in HEADER_CELL_INDICATORS:
                    data_rows.append(row)
        
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
            
            # Extract detail page URL from "Where Found" column
            where_found_cell = cells[4]
            detail_link = where_found_cell.find("a")
            detail_url = urljoin(BASE_URL, detail_link.get("href")) if detail_link else None
            
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
                source_url=detail_url if detail_url else ALL_PRODUCTS_URL,
            )
            
            items.append(item)
        
        logger.info(f"Scraped {len(items)} items from All-ProductList page")
        return items

    def scrape_collection_items(self, collection_url: str, collection_name: str) -> list[VillageItem]:
        """Scrape items from a specific collection page.

        Args:
            collection_url: URL of the collection page
            collection_name: Name of the collection

        Returns:
            List of VillageItem objects
        """
        logger.info(f"Fetching collection: {collection_name} from {collection_url}")

        try:
            response = self.client.get(collection_url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch collection {collection_name}: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        items = []

        # Look for item entries - typically in tables or divs with consistent structure
        # Try table rows first (common for collectible listings)
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    item = self._parse_table_row(cells, collection_name, collection_url)
                    if item:
                        items.append(item)

        # Also look for div/list structures
        for container in soup.find_all(["div", "li"], class_=re.compile(r"item|product|entry")):
            item = self._parse_item_container(container, collection_name, collection_url)
            if item:
                items.append(item)

        logger.info(f"Found {len(items)} items in {collection_name}")
        return items

    def _parse_table_row(
        self, cells: list, collection_name: str, source_url: str
    ) -> Optional[VillageItem]:
        """Parse a table row into a VillageItem."""
        texts = [clean_text(cell.get_text()) for cell in cells]

        # Need at least a name
        name = texts[0] if texts else None
        if not name or len(name) < 3:
            return None

        # Skip header rows
        if name.lower() in ["name", "item", "description", "price"]:
            return None

        # Try to extract item number (often in format like "56.12345")
        item_number = None
        for text in texts:
            match = re.search(r"\d{2}\.\d{4,6}", text)
            if match:
                item_number = match.group()
                break

        # Try to find year and price
        year_introduced = None
        original_price = None
        description = None

        for text in texts[1:]:
            if year_introduced is None:
                year_introduced = parse_year(text)
            if original_price is None:
                original_price = parse_price(text)
            if len(text) > 20 and description is None:
                description = text

        # Check for images
        image_url = None
        for cell in cells:
            img = cell.find("img")
            if img and img.get("src"):
                image_url = urljoin(source_url, img["src"])
                break

        return VillageItem(
            id=generate_item_id(name, item_number),
            name=name,
            item_number=item_number,
            collection=collection_name,
            description=description,
            year_introduced=year_introduced,
            original_price=original_price,
            image_url=image_url,
            source_url=source_url,
        )

    def _parse_item_container(
        self, container, collection_name: str, source_url: str
    ) -> Optional[VillageItem]:
        """Parse a div/container element into a VillageItem."""
        # Look for name in headers or strong tags
        name_element = container.find(["h1", "h2", "h3", "h4", "strong", "b"])
        name = clean_text(name_element.get_text()) if name_element else None

        if not name or len(name) < 3:
            return None

        # Get full text for parsing
        full_text = clean_text(container.get_text())

        # Extract item number
        item_number = None
        match = re.search(r"\d{2}\.\d{4,6}", full_text)
        if match:
            item_number = match.group()

        # Look for image
        image_url = None
        img = container.find("img")
        if img and img.get("src"):
            image_url = urljoin(source_url, img["src"])

        return VillageItem(
            id=generate_item_id(name, item_number),
            name=name,
            item_number=item_number,
            collection=collection_name,
            description=full_text[:500] if len(full_text) > 20 else None,
            year_introduced=parse_year(full_text),
            original_price=parse_price(full_text),
            image_url=image_url,
            source_url=source_url,
        )

    def scrape_dept56_retired_products(self) -> list[VillageItem]:
        """Scrape items from Department 56 retired products website.
        
        Fetches the history lists page and extracts PDF links, then downloads
        and parses each PDF to extract item information.
        
        Returns:
            List of VillageItem objects from all PDFs
        """
        logger.info(f"Fetching Department 56 history lists page: {DEPT56_HISTORY_LISTS_URL}")
        
        try:
            response = self.client.get(DEPT56_HISTORY_LISTS_URL)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch Department 56 history lists page: {e}")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        
        # Find all PDF links on the page
        pdf_links = []
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.endswith(".pdf"):
                full_url = urljoin(DEPT56_RETIRED_BASE_URL, href)
                pdf_links.append(full_url)
        
        logger.info(f"Found {len(pdf_links)} PDF links on history lists page")
        
        # Download and parse each PDF
        for pdf_url in pdf_links:
            try:
                logger.info(f"Downloading PDF: {pdf_url}")
                pdf_response = self.client.get(pdf_url)
                pdf_response.raise_for_status()
                
                # Extract filename from URL
                filename = pdf_url.split('/')[-1].split('?')[0]
                
                # Extract collection name from PDF
                collection_name = extract_collection_name_from_pdf(pdf_response.content, filename)
                
                # Parse PDF and extract items
                pdf_items = parse_pdf_items(pdf_response.content, collection_name, pdf_url)
                items.extend(pdf_items)
                
            except httpx.HTTPError as e:
                logger.error(f"Failed to download PDF {pdf_url}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing PDF {pdf_url}: {e}")
                continue
        
        logger.info(f"Scraped {len(items)} total items from Department 56 retired products")
        return items

    def scrape_all(self) -> tuple[list[VillageCollection], list[VillageItem]]:
        """Scrape all collections and items from the website.
        
        Uses the All-ProductList page to get all items efficiently,
        plus the Department 56 retired products PDFs,
        then optionally enriches with detail pages.

        Returns:
            Tuple of (collections, items)
        """
        logger.info("Starting full scrape of Village Chronicler and Department 56")

        # First, scrape all items from the All-ProductList page
        self.items = self.scrape_all_products_page()
        
        # Also scrape Department 56 retired products PDFs
        dept56_items = self.scrape_dept56_retired_products()
        self.items.extend(dept56_items)
        
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

        logger.info(f"Scrape complete: {len(self.collections)} collections, {len(self.items)} items")
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
