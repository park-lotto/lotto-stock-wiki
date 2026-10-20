"""정독 카드 인용 검사(주인 함수) — 카드의 모든 quote 가 자막 원문에 실제로 있는지 보고, 없는 항목은 버린다.
누가 만든 카드든(제미나이 analyze_tx / Claude 에이전트) 이 검사를 거쳐야 cards_tx 에 남는다.
실행: py -I verify_tx.py  → cards_tx/*.json 전부 다시 검사(_check 갱신)"""
import glob, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from fidelity import norm

def ok(q, t):
    q = norm(q or "")
    return len(q) >= 4 and q in t

def verify(card, transcript):
    t = norm(transcript); kept = dropped = 0
    for m in card.get("methods", []):
        for key in ("thresholds", "examples"):
            good = [x for x in m.get(key) or [] if ok(x.get("quote"), t)]
            dropped += len(m.get(key) or []) - len(good); kept += len(good); m[key] = good
        m["signal_verified"] = ok(m.get("signal_quote"), t)
    pits = card.get("pitfalls", [])
    card["pitfalls"] = [p for p in pits if ok(p.get("quote"), t)]
    dropped += len(pits) - len(card["pitfalls"]); kept += len(card["pitfalls"])
    before = len(card.get("methods", []))
    card["methods"] = [m for m in card.get("methods", []) if m["thresholds"] or m["examples"] or m["signal_verified"]]
    card["insight_verified"] = ok(card.get("insight_quote"), t)
    # 고르게 읽었나: 남은 인용들이 자막을 3등분한 구간 중 몇 곳에서 나왔나(앞부분만 읽으면 1/3). last_sentence 는 스크립트로 뽑을 수 있어 증거로 약하다
    qs = [x.get("quote") for m in card["methods"] for k in ("thresholds", "examples") for x in m[k]] + [p.get("quote") for p in card["pitfalls"]]
    pos = [t.find(norm(q)) / max(1, len(t)) for q in qs if ok(q, t)]
    card["coverage_thirds"] = len({min(2, int(p * 3)) for p in pos})
    last = norm((card.get("read_check") or {}).get("last_sentence") or "")
    card["read_to_end"] = bool(last) and len(last) >= 4 and last[-15:] in t[-400:]   # 맨 끝 문장이 자막 끝 400자 안에 있어야 끝까지 읽은 것
    card["_check"] = {"kept": kept, "dropped": dropped, "methods_dropped": before - len(card["methods"]), "subs_chars": len(transcript)}
    return card

if __name__ == "__main__":
    tot = [0, 0]
    for f in sorted(glob.glob(os.path.join(HERE, "cards_tx", "*.json"))):
        c = json.load(open(f, encoding="utf-8")); vid = os.path.basename(f)[:-5]
        sp = os.path.join(HERE, "subs", vid + ".txt")
        if not os.path.exists(sp): print("자막 없음", vid); continue
        c = verify(c, open(sp, encoding="utf-8").read())
        json.dump(c, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        tot[0] += c["_check"]["kept"]; tot[1] += c["_check"]["dropped"]
        print(vid, c["_check"], "끝까지" if c["read_to_end"] else "★끝 문장 불일치", f"인용 분포 {c['coverage_thirds']}/3")
    print("인용 확인", tot[0], "버림", tot[1])
