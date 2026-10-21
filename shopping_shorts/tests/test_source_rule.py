# -*- coding: utf-8 -*-
"""재료 출처 규칙 — 사장님 10-21 "반드시 원본을 찾아서 / 다른 채널의 연예인 영상을 그대로 가져다 쓰면 절대 안 된다".
판단 주인(볼케이노형 분해 뒤): ①② 벤치·얼굴 컷 = hybrid/rules.source_rule_static(서버 지시서가 부른다) ·
③ 원본 밖 재료 컷의 장면 전환(10-21 이미도: 리뷰여왕 별 전환) = hybrid/runner_ops.source_rule_scan(영상이 있는 회원 PC 가 잰다)."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.hybrid import rules as RU  # noqa: E402


def _clip(path: Path, wipe: bool):
    """2초 회색 화면. wipe=True 면 1초에 노랑·민트가 번갈아 번쩍(남의 편집 전환)."""
    vf = "geq=lum='if(between(T,1,1.6),if(mod(N,2),230,40),120)':cb=128:cr=128" if wipe else "null"
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=gray:s=160x160:d=2:r=30", "-vf", vf, "-pix_fmt", "yuv420p", str(path)],
                   check=True, stdin=subprocess.DEVNULL)


def test_face_cut_must_come_from_origin():
    M = {"cuts": {"N1": [{"src": "6E0Mqxsxrgc.mp4", "face": "이미도"}], "N2": [{"src": "hrT1RQX_a6s.mp4", "face": "없음"}],
                  "N3": [{"src": "hrT1RQX_a6s.mp4", "face": "이미도"}], "N4": [{"src": "dL1t0o9k2Gk.mp4", "face": "없음"}]}}
    bad = RU.source_rule_static(M, {"6E0Mqxsxrgc.mp4"}, "dL1t0o9k2Gk", {})
    assert any(b.startswith("N3:") for b in bad)        # 남의 채널 영상의 연예인 얼굴
    assert any(b.startswith("N4:") for b in bad)        # 벤치 쇼츠를 재료로
    assert not any(b.startswith(("N1:", "N2:")) for b in bad)


def test_other_performer_shot():
    shots = {"6E0Mqxsxrgc": [{"i": 0, "a": 0.0, "b": 3.0, "who": "main"}, {"i": 1, "a": 3.0, "b": 6.0, "who": "other", "desc": "PD"}]}
    M = {"cuts": {"N1": [{"src": "6E0Mqxsxrgc.mp4", "ss": 1.0, "face": "이미도"}], "N2": [{"src": "6E0Mqxsxrgc.mp4", "ss": 4.0, "face": "이미도"}]}}
    bad = RU.source_rule_static(M, {"6E0Mqxsxrgc.mp4"}, "", shots)
    assert [b.split(":")[0] for b in bad] == ["N2"], bad


def test_transition_inside_other_channel_cut(tmp_path):
    from tools.calcopy.hybrid import runner_ops as R
    _clip(tmp_path / "src" / "wipe.mp4", True)
    _clip(tmp_path / "src" / "calm.mp4", False)
    T = {"cuts": [{"line": "N3", "src": "wipe.mp4", "ss": 0.3, "dur": 1.6}, {"line": "N4", "src": "calm.mp4", "ss": 0.3, "dur": 1.6}]}
    bad = R.source_rule_scan(tmp_path, T, set())
    assert [b.split(":")[0] for b in bad] == ["N3"], bad


def test_fill_shot_max_centers_main():
    shots = {"o": [{"i": 0, "a": 0.0, "b": 4.0, "who": "main", "cx": 0.75}]}
    M = {"cuts": {"N1": [{"src": "o.mp4", "ss": 1.0, "face": "이미도", "crop": "face"}]}}
    RU.fill_shot_max(M, None, {"o.mp4": [1920, 1080]}, shots, 9 / 16)
    c = M["cuts"]["N1"][0]
    assert c["max"] == 3.0 and c["center"] == "주인공"
    assert abs((c["crop"][0] + c["crop"][2] / 2) - 0.75 * 1920) <= 1      # 주인공 얼굴 가운데
