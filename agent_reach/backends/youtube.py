# -*- coding: utf-8 -*-
"""YouTube extraction backend for Agent Reach.

Extracts structured metadata, description, chapters, and available subtitle
information for YouTube video URLs using yt-dlp.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from agent_reach.utils.url import host_matches

logger = logging.getLogger(__name__)


def is_youtube_url(url: str) -> bool:
    """Return True if the URL points to YouTube or youtu.be."""
    if not url:
        return False
    return host_matches(url, "youtube.com", "youtu.be")


def extract_youtube_info(url: str, timeout: int = 25) -> Dict[str, Any]:
    """Extract YouTube video or playlist metadata via yt-dlp.

    First tries the python yt_dlp library directly. If unavailable or fails,
    falls back to calling the yt-dlp CLI via subprocess.
    """
    # 1. Try python library
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return info
    except Exception as exc:
        logger.debug(f"yt_dlp python module extraction failed: {exc}")

    # 2. Try CLI subprocess fallback
    yt_dlp_cmd = shutil.which("yt-dlp")
    if yt_dlp_cmd:
        try:
            proc = subprocess.run(
                [
                    yt_dlp_cmd,
                    "--dump-json",
                    "--no-playlist",
                    "--no-warnings",
                    "--skip-download",
                    url,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return json.loads(proc.stdout.strip().splitlines()[0])
        except Exception as exc:
            logger.debug(f"yt-dlp subprocess extraction failed: {exc}")

    raise RuntimeError(
        "Could not extract YouTube video info using yt-dlp. "
        "Please ensure yt-dlp is installed: python -m pip install -U \"yt-dlp[default]\""
    )


def format_youtube_markdown(info: Dict[str, Any], original_url: str = "") -> str:
    """Format extracted YouTube metadata into clean, high-signal Markdown."""
    is_playlist = info.get("_type") == "playlist" or ("entries" in info and not info.get("id"))
    
    if is_playlist:
        playlist_title = info.get("title") or "YouTube Playlist"
        uploader = info.get("uploader") or info.get("channel") or "Unknown"
        entries = [e for e in info.get("entries") or [] if isinstance(e, dict)]
        
        lines = [
            f"## 📋 [{playlist_title}]({original_url})",
            "",
            f"- **Channel / Curator:** **{uploader}**",
            f"- **Total Items:** `{len(entries)}`",
            "",
            "### 🎬 Videos in Playlist:",
        ]
        for idx, entry in enumerate(entries[:25], 1):
            title = entry.get("title") or "Untitled Video"
            url = entry.get("webpage_url") or entry.get("url") or ""
            dur = entry.get("duration_string") or ""
            dur_str = f" `({dur})`" if dur else ""
            if url:
                lines.append(f"{idx}. [{title}]({url}){dur_str}")
            else:
                lines.append(f"{idx}. {title}{dur_str}")
        return "\n".join(lines)

    title = info.get("title") or "YouTube Video"
    uploader = info.get("uploader") or info.get("channel") or "Unknown"
    uploader_url = info.get("uploader_url") or info.get("channel_url") or ""
    duration = info.get("duration_string") or "N/A"
    
    views = info.get("view_count")
    views_str = f"{views:,}" if isinstance(views, (int, float)) else "N/A"
    likes = info.get("like_count")
    likes_str = f"{likes:,}" if isinstance(likes, (int, float)) else "N/A"
    
    upload_date = info.get("upload_date")
    if upload_date and len(str(upload_date)) == 8:
        d = str(upload_date)
        upload_date_str = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    else:
        upload_date_str = str(upload_date or "N/A")

    webpage_url = info.get("webpage_url") or info.get("original_url") or original_url
    thumbnail = info.get("thumbnail")
    description = (info.get("description") or "").strip()
    chapters = info.get("chapters") or []
    tags = info.get("tags") or []
    categories = info.get("categories") or []

    lines: List[str] = [
        f"## 📺 [{title}]({webpage_url})",
        "",
    ]

    ch_link = f"[{uploader}]({uploader_url})" if uploader_url else f"**{uploader}**"
    lines.append(f"- **Channel / Creator:** {ch_link}")
    lines.append(f"- **Duration:** `{duration}`  |  **Published Date:** `{upload_date_str}`")
    lines.append(f"- **Views:** `{views_str}`  |  **Likes:** `{likes_str}`")
    
    if categories:
        lines.append(f"- **Category:** {', '.join(categories)}")

    lines.append("")

    if thumbnail:
        lines.append(f"[![Video Thumbnail]({thumbnail})]({webpage_url})")
        lines.append("")

    if chapters:
        lines.append("### ⏱️ Video Chapters")
        for ch in chapters[:25]:
            start = ch.get("start_time", 0)
            mins = int(start // 60)
            secs = int(start % 60)
            ch_title = ch.get("title") or "Chapter"
            lines.append(f"- **`{mins:02d}:{secs:02d}`** — {ch_title}")
        lines.append("")

    if description:
        lines.append("### 📝 Video Description")
        desc_preview = description[:2500]
        if len(description) > 2500:
            desc_preview += "\n\n*(Description truncated for preview)*"
        lines.append(desc_preview)
        lines.append("")

    if tags and len(tags) > 0:
        clean_tags = [f"`#{t}`" for t in tags[:12]]
        lines.append(f"**Tags:** {' '.join(clean_tags)}")
        lines.append("")

    subtitles = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    available_sub_langs: List[str] = []
    if subtitles:
        available_sub_langs.extend([f"{k} (manual)" for k in list(subtitles.keys())[:5]])
    if auto_subs and len(available_sub_langs) < 6:
        auto_keys = [k for k in auto_subs.keys() if k not in subtitles][:5]
        available_sub_langs.extend([f"{k} (auto)" for k in auto_keys])

    if available_sub_langs:
        lines.append(f"> 💬 **Available Subtitles:** {', '.join(available_sub_langs)}")
        lines.append("> 💡 *To transcribe full audio with Whisper, run: `agent-reach transcribe <url>`*")
        lines.append("")

    return "\n".join(lines)


def fetch_youtube_content(url: str) -> Dict[str, Any]:
    """High-level function returning structured chat response data for YouTube URLs."""
    info = extract_youtube_info(url)
    title = info.get("title") or "YouTube Video"
    uploader = info.get("uploader") or info.get("channel") or "Unknown"
    duration = info.get("duration_string") or ""
    summary_markdown = format_youtube_markdown(info, original_url=url)
    webpage_url = info.get("webpage_url") or url
    description = (info.get("description") or "").strip()
    highlight = description[:240].strip() + "..." if len(description) > 240 else description

    source_title = f"{title} | {uploader}"
    if duration:
        source_title += f" ({duration})"

    return {
        "title": title,
        "channel": uploader,
        "duration": duration,
        "summary": summary_markdown,
        "sources": [
            {
                "title": source_title,
                "url": webpage_url,
                "author": uploader,
                "highlights": [highlight] if highlight else [],
            }
        ],
        "metadata": {
            "platform": "youtube",
            "video_id": info.get("id"),
            "title": title,
            "channel": uploader,
            "duration": duration,
            "views": info.get("view_count"),
            "likes": info.get("like_count"),
            "url": webpage_url,
        },
    }
