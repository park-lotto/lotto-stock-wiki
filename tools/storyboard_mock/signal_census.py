# -*- coding: utf-8 -*-
"""히트 대본의 고조·반전 신호어(칸 첫머리 낱말)를 전수로 센다 — 신호어 세트(story_writer.YT_SETS·IG_SETS)의 근거.

재료(읽기만 한다 — main 폴더):
  유튜브(썰) = raw/analysis/썰쇼핑_*/hits_subs*.json 자막 전사본(video_id 로 중복 제거)
  인스타     = docs/tone_census_2026-09-22/corpus60*.json 의 인스타 씨앗(히트작) 전문
              ※ 인스타 641편 코퍼스(/tmp/hits_cls_all.json)는 서버 임시파일이라 로컬에 없다.
  ★2026-10-05 재료 범위 실측: main 의 raw/analysis 는 썰쇼핑 3폴더뿐, research/·out/ 에 자막 전사본 없음
   (out/*판정_원본.json 은 제목·채널만), reference.db 의 script_wiki 2편·pattern_source 15편은 출처 불명이라 뺐다.
자리: 한 편 안에서 신호어가 나온 순서 — 1번째 = [1]대비, 2번째 = [2]더하기, 마지막(3개 이상일 때) = [3]최고 반전.

  py tools/storyboard_mock/signal_census.py            # 표(꼴·횟수·편수·채널 수·자리·채택 판정)
  py tools/storyboard_mock/signal_census.py --discover # + 목록 밖 n-gram 발굴
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
# ★2026-10-05 확장(사장님 "더 다양하게, 억지스럽지 않게 많이 쓰는 것"): discover() 의 n-gram 전수에서 새로 나온 꼴
#   "…포인트는 따로 있었는데" · "근데 진짜는 여기서부터" · "(진짜) 반전은" · "여기서 끝이 아니라" · "소름 돋는 건" ·
#   "충격적인 사실은" 을 앞에 둔다(긴 꼴이 먼저 맞아야 "근데 진짜 미친 포인트는"에서 잘리지 않는다).
SIG = re.compile(
    r"(?:(?:근데|그런데|하지만)\s)?(?:(?:진짜|더|가장|제일)\s?){0,2}(?:(?:미친|충격적인|놀라운|대박인|소름\s?돋는)\s?)?"
    r"(?:포인트는|활용법은|건)\s따로\s있었는데"
    r"|(?:(?:근데|그런데|하지만)\s)?진짜는\s여기서부터"
    r"|(?:(?:근데|그런데|하지만)\s)?(?:(?:진짜|더)\s)?반전은"
    r"|(?:하지만\s)?여기서\s끝이\s아니라"
    r"|(?:(?:근데|그런데|하지만|그리고)\s)?(?:(?:이게|이건|진짜|정말|더|제일|가장|여기서)\s?){0,3}"
    r"(?:말도\s?안\s?되는|미친|충격적인|대박인|놀라운|소름\s?돋는|신기한|기가\s?막힌|어이없는|웃긴|사기인|레전드인)\s?"
    r"(?:포인트인\s?게|포인트는|포인트가|포인트|게|거는|건|점은|부분은|사실은)"
    r"|심지어|게다가|거기다가?|무엇보다|뿐만\s?아니라|더\s?좋은\s?건|제일\s?좋은\s?건")

# 채택 기준(억지스럽지 않게 = 여러 사람이 실제로 쓰는 말): 서로 다른 영상 MIN_DOCS 편↑ · 서로 다른 채널 MIN_CH 개↑
#   · 등장 순서로 본 자리 몫 MIN_RANK_SHARE↑. 5편 = 1~4편짜리는 한 채널 말버릇·자막 오인식("미신 포인트")과
#   구별이 안 된다(실측 표의 '버림' 줄). 채널 2개↑ = 한 채널 말버릇 제외.
MIN_DOCS, MIN_CH, MIN_RANK_SHARE = 5, 2, 0.6
# 숫자는 넘어도 버린 꼴(눈으로 문맥 확인 — 2026-10-05). 판정표에 이유로 찍힌다.
REJECT = {
    "포인트는 따로 있었는데": "앞 낱말이 잘린 꼴(…소름인/활용/진짜 포인트는) — 홀로 첫머리에 안 쓴다",
    "반전은": "늘 앞 낱말이 붙어 나온다(…반전은) — 홀로 첫머리에 안 쓴다",
    "활용법은 따로 있었는데": "내용 의존 — 반전이 '쓰임새'일 때만 맞는다",
    "근데 진짜 미친 활용법은 따로 있었는데": "내용 의존 — 반전이 '쓰임새'일 때만 맞는다",
    "진짜 미친 활용법은 따로 있었는데": "내용 의존 — 반전이 '쓰임새'일 때만 맞는다",
    "근데 미친 활용법은 따로 있었는데": "내용 의존 — 반전이 '쓰임새'일 때만 맞는다",
}
# discover 에서 많이 나왔지만 신호어 꼴이 아닌 것: "~는 기본이고"(128편)·"~는 물론이고"(57)·"~데다가"(45) =
#   앞에 명사구가 있어야 서는 말(칸 첫머리에 박을 수 없다) / "깔끔하게·완벽하게" = 부사 / "이게·이건" = 지시어.
# 첫머리 n-gram 발굴용 끝 꼴(신호어가 끝나는 모양) — 목록에 없는 꼴을 데이터에서 찾는다
DISC_END = re.compile(r"(건|게|포인트는|포인트인게|점은|부분은|반전은|진짜는|핵심은|비밀은|사실은|여기서부터|따로 있었는데|"
                      r"기본이고|물론이고|아니라|데다가)$")


def norm(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"말도\s?안\s?되는", "말도 안 되는", s)
    s = re.sub(r"되는 ?게$", "되는게", s)
    return s


def yt_texts():
    """[(채널, 전문)] — video_id 로 중복 제거. 재료: 썰쇼핑 자막 3폴더 + 톤 조사 폴더의 유튜브 씨앗."""
    seen = {}
    for f in sorted(glob.glob(os.path.join(MAIN, "raw", "analysis", "썰쇼핑_*", "hits_subs*.json"))):
        for r in json.load(open(f, encoding="utf-8")):
            vid = r.get("video_id")
            t = " ".join(s[1] for s in (r.get("segments") or []) if len(s) > 1)
            if vid and t and len(t) > len(seen.get(vid, ("", ""))[1]):
                seen[vid] = (r.get("channel_id") or r.get("channel") or "?", t)
    for r in _tone_seeds("yt"):
        if r["seed_vid"] not in seen:
            seen[r["seed_vid"]] = ("?seed:" + str(r["seed_vid"]), r["seed_text"])   # 채널 정보 없음 = 영상마다 따로 친다
    return list(seen.values())


def _tone_seeds(platform):
    out = {}
    for f in glob.glob(os.path.join(MAIN, "docs", "tone_census_2026-09-22", "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for r in d if isinstance(d, list) else []:
            if isinstance(r, dict) and r.get("seed_platform") == platform and r.get("seed_text"):
                out[r.get("seed_vid")] = r
    return list(out.values())


def ig_texts():
    """인스타 씨앗 전문 — 톤 조사 폴더 전체(라운드·코퍼스). 채널 정보가 없어 영상마다 따로 친다."""
    return [("?seed:%s" % r.get("seed_vid"), r["seed_text"]) for r in _tone_seeds("ig")]


def census(texts):
    """texts = [(채널, 전문)]. 꼴마다 횟수·편수·채널 수, 자리(편 안 등장 순서)별 횟수."""
    allc, pos = collections.Counter(), {1: collections.Counter(), 2: collections.Counter(), 3: collections.Counter()}
    docs, chs = collections.defaultdict(set), collections.defaultdict(set)
    rel = collections.defaultdict(collections.Counter)
    with_sig = 0
    for i, (ch, t) in enumerate(texts):
        hits = [norm(m.group(0)) for m in SIG.finditer(t)]
        if not hits:
            continue
        with_sig += 1
        allc.update(hits)
        for h in hits:
            docs[h].add(i)
            chs[h].add(ch)
        pos[1][hits[0]] += 1
        if len(hits) >= 2:                      # 두 개 이상 나온 편에서만 상대 순서를 본다(하나뿐인 편은 늘 1번째라 자리를 못 가른다)
            for j, h in enumerate(hits):
                rel[h]["first" if j == 0 else "last" if j == len(hits) - 1 else "mid"] += 1
        if len(hits) >= 2:
            pos[2][hits[1]] += 1
        if len(hits) >= 3:
            pos[3][hits[-1]] += 1
    return {"n": len(texts), "with_sig": with_sig, "all": allc, "pos": pos,
            "docs": {k: len(v) for k, v in docs.items()}, "chs": {k: len(v) for k, v in chs.items()}, "rel": rel}


def rank_of(c, k):
    """자리 판정 — 신호어가 2개 이상 나온 편에서 그 꼴이 첫째로 나온 몫 / 마지막으로 나온 몫.
    첫째 ≥ MIN_RANK_SHARE → [1] · 마지막 ≥ MIN_RANK_SHARE → [3] · 그 밖에 첫째가 아닌 몫 ≥ MIN_RANK_SHARE → [2]."""
    r = c["rel"].get(k) or collections.Counter()
    tot = sum(r.values())
    if not tot:
        return 0, 0.0
    f, l = r["first"] / tot, r["last"] / tot
    if f >= MIN_RANK_SHARE:
        return 1, f
    if l >= MIN_RANK_SHARE:
        return 3, l
    return (2, 1 - f) if 1 - f >= MIN_RANK_SHARE else (0, max(f, l))


def family(k):
    """비슷한 꼴 한 묶음 — 앞 접속사(근데·그런데·하지만)·'진짜'·띄어쓰기 차이를 지운 키."""
    k = re.sub(r"^(?:근데|그런데|하지만|그리고)\s", "", k)
    return re.sub(r"\s+", "", re.sub(r"(?:^|\s)진짜(?=\s)", " ", " " + k))


def family_rel(c):
    out = collections.defaultdict(collections.Counter)
    for k, r in c["rel"].items():
        out[family(k)].update(r)
    return out


def verdict(c, k):
    """채택 판정: 그 꼴의 편수·채널 수 + 자리(묶음 전체의 등장 순서 — 표본이 적은 변형이 따로 갈리지 않게)."""
    if k in REJECT:
        return "버림(" + REJECT[k] + ")"
    d, ch = c["docs"].get(k, 0), c["chs"].get(k, 0)
    fam = c.get("_fam") or family_rel(c)
    c["_fam"] = fam
    p, share = rank_of({"rel": fam}, family(k))
    if d < MIN_DOCS:
        return "버림(편수 %d<%d)" % (d, MIN_DOCS)
    if ch < MIN_CH:
        return "버림(채널 %d<%d)" % (ch, MIN_CH)
    if not p:
        return "버림(자리 갈림 묶음 첫%d·중%d·끝%d)" % tuple(fam[family(k)][x] for x in ("first", "mid", "last"))
    return "채택[%d] %.0f%%" % (p, 100 * share)


def discover(texts, known=(), top=60):
    """목록 밖 꼴 발굴 — 전문의 모든 위치에서 1~4어절 n-gram 중 DISC_END 로 끝나는 것을 편수·채널 수로 센다.
    비슷한 꼴(띄어쓰기·'거는/건'·'되는 거/게')은 한 키로 묶어 합산하고 가장 흔한 표기를 보인다."""
    docs, chs, surf = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(collections.Counter)
    for i, (ch, t) in enumerate(texts):
        w = re.sub(r"[.,!?~…]", " ", t).split()
        for a in range(len(w)):
            for n in range(1, 5):
                if a + n > len(w):
                    break
                g = " ".join(w[a:a + n])
                if DISC_END.search(g):
                    key = re.sub(r"\s+", "", g).replace("거는", "건").replace("되는거", "되는게")
                    docs[key].add(i)
                    chs[key].add(ch)
                    surf[key][g] += 1
    kn = {re.sub(r"\s+", "", k) for k in known}
    rows = [(len(docs[k]), len(chs[k]), surf[k].most_common(1)[0][0]) for k in docs
            if len(docs[k]) >= MIN_DOCS and len(chs[k]) >= MIN_CH and k not in kn]
    return sorted(rows, reverse=True)[:top]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = {}
    for name, texts in (("yt", yt_texts()), ("ig", ig_texts())):
        c = census(texts)
        print("=== %s %d편 · 채널 %d (신호어 있는 편 %d) ===" % (name, c["n"], len({ch for ch, _ in texts}), c["with_sig"]))
        print("   %-28s %5s %4s %4s   첫  중  끝(2개↑ 편)  판정" % ("꼴", "횟수", "편", "채널"))
        for k, v in c["all"].most_common(70):
            r = c["rel"][k]
            print("   %-28s %5d %4d %4d   %3d %3d %3d   %s" % (k, v, c["docs"][k], c["chs"][k], r["first"], r["mid"],
                                                          r["last"], verdict(c, k)))
        if "--discover" in sys.argv:
            print("   --- 목록 밖 n-gram (편 %d↑·채널 %d↑, 1~4어절) ---" % (MIN_DOCS, MIN_CH))
            for d, ch, g in discover(texts, c["all"]):
                print("   %4d편 %3d채널  %s" % (d, ch, g))
        out[name] = {"n": c["n"], "with_sig": c["with_sig"], "all": dict(c["all"].most_common()),
                     "docs": c["docs"], "chs": c["chs"], "verdict": {k: verdict(c, k) for k in c["all"]},
                     "rel": {k: dict(v) for k, v in c["rel"].items()},
                     "pos": {str(p): dict(c["pos"][p].most_common()) for p in c["pos"]}}
    if "--json" in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
