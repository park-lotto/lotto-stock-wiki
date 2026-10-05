# -*- coding: utf-8 -*-
"""히트 대본의 고조·반전 신호어(칸 첫머리 낱말)를 전수로 센다 — 신호어 세트(story_writer.YT_SETS·IG_SETS)의 근거.

재료(읽기만 한다 — main 폴더):
  유튜브(썰) = raw/analysis/썰쇼핑_*/hits_subs*.json 자막 전사본(video_id 로 중복 제거)
  인스타     = docs/tone_census_2026-09-22/corpus60*.json 의 인스타 씨앗(히트작) 전문
              ※ 인스타 641편 코퍼스(/tmp/hits_cls_all.json)는 서버 임시파일이라 로컬에 없다.
자리: 한 편 안에서 신호어가 나온 순서 — 1번째 = [1]대비, 2번째 = [2]더하기, 마지막(3개 이상일 때) = [3]최고 반전.

  py tools/storyboard_mock/signal_census.py            # 표 출력
  py tools/storyboard_mock/signal_census.py --json out.json
"""
import collections
import glob
import json
import os
import re
import sys

MAIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if not os.path.isdir(os.path.join(MAIN, "raw")):          # 트랙 폴더가 아니라 main 폴더에서 돌렸을 때
    MAIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# 신호어 꼴(넓게 잡고 낱말 그대로 센다). 길게 맞는 꼴이 먼저.
SIG = re.compile(
    r"(?:(?:근데|그런데|하지만|그리고)\s)?(?:(?:이게|이건|진짜|정말|더|제일|가장|여기서)\s?){0,3}"
    r"(?:말도\s?안\s?되는|미친|충격적인|대박인|놀라운|소름\s?돋는|신기한|기가\s?막힌|어이없는|웃긴|사기인|레전드인)\s?"
    r"(?:포인트인\s?게|포인트는|포인트가|포인트|게|거는|건|점은|부분은)"
    r"|심지어|게다가|거기다가?|무엇보다|뿐만\s?아니라|더\s?좋은\s?건|제일\s?좋은\s?건")


def norm(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"말도\s?안\s?되는", "말도 안 되는", s)
    s = re.sub(r"되는 ?게$", "되는게", s)
    return s


def yt_texts():
    seen = {}
    for f in sorted(glob.glob(os.path.join(MAIN, "raw", "analysis", "썰쇼핑_*", "hits_subs*.json"))):
        for r in json.load(open(f, encoding="utf-8")):
            vid = r.get("video_id")
            t = " ".join(s[1] for s in (r.get("segments") or []) if len(s) > 1)
            if vid and t and len(t) > len(seen.get(vid, "")):
                seen[vid] = t
    return list(seen.values())


def ig_texts():
    seen = {}
    for f in glob.glob(os.path.join(MAIN, "docs", "tone_census_2026-09-22", "corpus60*.json")):
        for r in json.load(open(f, encoding="utf-8")):
            if r.get("seed_platform") == "ig" and r.get("seed_text"):
                seen[r.get("seed_vid")] = r["seed_text"]
    return list(seen.values())


def census(texts):
    allc, pos = collections.Counter(), {1: collections.Counter(), 2: collections.Counter(), 3: collections.Counter()}
    with_sig = 0
    for t in texts:
        hits = [norm(m.group(0)) for m in SIG.finditer(t)]
        if not hits:
            continue
        with_sig += 1
        allc.update(hits)
        pos[1][hits[0]] += 1
        if len(hits) >= 2:
            pos[2][hits[1]] += 1
        if len(hits) >= 3:
            pos[3][hits[-1]] += 1
    return {"n": len(texts), "with_sig": with_sig, "all": allc, "pos": pos}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = {}
    for name, texts in (("yt", yt_texts()), ("ig", ig_texts())):
        c = census(texts)
        print("=== %s %d편 (신호어 있는 편 %d) ===" % (name, c["n"], c["with_sig"]))
        for k, v in c["all"].most_common(30):
            print("   %-24s %4d   [1]%3d [2]%3d [3]%3d" % (k, v, c["pos"][1][k], c["pos"][2][k], c["pos"][3][k]))
        out[name] = {"n": c["n"], "with_sig": c["with_sig"], "all": dict(c["all"].most_common()),
                     "pos": {str(p): dict(c["pos"][p].most_common()) for p in c["pos"]}}
    if "--json" in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
