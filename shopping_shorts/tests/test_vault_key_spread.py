"""키 분산·EDL 실패사유 회귀 (2026-08-31 실사고).

★이 파일은 **모듈 속성을 바꿔치기하지 않는다.** 예전 판은
  `monkeypatch.setattr(edit_plan, "_vault_call_once", ...)`로 실제 함수를 갈아끼웠는데,
  전체 게이트에서 뒤에 도는 test_byok_charge_wiring 3건이 깨졌다(단독·부분조합은 통과).
  여기서 지킬 불변식은 순수 함수 하나로 확인할 수 있으니 그렇게만 한다.
"""
from shopping_shorts import edit_plan, mix_pipeline


def test_오프셋은_부를때마다_달라진다():
    """★사고: key_offset 기본값이 0이라 워커 12개가 전부 keys[0]만 두들겼다.
    실측 08-31: 제미니 1,825건 중 429가 816건(45%). 429 사유는 전부 '분당' 한도고
    '하루'는 0건 — 키가 모자란 게 아니라 앞쪽 키에 몰린 것이었다."""
    vals = [edit_plan._auto_key_offset() for _ in range(8)]
    assert len(set(vals)) == 8, f"오프셋이 겹친다 {vals} — 같은 키에 몰린다"
    # 키 10개 풀이면 서로 다른 인덱스로 흩어져야 한다
    assert len({v % 10 for v in vals}) == 8


def test_분당한도만_대기대상이다():
    """분당은 쉬면 풀리고 일일·403은 안 풀린다. 뭉치면 전자를 후자처럼 버린다."""
    rpm = ("429 RESOURCE_EXHAUSTED Quota exceeded for quota metric "
           "'Generate Content API requests per minute'")
    assert edit_plan._is_per_minute_quota(rpm) is True
    assert edit_plan._is_per_minute_quota("429 ... requests per day") is False
    assert edit_plan._is_per_minute_quota("403 PERMISSION_DENIED") is False


def test_API가_말한_사유가_소스글자수를_이긴다():
    """★사고: 키가 429+401로 다 튕긴 job이 'extract_empty'(소스 대사 0자)로 떴다.
    그 라벨을 믿고 "대사 없는 영상이라 안 된다"고 잘못 보고했다 — 대사가 없어도
    확정 대본이 있으면 scene_desc로 정상 매칭된다. 소스 글자수는 원인이 아니다."""
    srcs = [{"full_text": ""}, {"full_text": ""}]      # 대사 0자
    code, why = mix_pipeline._edl_empty_reason(
        srcs, {}, api_reason="429 RESOURCE_EXHAUSTED ... per minute")
    assert code == "api_failed", "API 실패를 '추출 실패'로 부르면 엉뚱한 데를 본다"
    assert "429" in why

    # 사유가 없을 때만 종전 판정으로 떨어진다(회귀 0)
    code2, _ = mix_pipeline._edl_empty_reason(srcs, {})
    assert code2 == "extract_empty"
