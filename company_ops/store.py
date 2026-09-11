"""SQLite 저장소와 원자적인 프로젝트 상태 변경."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .catalog import STAGE_IDS, TEAM_WORKFLOWS


class StoreError(Exception):
    pass


class NotFoundError(StoreError):
    pass


class ConflictError(StoreError):
    pass


class InvalidActionError(StoreError):
    pass


class SchemaVersionError(StoreError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.path,
            timeout=5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as db:
            current_version = db.execute("PRAGMA user_version").fetchone()[0]
            if current_version not in (0, 1, 2):
                raise SchemaVersionError(f"지원하지 않는 스키마 버전입니다: {current_version}")
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        company_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        team_id TEXT NOT NULL,
                        owner TEXT NOT NULL,
                        description TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        blocked INTEGER NOT NULL DEFAULT 0,
                        version INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                project_columns = {row[1] for row in db.execute("PRAGMA table_info(projects)")}
                for name, ddl in (
                    ("planner_role", "TEXT NOT NULL DEFAULT 'astra'"),
                    ("executor_role", "TEXT NOT NULL DEFAULT 'codex'"),
                    ("reviewer_role", "TEXT NOT NULL DEFAULT 'claude'"),
                    ("current_assignee", "TEXT NOT NULL DEFAULT 'astra'"),
                ):
                    if name not in project_columns:
                        db.execute(f"ALTER TABLE projects ADD COLUMN {name} {ddl}")
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS assignments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        company_id TEXT NOT NULL,
                        team_id TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        role_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        note TEXT NOT NULL DEFAULT '',
                        started_at TEXT NOT NULL,
                        completed_at TEXT
                    )
                    """
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_assignments_project_id_id "
                    "ON assignments(project_id, id DESC)"
                )
                if current_version < 2:
                    # v1 프로젝트도 팀 규칙과 현재 단계에 맞는 담당자를 복원한다.
                    # ALTER TABLE의 고정 기본값을 그대로 두면 모든 기존 일이 Astra로 잘못 보인다.
                    existing_projects = db.execute(
                        "SELECT id, company_id, team_id, stage, blocked, created_at, updated_at FROM projects"
                    ).fetchall()
                    for project in existing_projects:
                        workflow = TEAM_WORKFLOWS.get(project[2], TEAM_WORKFLOWS["new"])
                        assignee = {
                            "intake": workflow["planner"],
                            "design": workflow["planner"],
                            "build": workflow["executor"],
                            "verify": workflow["reviewer"],
                            "done": "",
                        }.get(project[3], workflow["planner"])
                        db.execute(
                            "UPDATE projects SET planner_role=?, executor_role=?, reviewer_role=?, current_assignee=? WHERE id=?",
                            (workflow["planner"], workflow["executor"], workflow["reviewer"], assignee, project[0]),
                        )
                        if project[3] != "done":
                            db.execute(
                                "INSERT INTO assignments (project_id, company_id, team_id, stage, role_id, status, note, started_at) "
                                "VALUES (?, ?, ?, ?, ?, ?, '기존 프로젝트 담당 복원', ?)",
                                (project[0], project[1], project[2], project[3], assignee,
                                 "blocked" if project[4] else "active", project[6] or project[5]),
                            )
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        company_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        message TEXT NOT NULL,
                        evidence TEXT NOT NULL DEFAULT '',
                        reviewer TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL
                    )
                    """
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_events_project_id_id "
                    "ON events(project_id, id DESC)"
                )
                # 초기 v2 시제품이 담당 역할을 검수자 칸에 기록했던 값을 정리한다.
                db.execute("UPDATE events SET reviewer='' WHERE kind='assigned' AND reviewer<>''")
                if current_version < 2:
                    db.execute("PRAGMA user_version = 2")
                db.commit()
            except Exception:
                db.rollback()
                raise

    @staticmethod
    def _project(row: sqlite3.Row | tuple) -> dict:
        keys = (
            "id", "company_id", "title", "team_id", "owner", "description",
            "stage", "blocked", "version", "created_at", "updated_at",
            "planner_role", "executor_role", "reviewer_role", "current_assignee",
        )
        return dict(zip(keys, row)) | {"blocked": bool(row[7])}

    @staticmethod
    def _event(row: sqlite3.Row | tuple) -> dict:
        keys = ("id", "project_id", "company_id", "kind", "message", "evidence", "reviewer", "created_at")
        return dict(zip(keys, row))

    def create_project(self, *, company_id: str, title: str, team_id: str, owner: str, description: str) -> dict:
        project_id = str(uuid.uuid4())
        timestamp = utc_now()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                workflow = TEAM_WORKFLOWS[team_id]
                db.execute(
                    "INSERT INTO projects (id, company_id, title, team_id, owner, description, stage, blocked, version, created_at, updated_at, planner_role, executor_role, reviewer_role, current_assignee) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'intake', 0, 1, ?, ?, ?, ?, ?, ?)",
                    (project_id, company_id, title, team_id, owner, description, timestamp, timestamp,
                     workflow["planner"], workflow["executor"], workflow["reviewer"], workflow["planner"]),
                )
                db.execute(
                    "INSERT INTO events (project_id, company_id, kind, message, created_at) VALUES (?, ?, 'created', ?, ?)",
                    (project_id, company_id, f"프로젝트 생성: {title}", timestamp),
                )
                db.execute(
                    "INSERT INTO assignments (project_id, company_id, team_id, stage, role_id, status, note, started_at) "
                    "VALUES (?, ?, ?, 'intake', ?, 'active', '접수와 목표 확인', ?)",
                    (project_id, company_id, team_id, workflow["planner"], timestamp),
                )
                db.execute(
                    "INSERT INTO events (project_id, company_id, kind, message, created_at) "
                    "VALUES (?, ?, 'assigned', ?, ?)",
                    (project_id, company_id, f"접수 업무 배정 → {workflow['planner']}", timestamp),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict:
        with self.connection() as db:
            row = db.execute(
                "SELECT id, company_id, title, team_id, owner, description, stage, blocked, version, created_at, updated_at, planner_role, executor_role, reviewer_role, current_assignee FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(project_id)
        return self._project(row)

    def apply_action(
        self,
        project_id: str,
        *,
        action: str,
        version: int,
        note: str,
        evidence: str,
        reviewer: str,
    ) -> dict:
        with self.connection() as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                db.rollback()
                raise NotFoundError(project_id)
            if row["version"] != version:
                db.rollback()
                raise ConflictError("버전이 최신 상태와 다릅니다")

            stage = row["stage"]
            blocked = bool(row["blocked"])
            next_stage = stage
            next_blocked = blocked
            next_assignee = row["current_assignee"]
            if stage == "done":
                db.rollback()
                raise ConflictError("완료된 프로젝트는 변경할 수 없습니다")
            if blocked:
                if action != "resume":
                    db.rollback()
                    raise ConflictError("차단된 프로젝트는 재개만 할 수 있습니다")
                if not note:
                    db.rollback()
                    raise InvalidActionError("재개하려면 사유가 필요합니다")
                next_blocked = False
                db.execute(
                    "UPDATE assignments SET status='active', note=?, completed_at=NULL "
                    "WHERE id=(SELECT id FROM assignments WHERE project_id=? ORDER BY id DESC LIMIT 1)",
                    (note, project_id),
                )
            elif action == "advance":
                if stage == "verify":
                    if not evidence or not reviewer:
                        db.rollback()
                        raise InvalidActionError("완료에는 검증 증거와 검토자가 필요합니다")
                    if reviewer.casefold() == row["owner"].strip().casefold():
                        db.rollback()
                        raise InvalidActionError("검토자는 담당자와 달라야 합니다")
                next_stage = STAGE_IDS[STAGE_IDS.index(stage) + 1]
                next_assignee = self._assignee_for(row, next_stage)
            elif action == "block":
                if stage not in STAGE_IDS[:-1] or not note:
                    db.rollback()
                    raise InvalidActionError("차단하려면 진행 중 단계와 사유가 필요합니다")
                next_blocked = True
                db.execute(
                    "UPDATE assignments SET status='blocked', note=? "
                    "WHERE id=(SELECT id FROM assignments WHERE project_id=? ORDER BY id DESC LIMIT 1)",
                    (note, project_id),
                )
            elif action == "resume":
                db.rollback()
                raise ConflictError("차단되지 않은 프로젝트는 재개할 수 없습니다")
            elif action == "reject":
                if stage != "verify":
                    db.rollback()
                    raise ConflictError("반려는 검증 단계에서만 할 수 있습니다")
                if not note:
                    db.rollback()
                    raise InvalidActionError("반려하려면 사유가 필요합니다")
                next_stage = "build"
                next_assignee = row["executor_role"]
            else:
                db.rollback()
                raise InvalidActionError("알 수 없는 작업입니다")

            timestamp = utc_now()
            new_version = row["version"] + 1
            db.execute(
                "UPDATE projects SET stage = ?, blocked = ?, version = ?, updated_at = ?, current_assignee = ? WHERE id = ?",
                (next_stage, int(next_blocked), new_version, timestamp, next_assignee, project_id),
            )
            message = note or f"{action}: {stage} → {next_stage}"
            db.execute(
                "INSERT INTO events (project_id, company_id, kind, message, evidence, reviewer, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, row["company_id"], action, message, evidence, reviewer, timestamp),
            )
            if next_stage != stage:
                db.execute(
                    "UPDATE assignments SET status='done', completed_at=? "
                    "WHERE id=(SELECT id FROM assignments WHERE project_id=? ORDER BY id DESC LIMIT 1)",
                    (timestamp, project_id),
                )
                if next_stage != "done":
                    assignment_note = {
                        "design": "해결안과 완료 조건 설계",
                        "build": "승인된 설계 구현",
                        "verify": "실행 결과와 완료 조건 검증",
                    }[next_stage]
                    db.execute(
                        "INSERT INTO assignments (project_id, company_id, team_id, stage, role_id, status, note, started_at) "
                        "VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                        (project_id, row["company_id"], row["team_id"], next_stage,
                         next_assignee, assignment_note, timestamp),
                    )
                    db.execute(
                        "INSERT INTO events (project_id, company_id, kind, message, created_at) "
                        "VALUES (?, ?, 'assigned', ?, ?)",
                        (project_id, row["company_id"], f"{next_stage} 업무 배정 → {next_assignee}", timestamp),
                    )
            db.commit()
            updated = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._project(updated)

    @staticmethod
    def _assignee_for(row: sqlite3.Row, stage: str) -> str:
        if stage in {"intake", "design"}:
            return row["planner_role"]
        if stage == "build":
            return row["executor_role"]
        if stage == "verify":
            return row["reviewer_role"]
        return ""

    def state(self) -> dict:
        with self.connection() as db:
            db.row_factory = sqlite3.Row
            projects = db.execute(
                "SELECT id, company_id, title, team_id, owner, description, stage, blocked, version, created_at, updated_at, planner_role, executor_role, reviewer_role, current_assignee FROM projects ORDER BY created_at DESC, id DESC"
            ).fetchall()
            events = db.execute(
                "SELECT id, project_id, company_id, kind, message, evidence, reviewer, created_at FROM events ORDER BY id DESC LIMIT 100"
            ).fetchall()
            assignments = db.execute(
                "SELECT id, project_id, company_id, team_id, stage, role_id, status, note, started_at, completed_at "
                "FROM assignments ORDER BY id DESC LIMIT 300"
            ).fetchall()
        assignment_keys = ("id", "project_id", "company_id", "team_id", "stage", "role_id", "status", "note", "started_at", "completed_at")
        return {
            "projects": [self._project(row) for row in projects],
            "events": [self._event(row) for row in events],
            "assignments": [dict(zip(assignment_keys, row)) for row in assignments],
        }

    def project_events(self, project_id: str, *, before_id: int | None = None, limit: int = 50) -> list[dict]:
        with self.connection() as db:
            db.row_factory = sqlite3.Row
            if db.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
                raise NotFoundError(project_id)
            if before_id is None:
                rows = db.execute(
                    "SELECT id, project_id, company_id, kind, message, evidence, reviewer, created_at FROM events WHERE project_id = ? ORDER BY id DESC LIMIT ?",
                    (project_id, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, project_id, company_id, kind, message, evidence, reviewer, created_at FROM events WHERE project_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                    (project_id, before_id, limit),
                ).fetchall()
        return [self._event(row) for row in rows]
