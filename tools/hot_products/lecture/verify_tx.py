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
        print(vid, c["_check"])
    print("인용 확인", tot[0], "버림", tot[1])
