# -*- coding: utf-8 -*-
"""Unit tests for Exa API backend following build-with-exa skill specifications."""

import json
import pytest
import requests

from agent_reach.backends.exa import (
    ExaAPIError,
    format_search_results,
    get_exa_api_key,
    search_exa,
)
from agent_reach.channels.exa_search import ExaSearchChannel
from agent_reach.config import Config


class DummyResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = json.dumps(json_data)

    def json(self):
        return self._json


def test_search_exa_raises_when_no_api_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(ExaAPIError) as exc_info:
        search_exa("python news", api_key=None, config=Config())
    assert "EXA_API_KEY is not set" in str(exc_info.value)


def test_search_exa_canonical_payload(monkeypatch):
    captured = {}

    def mock_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return DummyResponse({
            "results": [
                {
                    "title": "Exa AI Search",
                    "url": "https://exa.ai",
                    "highlights": ["Semantic search for AI agents."],
                }
            ]
        })

    monkeypatch.setattr(requests, "post", mock_post)
    result = search_exa("latest AI", api_key="test-key", num_results=3)

    assert captured["url"] == "https://api.exa.ai/search"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["json"]["query"] == "latest AI"
    assert captured["json"]["type"] == "auto"
    assert captured["json"]["contents"] == {"highlights": True}
    assert captured["json"]["numResults"] == 3
    assert len(result["results"]) == 1


def test_format_search_results():
    data = {
        "results": [
            {
                "title": "Exa AI Search",
                "url": "https://exa.ai",
                "author": "Exa Team",
                "publishedDate": "2026-10-12T00:00:00Z",
                "highlights": ["Semantic search for AI agents."],
            }
        ]
    }
    formatted = format_search_results(data)
    assert "Exa AI Search" in formatted
    assert "https://exa.ai" in formatted
    assert "Exa Team" in formatted
    assert "Semantic search for AI agents." in formatted


def test_exa_search_channel_active_with_api_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "dummy-key-123")
    ch = ExaSearchChannel()
    status, msg = ch.check()
    assert status == "ok"
    assert ch.active_backend == "Exa API"
