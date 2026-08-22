import os
import json
import math
from app.rag.schema_docs import SCHEMA_CARDS
from app.rag.embeddings import get_embedding

# Paths for embedding caching
CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(CACHE_DIR, "schema_cache.json")

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Computes the cosine similarity between two vectors in pure Python."""
    dot_product = sum(x * y for x, y in zip(v1, v2))
    norm_v1 = math.sqrt(sum(x * x for x in v1))
    norm_v2 = math.sqrt(sum(x * x for x in v2))
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

class SchemaRetriever:
    """
    Handles indexing of schema card documents, caching their embeddings,
    and retrieving relevant DDL schemas using semantic vector similarity search.
    """
    def __init__(self):
        self.cache = {}
        self._initialize_index()

    def _initialize_index(self):
        """Loads cached schema card embeddings or generates and caches them."""
        # 1. If cache file exists, load it
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                # Verify we have entries for all cards
                if all(table in self.cache for table in SCHEMA_CARDS):
                    print("[SchemaRetriever] Loaded schema embeddings from cache.")
                    return
            except Exception as e:
                print(f"[SchemaRetriever] Failed to read cache: {e}. Rebuilding...")

        # 2. Build cache if missing/corrupted
        print("[SchemaRetriever] Generating schema embeddings (one-time API generation)...")
        self.cache = {}
        for table_name, card in SCHEMA_CARDS.items():
            # Embed table descriptions + ddl contexts
            text_to_embed = f"Table: {card['name']}. Description: {card['description']}. Context: {card['context']}"
            embedding = get_embedding(text_to_embed)
            self.cache[table_name] = {
                "embedding": embedding,
                "ddl": card["ddl"],
                "description": card["description"]
            }
            
        # 3. Save cache to disk
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=4)
            print("[SchemaRetriever] Pre-computed schema embeddings cached to disk.")
        except Exception as e:
            print(f"[SchemaRetriever] Failed to write cache: {e}")

    def retrieve(self, query: str, k: int = 3) -> str:
        """
        Embeds the query, calculates similarity with all schema cards,
        and returns the top k relevant DDL blocks combined.
        """
        print(f"[SchemaRetriever] Searching schema for query: '{query}'...")
        
        # Get query vector representation
        query_vector = get_embedding(query)
        
        # Calculate similarity scores
        scores = []
        for table_name, data in self.cache.items():
            sim = cosine_similarity(query_vector, data["embedding"])
            scores.append((table_name, sim, data["ddl"], data["description"]))
            
        # Sort by similarity descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        print("\n--- Semantic Retrieval Scores ---")
        for table_name, score, _, _ in scores:
            print(f" - Table: {table_name:<12} | Cosine Similarity: {score:.4f}")
        print("---------------------------------\n")
        
        # Extract the top k DDL cards
        top_k_ddl = []
        for i in range(min(k, len(scores))):
            table_name, _, ddl, desc = scores[i]
            # Format the DDL card cleanly for the prompt context
            card_str = f"-- Table: {table_name}\n-- Description: {desc}\n{ddl}\n"
            top_k_ddl.append(card_str)
            
        return "\n".join(top_k_ddl)

# Instantiated single retriever instance
_retriever = None

def retrieve_relevant_schema(query: str, k: int = 3) -> str:
    """Helper functional interface to call retriever."""
    global _retriever
    if _retriever is None:
        _retriever = SchemaRetriever()
    return _retriever.retrieve(query, k=k)
