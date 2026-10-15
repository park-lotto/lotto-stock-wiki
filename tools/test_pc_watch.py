"""관제 214 — PC 점검기 판단(scan): 끌 것 / 절대 안 끌 것."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pc_watch as w  # noqa: E402

NOW = 2_000_000_000


def P(pid, ppid, name, cmd="", mb=100, age_h=1):
    return {"pid": pid, "ppid": ppid, "name": name, "cmd": cmd, "mb": mb, "start": NOW - age_h * 3600}


def _scan(procs, sessions):
    w.free_mb = lambda: 9999
    return w.scan(procs, sessions, now=NOW)


def test_끌_것과_안_끌_것():
    procs = [
        P(1, 0, "explorer.exe"),
        P(10, 1, "powershell.exe"), P(11, 10, "claude.exe", age_h=50),          # 세션 파일 있는 살아 있는 창
        P(20, 1, "powershell.exe"), P(21, 20, "claude.exe", age_h=50),          # 세션 파일 없는 유령(50시간)
        P(30, 1, "powershell.exe"), P(31, 30, "claude.exe", age_h=2),           # 세션 파일 없지만 2시간 — 아직 안 끔
        P(40, 1, "sihost.exe"), P(41, 40, "claude.exe", age_h=99),              # 데스크톱 앱 — 안 끔
        P(50, 999, "node.exe", "node .../firecrawl-mcp/dist/index.js"),         # 부모 없는 도구 서버 찌꺼기 — 끔
        P(60, 999, "python.exe", 'python -c "import subprocess,sys;o=open(x)" track.py finish 장면보충'),  # 분리 실행 finish — 절대 안 끔
        P(70, 999, "python.exe", "python -u -c \"import sys;exec(eval(sys.stdin.readline()))\""),         # 주인 없는 관문 일꾼 — 끔
        P(80, 999, "python.exe", "python some_script.py"),                       # 모르는 파이썬 — 안 끔
    ]
    sessions = {11: {"pid": 11, "status": "idle", "updatedAt": (NOW - 3 * 3600) * 1000, "name": "오래 쉰 창"}}
    r = _scan(procs, sessions)
    killed = {p["pid"] for p, _ in r["kill"]}
    assert killed == {21, 50, 70}, killed
    assert [s["pid"] for s in r["idle"]] == [11], "살아 있는 창은 끄지 않고 '쉬는 창'으로만 알린다"


def test_바쁜_창은_쉬는_창에_안_뜬다():
    procs = [P(1, 0, "explorer.exe"), P(10, 1, "powershell.exe"), P(11, 10, "claude.exe")]
    r = _scan(procs, {11: {"pid": 11, "status": "busy", "updatedAt": 0}})
    assert r["idle"] == [] and r["kill"] == []
