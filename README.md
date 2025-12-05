# Plugin-Nesventory-LLM

An LLM-powered AI plugin for [NesVentory](https://github.com/tokendad/NesVentory) pre-trained on Department 56 Village Collectibles inventory data.

## Overview

This plugin provides AI-powered assistance for identifying and learning about Department 56 village collectibles, including:

- **Dickens Village** - Victorian-era English village pieces
- **Original Snow Village** - Classic American small-town winter scenes
- **North Pole Series** - Santa's magical workshop
- **New England Village** - Coastal New England scenes
- **Christmas in the City** - Urban holiday scenes
- **Alpine Village** - Swiss and German mountain villages

## Features

- 🔍 **Semantic Search** - Find items using natural language queries
- 🤖 **AI-Powered Responses** - Get detailed information about collectibles
- 📊 **Knowledge Base** - Pre-seeded with Department 56 item data
- 🔌 **NesVentory Integration** - Designed as a plugin for NesVentory inventory management
- 🌐 **REST API** - Easy integration with any application
- 💻 **CLI Tool** - Command-line interface for queries and management

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/tokendad/Plugin-Nesventory-LLM.git
cd Plugin-Nesventory-LLM

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
pip install -e ".[dev]"
```

### Requirements

- Python 3.9 or higher
- Dependencies are automatically installed:
  - FastAPI for the REST API
  - sentence-transformers for semantic search
  - BeautifulSoup4 for web scraping
  - scikit-learn for similarity calculations

## Quick Start

### 1. Initialize with Sample Data

The plugin comes with pre-seeded sample data for Department 56 collectibles:

```bash
# Generate sample data
python -c "from plugin_nesventory_llm.seed_data import save_sample_data; save_sample_data()"
```

### 2. Build the Knowledge Base

```bash
# Build embeddings for semantic search
nesventory-llm build
```

### 3. Query the Knowledge Base

```bash
# Single query
nesventory-llm query "Victorian house from Dickens Village"

# Interactive mode
nesventory-llm query -i
```

### 4. Start the API Server

```bash
# Start the server on port 8002
nesventory-llm serve

# With auto-reload for development
nesventory-llm serve --reload
```

## CLI Commands

```bash
# Show help
nesventory-llm --help

# Scrape data from The Village Chronicler (when available)
nesventory-llm scrape

# Build embeddings for the knowledge base
nesventory-llm build
nesventory-llm build --force  # Force rebuild

# Query the knowledge base
nesventory-llm query "lighthouse"
nesventory-llm query "lighthouse" --verbose  # Show sources
nesventory-llm query "lighthouse" --json     # JSON output
nesventory-llm query -i                      # Interactive mode

# Show statistics
nesventory-llm stats

# Start API server
nesventory-llm serve
nesventory-llm serve --port 8003
nesventory-llm serve --reload
```

## API Endpoints

When running the server (`nesventory-llm serve`), the following endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check and status |
| `/stats` | GET | Knowledge base statistics |
| `/query` | POST | Natural language query |
| `/search` | POST | Semantic search with filters |
| `/items` | GET | List all items |
| `/items/{id}` | GET | Get specific item |
| `/scrape` | POST | Trigger data scrape |
| `/nesventory/identify` | POST | Identify item for NesVentory |
| `/nesventory/collections` | GET | Get collections for NesVentory |

### Example API Usage

```bash
# Health check
curl http://localhost:8002/health

# Query the knowledge base
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Victorian house", "limit": 5}'

# Search with filters
curl -X POST http://localhost:8002/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "lighthouse",
    "collection": "New England Village",
    "limit": 10
  }'

# Identify an item (for NesVentory integration)
curl -X POST "http://localhost:8002/nesventory/identify?query=Scrooge%20counting%20house"
```

## NesVentory Integration

This plugin is designed to integrate with [NesVentory](https://github.com/tokendad/NesVentory) as an AI assistant for:

1. **Item Identification** - Identify Department 56 items from user descriptions
2. **Value Estimation** - Provide estimated values for collectibles
3. **Collection Information** - Get details about specific collections
4. **Similar Items** - Find similar items in the inventory

### Integration Example

```python
import httpx

# Query the plugin from NesVentory
async def identify_village_item(description: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/nesventory/identify",
            params={"query": description}
        )
        return response.json()
```

## Data Sources

The knowledge base can be populated from:

1. **Sample Data** - Pre-seeded Department 56 collectibles (included)
2. **Web Scraping** - Scrape from The Village Chronicler website
3. **Manual Entry** - Add items via the API

### Sample Collections Included

- Dickens Village (Victorian England)
- Original Snow Village (American winter scenes)
- North Pole Series (Santa's workshop)
- New England Village (Coastal scenes)
- Christmas in the City (Urban holidays)
- Alpine Village (Swiss/German mountains)

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=plugin_nesventory_llm
```

### Code Formatting

```bash
# Format code
black src tests

# Lint code
ruff check src tests
```

## Project Structure

```
Plugin-Nesventory-LLM/
├── src/
│   └── plugin_nesventory_llm/
│       ├── __init__.py       # Package info
│       ├── api.py            # FastAPI endpoints
│       ├── cli.py            # Command-line interface
│       ├── knowledge_base.py # Semantic search engine
│       ├── models.py         # Pydantic data models
│       ├── scraper.py        # Web scraper
│       └── seed_data.py      # Sample data
├── data/                     # Data storage directory
├── tests/                    # Test suite
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please see the main NesVentory repository for contribution guidelines.

## Related Projects

- [NesVentory](https://github.com/tokendad/NesVentory) - Home inventory management system
- [The Village Chronicler](https://thevillagechronicler.com) - Department 56 collectibles reference
