# -*- coding: utf-8 -*-
"""Launcher for Agent Reach ChatGPT-style UI."""

import sys
import webbrowser
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv

    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
except Exception:
    pass

import uvicorn
from ui.server import app

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import io
            if hasattr(sys.stdout, "buffer"):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}"
    print("\n" + "=" * 55)
    print("  [Agent Reach] Web Interface Starting...")
    print(f"  URL: {url}")
    print("  Press Ctrl + C to stop the server")
    print("=" * 55 + "\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    uvicorn.run("ui.server:app", host=host, port=port, reload=True)
