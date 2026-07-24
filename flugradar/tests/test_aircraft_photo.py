"""Tests for the photo cache: planespotters (existing) + adsbdb fallback
(new) sharing one disk cache, plus the new size-capped eviction."""

import threading
import time

import pytest

import flugradar.data_sources.aircraft_photo as photo_mod


class _SyncThread:
    """Drop-in replacement for threading.Thread that runs synchronously,
    so background photo lookups become deterministic in tests."""

    def __init__(self, target=None, daemon=None):
        self._target = target

    def start(self):
        self._target()


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    cache_dir = tmp_path / "aircraft_photos"
    monkeypatch.setattr(photo_mod, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(photo_mod, "_META_PATH", cache_dir / "index.json")
    monkeypatch.setattr(photo_mod, "_meta", None)
    monkeypatch.setattr(photo_mod, "_pending", set())
    monkeypatch.setattr(photo_mod.threading, "Thread", _SyncThread)
    yield


def _fake_download_ok(url, dest):
    with open(dest, "wb") as fh:
        fh.write(b"x" * 1000)
    return True


class TestAdsbdbPhotoFallback:
    def test_downloads_and_caches_with_generic_credit(self, monkeypatch):
        monkeypatch.setattr(photo_mod, "_download_image", _fake_download_ok)
        photo_mod.request_adsbdb_photo("4b1805", "https://x/thumb.jpg", "https://x/full.jpg")

        info = photo_mod.get_photo_info("4b1805")
        assert info is not None
        assert "airport-data.com" in info["credit"]

    def test_second_call_does_not_redownload(self, monkeypatch):
        calls = []

        def counting_download(url, dest):
            calls.append(url)
            return _fake_download_ok(url, dest)

        monkeypatch.setattr(photo_mod, "_download_image", counting_download)
        photo_mod.request_adsbdb_photo("4b1805", "https://x/thumb.jpg")
        photo_mod.request_adsbdb_photo("4b1805", "https://x/thumb.jpg")

        assert len(calls) == 1

    def test_skips_when_planespotters_already_has_a_photo(self, monkeypatch, tmp_path):
        existing = tmp_path / "existing.jpg"
        existing.write_bytes(b"x" * 10)
        meta = photo_mod._load_meta()
        meta["4b1805"] = {
            "miss": False, "ts": time.time(), "hex": "4b1805",
            "path": str(existing), "credit": "Photo: Jane Doe (planespotters.net)",
            "source": "planespotters",
        }
        photo_mod._save_meta()

        calls = []
        monkeypatch.setattr(photo_mod, "_download_image", lambda u, d: calls.append(u) or True)
        photo_mod.request_adsbdb_photo("4b1805", "https://x/thumb.jpg")

        assert calls == []
        info = photo_mod.get_photo_info("4b1805")
        assert info["credit"] == "Photo: Jane Doe (planespotters.net)"

    def test_no_url_is_a_no_op(self, monkeypatch):
        calls = []
        monkeypatch.setattr(photo_mod, "_download_image", lambda u, d: calls.append(u) or True)
        photo_mod.request_adsbdb_photo("4b1805", "", "")
        assert calls == []
        assert photo_mod.get_photo_info("4b1805") is None


class TestCacheEviction:
    def test_evicts_oldest_when_over_budget(self, monkeypatch, tmp_path):
        monkeypatch.setattr(photo_mod, "_MAX_CACHE_BYTES", 1500)
        photo_mod._ensure_cache_dir()
        meta = photo_mod._load_meta()

        # Three "photos" of 1000 bytes each, oldest first.
        for i, ts in enumerate([100.0, 200.0, 300.0]):
            path = photo_mod._CACHE_DIR / f"h{i}.jpg"
            path.write_bytes(b"x" * 1000)
            meta[f"h{i}"] = {"miss": False, "ts": ts, "hex": f"h{i}", "path": str(path)}
        photo_mod._save_meta()

        photo_mod._evict_if_needed()

        meta_after = photo_mod._load_meta()
        assert "h0" not in meta_after  # oldest evicted
        assert "h2" in meta_after  # newest kept
        assert not (photo_mod._CACHE_DIR / "h0.jpg").exists()

    def test_under_budget_evicts_nothing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(photo_mod, "_MAX_CACHE_BYTES", 10_000)
        photo_mod._ensure_cache_dir()
        meta = photo_mod._load_meta()
        path = photo_mod._CACHE_DIR / "h0.jpg"
        path.write_bytes(b"x" * 100)
        meta["h0"] = {"miss": False, "ts": 100.0, "hex": "h0", "path": str(path)}
        photo_mod._save_meta()

        photo_mod._evict_if_needed()

        assert "h0" in photo_mod._load_meta()
