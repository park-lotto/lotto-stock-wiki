"""10-30 얜샷템 회원 시험(BRa5Iv4A3Y8 최화정): 썸네일 A(최화정 인물순간)가 카드 크기 0.19<0.2 로 탈락 · B 는 물건 → 성시경 '짤반응' C 만
기준 얼굴이 돼 최화정 본인 컷 7개가 '연예인 아닌 얼굴'로 렌더 3번 헛돌고 멈춤. 기준 = 인물순간 카드(크기 관문과 따로), 짤반응은 기준이 아니다.
실데이터 재현: 그 편 작업 폴더 복사본(C:/t/yan_chk) 계획 관문 — 고친 뒤 얼굴 반려 7건 → 0건(남은 건 카드 A·B 크기·얼굴 없음 = 진짜 관문)."""
import json

from tools.calcopy.hybrid import render_bench as RB, thumb as TH
from shopping_shorts.channelkit import vision as V


def _setup(tmp_path, monkeypatch, opts, ok_ids):
    (tmp_path / "썸네일.json").write_text(json.dumps({"options": opts}), encoding="utf-8")
    monkeypatch.setattr(TH, "card_faces", lambda st, doc, T, cd: [{"id": o["id"], "ok": o["id"] in ok_ids} for o in opts])
    monkeypatch.setattr(TH, "card_scene_frame", lambda o, T, cd, win: (o["id"], ""))
    monkeypatch.setattr(V, "faces_all", lambda im: [({"h": 0.3}, "emb_" + im)])
    monkeypatch.setattr(RB, "frame_window", lambda fr: (0, 0, 1080, 1080))


def test_anchor_is_person_moment_even_if_card_gate_failed(tmp_path, monkeypatch):
    opts = [{"id": "A", "axis": "인물순간"}, {"id": "B", "axis": "물건근접"}, {"id": "C", "axis": "짤반응"}]
    _setup(tmp_path, monkeypatch, opts, ok_ids={"C"})
    assert RB.face_anchors({"frame": {}}, tmp_path, {}, tmp_path) == ["emb_A"]


def test_without_person_moment_reaction_card_is_not_anchor(tmp_path, monkeypatch):
    opts = [{"id": "B", "axis": "물건근접"}, {"id": "C", "axis": "짤반응"}, {"id": "D", "axis": "황당사실"}]
    _setup(tmp_path, monkeypatch, opts, ok_ids={"C", "D"})
    assert RB.face_anchors({"frame": {}}, tmp_path, {}, tmp_path) == ["emb_D"]
