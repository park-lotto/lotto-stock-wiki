"""자막제거 BEFORE/AFTER가 다른 영상을 보여주던 버그 (2026-08-27 사장님 제보).

증상: BEFORE=벽 페인트칠 / AFTER=보라색 매트 — 전혀 다른 영상.

원인: 완성본 1편만 청소하는 방식으로 바뀌면서 "이 소스가 완성본 어디에 있나"를
찾아야 했는데, _final_time_of_source가 None(=완성본에 안 쓰임)을 줄 때 호출부가
아무 처리도 안 했다. 원본 기준 pos(0.5)가 그대로 남아 **완성본 전체의 가운데**를
가리켰다 = 전혀 다른 소스 구간.

★기존 테스트의 구멍: _final_time_of_source가 None을 준다는 건 이미 테스트돼 있었다
  (test_clean_step2_final.py). 하지만 **그 None을 받는 쪽**은 아무도 안 봤다.
  함수는 맞았고 호출부가 틀렸다. 그래서 이 파일은 호출부만 본다.
"""
import pytest

from shopping_shorts import mix_pipeline as mp


def _plan(*vids):
    """비트마다 소스 하나씩 쓰는 최소 편집안."""
    return {"beats": [{"beat_idx": i, "target_seconds": 2.0,
                       "primary": {"video_id": v}} for i, v in enumerate(vids)]}


class TestFinalSourceIndices:
    """1겹 — 넘겨볼 수 있는 소스 번호 목록."""

    def test_only_used_sources_listed(self):
        """담은 건 5개여도 편성된 3개만 나온다 — 이게 이번 버그의 핵심."""
        plan = _plan("s0", "s2", "s4")
        assert mp._final_source_indices(plan, 5) == [0, 2, 4]

    def test_all_used(self):
        assert mp._final_source_indices(_plan("s0", "s1", "s2"), 3) == [0, 1, 2]

    def test_none_used_returns_empty(self):
        """편집안이 비면 빈 목록 — 넘기기 화살표 자체가 안 뜬다."""
        assert mp._final_source_indices({}, 5) == []

    def test_never_lists_what_time_lookup_rejects(self):
        """★불변식: 목록에 있으면 시각도 반드시 나온다.

        이 둘이 어긋나면 증상이 그대로 재발한다(목록엔 있는데 AFTER는 404).
        그래서 _final_source_indices는 판정을 새로 짜지 않고 같은 함수를 부른다.
        """
        plan = _plan("s0", "s3")
        for i in mp._final_source_indices(plan, 6):
            at = mp._final_time_of_source(plan, mp._source_video_id(i))
            assert at is not None, f"목록에 s{i}가 있는데 시각이 None이다"

    def test_excluded_ones_really_have_no_time(self):
        """뒤집어서도 성립 — 목록에 없는 건 정말로 완성본에 없다."""
        plan = _plan("s0", "s3")
        listed = set(mp._final_source_indices(plan, 6))
        for i in set(range(6)) - listed:
            assert mp._final_time_of_source(plan, mp._source_video_id(i)) is None

    def test_bad_input_does_not_crash(self):
        for n in (0, None, -3):
            assert mp._final_source_indices(_plan("s0"), n) == []


class TestCallerHandlesNone:
    """2겹 — 호출부가 None을 만났을 때. 여기가 이번에 뚫린 자리다."""

    def test_app_returns_404_not_wrong_frame(self):
        """app.py가 _at is None에서 404로 빠져나가는지 소스로 확인.

        실제 HTTP 호출은 유료게이트·DB·ffmpeg가 얽혀 단위테스트가 어렵다.
        대신 '조용히 넘어가는 모양'이 되돌아오지 않았는지를 본다 —
        되돌아오면 증상이 그대로 재발하므로, 그 형태를 금지한다.
        """
        import pathlib
        src = pathlib.Path(__file__).resolve().parents[1] / "app.py"
        text = src.read_text(encoding="utf-8")
        # 2026-08-27: 판정이 비트 단위 -> **컷 단위**(final_pair_for_source)로 바뀌었다.
        #   이름이 아니라 **모양**을 검사한다 — 조용한 폴백이 되돌아오면 증상 재발이다.
        i = text.find("final_pair_for_source")
        assert i > 0, "자리 판정 호출부가 사라졌다 — 이 테스트를 갱신하라"
        window = text[i:i + 1400]
        assert "not_in_final" in window, \
            "자리를 못 찾을 때 404로 빠지지 않는다 — 엉뚱한 프레임이 나간다"
        assert "if _final_sec is None:" in window, \
            "조용한 폴백이 되돌아왔다 — 못 찾으면 반드시 거부해야 한다"
