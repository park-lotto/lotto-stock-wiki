"""회사 운영실 FastAPI 애플리케이션."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from .catalog import (
    COMPANIES,
    COMPANY_IDS,
    INTEGRATIONS,
    ROLES,
    STAGE_DEFINITIONS,
    TEAM_IDS,
    TEAMS,
)
from .store import ConflictError, InvalidActionError, NotFoundError, SchemaVersionError, Store


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: str
    title: str = Field(min_length=1, max_length=120)
    team_id: str
    owner: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=4000)

    @field_validator("company_id", "team_id", "title", "owner", "description", mode="before")
    @classmethod
    def trim_text(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip()


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["advance", "block", "resume", "reject"]
    version: StrictInt = Field(ge=1)
    note: str = Field(default="", max_length=4000)
    evidence: str = Field(default="", max_length=4000)
    reviewer: str = Field(default="", max_length=80)

    @field_validator("action", "note", "evidence", "reviewer", mode="before")
    @classmethod
    def trim_text(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip()


def _default_db_path() -> Path:
    configured = os.environ.get("COMPANY_OPS_DB")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "data" / "company_ops.sqlite3"


def create_app(db_path: str | Path | None = None) -> FastAPI:
    store = Store(db_path if db_path is not None else _default_db_path())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        store.initialize()
        yield

    application = FastAPI(title="회사 운영실", lifespan=lifespan)
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1"],
    )

    @application.middleware("http")
    async def local_write_security(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                return JSONResponse({"detail": "쓰기 요청은 application/json이어야 합니다"}, status_code=415)
            if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
                return JSONResponse({"detail": "교차 출처 요청은 허용되지 않습니다"}, status_code=403)
            origin = request.headers.get("origin")
            if origin:
                expected = f"{request.url.scheme}://{request.url.netloc}"
                if origin.rstrip("/") != expected.rstrip("/"):
                    return JSONResponse({"detail": "요청 출처가 허용되지 않습니다"}, status_code=403)
        return await call_next(request)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _exc: RequestValidationError):
        return JSONResponse({"detail": "입력값이 올바르지 않습니다"}, status_code=422)

    @application.exception_handler(NotFoundError)
    async def not_found(_request: Request, _exc: NotFoundError):
        return JSONResponse({"detail": "프로젝트를 찾을 수 없습니다"}, status_code=404)

    @application.exception_handler(ConflictError)
    async def conflict(_request: Request, exc: ConflictError):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @application.exception_handler(InvalidActionError)
    async def invalid_action(_request: Request, exc: InvalidActionError):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @application.get("/api/state")
    def get_state():
        return {
            "companies": COMPANIES,
            "teams": TEAMS,
            "roles": ROLES,
            **store.state(),
            "stages": STAGE_DEFINITIONS,
            "integrations": INTEGRATIONS,
        }

    @application.post("/api/projects", status_code=201)
    def create_project(payload: ProjectCreate):
        if payload.company_id not in COMPANY_IDS or payload.team_id not in TEAM_IDS:
            return JSONResponse({"detail": "알 수 없는 회사 또는 팀입니다"}, status_code=422)
        return store.create_project(**payload.model_dump())

    @application.post("/api/projects/{project_id}/actions")
    def project_action(project_id: str, payload: ActionRequest):
        return store.apply_action(project_id, **payload.model_dump())

    @application.get("/api/projects/{project_id}/events")
    def get_project_events(
        project_id: str,
        before_id: int | None = Query(default=None, ge=1),
        limit: int = Query(default=50, ge=1, le=100),
    ):
        return store.project_events(project_id, before_id=before_id, limit=limit)

    static_dir = Path(__file__).resolve().parent / "static"
    application.mount("/static", StaticFiles(directory=static_dir), name="static")
    application.mount("/", StaticFiles(directory=static_dir, html=True), name="site")
    return application


app = create_app()
