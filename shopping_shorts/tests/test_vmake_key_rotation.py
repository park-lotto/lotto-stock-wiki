"""VMake 키 로테이션 — 한 키가 소진되면 다음 키로 넘어간다(2026-08-29).

사장님 제보: "v메이커를 두개 키등록했다는데 한개 소진후 다른걸로 안넘어가는것같은데"

실측으로 확인한 뿌리(고치기 전):
  · mix_pipeline._vmake_key가 `keys[0] if keys else ""` — **첫 키 하나만** 돌려줬다.
  · keyroute.SINGLE_KEY에 vmake가 들어 있어 "나중에 등록한 키를 앞에" 두는 정렬만 하고,
    소진 시 다음 키로 넘기는 코드는 아예 없었다.
  · 서버 DB cid 57: vmake 키 id 235·236이 둘 다 status='ok'인데 236만 쓰였다.

사장님 결정(2026-08-29):
  · 소진(60002)을 만나면 다음 키로 재시도한다.
  · **회원 키가 전부 소진돼도 본사 키로 넘기지 않는다** — 조용히 넘어가 사장님 포인트가
    깎이던 사고가 이미 있었다(cid57 2.1P).
"""
import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import vmake_client


NO_CREDIT = "[60002] You don't have enough credits for this API. Purchase a subscription..."


class Test소진판정:
    """★판정은 vmake_client 한 곳 — mix_pipeline(넘길지)과 app(문구)이 같이 쓴다."""

    def test_소진_원문을_잡는다(self):
        assert vmake_client.is_no_credit(NO_CREDIT)
        assert vmake_client.is_no_credit(Exception(NO_CREDIT))
        assert vmake_client.is_no_credit("code 60002")

    @pytest.mark.parametrize("other", [
        "[10101] right reduce error",       # 영상 처리 불가 — 키 문제가 아니다
        "Connection reset by peer",         # 네트워크
        "포인트가 부족합니다",                 # 우리 포인트 — 남의 키를 태우면 안 된다
        "",
    ])
    def test_다른_실패는_소진이_아니다(self, other):
        assert not vmake_client.is_no_credit(other), \
            "넓게 잡으면 멀쩡한 키를 죽은 것으로 보고 다 태운다"

    def test_화면_문구도_같은_판정을_쓴다(self):
        """app.clean_failure_kind가 따로 문자열을 검사하면 로테이션과 어긋난다."""
        from shopping_shorts import app
        assert app.clean_failure_kind(NO_CREDIT) == "no_credit"
        assert app.clean_failure_kind("[10101] right reduce error") == "unsupported"
        assert app.clean_failure_kind("포인트가 부족합니다") == "no_points"


class Test로테이션:
    def _spy(self, monkeypatch, script):
        """remove_subtitles를 가로채 (호출된 키 목록, 동작)을 기록한다.

        ★호출부 형태 그대로 받는다 — _vmake_clean은 (path, key, out_path=...)로 부른다.
        """
        seen = []

        def fake(video_path, api_key, out_path, **kw):
            seen.append(api_key)
            act = script.get(api_key, "ok")
            if act == "no_credit":
                raise RuntimeError(NO_CREDIT)
            if act:
                if act != "ok":
                    raise RuntimeError(act)
            return out_path
        monkeypatch.setattr(mp, "remove_subtitles", fake)
        return seen

    def test_첫_키가_소진이면_다음_키로_넘어간다(self, monkeypatch):
        """★뿌리 회귀: 고치기 전엔 키가 둘이어도 첫 키에서 끝났다."""
        seen = self._spy(monkeypatch, {"K1": "no_credit"})
        out = mp._vmake_clean("in.mp4", ["K1", "K2"], "out.mp4")
        assert seen == ["K1", "K2"], f"다음 키로 안 넘어갔다: {seen}"
        assert out == "out.mp4"

    def test_세_키중_둘이_소진이어도_끝까지_간다(self, monkeypatch):
        seen = self._spy(monkeypatch, {"K1": "no_credit", "K2": "no_credit"})
        mp._vmake_clean("in.mp4", ["K1", "K2", "K3"], "out.mp4")
        assert seen == ["K1", "K2", "K3"]

    def test_첫_키가_멀쩡하면_한_번만_부른다(self, monkeypatch):
        """멀쩡한데 여러 키를 태우면 남의 크레딧을 공짜로 깎는다."""
        seen = self._spy(monkeypatch, {})
        mp._vmake_clean("in.mp4", ["K1", "K2"], "out.mp4")
        assert seen == ["K1"]

    def test_소진이_아닌_실패는_키를_갈아타지_않는다(self, monkeypatch):
        """네트워크·처리불가로 키를 바꾸면 멀쩡한 키만 태우고 원인은 그대로다."""
        seen = self._spy(monkeypatch, {"K1": "[10101] right reduce error"})
        with pytest.raises(RuntimeError):
            mp._vmake_clean("in.mp4", ["K1", "K2"], "out.mp4")
        assert seen == ["K1"], f"엉뚱하게 다음 키를 태웠다: {seen}"

    def test_전부_소진이면_마지막_오류를_올린다(self, monkeypatch):
        """화면이 종전처럼 'no_credit'을 띄워야 한다 — 본사 키로 넘기지 않는다."""
        from shopping_shorts import app
        seen = self._spy(monkeypatch, {"K1": "no_credit", "K2": "no_credit"})
        with pytest.raises(Exception) as ei:
            mp._vmake_clean("in.mp4", ["K1", "K2"], "out.mp4")
        assert seen == ["K1", "K2"]
        assert app.clean_failure_kind(str(ei.value)) == "no_credit"

    def test_키가_없으면_명확히_거절한다(self, monkeypatch):
        self._spy(monkeypatch, {})
        with pytest.raises(ValueError):
            mp._vmake_clean("in.mp4", [], "out.mp4")
        with pytest.raises(ValueError):
            mp._vmake_clean("in.mp4", ["", None], "out.mp4")


class Test키목록:
    def test_등록한_키를_전부_준다(self, monkeypatch):
        """★뿌리: 종전 _vmake_key는 keys[0] 하나만 줬다."""
        from shopping_shorts import keyroute
        monkeypatch.setattr(keyroute, "keys_for", lambda st, cid, svc: (["A", "B"], "customer"))
        assert mp._vmake_keys(object(), 57) == ["A", "B"]

    def test_키가_없으면_빈_목록(self, monkeypatch):
        from shopping_shorts import keyroute
        monkeypatch.setattr(keyroute, "keys_for", lambda st, cid, svc: ([], "none"))
        assert mp._vmake_keys(object(), 57) == []
