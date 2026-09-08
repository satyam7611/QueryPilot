import os
import json
import math
from typing import Optional, Dict, Any, List
from app.rag.schema_docs import SCHEMA_CARDS, build_custom_schema_card
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
    and retrieving relevant DDL schemas using semantic vector similarity search
    for both default demo database and isolated dynamic uploaded datasets.
    """
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.dataset_cache: Dict[str, Dict[str, Any]] = {}
        self._initialize_index()

    def _initialize_index(self):
        """Loads cached demo schema card embeddings or generates and caches them."""
        # 1. If cache file exists, load it
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                # Verify we have entries for all cards
                if all(table in self.cache for table in SCHEMA_CARDS):
                    print("[SchemaRetriever] Loaded demo schema embeddings from cache.")
                    return
            except Exception as e:
                print(f"[SchemaRetriever] Failed to read cache: {e}. Rebuilding...")

        # 2. Build cache if missing/corrupted
        print("[SchemaRetriever] Generating demo schema embeddings (one-time API generation)...")
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

    def index_dataset(
        self,
        dataset_id: str,
        table_name: str,
        filename: str,
        columns_metadata: list,
        api_key: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Builds a structured schema card, computes its hash, generates embeddings
        if missing or changed, and caches the dataset schema index in-memory.
        """
        card = build_custom_schema_card(dataset_id, table_name, filename, columns_metadata)
        schema_hash = card["schema_hash"]
        
        # Check if already cached with matching hash
        if not force_refresh and dataset_id in self.dataset_cache:
            existing = self.dataset_cache[dataset_id]
            if existing.get("schema_hash") == schema_hash and "embedding" in existing:
                print(f"[SchemaRetriever] Reusing cached schema embeddings for dataset {dataset_id} (hash: {schema_hash})")
                return existing

        # Generate embedding for custom schema
        print(f"[SchemaRetriever] Generating schema embeddings for dataset {dataset_id} (hash: {schema_hash})...")
        embedding = get_embedding(card["text_to_embed"], api_key=api_key)
        
        entry = {
            "dataset_id": dataset_id,
            "table_name": table_name,
            "filename": filename,
            "schema_hash": schema_hash,
            "embedding": embedding,
            "ddl": card["ddl"],
            "description": card["description"],
            "context": card["context"],
            "columns": columns_metadata
        }
        self.dataset_cache[dataset_id] = entry
        print(f"[SchemaRetriever] Successfully indexed schema for dataset {dataset_id}")
        return entry

    def delete_dataset(self, dataset_id: str):
        """Removes a dataset's schema embeddings and index from memory."""
        if dataset_id in self.dataset_cache:
            del self.dataset_cache[dataset_id]
            print(f"[SchemaRetriever] Deleted schema embeddings for dataset {dataset_id}")

    def _ensure_dataset_loaded(self, dataset_id: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Loads dataset metadata from PostgreSQL if not present in memory cache."""
        if dataset_id in self.dataset_cache:
            return self.dataset_cache[dataset_id]
            
        from app.services.dataset_service import get_db_connection, ensure_metadata_table
        ensure_metadata_table()
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name, original_filename, columns_metadata
                    FROM datasets_metadata WHERE dataset_id = %s;
                """, (dataset_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Dataset {dataset_id} not found in metadata.")
                table_name, filename, cols_meta = row
                if isinstance(cols_meta, str):
                    cols_meta = json.loads(cols_meta)
                return self.index_dataset(dataset_id, table_name, filename, cols_meta, api_key=api_key)
        finally:
            conn.close()

    def retrieve(
        self,
        query: str,
        k: int = 3,
        api_key: Optional[str] = None,
        dataset_id: Optional[str] = None
    ) -> str:
        """
        Embeds the query, calculates similarity with relevant schema cards,
        and returns the top k relevant DDL blocks combined.
        Guarantees strict dataset isolation (dataset_id scope).
        """
        print(f"[SchemaRetriever] Searching schema for query: '{query}' (dataset: {dataset_id or 'demo'})...")
        
        # Get query vector representation
        query_vector = get_embedding(query, api_key=api_key)
        
        # 1. Custom Dataset Scope
        if dataset_id:
            ds_data = self._ensure_dataset_loaded(dataset_id, api_key=api_key)
            if not ds_data:
                return f"-- Error: Schema not found for dataset {dataset_id}"
                
            sim = cosine_similarity(query_vector, ds_data["embedding"])
            print(f" - Custom Table: {ds_data['table_name']} | Cosine Similarity: {sim:.4f}")
            return f"-- Table: {ds_data['table_name']}\n-- Description: {ds_data['description']}\n{ds_data['ddl']}\n"
            
        # 2. Demo Database Scope
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
            card_str = f"-- Table: {table_name}\n-- Description: {desc}\n{ddl}\n"
            top_k_ddl.append(card_str)
            
        return "\n".join(top_k_ddl)

# Instantiated single retriever instance
_retriever = None

def get_schema_retriever() -> SchemaRetriever:
    global _retriever
    if _retriever is None:
        _retriever = SchemaRetriever()
    return _retriever

def retrieve_relevant_schema(
    query: str,
    k: int = 3,
    api_key: Optional[str] = None,
    dataset_id: Optional[str] = None
) -> str:
    """Helper functional interface to call retriever."""
    return get_schema_retriever().retrieve(query, k=k, api_key=api_key, dataset_id=dataset_id)

def index_dataset_schema(
    dataset_id: str,
    table_name: str,
    filename: str,
    columns_metadata: list,
    api_key: Optional[str] = None,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """Indexes custom dataset schema metadata into RAG."""
    return get_schema_retriever().index_dataset(
        dataset_id=dataset_id,
        table_name=table_name,
        filename=filename,
        columns_metadata=columns_metadata,
        api_key=api_key,
        force_refresh=force_refresh
    )

def delete_dataset_schema(dataset_id: str):
    """Deletes custom dataset schema embeddings from RAG index."""
    get_schema_retriever().delete_dataset(dataset_id)

def get_active_schema_hash(dataset_id: Optional[str] = None) -> str:
    """Returns the deterministic schema hash for a dataset or demo database."""
    if not dataset_id:
        return "demo_v1"
    try:
        ds_info = get_schema_retriever()._ensure_dataset_loaded(dataset_id)
        return ds_info["schema_hash"] if ds_info else "custom_unknown"
    except Exception:
        return "custom_unknown"
