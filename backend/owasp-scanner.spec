# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for OWASP Dependency Scanner standalone build.
#
# Usage (from the backend/ directory):
#   pip install pyinstaller
#   pyinstaller owasp-scanner.spec
#
# Output: dist/owasp-scanner/owasp-scanner.exe  (one-directory bundle)

import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# ---------------------------------------------------------------------------
# Collect data / binaries for packages that rely on non-Python files
# ---------------------------------------------------------------------------
anthropic_datas, anthropic_bins, anthropic_hidden = collect_all("anthropic")
httpx_datas, httpx_bins, httpx_hidden = collect_all("httpx")
lxml_datas, lxml_bins, lxml_hidden = collect_all("lxml")

extra_datas = (
    anthropic_datas
    + httpx_datas
    + lxml_datas
    + collect_data_files("pydantic")
    + collect_data_files("pydantic_settings")
    + collect_data_files("sqlmodel")
    + collect_data_files("starlette")
    + collect_data_files("fastapi")
)

extra_binaries = anthropic_bins + httpx_bins + lxml_bins

# ---------------------------------------------------------------------------
# Application source files
# ---------------------------------------------------------------------------
app_datas = [
    ("app", "app"),  # entire app/ package
]

# Include the React build if it already exists next to backend/
_frontend_dist = os.path.join("..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app_datas.append((_frontend_dist, "frontend/dist"))
else:
    print(
        "WARNING: ../frontend/dist not found. Run `npm run build` in the frontend "
        "directory before packaging, or the UI will not be bundled."
    )

all_datas = app_datas + extra_datas

# ---------------------------------------------------------------------------
# Hidden imports
# (Packages that use dynamic loading and aren't auto-detected by PyInstaller)
# ---------------------------------------------------------------------------
hidden_imports = [
    # uvicorn internals
    "uvicorn.lifespan.on",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.logging",
    # fastapi / starlette
    "fastapi.middleware.cors",
    "fastapi.staticfiles",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.staticfiles",
    "starlette.responses",
    "starlette.background",
    # pydantic
    "pydantic.deprecated.class_validators",
    "pydantic.v1",
    "pydantic_settings",
    # sqlmodel / sqlalchemy
    "sqlmodel",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.sql.default_comparator",
    # passlib
    "passlib.handlers.bcrypt",
    "passlib.handlers.sha2_crypt",
    "passlib.handlers.pbkdf2",
    # jose / cryptography
    "jose",
    "jose.jwt",
    "jose.exceptions",
    "cryptography.hazmat.primitives.asymmetric.rsa",
    "cryptography.hazmat.primitives.asymmetric.padding",
    # python-multipart
    "multipart",
    "multipart.multipart",
    # slowapi / limits
    "slowapi",
    "limits",
    "limits.storage",
    "limits.strategies",
    # anthropic extras
    *anthropic_hidden,
    # httpx extras
    *httpx_hidden,
    # lxml
    *lxml_hidden,
    "lxml.etree",
    "lxml._elementpath",
    # aiofiles
    "aiofiles",
    "aiofiles.os",
    # python-dotenv
    "dotenv",
    # email (stdlib, sometimes missed)
    "email.mime.text",
    "email.mime.multipart",
    # logging
    "logging.config",
    # app modules (ensure they're all collected)
    "app.main",
    "app.config",
    "app.database",
    "app.limiter",
    "app.auth.models",
    "app.auth.router",
    "app.auth.utils",
    "app.scanner.models",
    "app.scanner.router",
    "app.scanner.owasp",
    "app.ai",
    "app.integrations.router",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=extra_binaries,
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy packages that aren't needed
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "scipy",
        "pytest",
        "IPython",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="owasp-scanner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,          # console=True so logs are visible; set False for silent
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,             # replace with path to .ico if available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="owasp-scanner",
)
