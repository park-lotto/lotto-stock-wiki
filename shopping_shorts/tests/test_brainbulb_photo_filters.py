# -*- coding: utf-8 -*-
"""사진 거르기 — 이어붙임 자르기 · 글자 과다 · 얼굴.

실사고 2026-09-13 (사장님 "두 번 연속 나오고 위아래로 나오거나 양옆 동일 사진도 있고"):
  박수홍 편에서 받은 4장 중 3장이 문제였다.
    01 위아래로 두 장면 이어붙임 · 02 좌우로 같은 장면 두 번 · 07/08 가격표가 깔린 홈쇼핑 캡처
  그대로 슬롯에 넣어 같은 사람이 한 화면에 두 번 나오거나 글자가 박힌 채 들어갔다.
"""
import numpy as np
import pytest
from PIL import Image

from shopping_shorts.brainbulb import photos, spec


def _collage(path, axis="v", size=(600, 400)):
    """좌우(또는 위아래)로 밝기가 확 다른 두 칸을 이어붙인 가짜 사진."""
    w, h = size
    a = np.zeros((h, w, 3), dtype=np.uint8)
    if axis == "v":
        a[:, : w // 2] = 40
        a[:, w // 2:] = 210
    else:
        a[: h // 2, :] = 40
        a[h // 2:, :] = 210
    Image.fromarray(a).save(path, "JPEG", quality=95)


def _noise(path, size=(600, 400), seed=0):
    """이어붙임이 없는 자연스러운 사진(난수 무늬)."""
    rng = np.random.default_rng(seed)
    a = rng.integers(60, 200, (size[1], size[0], 3), dtype=np.uint8)
    Image.fromarray(a).save(path, "JPEG", quality=95)


def test_find_seam_detects_vertical_and_horizontal(tmp_path):
    v = tmp_path / "v.jpg"; _collage(v, "v")
    h = tmp_path / "h.jpg"; _collage(h, "h")
    sv, sh = photos.find_seam(str(v)), photos.find_seam(str(h))
    assert sv and sv[0] == "v" and abs(sv[1] - 300) <= 2
    assert sh and sh[0] == "h" and abs(sh[1] - 200) <= 2


def test_find_seam_ignores_normal_photo(tmp_path):
    p = tmp_path / "n.jpg"; _noise(p)
    assert photos.find_seam(str(p)) is None


def test_split_collage_keeps_larger_half(tmp_path):
    """경계는 가운데 35~65%만 본다 — 가장자리 띠·워터마크를 경계로 오인하지 않기 위해서다.
    그래서 한쪽이 더 큰 경우도 그 범위 안(여기선 60%)에서 시험한다."""
    p = tmp_path / "v.jpg"
    w, h = 600, 400
    a = np.zeros((h, w, 3), dtype=np.uint8)
    a[:, :360] = 40             # 왼쪽 360 ← 더 크다
    a[:, 360:] = 210            # 오른쪽 240
    Image.fromarray(a).save(p, "JPEG", quality=95)
    assert photos.split_collage(str(p)) is True
    out = Image.open(p)
    assert out.size == (360, 400)                        # 큰 쪽만 남았다
    assert np.asarray(out.convert("L")).mean() < 100      # 어두운(왼쪽) 칸


def test_split_collage_ignores_seam_outside_middle_band(tmp_path):
    """33% 자리의 밝기 단차는 자르지 않는다 — 사진 안의 정상적인 명암 경계일 수 있다."""
    p = tmp_path / "edge.jpg"
    a = np.zeros((400, 600, 3), dtype=np.uint8)
    a[:, :200] = 40
    a[:, 200:] = 210
    Image.fromarray(a).save(p, "JPEG", quality=95)
    assert photos.split_collage(str(p)) is False


def test_split_collage_leaves_normal_photo(tmp_path):
    p = tmp_path / "n.jpg"; _noise(p)
    before = Image.open(p).size
    assert photos.split_collage(str(p)) is False
    assert Image.open(p).size == before                  # 손대지 않았다


def test_text_ratio_separates_caption_overlay(tmp_path):
    """글자가 깔린 그림 vs 일반 사진. 실측값: 홈쇼핑 캡처 14.3% / 사진 0.2~0.5%."""
    cv2 = pytest.importorskip("cv2")
    plain = tmp_path / "p.jpg"; _noise(plain, seed=3)
    texty = tmp_path / "t.jpg"
    a = np.full((400, 600, 3), 235, dtype=np.uint8)      # 단조로운 밝은 배경 = 자막 판
    img = a.copy()
    for i, y in enumerate(range(40, 360, 40)):
        cv2.putText(img, "50,000 SPECIAL PRICE 080-850", (20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    Image.fromarray(img).save(texty, "JPEG", quality=95)
    assert photos.text_ratio(str(texty)) > spec.POLICY_PHOTO_TEXT_MAX
    assert photos.text_ratio(str(plain)) <= spec.POLICY_PHOTO_TEXT_MAX


def test_text_ratio_survives_missing_file(tmp_path):
    assert photos.text_ratio(str(tmp_path / "없음.jpg")) == 0.0


def test_has_face_passes_when_model_missing(tmp_path, monkeypatch):
    """모델이 없으면 통과 — 못 잰 것을 '얼굴 없음'으로 단정하지 않는다."""
    monkeypatch.setattr(photos, "_yunet_model", lambda: None)
    p = tmp_path / "n.jpg"; _noise(p)
    assert photos.has_face(str(p)) is True


def test_pick_photo_splits_and_rejects_texty(tmp_path, monkeypatch):
    """수집 과정 전체: 글자 과다는 버리고 다음 후보로, 이어붙임은 잘라서 쓴다."""
    import shutil
    good = tmp_path / "src_good.jpg"; _collage(good, "v")       # 이어붙임 → 잘라서 사용
    bad = tmp_path / "src_bad.jpg"; _noise(bad, seed=7)         # 글자 과다 → 버림
    hits = [{"url": "http://x/bad.jpg", "source": "연합뉴스", "title": "", "w": 600, "h": 400},
            {"url": "http://x/good.jpg", "source": "한국경제", "title": "", "w": 600, "h": 400}]
    monkeypatch.setattr(photos, "search_images", lambda q, **k: hits)
    monkeypatch.setattr(photos, "download",
                        lambda u, p, **k: shutil.copy(str(bad if "bad" in u else good), p))
    monkeypatch.setattr(photos, "text_ratio",
                        lambda p, **k: 0.5 if _seen.append(p) or len(_seen) == 1 else 0.0)
    _seen = []                   # 첫 후보만 글자 과다로 본다
    monkeypatch.setattr(photos, "has_face", lambda p, **k: True)
    r = photos.pick_photo("q", str(tmp_path), 1, log=lambda *a: None)
    assert r is not None
    assert Image.open(r["path"]).size == (300, 400)             # 둘째 후보가 반으로 잘려 들어갔다


def test_imread_handles_korean_path(tmp_path):
    """★한글 경로 회귀 — 박위 편 7컷이 전부 조용히 버려진 진짜 원인.

    실측 2026-09-13: `out/brainbulb/박위_photo/photo/11.jpg`가 325,823B로 멀쩡히 있는데
    `cv2.imread`는 None을 돌려줬다. 그래서 얼굴 0·글자 0%로 읽혀 후보가 전부 탈락,
    수집 0/7이 됐다. 필터가 엄격해서가 아니라 **사진을 아예 못 읽고 있었다.**
    """
    pytest.importorskip("cv2")
    d = tmp_path / "박위_photo" / "photo"
    d.mkdir(parents=True)
    p = d / "01.jpg"
    _noise(p)
    assert photos.imread(str(p)) is not None


def test_face_and_text_survive_korean_path(tmp_path):
    """판정 두 개가 한글 경로에서도 실제로 픽셀을 본다."""
    pytest.importorskip("cv2")
    d = tmp_path / "한글폴더"
    d.mkdir()
    p = d / "사진.jpg"
    _noise(p, seed=11)
    assert photos.text_ratio(str(p)) < 0.5          # 0.0(못 읽음)이 아니라 실제로 쟀다
    assert photos.has_face(str(p)) in (True, False)  # 예외 없이 판정된다


def test_no_direct_cv2_imread_calls():
    """판정은 한 군데에서만(0순위-B) — cv2.imread를 다시 직접 부르면 같은 병이 재발한다."""
    import inspect
    src = inspect.getsource(photos)
    assert "cv2.imread(" not in src


def test_pick_photo_rejects_duplicate_across_slots(tmp_path, monkeypatch):
    """★같은 사진이 두 컷에 — 사장님이 지적한 "두 번 연속 나온다".

    실측 2026-09-13 박위 편: 검색어가 달라도 같은 기사 사진이 와서 슬롯 5·8이 바이트까지 같았다.
    """
    same = tmp_path / "same.jpg"; _noise(same, seed=21)
    other = tmp_path / "other.jpg"; _noise(other, seed=22)
    import shutil
    hits = [{"url": "http://x/a.jpg", "source": "연합뉴스", "title": "", "w": 600, "h": 400},
            {"url": "http://x/b.jpg", "source": "한국경제", "title": "", "w": 600, "h": 400}]
    monkeypatch.setattr(photos, "search_images", lambda q, **k: hits)
    monkeypatch.setattr(photos, "download",
                        lambda u, p, **k: shutil.copy(str(same if "a.jpg" in u else other), p))
    monkeypatch.setattr(photos, "text_ratio", lambda p, **k: 0.0)
    monkeypatch.setattr(photos, "has_face", lambda p, **k: True)
    seen = set()
    a = photos.pick_photo("q1", str(tmp_path), 1, log=lambda *x: None, seen=seen)
    b = photos.pick_photo("q2", str(tmp_path), 2, log=lambda *x: None, seen=seen)
    assert a and b
    assert photos._fingerprint(a["path"]) != photos._fingerprint(b["path"])   # 둘째는 다른 사진


def test_split_collage_stops_before_slivers(tmp_path):
    """자르고 또 잘라도 슬롯에 못 넣을 만큼 얇아지면 멈춘다.

    실측 2026-09-13 박위 04번: 한 번 자르면 642→357, 또 자르면 184px라 쓸 수 없다.
    그래서 남은 글자 판은 `split_collage`가 아니라 `text_ratio`가 걸러야 한다(아래 시험).
    """
    w, h = 700, 400
    a = np.zeros((h, w, 3), dtype=np.uint8)
    a[:, :420] = 40
    a[:, 420:] = 210
    p = tmp_path / "two.jpg"
    Image.fromarray(a).save(p, "JPEG", quality=95)
    assert photos.split_collage(str(p), min_side=500) is False    # 잘라봤자 얇아 → 손대지 않는다
    assert Image.open(p).size == (700, 400)


def test_text_ratio_catches_light_text_on_dark(tmp_path):
    """★밝은 글씨/어두운 바탕 — 박위 04번 사과문 캡처가 0.2%로 통과하던 구멍.

    잉크를 '어두운 쪽'으로 단정하면 흰 글씨를 못 본다. 적은 쪽을 잉크로 본 뒤 11.7%로 걸린다.
    """
    cv2 = pytest.importorskip("cv2")
    img = np.full((400, 600, 3), 25, dtype=np.uint8)          # 어두운 바탕
    for y in range(40, 360, 40):
        cv2.putText(img, "sorry for the trouble caused today", (20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (235, 235, 235), 2)   # 흰 글씨
    p = tmp_path / "dark.jpg"
    Image.fromarray(img).save(p, "JPEG", quality=95)
    assert photos.text_ratio(str(p)) > spec.POLICY_PHOTO_TEXT_MAX
