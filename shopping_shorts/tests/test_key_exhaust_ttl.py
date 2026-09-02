# -*- coding: utf-8 -*-
"""소진 잠금은 **한시적**이다 — 하루짜리 영구 낙인이 아니다 (2026-08-27).

★사고: 제작소 1단계가 "Gemini 키 풀이 전부 소진"으로 5/5 실패했다(사장님 "왜실패하나 계속").
  실측으로 갈라보니:
    - 오전에 429였던 키가 **오후엔 전부 200**이었다. 쿼터는 시간이 지나면 회복된다.
    - 그런데 코드는 한 번 잠근 키를 **그날이 끝날 때까지** 배제했다(날짜 바뀔 때만 리셋).
    - 아침 크론(태거·백필)이 한 바퀴 돌며 키를 잠그면 낮에 쓸 키가 없었다.
    - 서버가 'Please retry in 45.5s'로 알려주는데(retry_delay_seconds) 잠금엔 안 썼다.

  → 잠금에 **만료시각**을 둔다. 서버가 알려준 값이 있으면 그만큼, 없으면 기본 TTL.
"""
import time

import pytest

from shopping_shorts import comment_gen as cg


@pytest.fixture
def st(tmp_path, monkeypatch):
    monkeypatch.setattr(cg, "_STATE_PATH", tmp_path / "state.json")
    return cg


class Test만료되면_풀린다:
    def test_잠근_직후엔_배제(self, st):
        st._mark_key_exhausted(3, retry_after=60)
        assert 3 in st._live_exhausted()

    def test_만료_뒤엔_자동_해제(self, st, monkeypatch):
        st._mark_key_exhausted(3, retry_after=60)
        later = time.time() + 10_000
        monkeypatch.setattr(time, "time", lambda: later)
        assert 3 not in st._live_exhausted(), "만료됐는데 아직 잠겨 있다"

    def test_서버가_알려준_시간을_쓴다(self, st):
        st._mark_key_exhausted(1, retry_after=45.5)
        until = st._live_exhausted()[1]
        assert 40 <= (until - time.time()) <= 60

    def test_값이_없으면_기본_TTL(self, st):
        st._mark_key_exhausted(2)
        until = st._live_exhausted()[2]
        assert (until - time.time()) == pytest.approx(cg._EXHAUST_TTL_S, abs=5)

    def test_영구_낙인은_만들지_않는다(self, st):
        """★핵심 — 아무리 길어도 상한이 있다. 이게 없으면 2026-08-27 사고가 재발한다.

        ★상한을 6시간 → 24시간으로 넓혔다(2026-09-02). 사유별로 갈라야 했기 때문이다:
          · 분당 한도는 서버가 '45.5초 뒤'라고 알려주고 실제로 그때 풀린다 → 짧게(위 테스트가 지킨다)
          · **일일 소진**은 태평양 자정까지 진짜 안 풀린다. 그런데 구글은 하루치를 다 쓴
            429에도 'Please retry in 57.4s'를 함께 준다 — 그 값을 믿고 57초 뒤 풀면
            또 때리고 또 막힌다(실측: 사장님이 본 '죽은 키 1개를 18번 헛되이 호출' 경보).
          한국 새벽~오전에 소진되면 자정까지 15시간이 남는데 6시간으로 잘려 되풀이됐다.
        ★취지는 그대로다: 24시간이면 반드시 한 번은 다시 시험해 본다 = 영구가 아니다.
        """
        st._mark_key_exhausted(4, retry_after=999_999)
        until = st._live_exhausted()[4]
        left = until - time.time()
        assert left <= 24 * 3600 + 5, "상한이 없으면 키가 영영 안 돌아온다"
        assert left > 6 * 3600, "일일 소진을 담을 만큼은 넓어야 한다"

    def test_너무_짧아도_최소값(self, st):
        st._mark_key_exhausted(5, retry_after=0.1)
        assert (st._live_exhausted()[5] - time.time()) >= 25

    def test_더_긴_잠금이_이긴다(self, st):
        st._mark_key_exhausted(6, retry_after=3600)
        st._mark_key_exhausted(6, retry_after=60)
        assert (st._live_exhausted()[6] - time.time()) > 600, "짧은 잠금이 긴 것을 덮었다"


class Test하위호환:
    def test_옛_형식_리스트도_읽는다(self, st):
        """배포 순간 파일이 옛 모양(list)일 수 있다 — 그때 터지면 안 된다.

        ★옛 항목도 **만료가 붙어야** 한다. 영구로 두면 배포 직후 하루는
          종전 증상(하루짜리 낙인)이 그대로다.
        """
        m = st._exhausted_map({"exhausted": [1, 2, 3]})
        assert set(m) == {1, 2, 3}
        for t in m.values():
            assert t != float("inf"), "옛 항목이 영구 낙인으로 남았다"
            assert (t - time.time()) == pytest.approx(cg._EXHAUST_TTL_S, abs=5)

    def test_빈_상태도_안전(self, st):
        assert st._exhausted_map({}) == {}
        assert st._exhausted_map({"exhausted": None}) == {}

    def test_망가진_값은_건너뛴다(self, st):
        assert st._exhausted_map({"exhausted": {"1": "x", "2": 100.0}}) == {2: 100.0}


class Test프로브를_한번만_믿는다:
    """★프로브(maxOutputTokens=1)는 '가벼운 요청'만 대표한다.

    Gemini는 하루 요청 수(RPD)와 토큰 수(TPD)가 따로라, 텍스트 1토큰은 200인데
    영상 업로드는 429다. 그래서 되살린 키가 또 소진되면 오늘은 더 안 믿는다.
    """

    def test_되살린_키가_또_죽으면_다시_안_되살린다(self, st, monkeypatch):
        st._mark_key_exhausted(0, retry_after=3600)
        monkeypatch.setattr(cg, "SHORTS_GEMINI_KEYS", ["k0", "k1"])
        monkeypatch.setattr(cg, "_probe_key_alive", lambda k, timeout=15: True)
        cg._last_recheck["t"] = 0.0
        assert st._recheck_exhausted_keys() == [0]          # 1회차: 되살아난다
        st._mark_key_exhausted(0, retry_after=3600)          # 실제 작업에서 또 429
        cg._last_recheck["t"] = 0.0
        assert st._recheck_exhausted_keys() == [], "두 번째도 되살렸다 — 무한 반복이 된다"
