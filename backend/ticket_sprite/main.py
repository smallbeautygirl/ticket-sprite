"""ASGI entry point: `uvicorn ticket_sprite.main:app`."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db
from .config import Settings, get_settings
from .engine.llm import ClaudeInterviewer, FakeInterviewer, InterviewLLM
from .knowledge import knowledge_sync_loop
from .notify import Notifier
from .routers.api import router
from .services import Deps, reminder_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(
    settings: Settings | None = None,
    *,
    llm: InterviewLLM | None = None,
    notifier: Notifier | None = None,
    background_jobs: bool = True,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.init_engine(settings.database_url)
        await db.create_all()
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        chosen_llm = llm or (FakeInterviewer() if settings.llm_mode == "fake" else ClaudeInterviewer(settings))
        app.state.deps = Deps(
            settings=settings,
            sessionmaker=db.sessionmaker(),
            llm=chosen_llm,
            notifier=notifier or Notifier(settings),
            ado_transport=getattr(app.state, "ado_transport", None),
        )
        jobs: list[asyncio.Task] = []
        if background_jobs:
            jobs.append(asyncio.create_task(knowledge_sync_loop(settings)))
            jobs.append(asyncio.create_task(reminder_loop(app.state.deps)))
        yield
        for job in jobs:
            job.cancel()
        await app.state.deps.drain()

    app = FastAPI(title="Ticket Sprite", lifespan=lifespan)
    app.dependency_overrides[get_settings] = lambda: settings
    app.include_router(router)

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    return app


app = create_app()
