# -*- coding: utf-8 -*-
"""FastAPI Backend Server for Agent Reach ChatGPT-style UI."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_reach.backends.exa import ExaAPIError, get_exa_api_key, search_exa
from agent_reach.backends.youtube import fetch_youtube_content, is_youtube_url
from agent_reach.config import Config
from agent_reach.doctor import check_all

UI_DIR = Path(__file__).resolve().parent
ROOT_DIR = UI_DIR.parent
ENV_FILE = ROOT_DIR / ".env"


def _reload_env():
    """Ensure environment variables from .env file are loaded/updated."""
    try:
        from dotenv import load_dotenv

        if ENV_FILE.exists():
            load_dotenv(ENV_FILE, override=True)
    except Exception:
        pass


_reload_env()

app = FastAPI(
    title="Agent Reach AI Web Interface",
    description="ChatGPT-style Web interface for Agent Reach internet searching & reading",
    version="1.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str
    num_results: Optional[int] = 5


class SourceItem(BaseModel):
    title: str
    url: str
    author: Optional[str] = None
    publishedDate: Optional[str] = None
    highlights: List[str] = []


class ChatResponse(BaseModel):
    query: str
    type: str  # "search" or "url_read"
    summary: str
    sources: List[SourceItem] = []
    metadata: Dict[str, Any] = {}


@app.get("/api/status")
def get_system_status():
    """Return health check and status of Agent Reach channels."""
    _reload_env()
    config = Config()
    results = check_all(config)
    exa_configured = bool(get_exa_api_key(config))

    return {
        "exa_configured": exa_configured,
        "channels": results,
    }


def _extract_first_url(text: str) -> Optional[str]:
    """Extract a http/https URL if present in the text."""
    url_pattern = r"https?://[^\s<>\"'()]+"
    match = re.search(url_pattern, text)
    return match.group(0) if match else None


def _read_url_via_jina(url: str, timeout: int = 15) -> str:
    """Read and clean webpage content using Jina Reader."""
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "User-Agent": "agent-reach/1.5.0",
        "Accept": "text/markdown, text/plain, */*",
    }
    response = requests.get(jina_url, headers=headers, timeout=timeout)
    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Jina Reader could not fetch the URL: {response.text[:200]}",
        )
    return response.text


@app.post("/api/chat", response_model=ChatResponse)
def handle_chat_query(req: QueryRequest):
    """Handle search or web page read query."""
    raw_query = req.query.strip()
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    first_url = _extract_first_url(raw_query)

    # 1. Specialized YouTube video extraction via yt-dlp
    if first_url and is_youtube_url(first_url):
        try:
            yt_data = fetch_youtube_content(first_url)
            return ChatResponse(
                query=raw_query,
                type="youtube_video",
                summary=yt_data["summary"],
                sources=[
                    SourceItem(
                        title=s["title"],
                        url=s["url"],
                        author=s.get("author"),
                        publishedDate=s.get("publishedDate"),
                        highlights=s.get("highlights", []),
                    )
                    for s in yt_data.get("sources", [])
                ],
                metadata=yt_data.get("metadata", {}),
            )
        except Exception as e:
            return ChatResponse(
                query=raw_query,
                type="youtube_video",
                summary=(
                    f"### ⚠️ Could Not Extract YouTube Video\n\n"
                    f"**URL:** {first_url}\n\n"
                    f"**Error Details:** {str(e)}\n\n"
                    f"💡 *Tip: Ensure yt-dlp is updated: `python -m pip install -U \"yt-dlp[default]\"`*"
                ),
                sources=[
                    SourceItem(
                        title=f"YouTube Video - {first_url}",
                        url=first_url,
                        highlights=[str(e)[:200]],
                    )
                ],
                metadata={"error": True, "details": str(e), "url": first_url},
            )

    # 2. If the user input is primarily a generic URL, fetch the page directly via Jina Reader
    if first_url and (raw_query == first_url or raw_query.startswith("read ") or raw_query.startswith("http")):
        try:
            markdown_content = _read_url_via_jina(first_url)

            # Check for target site anti-bot / authorization error notices in Jina output
            error_match = re.search(
                r"Warning:\s*Target URL returned error\s*(\d{3}):\s*([^\n\r]+)",
                markdown_content,
                re.IGNORECASE,
            )
            if error_match:
                status_code, err_msg = error_match.groups()
                clean_err_notice = (
                    f"### ⚠️ Could Not Read Webpage ({status_code} {err_msg.strip()})\n\n"
                    f"The target website at [{first_url}]({first_url}) returned an access restriction.\n\n"
                    f"- **URL:** `{first_url}`\n"
                    f"- **Status:** `{status_code} {err_msg.strip()}`\n\n"
                    f"💡 *Tip: For platforms requiring authentication, use dedicated platform CLI or configure cookies.*"
                )
                return ChatResponse(
                    query=raw_query,
                    type="url_read",
                    summary=clean_err_notice,
                    sources=[
                        SourceItem(
                            title=f"Access Denied ({status_code}) - {first_url}",
                            url=first_url,
                            highlights=[f"Target site returned error {status_code}: {err_msg.strip()}"],
                        )
                    ],
                    metadata={"error": True, "status_code": status_code, "url": first_url},
                )

            # Truncate preview if extremely large
            preview = markdown_content[:5000] if len(markdown_content) > 5000 else markdown_content
            return ChatResponse(
                query=raw_query,
                type="url_read",
                summary=preview,
                sources=[
                    SourceItem(
                        title=f"Extracted page content from {first_url}",
                        url=first_url,
                        highlights=[markdown_content[:280].strip() + "..."],
                    )
                ],
                metadata={"total_characters": len(markdown_content), "url": first_url},
            )
        except Exception as e:
            # Fall back to search if URL read fails
            pass

    # Perform Exa Semantic Search
    _reload_env()
    try:
        data = search_exa(query=raw_query, num_results=req.num_results or 5)
    except ExaAPIError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    results = data.get("results", [])
    sources_list: List[SourceItem] = []
    synthesis_lines: List[str] = []

    for idx, item in enumerate(results, 1):
        title = item.get("title") or "Untitled Document"
        url = item.get("url", "")
        author = item.get("author")
        pub_date = item.get("publishedDate")
        highlights = item.get("highlights", [])

        sources_list.append(
            SourceItem(
                title=title,
                url=url,
                author=author,
                publishedDate=pub_date,
                highlights=highlights,
            )
        )

        # Build clean synthesized insight lines
        meta_info = []
        if author:
            meta_info.append(author)
        if pub_date:
            meta_info.append(pub_date[:10])
        meta_str = f" *({', '.join(meta_info)})*" if meta_info else ""

        synthesis_lines.append(f"### [{idx}] [{title}]({url}){meta_str}\n")
        if highlights:
            for h in highlights:
                clean_h = " ".join(h.split())
                # Strip leading or embedded markdown heading markers (e.g. '# ', '## ') so quotes don't become giant headings
                clean_h = re.sub(r"(^|\s)#+\s+", r"\1", clean_h).strip()
                synthesis_lines.append(f"> {clean_h}\n")
        else:
            synthesis_lines.append("> *(No highlighted snippet provided by source)*\n")

    summary_text = (
        f"Retrieved **{len(results)} high-signal sources** for **\"{raw_query}\"**:\n\n"
        + "\n".join(synthesis_lines)
    )

    return ChatResponse(
        query=raw_query,
        type="search",
        summary=summary_text,
        sources=sources_list,
        metadata={"count": len(results)},
    )


# Serve static assets
if (UI_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(UI_DIR / "static")), name="static")


@app.get("/")
def serve_index():
    index_file = UI_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>UI files not found</h1>", status_code=404)
    return FileResponse(str(index_file))


def start_server(host: str = "127.0.0.1", port: int = 8000):
    print(f"Starting Agent Reach Web UI on http://{host}:{port} ...")
    uvicorn.run("ui.server:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    start_server()
