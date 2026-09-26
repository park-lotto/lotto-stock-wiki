# -*- coding: utf-8 -*-
"""업체 결과 받기가 끊겨도 **두 번 과금되지 않는다** (2026-09-27 사장님 "고쳐야지").

실측(2026-09-26 16:19): 고급 청소가 업체에서 끝났는데(크레딧 차감) 결과 다운로드에서 연결이 끊겨
job이 failed → 고객이 다시 누르면 새로 업로드·과금. 작업 번호(task_id)로 재조회하면 공짜로 받을 수 있었다.
"""
import urllib.request
from pathlib import Path

import pytest

from shopping_shorts import vmake_client as vc


class _Client:
    def __init__(self, log):
        self.log = log
        self.poll_url = "https://r/poll.mp4"
        self.poll_fail = False
        self.crash_after_submit = False

    def fetch_config(self, version=None):
        pass

    def run_task(self, task_name, image_path, params=None, on_async_submitted=None):
        self.log.append(("run", task_name))
        if on_async_submitted:
            on_async_submitted("t_123")
        if self.crash_after_submit:
            raise KeyboardInterrupt("워커가 죽었다")          # 제출 뒤 프로세스가 끊긴 상황
        return {"output_urls": ["https://r/first.mp4"], "task_id": "t_123"}

    def poll_task_status(self, task_id):
        self.log.append(("poll", task_id))
        if self.poll_fail:
            raise ConnectionError("조회도 끊김")
        return {"output_urls": [self.poll_url], "task_id": task_id}


@pytest.fixture
def env(tmp_path, monkeypatch):
    log, fail_urls = [], set()
    cl = _Client(log)
    monkeypatch.setattr(vc, "_new_api_client", lambda ak, sk: cl)
    monkeypatch.setattr(vc.time, "sleep", lambda s: None)
    monkeypatch.setattr(vc, "_seconds", lambda p: 6.33)

    def _get(url, dst):
        log.append(("get", url))
        if url in fail_urls:
            raise ConnectionAbortedError("10053")
        Path(dst).write_bytes(b"v" * 4096)
    monkeypatch.setattr(urllib.request, "urlretrieve", _get)
    src = tmp_path / "in.mp4"; src.write_bytes(b"i" * 4096)
    return cl, log, fail_urls, src, tmp_path


def _call(src, tmp, key="final:final_clean_abc.mp4"):
    return vc.remove_subtitles(str(src), "ak:sk", str(tmp / "out.mp4"), tier="pro", resume_key=key)


def test_download_retries_then_succeeds(env, monkeypatch):
    cl, log, fail, src, tmp = env
    n = {"k": 0}
    orig = urllib.request.urlretrieve

    def flaky(url, dst):
        n["k"] += 1
        if n["k"] == 1:
            raise ConnectionAbortedError("10053")
        return orig(url, dst)
    monkeypatch.setattr(urllib.request, "urlretrieve", flaky)
    assert _call(src, tmp).endswith("out.mp4")
    assert [x for x in log if x[0] == "run"] == [("run", "SKM0005")] and n["k"] == 2
    assert not [x for x in log if x[0] == "poll"]          # 재조회 없이 그냥 다시 받아서 끝났다
    assert not (tmp / "out.mp4.part").exists()


def test_expired_url_refetched_by_task_id_without_new_upload(env):
    cl, log, fail, src, tmp = env
    fail.add("https://r/first.mp4")                      # 첫 주소는 끝까지 안 받아진다
    assert _call(src, tmp).endswith("out.mp4")
    assert [x[0] for x in log if x[0] in ("run", "poll")] == ["run", "poll"]     # 새로 맡기지 않았다


def test_total_failure_keeps_ledger_and_retry_click_resumes_free(env):
    from shopping_shorts.app import clean_failure_kind
    cl, log, fail, src, tmp = env
    fail.update({"https://r/first.mp4", "https://r/poll.mp4"})
    with pytest.raises(RuntimeError) as ei:
        _call(src, tmp)
    assert "추가 비용 없이" in str(ei.value)
    assert clean_failure_kind(str(ei.value)) == "interrupted"       # 화면: "다시 누르면 된다"
    assert vc._pending_get(tmp / "out.mp4", "final:final_clean_abc.mp4|pro|SKM0005")["task_id"] == "t_123"
    # 고객이 다시 누른다 — 이번엔 연결이 된다
    fail.clear(); log.clear()
    assert _call(src, tmp).endswith("out.mp4")
    assert ("run", "SKM0005") not in log and ("poll", "t_123") in log               # ★업로드·과금 0
    assert vc._pending_get(tmp / "out.mp4", "final:final_clean_abc.mp4|pro|SKM0005") is None


def test_worker_death_after_submit_resumes_on_next_click(env):
    cl, log, fail, src, tmp = env
    cl.crash_after_submit = True
    with pytest.raises(KeyboardInterrupt):
        _call(src, tmp)
    cl.crash_after_submit = False; log.clear()
    _call(src, tmp)
    assert ("run", "SKM0005") not in log and ("poll", "t_123") in log


def test_different_job_is_not_resumed(env):
    cl, log, fail, src, tmp = env
    fail.update({"https://r/first.mp4", "https://r/poll.mp4"})
    with pytest.raises(RuntimeError):
        _call(src, tmp, key="final:final_clean_abc.mp4")
    fail.clear(); log.clear()
    _call(src, tmp, key="final:final_clean_OTHER.mp4")               # 장면을 바꿨다 = 다른 작업
    assert ("run", "SKM0005") in log


def test_resumed_result_with_wrong_length_is_discarded(env, monkeypatch):
    cl, log, fail, src, tmp = env
    fail.update({"https://r/first.mp4", "https://r/poll.mp4"})
    with pytest.raises(RuntimeError):
        _call(src, tmp)
    fail.clear(); log.clear()
    lens = iter([6.33, 20.0])                                         # 보낸 것 6.33초, 이어받은 것 20초
    monkeypatch.setattr(vc, "_seconds", lambda p: next(lens, 6.33))
    _call(src, tmp)
    assert ("run", "SKM0005") in log                                  # 엉뚱한 결과를 쓰지 않고 새로 맡겼다


def test_sync_completed_task_without_callback_still_resumes_free(env):
    """★실측 사고(2026-09-27 03:40·03:54): 짧은 영상은 업체가 동기로 끝내 SDK가 제출 콜백을 안 부른다.
    콜백만 믿으면 장부가 비어 재클릭이 재과금된다 — 결과를 받은 직후 장부를 써야 한다."""
    cl, log, fail, src, tmp = env
    orig = cl.run_task

    def run_sync(task_name, image_path, params=None, on_async_submitted=None):
        cl.log.append(("run", task_name))
        return {"output_urls": ["https://r/first.mp4"], "task_id": "t_sync"}     # 콜백 없이 바로 결과
    cl.run_task = run_sync
    fail.update({"https://r/first.mp4", "https://r/poll.mp4"})
    with pytest.raises(RuntimeError):
        _call(src, tmp)
    assert vc._pending_get(tmp / "out.mp4", "final:final_clean_abc.mp4|pro|SKM0005")["task_id"] == "t_sync"
    fail.clear(); log.clear()
    assert _call(src, tmp).endswith("out.mp4")
    assert ("run", "SKM0005") not in log and ("poll", "t_sync") in log            # ★재업로드·재과금 0
    cl.run_task = orig


def test_no_resume_key_keeps_old_call_shape(env):
    """이름표가 없으면 종전 호출 모양 그대로(on_async_submitted 안 넘김) — 장부도 안 쓴다."""
    cl, log, fail, src, tmp = env
    vc.remove_subtitles(str(src), "ak:sk", str(tmp / "out.mp4"), tier="pro")
    assert not (tmp / vc._PENDING_FILE).exists()
