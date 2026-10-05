# -*- coding: utf-8 -*-
"""신호어(고조·반전 칸 첫머리) 점검 — 세트 주인은 story_writer.py 하나다. 이 도구는 **재기만** 한다.

(a) 세트 다양성: 회원 100명(작업 key 100개)이 돌려 쓸 때 서로 다른 조합 수 · 가장 흔한 조합 몫 ·
    첫 신호어([1]) 겹침률(아무 두 명이 같은 [1]을 받을 확률) — 지금 코드 vs git HEAD(고치기 전) 대조.
(b) 저장된 스토리보드(%TEMP%\\sbtrial_*.json): 고조·반전 계열 칸 중 신호어로 연 비율
    — 저장본 그대로(고치기 전 결과) / story_writer.storyboard_signals 를 적용한 뒤 — 와 어색한 결합 사례.

  py tools/storyboard_mock/audit_signals.py
"""
import glob
import os
import re
import subprocess
import sys
import zlib
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shopping_shorts import story_writer as sw          # noqa: E402
from shopping_shorts import storyboard as sbd           # noqa: E402

# 신호어 꼴(넓게) — signal_census.py 와 같은 꼴. 저장본 판정용(코드가 박는 낱말 목록과 별개로 '신호어로 열었나'만 본다)
from signal_census import SIG                           # noqa: E402

AWK = [("신호어 뒤 접속사·신호어 겹침", re.compile(r"^(?:근데|그런데|그리고|그래서|또|하지만|심지어|게다가|거기다|무엇보다|뿐만)\s")),
       ("신호어 뒤 조사만 남음", re.compile(r"^(?:은|는|이|가|을|를|도|에|의)(?:\s|$)")),
       ("'이게'가 두 번", re.compile(r"^(?:이게|이건|이거)\s")),
       ("빈 문장", re.compile(r"^\s*$"))]
# [1] 꼴("~게")은 히트작에서 "…다는 거 / …다고"로 받는다 — 설명문 어미(~됩니다·~주세요)로 끝나면 어색하다(코드는 어미를 못 고친다 → 프롬프트 몫)
FIRST_END = re.compile(r"(?:거|것|다고|거든요?|잖아요?|거죠|다니까요?|더라고요?)[.!?~…]*$")


def old_sets():
    """git HEAD 의 YT_SETS(고치기 전 8세트)."""
    try:
        src = subprocess.run(["git", "-C", ROOT, "show", "HEAD:shopping_shorts/story_writer.py"],
                             capture_output=True, encoding="utf-8").stdout
    except OSError:
        return {}
    m = re.search(r"^YT_SETS = \{.*?^\}", src, re.S | re.M)
    ns = {}
    exec(m.group(0), ns) if m else None                  # noqa: S102 — 우리 저장소 코드
    return ns.get("YT_SETS") or {}


def diversity(pick, n=100):
    combos = [tuple(pick("member%03d" % i)) for i in range(n)]
    c = Counter(combos)
    first = Counter(x[0] for x in combos)
    same_first = sum(v * (v - 1) for v in first.values()) / (n * (n - 1))
    rep = sum(1 for x in combos if len([w for w in x if w]) != len({w for w in x if w}))
    return {"조합 수": len(c), "최다 조합 몫": "%d/%d" % (c.most_common(1)[0][1], n),
            "[1] 종류": len(first), "[1] 겹침률": "%.1f%%" % (100 * same_first), "한 편 안 반복": rep}


def part_a():
    print("== (a) 세트 다양성 — 회원 100명 ==")
    old = old_sets()
    if old:
        names = sorted(old)

        def old_pick(key):
            return old[names[zlib.crc32(key.encode()) % len(names)]]
        print("  고치기 전(YT 8세트):", diversity(old_pick))
    if hasattr(sw, "pick_signals"):
        print("  지금(YT):", diversity(lambda k: sw.pick_signals("yt", k, 0)[1]))
        print("  지금(IG):", diversity(lambda k: sw.pick_signals("ig", k, 0)[1]))
        print("  가능한 조합 수(YT/IG):", sw.signal_combo_count("yt"), "/", sw.signal_combo_count("ig"))


def kinds_of(slots):
    """storyboard 가 칸 → 신호어 자리 종류를 정하는 함수를 그대로 쓴다(없으면 고치기 전 = 이름으로만)."""
    if hasattr(sbd, "signal_kinds"):
        return sbd.signal_kinds(slots)
    esc, tw = sbd.EXTRA_KIN["escalation"], sbd.EXTRA_KIN["twist"]
    return [("esc" if str(s.get("slot") or "").split("_")[0].lower() in esc else
             "twist" if str(s.get("slot") or "").split("_")[0].lower() in tw else "") for s in slots]


def part_b():
    print("== (b) 저장된 스토리보드 ==")
    tmp = os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
    files = sorted(glob.glob(os.path.join(tmp, "sbtrial_*.json")))
    tot = before = after = 0
    awk = []
    import copy
    import json
    for p in files:
        d = json.load(open(p, encoding="utf-8"))
        for k, b in (d.get("boards") or {}).items():
            slots = b.get("slots") or []
            kinds = kinds_of(slots)
            idx = [i for i, x in enumerate(kinds) if x]
            tot += len(idx)
            before += sum(1 for i in idx if SIG.match(slots[i].get("line") or ""))
            if hasattr(sw, "storyboard_signals"):
                s2 = copy.deepcopy(slots)
                names = (d.get("family_names") or {}).get(k) or []
                yt = any(str(n).startswith("유튜브") for n in names) if names else                     sw.seed_platform(" ".join(x.get("line") or "" for x in slots)) == "yt"
                sbd.apply_signals(s2, key="%s:%s" % (d.get("job"), k), nth=0, yt=yt)
                for i in idx:
                    line = s2[i].get("line") or ""
                    w = s2[i].get("signal") or ""
                    if w and line.startswith(w):
                        after += 1
                        rest = line[len(w):].strip()
                        for name, rx in AWK:
                            if rx.search(rest):
                                awk.append((os.path.basename(p), k, name, line))
                        if re.search(r"(?:건|는)$", w) and re.search(r"(?:세요|주세요|십시오)[.!?~]*$", line):
                            awk.append((os.path.basename(p), k, "'~건/~는' 뒤 명령형(어미)", line))
                        if w.endswith("게") and not FIRST_END.search(line):
                            awk.append((os.path.basename(p), k, "[1] 꼴인데 '~다는 거'로 안 받음(어미)", line))
                    print("   %-26s %-5s %-3s %-12s %s" % (os.path.basename(p)[:26], k, "yt" if yt else "ig", s2[i].get("slot"), line))
    print("  파일 %d · 고조·반전 계열 칸 %d" % (len(files), tot))
    print("  신호어로 연 칸 — 저장본 그대로: %d/%d" % (before, tot))
    if hasattr(sw, "storyboard_signals"):
        print("  신호어로 연 칸 — 박기 적용 뒤: %d/%d" % (after, tot))
        print("  어색한 결합: %d건" % len(awk))
        for a in awk:
            print("    ", a)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, os.path.dirname(__file__))
    part_a()
    part_b()
