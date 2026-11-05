# -*- coding: utf-8 -*-
"""버퍼 매일 예약(사장님 2026-10-29 "매일 규칙적으로 / 1시에 쿠팡 작업 시작 / 3시반·7시반 / 랜덤 배정").
매일 13:00 작업 스케줄러 '숏템_버퍼_매일예약' 이 `run` 을 부른다.

    py tools/buffer_daily.py plan            # 오늘 빈 칸·준비할 영상(무작위)을 JSON 으로 — 아무것도 안 바꾼다
    py tools/buffer_daily.py run [--dry]     # plan → 헤드리스 클로드가 준비(장면·제목·쿠팡·인포크·.txt) → post → 점검

판단 나눔: 빈 칸·무작위 선택 = 여기(코드) / 제품 알아보기·글·상품 고르기 = 클로드(tools/buffer_daily_prompt.md)
칸·중복·인포크 관문은 전부 buffer_post 가 다시 지킨다(클로드가 틀려도 그 관문을 못 넘는다).
"""
import argparse
import datetime as dt
import json
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools import buffer_post as bp  # noqa: E402

# 매일 돌리는 계정 — 인포크 계정이 정해진 채널만(bp._inpock_acct). 나머지 _2 채널은 인포크가 정해지면 넣는다
# 995_2 얜샷템: 인포크 ystem · 유튜브 프로필 링크 link.inpock.co.kr/ystem (10-29 걸고 정보 창에서 실측)
ACCOUNTS = ["21(수창) 쓸데수집", "950 숏템리폿", "987_1 샥템스토리", "994_1 썰템홈샷", "995_1 썰템쇼", "995_2 얜샷템",
            "998_1 꿀템샷", "999_1 잇썸홈"]
SHOPLINK_DIR = os.path.join(ROOT, ".tracks", "쇼핑링크자동") if os.path.isdir(os.path.join(ROOT, ".tracks", "쇼핑링크자동")) \
    else os.path.join(os.path.dirname(os.path.dirname(ROOT)), "쇼핑링크자동")   # 트랙 폴더에서 돌 때(.tracks/버퍼예약드라이브)
LOG_DIR = os.path.expanduser(r"~\.claude\buffer_daily")
PROMPT = os.path.join(ROOT, "tools", "buffer_daily_prompt.md")


def _kst(u):
    return dt.datetime.strptime(u[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc).astimezone(bp.KST).strftime("%H:%M")


def plan(now=None):
    """계정마다 오늘 남은 칸 수 · 이미 준비된 영상(.txt 있음) · 새로 준비할 영상(무작위)."""
    now = now or dt.datetime.now(bp.KST)
    rows = bp._load(bp.LEDGER, [])
    out = []
    for f in ACCOUNTS:
        d = os.path.join(bp.DRIVE, f)
        if not os.path.isdir(d):
            out.append({"folder": f, "skip": "드라이브 폴더 없음"})
            continue
        today = [u for u in bp._slot_dues(rows, f, 2, now)
                 if dt.datetime.strptime(u[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc).astimezone(bp.KST).date() == now.date()]
        vs = bp._videos(d)
        ready = [v for v in vs if bp._caption(d, v)[0]]
        raw = [v for v in vs if v not in ready]
        need = max(0, len(today) - len(ready))
        out.append({"folder": f, "inpock": bp._inpock_acct(f), "free_slots_today": [_kst(u) for u in today], "ready": ready,
                    "prepare": random.sample(raw, min(need, len(raw))), "left_after": len(raw) - min(need, len(raw))})
    return out


def _log(msg):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR, "run.log"), "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now(bp.KST):%Y-%m-%d %H:%M:%S} {msg}\n")


def run(dry=False):
    p = plan()
    _log("plan " + json.dumps(p, ensure_ascii=False))
    if not any(x.get("free_slots_today") for x in p):
        _log("오늘 빈 칸 없음 — 끝")
        print("오늘 빈 칸 없음")
        return 0
    day = dt.datetime.now(bp.KST).strftime("%Y-%m-%d")
    report = os.path.join(LOG_DIR, f"{day}.md")
    prompt = open(PROMPT, encoding="utf-8").read().format(
        plan=json.dumps(p, ensure_ascii=False, indent=1), root=ROOT, shoplink=SHOPLINK_DIR, report=report,
        drive=bp.DRIVE)
    if dry:
        print(prompt)
        return 0
    cmd = ["claude", "-p", prompt, "--allowedTools", "Bash Read Write Edit Glob Grep",
           "--add-dir", SHOPLINK_DIR, "--add-dir", bp.DRIVE, "--add-dir", LOG_DIR,
           "--output-format", "stream-json", "--verbose"]
    # 11-03 사고: claude 가 첫 단계도 안 하고 2시간 멈춤 → 시간초과로 출력까지 버려져 원인을 못 봤고, 그날 예약 0건.
    # 그래서 ① 출력을 줄마다 <날짜>.out.log 에 바로 남기고 ② STALL 동안 한 줄도 안 나오면 끊고
    # ③ 오늘 예약이 0건이면 한 번 더 돈다(칸·중복은 buffer_post 관문이 다시 지킨다).
    rc = 1
    for attempt in (1, 2):
        rc = _run_claude(cmd, os.path.join(LOG_DIR, f"{day}.out.log"), attempt)
        n = _today_rows(day)
        _log(f"시도 {attempt} 끝 rc={rc} · 오늘 예약 행 {n}")
        if n or dt.datetime.now(bp.KST).hour >= 19:
            break
    if not _today_rows(day):
        _log("★오늘 예약 0건 — 사람이 봐야 한다")
    return rc


STALL = 20 * 60        # 이 시간 동안 출력이 한 줄도 없으면 멈춘 것으로 본다
LIMIT = 100 * 60       # 한 번 시도의 최대 시간


def _run_claude(cmd, out_path, attempt):
    import threading
    import time
    _log(f"claude 시작(시도 {attempt}) → {out_path}")
    last = [time.time()]
    with open(out_path, "a", encoding="utf-8") as out:
        out.write(f"\n===== {dt.datetime.now(bp.KST):%H:%M:%S} 시도 {attempt}\n")
        out.flush()
        # ★11-03·04 멈춤의 뿌리(실측): ~/.claude 에 켜진 숏템 회원 플러그인의 SessionStart 훅 wake.js 가
        #   팀 메시지를 6시간 기다리는데(asyncRewake), 헤드리스 -p 는 그 훅이 끝나길 기다려 아무것도 안 한다.
        #   이 실행에서만 대기 시간을 0 으로 — wake.js 가 첫 확인에서 바로 끝난다(회원 플러그인 자체는 그대로).
        env = dict(os.environ, SHORTEM_WAKE_LIFE_MS="0")
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             text=True, encoding="utf-8", errors="replace", env=env)

        def pump():
            for line in p.stdout:
                out.write(line)
                out.flush()
                last[0] = time.time()
        th = threading.Thread(target=pump, daemon=True)
        th.start()
        t0 = time.time()
        why = ""
        while p.poll() is None:
            time.sleep(5)
            if time.time() - last[0] > STALL:
                why = f"{STALL // 60}분 동안 출력 없음"
            elif time.time() - t0 > LIMIT:
                why = f"{LIMIT // 60}분 넘음"
            if why:
                _log(f"claude 끊음(시도 {attempt}): {why}")
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
                break
        th.join(timeout=10)
        return p.wait() if not why else 124


def _today_rows(day):
    """장부에서 오늘(KST) 게시 예정인 행 수 — '오늘 예약이 들어갔나'의 판정은 장부 하나로 한다."""
    n = 0
    for r in bp._load(bp.LEDGER, []):
        u = str(r.get("due") or "")
        if len(u) >= 16 and r.get("final_status") != "deleted":
            d = dt.datetime.strptime(u[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc).astimezone(bp.KST)
            n += d.strftime("%Y-%m-%d") == day
    return n


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    r = sub.add_parser("run")
    r.add_argument("--dry", action="store_true", help="클로드를 부르지 않고 프롬프트만 찍는다")
    a = ap.parse_args()
    if a.cmd == "plan":
        print(json.dumps(plan(), ensure_ascii=False, indent=1))
        return 0
    return run(a.dry)


if __name__ == "__main__":
    sys.exit(main())
