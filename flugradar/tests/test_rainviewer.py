"""Unit tests for the RainViewer frame-index client. All requests mocked."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from flugradar.maps.rainviewer import RainViewerClient

_SAMPLE_RESPONSE = {
    "version": "2.0",
    "generated": 1784930400,
    "host": "https://tilecache.rainviewer.com",
    "radar": {
        "past": [
            {"time": 1784929500, "path": "/v2/radar/aaa111"},
            {"time": 1784930400, "path": "/v2/radar/bbb222"},
        ],
        "nowcast": [],
    },
}


def _resp(json_data=None, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(str(status_code))
    return resp


class TestLatestFramePath:
    def test_resolves_latest_past_frame(self):
        client = RainViewerClient()
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(_SAMPLE_RESPONSE)
            path = client.latest_frame_path()

        assert path == "https://tilecache.rainviewer.com/v2/radar/bbb222"
        client.close()

    def test_uses_the_last_entry_not_the_first(self):
        client = RainViewerClient()
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(_SAMPLE_RESPONSE)
            path = client.latest_frame_path()
        assert "bbb222" in path
        assert "aaa111" not in path
        client.close()

    def test_never_fetched_and_request_fails_returns_empty(self):
        client = RainViewerClient()
        with patch.object(client, "_session") as mock_session:
            mock_session.get.side_effect = requests.ConnectionError("offline")
            path = client.latest_frame_path()
        assert path == ""
        client.close()


class TestCaching:
    def test_second_call_within_ttl_does_not_refetch(self):
        client = RainViewerClient(ttl_s=300.0)
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(_SAMPLE_RESPONSE)
            client.latest_frame_path()
            client.latest_frame_path()
        assert mock_session.get.call_count == 1
        client.close()

    def test_refetches_after_ttl_expires(self):
        client = RainViewerClient(ttl_s=0.01)
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(_SAMPLE_RESPONSE)
            client.latest_frame_path()
            time.sleep(0.02)
            client.latest_frame_path()
        assert mock_session.get.call_count == 2
        client.close()

    def test_first_call_always_fetches_even_though_monotonic_epoch_is_small(self):
        """Regression test: time.monotonic()'s epoch is unspecified and can
        itself be a small number early in a process's life, so a naive
        `0.0` "never fetched" sentinel can make the very first call look
        artificially fresh and skip fetching entirely."""
        client = RainViewerClient(ttl_s=300.0)
        with patch("flugradar.maps.rainviewer.time.monotonic", return_value=100.0):
            with patch.object(client, "_session") as mock_session:
                mock_session.get.return_value = _resp(_SAMPLE_RESPONSE)
                path = client.latest_frame_path()
        assert mock_session.get.call_count == 1
        assert path != ""

    def test_network_failure_keeps_last_known_frame(self):
        client = RainViewerClient(ttl_s=0.01)
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(_SAMPLE_RESPONSE)
            first = client.latest_frame_path()
            assert first != ""

            time.sleep(0.02)
            mock_session.get.side_effect = requests.ConnectionError("offline")
            second = client.latest_frame_path()

        assert second == first  # stale-but-good, not wiped by the failed refresh
        client.close()


class TestFrameChanged:
    def test_detects_change(self):
        client = RainViewerClient()
        with patch.object(client, "_session") as mock_session:
            mock_session.get.return_value = _resp(_SAMPLE_RESPONSE)
            current = client.latest_frame_path()
        assert client.frame_changed_since("something-else") is True
        assert client.frame_changed_since(current) is False
        client.close()
