"""10-29 썰템쇼 회원 시험 — 재료 후보를 시트로 볼 순서(screen.pick_ids).
후보 72개 중 앞 8개(첫 검색어 영어 결과)만 잘라 봐서 제목에 제품 이름이 있는 한국어 영상이 한 번도 안 올라 재료 0개가 됐다.
고친 길: 제목 적중 먼저 → 검색어마다 번갈아."""
from tools.calcopy.hybrid import screen


def _c(i, q, title):
    return {"id": i, "q": q, "title": title}


def test_title_hits_first_then_round_robin():
    cands = [_c(f"en{k}", "moose maple butter", f"Miss Maple Moose recipe {k}") for k in range(10)]
    cands += [_c("ko1", "무스 메이플버터", "맛있어서 소개하는 무스메이플 버터"), _c("ko2", "무스 메이플버터", "코스트코 강추템(무스 메이플버터)")]
    cands += [_c("bb1", "아웃백 부시맨빵 버터", "아웃백 부시맨 브레드 만들기")]
    ids = screen.pick_ids(cands, ["무스 메이플버터", "MOOSE MAPLE BUTTER"], 8)
    assert ids[:2] == ["ko1", "ko2"]                 # 띄어쓰기 달라도(무스메이플 버터) 제목 적중
    assert "bb1" in ids                              # 다른 검색어 결과도 자리를 얻는다(첫 검색어가 다 먹지 않게)
    assert len(ids) == 8 and len(set(ids)) == 8


def test_no_keywords_round_robin_only():
    cands = [_c("a1", "A", "x"), _c("a2", "A", "x"), _c("b1", "B", "y")]
    assert screen.pick_ids(cands, [], 3) == ["a1", "b1", "a2"]
