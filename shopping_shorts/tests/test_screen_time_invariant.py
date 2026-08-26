"""화면 길이 불변식은 **저장 출구**에서 보장한다(2026-08-18).

사장님 지적: "두더지는 하지 마."
_fill_beat_screen_time은 계획을 만드는 경로마다 따로 불렸다(3곳). 그래서 경로가 갈릴
때마다 한쪽만 고쳐졌고 같은 병이 오늘만 다섯 번 반복됐다. 게다가 scene_first는 fill
뒤에 재픽이 화면을 갈아치워 길이가 다시 줄었다 — 만드는 쪽에서 채워도 소용이 없다.

★실측(job c431df5dba7b, scene_first=1): 비트0 화면 4.0초/필요 5.5초, 비트1 4.5/6.4,
  비트5 4.9/6.2 — fill이 도는 경로인데도 미달이 남아 있었다.
저장은 update_mix_job 하나를 지난다 = 단일 출구. 여기서 보장하면 경로가 몇 개든 상관없다.
"""
import json
import tempfile
import pathlib

from shopping_shorts.store import Store


def _store():
    d = tempfile.mkdtemp()
    return Store(str(pathlib.Path(d) / "t.db"))


def _job_with_stock(st):
    """세그가 넉넉한 job — 화면을 채울 재고가 있다."""
    segs = [{"seg_id": f"A-{i}", "start": float(i * 2), "end": float(i * 2 + 2),
             "text": f"t{i}", "scene_desc": f"장면{i}"} for i in range(10)]
    jid = "job-test-1"
    st.create_mix_job(jid, ["u"], 30, "free")
    return jid, {"A": {"segments": segs}}


def test_저장하면_화면이_대사보다_짧지_않다():
    st = _store()
    jid, extract = _job_with_stock(st)
    st.update_mix_job(jid, extract=extract)
    plan = {"beats": [{"role": "hook", "narration": "가" * 60, "target_seconds": 10.0,
                       "primary": {"seg_id": "A-1", "video_id": "A", "start": 2.0, "end": 4.0},
                       "alternates": []}]}
    st.update_mix_job(jid, edit_plan=plan)
    saved = (st.get_mix_job(jid) or {}).get("edit_plan") or {}
    b = (saved.get("beats") or [{}])[0]
    got = sum(max(0.0, (s.get("end") or 0) - (s.get("start") or 0))
              for s in [b.get("primary")] + list(b.get("alternates") or []) if s)
    assert got >= b.get("target_seconds", 0), (
        "저장된 계획이 불변식을 어겼다 — 화면 %.1f초 < 대사 %.1f초" % (got, b.get("target_seconds", 0)))


def test_출구에_보장이_배선돼_있다():
    """★구조 검사 — 만드는 쪽이 아니라 **저장 출구**에 걸려 있어야 한다.

    이게 빠지면 다시 경로마다 채우는 구조로 돌아가고, 그러면 또 한 곳이 빠진다.
    """
    import inspect
    from shopping_shorts import store as S
    src = inspect.getsource(S.Store.update_mix_job)
    assert "_ensure_screen_time" in src, "저장 출구에서 화면 길이 보장이 빠졌다"
    assert hasattr(S, "_ensure_screen_time")


def test_보장_실패가_저장을_막지_않는다():
    """fail-open — 보장은 부가가치지 저장의 전제가 아니다."""
    from shopping_shorts import store as S

    class _Broken:
        def get_mix_job(self, jid):
            raise RuntimeError("boom")

    plan = {"beats": [{"role": "hook", "narration": "x", "target_seconds": 9}]}
    assert S._ensure_screen_time(plan, _Broken(), "j") == plan
