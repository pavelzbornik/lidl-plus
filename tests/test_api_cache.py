"""Tests for LidlPlusApi cache integration. Network is monkeypatched away."""

import lidlplus.api as api_module
from lidlplus import LidlPlusApi


class FakeResponse:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, json_data=None, text=""):
        self._json = json_data
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


def test_cache_disabled_by_default():
    api = LidlPlusApi("de", "AT")
    assert api._cache is None


def test_cache_enabled_with_flag(tmp_path):
    api = LidlPlusApi("de", "AT", cache=True, cache_dir=tmp_path)
    assert api._cache is not None
    assert api._cache.directory == tmp_path


def test_clear_cache_without_cache_is_noop():
    # must not raise when caching is disabled
    LidlPlusApi("de", "AT").clear_cache()


def test_public_endpoint_served_from_cache(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_get(_url, **_kwargs):
        calls["n"] += 1
        return FakeResponse(json_data=[{"id": "DE"}, {"id": "AT"}])

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    api = LidlPlusApi("de", "AT", cache=True, cache_dir=tmp_path)

    first = api.countries()
    second = api.countries()
    assert first == second == [{"id": "DE"}, {"id": "AT"}]
    assert calls["n"] == 1  # second call served from cache, no request


def test_without_cache_calls_api_every_time(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_get(_url, **_kwargs):
        calls["n"] += 1
        return FakeResponse(json_data=[])

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    api = LidlPlusApi("de", "AT")  # caching off

    api.countries()
    api.countries()
    assert calls["n"] == 2


def test_clear_cache_forces_refetch(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_get(_url, **_kwargs):
        calls["n"] += 1
        return FakeResponse(json_data=[])

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    api = LidlPlusApi("de", "AT", cache=True, cache_dir=tmp_path)

    api.countries()
    api.clear_cache()
    api.countries()
    assert calls["n"] == 2


def test_activating_coupon_invalidates_cached_list(tmp_path, monkeypatch):
    get_calls = {"n": 0}
    post_calls = {"n": 0}

    def fake_get(_url, **_kwargs):
        get_calls["n"] += 1
        return FakeResponse(json_data={"sections": [], "n": get_calls["n"]})

    def fake_post(_url, **_kwargs):
        post_calls["n"] += 1
        return FakeResponse(json_data={})

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    monkeypatch.setattr(api_module.requests, "post", fake_post)
    api = LidlPlusApi("de", "AT", cache=True, cache_dir=tmp_path)
    # avoid the real token/network path inside _default_headers
    monkeypatch.setattr(api, "_default_headers", lambda: {})

    first = api.coupons()
    cached_again = api.coupons()
    assert first == cached_again
    assert first["n"] == 1
    assert get_calls["n"] == 1  # second read came from cache

    api.activate_coupon("DISC123")
    assert post_calls["n"] == 1

    after = api.coupons()
    assert get_calls["n"] == 2  # cache was invalidated, so a fresh request ran
    assert after["n"] == 2
