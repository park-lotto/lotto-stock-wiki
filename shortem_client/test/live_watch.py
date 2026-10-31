"""라이브 시험 감시 — 결과 파일만 기다리지 않고 이상 신호가 뜨는 즉시 끝나 알린다(사장님 10-31 "문제가 조금이라도 되면 감시를 두라").
쓰기: py shortem_client/test/live_watch.py C:/t/live_gadget [--seen 파일]  · 신호가 나면 한 줄씩 찍고 종료(이미 알린 신호는 --seen 에 남겨 다시 안 낸다)."""
import collections
import glob
import json
import os
import re
import sys
import time

SLOW_MIN = 60      # 한 편 시작 뒤 이 분을 넘으면 알림(실측 1편 35분)
QUIET_MIN = 10     # 작업 기록이 이 분 동안 안 늘면 멈춘 것으로 본다
REPEAT = 2         # 같은 × 검사가 이 번 나오면 알림


def signals(d: str) -> list[str]:
    out = []
    rs = glob.glob(os.path.join(d, "home", "창고", "flow", "*", "runner.log"))
    if not rs:
        return out
    log = open(rs[0], encoding="utf-8", errors="replace").read()
    for m in re.findall(r"^\[runner\] (\S+) [\d.]+s ERR (.{0,60})", log, re.M):
        out.append(f"실행오류 {m[0]}: {m[1]}")
    fails = collections.Counter(re.sub(r"\(.*", "", x).strip() for x in re.findall(r"^\s*× (.+)$", log, re.M))
    out += [f"같은 불합격 {n}번: {k}" for k, n in fails.items() if n >= REPEAT]
    fl = os.path.join(os.path.dirname(rs[0]), "flow.json")
    try:
        s = json.load(open(fl, encoding="utf-8"))
        age = (time.time() * 1000 - s.get("created", 0)) / 60000
        for n in range(1, int(age // SLOW_MIN) + 1):
            out.append(f"{n * SLOW_MIN}분 넘김 · 지금 {(s.get('stage') or {}).get('text')}")
        if s.get("fail"):
            out.append(f"멈춤: {str(s['fail'])[:100]}")
    except (OSError, ValueError):
        pass
    return out


def main():
    d = sys.argv[1]
    sf = sys.argv[sys.argv.index("--seen") + 1] if "--seen" in sys.argv else d + "_watch_seen.json"
    try:
        seen = set(json.load(open(sf, encoding="utf-8")))
    except (OSError, ValueError):
        seen = set()
    res = d + "_result.json"
    jl = os.path.join(d, "claude.jsonl")
    while True:
        new = [x for x in signals(d) if x not in seen]
        if os.path.exists(jl) and time.time() - os.path.getmtime(jl) > QUIET_MIN * 60 and not (os.path.exists(res) and os.path.getsize(res)):
            new.append(f"{QUIET_MIN}분째 움직임 없음 {time.strftime('%H:%M')}")
        if os.path.exists(res) and os.path.getsize(res):
            new.append("끝남")
        if new:
            json.dump(sorted(seen | set(new)), open(sf, "w", encoding="utf-8"), ensure_ascii=False)
            print(os.path.basename(d), *new, sep="\n  ", flush=True)
            return
        time.sleep(30)


if __name__ == "__main__":
    main()
