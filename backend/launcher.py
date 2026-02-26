"""Standalone launcher for OWASP Dependency Scanner.

This is the PyInstaller entry point.  It:
  1. Creates writable user-data directories in %APPDATA%\\OWASP Scanner\\
  2. Auto-generates a .env with a strong SECRET_KEY on first run
  3. Sets environment variables so app.config picks up the right paths
  4. Loads the user .env (ANTHROPIC_API_KEY, NVD_API_KEY, etc.)
  5. Starts uvicorn on http://127.0.0.1:8000
  6. Opens the browser after uvicorn is ready
"""

from __future__ import annotations

import os
import secrets
import sys
import threading
import time
import webbrowser
from pathlib import Path


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "OWASP Scanner"


def get_install_dir() -> Path:
    """Return the directory that contains owasp-scanner.exe (or launcher.py)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # Dev mode: launcher.py lives in backend/
    return Path(__file__).parent


# ---------------------------------------------------------------------------
# First-run .env setup
# ---------------------------------------------------------------------------

_ENV_TEMPLATE = """\
# OWASP Dependency Scanner — configuration
# Generated automatically on first run.  Edit as needed.

# JWT signing key (auto-generated — do not change after first login)
SECRET_KEY={secret_key}

# Anthropic API key — required for AI false-positive analysis
# Get one at https://console.anthropic.com/
ANTHROPIC_API_KEY=

# NVD API key — optional but greatly speeds up the first NVD database download
# Request a free key at https://nvd.nist.gov/developers/request-an-api-key
NVD_API_KEY=
"""


def ensure_env_file(env_path: Path) -> None:
    if env_path.exists():
        return
    env_path.write_text(
        _ENV_TEMPLATE.format(secret_key=secrets.token_hex(32)),
        encoding="utf-8",
    )
    print(f"[launcher] Created configuration file: {env_path}")
    print("[launcher] Edit it to add your ANTHROPIC_API_KEY before using AI features.")


# ---------------------------------------------------------------------------
# Browser open
# ---------------------------------------------------------------------------

def _open_browser_after_delay(url: str, delay: float = 2.5) -> None:
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    app_data = get_appdata_dir()
    install_dir = get_install_dir()

    # Create persistent user-data directories
    for sub in ("data", "uploads", "reports", "dependency-check-data"):
        (app_data / sub).mkdir(parents=True, exist_ok=True)

    # Create / verify .env
    env_path = app_data / ".env"
    ensure_env_file(env_path)

    # ---------------------------------------------------------------------------
    # Set environment variables before importing app.config (pydantic-settings
    # reads them at import time).  We use setdefault so explicit env vars win.
    # ---------------------------------------------------------------------------
    owasp_dc = install_dir / "dependency-check" / "bin" / "dependency-check.bat"
    overrides = {
        "OWASP_DC_PATH":     str(owasp_dc),
        "OWASP_DC_DATA_DIR": str(app_data / "dependency-check-data"),
        "UPLOAD_DIR":        str(app_data / "uploads"),
        "REPORTS_DIR":       str(app_data / "reports"),
        "DATABASE_URL":      f"sqlite:///{app_data / 'data' / 'app.db'}",
        "FRONTEND_DIST_PATH": str(
            (install_dir / "frontend" / "dist")
            if getattr(sys, "frozen", False)
            else (install_dir.parent / "frontend" / "dist")
        ),
    }
    for key, val in overrides.items():
        os.environ.setdefault(key, val)

    # Load user .env (may add/override ANTHROPIC_API_KEY, NVD_API_KEY, etc.)
    # python-dotenv won't override vars already in the environment.
    from dotenv import load_dotenv
    load_dotenv(env_path, override=False)

    # Work from app_data so any remaining relative-path references resolve there
    os.chdir(app_data)

    # Open the browser in a background thread after uvicorn starts
    threading.Thread(
        target=_open_browser_after_delay,
        args=("http://127.0.0.1:8000",),
        daemon=True,
    ).start()

    print("[launcher] Starting OWASP Dependency Scanner on http://127.0.0.1:8000")
    print(f"[launcher] Data directory: {app_data}")
    print("[launcher] Press Ctrl+C to stop.")

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
