# -*- coding: utf-8 -*-
"""4단계 — 전사를 **스타일로 분류**한다 (2026-09-05).

## 이게 사장님이 지적한 빠진 단계다

    "지금 뭐가 어떤 채널이 어떤 영상이 어떤 대본 스타일이 터지는가"

내 첫 시도는 '채널 3개 → 틀' 이었다. 터진 영상을 **뜯어서 분류하는** 단계가 없어서
"어떤 영상이 어떤 스타일인가"를 대답할 수 없었다. 여기서 그걸 한다.

## 어떻게 분류하나 — ★스타일을 미리 정하지 않는다

내가 축을 먼저 정하고 거기 맞추면 또 헛다리다(1차 시도가 그랬다).
대신 **자막에서 구조 신호를 뽑아** 비슷한 것끼리 뭉친다:

    ① 훅 형태     첫 문장의 모양 (질문 / 금지 / 감탄 / 목격 / 선언 …)
    ② 화자        1인칭('저는·제가') vs 3인칭('~다는데·~라고')
    ③ 권위 출처   직업인 / 지인 / 할머니 / 익명 천재 / 없음
    ④ CTA        댓글유도 / 좋아요·화면 / 없음
    ⑤ 몸통 진행   계량순서 / 원리설명 / 사례나열 / 서사
    ⑥ 말끝        ~어요 / ~습니다 / ~음·~다는거

이 6축의 조합이 **같은 것끼리 뭉치면 그게 스타일**이다. 뭉치는 덩어리에 이름을
붙이는 것이지, 이름을 먼저 짓고 영상을 밀어넣는 게 아니다.

★기존 라이브 12틀과 겹치는 덩어리는 **표시만 하고 새로 만들지 않는다**
  (사장님 지시 2026-09-05: "이미 인스타에 그런 스타일 있는데 억지로 더 만들지마").

## 토큰

집계표만 화면에 낸다. 전사 원문은 파일에만 둔다.

실행:
    py scripts/classify_scripts.py                 # 집계
    py scripts/classify_scripts.py --show 훅질문형   # 그 무리의 실제 문장 보기
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


# ── 6축 신호 ─────────────────────────────────────────────────────────────
def hook_type(first):
    """첫 문장의 모양. 순서가 중요하다 — 위에서부터 먼저 맞는 것."""
    f = first
    if re.search(r"(하지|쓰지|넣지|버리지|두지|사지)\s?마|절대|제발", f):
        return "금지경고"
    if re.search(r"\?|나요|까요|아세요|계신가요|맞죠", f):
        return "질문도입"
    if re.search(r"^(와|아니|으아|헐|대박)[\s,]|진짜\s?(미쳤|충격|신박)", f):
        return "감탄즉시"
    if re.search(r"(놀러|갔다가|집에서|친구|언니|지인|시댁).{0,12}(봤|보고|갔)", f):
        return "목격전달"
    if re.search(r"놀라운\s?일|벌어집니다|생깁니다", f):
        return "결과예고"
    if re.search(r"무조건|꼭|반드시|이렇게\s?하세요", f):
        return "단정명령"
    if re.search(r"만\s?원|아꼈|아낍|굳었", f):
        return "금액절약"
    return "기타"


def speaker(t):
    me = len(re.findall(r"저는|제가|저도|우리\s?집|저희", t))
    it = len(re.findall(r"라는데|다는데|라고\s?합니다|다고\s?합니다|었음|~다는\s?거", t))
    if me > it:
        return "1인칭"
    if it > me:
        return "3인칭"
    return "혼합"


def authority(t):
    if re.search(r"할머니|어르신|평생.{0,8}(해온|해오신)", t):
        return "할머니"
    if re.search(r"(직원|사장님|기사님|전문가|경력|년째|업체|호텔리어|박사|의사)", t):
        return "직업인"
    if re.search(r"(언니|친구|지인|친척|엄마|동생|형)", t):
        return "지인"
    if re.search(r"천재|개발자|제조사|발명", t):
        return "익명천재"
    return "없음"


def cta_type(t):
    tail = t[-90:]
    if re.search(r"남겨\s?주|댓글", tail):
        return "댓글유도"
    if re.search(r"좋아요|눌러\s?주|두\s?번\s?누르", tail):
        return "좋아요·화면"
    if re.search(r"링크|프로필|더보기", tail):
        return "링크안내"
    return "없음"


def body_type(t):
    if re.search(r"먼저.{0,25}(넣|부어|섞)|그다음|한\s?큰\s?술|스푼|ml|컵을", t):
        return "계량순서"
    if re.search(r"성분|때문에.{0,10}(생기|늘어|발생)|원리|효소|균|산화", t):
        return "원리설명"
    if re.search(r"첫\s?번째|두\s?번째|세\s?번째|하는가\s?하면|쓰기도", t):
        return "사례나열"
    return "서사"


def ending(t):
    e = collections.Counter()
    for m in re.finditer(r"(어요|아요|에요|예요|거든요|더라고요|더라구요|습니다|입니다|었음|다는\s?거)", t):
        e[m.group(1).replace(" ", "")] += 1
    if not e:
        return "기타"
    top = e.most_common(1)[0][0]
    if top in ("습니다", "입니다"):
        return "~습니다"
    if top in ("었음",) or top.startswith("다는"):
        return "~음/~다는거"
    return "~어요"


def first_sentence(t):
    m = re.split(r"(?<=[.!?])\s|(?<=요)\s|(?<=다)\s", t.strip())
    return (m[0] if m else t)[:60]


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


def profile(d):
    t = d["text"]
    return {
        "훅": hook_type(first_sentence(t)),
        "화자": speaker(t),
        "권위": authority(t),
        "CTA": cta_type(t),
        "몸통": body_type(t),
        "말끝": ending(t),
    }


def main(show, min_n):
    rows = load()
    if not rows:
        print("전사가 없다 — 먼저 transcribe_hits.py --transcribe")
        return
    print("전사 %d편 분석\n" % len(rows))

    for axis in ("훅", "화자", "권위", "CTA", "몸통", "말끝"):
        c = collections.Counter(profile(d)[axis] for d in rows)
        line = "  ".join("%s %d(%.0f%%)" % (k, v, v / len(rows) * 100)
                         for k, v in c.most_common())
        print("%-4s %s" % (axis, line))

    print("\n" + "=" * 74)
    print("★조합이 뭉치는 덩어리 = 스타일 후보 (%d편 이상)" % min_n)
    print("=" * 74)
    combo = collections.Counter()
    bucket = collections.defaultdict(list)
    for d in rows:
        p = profile(d)
        key = "%s|%s|%s|%s" % (p["훅"], p["화자"], p["권위"], p["몸통"])
        combo[key] += 1
        bucket[key].append(d)
    for key, n in combo.most_common(18):
        if n < min_n:
            continue
        vs = bucket[key]
        med = sorted(v["views"] for v in vs)[len(vs) // 2]
        chans = len({v["channel"] for v in vs})
        print("%-42s %3d편 %2d채널 중앙 %s회"
              % (key, n, chans, format(med, ",")))

    if show:
        print("\n[%s] 실제 첫 문장" % show)
        for d in rows:
            p = profile(d)
            key = "%s|%s|%s|%s" % (p["훅"], p["화자"], p["권위"], p["몸통"])
            if show in key:
                print("  %8d %-12s %s"
                      % (d["views"], d["channel"][:10], first_sentence(d["text"])[:52]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default="")
    ap.add_argument("--min-n", type=int, default=4)
    a = ap.parse_args()
    main(a.show, a.min_n)
