"""10-29 썰템쇼 회원 시험 — 제목 자동 정리(rules.title_colors_fix)가 본문 틀 제목 칸(1칸)만 보고 훅 카드 구간 틀(흰·연두 2칸)용
2번째 줄을 잘라 '제목 1줄' 관문이 고치기 내내 반복됐다. 판단 주인 rules.title_spec = 본문·구간 틀 중 칸이 많은 것, join 이면 제한 없음."""
from tools.calcopy.hybrid import rules as RU

ST = {"frame": {"title": [{"color": "#000000"}],
                "segments": [{"t0": 0, "t1": 2, "frame": {"title": [{"color": "#FFFFFF"}, {"color": "#84FD46"}]}}]}}


def test_hook_segment_second_line_kept():
    S = {"title_lines": [[["오뚜기에서", None]], [["절대 안 파는 이것", None]]]}
    RU.title_colors_fix(S, ST)
    assert len(S["title_lines"]) == 2 and RU.title_colors_bad(S, ST) == []


def test_more_lines_than_any_frame_still_cut():
    S = {"title_lines": [[["a", None]], [["b", None]], [["c", None]]]}
    RU.title_colors_fix(S, ST)
    assert len(S["title_lines"]) == 2


def test_join_means_no_limit():
    st = {"frame": {"title": [{"color": "#000", "join": " "}]}}
    S = {"title_lines": [[["a", None]], [["b", None]], [["c", None]]]}
    RU.title_colors_fix(S, st)
    assert len(S["title_lines"]) == 3
