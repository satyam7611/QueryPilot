import re
import time
import hashlib
import threading
from typing import Optional, Dict, Any

def normalize_sql_for_cache(sql_query: str) -> str:
    """Normalizes SQL query whitespace and casing for deterministic cache key generation."""
    if not sql_query:
        return ""
    # Strip comments
    cleaned = re.sub(r"--.*$", "", sql_query, flags=re.MULTILINE)
    # Collapse multiple whitespace characters to a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.rstrip(";").strip()

class QueryResultCache:
    """
    Thread-safe in-memory cache for validated SQL query results with TTL support
    and strict dataset / schema-hash isolation.
    """
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _build_key(self, dataset_id: Optional[str], schema_hash: Optional[str], sql_query: str) -> str:
        norm_sql = normalize_sql_for_cache(sql_query)
        ds_part = dataset_id or "demo"
        hash_part = schema_hash or "demo_v1"
        raw_key = f"{ds_part}:{hash_part}:{norm_sql}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(
        self,
        dataset_id: Optional[str],
        schema_hash: Optional[str],
        sql_query: str
    ) -> Optional[str]:
        """
        Retrieves a cached query result if available and unexpired.
        Returns None on cache miss or expiration.
        """
        if not sql_query:
            return None

        key = self._build_key(dataset_id, schema_hash, sql_query)
        now = time.time()

        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None

            # Check expiration
            if now > entry["expires_at"]:
                del self._cache[key]
                return None

            return entry["result"]

    def set(
        self,
        dataset_id: Optional[str],
        schema_hash: Optional[str],
        sql_query: str,
        result: str,
        ttl: Optional[int] = None
    ):
        """
        Caches a successful query result. Does NOT cache errors or empty failures.
        """
        if not sql_query or not result or result.startswith("Database Error:"):
            return

        key = self._build_key(dataset_id, schema_hash, sql_query)
        ttl_seconds = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl_seconds
        ds_part = dataset_id or "demo"

        with self._lock:
            self._cache[key] = {
                "result": result,
                "dataset_id": ds_part,
                "schema_hash": schema_hash or "demo_v1",
                "expires_at": expires_at,
                "created_at": time.time()
            }

    def invalidate_dataset(self, dataset_id: Optional[str]):
        """Purges all cached query results associated with a specific dataset."""
        ds_part = dataset_id or "demo"
        with self._lock:
            keys_to_delete = [
                k for k, v in self._cache.items()
                if v.get("dataset_id") == ds_part
            ]
            for k in keys_to_delete:
                del self._cache[k]

    def clear(self):
        """Clears all cached results."""
        with self._lock:
            self._cache.clear()

# Global singleton cache instance
query_cache = QueryResultCache(default_ttl=300)
