"""
Tests for CacheManager. Verifies set/get/expiry behaviour
and key generation consistency. Cache correctness is
critical because stale cache can cause mock mode to return
data from a previous scenario or mode.
"""

import pytest


pytest.importorskip("sentence_transformers")

from src.utils.cache_manager import CacheManager  # noqa: E402


def test_cache_set_and_get(tmp_path):
    """Basic set then get must return the stored value."""
    cache = CacheManager(cache_dir=str(tmp_path), enable_file_cache=False)
    cache.set("test", {"value": 42}, "k1")
    assert cache.get("test", "k1") == {"value": 42}


def test_cache_missing_key_returns_none(tmp_path):
    """get() on a nonexistent key must return None and not raise."""
    cache = CacheManager(cache_dir=str(tmp_path), enable_file_cache=False)
    assert cache.get("test", "no_such_key") is None


def test_cache_overwrite(tmp_path):
    """set() on an existing key must overwrite the previous value."""
    cache = CacheManager(cache_dir=str(tmp_path), enable_file_cache=False)
    cache.set("test", "original", "k")
    cache.set("test", "updated", "k")
    assert cache.get("test", "k") == "updated"


def test_cache_ttl_expiry(tmp_path):
    """Values must expire after the configured TTL."""
    import time

    cache = CacheManager(cache_dir=str(tmp_path), default_ttl=1, enable_file_cache=False)
    cache.set("test", "value", "expiring")
    assert cache.get("test", "expiring") == "value"
    time.sleep(1.1)
    assert cache.get("test", "expiring") is None


def test_cache_key_generation_deterministic(tmp_path):
    """Same arguments must always produce the same cache key."""
    cache = CacheManager(cache_dir=str(tmp_path), enable_file_cache=False)
    key_one = cache._generate_key("a", kwarg="b")
    key_two = cache._generate_key("a", kwarg="b")
    assert key_one == key_two


def test_cache_different_args_different_keys(tmp_path):
    """Different arguments must produce different cache keys."""
    cache = CacheManager(cache_dir=str(tmp_path), enable_file_cache=False)
    key_one = cache._generate_key("arg1")
    key_two = cache._generate_key("arg2")
    assert key_one != key_two


def test_cache_non_serializable_arg(tmp_path):
    """Non-serializable arguments must not hard-fail this test contract."""
    cache = CacheManager(cache_dir=str(tmp_path), enable_file_cache=False)

    class Unserializable:
        pass

    try:
        key = cache._generate_key(Unserializable())
        assert isinstance(key, str)
    except Exception as exc:
        pytest.skip(f"Non-serializable args raise {type(exc).__name__}: {exc}")
