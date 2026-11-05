"""관제 318 서버 지시서 수리 증명 시험(main 반영분) — 원본 시험 = 엔진 트랙 test_shortcl_1103_proofs.py.
수리를 되돌린 코드에서 실패를 실측하고 넣었다."""
import subprocess

import pytest


def test_318_server_leaves_shot_cap_to_render(tmp_path):
    """관제 318 '컷 길이·장면 경계 3번 연속'(#2976 외 6명): 서버 fill_shot_max 가 거친 샷 표로 max 를 채우면
    렌더 shot_cap(관문과 같은 경계 shot_starts — max 가 비었을 때만 돈다)이 막히고 회원이 줄인 max 를 다시 늘린다.
    → 서버는 max 를 쓰지 않고, 회원이 직접 적은 max 는 그대로 둔다. 렌더는 비어 있는 max 에 관문 경계 한도를 붙인다."""
    from tools.calcopy.hybrid import rules as RU
    from tools.calcopy.hybrid import render_bench as RB
    shots = {"o": [{"i": 0, "a": 0.0, "b": 20.0, "who": "main", "cx": 0.5}]}       # 거친 샷 표: 0~20초 한 샷
    M = {"cuts": {"N1": [{"src": "o.mp4", "ss": 5.6}], "N2": [{"src": "o.mp4", "ss": 1.0, "max": 1.5}]}}
    RU.fill_shot_max(M, None, {"o.mp4": [1920, 1080]}, shots, 9 / 16)
    assert "max" not in M["cuts"]["N1"][0]                 # 수리 전: 14.4(샷 표 끝까지)
    assert M["cuts"]["N2"][0]["max"] == 1.5                # 회원이 적은 한도는 그대로(수리 전: 19.0 으로 늘림)
    # 렌더 쪽: 비어 있는 max 에 shot_starts(관문 경계)로 한도 — 0~3·3~10 두 샷 영상
    v = tmp_path / "o.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=3:r=30", "-f", "lavfi", "-i",
                    "color=c=white:s=320x180:d=7:r=30", "-filter_complex", "[0][1]concat=n=2:v=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(v)], check=True)
    c = {"src": "o.mp4", "ss": 1.0}
    RB.shot_cap(c, v)
    assert c.get("max_auto") and c["max"] is not None and abs(c["max"] - 2.0) < 0.1, c



def test_318_foreign_origin_low_res_refinds_once_then_stops(monkeypatch):
    """관제 318 #3360(김효준 해외원본형): 480x360 옛 리뷰가 원본으로 정해져 제품 확인까지 감 — 하한이 자막노래형 길에만 있었다.
    받은 원본 높이 < 하한(판 min_h, 없으면 720)이면 빼고, 다 빠지면 원본 확인 탈락과 같은 길로 한 번 더 찾고, 그래도면 멈춘다."""
    from tools.calcopy.hybrid import flow as F
    monkeypatch.setattr(F, "_style", lambda v: {})
    st = {"fmt": "해외원본형", "version": "x", "log": [], "tries": {}, "origins": [{"id": "gPyUKlicXXY", "how": "찾기 같은 촬영분"}]}
    r = F.f_of_fetched(st, {"og_0": {"files": [{"name": "gPyUKlicXXY.mp4", "w": 480, "h": 360, "dur": 60}]}}, {}, {})
    assert r == {"goto": "of_find"} and st["skip_ids"] == ["gPyUKlicXXY"] and "720" in st["of_find_why"] and st["origins"] == []
    st["origins"] = [{"id": "B", "how": "찾기 같은 촬영분"}]
    with pytest.raises(F._Stop):
        F.f_of_fetched(st, {"og_0": {"files": [{"name": "B.mp4", "h": 480, "dur": 60}]}}, {}, {})
    st2 = {"fmt": "해외원본형", "version": "x", "log": [], "tries": {}, "origins": [{"id": "lo", "how": "같은 제품 다른 해외 반응"}, {"id": "hi", "how": "같은 제품 다른 해외 반응"}]}
    F.f_of_fetched(st2, {"og_0": {"files": [{"name": "lo.mp4", "h": 360, "dur": 30}]}, "og_1": {"files": [{"name": "hi.mp4", "h": 1080, "dur": 30}]}}, {}, {})
    assert [o["id"] for o in st2["origins"]] == ["hi"]          # 높은 화질만 남긴다
    st3 = {"fmt": "연예인형", "version": "x", "log": [], "tries": {}, "origins": [{"id": "z", "how": "같은 제품 다른 해외 반응"}]}
    F.f_of_fetched(st3, {"og_0": {"files": [{"name": "z.mp4", "h": 360, "dur": 30}]}}, {}, {})
    assert [o["id"] for o in st3["origins"]] == ["z"]            # 하한 없는 형식은 그대로
