# -*- coding: utf-8 -*-
"""★정교한 분류의 핵심 — **고정 어구를 자막에서 직접 캐낸다** (2026-09-05).

## 왜 정규식 6축으로는 부족한가

`classify_scripts.py`의 6축은 내가 **미리 정한 패턴**에 맞춰본다. 그래서
"결과예고냐 금지경고냐" 정도만 갈리고, **문장 구조가 진짜 같은지는 못 본다.**

오용형·은폐형이 축으로 인정된 근거는 딱 하나였다 —
    **"볼드 어구가 글자 그대로 동일. 소재만 갈아끼운다"**
정규식은 그걸 못 센다. 내가 아는 문형만 확인할 뿐 **모르는 문형은 영영 못 찾는다.**

## 그래서 뒤집는다 — 내가 패턴을 정하지 않는다

전사 전체에서 **n-gram(연속 어절)을 세어**, 여러 채널에 걸쳐 반복되는 어구를 캐낸다.
그게 곧 그 장르의 고정 어구다. 사람이 미리 알 필요가 없다.

    ① 자막을 어절로 쪼갠다
    ② 3~9어절 n-gram을 전부 센다
    ③ ★**채널 수**로 거른다 — 한 채널에서 100번 나오면 그건 그 채널 습관이다
       (1차 시도의 A 비법조제형이 17/20 한 채널이라 실패했다)
    ④ 소재어(제품명)는 빼고 **기능어 뼈대**만 남긴다
    ⑤ 남은 어구들이 함께 나타나는 영상끼리 묶는다 = 스타일 후보

## 소재 갈아끼우기를 감지하는 법

"선풍기에 비닐봉지를 씌우면" / "세탁기에 식초를 부으면" 은 소재만 다르고 뼈대가 같다.
숫자·제품명 같은 **가변 자리를 마스킹**해서 같은 틀로 본다.

    선풍기에 비닐봉지를 씌우면 놀라운 일이 벌어집니다
    → ⬛에 ⬛를 씌우면 놀라운 일이 벌어집니다     ← 이 뼈대가 반복되면 고정 어구

실행:
    py scripts/mine_phrases.py                      # 채널 3개+ 에서 반복되는 어구
    py scripts/mine_phrases.py --min-ch 5 --top 60
    py scripts/mine_phrases.py --show "놀라운 일이"   # 그 어구를 쓴 실제 문장
"""
import argparse
import collections
import io
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = BASE / "out" / "sul_survey"
TDIR = OUT / "transcripts"

# ── 마스킹 — 소재가 바뀌어도 같은 뼈대로 보이게 ──────────────────────────
_NUM = re.compile(r"\d[\d,\.]*")
# 조사를 떼어 어간만 남긴다(소재어 판정용)
_JOSA_TAIL = ("으로", "에서", "에게", "한테", "라고", "이라고", "까지", "부터",
              "이나", "나", "은", "는", "이", "가", "을", "를", "에", "의", "도", "와", "과", "로")


def _stem(w):
    for j in sorted(_JOSA_TAIL, key=len, reverse=True):
        if w.endswith(j) and len(w) - len(j) >= 1:
            return w[:-len(j)]
    return w


# ★기능어 = 어느 소재에나 나오는 말. 이것들이 뼈대를 이룬다.
#   여기 없는 명사는 '소재'로 보고 마스킹한다 — 그래야 "선풍기에"와 "세탁기에"가 같아진다.
_FUNC = set("""
그런데 근데 그리고 그래서 하지만 그냥 진짜 정말 완전 이거 그거 저거 이게 그게 이건 그건
여러분 사실 심지어 특히 바로 결국 이제 아직 이미 벌써 다시 한번 조금 많이 너무 아주
있는 없는 있다 없다 있어요 없어요 하면 하고 해서 했더니 하니까 하는 한다 합니다 해요
보면 보니까 봤더니 보세요 나오는 나와요 되는 되면 됩니다 돼요 같아요 같은 처럼 만큼
때문에 덕분에 대신 말고 보다 위해 통해 대해 관해 이유 방법 정도 경우 때는 때가
안 못 잘 더 덜 또 꼭 좀 다 딱 막 겨우 그냥 역시 오히려 물론 아마 혹시 만약
저는 제가 저도 저희 우리 내가 나도 당신 그분 사람 분들 분이 사람들
놀라운 대박 미친 신박한 충격 소름 실화 레전드 갓 꿀 필수 강추 인생
절대 무조건 반드시 제발 진심 솔직히 확실히 분명히
""".split())

_STOP_SHORT = {"이", "그", "저", "것", "수", "때", "등", "및", "좀", "잘", "안", "더"}


def mask(text):
    """소재를 ⬛로 가려 **뼈대만** 남긴 어절 리스트."""
    text = _NUM.sub("⬛", text)
    out = []
    for w in text.split():
        w = re.sub(r"[^\w가-힣⬛]", "", w)
        if not w:
            continue
        if w in _FUNC or _stem(w) in _FUNC:
            out.append(w)
        elif "⬛" in w:
            out.append("⬛")
        elif re.fullmatch(r"[가-힣]+", w) and len(_stem(w)) >= 2:
            # 소재어 후보 — 조사는 살려서 문형을 유지한다("⬛에", "⬛를")
            st = _stem(w)
            tail = w[len(st):]
            out.append("⬛" + tail)
        else:
            out.append(w)
    return out


def load():
    rows = []
    for f in TDIR.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("ok") and (d.get("text") or "").strip():
            rows.append(d)
    return rows


def mine(rows, lo=3, hi=9, min_ch=3, top=50):
    """n-gram → {어구: (편수, 채널수, 중앙조회수)}. ★채널수로 거른다."""
    seen_ch = collections.defaultdict(set)      # 어구 → 채널 집합
    seen_v = collections.defaultdict(list)      # 어구 → 영상들
    for d in rows:
        ws = mask(d["text"])
        got = set()
        for n in range(lo, hi + 1):
            for i in range(len(ws) - n + 1):
                g = " ".join(ws[i:i + n])
                if g.count("⬛") > n * 0.6:      # 소재만 늘어선 조각은 버린다
                    continue
                got.add(g)
        for g in got:
            seen_ch[g].add(d["channel"])
            seen_v[g].append(d)

    rank = []
    for g, chs in seen_ch.items():
        if len(chs) < min_ch:
            continue
        vs = seen_v[g]
        med = sorted(v["views"] for v in vs)[len(vs) // 2]
        rank.append((g, len(vs), len(chs), med))
    # 채널 수 우선, 그다음 편수 — **퍼진 것**이 진짜 장르 문법이다
    rank.sort(key=lambda r: (-r[2], -r[1]))
    return rank[:top]


def main(min_ch, top, show, lo, hi):
    rows = load()
    if not rows:
        print("전사가 없다 — transcribe_hits.py --transcribe 부터")
        return
    chs = len({d["channel"] for d in rows})
    print("전사 %d편 / %d채널 분석 (n-gram %d~%d어절, 채널 %d개 이상)\n"
          % (len(rows), chs, lo, hi, min_ch))

    if show:
        print("[%s] 를 쓴 실제 문장" % show)
        n = 0
        for d in rows:
            if show in d["text"]:
                idx = d["text"].find(show)
                seg = d["text"][max(0, idx - 30):idx + 60]
                print("  %8d %-12s …%s…" % (d["views"], d["channel"][:10], seg))
                n += 1
                if n >= 25:
                    break
        print("\n총 %d편에서 발견" % n)
        return

    rank = mine(rows, lo, hi, min_ch, top)
    print("%-52s %4s %4s %10s" % ("고정 어구(뼈대)", "편", "채널", "중앙조회"))
    print("-" * 76)
    for g, nv, nc, med in rank:
        print("%-52s %4d %4d %10s" % (g[:50], nv, nc, format(med, ",")))
    print("\n★채널 수가 많을수록 장르 문법. 한 채널에 몰리면 그 채널 습관이다.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-ch", type=int, default=3)
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--show", default="")
    ap.add_argument("--lo", type=int, default=3)
    ap.add_argument("--hi", type=int, default=9)
    a = ap.parse_args()
    main(a.min_ch, a.top, a.show, a.lo, a.hi)
