"""작업 스케줄러가 띄우는 실행기 — 창 없이 돌고, 출력은 로그 파일로(관제 107).

  pythonw.exe tools\\sched_run.py --log <로그> -- tools\\storage.py apply --auto

왜(2026-10-04 실측):
- cmd /c 로 띄우면 매시간 검은 명령창이 화면에 떴고, 사장님이 닫으면 Ctrl+C 로 작업이 죽었다(-1073741510, 10:41 실행 4분 만에 끝).
- cmd 를 거치면 따옴표 규칙이 끼어 등록 뒤 한 달간 한 번도 안 돌았다(cd /d \\"…\\").
- 출력이 끝날 때 한꺼번에 써져 중간에 죽으면 무엇을 하다 죽었는지 안 남았다.
그래서: pythonw(창 없음) → 숨긴 콘솔을 하나 붙여 자식(git·ssh)도 창이 안 뜨게 → 줄 단위로 로그에 쓴다 → 시작·끝·종료코드를 남긴다.
"""
import os
import runpy
import sys
import time


def _hidden_console():
    """창 없는 pythonw 에 숨긴 콘솔을 붙인다 — 콘솔 프로그램 자식(git·ssh)이 저마다 새 창을 띄우지 않게."""
    if os.name != "nt":
        return
    import ctypes
    k = ctypes.windll.kernel32
    if k.GetConsoleWindow():
        return
    if k.AllocConsole():
        h = k.GetConsoleWindow()
        if h:
            ctypes.windll.user32.ShowWindow(h, 0)     # SW_HIDE


def main(argv):
    if "--" not in argv or "--log" not in argv:
        print("사용: sched_run.py --log <로그> -- <스크립트> [인자…]", file=sys.stderr)
        return 2
    log = argv[argv.index("--log") + 1]
    target = argv[argv.index("--") + 1:]
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo)
    _hidden_console()
    f = open(log, "a", encoding="utf-8", buffering=1)          # 줄 단위 — 중간에 죽어도 거기까지 남는다
    sys.stdout = sys.stderr = f
    os.environ["PYTHONIOENCODING"] = "utf-8"
    print("[%s] ▶ %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), " ".join(target)))
    sys.path.insert(0, os.path.join(repo, os.path.dirname(target[0])))
    sys.argv = target
    rc = 0
    try:
        runpy.run_path(target[0], run_name="__main__")
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except BaseException:
        import traceback
        traceback.print_exc()
        rc = 1
    print("[%s] ■ 끝 rc=%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), rc))
    f.flush()
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
