from __future__ import annotations

import json
import inspect
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from company_ops.app import SchemaVersionError, create_app


class CompanyOpsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temporary_directory.name) / "company-ops.sqlite3"
        self.client = TestClient(create_app(self.db_path), base_url="http://localhost")
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "company_id": "makers",
            "title": "API 검수 프로젝트",
            "team_id": "qa",
            "owner": "운영자",
            "description": "검수 설명",
        }
        payload.update(overrides)
        return payload

    def create_project(self, **overrides: object) -> dict:
        response = self.client.post("/api/projects", json=self.payload(**overrides))
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def action(self, project: dict, action: str, **overrides: object) -> dict:
        payload: dict[str, object] = {"action": action, "version": project["version"]}
        payload.update(overrides)
        response = self.client.post(f"/api/projects/{project['id']}/actions", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def advance_to_verify(self, project: dict) -> dict:
        for expected_stage in ("design", "build", "verify"):
            project = self.action(project, "advance")
            self.assertEqual(project["stage"], expected_stage)
        return project

    def test_state_exposes_fixed_catalog_and_empty_arrays(self) -> None:
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        state = response.json()
        self.assertEqual({item["id"] for item in state["companies"]}, {"makers", "hnl", "stock"})
        self.assertEqual({item["id"] for item in state["teams"]}, {"new", "improve", "cs", "ops", "qa"})
        workflows = {item["id"]: item["workflow"] for item in state["teams"]}
        self.assertEqual(workflows["new"], {"planner": "astra", "executor": "codex", "reviewer": "claude"})
        self.assertEqual(workflows["cs"], {"planner": "claude", "executor": "opus", "reviewer": "astra"})
        self.assertEqual(
            state["stages"],
            [
                {"id": "intake", "label": "접수"},
                {"id": "design", "label": "설계"},
                {"id": "build", "label": "구현"},
                {"id": "verify", "label": "검증"},
                {"id": "done", "label": "완료"},
            ],
        )
        self.assertEqual(state["projects"], [])
        self.assertEqual(state["events"], [])
        self.assertEqual(state["assignments"], [])
        catalog_text = json.dumps(state["companies"], ensure_ascii=False)
        self.assertNotIn("확정 매출", catalog_text)
        self.assertNotIn("후보수익", catalog_text)
        self.assertTrue(all("미연결" in item["status"] for item in state["roles"] + state["integrations"]))
        self.assertEqual(
            {item["name"]: item["role"] for item in state["roles"]},
            {"Astra": "기획 책임", "Claude": "기획 책임", "Opus": "실행 리더", "Codex": "실행 리더"},
        )

    def test_lifespan_initializes_schema_at_version_two(self) -> None:
        db = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
        finally:
            db.close()

    def test_v1_projects_migrate_to_team_and_stage_assignments(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy.sqlite3"
        db = sqlite3.connect(legacy_path)
        try:
            db.executescript(
                """
                CREATE TABLE projects (
                    id TEXT PRIMARY KEY, company_id TEXT NOT NULL, title TEXT NOT NULL,
                    team_id TEXT NOT NULL, owner TEXT NOT NULL, description TEXT NOT NULL,
                    stage TEXT NOT NULL, blocked INTEGER NOT NULL DEFAULT 0,
                    version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                    company_id TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL,
                    evidence TEXT NOT NULL DEFAULT '', reviewer TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
                );
                INSERT INTO projects VALUES (
                    'legacy-build', 'makers', '기존 개선 업무', 'improve', '대표', '',
                    'build', 1, 4, '2026-09-10T00:00:00Z', '2026-09-11T00:00:00Z'
                );
                INSERT INTO projects VALUES (
                    'legacy-done', 'makers', '기존 완료 업무', 'ops', '대표', '',
                    'done', 0, 8, '2026-09-09T00:00:00Z', '2026-09-10T00:00:00Z'
                );
                PRAGMA user_version = 1;
                """
            )
            db.commit()
        finally:
            db.close()

        with TestClient(create_app(legacy_path), base_url="http://localhost") as legacy_client:
            state = legacy_client.get("/api/state").json()
        projects = {item["id"]: item for item in state["projects"]}
        self.assertEqual(projects["legacy-build"]["current_assignee"], "codex")
        self.assertEqual(projects["legacy-done"]["current_assignee"], "")
        self.assertEqual(len(state["assignments"]), 1)
        self.assertEqual(state["assignments"][0]["project_id"], "legacy-build")
        self.assertEqual(state["assignments"][0]["role_id"], "codex")
        self.assertEqual(state["assignments"][0]["status"], "blocked")

    def test_newer_schema_version_is_rejected_without_downgrade(self) -> None:
        newer_db_path = Path(self.temporary_directory.name) / "newer.sqlite3"
        db = sqlite3.connect(newer_db_path)
        try:
            db.execute("PRAGMA user_version = 3")
            db.commit()
        finally:
            db.close()
        newer_client = TestClient(create_app(newer_db_path), base_url="http://localhost")
        with self.assertRaises(SchemaVersionError):
            newer_client.__enter__()
        db = sqlite3.connect(newer_db_path)
        try:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 3)
        finally:
            db.close()

    def test_state_read_does_not_wait_for_an_immediate_write_lock(self) -> None:
        lock_holder = sqlite3.connect(self.db_path, isolation_level=None)
        lock_holder.execute("BEGIN IMMEDIATE")
        original_connect = sqlite3.connect

        def short_timeout_connect(*args, **kwargs):
            kwargs["timeout"] = 0.1
            return original_connect(*args, **kwargs)

        try:
            with mock.patch("company_ops.store.sqlite3.connect", side_effect=short_timeout_connect):
                started = time.monotonic()
                response = self.client.get("/api/state")
                elapsed = time.monotonic() - started
        finally:
            lock_holder.rollback()
            lock_holder.close()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertLess(elapsed, 1.0)

    def test_database_routes_are_synchronous_threadpool_endpoints(self) -> None:
        routes = {route.path: route for route in self.client.app.routes if hasattr(route, "endpoint")}
        for path in ("/api/state", "/api/projects", "/api/projects/{project_id}/actions", "/api/projects/{project_id}/events"):
            self.assertFalse(inspect.iscoroutinefunction(routes[path].endpoint), path)

    def test_catalog_includes_the_full_handoff_product_and_revenue_scope(self) -> None:
        companies = {item["id"]: item for item in self.client.get("/api/state").json()["companies"]}
        makers = json.dumps(companies["makers"], ensure_ascii=False)
        hnl = json.dumps(companies["hnl"], ensure_ascii=False)
        stock = json.dumps(companies["stock"], ensure_ascii=False)
        for text in ("숏템메이커", "추가 쇼츠", "인스타 카드뉴스", "블로그", "프로그램 판매", "설치", "컨설팅", "—"):
            self.assertIn(text, makers)
        for text in ("중고폰 수출", "오프라인", "직원 2명", "기관물량", "폐폰 수익화", "재고관리", "세부회계 미연결", "과금 계획", "방식 미정", "—"):
            self.assertIn(text, hnl)
        for text in ("섹터맵", "인사이트", "개발", "미출시", "수익모델 미확정", "출시전", "—"):
            self.assertIn(text, stock)
        for text in (makers, hnl, stock):
            self.assertIn("미연결", text)

    def test_create_trims_preserves_html_and_creates_utc_event(self) -> None:
        project = self.create_project(
            title="  <b>HTML 제목</b>  ",
            owner="  담당자  ",
            description="  <em>설명은 보존</em>  ",
        )
        self.assertEqual(project["title"], "<b>HTML 제목</b>")
        self.assertEqual(project["owner"], "담당자")
        self.assertEqual(project["description"], "<em>설명은 보존</em>")
        self.assertEqual(project["stage"], "intake")
        self.assertEqual(project["version"], 1)
        self.assertTrue(project["created_at"].endswith("Z"))
        events = self.client.get(f"/api/projects/{project['id']}/events").json()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["kind"], "assigned")
        self.assertEqual(events[1]["kind"], "created")
        self.assertEqual(events[0]["reviewer"], "")
        self.assertTrue(events[0]["created_at"].endswith("Z"))

    def test_team_rules_assign_and_move_real_work_between_roles(self) -> None:
        project = self.create_project(team_id="improve")
        self.assertEqual(project["planner_role"], "claude")
        self.assertEqual(project["executor_role"], "codex")
        self.assertEqual(project["reviewer_role"], "astra")
        self.assertEqual(project["current_assignee"], "claude")
        state = self.client.get("/api/state").json()
        self.assertEqual(state["assignments"][0]["role_id"], "claude")
        self.assertEqual(state["assignments"][0]["status"], "active")

        project = self.action(project, "advance", note="설계 시작")
        self.assertEqual(project["stage"], "design")
        self.assertEqual(project["current_assignee"], "claude")
        project = self.action(project, "advance", note="구현 시작")
        self.assertEqual(project["stage"], "build")
        self.assertEqual(project["current_assignee"], "codex")
        project = self.action(project, "advance", note="검증 시작")
        self.assertEqual(project["stage"], "verify")
        self.assertEqual(project["current_assignee"], "astra")

        assignments = self.client.get("/api/state").json()["assignments"]
        active = [item for item in assignments if item["status"] == "active"]
        self.assertEqual([(item["stage"], item["role_id"]) for item in active], [("verify", "astra")])
        self.assertEqual({item["stage"] for item in assignments}, {"intake", "design", "build", "verify"})

    def test_block_and_resume_update_the_active_assignment(self) -> None:
        project = self.create_project(team_id="ops")
        project = self.action(project, "block", note="서버 확인 대기")
        assignment = self.client.get("/api/state").json()["assignments"][0]
        self.assertEqual(assignment["status"], "blocked")
        project = self.action(project, "resume", note="확인 완료")
        assignment = self.client.get("/api/state").json()["assignments"][0]
        self.assertEqual(assignment["status"], "active")
        self.assertEqual(assignment["note"], "확인 완료")

    def test_create_rejects_unknown_blank_or_extra_catalog_fields(self) -> None:
        for overrides in (
            {"company_id": "unknown"},
            {"team_id": "unknown"},
            {"company_id": ""},
            {"team_id": ""},
            {"title": "   "},
            {"owner": "   "},
            {"unexpected": "field"},
        ):
            response = self.client.post("/api/projects", json=self.payload(**overrides))
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get("/api/state").json()["projects"], [])

    def test_create_event_and_project_are_atomic_on_validation_failure(self) -> None:
        before = self.client.get("/api/state").json()
        response = self.client.post("/api/projects", json=self.payload(company_id="not-a-company"))
        after = self.client.get("/api/state").json()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(after["projects"], before["projects"])
        self.assertEqual(after["events"], before["events"])

    def test_event_insert_failure_rolls_back_the_created_project(self) -> None:
        self.client.get("/api/state")
        db = sqlite3.connect(self.db_path)
        try:
            db.execute(
                "CREATE TRIGGER reject_project_event BEFORE INSERT ON events "
                "WHEN NEW.kind = 'created' BEGIN SELECT RAISE(ABORT, 'event denied'); END;"
            )
            db.commit()
        finally:
            db.close()
        with self.assertRaises(sqlite3.IntegrityError):
            self.client.post("/api/projects", json=self.payload())
        state = self.client.get("/api/state").json()
        self.assertEqual(state["projects"], [])
        self.assertEqual(state["events"], [])

    def test_projects_and_schema_persist_for_a_second_app_instance(self) -> None:
        project = self.create_project()
        second_client = TestClient(create_app(self.db_path), base_url="http://localhost")
        second_client.__enter__()
        try:
            state = second_client.get("/api/state").json()
            self.assertEqual([item["id"] for item in state["projects"]], [project["id"]])
            self.assertEqual(len(state["events"]), 2)
        finally:
            second_client.__exit__(None, None, None)

    def test_unknown_projects_return_404(self) -> None:
        response = self.client.get("/api/projects/does-not-exist/events")
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            "/api/projects/does-not-exist/actions",
            json={"action": "advance", "version": 1},
        )
        self.assertEqual(response.status_code, 404)

    def test_action_payload_validation_rejects_unknown_invalid_or_nonpositive_version(self) -> None:
        project = self.create_project()
        cases = (
            {"action": "unknown", "version": project["version"]},
            {"action": "advance", "version": 0},
            {"action": "advance", "version": project["version"], "extra": True},
            {"action": "advance", "version": project["version"], "reviewer": "x" * 81},
        )
        for payload in cases:
            response = self.client.post(f"/api/projects/{project['id']}/actions", json=payload)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertRegex(response.json()["detail"], "[가-힣]")
        for invalid_version in (True, 1.0, "1"):
            response = self.client.post(
                f"/api/projects/{project['id']}/actions",
                json={"action": "advance", "version": invalid_version},
            )
            self.assertEqual(response.status_code, 422, response.text)

    def test_stale_action_has_no_state_or_event_mutation(self) -> None:
        project = self.create_project()
        updated = self.action(project, "advance")
        before_events = self.client.get(f"/api/projects/{project['id']}/events").json()
        response = self.client.post(
            f"/api/projects/{project['id']}/actions",
            json={"action": "advance", "version": project["version"]},
        )
        self.assertEqual(response.status_code, 409)
        current = self.client.get("/api/state").json()["projects"][0]
        after_events = self.client.get(f"/api/projects/{project['id']}/events").json()
        self.assertEqual(current, updated)
        self.assertEqual(after_events, before_events)

    def test_block_resume_and_reject_follow_the_state_machine(self) -> None:
        project = self.create_project()
        blocked = self.action(project, "block", note="  외부 의존성 대기  ")
        self.assertTrue(blocked["blocked"])
        denied = self.client.post(
            f"/api/projects/{project['id']}/actions",
            json={"action": "advance", "version": blocked["version"]},
        )
        self.assertEqual(denied.status_code, 409)
        project = self.action(blocked, "resume", note="  의존성 해소  ")
        self.assertFalse(project["blocked"])
        project = self.advance_to_verify(project)
        rejected = self.action(project, "reject", note="  재작업 필요  ")
        self.assertEqual(rejected["stage"], "build")
        self.assertFalse(rejected["blocked"])

    def test_block_resume_and_reject_require_notes(self) -> None:
        project = self.create_project()
        response = self.client.post(
            f"/api/projects/{project['id']}/actions",
            json={"action": "block", "version": project["version"], "note": "   "},
        )
        self.assertEqual(response.status_code, 422, response.text)
        blocked = self.action(project, "block", note="대기")
        response = self.client.post(
            f"/api/projects/{project['id']}/actions",
            json={"action": "resume", "version": blocked["version"], "note": "   "},
        )
        self.assertEqual(response.status_code, 422, response.text)
        project = self.action(blocked, "resume", note="재개")
        project = self.advance_to_verify(project)
        response = self.client.post(
            f"/api/projects/{project['id']}/actions",
            json={"action": "reject", "version": project["version"], "note": "   "},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_completion_requires_evidence_and_a_distinct_normalized_reviewer(self) -> None:
        project = self.advance_to_verify(self.create_project(owner="  Alice Example  "))
        missing = self.client.post(
            f"/api/projects/{project['id']}/actions",
            json={"action": "advance", "version": project["version"]},
        )
        self.assertEqual(missing.status_code, 422)
        same_reviewer = self.client.post(
            f"/api/projects/{project['id']}/actions",
            json={
                "action": "advance",
                "version": project["version"],
                "evidence": "테스트 결과",
                "reviewer": "  alice example  ",
            },
        )
        self.assertEqual(same_reviewer.status_code, 422)
        completed = self.action(project, "advance", evidence="테스트 결과", reviewer="Bob")
        self.assertEqual(completed["stage"], "done")

    def test_done_projects_are_immutable(self) -> None:
        project = self.advance_to_verify(self.create_project())
        done = self.action(project, "advance", evidence="승인 증거", reviewer="검수자")
        for action in ("advance", "block", "resume", "reject"):
            response = self.client.post(
                f"/api/projects/{done['id']}/actions",
                json={"action": action, "version": done["version"], "note": "변경 시도"},
            )
            self.assertEqual(response.status_code, 409, response.text)

    def test_write_requests_enforce_json_content_type_and_same_origin(self) -> None:
        raw = json.dumps(self.payload(), ensure_ascii=False).encode()
        response = self.client.post("/api/projects", content=raw, headers={"Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 415)
        self.assertRegex(response.json()["detail"], "[가-힣]")
        response = self.client.post(
            "/api/projects",
            json=self.payload(),
            headers={"Origin": "https://external.example"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertRegex(response.json()["detail"], "[가-힣]")
        response = self.client.post("/api/projects", json=self.payload(), headers={"Origin": "null"})
        self.assertEqual(response.status_code, 403)
        response = self.client.post("/api/projects", json=self.payload(), headers={"Origin": "http://localhost:8000"})
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            "/api/projects",
            json=self.payload(),
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post("/api/projects", json=self.payload(), headers={"Origin": "http://localhost"})
        self.assertEqual(response.status_code, 201, response.text)

    def test_host_allow_list_and_static_mount_do_not_shadow_api(self) -> None:
        response = self.client.get("/api/state", headers={"Host": "evil.example"})
        self.assertEqual(response.status_code, 400)
        response = self.client.get("/api/state", headers={"Host": "testserver"})
        self.assertEqual(response.status_code, 400)
        response = self.client.get("/api/state", headers={"Host": "127.0.0.1"})
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_custom_error_details_are_korean(self) -> None:
        invalid_catalog = self.client.post("/api/projects", json=self.payload(company_id="unknown"))
        self.assertEqual(invalid_catalog.status_code, 422)
        self.assertRegex(invalid_catalog.json()["detail"], "[가-힣]")
        missing = self.client.get("/api/projects/missing/events")
        self.assertEqual(missing.status_code, 404)
        self.assertRegex(missing.json()["detail"], "[가-힣]")
        project = self.create_project()
        stale = self.client.post(
            f"/api/projects/{project['id']}/actions",
            json={"action": "advance", "version": 2},
        )
        self.assertEqual(stale.status_code, 409)
        self.assertRegex(stale.json()["detail"], "[가-힣]")

    def test_unblocked_resume_is_an_impossible_transition(self) -> None:
        project = self.create_project()
        response = self.client.post(
            f"/api/projects/{project['id']}/actions",
            json={"action": "resume", "version": project["version"], "note": "재개 시도"},
        )
        self.assertEqual(response.status_code, 409)

    def test_event_pagination_has_no_loss_after_more_than_one_hundred_events(self) -> None:
        project = self.create_project()
        for index in range(53):
            project = self.action(project, "block", note=f"대기 {index}")
            project = self.action(project, "resume", note=f"재개 {index}")

        event_ids: list[int] = []
        before_id = None
        while True:
            params = {"limit": 100}
            if before_id is not None:
                params["before_id"] = before_id
            response = self.client.get(f"/api/projects/{project['id']}/events", params=params)
            self.assertEqual(response.status_code, 200)
            page = response.json()
            if not page:
                break
            event_ids.extend(event["id"] for event in page)
            before_id = page[-1]["id"]

        self.assertEqual(len(event_ids), 108)
        self.assertEqual(len(event_ids), len(set(event_ids)))
        self.assertEqual(event_ids, sorted(event_ids, reverse=True))

    def test_same_version_concurrent_requests_allow_exactly_one_success(self) -> None:
        project = self.create_project()

        def advance_once(_: int) -> int:
            with TestClient(create_app(self.db_path), base_url="http://localhost") as client:
                response = client.post(
                    f"/api/projects/{project['id']}/actions",
                    json={"action": "advance", "version": project["version"]},
                )
                return response.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(advance_once, range(2)))
        self.assertCountEqual(statuses, [200, 409])


if __name__ == "__main__":
    unittest.main()
