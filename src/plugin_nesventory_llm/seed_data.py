"""
Sample seed data for Department 56 Village Collectibles.

This module provides example items to get started with the knowledge base
when scraping is not available or for testing purposes.
"""

from pathlib import Path
import json

from .models import VillageCollection, VillageItem


# Sample Department 56 collections
SAMPLE_COLLECTIONS = [
    VillageCollection(
        id="dickens-village",
        name="Dickens Village",
        description="Victorian-era English village inspired by the works of Charles Dickens. Features buildings, accessories, and figures from 19th century England.",
        manufacturer="Department 56",
        year_started=1984,
        is_active=True,
    ),
    VillageCollection(
        id="snow-village",
        name="Original Snow Village",
        description="Classic American small-town winter scenes featuring homes, shops, and community buildings covered in snow.",
        manufacturer="Department 56",
        year_started=1976,
        is_active=True,
    ),
    VillageCollection(
        id="north-pole",
        name="North Pole Series",
        description="Santa's magical North Pole workshop featuring elf buildings, toy factories, and Christmas-themed structures.",
        manufacturer="Department 56",
        year_started=1990,
        is_active=True,
    ),
    VillageCollection(
        id="new-england",
        name="New England Village",
        description="Charming New England coastal village with lighthouses, sea captain homes, and maritime-themed buildings.",
        manufacturer="Department 56",
        year_started=1986,
        is_active=True,
    ),
    VillageCollection(
        id="christmas-in-the-city",
        name="Christmas in the City",
        description="Urban holiday scenes featuring department stores, brownstones, and city landmarks decorated for Christmas.",
        manufacturer="Department 56",
        year_started=1987,
        is_active=True,
    ),
    VillageCollection(
        id="alpine-village",
        name="Alpine Village",
        description="Swiss and German mountain village with chalets, churches, and traditional Alpine architecture.",
        manufacturer="Department 56",
        year_started=1986,
        is_active=False,
        year_ended=2005,
    ),
]


# Sample items for each collection
SAMPLE_ITEMS = [
    # Dickens Village
    VillageItem(
        id="dept56-dv001",
        name="Scrooge & Marley Counting House",
        item_number="65.6500-5",
        collection="Dickens Village",
        category="Buildings",
        description="The famous counting house from A Christmas Carol where Ebenezer Scrooge worked. Features detailed Victorian architecture with snow-covered roof and period-accurate signage.",
        year_introduced=1984,
        is_retired=True,
        year_retired=1990,
        original_price=25.00,
        estimated_value_min=150.00,
        estimated_value_max=250.00,
        dimensions="6\" x 4\" x 7\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-dv002",
        name="The Old Curiosity Shop",
        item_number="65.5905-6",
        collection="Dickens Village",
        category="Buildings",
        description="Quaint shop inspired by Dickens' novel of the same name. Tudor-style building with antique shop front and living quarters above.",
        year_introduced=1987,
        is_retired=True,
        year_retired=1999,
        original_price=32.00,
        estimated_value_min=75.00,
        estimated_value_max=125.00,
        dimensions="5.5\" x 4\" x 6.5\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-dv003",
        name="Crown & Cricket Inn",
        item_number="65.5750-9",
        collection="Dickens Village",
        category="Buildings",
        description="Traditional English pub and inn with Tudor architecture, featuring exposed timber beams and a warm, welcoming atmosphere.",
        year_introduced=1986,
        is_retired=False,
        original_price=35.00,
        dimensions="7\" x 5\" x 6\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-dv004",
        name="Carolers - Set of 3",
        item_number="65.6526-9",
        collection="Dickens Village",
        category="Accessories",
        description="Three Victorian carolers in period dress singing holiday songs. Includes two adults and one child holding songbooks.",
        year_introduced=1984,
        is_retired=True,
        year_retired=1992,
        original_price=10.00,
        estimated_value_min=25.00,
        estimated_value_max=40.00,
        materials="Hand-painted resin",
    ),
    # Snow Village
    VillageItem(
        id="dept56-sv001",
        name="Mountain Lodge",
        item_number="50.5001-3",
        collection="Original Snow Village",
        category="Buildings",
        description="Cozy ski lodge with A-frame design, perfect for après-ski gatherings. Features stone chimney and large windows.",
        year_introduced=1976,
        is_retired=True,
        year_retired=1979,
        original_price=20.00,
        estimated_value_min=300.00,
        estimated_value_max=500.00,
        dimensions="8\" x 5\" x 6\"",
        materials="Ceramic, hand-painted",
        notes="One of the original 6 Snow Village pieces",
    ),
    VillageItem(
        id="dept56-sv002",
        name="Nantucket Renovation",
        item_number="54.5441-0",
        collection="Original Snow Village",
        category="Buildings",
        description="Cape Cod style home undergoing renovation. Features scaffolding, workers, and home improvement details.",
        year_introduced=1993,
        is_retired=True,
        year_retired=1999,
        original_price=55.00,
        estimated_value_min=60.00,
        estimated_value_max=90.00,
        dimensions="6\" x 5\" x 5.5\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-sv003",
        name="Starbucks Coffee",
        item_number="54.5459-5",
        collection="Original Snow Village",
        category="Buildings",
        description="Licensed Starbucks coffee shop building with authentic signage and coffee shop interior details.",
        year_introduced=1995,
        is_retired=True,
        year_retired=2005,
        original_price=48.00,
        estimated_value_min=125.00,
        estimated_value_max=175.00,
        dimensions="5\" x 4\" x 5\"",
        materials="Porcelain, hand-painted",
        notes="Popular licensed building",
    ),
    # North Pole
    VillageItem(
        id="dept56-np001",
        name="Santa's Workshop",
        item_number="56.5600-6",
        collection="North Pole Series",
        category="Buildings",
        description="The heart of the North Pole village - Santa's main toy workshop where elves create gifts for children around the world.",
        year_introduced=1990,
        is_retired=False,
        original_price=72.00,
        dimensions="9\" x 6\" x 7\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-np002",
        name="Elf Bunkhouse",
        item_number="56.5601-4",
        collection="North Pole Series",
        category="Buildings",
        description="Where Santa's helpers rest after a long day of toy making. Features bunk beds visible through windows and candy-cane trim.",
        year_introduced=1990,
        is_retired=True,
        year_retired=1996,
        original_price=35.00,
        estimated_value_min=65.00,
        estimated_value_max=95.00,
        dimensions="5\" x 4\" x 5\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-np003",
        name="Reindeer Barn",
        item_number="56.5620-1",
        collection="North Pole Series",
        category="Buildings",
        description="Home to Santa's famous flying reindeer. Red barn with golden trim, hay loft, and reindeer stalls.",
        year_introduced=1992,
        is_retired=False,
        original_price=45.00,
        dimensions="6\" x 5\" x 5.5\"",
        materials="Porcelain, hand-painted",
    ),
    # New England Village
    VillageItem(
        id="dept56-ne001",
        name="Cape Keag Fish Cannery",
        item_number="59.5652-8",
        collection="New England Village",
        category="Buildings",
        description="Working fish cannery on the New England coast. Features dock, fishing boats, and industrial details.",
        year_introduced=1994,
        is_retired=True,
        year_retired=2000,
        original_price=48.00,
        estimated_value_min=55.00,
        estimated_value_max=80.00,
        dimensions="7\" x 5\" x 5\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-ne002",
        name="Craggy Cove Lighthouse",
        item_number="59.5930-7",
        collection="New England Village",
        category="Buildings",
        description="Classic New England lighthouse perched on rocky coast. Features rotating light mechanism and keeper's quarters.",
        year_introduced=1987,
        is_retired=True,
        year_retired=1994,
        original_price=35.00,
        estimated_value_min=90.00,
        estimated_value_max=140.00,
        dimensions="8\" x 4\" x 9\"",
        materials="Porcelain, hand-painted",
        notes="Very popular piece, one of the most sought-after",
    ),
    # Christmas in the City
    VillageItem(
        id="dept56-cc001",
        name="Hollydale's Department Store",
        item_number="58.5534-4",
        collection="Christmas in the City",
        category="Buildings",
        description="Grand department store decorated for the holidays. Features animated window displays and holiday shoppers.",
        year_introduced=1991,
        is_retired=True,
        year_retired=1997,
        original_price=75.00,
        estimated_value_min=120.00,
        estimated_value_max=180.00,
        dimensions="10\" x 6\" x 8\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-cc002",
        name="City Hall",
        item_number="58.5969-2",
        collection="Christmas in the City",
        category="Buildings",
        description="Stately city hall building with classical architecture, decorated with wreaths and holiday banners.",
        year_introduced=1988,
        is_retired=False,
        original_price=65.00,
        dimensions="8\" x 6\" x 9\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-cc003",
        name="Radio City Music Hall",
        item_number="58.5889-0",
        collection="Christmas in the City",
        category="Buildings",
        description="Iconic New York City landmark featuring Art Deco architecture and famous marquee. Licensed building.",
        year_introduced=2001,
        is_retired=True,
        year_retired=2008,
        original_price=175.00,
        estimated_value_min=200.00,
        estimated_value_max=325.00,
        dimensions="11\" x 7\" x 10\"",
        materials="Porcelain, hand-painted",
        notes="Licensed landmark building",
    ),
    # Alpine Village
    VillageItem(
        id="dept56-av001",
        name="Alpine Church",
        item_number="65.6541-2",
        collection="Alpine Village",
        category="Buildings",
        description="Traditional Alpine church with tall steeple and clock tower. Features classic Swiss architectural elements.",
        year_introduced=1987,
        is_retired=True,
        year_retired=1991,
        original_price=32.00,
        estimated_value_min=85.00,
        estimated_value_max=130.00,
        dimensions="6\" x 4\" x 9\"",
        materials="Porcelain, hand-painted",
    ),
    VillageItem(
        id="dept56-av002",
        name="Kukuck Uhren",
        item_number="65.6189-1",
        collection="Alpine Village",
        category="Buildings",
        description="Cuckoo clock shop in the German Alpine style. Features oversized cuckoo clock on facade and clock displays.",
        year_introduced=1992,
        is_retired=True,
        year_retired=1996,
        original_price=42.00,
        estimated_value_min=55.00,
        estimated_value_max=80.00,
        dimensions="5\" x 4\" x 6\"",
        materials="Porcelain, hand-painted",
    ),
]


def get_sample_collections() -> list[VillageCollection]:
    """Get sample collections."""
    return SAMPLE_COLLECTIONS.copy()


def get_sample_items() -> list[VillageItem]:
    """Get sample items."""
    return SAMPLE_ITEMS.copy()


def save_sample_data(data_dir: Path | str = "data"):
    """Save sample data to JSON files.

    Args:
        data_dir: Directory to save data to
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    items_file = data_dir / "village_items.json"
    collections_file = data_dir / "village_collections.json"

    with open(items_file, "w", encoding="utf-8") as f:
        json.dump([item.model_dump() for item in SAMPLE_ITEMS], f, indent=2)

    with open(collections_file, "w", encoding="utf-8") as f:
        json.dump([coll.model_dump() for coll in SAMPLE_COLLECTIONS], f, indent=2)

    print(f"Saved {len(SAMPLE_ITEMS)} items to {items_file}")
    print(f"Saved {len(SAMPLE_COLLECTIONS)} collections to {collections_file}")


if __name__ == "__main__":
    save_sample_data()
