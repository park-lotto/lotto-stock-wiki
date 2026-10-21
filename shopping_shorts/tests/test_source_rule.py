# -*- coding: utf-8 -*-
"""재료 출처 규칙(customer.source_rule_bad) — 사장님 10-21 "반드시 원본을 찾아서 / 다른 채널의 연예인 영상을 그대로 가져다 쓰면 절대 안 된다".
벤치는 재료가 아니다 · 사람 얼굴 컷은 원본 파일만 · 원본 밖 재료 컷에 장면 전환(10-21 이미도: 리뷰여왕 별 전환)이 섞이면 걸린다."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _piece(tmp_path):
    os.environ["CALCOPY_DATA_DIR"] = str(tmp_path)
    from tools.calcopy.hybrid import customer as C
    P = C.Piece("aaaaaaaaaaaa")
    (P.W / "src").mkdir(parents=True, exist_ok=True)
    P.s.update(bench={"id": "dL1t0o9k2Gk"}, origin={"files": [str(P.W / "src" / "6E0Mqxsxrgc.mp4")]})
    return C, P


def _clip(path: Path, wipe: bool):
    """2초 회색 화면. wipe=True 면 1초에 노랑·민트가 번갈아 번쩍(남의 편집 전환)."""
    vf = "geq=lum='if(between(T,1,1.6),if(mod(N,2),230,40),120)':cb=128:cr=128" if wipe else "null"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=gray:s=160x160:d=2:r=30", "-vf", vf, "-pix_fmt", "yuv420p", str(path)],
                   check=True, stdin=subprocess.DEVNULL)


def test_face_cut_must_come_from_origin(tmp_path):
    C, P = _piece(tmp_path)
    M = {"cuts": {"N1": [{"src": "6E0Mqxsxrgc.mp4", "face": "이미도"}], "N2": [{"src": "hrT1RQX_a6s.mp4", "face": "없음"}],
                  "N3": [{"src": "hrT1RQX_a6s.mp4", "face": "이미도"}], "N4": [{"src": "dL1t0o9k2Gk.mp4", "face": "없음"}]}}
    bad = C.source_rule_bad(P, M)
    assert any(b.startswith("N3:") for b in bad)        # 남의 채널 영상의 연예인 얼굴
    assert any(b.startswith("N4:") for b in bad)        # 벤치 쇼츠를 재료로
    assert not any(b.startswith(("N1:", "N2:")) for b in bad)


def test_transition_inside_other_channel_cut(tmp_path):
    C, P = _piece(tmp_path)
    _clip(P.W / "src" / "wipe.mp4", True)
    _clip(P.W / "src" / "calm.mp4", False)
    M = {"cand_dir": str(P.W / "src"), "cuts": {}}
    T = {"cuts": [{"line": "N3", "src": "wipe.mp4", "ss": 0.3, "dur": 1.6}, {"line": "N4", "src": "calm.mp4", "ss": 0.3, "dur": 1.6}]}
    bad = C.source_rule_bad(P, M, T)
    assert [b.split(":")[0] for b in bad] == ["N3"], bad
