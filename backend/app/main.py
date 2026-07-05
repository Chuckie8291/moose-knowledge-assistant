"""Application entry point - serves API + built-in chat UI."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import settings
from app.dependencies import init_db, close_db

_CHAT_PATH = Path(__file__).parent / "chat.html"
CHAT_HTML = _CHAT_PATH.read_text(encoding="utf-8") if _CHAT_PATH.exists() else "<h1>Chat UI not found</h1>"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from app.api.v1.router import api_router
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": settings.app_version}

    @app.get("/", response_class=HTMLResponse)
    async def chat_ui():
        return CHAT_HTML

    return app


app = create_app()
