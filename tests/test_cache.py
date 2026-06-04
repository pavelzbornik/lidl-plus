"""Tests for the opt-in file cache (lidlplus.cache). All offline."""

import lidlplus.cache as cache_module
from lidlplus.cache import MISSING, FileCache, cached, default_cache_dir


def test_miss_then_hit(tmp_path):
    cache = FileCache(tmp_path)
    assert cache.get("k") is MISSING
    cache.set("k", {"a": 1}, ttl=60)
    assert cache.get("k") == {"a": 1}


def test_permanent_entry_never_expires(tmp_path, monkeypatch):
    cache = FileCache(tmp_path)
    cache.set("perm", [1, 2, 3], ttl=None)
    # Jump far into the future; a ttl=None entry must still be served.
    monkeypatch.setattr(cache_module.time, "time", lambda: 10**12)
    assert cache.get("perm") == [1, 2, 3]


def test_entry_expires_after_ttl(tmp_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(cache_module.time, "time", lambda: now[0])
    cache = FileCache(tmp_path)
    cache.set("short", "v", ttl=10)
    assert cache.get("short") == "v"
    now[0] += 11
    assert cache.get("short") is MISSING


def test_delete_is_idempotent(tmp_path):
    cache = FileCache(tmp_path)
    cache.set("x", 1, ttl=60)
    cache.delete("x")
    assert cache.get("x") is MISSING
    cache.delete("x")  # deleting a missing key must not raise


def test_clear_removes_all_entries(tmp_path):
    cache = FileCache(tmp_path)
    cache.set("a", 1, ttl=60)
    cache.set("b", 2, ttl=None)
    cache.clear()
    assert cache.get("a") is MISSING
    assert cache.get("b") is MISSING


def test_clear_on_empty_dir_is_noop(tmp_path):
    # directory created lazily on first write; clearing before that must be safe
    FileCache(tmp_path / "missing").clear()


def test_corrupt_file_treated_as_miss(tmp_path):
    cache = FileCache(tmp_path)
    cache.set("k", {"a": 1}, ttl=60)
    cache._path("k").write_text("not valid json", encoding="utf-8")
    assert cache.get("k") is MISSING


def test_cached_runs_producer_once_then_serves_cache(tmp_path):
    cache = FileCache(tmp_path)
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return {"served": calls["n"]}

    first = cached(cache, "key", 60, producer)
    second = cached(cache, "key", 60, producer)
    assert first == second == {"served": 1}
    assert calls["n"] == 1


def test_cached_passthrough_when_cache_disabled():
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return calls["n"]

    assert cached(None, "key", 60, producer) == 1
    assert cached(None, "key", 60, producer) == 2
    assert calls["n"] == 2


def test_default_cache_dir_named_for_package():
    assert default_cache_dir().name == "lidl-plus"
