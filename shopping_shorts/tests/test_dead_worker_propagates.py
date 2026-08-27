"""워커가 죽으면 화면에도 실패가 보여야 한다 (2026-08-27 실사고).

사고: 배포가 렌더 중이던 워커를 재시작 → 큐는 'failed'가 됐는데 mix_jobs.status는
'rendering'에 그대로 남았다. 화면은 계속 "최종 렌더 중…"을 돌렸고 고객(cid204,
job 261ed17263ec)은 13분을 기다리다 제보했다. 실패가 화면에 닿지 않으면
"다시 시도" 버튼도 안 뜬다 — 영원히 멈춘다.

실측 근거: 이 구멍 때문에 라이브에 extracting 6 / downloading 5 / planning 3 / tts 1건이
진행중인 채로 굳어 있었다.
"""
import json
import pytest

from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def _running(s, task, job_id, hb_minutes_ago):
    """running 상태 큐 행을 직접 넣는다(하트비트를 과거로)."""
    with s._conn() as c:
        c.execute(
            "INSERT INTO job_queue (task,args_json,state,created_at,claimed_at,heartbeat_at) "
            "VALUES (?,?,'running',datetime('now'),datetime('now'),"
            "        datetime('now', ?))",
            (task, json.dumps({"job_id": job_id}), f"-{hb_minutes_ago} minutes"))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def _job(s, job_id, **kw):
    """테스트용 job 행 — 실제 호출부(app.py:12542)와 같은 형태로 만든다."""
    s.create_mix_job(job_id, [], 30, "free")
    if kw:
        s.update_mix_job(job_id, **kw)


def _get(s, job_id, col):
    with s._conn() as c:
        r = c.execute(f"SELECT {col} FROM mix_jobs WHERE job_id=?", (job_id,)).fetchone()
        return r[0] if r else None


class TestPropagation:
    def test_render_death_reaches_screen(self, tmp_path):
        """★핵심 회귀 — 렌더 워커가 죽으면 status도 failed가 돼야 한다."""
        s = _store(tmp_path)
        _job(s, "j1", status="rendering")
        _running(s, "render", "j1", hb_minutes_ago=10)
        assert s.reap_stale() == 1
        assert _get(s, "j1", "status") == "failed", "화면이 실패를 모른다 — 영원히 멈춘다"
        assert _get(s, "j1", "error"), "왜 실패했는지도 말해야 한다"

    def test_clean_uses_its_own_column(self, tmp_path):
        """단계마다 화면이 읽는 칸이 다르다 — clean은 clean_status."""
        s = _store(tmp_path)
        _job(s, "j2", clean_status="cleaning")
        _running(s, "clean", "j2", hb_minutes_ago=10)
        s.reap_stale()
        assert _get(s, "j2", "clean_status") == "failed"
        assert _get(s, "j2", "clean_error")

    def test_preview_uses_its_own_column(self, tmp_path):
        s = _store(tmp_path)
        _job(s, "j3", preview_status="previewing")
        _running(s, "preview", "j3", hb_minutes_ago=10)
        s.reap_stale()
        assert _get(s, "j3", "preview_status") == "failed"

    def test_does_not_overwrite_finished(self, tmp_path):
        """이미 끝난 것은 덮지 않는다 — 재시도가 먼저 성공했을 수 있다."""
        s = _store(tmp_path)
        _job(s, "j4", status="done")
        _running(s, "render", "j4", hb_minutes_ago=10)
        s.reap_stale()
        assert _get(s, "j4", "status") == "done", "성공한 작업을 실패로 되돌리면 더 나쁘다"

    def test_background_task_does_not_touch_jobs(self, tmp_path):
        """배경작업(durfill 등)은 화면에 알릴 자리가 없다 — 건드리면 안 된다."""
        s = _store(tmp_path)
        _job(s, "j5", status="ready_for_review")
        _running(s, "durfill", "j5", hb_minutes_ago=10)
        s.reap_stale()
        assert _get(s, "j5", "status") == "ready_for_review"

    def test_missing_job_id_is_safe(self, tmp_path):
        """job_id 없는 큐 항목(overseas 등)에서 죽지 않는다."""
        s = _store(tmp_path)
        with s._conn() as c:
            c.execute("INSERT INTO job_queue (task,args_json,state,created_at,claimed_at,"
                      "heartbeat_at) VALUES ('overseas','{}','running',datetime('now'),"
                      "datetime('now'),datetime('now','-10 minutes'))")
        assert s.reap_stale() == 1      # 예외 없이 처리된다


class TestGracePeriod:
    def test_alive_render_is_not_reaped(self, tmp_path):
        """★렌더는 실측 최대 121초 침묵한다 — 2분 기준이면 산 걸 죽인다."""
        s = _store(tmp_path)
        _job(s, "j6", status="rendering")
        _running(s, "render", "j6", hb_minutes_ago=2.5)     # 150초 침묵 = 살아있음
        assert s.reap_stale() == 0, "실측 침묵(121초)보다 긴 여유가 있어야 한다"
        assert _get(s, "j6", "status") == "rendering"

    def test_really_dead_is_reaped(self, tmp_path):
        """진짜 죽은 것은 잡아야 한다."""
        s = _store(tmp_path)
        _job(s, "j7", status="rendering")
        _running(s, "render", "j7", hb_minutes_ago=10)
        assert s.reap_stale() == 1

    def test_deploy_guard_is_more_conservative(self):
        """배포 가드(_worker_busy)가 reap_stale보다 여유가 커야 한다.

        여기가 뒤집히면 "죽었다고 판정된 작업을 배포가 또 건드리는" 겹침이 난다.
        """
        import inspect, pathlib, re
        from shopping_shorts.store import Store
        reap_default = inspect.signature(Store.reap_stale).parameters["minutes"].default
        sh = (pathlib.Path(__file__).resolve().parents[2] / "deploy" / "auto_deploy.sh").read_text(encoding="utf-8")
        m = re.search(r"_worker_busy\(\).*?datetime\('now','-(\d+) minutes'\)", sh, re.S)
        assert m, "auto_deploy.sh의 _worker_busy 기준을 못 찾았다"
        assert int(m.group(1)) > reap_default, (
            f"배포 가드({m.group(1)}분)가 reap_stale({reap_default}분)보다 여유가 커야 한다")
