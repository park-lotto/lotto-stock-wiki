"""무음 영상도 대본 재료다 — 생성 관문이 원문(full_text)만 보고 막으면 안 된다.

2026-09-28 차순엽 회원 제보: 담긴 영상(유튜브 리필 디스펜서·샤오홍슈 세제 소분)의 1단계 분석은
끝났는데(extract_method=frames, 세그 23개, scene_desc·source_brief 정상) 말이 없어 full_text=''.
"이 스타일로 대본 만들기"가 422 "재료(대본 원문)가 아직 없어요 — 분석이 끝난 뒤 다시 눌러주세요"
를 냈고, 기다려도 영영 안 풀리는 안내라 회원이 저녁에만 10번 다시 눌렀다(라이브 로그 실측).
재료 조립(_sources_for_generate)은 09-09에 무음 소재를 담게 바뀌었는데 관문 두 곳은 그대로였다.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from shopping_shorts.app import _generate_material_ready, _sources_for_generate  # noqa: E402


def _silent_item():
    """라이브 실측(grab_youtube_362fc93d6b87)과 같은 모양: 말은 없고 장면 설명·제품명만."""
    return {
        "full_text": "", "structure": {}, "category": "생활",
        "url": "https://www.youtube.com/shorts/yysfmETZvUM",
        "shortcode": "grab_youtube_362fc93d6b87",
        "source_brief": {"product": "리필용 펌프 디스펜서"},
        "segments": [{"seg_id": "grab_youtube_362fc93d6b87-0", "start": 0.0, "end": 1.0,
                      "text": "", "text_ko": "",
                      "scene_desc": "가위로 리필 봉투 상단을 자르고 펌프형 디스펜서에 넣는 모습"}],
    }


def test_silent_video_counts_as_material():
    """말이 없어도 장면 설명이 있으면 재료다(관문 통과)."""
    src = _sources_for_generate(_silent_item(), None)
    assert src, "무음 소재가 재료 목록에서 빠지면 09-09 수정이 죽은 것"
    assert _generate_material_ready(src) is True


def test_product_only_counts_as_material():
    assert _generate_material_ready([{"full_text": "", "product": "펌프 디스펜서", "segments": []}])


def test_spoken_material_still_passes():
    assert _generate_material_ready([{"full_text": "이거 진짜 편해요", "segments": []}])


def test_truly_empty_is_blocked():
    """아무것도 없으면 여전히 막는다 — 이 상태로 생성하면 모델이 통째로 지어낸다."""
    assert _generate_material_ready([]) is False
    assert _generate_material_ready([{"full_text": "  ", "product": "", "segments": [
        {"seg_id": "x-0", "text": "", "scene_desc": ""}]}]) is False
    assert _generate_material_ready([None, "junk"]) is False


def test_old_gate_would_have_blocked_silent_source():
    """고치기 전 판정(원문만 봄)은 같은 재료를 막았다 — 검사가 실제로 무언가를 재는지 확인."""
    src = _sources_for_generate(_silent_item(), None)
    old_gate = bool([x for x in src if (x.get("full_text") or "").strip()])
    assert old_gate is False
