"""
Data scraper for The Village Chronicler website.

This module scrapes collectible item information from
https://thevillagechronicler.com/TheCollections.shtml
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .models import VillageCollection, VillageItem

logger = logging.getLogger(__name__)

# Base URL for the Village Chronicler
BASE_URL = "https://thevillagechronicler.com"
COLLECTIONS_URL = f"{BASE_URL}/TheCollections.shtml"


def generate_item_id(name: str, item_number: Optional[str] = None) -> str:
    """Generate a unique ID for an item based on its name and item number."""
    source = f"{name}-{item_number}" if item_number else name
    return f"dept56-{hashlib.md5(source.encode()).hexdigest()[:8]}"


def parse_year(text: str) -> Optional[int]:
    """Extract a year from text."""
    match = re.search(r"\b(19[89]\d|20[0-2]\d)\b", text)
    return int(match.group(1)) if match else None


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

    def scrape_all(self) -> tuple[list[VillageCollection], list[VillageItem]]:
        """Scrape all collections and items from the website.

        Returns:
            Tuple of (collections, items)
        """
        logger.info("Starting full scrape of Village Chronicler")

        collection_links = self.scrape_collections_page()

        for coll_info in collection_links:
            collection = VillageCollection(
                id=hashlib.md5(coll_info["name"].encode()).hexdigest()[:8],
                name=coll_info["name"],
                manufacturer="Department 56",
            )

            items = self.scrape_collection_items(coll_info["url"], coll_info["name"])
            collection.item_count = len(items)

            self.collections.append(collection)
            self.items.extend(items)

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
