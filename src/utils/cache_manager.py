"""
Simple Cache Manager for tool outputs.
Implements in-memory caching with optional file persistence.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Optional
from datetime import datetime


class CacheManager:
    """
    Simple cache manager with TTL support.
    Used to avoid redundant API calls and ChromaDB queries.
    """
    
    def __init__(
        self,
        cache_dir: str = "data/cache",
        default_ttl: int = 300,  # 5 minutes
        enable_file_cache: bool = True
    ):
        self.cache_dir = Path(cache_dir)
        self.default_ttl = default_ttl
        self.enable_file_cache = enable_file_cache
        self._memory_cache: dict[str, dict] = {}
        
        if enable_file_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate a unique cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(
        self,
        cache_name: str,
        *args,
        ttl: Optional[int] = None,
        **kwargs
    ) -> Optional[Any]:
        """
        Get cached value if exists and not expired.
        
        Args:
            cache_name: Name of the cache (e.g., 'historical', 'cost_api')
            *args, **kwargs: Arguments used to generate cache key
            ttl: Time-to-live in seconds (uses default if not specified)
        
        Returns:
            Cached value or None if not found/expired
        """
        ttl = ttl or self.default_ttl
        key = self._generate_key(*args, **kwargs)
        full_key = f"{cache_name}:{key}"
        
        # Check memory cache first
        if full_key in self._memory_cache:
            entry = self._memory_cache[full_key]
            if time.time() - entry["timestamp"] < ttl:
                return entry["value"]
            else:
                del self._memory_cache[full_key]
        
        # Check file cache
        if self.enable_file_cache:
            cache_file = self.cache_dir / f"{cache_name}_cache.json"
            if cache_file.exists():
                try:
                    with open(cache_file, "r") as f:
                        file_cache = json.load(f)
                    if key in file_cache:
                        entry = file_cache[key]
                        if time.time() - entry["timestamp"] < ttl:
                            # Promote to memory cache
                            self._memory_cache[full_key] = entry
                            return entry["value"]
                except (json.JSONDecodeError, KeyError):
                    pass
        
        return None
    
    def set(
        self,
        cache_name: str,
        value: Any,
        *args,
        **kwargs
    ) -> None:
        """
        Store value in cache.
        
        Args:
            cache_name: Name of the cache
            value: Value to cache
            *args, **kwargs: Arguments used to generate cache key
        """
        key = self._generate_key(*args, **kwargs)
        full_key = f"{cache_name}:{key}"
        
        entry = {
            "value": value,
            "timestamp": time.time(),
            "created_at": datetime.now().isoformat()
        }
        
        # Store in memory
        self._memory_cache[full_key] = entry
        
        # Store in file
        if self.enable_file_cache:
            cache_file = self.cache_dir / f"{cache_name}_cache.json"
            file_cache = {}
            if cache_file.exists():
                try:
                    with open(cache_file, "r") as f:
                        file_cache = json.load(f)
                except json.JSONDecodeError:
                    pass
            
            file_cache[key] = entry
            with open(cache_file, "w") as f:
                json.dump(file_cache, f, indent=2)
    
    def clear(self, cache_name: Optional[str] = None) -> None:
        """Clear cache (all or specific cache_name)."""
        if cache_name:
            # Clear specific cache
            keys_to_remove = [k for k in self._memory_cache if k.startswith(f"{cache_name}:")]
            for k in keys_to_remove:
                del self._memory_cache[k]
            
            if self.enable_file_cache:
                cache_file = self.cache_dir / f"{cache_name}_cache.json"
                if cache_file.exists():
                    cache_file.unlink()
        else:
            # Clear all
            self._memory_cache.clear()
            if self.enable_file_cache:
                for f in self.cache_dir.glob("*_cache.json"):
                    f.unlink()
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        stats = {
            "memory_entries": len(self._memory_cache),
            "caches": {}
        }
        
        for key in self._memory_cache:
            cache_name = key.split(":")[0]
            stats["caches"][cache_name] = stats["caches"].get(cache_name, 0) + 1
        
        return stats


# Global cache instance
_cache_instance: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager()
    return _cache_instance
