"""이븐쇼핑 22편 → 칸별 부품 사전 (2026-09-21 사장님 확정).

사장님: "oo천재 발명 / 천재oo활용 / 개발자 / 떼돈 이런거 다 활용할수있자나
        => 여기에 붙는 내용들 하나씩 끼워주고"

★왜 이 방식인가(실측 근거):
  이븐쇼핑 22편은 유형 라벨이 4가지(발명품형15·제품정체형3·오용형3·다이소1)인데
  **문장 구조는 하나**다 — `천재` 22/22(100%) · `최근` 21/22(95%) ·
  `말도 안 되는` 21/22(95%) · `이건 바로` 17/22(77%).
  즉 유형은 껍데기이고 훅 **끝말**만 바뀐다:
    …천재의 발명품 / …때돈 제품의 정체 / …천재 주부의 활용법
  → 틀 하나 + 칸별 부품을 순번으로 돌리면 조합이 수백만 가지가 된다.
  (원문 한 편을 통째로 베끼면 남의 제품 이야기가 그대로 나온다 — 그래서 부품으로 쪼갠다)

쓰기(서버):
  python3 tools/spine_presets/even_parts.py /tmp/hits_cls_all.json /tmp/even_parts.json
"""
import json
import re
import sys
import collections

SPLIT = re.compile(r"(?<=[.!?])\s+")

# ★마침표로만 자르면 안 된다 (2026-09-21 실측): 유튜브 자동자막은 마침표를 거의 안 찍어
#   한 문장이 102~168자로 뭉친다(83문장 중 17개가 120자 초과). 그래서 `이건 바로`가
#   앞 칸(bait)에 먹혀 reveal이 0개로 나왔다. **칸 경계 표지 앞에서도 자른다.**
_CUTS = re.compile(r"(?=(?:이건 바로|이게 바로|이게 말도 안 되는게|이 말도 안 되는게|"
                   r"근데 진짜 (?:충격|미친)|심지어|원래는|최근))")


def phrases(text):
    """문장 → 칸 단위 구절. 마침표와 칸 표지 양쪽으로 자른다."""
    out = []
    for s in SPLIT.split(text or ""):
        for p in _CUTS.split(s):
            p = p.strip(" .")
            if len(p) >= 6:
                out.append(p)
    return out

# 칸 판정 — 앞 칸부터 본다(겹치면 먼저 맞는 칸으로)
SLOTS = [
    ("title",  r"천재의 발명품|제품의 정체|천재 주부의 활용법|돈 ?방석 앉은 제품"),
    ("bait",   r"최근|딱 봤을 때|평범한|도저히 (용도|어디)"),
    ("fame",   r"때돈|떼돈|돈 ?방석|품절|매달 \d|수천만|바이럴|바이러럴|논란"),
    ("reveal", r"이건 바로|이게 바로"),
    ("limit",  r"말도 안 ?되|원래는"),
    ("twist",  r"진짜 (충격|미친)|근데 진짜|심지어"),
    ("land",   r"이러니|난리|끝났|더 이상"),
]

# 훅 머리 축 — 사장님이 지목한 네 가지
AXES = [
    ("천재발명", r"천재의 발명품"),
    ("천재활용", r"천재 주부의 활용법"),
    ("떼돈",     r"때돈|떼돈|돈 ?방석"),
    ("정체",     r"제품의 정체"),
    ("개발자",   r"개발자|제조사|본사"),
]


def slot_of(s):
    for name, pat in SLOTS:
        if re.search(pat, s):
            return name
    return ""


def axes_of(hook):
    return [n for n, p in AXES if re.search(p, hook)] or ["기타"]


def main():
    src, dst = sys.argv[1], sys.argv[2]
    rows = [r for r in json.load(open(src, encoding="utf-8"))
            if "이븐" in (r.get("user") or "")]
    parts = collections.defaultdict(list)
    hooks = []
    for r in rows:
        sents = phrases(r.get("text") or "")
        if not sents:
            continue
        hooks.append({"text": sents[0], "axes": axes_of(sents[0]),
                      "views": r.get("views") or 0, "id": r.get("id")})
        for s in sents:
            k = slot_of(s)
            if k and s not in parts[k]:
                parts[k].append(s)
    out = {"source": "이븐쇼핑", "n_videos": len(rows),
           "hooks": sorted(hooks, key=lambda h: -h["views"]),
           "parts": dict(parts)}
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("영상 %d편 · 훅 %d개" % (len(rows), len(hooks)))
    for k, v in parts.items():
        print("  %-8s %3d개" % (k, len(v)))
    n = 1
    for k in ("title", "bait", "fame", "reveal", "limit", "twist"):
        n *= max(1, len(parts.get(k) or []))
    print("조합(대략): %s가지" % format(n, ","))
    print("축별 훅:", dict(collections.Counter(a for h in hooks for a in h["axes"])))


if __name__ == "__main__":
    main()
