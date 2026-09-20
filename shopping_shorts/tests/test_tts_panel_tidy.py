"""5단계 TTS 패널 정리(2026-09-04 사장님 6건).

① '마음에 드는 목소리 찾기' → '일레븐랩스 성우 찾기'(타입캐스트와 이름 맞춤)
② 2×2: 1줄 찾기(일레븐|타입캐스트), 2줄 내가 만든 목소리(일레븐|타입캐스트)
③ 타입캐스트 '내가 만든 목소리' = 내 키로 목록 받아 uc_만
④ 재생 중 파형 애니메이션 + 단독 재생 끝나면 강조 해제
⑤ '자막 당기기/밀기'·'발음 이상해요' 버튼 삭제(함수는 남김)
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def _grid():
    i = HTML.index('<div class="findCols">')
    j = HTML.index('<!-- .findCols 끝 -->', i)
    return HTML[i:j]


def test_names_match_and_old_name_gone():
    assert "마음에 드는 목소리 찾기" not in HTML
    g = _grid()
    assert "🔎 일레븐랩스 성우 찾기" in g and "🔎 타입캐스트 성우 찾기" in g


def test_two_by_two_order_left_eleven_right_typecast():
    g = _grid()
    order = [g.index('id="vlibBox"'), g.index('id="tcvBox"'), g.index('id="vmineBox"'), g.index('id="tcmineBox"')]
    assert order == sorted(order), "1줄=찾기(일레븐|타입), 2줄=내가 만든(일레븐|타입) 순서"
    assert 'id="elvAdmin"' not in g                       # 관리자 전용은 격자 밖(고객 화면 2×2 유지)
    assert 'id="elvAdmin"' in HTML
    assert ".findCols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in HTML
    assert "· 일레븐랩스</span>" in g and "· 타입캐스트</span>" in g


def test_typecast_mine_wiring_in_html():
    assert "/api/typecast/voices/mine" in HTML
    assert "function loadTypecastMine(" in HTML and "function toggleTypecastMine(" in HTML
    assert "tcvUse(this,'+i+',\\'mine\\')" in HTML or "tcvUse(this,'+i+',\\'mine\\')" in HTML.replace('\\', '\\')


def test_typecast_mine_api_filters_uc_and_needs_own_key(monkeypatch, tmp_path):
    from shopping_shorts import typecast_tts
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    seen = {}

    def fake_list(timeout=30, customer_id=0):
        seen["cid"] = customer_id
        return {"ok": True, "error": None, "voices": [
            {"voice_id": "tc_official1", "name": "공식", "model": "ssfm-v30", "emotions": []},
            {"voice_id": "uc_mine1", "name": "내목소리", "model": "ssfm-v30", "emotions": ["normal"]},
        ]}
    monkeypatch.setattr(typecast_tts, "list_voices", fake_list)
    c = TestClient(appmod.app)
    # 내 키 없음 + 관리자 아님 → need_key
    monkeypatch.setattr(appmod.keyroute, "has_own_key", lambda s, cid, svc: False)
    monkeypatch.setattr(appmod, "_is_admin", lambda cid: False)
    j = c.get("/api/typecast/voices/mine").json()
    assert j["need_key"] is True and j["voices"] == []
    # 내 키 있음 → 내 키(cid)로 목록, uc_만
    monkeypatch.setattr(appmod.keyroute, "has_own_key", lambda s, cid, svc: True)
    j = c.get("/api/typecast/voices/mine").json()
    assert j["ok"] and [v["voice_id"] for v in j["voices"]] == ["uc_mine1"] and j["total"] == 2
    assert "cid" in seen


def test_adopt_validates_with_customer_key(monkeypatch, tmp_path):
    """담기(adopt)가 운영자 키 목록으로만 검증하면 내가 만든 uc_ 목소리는 항상 404였다."""
    from shopping_shorts import typecast_tts
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    seen = {}

    def fake_list(timeout=30, customer_id=0):
        seen["cid"] = customer_id
        return {"ok": True, "error": None,
                "voices": [{"voice_id": "uc_mine1", "name": "내목소리", "model": "ssfm-v30", "emotions": []}]}
    monkeypatch.setattr(typecast_tts, "list_voices", fake_list)
    r = TestClient(appmod.app).post("/api/typecast/voices/adopt",
                                    json={"voice_id": "uc_mine1", "name": "내목소리", "model": "ssfm-v30"})
    assert r.status_code != 404, r.text
    assert "cid" in seen                                   # customer_id 인자로 불렀다


def test_wave_animates_while_playing_and_stops_on_end():
    assert "@keyframes wavePulse" in HTML
    assert ".ttsRow.playing .wave i{background:var(--accent);transform-origin:bottom;animation:wavePulse" in HTML
    assert "prefers-reduced-motion" in HTML
    fn = HTML[HTML.index("function vpPlayBeat(i){"):HTML.index("function vpMarkPlaying(i){")]
    assert "a.onended=()=>{ if(!VP_ALL) vpMarkPlaying(-1); }" in fn


def test_row_toolbar_buttons_removed_but_functions_kept():
    row = HTML[HTML.index('<div id="vpMore${i}" class="ttsMore"'):HTML.index('id="vpMsg${i}"')]
    row = re.sub(r"<!--.*?-->", "", row, flags=re.S)        # 설명 주석은 버튼이 아니다
    for gone in ("자막 당기기", "자막 밀기", "발음 이상해요", "vpNudge(", "pronReport("):
        assert gone not in row, gone
    assert "vpResetOffset(${i})" in row and "vpRegenTone(${i})" in row
    assert "function vpNudge" in HTML and "function pronReport" in HTML
