"""계획이 짧은 조각을 스스로 푼다(사장님 10-27 "걸림이 생기는 걸 없애라 · 단계별로 매끄럽게 완주").

주인: 짧은 조각 판정 = render_bench.edge_fault 하나(계획 settle_edges · 렌더 전 관문 ③ cut_boundary_gate 가 같이 부른다) ·
      푸는 곳 = render_bench.settle_edges(fit_cut·fit_lip_edges 뒤 남은 것 — 범위 넓혀 다시 맞추기 → 이웃 컷과 경계 시각 옮기기).
옛 코드: 남은 짧은 조각을 관문 ③이 반려 → Claude 가 재료 초를 손으로 고침(10-26 까르보 '컷 경계를 맞추는 중' 22번·'컷 길이' 8번).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402

FPS = RB.FPS


@pytest.fixture
def src(tmp_path, monkeypatch):
    """샷 경계 [0, 2.0, 4.0, 4.13, 9.0] 인 가짜 원본 — 4.0~4.13 은 0.13초짜리 짧은 샷(10-26 까르보 L2 꼴)."""
    p = tmp_path / "a.mp4"
    p.write_bytes(b"x")
    monkeypatch.setattr(RB, "shot_starts", lambda s: [0.0, 2.0, 4.0, 4.13, 9.0])
    monkeypatch.setattr(RB, "src_left", lambda s, t: 20.0 - t)
    monkeypatch.setattr(RB, "src_start", lambda s, t: t)
    return p


def _cut(t0, t1, ss, kind="tts", line="L1", **kw):
    return {"t0": t0, "t1": t1, "ss": ss, "src": "a.mp4", "kind": kind, "line": line, **kw}


def _refit(cuts, src_dir):
    """계획의 fit_all 과 같은 일 — t1 다시 잇고 나레 컷만 fit_cut."""
    def run(reach=0.4):
        for i, c in enumerate(cuts):
            if i + 1 < len(cuts):
                c["t1"] = cuts[i + 1]["t0"]
            if c["kind"] != "orig":
                base = float(c.get("ss_planned", c["ss"]))
                s2, k = RB.fit_cut(src_dir / c["src"], base, round(c["t1"] * FPS) - round(c["t0"] * FPS), c.get("max"), reach)
                c.pop("speed", None)
                if s2 != base:
                    c["ss_planned"], c["ss"] = base, s2
                if k < 1.0:
                    c["speed"] = k
    return run


def test_edge_fault_finds_short_tail_piece(src):
    """원음 컷이 원본 3.0~4.1초를 쓰면 4.0 경계 뒤 0.1초 조각 — 짧은 조각."""
    f = RB.edge_fault(_cut(0.0, 1.1, 3.0, kind="orig"), src.parent)
    assert f and min(f["pieces"]) < RB.MIN_PIECE_SEC


def test_lip_tail_piece_moved_to_next_cut(src):
    """원음(입 맞춤) 컷 끝 0.1초 조각 → 원음 컷을 일찍 끝내고 다음 나레 컷이 일찍 시작. 관문 ③ 반려 없음."""
    cuts = [_cut(0.0, 1.1, 3.0, kind="orig", line="L1"), _cut(1.1, 2.6, 10.0, line="L2")]
    RB.settle_edges(cuts, src.parent, 2.6, {"L1": "a.mp4"}, _refit(cuts, src.parent))
    assert all(RB.edge_fault(c, src.parent) is None for c in cuts)
    assert cuts[1]["t0"] < 1.1 and cuts[0]["t1"] == cuts[1]["t0"]
    assert cuts[0]["ss"] == 3.0                     # 입 맞춤 그대로(원본 시작 초 안 옮김)
    assert RB.cut_boundary_gate({"cuts": cuts}, {"cand_dir": str(src.parent)}) == []


def test_lip_head_piece_starts_later(src):
    """원음 컷이 3.95초부터 쓰면 첫 조각 0.05초 → 컷을 늦게 시작(원본 초도 같이), 앞 컷이 길어진다."""
    cuts = [_cut(0.0, 1.0, 10.0, line="L1"), _cut(1.0, 2.5, 3.95, kind="orig", line="L2")]
    RB.settle_edges(cuts, src.parent, 2.5, {"L2": "a.mp4"}, _refit(cuts, src.parent))
    assert all(RB.edge_fault(c, src.parent) is None for c in cuts)
    assert cuts[1]["t0"] > 1.0 and abs((cuts[1]["ss"] - 3.95) - (cuts[1]["t0"] - 1.0)) < 1e-3    # 입 맞춤 = 화면·원본 같이 옮김


def test_narration_cut_refits_with_wider_reach(src):
    """나레 컷이 0.13초 샷(4.0~4.13)에 걸리면(±0.4초 옮기기로 못 피함) 넓혀 다시 맞춰 샷 안으로."""
    cuts = [_cut(0.0, 1.5, 3.3, line="L1", max=None)]
    RB.settle_edges(cuts, src.parent, 1.5, {}, _refit(cuts, src.parent))
    assert RB.edge_fault(cuts[0], src.parent) is None
