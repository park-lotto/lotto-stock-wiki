"""첫 줄 검사(버텍스 없음) — 이미 뽑힌 out/*.json 첫 줄만 본다(2026-10-20).
사장님 지적: B(새 설명서) 첫 줄이 A의 '…하다 답답했던 천재가 만들어 떼돈 번 ○○의 정체' 꼴을 잃었다.
① 틀 뼈대 유지: 첫 줄이 그 카드 「제목 틀 사전」 중 하나의 고정 낱말({슬롯} 밖 글자)을 70% 이상 담았나
② 스타일끼리 같은 구절: 같은 소재에서 서로 다른 스타일 3곳 이상 첫 줄에 나온 공백 뺀 6자+ 구절(설명서 예문이 퍼진 흔적)
③ 근거 없는 나라
⑤ 템플릿에 담기나: 라이브 split_hook(11자+10자)으로 잘라 낱말이 하나도 안 버려지나(버려지면 라이브가 대본 제목 대신 AI 후보를 넣는다)
④ 불편 원인 앞(발명품·정체·해답·활용법 계열): 첫 줄 앞 2/3 안에 불편 낱말이 있나 — 사장님 10-20 '사생활 침해로 빡쳤던 사람들 구원한' O / '자취생 구원한' X
사용: py first_line_check.py --side B2 [--cards ../cards_v2]   (A 는 --side A, 카드는 같은 이름 카드의 틀로 잰다)"""
import argparse, glob, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
from shopping_shorts.template_copy import split_hook  # noqa: E402  라이브 템플릿 제목 자르기(11+10)
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CARD_OF = {"jungche": "정체숨김", "oyong": "오용활용법", "even": "이븐쇼핑", "hdn": "두유노홈디노",
           "55": "정체숨김", "65": "정체숨김", "74": "정체숨김", "75": "정체숨김", "76": "정체숨김",
           "56": "오용활용법", "70": "오용활용법", "71": "오용활용법", "72": "오용활용법", "73": "오용활용법"}
SUBJ_RE = re.compile(r"(\S+)\s*(천재|개발자|주부|학생|사장님|엄마|아빠|대학생|약사)")
MOD_BAD = {"한", "그", "이", "만든", "번", "온", "던", "의"}
PAIN_FAMILY = {"jungche", "even", "60", "66", "oyong", "55", "65", "74", "75", "76", "56", "70", "71", "72", "73"}
PAIN_RE = re.compile(r"답답|빡|짜증|귀찮|불편|싫|고생|현타|스트레스|지옥|노이로제|조마조마|샘|들뜸|엿보|끈적|시선|새는|기포|자국|보일까|사생활 없|훤히|서러|침해|노출|새서|새던|들뜨|흘러|번지|엉켜|풀려|안 붙|못 |하다가?\s|때문에|하다 |씌우다|포장하다|덮다|붙이다")
NATIONS = ["일본", "미국", "독일", "중국", "한국", "프랑스", "영국", "해외"]


def ns(t):
    return re.sub(r"[\s.,!?~…'\"]", "", t or "")


def fixed_parts(mold):
    """틀에서 {슬롯}과 설명 괄호를 뺀 고정 낱말 조각."""
    m = re.split(r"\s[—←(]", mold)[0]
    return [p for p in (ns(x) for x in re.split(r"\{[^}]*\}", m)) if len(p) >= 2]


def mold_score(line, molds):
    t, best, which = ns(line), 0.0, ""
    for mo in molds:
        parts = fixed_parts(mo.get("mold", ""))
        total = sum(len(p) for p in parts)
        if not total:
            continue
        hit = sum(len(p) for p in parts if p in t)
        if hit / total > best:
            best, which = hit / total, mo.get("no", "")
    return best, which


def card_for(cid, cards_dir):
    name = CARD_OF.get(str(cid))
    pat = name if name else "%s_" % cid
    fs = sorted(glob.glob(os.path.join(cards_dir, pat + "*.json")))
    return json.load(open(fs[0], encoding="utf-8")) if fs else {}


def firsts(d):
    out = []
    for dd in d.get("drafts") or []:
        if isinstance(dd, dict) and dd.get("lines"):
            l0 = dd["lines"][0]
            out.append(l0.get("text") if isinstance(l0, dict) else str(l0))
    if not out and isinstance(d.get("lines"), list) and d["lines"]:
        l0 = d["lines"][0]
        out.append(l0.get("text") if isinstance(l0, dict) else str(l0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", default="B2")
    ap.add_argument("--cards", default=os.path.join(HERE, "..", "cards_v2"))
    ap.add_argument("--th", type=float, default=0.7)
    a = ap.parse_args()
    rows, by_src = [], defaultdict(list)
    for f in sorted(glob.glob(os.path.join(OUT, "%s_*_*.json" % a.side))):
        _, cid, src = os.path.basename(f)[:-5].split("_", 2)
        if src.endswith("engine"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        ev = json.dumps(json.load(open(os.path.join(HERE, "inputs", src + ".json"), encoding="utf-8")), ensure_ascii=False) \
            if os.path.exists(os.path.join(HERE, "inputs", src + ".json")) else ""
        molds = card_for(cid, a.cards).get("title_molds") or []
        for i, line in enumerate(firsts(d)):
            sc, no = mold_score(line, molds)
            rows.append(dict(id=cid, src=src, i=i, line=line, mold=no, score=round(sc, 2), keep=sc >= a.th,
                             nations=[n for n in NATIONS if n in line and n not in ev],
                             modifier=(lambda m: bool(m) and not any(m.group(1).endswith(x) for x in ("던", "온", "친", "한", "된")) and m.group(1) not in MOD_BAD)(SUBJ_RE.search(line)) if str(cid) in PAIN_FAMILY else None,
                             fits=len(" ".join(split_hook(line)).split()) == len(line.split()), chars=len(line.strip()),
                             pain=(None if str(cid) not in PAIN_FAMILY else bool(PAIN_RE.search(line[:max(8, len(line) * 2 // 3)])))))
            by_src[src].append((cid, ns(line)))
    spread = {}
    for src, items in by_src.items():
        seen = defaultdict(set)
        for cid, t in items:
            for k in range(6, 13):
                for j in range(len(t) - k + 1):
                    seen[t[j:j + k]].add(CARD_OF.get(cid, cid))
        frags = sorted((g for g, s in seen.items() if len(s) >= 3), key=len, reverse=True)
        keep = []
        for g in frags:
            if not any(g in k for k in keep):
                keep.append(g)
        spread[src] = {g: sorted(seen[g]) for g in keep}
    n = len(rows)
    fam = [r for r in rows if r["pain"] is not None]
    print("[%s] 템플릿 담김 %d/%d · 주체 꾸밈말 %d/%d" % (a.side, sum(r["fits"] for r in rows), len(rows), sum(bool(r.get("modifier")) for r in rows), sum(r.get("modifier") is not None for r in rows)))
    print("[%s] 첫 줄 %d개 · 틀 뼈대 유지 %d · 근거 없는 나라 %d · 불편 원인 앞 %d/%d(발명품 계열)" % (a.side, n, sum(r["keep"] for r in rows), sum(bool(r["nations"]) for r in rows), sum(r["pain"] for r in fam), len(fam)))
    for r in rows:
        flag = ("" if r["keep"] else " ✗틀") + (" ✗꾸밈말" if r.get("modifier") is False else "") + ("" if r["fits"] else " ✗템플릿 안 담김(%d자)" % r["chars"]) + (" ✗원인없음" if r["pain"] is False else "") + (" ✗나라:" + ",".join(r["nations"]) if r["nations"] else "")
        print("  %-8s %-10s %d %.2f%-4s %s%s" % (r["id"], r["src"], r["i"], r["score"], r["mold"], r["line"], flag))
    for src, sp in spread.items():
        print("[%s] 스타일 3곳+ 첫 줄에 같은 구절: %s" % (src, "; ".join("%s(%d)" % (g, len(s)) for g, s in sp.items()) or "없음"))
    json.dump({"rows": rows, "spread": spread}, open(os.path.join(HERE, "first_line_%s.json" % a.side), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
