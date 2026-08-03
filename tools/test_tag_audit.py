"""tag_audit 순수 로직 테스트 — DB도 Gemini도 안 부른다.

여기서 지키는 계약은 하나다: **코호트 A(저장 점수)와 B(재계산)를 절대 섞지 않는다.**
섞이면 커버리지 검사 유무 때문에 점수 체계가 달라져 배포 전후 비교가 조용히 틀어진다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import tag_audit  # noqa: E402


def _seg(i, start, end, text="말", desc="화면 묘사가 충분히 길다"):
    """★필드 타입은 script_extract의 스키마·정규화(:50, :189)를 그대로 따른다 —
    change는 **문자열**(사물 변화 한 줄), is_key/has_effect만 bool이다.
    여기서 타입을 지어내면 하네스가 계약을 발명해 0% 동작도 초록이 된다."""
    return {"seg_id": f"s{i}", "start": start, "end": end, "text": text,
            "scene_desc": f"{desc} {i}", "shot_role": "사용중",
            "change": f"사물이 변한다 {i}", "is_key": i == 1}


def _good_result(tag_qa_block=None):
    segs = [_seg(0, 0, 3), _seg(1, 3, 6), _seg(2, 6, 9)]
    r = {"segments": segs, "full_text": " ".join(s["text"] for s in segs)}
    if tag_qa_block is not None:
        r["tag_qa"] = tag_qa_block
    return r


def _row(shortcode, result, at="2026-08-01T10:00:00"):
    return (shortcode, json.dumps(result, ensure_ascii=False), at)


# ── 코호트 분리 ───────────────────────────────────────────────────

def test_저장점수가_있으면_A로_가고_그_값을_그대로_쓴다():
    rows = [_row("aaa", _good_result({"score": 0.42, "flags": ["훅 누락: 1.2초"],
                                      "retried": True}))]
    rec = tag_audit.score_rows(rows)[0]
    assert rec["cohort"] == "A"
    assert rec["score"] == 0.42          # 재계산으로 덮어쓰지 않는다
    assert rec["retried"] is True


def test_저장점수가_없으면_B로_가고_재계산된다():
    rec = tag_audit.score_rows([_row("bbb", _good_result())])[0]
    assert rec["cohort"] == "B"
    assert rec["score"] is not None


def test_summarize는_다른_코호트를_섞지_않는다():
    rows = [_row("a1", _good_result({"score": 0.10, "flags": [], "retried": False})),
            _row("b1", _good_result()),
            _row("b2", _good_result())]
    recs = tag_audit.score_rows(rows)
    a, b = tag_audit.summarize(recs, "A"), tag_audit.summarize(recs, "B")
    assert a["n"] == 1 and a["avg"] == 0.10
    assert b["n"] == 2
    assert b["avg"] != a["avg"]          # 합산 평균이었으면 같은 값이 나왔을 것


def test_A가_없으면_summarize가_None을_준다():
    """None이어야 main이 '기준선으로 삼지 마라' 경고를 띄운다."""
    recs = tag_audit.score_rows([_row("b1", _good_result())])
    assert tag_audit.summarize(recs, "A") is None


# ── 깨진 행 ───────────────────────────────────────────────────────

def test_파싱_실패는_버리지_않고_깨짐으로_남는다():
    recs = tag_audit.score_rows([("bad", "{not json", "2026-08-01")])
    assert recs[0]["cohort"] == "깨짐" and recs[0]["score"] is None


def test_옛_스키마로_채점이_죽어도_감사는_계속된다():
    """change가 bool인 옛 행(지금 스키마는 문자열) 하나 때문에 전체가 멈추면 안 된다.
    ★이 케이스는 실제로 잡혔다 — 처음엔 fixture가 bool이라 4건이 AttributeError로 터졌다."""
    bad = _good_result()
    bad["segments"][0]["change"] = True          # 옛 타입
    recs = tag_audit.score_rows([_row("old", bad), _row("b1", _good_result())])
    assert recs[0]["cohort"] == "깨짐"
    assert "채점 실패" in recs[0]["flags"][0]
    assert tag_audit.summarize(recs, "B")["n"] == 1   # 멀쩡한 행은 그대로 집계된다


def test_깨짐은_어느_코호트_집계에도_안_들어간다():
    recs = tag_audit.score_rows([("bad", "{", "x"),
                                 _row("b1", _good_result())])
    assert tag_audit.summarize(recs, "B")["n"] == 1
    assert tag_audit.summarize(recs, "A") is None


# ── 집계 ─────────────────────────────────────────────────────────

def test_flag는_수치를_떼고_종류로_묶인다():
    """'커버리지 부족: 68%'와 '...71%'가 따로 세지면 최빈 집계가 무의미해진다."""
    rows = [_row("a1", _good_result({"score": 0.5,
                                     "flags": ["커버리지 부족: 영상 30초 중 68%만 태깅됨"]})),
            _row("a2", _good_result({"score": 0.5,
                                     "flags": ["커버리지 부족: 영상 20초 중 71%만 태깅됨"]}))]
    top = tag_audit.summarize(tag_audit.score_rows(rows), "A")["top_flags"]
    assert top == [("커버리지 부족", 2)]


def test_최악_목록은_점수_오름차순이다():
    rows = [_row(f"a{i}", _good_result({"score": s, "flags": []}))
            for i, s in enumerate([0.9, 0.2, 0.55])]
    worst = tag_audit.summarize(tag_audit.score_rows(rows), "A")["worst"]
    assert [w["score"] for w in worst] == [0.2, 0.55, 0.9]


def test_재시도선_미만_건수는_0_6_기준이다():
    """script_extract._QA_RETRY_BELOW와 같은 값이어야 '재시도가 걸렸어야 할 수준'이 읽힌다."""
    rows = [_row(f"a{i}", _good_result({"score": s, "flags": []}))
            for i, s in enumerate([0.59, 0.60, 0.61])]
    assert tag_audit.summarize(tag_audit.score_rows(rows), "A")["below_retry_line"] == 1


def test_히스토그램_합은_표본수와_같다():
    rows = [_row(f"a{i}", _good_result({"score": s, "flags": []}))
            for i, s in enumerate([0.0, 0.35, 0.5, 0.75, 1.0])]
    s = tag_audit.summarize(tag_audit.score_rows(rows), "A")
    assert sum(b["n"] for b in s["hist"]) == s["n"] == 5   # 1.0이 구간 밖으로 새지 않는다
