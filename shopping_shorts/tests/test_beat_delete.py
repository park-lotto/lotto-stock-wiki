# -*- coding: utf-8 -*-
"""문장 칸 삭제 (2026-09-03 고객 이유준 "음성이 두 번 되어서 마지막 것을 삭제해야 한다").

여태 칸은 고치거나 다시 뽑을 수만 있었다. 대본이 중복 생성돼 같은 말이 두 번 들어가면
글자를 지우려 해도 저장 API가 "대본이 비었어요"로 막아 앱 안에 빠져나갈 구멍이 없었다.

여기서 못 박는 것:
1. 지운 칸만 빠지고 **남은 칸의 beat_idx는 그대로**다 — mp3 이름(beat_{idx}_*.mp3)과
   tts_paths가 전부 beat_idx로 짝을 찾으므로, 번호를 당기면 남의 음성을 물고 간다.
2. 생성·렌더 중에는 못 지운다(narration 저장과 같은 가드).
3. 마지막 한 칸은 못 지운다(빈 영상이 된다).
"""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "run_render", lambda *a, **k: None)
    return TestClient(app_module.app), Store(db)


def _beat(i, text):
    return {"beat_idx": i, "role": "훅", "narration": text, "target_seconds": 2,
            "primary": {"video_id": "s0", "seg_id": f"s0-{i}", "start": 0.0, "end": 2.0},
            "alternates": [], "effect": "cut"}


def _seed(store, status="ready_for_review", n=3):
    store.create_mix_job("j1", ["u0"], 20, "free")
    store.update_mix_job("j1", status=status, edit_plan={
        "structure": "free",
        "beats": [_beat(i, f"문장{i}") for i in range(n)],
        "plagiarism_flags": []})


def test_지운_칸만_빠지고_남은_번호는_그대로다(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    r = client.post("/api/mix/scene_lab/j1/beat/1/delete")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] and r.json()["left"] == 2
    beats = store.get_mix_job("j1")["edit_plan"]["beats"]
    assert [b["beat_idx"] for b in beats] == [0, 2], "번호를 당기면 남은 칸이 남의 음성을 문다"
    assert [b["narration"] for b in beats] == ["문장0", "문장2"]


def test_없는_칸은_404(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    assert client.post("/api/mix/scene_lab/j1/beat/9/delete").status_code == 404


def test_마지막_한_칸은_못_지운다(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store, n=1)
    r = client.post("/api/mix/scene_lab/j1/beat/0/delete")
    assert r.status_code == 422
    assert len(store.get_mix_job("j1")["edit_plan"]["beats"]) == 1


def test_생성중에는_못_지운다(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store, status=app_module._MIX_ACTIVE_STAGES[0])
    r = client.post("/api/mix/scene_lab/j1/beat/1/delete")
    assert r.status_code == 409
    assert len(store.get_mix_job("j1")["edit_plan"]["beats"]) == 3


def test_뒷단계_완성본이_무효화된다(monkeypatch, tmp_path):
    """지운 칸이 든 옛 mp4를 그대로 쓰면 9단계 완성본이 지운 문장을 계속 말하고,
    캡컷은 그 옛 완성본을 새 타임라인으로 잘라(split_final_into_beat_clips) 어긋난다."""
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    store.update_mix_job("j1", video_path="/w/final.mp4", clean_video_path="/w/clean.mp4",
                         fx_path="/w/fx.mp4", fx_status="done")
    r = client.post("/api/mix/scene_lab/j1/beat/1/delete")
    assert r.status_code == 200, r.text
    job = store.get_mix_job("j1")
    assert not job.get("video_path"), "옛 완성본이 남으면 지운 문장이 계속 나온다"
    assert not job.get("clean_video_path"), "옛 청소 조립본을 새 타임라인으로 자르면 캡컷이 어긋난다"
    assert not job.get("fx_path") and not job.get("fx_status")


def test_소스별_청소본은_안_건드린다(monkeypatch, tmp_path):
    """clean_sources는 소스 영상 기준이라 칸과 무관 — 지우면 VMake를 다시 태워 돈이 나간다."""
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    store.update_mix_job("j1", clean_status="ready")
    before = store.get_mix_job("j1").get("clean_sources")
    client.post("/api/mix/scene_lab/j1/beat/1/delete")
    after = store.get_mix_job("j1")
    assert after.get("clean_sources") == before
    assert after.get("clean_status") == "ready", "clean_status를 지우면 자막제거를 다시 돌리게 된다"


# ── 확정대본 모드에서 지운 칸이 되살아난다 (2026-09-06 고객 재제보) ─────────────
# job 3ec9df659411(work c55d6f8988e8, 26.피규어) — 09-06 새벽 beat_idx 중복을 고친
# 뒤에도 "삭제가 안 된다"가 그대로였다. 라이브 실측으로 갈라 보니 **다른 층**이었다:
#
#   삭제 필터 직후(app.py가 넘기는 값)  : 6칸 [0,1,2,3,4,6]
#   ① enforce_scripted_narration 후    : 6칸 [0,1,2,3,4,6]
#   ② enforce_script_order 후          : 7칸 [0,1,2,3,4,5,6]  ← 여기서 부활
#
# store.update_mix_job이 저장 직전 _ensure_screen_time을 부르고, 그 안의
# enforce_script_order가 "확정대본 7줄인데 칸이 6개다 → 줄마다 칸 하나로 다시 짜라"
# (edit_plan.py `_lines_mode and len(targets) != len(sents)` 분기)로 지운 칸을 되살린다.
#
# ★API는 ok:True, deleted:5를 반환하면서 실제로는 안 지워졌다(left:7) — 조용한 실패라
#   화면은 "지웠다"고 하고 새로고침하면 그대로 있었다.
#
# 위쪽 기존 테스트들이 못 잡은 이유: given_script 없이 seed하므로 enforce_script_order가
# 첫 줄에서 곧장 되돌아간다(빈 대본 = 검사 대상 아님). 확정대본을 줘야 재현된다.

_SCRIPT = "\n".join(f"문장{i}입니다." for i in range(3))


def _seed_scripted(store, n=3):
    """확정대본(given_script) 모드 — 고객 job과 같은 조건.

    ★extract가 있어야 한다. _ensure_screen_time은 extract가 비면 첫머리에서 그대로
      돌아가므로(store.py `if not extract: return plan`), 없으면 확정대본 검사 자체가
      돌지 않아 이 버그가 재현되지 않는다(위 기존 테스트들이 못 잡은 이유이기도 하다).
    """
    store.create_mix_job("j2", ["u0"], 20, "free", given_script=_SCRIPT)
    store.update_mix_job("j2", status="ready_for_review", extract={
        "s0": {"segments": [
            {"seg_id": f"s0-{i}", "start": float(i) * 2, "end": float(i) * 2 + 2.0,
             "text": "", "scene_desc": f"장면{i}"} for i in range(n + 3)]}},
        edit_plan={
            "structure": "free",
            "beats": [_beat(i, f"문장{i}입니다.") for i in range(n)],
            "plagiarism_flags": []})


def test_확정대본_모드에서도_지운_칸이_되살아나지_않는다(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed_scripted(store)
    r = client.post("/api/mix/scene_lab/j2/beat/1/delete")
    assert r.status_code == 200, r.text
    beats = store.get_mix_job("j2")["edit_plan"]["beats"]
    idxs = [b["beat_idx"] for b in beats]
    assert 1 not in idxs, f"지운 칸이 확정대본 검사로 되살아났다: {idxs}"
    assert idxs == [0, 2], idxs


def test_삭제_응답의_left가_실제_저장된_칸수와_같다(monkeypatch, tmp_path):
    """ok:True인데 안 지워지는 조용한 실패를 막는다 — 응답과 DB가 어긋나면 안 된다."""
    client, store = _client(monkeypatch, tmp_path)
    _seed_scripted(store)
    r = client.post("/api/mix/scene_lab/j2/beat/1/delete")
    assert r.status_code == 200, r.text
    left = r.json()["left"]
    real = len(store.get_mix_job("j2")["edit_plan"]["beats"])
    assert left == real, f"응답 left={left} 인데 실제 저장은 {real}칸"


def test_삭제해도_남은_칸의_대사는_안_바뀐다(monkeypatch, tmp_path):
    """비례 재배분이 돌면 남은 칸에 옛 문장이 쪼개져 붙는다(2026-08-25 실사고와 같은 모양)."""
    client, store = _client(monkeypatch, tmp_path)
    _seed_scripted(store)
    client.post("/api/mix/scene_lab/j2/beat/1/delete")
    beats = store.get_mix_job("j2")["edit_plan"]["beats"]
    assert [b["narration"] for b in beats] == ["문장0입니다.", "문장2입니다."]
