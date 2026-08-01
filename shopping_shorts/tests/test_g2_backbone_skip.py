"""G2(2026-08-01) — 슬롯 경로에서 백본 화면 후처리 5종을 건너뛰는가.

왜 있는가: 이 5종(order_by_backbone·dedup_and_balance·ensure_sources_used·
dedup_clips_global·swap_hook_cta_for_differentiation)은 primary/alternates만 만지는데,
바로 뒤의 `_assign_timeline`(2회차)이 그 둘을 통째로 재설정해 **결과가 예외 없이 소멸**한다.
일을 하고 그 일을 버리는 구조였고, 그 과정에서 슬롯을 깨뜨려 두더지를 만들었다
(ping_pong 클립 중복 배정, CTA가 끝에서 밀려나 _fix_beat_structure를 3번 부르게 된 것).

실측 근거: `scratchpad/g2_probe.py`(반사실 대조) — 소재 5종 × 후보 16개 전부
"스킵했을 때의 최종 화면 == 실제 최종 화면", 차이 0건.

이 테스트가 지키는 것:
  1) 슬롯 경로(REWRITE_MIX=1 → tl_groups 있음)에선 5종이 **한 번도 안 불린다**
  2) 옛 경로(REWRITE_MIX=0 → tl_groups 없음)에선 종전대로 **그대로 돈다**(롤백 보존)
  3) ping_pong_reconcile은 슬롯 경로에서도 계속 돈다(나레이션 재작성 담당 — 스코프 밖)
"""
from shopping_shorts import backbone, edit_plan


_WATCHED = ["order_by_backbone", "dedup_and_balance", "ensure_sources_used",
            "dedup_clips_global", "swap_hook_cta_for_differentiation"]

# ★첫·끝 세그는 인벤토리에서 제외된다(썸네일·CTA 차단) — 후보가 참조할 수 있는 것은
#   가운데 세그뿐이라 소스마다 4개씩 둔다. 이걸 모르면 후보 0개가 나와 테스트가
#   "아무 일도 안 일어나서 통과"하는 가짜 green이 된다(초안이 실제로 그랬다).
_SOURCES = [
    {"video_id": "s0", "full_text": "가", "segments": [
        {"seg_id": "s0-0", "start": 0, "end": 1, "text": "", "scene_desc": "썸네일"},
        {"seg_id": "s0-1", "start": 1, "end": 4, "text": "가1", "scene_desc": "칸막이에 넣는",
         "action": "넣다", "shot_role": "훅"},
        {"seg_id": "s0-2", "start": 4, "end": 7, "text": "가2", "scene_desc": "고리에 거는",
         "action": "걸다", "shot_role": "사용중"},
        {"seg_id": "s0-3", "start": 7, "end": 8, "text": "", "scene_desc": "엔딩"}]},
    {"video_id": "s1", "full_text": "나", "segments": [
        {"seg_id": "s1-0", "start": 0, "end": 1, "text": "", "scene_desc": "썸네일"},
        {"seg_id": "s1-1", "start": 1, "end": 4, "text": "나1", "scene_desc": "가방 여는",
         "action": "열다", "shot_role": "문제"},
        {"seg_id": "s1-2", "start": 4, "end": 7, "text": "나2", "scene_desc": "완성된 가방",
         "action": "보이다", "shot_role": "완성"},
        {"seg_id": "s1-3", "start": 7, "end": 8, "text": "", "scene_desc": "엔딩"}]},
]

_N1 = "칸막이에 쏙 넣으면 가방 안이 정리가 되는데 이게 진짜 신세계라서 매일 쓰고 있어요"
_N2 = "가방을 열어보면 물건이 다 보이니까 뭘 찾느라 헤맬 일이 아예 없어지더라고요"
_N3 = "링크는 프로필에 걸어둘 테니까 궁금하신 분들은 댓글로 물어봐 주세요"


def _fake_call(prompt, schema, **kw):
    """슬롯 순서 질의와 후보 생성 질의를 갈라 각각 유효한 응답을 준다.

    슬롯 질의 판별은 다른 테스트와 같은 방식(schema.required == ["order"])을 쓴다 —
    프롬프트 문구로 가르면 문구가 바뀔 때 조용히 틀린 분기를 탄다."""
    if (schema or {}).get("required") == ["order"]:
        return {"order": []}        # 폴백 순서(_pick_timeline)로 tl_groups를 채운다
    return {"candidates": [{"hook": "H", "cta_keyword": "k", "beats": [
        {"role": "훅", "narration": _N1, "seg_ids": ["s0-1"], "fit": 5, "forced": False},
        {"role": "전개", "narration": _N2, "seg_ids": ["s1-1"], "fit": 5, "forced": False},
        {"role": "cta", "narration": _N3, "seg_ids": ["s1-2"], "fit": 5, "forced": False}]}]}


def _spy_backbone(monkeypatch):
    """5종 호출 횟수를 센다(동작은 원본 그대로)."""
    calls = {n: 0 for n in _WATCHED}

    def make(name):
        orig = getattr(backbone, name)

        def w(*a, **k):
            calls[name] += 1
            return orig(*a, **k)
        return w

    for n in _WATCHED:
        monkeypatch.setattr(backbone, n, make(n))
    return calls


def _run(monkeypatch, rewrite_mix):
    """계획을 만들고 **후보가 실제로 나왔는지 확인**한다.

    ★후보 0개면 루프 본문이 통째로 안 돌아 '5종 호출 0회'가 자동으로 성립한다 —
      아무 일도 안 일어나서 통과하는 가짜 green. 그래서 여기서 먼저 막는다."""
    monkeypatch.setattr(edit_plan, "REWRITE_MIX", rewrite_mix)
    res = edit_plan.build_scene_first_plan(_SOURCES, "", 20, n_candidates=1,
                                           call=_fake_call, ping_pong=True)
    cands = res.get("candidates") or []
    assert cands, "후보가 0개다 — 루프를 안 탔으므로 이 테스트는 아무것도 검증하지 못한다"
    return cands


def test_slot_path_skips_backbone_screen_stages(monkeypatch):
    """슬롯 경로: 5종이 한 번도 안 불린다 — 어차피 버려질 일을 하지 않는다."""
    calls = _spy_backbone(monkeypatch)
    _run(monkeypatch, True)
    assert calls == {n: 0 for n in _WATCHED}, f"슬롯 경로에서 5종이 불렸다: {calls}"


def test_legacy_path_still_runs_backbone_stages(monkeypatch):
    """옛 경로(REWRITE_MIX=0): 종전대로 돈다 — 롤백 경로를 깨지 않았다는 보증."""
    calls = _spy_backbone(monkeypatch)
    _run(monkeypatch, False)
    # order_by_backbone은 백본(bb) 선정에 실패하면 안 불릴 수 있어 '하나라도'로 본다.
    ran = [n for n in _WATCHED if calls[n] > 0]
    assert ran, f"옛 경로인데 5종이 하나도 안 돌았다: {calls}"


def test_slot_path_still_runs_ping_pong_reconcile(monkeypatch):
    """ping_pong_reconcile은 슬롯 경로에서도 계속 돈다 — 나레이션 재작성 담당이라 스코프 밖."""
    seen = {"n": 0}
    orig = backbone.ping_pong_reconcile

    def w(*a, **k):
        seen["n"] += 1
        return orig(*a, **k)

    monkeypatch.setattr(backbone, "ping_pong_reconcile", w)
    _run(monkeypatch, True)
    assert seen["n"] > 0, "ping_pong_reconcile까지 같이 꺼졌다(나레이션 재작성이 사라진다)"
