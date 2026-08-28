"""가려진 키는 등록 단계에서 막는다 (2026-08-28 실사고).

두 고객이 같은 실수를 했다: 발급 화면에 **가려져 보이는** 키를 그대로 복사해 등록.
등록은 성공(status=ok)으로 저장돼 "등록 완료"가 뜨는데, 정작 쓸 때만 서명이 안 맞아
실패했다. 고객은 잘 된 줄 알고 있다가 자막제거를 눌러야 알았다.

실측 cid18 강민희(pro): 키 140자(정상 184) / 라벨 끝 '*****' / 6회 시도 전부 실패
  에러 [10021] sign not equals client ... Access=13a08ac2eb5f4f — 그 키가 실제로 쓰였다
cid134 최소연도 같은 모양이었다가 재등록으로 정상화(전수 22건 중 1건 남음).
"""
import pytest

from shopping_shorts import keyroute


class TestMaskedKeyDetection:
    def test_real_case_star_masked(self):
        """★실제 사고 모양 — VMake 화면의 가려진 키."""
        r = keyroute.masked_key_reason("13a08ac2eb5f4f••••••••*****")
        assert r, "가려진 키를 통과시키면 안 된다"
        assert "전체 키" in r, "무엇을 해야 하는지 말해야 한다"

    @pytest.mark.parametrize("bad", [
        "abcd1234*****",            # 별표
        "abcd••••1234",             # 가운뎃점
        "abcd●●●●1234",             # 검은 원
        "ak:sk··········",          # 라틴 가운뎃점
        "abc✱✱✱def",
    ])
    def test_various_mask_chars(self, bad):
        assert keyroute.masked_key_reason(bad), f"{bad} 를 막아야 한다"

    @pytest.mark.parametrize("good", [
        "13a08ac2eb5f4f1234567890abcdef",
        "AIzaSyBp0000000000000000000vlnm0",
        "sk_521ea0000000000000000000004f0d0",
        "ak_abc123:sk_def456",                    # vmake는 ak:sk 한 덩어리
        "AQ.Ab8RN-0000_0000-abcIWJaw",            # 점·하이픈·밑줄은 정상 키에 흔하다
    ])
    def test_normal_keys_pass(self, good):
        """★오탐이 없어야 한다 — 멀쩡한 키를 막으면 등록 자체가 불가능해진다."""
        assert keyroute.masked_key_reason(good) is None, f"{good} 는 통과해야 한다"

    def test_empty_is_not_our_job(self):
        """빈 값은 호출부가 '키를 입력하세요'로 따로 안내한다."""
        assert keyroute.masked_key_reason("") is None
        assert keyroute.masked_key_reason(None) is None

    def test_length_is_not_used(self):
        """★길이로 판정하지 않는다 — 서비스마다 다르고 새 형식이 나오면 멀쩡한 걸 막는다."""
        assert keyroute.masked_key_reason("abc") is None          # 짧아도 통과
        assert keyroute.masked_key_reason("x" * 500) is None      # 길어도 통과


class TestRegisterApiBlocks:
    def test_api_calls_the_check(self):
        """등록 API가 실제로 이 판정을 부르는지 — 붙여만 두고 안 부르면 소용없다."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        i = src.find('@app.post("/api/settings/keys")')
        assert i > 0, "등록 API가 사라졌다 — 이 테스트를 갱신하라"
        window = src[i:i + 2000]
        assert "masked_key_reason" in window, "등록 API가 가림문자 검사를 안 부른다"
        assert window.index("masked_key_reason") < window.index("add_customer_key"), \
            "저장(add_customer_key)보다 먼저 검사해야 한다"
