"""
Command-line interface for NesVentory LLM Plugin.

Provides commands for scraping data, querying the knowledge base,
and running the API server.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def cmd_scrape(args):
    """Scrape data from The Village Chronicler website."""
    from .scraper import VillageChroniclerScraper

    logger.info(f"Scraping data to {args.data_dir}")

    with VillageChroniclerScraper(args.data_dir) as scraper:
        collections, items = scraper.scrape_all()
        output_file = scraper.save_data()

    print(f"\nScraping complete!")
    print(f"  Collections found: {len(collections)}")
    print(f"  Items found: {len(items)}")
    print(f"  Data saved to: {output_file}")


def cmd_build(args):
    """Build embeddings for the knowledge base."""
    from .knowledge_base import KnowledgeBase

    kb = KnowledgeBase(data_dir=args.data_dir)
    items_loaded = kb.load_items()

    if items_loaded == 0:
        print("No items found. Run 'nesventory-llm scrape' first.")
        sys.exit(1)

    print(f"Building embeddings for {items_loaded} items...")
    embeddings = kb.build_embeddings(force=args.force)
    print(f"Embeddings built: shape {embeddings.shape}")


def cmd_query(args):
    """Query the knowledge base."""
    from .knowledge_base import KnowledgeBase
    from .models import ItemQuery

    kb = KnowledgeBase(data_dir=args.data_dir)
    items_loaded = kb.load_items()

    if items_loaded == 0:
        print("No items found. Run 'nesventory-llm scrape' first.")
        sys.exit(1)

    kb.build_embeddings()

    if args.interactive:
        print("Interactive mode. Type 'quit' to exit.\n")
        while True:
            try:
                query_text = input("Query> ").strip()
                if query_text.lower() in ("quit", "exit", "q"):
                    break
                if not query_text:
                    continue

                response = kb.generate_response(query_text, limit=args.limit)
                print(f"\n{response.answer}\n")
                if args.verbose and response.sources:
                    print("Sources:")
                    for src in response.sources:
                        print(f"  - {src.item.name} (score: {src.relevance_score:.3f})")
                    print()
            except KeyboardInterrupt:
                print("\n")
                break
    else:
        if not args.query:
            print("Error: Query required in non-interactive mode")
            sys.exit(1)

        response = kb.generate_response(args.query, limit=args.limit)

        if args.json:
            print(json.dumps(response.model_dump(), indent=2, default=str))
        else:
            print(f"\n{response.answer}\n")
            if args.verbose and response.sources:
                print(f"Confidence: {response.confidence:.2%}")
                print("\nSources:")
                for src in response.sources:
                    print(f"  - {src.item.name} (score: {src.relevance_score:.3f})")


def cmd_serve(args):
    """Run the API server."""
    import uvicorn

    logger.info(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(
        "plugin_nesventory_llm.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def cmd_stats(args):
    """Show statistics about the knowledge base."""
    from .knowledge_base import KnowledgeBase

    kb = KnowledgeBase(data_dir=args.data_dir)
    items_loaded = kb.load_items()

    if items_loaded == 0:
        print("No items in knowledge base.")
        print("Run 'nesventory-llm scrape' to fetch data.")
        return

    stats = kb.get_stats()

    print(f"\nKnowledge Base Statistics")
    print(f"{'=' * 40}")
    print(f"Total Items: {stats['total_items']}")
    print(f"\nCollections ({len(stats['collections'])}):")
    for coll in sorted(stats["collections"]):
        count = sum(1 for i in kb.items if i.collection == coll)
        print(f"  - {coll}: {count} items")

    if stats["categories"]:
        print(f"\nCategories ({len(stats['categories'])}):")
        for cat in sorted(stats["categories"]):
            count = sum(1 for i in kb.items if i.category == cat)
            print(f"  - {cat}: {count} items")

    print(f"\nEmbeddings: {'Ready' if stats['has_embeddings'] else 'Not built'}")
    if stats["embedding_shape"]:
        print(f"  Shape: {stats['embedding_shape']}")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="NesVentory LLM Plugin - Department 56 Village Collectibles AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nesventory-llm scrape              # Scrape data from Village Chronicler
  nesventory-llm build               # Build embeddings
  nesventory-llm query "Victorian house"  # Query the knowledge base
  nesventory-llm query -i            # Interactive query mode
  nesventory-llm serve               # Start the API server
  nesventory-llm stats               # Show knowledge base statistics
        """,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory for data storage (default: data)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape data from Village Chronicler")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build embeddings for the knowledge base")
    build_parser.add_argument("--force", action="store_true", help="Force rebuild of embeddings")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query the knowledge base")
    query_parser.add_argument("query", nargs="?", help="Query text")
    query_parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    query_parser.add_argument("-l", "--limit", type=int, default=5, help="Max results (default: 5)")
    query_parser.add_argument("-v", "--verbose", action="store_true", help="Show sources")
    query_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Run the API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8002, help="Port to bind (default: 8002)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show knowledge base statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Dispatch to command handler
    handlers = {
        "scrape": cmd_scrape,
        "build": cmd_build,
        "query": cmd_query,
        "serve": cmd_serve,
        "stats": cmd_stats,
    }

    try:
        handlers[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        logger.exception("Error")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
