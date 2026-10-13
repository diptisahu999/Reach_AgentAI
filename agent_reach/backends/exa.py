# -*- coding: utf-8 -*-
"""Exa API Search Client — canonical implementation following build-with-exa skill.

Use case: Web search tool
Primary endpoint: POST https://api.exa.ai/search
Recommended request shape:
  {
    "query": query,
    "type": "auto",
    "contents": {
      "highlights": True
    }
  }
"""

import os
from typing import Any, Dict, List, Optional
import requests

from agent_reach.config import Config

EXA_SEARCH_ENDPOINT = "https://api.exa.ai/search"
EXA_ANSWER_ENDPOINT = "https://api.exa.ai/answer"



class ExaAPIError(Exception):
    """Raised when the Exa API call fails."""
    pass


def get_exa_api_key(config: Optional[Config] = None) -> Optional[str]:
    """Retrieve Exa API key from environment variable or agent-reach config."""
    # 1. Environment variable (preferred by coding tools)
    api_key = os.environ.get("EXA_API_KEY")
    if api_key and api_key.strip():
        return api_key.strip()

    # 2. Agent Reach config / .env
    cfg = config or Config()
    key_from_cfg = cfg.get("exa_api_key")
    if key_from_cfg and str(key_from_cfg).strip():
        return str(key_from_cfg).strip()

    return None


def search_exa(
    query: str,
    api_key: Optional[str] = None,
    num_results: Optional[int] = None,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    config: Optional[Config] = None,
    timeout: int = 20,
) -> Dict[str, Any]:
    """Execute a semantic web search using the canonical Exa /search endpoint.

    Follows build-with-exa skill guidelines:
    - Default type is 'auto'
    - Nested contents with highlights: True
    - Unnecessary filters/parameters are avoided unless explicitly requested.
    """
    key = api_key or get_exa_api_key(config)
    if not key:
        raise ExaAPIError(
            "EXA_API_KEY is not set. Please set EXA_API_KEY in your environment, "
            ".env file, or run 'agent-reach configure exa-key <YOUR_KEY>'."
        )

    headers = {
        "x-api-key": key,
        "Content-Type": "application/json",
        "User-Agent": "agent-reach/1.5.0",
    }

    # Canonical recommended payload: type="auto" and contents={"highlights": True}
    payload: Dict[str, Any] = {
        "query": query,
        "type": "auto",
        "contents": {
            "highlights": True,
        },
    }

    if num_results is not None:
        payload["numResults"] = num_results
    if include_domains:
        payload["includeDomains"] = include_domains
    if exclude_domains:
        payload["excludeDomains"] = exclude_domains

    try:
        response = requests.post(
            EXA_SEARCH_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise ExaAPIError(f"Network error connecting to Exa API: {e}") from e

    if response.status_code == 401:
        raise ExaAPIError("Authentication failed: Invalid EXA_API_KEY provided.")
    if response.status_code == 429:
        raise ExaAPIError("Exa API rate limit reached.")
    if not response.ok:
        try:
            err_data = response.json()
            err_msg = err_data.get("error", response.text)
        except Exception:
            err_msg = response.text
        raise ExaAPIError(f"Exa API error ({response.status_code}): {err_msg}")

    return response.json()


def format_search_results(data: Dict[str, Any]) -> str:
    """Format search results nicely for CLI and agent display."""
    results = data.get("results", [])
    if not results:
        return "未找到相关结果。"

    lines = []
    lines.append(f"共找到 {len(results)} 条结果：\n")
    for idx, item in enumerate(results, 1):
        title = item.get("title") or "无标题"
        url = item.get("url", "")
        author = item.get("author")
        pub_date = item.get("publishedDate")
        highlights = item.get("highlights", [])

        meta_parts = []
        if author:
            meta_parts.append(f"作者: {author}")
        if pub_date:
            meta_parts.append(f"日期: {pub_date[:10]}")
        meta_str = f" ({', '.join(meta_parts)})" if meta_parts else ""

        lines.append(f"{idx}. [{title}]({url}){meta_str}")
        if highlights:
            for h in highlights:
                # Indent highlights as quotes
                clean_h = " ".join(h.split())
                lines.append(f"   > {clean_h}")
        lines.append("")

    return "\n".join(lines).strip()


def answer_exa(
    query: str,
    api_key: Optional[str] = None,
    config: Optional[Config] = None,
    timeout: int = 35,
) -> Dict[str, Any]:
    """Generate a synthesized, grounded answer with citations using Exa's built-in LLM."""
    key = api_key or get_exa_api_key(config)
    if not key:
        raise ExaAPIError(
            "EXA_API_KEY is not set. Please set EXA_API_KEY in your environment or .env."
        )

    headers = {
        "x-api-key": key,
        "Content-Type": "application/json",
        "User-Agent": "agent-reach/1.5.0",
    }
    payload = {"query": query}

    try:
        response = requests.post(
            EXA_ANSWER_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise ExaAPIError(f"Network error connecting to Exa Answer API: {e}") from e

    if response.status_code == 401:
        raise ExaAPIError("Authentication failed: Invalid EXA_API_KEY provided.")
    if response.status_code == 429:
        raise ExaAPIError("Exa API rate limit reached.")
    if not response.ok:
        try:
            err_data = response.json()
            err_msg = err_data.get("error", response.text)
        except Exception:
            err_msg = response.text
        raise ExaAPIError(f"Exa Answer API error ({response.status_code}): {err_msg}")

    return response.json()

