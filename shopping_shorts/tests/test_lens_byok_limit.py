# -*- coding: utf-8 -*-
"""렌즈 BYOK 한도 — 자기 SerpApi 키를 낸 회원은 하루 한도를 더 준다(2026-08-26).

★왜 필요한가 (실측)
회원 201(임영미)이 마이페이지에 SerpApi 키를 **2개** 등록했다(둘 다 status=ok).
그런데 `check_and_count(cid, "lens")`는 키 보유와 무관하게 돌아서, **본인이 SerpApi
비용을 내면서도 하루 10회에 막혔다.** 검색 비용은 그 사람 키에서 나가는데 한도는
사장님 키 기준으로 걸려 있던 것 — 앞뒤가 안 맞는다.

★왜 '고객별 컬럼'이 아니라 'BYOK 조건'인가
고객별 한도 컬럼을 만들면 같은 요청이 올 때마다 사람이 손으로 넣어야 한다.
키를 낸 사람에게 자동으로 주면 앞으로 등록하는 회원도 그냥 적용된다.

★판정은 keyroute.keys_for 하나만 본다(0순위-B)
'내 키를 쓰는가'는 이미 keyroute가 정한다(is_user). 여기서 다시 판정하면
키 고르는 쪽과 한도 주는 쪽이 어긋난다 — 그게 이 코드베이스가 반복해 겪은 사고다.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
APP = (SRC / "app.py").read_text(encoding="utf-8")


def test_byok_한도_상수가_있다():
    assert "_CREDIT_BYOK_DEFAULTS" in APP, "BYOK 전용 한도 기본값이 없다"
    m = re.search(r"_CREDIT_BYOK_DEFAULTS\s*=\s*\{([^}]*)\}", APP)
    assert m, "_CREDIT_BYOK_DEFAULTS 선언을 못 찾았다"
    assert '"lens": 20' in m.group(1), "렌즈 BYOK 한도가 20이 아니다"


def test_한도판정이_keyroute를_쓴다():
    """★'내 키인가'를 여기서 새로 판정하면 안 된다 — keys_for의 is_user를 빌려 쓴다."""
    m = re.search(r"def _lens_has_own_key\(.*?\n(?:.*?\n)*?\n\n", APP)
    assert m, "_lens_has_own_key 함수가 없다"
    body = m.group(0)
    assert "keys_for" in body and "SVC_SERPAPI" in body, (
        "BYOK 판정이 keyroute.keys_for를 안 쓴다 — 판단이 두 곳에 생긴다")
    # customer_keys를 직접 SELECT하는 식의 자체 판정은 금지
    assert "get_customer_keys" not in body, "keyroute를 우회해 직접 조회하고 있다"


def test_check_and_count가_byok한도를_본다():
    """실제 차단 판정에 BYOK 분기가 있어야 한다 — 화면만 바꾸면 여전히 10회에서 막힌다."""
    m = re.search(r"def check_and_count\(.*?\n(?:.*?\n)*?    return True\n", APP)
    assert m, "check_and_count를 못 찾았다"
    body = m.group(0)
    # 2026-08-26: 'BYOK면 20회 고정' → '키 1개당 10회'로 바뀌었다(사장님 지시).
    #   판정이 _lens_limit_for 한 곳에 모였으므로 그 함수를 부르는지로 본다.
    assert "_lens_limit_for" in body, (
        "check_and_count가 BYOK 한도를 안 본다 — 화면 표시만 바뀌고 실제로는 계속 막힌다")


def test_마이페이지도_같은_한도를_보여준다():
    """★표시와 실제가 어긋나면 '20회라더니 10회에서 막힌다'가 된다(0순위-B)."""
    i = APP.index("def _api_me(")          # 실제 함수명(2026-08-26 확인)
    seg = APP[i:i + 6000]
    assert ("_lens_limit_for" in seg or "_CREDIT_BYOK_DEFAULTS" in seg
            or "limit_lens_byok" in seg), (
        "/api/me가 BYOK 한도를 반영하지 않는다")


def test_렌즈만_올린다_다른_op는_그대로():
    """render·script까지 덩달아 올라가면 안 된다 — SerpApi 키는 렌즈에만 쓴다."""
    m = re.search(r"_CREDIT_BYOK_DEFAULTS\s*=\s*\{([^}]*)\}", APP)
    body = m.group(1)
    for op, val in (("render", 10), ("script", 200)):
        mm = re.search(rf'"{op}":\s*(\d+)', body)
        assert mm and int(mm.group(1)) == val, (
            f"{op} 한도가 pro 기본값({val})과 달라졌다 — 렌즈만 올려야 한다")


# ── 체험 차단 / 프로는 개인 키 — 2026-08-27 사장님 지시 ─────────────────────────

def _guard(monkeypatch, *, trial=False, my_keys=None, owner_left=0, cid=7):
    """게이트를 호출부 형태 그대로 부른다(app._lens_quota_guard(store, month, cid))."""
    from shopping_shorts import app as A, keyroute, lens_discover
    monkeypatch.setattr(A, "_is_trial", lambda c, now=None: trial)
    monkeypatch.setattr(keyroute, "keys_for",
                        lambda st, c, svc: ((my_keys, True) if my_keys else (["공용"], False)))
    monkeypatch.setattr(lens_discover, "account_searches_left",
                        lambda force=False, keys=None: (250 if keys and keys == my_keys
                                                        else owner_left))
    class _St:
        def lens_month_count(self, m): return 0
        def get_setting(self, k, d=None): return d
    return A._lens_quota_guard(_St(), "2026-08", cid)


def _body(resp):
    import json
    return json.loads(bytes(resp.body).decode())


def test_체험중이면_렌즈를_막는다(monkeypatch):
    """렌즈 1회는 SerpApi 실비다 — 체험에까지 열어주면 공용 키가 순식간에 마른다."""
    r = _guard(monkeypatch, trial=True, my_keys=["내키"])   # 키가 있어도 체험이면 막는다
    assert r is not None
    assert _body(r)["error_code"] == "lens_trial"


def test_정회원은_자기키가_없으면_등록안내(monkeypatch):
    """★공용으로 폴백하지 않는다. 공용 잔량이 남아 있어도 마찬가지다 —
    안 그러면 한 사람이 몰아 써서 다른 사람이 막힌다."""
    r = _guard(monkeypatch, my_keys=None, owner_left=999)
    assert r is not None
    assert _body(r)["error_code"] == "lens_need_key"


def test_정회원은_자기키가_있으면_통과(monkeypatch):
    assert _guard(monkeypatch, my_keys=["내키"], owner_left=0) is None


def test_사장님은_공용으로_계속_쓴다(monkeypatch):
    """cid 0만 공용 폴백을 남긴다 — 관리자까지 막으면 점검을 못 한다."""
    assert _guard(monkeypatch, my_keys=None, owner_left=100, cid=0) is None
