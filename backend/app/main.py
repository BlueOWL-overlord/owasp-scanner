import asyncio
import platform
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.auth.router import router as auth_router
from app.scanner.router import router as scanner_router
from app.integrations.router import router as integrations_router

# Windows requires ProactorEventLoop for asyncio subprocesses (uvicorn uses SelectorEventLoop by default)
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="OWASP Dependency Scanner",
    description="Web application for OWASP Dependency Check with AI-assisted false positive reduction",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(scanner_router)
app.include_router(integrations_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "owasp-scanner-api"}
