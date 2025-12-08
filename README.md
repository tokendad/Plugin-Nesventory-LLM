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
- 📸 **Image Search** - Upload photos to identify Department 56 collectibles
- 🤖 **AI-Powered Responses** - Get detailed information about collectibles
- 📊 **Knowledge Base** - Pre-seeded with Department 56 item data
- 🔌 **NesVentory Integration** - Designed as a plugin for NesVentory inventory management
- 🌐 **REST API** - Easy integration with any application
- 💻 **CLI Tool** - Command-line interface for queries and management

## Installation

### Using Docker (Recommended)

The easiest way to run NesVentory LLM is using Docker:

```bash
# Clone the repository
git clone https://github.com/tokendad/Plugin-Nesventory-LLM.git
cd Plugin-Nesventory-LLM

# Build the Docker image
docker build -t nesventory-llm:latest .

# Run with docker-compose (recommended)
docker-compose up -d

# Or run directly
docker run -d \
  --name nesventory-llm \
  -p 8002:8002 \
  -v $(pwd)/data:/app/data \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=UTC \
  --restart unless-stopped \
  nesventory-llm:latest
```

Access the status page at: http://localhost:8002

#### Troubleshooting Docker Build

If you encounter SSL certificate errors during the Docker build (common in corporate environments with SSL inspection):

**Option 1: Use corporate CA certificates (Recommended)**
```dockerfile
# Add to Dockerfile:
COPY corporate-ca.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates
```

**Option 2: Temporary SSL bypass (Development only)**
```bash
# Only use this in development/testing environments
docker build --build-arg PIP_TRUSTED_HOST=pypi.org,files.pythonhosted.org \
  -t nesventory-llm:latest .
```

⚠️ **Note**: Disabling SSL verification should only be used as a last resort and never in production environments.

### Docker Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PUID` | User ID for file permissions | 1000 |
| `PGID` | Group ID for file permissions | 1000 |
| `TZ` | Timezone (e.g., America/New_York) | UTC |

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

- Python 3.9 or higher (or Docker)
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

### 5. Access the Status Webpage

When using Docker or running the API server, a web-based status page is available at:

```
http://localhost:8002
```

The status page provides:
- **System Status** - Real-time health and statistics
- **Query Interface** - Search the knowledge base directly from your browser
- **Build Embeddings** - Rebuild the semantic search index
- **CLI Commands** - Quick reference for Docker CLI usage

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

### Using CLI Commands with Docker

When running in Docker, use `docker exec` to run CLI commands:

```bash
# Query the knowledge base
docker exec nesventory-llm nesventory-llm query "lighthouse"

# Build embeddings
docker exec nesventory-llm nesventory-llm build

# Show statistics
docker exec nesventory-llm nesventory-llm stats

# Interactive query mode
docker exec -it nesventory-llm nesventory-llm query -i
```

## API Endpoints

When running the server (`nesventory-llm serve`), the following endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Status webpage (HTML interface) |
| `/health` | GET | Health check and status |
| `/stats` | GET | Knowledge base statistics |
| `/query` | POST | Natural language query |
| `/search` | POST | Semantic search with filters |
| `/search/image` | POST | Search by uploading an image |
| `/items` | GET | List all items |
| `/items/{id}` | GET | Get specific item |
| `/build` | POST | Build/rebuild embeddings |
| `/scrape` | POST | Trigger data scrape |
| `/nesventory/identify` | POST | Identify item for NesVentory |
| `/nesventory/identify/image` | POST | Identify item from image for NesVentory |
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

# Search by image
curl -X POST http://localhost:8002/search/image \
  -F "file=@photo.jpg" \
  -F "limit=10" \
  -F "min_confidence=0.3"

# Identify an item (for NesVentory integration)
curl -X POST "http://localhost:8002/nesventory/identify?query=Scrooge%20counting%20house"

# Identify items from an image (for NesVentory integration)
curl -X POST http://localhost:8002/nesventory/identify/image \
  -F "file=@collectible.jpg"
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

# Identify items from an image
async def identify_from_image(image_path: str):
    async with httpx.AsyncClient() as client:
        with open(image_path, "rb") as f:
            files = {"file": f}
            response = await client.post(
                "http://localhost:8002/nesventory/identify/image",
                files=files
            )
        return response.json()
```

## Image Search

The plugin includes AI-powered image search capabilities, allowing you to identify Department 56 collectibles from photos. This feature uses computer vision to analyze images and match detected objects against the knowledge base.

### How It Works

1. **Upload an Image** - Provide a photo containing one or more Department 56 collectible items
2. **Object Detection** - The system analyzes the image and generates descriptions of the visible items
3. **Semantic Matching** - Detected objects are matched against the knowledge base using semantic similarity
4. **Return Results** - Get a list of matching items with confidence scores

### Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)
- BMP (.bmp)

### Using Image Search

#### Via API

```bash
# Search for items by uploading an image
curl -X POST http://localhost:8002/search/image \
  -F "file=@my_collectible.jpg" \
  -F "limit=5" \
  -F "min_confidence=0.3"

# For NesVentory integration
curl -X POST http://localhost:8002/nesventory/identify/image \
  -F "file=@my_collectible.jpg"
```

#### Via Python

```python
import httpx

async def search_by_image(image_path: str):
    async with httpx.AsyncClient() as client:
        with open(image_path, "rb") as f:
            files = {"file": ("image.jpg", f, "image/jpeg")}
            params = {
                "limit": 10,
                "min_confidence": 0.3,
                "collection": "Dickens Village"  # Optional filter
            }
            response = await client.post(
                "http://localhost:8002/search/image",
                files=files,
                params=params
            )
        return response.json()
```

### Response Format

The image search endpoint returns:

- **detected_objects**: List of objects detected in the image with confidence scores
- **matched_items**: Department 56 items that match the detected objects
- **overall_confidence**: Average confidence score across all matches
- **processing_time_ms**: Time taken to process the image in milliseconds

### Tips for Best Results

- Use clear, well-lit photos
- Ensure items are visible and not obscured
- Close-up shots work better than distant photos
- Multiple items can be detected in a single image

## Data Sources

The knowledge base can be populated from:

1. **Sample Data** - Pre-seeded Department 56 collectibles (included)
2. **Web Scraping** - Scrape from multiple sources:
   - The Village Chronicler website (https://thevillagechronicler.com/All-ProductList.shtml)
   - Department 56 Retired Products (https://retiredproducts.department56.com/pages/history-lists)
3. **Manual Entry** - Add items via the API

### Web Scraping Details

The scraper automatically collects data from:

**The Village Chronicler** - Provides comprehensive product lists with:
- Village collection names
- Item numbers
- Item descriptions
- Manufacturing date ranges
- Links to detailed collection pages

**Department 56 Retired Products** - Downloads and parses PDF files containing:
- Item numbers
- Detailed descriptions
- Year issued
- Year retired
- US suggested retail prices (SRP)
- Canadian suggested retail prices (SRP)

To run the scraper:
```bash
nesventory-llm scrape
```

This will fetch data from both sources and save it to the data directory.

### Sample Collections Included

- Dickens Village (Victorian England)
- Original Snow Village (American winter scenes)
- North Pole Series (Santa's workshop)
- New England Village (Coastal scenes)
- Christmas in the City (Urban holidays)
- Alpine Village (Swiss/German mountains)

## Docker Deployment

### Adding to Existing Docker Compose

To add NesVentory LLM to your existing docker-compose setup, add the following service definition:

```yaml
services:
  nesventory-llm:
    image: nesventory-llm:latest
    container_name: nesventory-llm
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=UTC
    volumes:
      - ./nesventory-llm-data:/app/data
    ports:
      - "8002:8002"
    restart: unless-stopped
```

Or use the provided `docker-compose.yml` as a starting point.

### Running the Container

Once built, you can run the container using docker-compose or directly:

**Using docker-compose (Recommended):**
```bash
docker-compose up -d
```

**Using docker run:**
```bash
docker run -d \
  --name nesventory-llm \
  -p 8002:8002 \
  -v $(pwd)/data:/app/data \
  -e PUID=$(id -u) \
  -e PGID=$(id -g) \
  -e TZ=America/New_York \
  --restart unless-stopped \
  nesventory-llm:latest
```

### Accessing the Status Page

The container provides a web-based status and management interface at:
```
http://localhost:8002
```

Features available through the web interface:
- System health and statistics
- Query the knowledge base
- Build/rebuild embeddings
- View CLI command reference

### Managing the Container

```bash
# View logs
docker logs nesventory-llm

# Follow logs in real-time
docker logs -f nesventory-llm

# Stop the container
docker-compose down
# or
docker stop nesventory-llm

# Restart the container
docker-compose restart
# or
docker restart nesventory-llm

# Access the container shell
docker exec -it nesventory-llm /bin/bash
```

### Persistent Data

The `data` directory is mapped as a volume to persist:
- Knowledge base items (JSON files)
- Embeddings (PKL files)
- Any scraped data

This ensures your data survives container restarts and updates.

### Updating the Container

To update to a new version:

```bash
# Stop the current container
docker-compose down

# Pull/rebuild the image
docker build -t nesventory-llm:latest .

# Start with the new image
docker-compose up -d
```

Your data in the `data` volume will be preserved.

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
