# -*- coding: utf-8 -*-
"""손으로 넣은 재료 vs 태깅에서 뽑은 재료 — 대본이 달라지나 (2026-09-22).

★왜 재야 하나: 지금까지 시험은 내가 pain을 손으로 써 넣고 돌렸다. 그건 **내가 정답을 흘려준 것**이라
  "대본이 좋다"는 결론이 라이브에서도 성립한다는 보장이 없다
  (메모리: 지어낸소재_지어낸결론 — 테스트 소재를 지어내면 지어낸 결론이 나온다).
  그래서 **같은 씨앗·같은 프롬프트**로 재료만 바꿔 뽑아 나란히 본다.

★노바와 우리가 다른 점(2026-09-22 사장님 질문): 노바는 씨앗 1편만 보고 쓰고 화면은 나중에
  인터넷에서 찾는다. 우리는 고객이 **이미 담은 영상**이 있고 태깅까지 돼 있다.
  그래서 한 단계(태깅→pain)를 더 한다 — 씨앗에 없는 장점을 재료에서 찾아 디벨롭하고,
  **있는 화면 안에서** 말하기 위해서다. 단 흐름의 주인은 씨앗이고 태깅은 재료일 뿐이다.

쓰기(서버, env 필요):
  python3 tools/seed_analyzer/compare_pain.py --job 13d4cab55fba --case 두피빗
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
sys.path.insert(0, HERE)

import pain_extract as PX  # noqa: E402
import insta_writer as IW  # noqa: E402
from cases import CASES  # noqa: E402
from try_writer import DEMO  # noqa: E402


def show(title, feats):
    print("── %s (%d개) ──" % (title, len(feats)))
    for f in feats:
        print("   ■ %s — %s" % (f.get("name"), (f.get("claim") or "")[:60]))
        print("      pain: %s" % ((f.get("pain") or "(빈칸)")[:78]))
    print()


def write_one(d, feats, label):
    from shopping_shorts import script_generate as _sg
    dd = dict(d, feats=feats)
    p = IW.build(dd)
    o = _sg._call_json(p, IW.SCHEMA) or {}
    lines = IW.to_lines(o, "A")
    au = IW.audit(lines, o, feats)
    print("========== %s ==========" % label)
    print("  고조 %d칸(불편 %d) · 인스타어미 %d%% · 썰어미 %d · 설명문 %d · 근거없음 %d"
          % (au["beats"], au["pain"], au["insta_end_rate"],
             len(au["yt_ending"]), len(au["flat"]), len(au["ungrounded"])))
    for l in lines:
        print("  [%s] %s" % (l["beat"], l["text"]))
    print()
    return au


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--case", default="")
    ap.add_argument("--product", default="")
    a = ap.parse_args()

    from shopping_shorts.store import Store
    from shopping_shorts import app as A
    store = Store("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
    job = A._enrich_job_extract(store.get_mix_job(a.job), store) or {}
    ext = job.get("extract") or {}

    # ★같은 제품으로 비교해야 한다 — 씨앗도 그 job에서 가져온다
    #   (2026-09-22 첫 시험 결함: 씨앗은 두피빗인데 태깅은 아일릿 펀치라 비교가 성립 안 했다)
    from shopping_shorts import backbone_assemble as ba
    srcs = ba.sources_from_extract(ext)
    seed = ba.seed_source(srcs, job.get("backbone_main")) or {}
    seed_text = (seed.get("full_text") or "").strip()
    base = CASES.get(a.case) or DEMO
    product = a.product or base["product"]
    if seed_text and not a.case:
        base = dict(base, seed=seed_text, product=product)
        print("씨앗: %s (%d자) — 이 job의 것\n" % (seed.get("video_id"), len(seed_text)))

    auto = PX.extract_pain(ext, product)
    show("태깅에서 뽑은 재료", auto)
    show("손으로 넣은 재료", base["feats"])

    r1 = None
    if a.case:      # 손으로 넣은 재료는 그 case가 있을 때만 의미가 있다
        r1 = write_one(base, base["feats"], "손으로 넣은 재료로 쓴 대본")
    r2 = write_one(base, auto, "태깅에서 뽑은 재료로 쓴 대본")

    if r1:
        print("== 나란히 ==")
        for k, t in (("beats", "고조 칸"), ("insta_end_rate", "인스타 어미%"),
                     ("pain", "불편 개수")):
            print("   %-12s 손 %-6s 태깅 %s" % (t, r1[k], r2[k]))
        print("   %-12s 손 %-6d 태깅 %d" % ("썰어미 줄", len(r1["yt_ending"]), len(r2["yt_ending"])))
        print("   %-12s 손 %-6d 태깅 %d" % ("설명문 줄", len(r1["flat"]), len(r2["flat"])))


if __name__ == "__main__":
    main()
