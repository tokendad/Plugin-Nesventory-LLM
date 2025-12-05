"""
Knowledge base for Department 65 village collectibles.

This module provides semantic search capabilities using sentence embeddings
for finding relevant items based on natural language queries.
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .models import ItemQuery, ItemSearchResult, LLMResponse, VillageItem

logger = logging.getLogger(__name__)

# Default embedding model - lightweight and effective for semantic search
DEFAULT_MODEL = "all-MiniLM-L6-v2"


class KnowledgeBase:
    """Knowledge base with semantic search for village collectibles."""

    def __init__(self, data_dir: Path | str = "data", model_name: str = DEFAULT_MODEL):
        """Initialize the knowledge base.

        Args:
            data_dir: Directory containing item data
            model_name: Name of the sentence-transformer model to use
        """
        self.data_dir = Path(data_dir)
        self.model_name = model_name
        self.items: list[VillageItem] = []
        self.embeddings: Optional[np.ndarray] = None
        self._model = None

    @property
    def model(self):
        """Lazy load the sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
                raise
        return self._model

    def _item_to_text(self, item: VillageItem) -> str:
        """Convert an item to a text representation for embedding."""
        parts = [item.name]

        if item.collection:
            parts.append(f"Collection: {item.collection}")

        if item.category:
            parts.append(f"Category: {item.category}")

        if item.description:
            parts.append(item.description)

        if item.item_number:
            parts.append(f"Item number: {item.item_number}")

        if item.year_introduced:
            parts.append(f"Introduced in {item.year_introduced}")

        if item.is_retired and item.year_retired:
            parts.append(f"Retired in {item.year_retired}")

        if item.materials:
            parts.append(f"Materials: {item.materials}")

        if item.notes:
            parts.append(item.notes)

        return " | ".join(parts)

    def load_items(self, items_file: Optional[Path] = None) -> int:
        """Load items from a JSON file.

        Args:
            items_file: Path to items JSON file. If None, uses default location.

        Returns:
            Number of items loaded
        """
        if items_file is None:
            items_file = self.data_dir / "village_items.json"

        if not items_file.exists():
            logger.warning(f"Items file not found: {items_file}")
            return 0

        with open(items_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.items = [VillageItem(**item) for item in data]

        logger.info(f"Loaded {len(self.items)} items from {items_file}")
        return len(self.items)

    def add_items(self, items: list[VillageItem]):
        """Add items to the knowledge base.

        Args:
            items: List of VillageItem objects to add
        """
        self.items.extend(items)
        # Invalidate embeddings since we added new items
        self.embeddings = None
        logger.info(f"Added {len(items)} items. Total: {len(self.items)}")

    def build_embeddings(self, force: bool = False) -> np.ndarray:
        """Build embeddings for all items.

        Args:
            force: If True, rebuild even if embeddings exist

        Returns:
            Numpy array of embeddings
        """
        embeddings_file = self.data_dir / "embeddings.pkl"

        # Try to load existing embeddings
        if not force and embeddings_file.exists():
            try:
                with open(embeddings_file, "rb") as f:
                    cached = pickle.load(f)
                    if cached.get("num_items") == len(self.items):
                        self.embeddings = cached["embeddings"]
                        logger.info(f"Loaded cached embeddings for {len(self.items)} items")
                        return self.embeddings
            except Exception as e:
                logger.warning(f"Failed to load cached embeddings: {e}")

        if not self.items:
            logger.warning("No items to embed")
            return np.array([])

        # Generate embeddings
        logger.info(f"Building embeddings for {len(self.items)} items...")
        texts = [self._item_to_text(item) for item in self.items]
        self.embeddings = self.model.encode(texts, show_progress_bar=True)

        # Cache embeddings
        with open(embeddings_file, "wb") as f:
            pickle.dump({"num_items": len(self.items), "embeddings": self.embeddings}, f)

        logger.info(f"Built and cached embeddings: shape {self.embeddings.shape}")
        return self.embeddings

    def search(self, query: ItemQuery) -> list[ItemSearchResult]:
        """Search for items matching a query.

        Args:
            query: ItemQuery object with search parameters

        Returns:
            List of ItemSearchResult objects sorted by relevance
        """
        if self.embeddings is None or len(self.embeddings) == 0:
            self.build_embeddings()

        if self.embeddings is None or len(self.embeddings) == 0:
            return []

        # Embed the query
        query_embedding = self.model.encode([query.query])

        # Calculate similarities
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]

        # Create results with scores
        results = []
        for idx, (item, score) in enumerate(zip(self.items, similarities)):
            # Apply filters
            if query.collection and item.collection != query.collection:
                continue
            if query.category and item.category != query.category:
                continue
            if query.min_year and item.year_introduced and item.year_introduced < query.min_year:
                continue
            if query.max_year and item.year_introduced and item.year_introduced > query.max_year:
                continue
            if not query.include_retired and item.is_retired:
                continue

            results.append(
                ItemSearchResult(
                    item=item, relevance_score=float(score), match_reason=self._explain_match(item, query.query)
                )
            )

        # Sort by relevance and limit
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[: query.limit]

    def _explain_match(self, item: VillageItem, query: str) -> str:
        """Generate an explanation for why an item matched a query."""
        query_lower = query.lower()
        reasons = []

        if item.name.lower() in query_lower or query_lower in item.name.lower():
            reasons.append(f"Name matches: '{item.name}'")

        if item.collection and item.collection.lower() in query_lower:
            reasons.append(f"Collection matches: '{item.collection}'")

        if item.category and item.category.lower() in query_lower:
            reasons.append(f"Category matches: '{item.category}'")

        if item.description and any(word in item.description.lower() for word in query_lower.split()):
            reasons.append("Description contains query terms")

        return "; ".join(reasons) if reasons else "Semantic similarity match"

    def generate_response(self, query: str, limit: int = 5) -> LLMResponse:
        """Generate a natural language response to a query about village items.

        This uses RAG (Retrieval Augmented Generation) to find relevant items
        and generate an informative response.

        Args:
            query: Natural language query
            limit: Maximum number of source items to use

        Returns:
            LLMResponse with answer and sources
        """
        # Search for relevant items
        item_query = ItemQuery(query=query, limit=limit)
        results = self.search(item_query)

        if not results:
            return LLMResponse(
                query=query,
                answer="I couldn't find any items matching your query in the Department 65 inventory.",
                sources=[],
                confidence=0.0,
            )

        # Generate response based on top results
        top_items = results[:3]
        avg_score = sum(r.relevance_score for r in top_items) / len(top_items)

        # Build response
        if len(top_items) == 1:
            item = top_items[0].item
            answer = self._format_single_item_response(item, query)
        else:
            answer = self._format_multi_item_response(top_items, query)

        return LLMResponse(
            query=query, answer=answer, sources=results[:limit], confidence=min(avg_score * 1.2, 1.0)
        )

    def _format_single_item_response(self, item: VillageItem, query: str) -> str:
        """Format a response for a single item match."""
        parts = [f"I found **{item.name}**"]

        if item.collection:
            parts[0] += f" from the {item.collection}"

        if item.item_number:
            parts.append(f"Item Number: {item.item_number}")

        if item.description:
            parts.append(f"Description: {item.description}")

        if item.year_introduced:
            status = "introduced" if not item.is_retired else "released"
            parts.append(f"Year {status}: {item.year_introduced}")

        if item.is_retired and item.year_retired:
            parts.append(f"Retired: {item.year_retired}")

        if item.original_price:
            parts.append(f"Original Price: ${item.original_price:.2f}")

        if item.estimated_value_min and item.estimated_value_max:
            parts.append(
                f"Estimated Value: ${item.estimated_value_min:.2f} - ${item.estimated_value_max:.2f}"
            )

        return "\n\n".join(parts)

    def _format_multi_item_response(self, results: list[ItemSearchResult], query: str) -> str:
        """Format a response for multiple item matches."""
        intro = f"I found {len(results)} items matching your query:\n\n"

        items_text = []
        for i, result in enumerate(results, 1):
            item = result.item
            item_info = f"{i}. **{item.name}**"
            if item.collection:
                item_info += f" ({item.collection})"
            if item.item_number:
                item_info += f" - #{item.item_number}"
            if item.year_introduced:
                item_info += f" [{item.year_introduced}]"
            items_text.append(item_info)

        return intro + "\n".join(items_text)

    def get_stats(self) -> dict:
        """Get statistics about the knowledge base.

        Returns:
            Dictionary with stats
        """
        collections = set(item.collection for item in self.items if item.collection)
        categories = set(item.category for item in self.items if item.category)

        return {
            "total_items": len(self.items),
            "collections": list(collections),
            "categories": list(categories),
            "has_embeddings": self.embeddings is not None,
            "embedding_shape": self.embeddings.shape if self.embeddings is not None else None,
        }
