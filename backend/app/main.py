import asyncio
import platform
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import create_db_and_tables, migrate_db
from app.auth.router import router as auth_router
from app.scanner.router import router as scanner_router
from app.integrations.router import router as integrations_router
from app.limiter import limiter

# Windows requires ProactorEventLoop for asyncio subprocesses (uvicorn uses SelectorEventLoop by default)
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    migrate_db()
    yield


app = FastAPI(
    title="OWASP Dependency Scanner",
    description="Web application for OWASP Dependency Check with AI-assisted false positive reduction",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth_router)
app.include_router(scanner_router)
app.include_router(integrations_router)


@app.get("/health")
def health():
    return {"status": "ok"}


def _find_frontend_dist() -> str | None:
    """Locate the React production build directory.

    Checks (in order):
    1. FRONTEND_DIST_PATH env var (set by standalone launcher)
    2. PyInstaller bundle directory (_MEIPASS)
    3. Source-tree location (backend/app/main.py → project-root/frontend/dist)
    """
    import os
    import sys

    p = os.environ.get("FRONTEND_DIST_PATH")
    if p and os.path.isdir(p):
        return p

    if getattr(sys, "frozen", False):
        p = os.path.join(sys._MEIPASS, "frontend", "dist")
        if os.path.isdir(p):
            return p

    here = os.path.dirname(os.path.abspath(__file__))   # backend/app/
    p = os.path.normpath(os.path.join(here, "..", "..", "frontend", "dist"))
    if os.path.isdir(p):
        return p

    return None


_dist = _find_frontend_dist()
if _dist:
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
