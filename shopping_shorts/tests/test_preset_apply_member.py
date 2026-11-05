# -*- coding: utf-8 -*-
"""11-04 회원 묶음 렌더(8/10)가 preset_make → preset_save import 로 멈췄다(ImportError: cannot import name 'preset_save').
preset_save(프리셋 만드는 기술)는 회원 PC 에 안 보낸다 — 적용(load·apply·규칙·글꼴)만 묶음 안 preset_apply 로 옮겼다.
HAND_SERVER_ONLY 가 preset_save 를 가려 의존 검사가 못 잡던 구멍도 닫았다(이제 회원 쪽이 부르면 빨강)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "claude_portal"))
import engine_bundle as EB  # noqa: E402

PRESET = ROOT / "channel" / "humorshowshow" / "preset" / "썰템쇼_화자썰"
MEMBER_RENDER = ("tools/calcopy/engine/preset_make.py", "tools/calcopy/hybrid/render_itssum.py")
RENDER_ROOTS = MEMBER_RENDER + ("tools/calcopy/engine/preset_gates.py",)   # 기본 렌더 길 출발점(PC제작형 c_pm 이 preset_gates 를 부른다)


def test_member_render_does_not_import_preset_save():
    for f in MEMBER_RENDER:
        s = (ROOT / f).read_text(encoding="utf-8")
        assert "engine import preset_save" not in s, f
    assert EB.hand_unresolved(ROOT) == []


def test_member_importing_preset_save_is_caught(monkeypatch, tmp_path):
    # 사보타주: preset_make 가 다시 preset_save 를 부르면 묶음 검사가 빨강이어야 한다(11-04 엔 HAND_SERVER_ONLY 가 가려 초록이었다)
    eng = tmp_path / "eng"
    for r in list(EB.HAND) + ["tools/calcopy/engine/preset_save.py", "shopping_shorts/calcopy_frame/preset_apply.py",
                              "shopping_shorts/calcopy_frame/per_video.py", "shopping_shorts/calcopy_frame/schema.py"]:
        if (ROOT / r).is_file():
            (eng / r).parent.mkdir(parents=True, exist_ok=True)
            (eng / r).write_bytes((ROOT / r).read_bytes())
    # 11-05: main 관제 319 고급반 명령(runner_ops.c_bm_*)이 preset_save 를 고급반 꾸러미로 빌려 쓰므로 HAND_SERVER_ONLY 가 preset_save 를 가린다.
    #   그래서 묶음 전체가 아니라 '기본 렌더 길'(preset_make·render_itssum·preset_gates 출발, preset_save 를 가리지 않음)로 본다(Jev 0.79·위험 0.19)
    ps = "tools/calcopy/engine/preset_save.py"
    monkeypatch.setattr(EB, "HAND", RENDER_ROOTS)
    monkeypatch.setattr(EB, "HAND_SERVER_ONLY", {x for x in EB.HAND_SERVER_ONLY if x != ps})
    assert ps not in EB.hand_deps(eng)                     # 사보타주 전 = 렌더 길은 preset_save 에 안 닿는다
    pm = eng / "tools/calcopy/engine/preset_make.py"
    pm.write_text(pm.read_text(encoding="utf-8") + "\n\ndef _bad():\n    from tools.calcopy.engine import preset_save as P\n", encoding="utf-8")
    assert EB.hand_deps(eng).get(ps) == "tools/calcopy/engine/preset_make.py"


def test_one_owner_and_applies_pc_deliverable():
    """주인 하나(preset_save·to_frame 은 preset_apply 를 다시 내보낼 뿐) + PC 납품본(작품3) frame_vars 로 렌더와 같은 길(preset_make.snapshot_and_timeline)을 탄다."""
    from shopping_shorts.calcopy_frame import preset_apply as A
    from tools.calcopy.engine import preset_make as PM
    from tools.calcopy.engine import preset_save as P
    from tools.calcopy.engine import to_frame as T
    assert P.apply is A.apply and P.load is A.load and P.apply_rules is A.apply_rules     # 두 벌 금지
    assert T.font_faces is A.font_faces and T._pil_font is A._pil_font
    assert PM.frame_spans.__module__ == PM.__name__
    import json
    S = json.loads((ROOT / "channel" / "humorshowshow" / "작품3_태양의맛썬" / "대본.json").read_text(encoding="utf-8"))
    pre, M = A.load(PRESET)
    F = A.apply(pre, None, dict(S["frame_vars"]), M["variable_stats"], None, M["rules"])
    title = next(l for f in F["frames"] for l in f["layers"] if l.get("role") == "title")
    assert title["text"] and title["size"] > 0 and title["line_h"] > 0           # 규칙(fill_w·글꼴 재기)까지 돌았다
