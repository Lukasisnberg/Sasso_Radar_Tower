"""Tests for the Tomorrow.io weather client."""

import time
from unittest.mock import MagicMock, patch

import pytest

from flugradar.data_sources.weather import DailyForecast, WeatherClient, WeatherData, _WEATHER_CODES


class TestWeatherData:
    def test_temperature_str(self):
        w = WeatherData(temperature_c=21.7)
        assert w.temperature_str() == "22°C"

    def test_temperature_str_negative(self):
        w = WeatherData(temperature_c=-3.2)
        assert w.temperature_str() == "-3°C"

    def test_temperature_str_fahrenheit(self):
        w = WeatherData(temperature_c=0.0)
        assert w.temperature_str("f") == "32°F"

    def test_temperature_str_fahrenheit_rounding(self):
        w = WeatherData(temperature_c=21.7)
        assert w.temperature_str("f") == "71°F"

    def test_wind_str(self):
        w = WeatherData(temperature_c=20, wind_speed_ms=5.14)
        assert "10kt" in w.wind_str

    def test_wind_str_none(self):
        w = WeatherData(temperature_c=20)
        assert w.wind_str == ""

    def test_condition_from_code(self):
        w = WeatherData(temperature_c=15, weather_code=1000, condition="Clear")
        assert w.condition == "Clear"


class TestWeatherClient:
    _SAMPLE_RESPONSE = {
        "data": {
            "time": "2025-01-15T12:00:00Z",
            "values": {
                "temperature": 18.5,
                "humidity": 65,
                "windSpeed": 3.2,
                "windDirection": 220,
                "weatherCode": 1101,
                "visibility": 10,
                "pressureSeaLevel": 1013.25,
                "cloudCover": 40,
            },
        }
    }

    def test_parse(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        result = client._parse(self._SAMPLE_RESPONSE)
        assert result.temperature_c == 18.5
        assert result.humidity == 65
        assert result.wind_speed_ms == 3.2
        assert result.condition == "Partly Cloudy"
        assert result.pressure_hpa == 1013.25
        assert result.cloud_cover_pct == 40
        client.close()

    def test_parse_missing_values(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        result = client._parse({"data": {"values": {"temperature": 5}}})
        assert result.temperature_c == 5
        assert result.humidity is None
        assert result.condition == ""
        client.close()

    @patch("flugradar.data_sources.weather.requests.Session")
    def test_fetch_and_cache(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._SAMPLE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = WeatherClient("test-key", 47.0, 8.0, cache_ttl_s=300)

        result = client.get_weather()
        assert result is not None
        assert result.temperature_c == 18.5

        result2 = client.get_weather()
        assert result2 is result
        assert mock_session.get.call_count == 1

        client.close()

    @patch("flugradar.data_sources.weather.requests.Session")
    def test_fetch_failure_returns_cached(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._SAMPLE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = WeatherClient("test-key", 47.0, 8.0, cache_ttl_s=0.01)
        first = client.get_weather()
        assert first is not None

        mock_session.get.side_effect = ConnectionError("offline")
        time.sleep(0.02)
        second = client.get_weather()
        assert second is first

        client.close()

    def test_no_data_returns_none(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        assert client._cache is None
        assert client.get_weather() is None
        client.close()


class TestDailyForecast:
    def test_temp_range_str(self):
        f = DailyForecast(date="2026-07-26", temp_min_c=10.4, temp_max_c=22.6)
        assert f.temp_range_str() == "10° / 23°C"

    def test_temp_range_str_fahrenheit(self):
        f = DailyForecast(date="2026-07-26", temp_min_c=0.0, temp_max_c=10.0)
        assert f.temp_range_str("f") == "32° / 50°F"


class TestWeatherClientForecast:
    _SAMPLE_FORECAST = {
        "timelines": {
            "daily": [
                {
                    "time": "2026-07-25T12:00:00Z",
                    "values": {
                        "temperatureMin": 14.2,
                        "temperatureMax": 26.8,
                        "weatherCodeMax": 1101,
                    },
                },
                {
                    "time": "2026-07-26T12:00:00Z",
                    "values": {
                        "temperatureMin": 15.0,
                        "temperatureMax": 28.0,
                        "weatherCodeMax": 4001,
                    },
                },
                {
                    "time": "2026-07-27T12:00:00Z",
                    "values": {
                        "temperatureMin": 13.5,
                        "temperatureMax": 24.0,
                        "weatherCodeMax": 8000,
                    },
                },
                {
                    "time": "2026-07-28T12:00:00Z",
                    "values": {"temperatureMin": 12.0, "temperatureMax": 20.0},
                },
            ],
        }
    }

    def test_parse_forecast(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        result = client._parse_forecast(self._SAMPLE_FORECAST, days=3)
        assert len(result) == 3
        assert result[0].date == "2026-07-25"
        assert result[0].temp_min_c == 14.2
        assert result[0].temp_max_c == 26.8
        assert result[0].condition == "Partly Cloudy"
        assert result[1].condition == "Rain"
        assert result[2].condition == "Thunderstorm"
        client.close()

    def test_parse_forecast_respects_days_limit(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        result = client._parse_forecast(self._SAMPLE_FORECAST, days=1)
        assert len(result) == 1
        client.close()

    def test_parse_forecast_missing_code(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        result = client._parse_forecast(self._SAMPLE_FORECAST, days=4)
        assert result[3].weather_code is None
        assert result[3].condition == ""
        client.close()

    def test_parse_forecast_empty_timelines(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        assert client._parse_forecast({}, days=3) == []
        client.close()

    @patch("flugradar.data_sources.weather.requests.Session")
    def test_fetch_and_cache_forecast(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._SAMPLE_FORECAST
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = WeatherClient("test-key", 47.0, 8.0, forecast_cache_ttl_s=300)

        result = client.get_forecast(days=3)
        assert len(result) == 3

        result2 = client.get_forecast(days=3)
        assert result2 == result
        assert mock_session.get.call_count == 1

        client.close()

    @patch("flugradar.data_sources.weather.requests.Session")
    def test_forecast_fetch_failure_returns_cached(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._SAMPLE_FORECAST
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = WeatherClient("test-key", 47.0, 8.0, forecast_cache_ttl_s=0.01)
        first = client.get_forecast(days=3)
        assert first

        mock_session.get.side_effect = ConnectionError("offline")
        time.sleep(0.02)
        second = client.get_forecast(days=3)
        assert second == first

        client.close()

    def test_no_forecast_returns_empty_list(self):
        client = WeatherClient("test-key", 47.0, 8.0)
        assert client.get_forecast() == []
        client.close()


class TestWeatherCodes:
    def test_known_codes(self):
        assert _WEATHER_CODES[1000] == "Clear"
        assert _WEATHER_CODES[8000] == "Thunderstorm"
        assert _WEATHER_CODES[5000] == "Snow"

    def test_all_codes_are_strings(self):
        for code, label in _WEATHER_CODES.items():
            assert isinstance(code, int)
            assert isinstance(label, str)
            assert len(label) > 0
