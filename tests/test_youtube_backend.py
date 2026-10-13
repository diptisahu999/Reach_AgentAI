# -*- coding: utf-8 -*-
"""Unit tests for YouTube backend extraction and UI server routing."""

import pytest
from fastapi.testclient import TestClient

from agent_reach.backends.youtube import (
    extract_youtube_info,
    fetch_youtube_content,
    format_youtube_markdown,
    is_youtube_url,
)
from ui.server import app, QueryRequest, handle_chat_query


def test_is_youtube_url():
    assert is_youtube_url("https://www.youtube.com/watch?v=jG9aLEawV7Y")
    assert is_youtube_url("https://youtu.be/jG9aLEawV7Y")
    assert is_youtube_url("https://www.youtube.com/watch?v=Jis04VOZyEU&list=RD2qrWc2d_MVo&index=11")
    assert is_youtube_url("https://m.youtube.com/shorts/abc123xyz")
    assert not is_youtube_url("https://example.com/video")
    assert not is_youtube_url("https://youtube.com.attacker.com/watch")
    assert not is_youtube_url("")


def test_format_youtube_markdown_video():
    info = {
        "id": "jG9aLEawV7Y",
        "title": "21 AI Tools That Will Make You Rich Before 2026",
        "uploader": "Zeeshan Shaikh",
        "uploader_url": "https://www.youtube.com/@ZeeshanShaikh",
        "duration_string": "29:01",
        "view_count": 888238,
        "like_count": 27073,
        "upload_date": "20250917",
        "thumbnail": "https://i.ytimg.com/vi/jG9aLEawV7Y/maxresdefault.jpg",
        "webpage_url": "https://www.youtube.com/watch?v=jG9aLEawV7Y",
        "description": "21 powerful AI tools to save time and boost productivity.",
        "chapters": [
            {"start_time": 0, "title": "Intro"},
            {"start_time": 120, "title": "Category 1"},
        ],
        "tags": ["ai", "productivity"],
        "categories": ["Education"],
    }

    md = format_youtube_markdown(info)
    assert "21 AI Tools That Will Make You Rich Before 2026" in md
    assert "Zeeshan Shaikh" in md
    assert "29:01" in md
    assert "888,238" in md
    assert "27,073" in md
    assert "2025-09-17" in md
    assert "Intro" in md
    assert "Category 1" in md
    assert "https://i.ytimg.com/vi/jG9aLEawV7Y/maxresdefault.jpg" in md


def test_format_youtube_markdown_playlist():
    info = {
        "_type": "playlist",
        "title": "Top Tech Talks",
        "uploader": "Tech Org",
        "entries": [
            {"title": "Talk 1", "webpage_url": "https://www.youtube.com/watch?v=1", "duration_string": "15:00"},
            {"title": "Talk 2", "webpage_url": "https://www.youtube.com/watch?v=2", "duration_string": "20:00"},
        ],
    }

    md = format_youtube_markdown(info, original_url="https://www.youtube.com/playlist?list=123")
    assert "Top Tech Talks" in md
    assert "Talk 1" in md
    assert "Talk 2" in md
    assert "Total Items" in md


def test_fetch_youtube_content_mock(monkeypatch):
    mock_info = {
        "id": "abc123",
        "title": "Mock Video Title",
        "uploader": "Mock Channel",
        "duration_string": "10:00",
        "view_count": 1000,
        "like_count": 100,
        "upload_date": "20260101",
        "description": "Mock video description.",
        "webpage_url": "https://www.youtube.com/watch?v=abc123",
    }
    monkeypatch.setattr(
        "agent_reach.backends.youtube.extract_youtube_info",
        lambda url, timeout=25: mock_info,
    )

    data = fetch_youtube_content("https://www.youtube.com/watch?v=abc123")
    assert data["title"] == "Mock Video Title"
    assert data["channel"] == "Mock Channel"
    assert data["duration"] == "10:00"
    assert "Mock Video Title" in data["summary"]
    assert len(data["sources"]) == 1
    assert data["metadata"]["platform"] == "youtube"


def test_ui_server_handles_youtube_url(monkeypatch):
    client = TestClient(app)

    mock_info = {
        "id": "jG9aLEawV7Y",
        "title": "21 AI Tools Video",
        "uploader": "Zeeshan Shaikh",
        "duration_string": "29:01",
        "view_count": 50000,
        "like_count": 2500,
        "upload_date": "20250917",
        "description": "Here are 21 AI tools.",
        "webpage_url": "https://www.youtube.com/watch?v=jG9aLEawV7Y",
    }
    monkeypatch.setattr(
        "agent_reach.backends.youtube.extract_youtube_info",
        lambda url, timeout=25: mock_info,
    )

    resp = client.post(
        "/api/chat",
        json={"query": "https://www.youtube.com/watch?v=jG9aLEawV7Y"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "youtube_video"
    assert "21 AI Tools Video" in data["summary"]
    assert data["metadata"]["duration"] == "29:01"
    assert data["metadata"]["channel"] == "Zeeshan Shaikh"
