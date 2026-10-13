# -*- coding: utf-8 -*-
"""Cross-channel backends.

A backend here is an upstream runtime that serves MULTIPLE channels
(e.g. OpenCLI covers xiaohongshu/reddit/bilibili/twitter through one
browser session), as opposed to the per-platform tools probed inside
each channel file.
"""

from .opencli import (  # noqa: F401
    OPENCLI_EXTENSION_URL,
    OPENCLI_PACKAGE,
    OpenCLIStatus,
    opencli_status,
    opencli_summary,
)
from .exa import (  # noqa: F401
    ExaAPIError,
    format_search_results,
    get_exa_api_key,
    search_exa,
)
from .youtube import (  # noqa: F401
    extract_youtube_info,
    fetch_youtube_content,
    format_youtube_markdown,
    is_youtube_url,
)

