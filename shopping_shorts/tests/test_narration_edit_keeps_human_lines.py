# -*- coding: utf-8 -*-
"""믹스에서 대사 글자를 고쳐도 **사람이 나눈 자막 줄은 남는다**(2026-09-21 박세현님 job fe21f8a5dc71).

실측: 14:13 믹스 타임라인에서 칸2의 세 줄을 한 줄로 합침 → 14:16:15 대사 「이건건식·습식」을
「이건 건식,습식」으로 고침(narration/2) → 서버가 caption_lines=None으로 지워 자동 분할로 돌아감
→ 14:16:43 다시 합쳐야 했다. 고객: "대본 자막을 제가 손본 게 풀리는 것 같아요".
글자 몇 개 고쳤다고 줄 나눔 전체를 버릴 이유가 없다 — 안 바뀐 어절에 걸린 경계는 그대로 옮긴다.
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts import video_assemble as va

OLD = "일반행주는 매번 삶아야 해서 번거스러웠는데, 이건건식·습식 다 되고 20번을 빨아도 짱짱해요"
NEW = "일반행주는 매번 삶아야 해서 번거스러웠는데, 이건 건식,습식 다 되고 20번을 빨아도 짱짱해요"
HUMAN = ["일반행주는 매번 삶아야 해서 번거스러웠는데", "이건건식·습식 다 되고", "20번을 빨아도 짱짱해요"]
WANT = ["일반행주는 매번 삶아야 해서 번거스러웠는데,", "이건 건식,습식 다 되고", "20번을 빨아도 짱짱해요"]


def test_안_바뀐_어절의_경계는_새_문장으로_옮겨진다():
    got = va.carry_caption_lines(OLD, HUMAN, NEW)
    assert got == WANT
    assert va.cap_preset_key("".join(got)) == va.cap_preset_key(NEW)      # 저장·렌더 대조를 통과한다
    assert len(va._caption_segments(NEW, got)) == 3                        # 렌더도 3줄로 그린다


def test_경계_양쪽_어절이_다_바뀌면_그_경계만_버린다():
    old = "하나 둘 셋 넷 다섯 여섯"
    lines = ["하나 둘", "셋 넷", "다섯 여섯"]
    got = va.carry_caption_lines(old, lines, "하나 둘 삼 사 다섯 여섯")      # 셋·넷이 바뀜
    assert got == ["하나 둘", "삼 사", "다섯 여섯"], got                    # 바깥 어절이 잡아 준다
    got2 = va.carry_caption_lines(old, lines, "하나 이 삼 넷 다섯 여섯")     # 둘·셋(첫 경계 양쪽)이 바뀜
    assert got2 == ["하나 이 삼 넷", "다섯 여섯"], got2


def test_문장이_통째로_바뀌면_옮기지_않는다():
    assert va.carry_caption_lines(OLD, HUMAN, "전혀 다른 말을 새로 적었습니다 정말로요") is None
    assert va.carry_caption_lines(OLD, None, NEW) is None
    assert va.carry_caption_lines(OLD, ["한 줄뿐"], NEW) is None


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod.video_assemble, "_probe_duration", lambda p: 5.95)
    monkeypatch.setattr(appmod.mix_pipeline, "_probe_duration", lambda p: 5.95)
    return TestClient(appmod.app)


def _job(tmp_path, human=True):
    s = appmod.Store(appmod.DB_PATH)
    s.create_mix_job("j", ["u"], 30, "free")
    over = [{"video_id": "s6", "seg_id": "a", "start": 7.98, "end": 10.28},
            {"video_id": "s6", "seg_id": "b", "start": 5.09, "end": 6.79},
            {"video_id": "s2", "seg_id": "c", "start": 28.2, "end": 29.78}]
    beat = {"beat_idx": 0, "role": "body", "narration": OLD, "target_seconds": 5.95,
            "caption_lines": list(HUMAN), "caption_lines_human": human, "phrase_sync": True,
            "cap_durs": [2.7, 1.7, 1.58], "cap_lead": 0.0, "scene_override": over}
    s.update_mix_job("j", status="ready_for_review", edit_plan={"beats": [beat]})
    return s


def _beat():
    return appmod.Store(appmod.DB_PATH).get_mix_job("j")["edit_plan"]["beats"][0]


def test_대사수정_API_사람이_나눈_줄이_남는다(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path)
    r = c.post("/api/mix/scene_lab/j/narration/0", json={"text": NEW, "regen": False})
    assert r.status_code == 200 and r.json().get("saved"), r.text
    b = _beat()
    assert b["narration"] == NEW
    assert b["caption_lines"] == WANT and b["caption_lines_human"] is True
    assert b["cap_durs"] is None, "옛 음성 기준 시간은 무효 — 다시 뽑을 때 새로 잰다"
    assert va.phrase_owners(b, 3) == [0, 1, 2]


def test_대사수정_API_AI가_나눈_줄은_종전대로_버린다(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path, human=False)
    r = c.post("/api/mix/scene_lab/j/narration/0", json={"text": NEW, "regen": False})
    assert r.status_code == 200, r.text
    b = _beat()
    assert b["caption_lines"] is None and b["caption_lines_human"] is False


def test_대사를_고쳐도_줄을_더_나눠둔_칸의_장면_짝이_유지된다(tmp_path, monkeypatch):
    """4줄·3장면(짝 [0,0,1,2]가 아니라 얼린 [0,1,2,2]) 상태에서 글자만 고침 → 짝 그대로."""
    c = _client(tmp_path, monkeypatch)
    s = _job(tmp_path)
    job = s.get_mix_job("j")
    b = job["edit_plan"]["beats"][0]
    va.ensure_clip_anchor(b)                                         # 3줄=3장면 1:1
    b["caption_lines"] = HUMAN[:2] + ["20번을 빨아도", "짱짱해요"]      # 마지막 줄을 나눔
    s.update_mix_job("j", edit_plan=job["edit_plan"])
    assert va.phrase_owners(_beat(), 3) == [0, 1, 2, 2]
    r = c.post("/api/mix/scene_lab/j/narration/0", json={"text": NEW, "regen": False})
    assert r.status_code == 200, r.text
    nb = _beat()
    assert len(nb["caption_lines"]) == 4
    assert va.phrase_owners(nb, 3) == [0, 1, 2, 2], "글자를 고쳤다고 장면이 밀리면 안 된다"
