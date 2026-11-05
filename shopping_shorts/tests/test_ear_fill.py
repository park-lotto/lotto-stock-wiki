# -*- coding: utf-8 -*-
"""받아쓰기 빈 답 → agy 직접 듣기로 나레 유무 채우기(bench_member.ear_fill) · 나레 꼴 판단 한 곳(remake.narration_kind)을 대본 골격도 부른다(관제 319 11-06).
실측 근거: 스냅봤니 Z956·CZd 제미나이 받아쓰기 빈 답 — agy 3/3 나레이션 없음·배경음악+현장음."""
import json

from tools.calcopy.engine import bench_member as BM
from tools.calcopy.engine import script_engine as SE

EMPTY = {"audio": {"composition": {"failed": "받아쓰기 빈 답"}}, "voice_rules": {"failed": "받아쓰기 빈 답"}}


def test_ear_fill_sets_narration_none_from_agy(tmp_path):
    J = json.loads(json.dumps(EMPTY))
    jp = tmp_path / "뜯기.json"
    ans = {"answer": {"speech": False, "narration": "없음", "captions_read_aloud": False, "bgm": True, "bgm_mood": "경쾌", "source_audio": True, "why": "자막을 읽는 목소리 없음"}}
    r = BM.ear_fill(J, tmp_path / "v.mp4", jp, ask=lambda v, a, s: ans)
    assert r["filled"] and r["narration"] == "none"
    c = json.loads(jp.read_text(encoding="utf-8"))["audio"]["composition"]
    assert c["narration"] == "none" and c["bgm"]["present"] and c["source_audio_kept"] and c["was"] == "받아쓰기 빈 답"


def test_ear_fill_leaves_other_and_agy_failure():
    J = {"audio": {"composition": {"narration": "tts"}}}
    assert BM.ear_fill(J, "v.mp4", ask=lambda *a: 1 / 0)["filled"] is False       # 빈 답이 아니면 묻지 않는다
    J = json.loads(json.dumps(EMPTY))
    r = BM.ear_fill(J, "v.mp4", ask=lambda *a: {"error": "agy_timeout"})
    assert r["filled"] is False and J["audio"]["composition"]["failed"] and J["audio"]["composition"]["ear_failed"] == "agy_timeout"


def test_skeleton_mode_follows_narration_kind(tmp_path):
    J = {"audio": {"composition": {"narration": "none"}}, "voice_rules": {"failed": "받아쓰기 빈 답"}}   # ear_fill 뒤 꼴 — voice_rules 는 실패로 남는다
    tj = tmp_path / "뜯기.json"
    tj.write_text(json.dumps(J, ensure_ascii=False), encoding="utf-8")
    sk = SE.skeleton({"tteutgi": str(tj), "chdir": tmp_path}, None, ["훅(질문·상황)", "전개", "마무리"])
    assert sk["mode"] == "captions"
