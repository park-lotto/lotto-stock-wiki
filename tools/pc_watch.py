# -*- coding: utf-8 -*-
"""PC 메모리 실시간 점검·정리기(관제 214, 2026-10-15 사장님 "정리할 수 있는 프로그램 / 매번 확인할 수 없으니 실시간으로").

    py tools/pc_watch.py              # 지금 상태 표(세션·도구 서버·관문 일꾼·크롬·남은 메모리) + 정리 후보
    py tools/pc_watch.py clean        # 안전한 것만 정리(주인 없는 프로세스·세션 파일 없는 유령 Claude)
    py tools/pc_watch.py tick         # 예약 작업이 5분마다 부른다: clean + 남은 메모리 모자라면 알림
    py tools/pc_watch.py schedule     # 윈도 작업 스케줄러에 5분마다 tick 등록(창 없이)

★자동으로 끄는 것(안전): ① 부모 프로세스가 사라진 node·python·npx(관문 시험 일꾼·도구 서버 찌꺼기)
  ② 세션 파일(~/.claude/sessions/<pid>.json)이 없고 하루 넘은 claude.exe(창이 닫혔는데 남은 유령 — 10-15 실측 2개 540MB).
★자동으로 안 끄는 것: 살아 있는 Claude 세션(작업이 날아간다) — 오래 쉬는 창은 알림에 이름으로만 보여 준다.
판단은 scan() 한 곳 — 표·정리·알림이 같은 목록을 본다.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
SESS = HOME / ".claude" / "sessions"
LOG = HOME / ".claude" / "pc_watch.log"
LOW_MB = 3000                 # 이 아래면 알림
IDLE_MIN = 120                # 이보다 오래 쉬는 세션은 '닫아도 될 후보'로 알린다
GHOST_HOURS = 24              # 세션 파일 없는 claude 가 이보다 오래면 유령
NOTIFY_GAP = 30 * 60          # 같은 알림은 30분에 한 번


def _ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=0x08000000 if os.name == "nt" else 0)
    return r.stdout


def processes():
    """[{pid, ppid, name, cmd, mb, start(epoch)}] — WMI 한 번."""
    out = _ps("[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-CimInstance Win32_Process | "
              "Select-Object ProcessId,ParentProcessId,Name,CommandLine,WorkingSetSize,"
              "@{n='t';e={[int64](($_.CreationDate.ToUniversalTime())-[datetime]'1970-01-01').TotalSeconds}} | ConvertTo-Json -Compress")
    rows = json.loads(out or "[]")
    return [{"pid": r["ProcessId"], "ppid": r["ParentProcessId"], "name": (r["Name"] or "").lower(),
             "cmd": r.get("CommandLine") or "", "mb": (r.get("WorkingSetSize") or 0) / 1048576, "start": r.get("t") or 0}
            for r in rows]


def free_mb():
    out = _ps("(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory")
    try:
        return int(out.strip()) / 1024
    except ValueError:
        return -1


def _sessions():
    out = {}
    for f in SESS.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out[int(d["pid"])] = d
        except Exception:      # noqa: BLE001 — 깨진 세션 파일은 건너뛴다
            pass
    return out


def _kind(p):
    c = p["cmd"]
    if p["name"] == "claude.exe":
        return "claude"
    if p["name"] == "node.exe":
        for k in ("agentmemory", "firecrawl", "after-effects", "browsermcp", "playwright"):
            if k in c:
                return "도구서버:" + k
        return "node"
    if p["name"] in ("python.exe", "pythonw.exe"):
        if "exec(eval(sys.stdin.readline()))" in c:
            return "관문 시험 일꾼"
        if "pytest" in c:
            return "관문 시험"
        if "track.py" in c or "import subprocess,sys;o=open(" in c:
            return "finish"
        return "python"
    if p["name"] == "chrome.exe":
        return "크롬"
    return ""


def scan(procs=None, sessions=None, now=None):
    """판단 한 곳 → {groups:{종류:[...]}, kill:[(proc, 이유)], idle:[세션], free_mb}."""
    procs = procs if procs is not None else processes()
    sessions = sessions if sessions is not None else _sessions()
    now = now or time.time()
    by = {p["pid"]: p for p in procs}
    groups, kill, idle = {}, [], []
    me = os.getpid()
    for p in procs:
        k = _kind(p)
        if not k:
            continue
        groups.setdefault(k, []).append(p)
        if p["pid"] == me:
            continue
        # ① 주인(부모)이 사라진 node·python — 도구 서버 찌꺼기·끝난 관문의 일꾼
        # ★finish 실행기는 **일부러** 부모 없이 돈다(분리 실행, 카드 081) — 절대 끄지 않는다(10-15 첫 시험에서 걸러냄)
        if p["name"] in ("node.exe", "python.exe") and k not in ("python", "finish") and p["ppid"] not in by:
            kill.append((p, "부모 프로세스 없음(%s)" % k))
        # ② 세션 파일 없는 claude(유령). 데스크톱 앱(부모 claude.exe·sihost)은 건너뛴다
        if k == "claude":
            par = by.get(p["ppid"]) or {}
            if par.get("name") in ("claude.exe", "sihost.exe"):
                continue
            s = sessions.get(p["pid"])
            if s is None and now - p["start"] > GHOST_HOURS * 3600:
                kill.append((p, "세션 파일 없음 · %.0f시간 전 시작(창 닫힌 유령)" % ((now - p["start"]) / 3600)))
            elif s is not None and s.get("status") == "idle":
                mins = (now * 1000 - (s.get("updatedAt") or 0)) / 60000
                if mins >= IDLE_MIN:
                    idle.append({"pid": p["pid"], "name": s.get("name") or "", "mins": mins, "mb": p["mb"]})
    return {"groups": groups, "kill": kill, "idle": sorted(idle, key=lambda x: -x["mins"]),
            "free_mb": free_mb() if procs is not None else -1}


def _kill(pid):
    subprocess.run(["powershell", "-NoProfile", "-Command", "Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % pid],
                   capture_output=True, creationflags=0x08000000 if os.name == "nt" else 0)


def clean(res, printer=print):
    freed = 0
    for p, why in res["kill"]:
        _kill(p["pid"])
        freed += p["mb"]
        printer("정리 %6d %-10s %5.0fMB — %s" % (p["pid"], p["name"], p["mb"], why))
    return freed


def report(res, printer=print):
    printer("남은 메모리 %.1fGB" % (res["free_mb"] / 1024))
    for k, ps in sorted(res["groups"].items(), key=lambda kv: -sum(p["mb"] for p in kv[1])):
        printer("  %-22s %3d개 %6.0fMB" % (k, len(ps), sum(p["mb"] for p in ps)))
    if res["kill"]:
        printer("자동 정리 대상 %d개(clean 으로 정리)" % len(res["kill"]))
    for s in res["idle"]:
        printer("  쉬는 창 %3.0f시간 · %s (pid %d, %.0fMB) — 안 쓰면 그 창에서 /exit" % (s["mins"] / 60, s["name"][:30], s["pid"], s["mb"]))


def _log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%m-%d %H:%M ") + msg + "\n")
    except OSError:
        pass


def _notify(title, body):
    """윈도 알림(토스트). 같은 알림은 NOTIFY_GAP 에 한 번."""
    stamp = HOME / ".claude" / "pc_watch.notified"
    try:
        if stamp.exists() and time.time() - stamp.stat().st_mtime < NOTIFY_GAP:
            return
        stamp.write_text(title, encoding="utf-8")
    except OSError:
        pass
    t = title.replace("'", "''")
    b = body.replace("'", "''")
    _ps("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        "$x=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        "$n=$x.GetElementsByTagName('text'); $n.Item(0).AppendChild($x.CreateTextNode('%s'))>$null; $n.Item(1).AppendChild($x.CreateTextNode('%s'))>$null;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('PC 점검기').Show([Windows.UI.Notifications.ToastNotification]::new($x))" % (t, b))


def tick():
    res = scan()
    lines = []
    freed = clean(res, printer=lines.append)
    for l in lines:
        _log(l)
    free = free_mb()
    _log("남은 %.1fGB · 정리 %.0fMB · 쉬는 창 %d" % (free / 1024, freed, len(res["idle"])))
    if 0 <= free < LOW_MB:
        names = ", ".join("%s(%.0f시간)" % (s["name"][:14], s["mins"] / 60) for s in res["idle"][:3]) or "쉬는 창 없음"
        _notify("메모리 %.1fGB 남음" % (free / 1024), "닫아도 될 창: " + names)


def schedule():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import win_schedule
    repo = Path(__file__).resolve().parents[1]
    return win_schedule.register("숏템_PC점검기", ["/SC", "MINUTE", "/MO", "5"], repo,
                                 ["tools\\pc_watch.py", "tick"], HOME / ".claude" / "pc_watch_sched.log")


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:      # noqa: BLE001
        pass
    cmd = argv[0] if argv else "status"
    if cmd == "tick":
        tick()
        return 0
    if cmd == "schedule":
        return 0 if schedule() else 1
    res = scan()
    report(res)
    if cmd == "clean":
        freed = clean(res)
        print("정리 %.0fMB" % freed)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
