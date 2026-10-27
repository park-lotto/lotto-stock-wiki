# -*- coding: utf-8 -*-
"""커뮤니티 반응 좋은 글 제목 → 썰쇼핑감 고르기(제미니 키풀 — 버텍스 안 씀). 서버 /tmp/banggu_pkg 에서 환경 실어 실행.
  python3 community_classify.py --src bobae_best.json --min-recomm 300 --out /tmp/community_pick.json
판정 기준(사장님 2026-10-07): 썰쇼핑과 이어지려면 **살 수 있는 제품·식품**이 있어야 하고, 반응 좋았던 글이어야 한다.
"""
import argparse, json, sys, time
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

PROMPT = """아래는 한국 커뮤니티(보배드림 베스트)에서 반응이 좋았던 글 제목들이다(추천·조회·댓글 수 포함).
쇼핑 쇼츠 '썰' 소재가 되는 것만 골라라.

썰쇼핑 소재의 조건
- 제목에 **살 수 있는 제품·식품·브랜드 상품**이 있거나, 그 글을 보고 사람들이 찾아볼 제품이 분명하다(라면·과자·생활용품·가전·매장 상품 등).
- "아 그래? / 그런 일이 있었어?" 하는 사건·뒷이야기·반전·숨은 사실이 있다.
- 사람 비방·사고·정치·혐오가 중심인 글은 빼라(제품이 곁가지인 갑질·사고 글 포함).

고른 글마다
- n        : 아래 번호
- product  : 연결할 상품(구체적으로, 예: "오뚜기 진라면", "다이소 차키 배터리")
- angle    : 이 글의 '아 그래?' 한 줄
- kind     : 뉴스 사건 | 논란 | 기업 대응 | 숨은 사실 | 리뉴얼·단종 | 발명 | 꿀팁 | 기타
- score    : 썰쇼핑감 점수 0~10 (제품 연결이 분명하고 뒷이야기가 셀수록 높다)

출력은 JSON 객체 하나: {"picks": [{"n": 3, "product": "...", "angle": "...", "kind": "...", "score": 8}]}

[글]
%s"""


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); ap.add_argument("--min-recomm", type=int, default=300)
    ap.add_argument("--out", default="/tmp/community_pick.json"); ap.add_argument("--batch", type=int, default=80)
    a = ap.parse_args()
    from shopping_shorts import usage_meter
    from shopping_shorts import script_generate as _sg
    # ★버텍스는 유료다(사장님 2026-10-07) — 분석은 제미니 키풀로만(vertex=False). 실패하면 그 묶음을 건너뛴다.
    SCHEMA = {"type": "object", "properties": {"picks": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"}, "product": {"type": "string"}, "angle": {"type": "string"}, "kind": {"type": "string"},
        "score": {"type": "integer"}}, "required": ["n", "product", "angle", "kind", "score"]}}}, "required": ["picks"]}

    def call(prompt):
        note = {}
        out = _sg._call_json(prompt, SCHEMA, note=note, vertex=False)
        if not out:
            raise RuntimeError("제미니 키 호출 실패: %s" % (note.get("reason") or "빈 응답"))
        return out

    rows = [x for x in json.load(open(a.src, encoding="utf-8")) if x["recomm"] >= a.min_recomm]
    rows.sort(key=lambda x: -x["recomm"])
    picks = []
    with usage_meter.track(op="커뮤니티분류", customer_id=0):
        for i in range(0, len(rows), a.batch):
            chunk = rows[i:i + a.batch]
            lines = "\n".join("%d. %s (추천 %d · 조회 %d · 댓글 %d · %s)" % (k, x["title"], x["recomm"], x["views"], x["replies"], x["date"]) for k, x in enumerate(chunk))
            try:
                out = call(PROMPT % lines)
            except (RuntimeError, ValueError) as e:
                print("묶음 %d 실패: %s" % (i, e)); continue
            for p in out.get("picks") or []:
                k = p.get("n")
                if isinstance(k, int) and 0 <= k < len(chunk):
                    picks.append(dict(chunk[k], **{key: p.get(key) for key in ("product", "angle", "kind", "score")}))
            print("묶음 %d~%d: 고른 것 누적 %d" % (i, i + len(chunk), len(picks)), flush=True)
    picks.sort(key=lambda x: (-(x.get("score") or 0), -x["recomm"]))
    json.dump(picks, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n===== %d건 중 %d건 고름" % (len(rows), len(picks)))
    for x in picks[:40]:
        print("%2s %5d %7d | %-22s | %s | %s" % (x.get("score"), x["recomm"], x["views"], (x.get("product") or "")[:22], x["title"][:40], x.get("angle") or ""))


if __name__ == "__main__":
    main()
