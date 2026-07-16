"""병합 게이트 — 병합이 **기존보다 더** 깨뜨렸는지만 본다.

`git merge --no-ff --no-commit`으로 커밋 없이 병합만 한 상태에서 돌린다.
통과해야만 `git commit` — 커밋하는 순간 post-commit 훅이 무조건 push하므로
게이트는 커밋 이전에 끝나야 의미가 있다.

## 왜 'green'이 아니라 '기준선'인가

현재 전체 pytest에 이미 25 failed가 있다(정체 미규명, 별건). 게이트가
"전부 green"을 요구하면 **모든 병합이 영구히 막힌다**. 그래서 병합 전
스냅샷을 찍어두고 병합 후와 비교해 **새로 깨진 것만** 막는다.
기존 실패는 통과시키되 `baseline_warnings()`로 남긴다 — 조용히 넘기면
게이트가 눈뜬장님이 된 걸 아무도 모른다.

사용:
    py tools/merge_gate.py snapshot --out before.json   # 병합 전
    py tools/merge_gate.py check --baseline before.json # 병합 후 (exit 0=통과)
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TARGET = "shopping_shorts"

# "FAILED id - 메시지" / "FAILED id" / "ERROR path - ImportError"
# id에 공백이 든 파라미터(test_p[a b c])가 있어 \S+로는 못 자른다.
_FAIL_RE = re.compile(r"^(?:FAILED|ERROR)\s+(.+?)(?:\s+-\s+.*)?$")

# pytest 종료코드: 0=전부통과 1=테스트실패 → 정상 범위.
# 2=수집오류 3=내부오류 4=사용법오류 5=수집0 → 게이트가 못 본 것.
_PYTEST_SANE_RC = (0, 1)


def make_output_safe():
    """Windows 콘솔은 cp949라 이모지를 인코딩 못 해 print가 UnicodeEncodeError로 터진다.

    실측(2026-07-16 드라이런): 게이트가 기준선을 수집하고도 'ℹ️'를 찍다가 크래시해
    **한 번도 완주하지 못했다.** 출력 장식 때문에 게이트가 죽으면 안 된다.
    인코딩은 그대로 두고(한글은 cp949에서 멀쩡하다) 못 찍는 문자만 '?'로 바꾼다.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError, ValueError):
            pass  # 리다이렉트·파이프 등 reconfigure 못 하는 스트림이면 그냥 둔다


def parse_failed(output):
    """pytest 출력에서 실패한 테스트 id 집합을 뽑는다."""
    failed = set()
    for line in output.splitlines():
        m = _FAIL_RE.match(line.strip())
        if m:
            failed.add(m.group(1).strip())
    return failed


def _run(cmd, cwd):
    p = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def snapshot(cwd=BASE, run=_run):
    """지금 이 워킹트리 상태를 찍는다 (문법·import·pytest)."""
    rc_c, out_c = run([sys.executable, "-m", "compileall", TARGET, "-q"], cwd)
    rc_i, out_i = run([sys.executable, "-c", f"import {TARGET}.app"], cwd)
    rc_p, out_p = run(
        [sys.executable, "-m", "pytest", f"{TARGET}/tests",
         "-q", "--tb=no", "-rf", "-p", "no:cacheprovider"],
        cwd,
    )
    return {
        "compile_ok": rc_c == 0,
        "compile_out": out_c[-4000:],
        "import_ok": rc_i == 0,
        "import_out": out_i[-4000:],
        "pytest_rc": rc_p,
        "pytest_out": out_p[-4000:],
        "failed": sorted(parse_failed(out_p)),
    }


def baseline_warnings(before):
    """병합 전부터 깨져 있던 것 — 막지는 않되 반드시 보여준다."""
    warn = []
    if not before["compile_ok"]:
        warn.append("⚠️ 병합 전부터 문법 오류가 있다 — 게이트의 문법 검사는 무력하다")
    if not before["import_ok"]:
        warn.append("⚠️ 병합 전부터 import가 깨져 있다 — 의미적 충돌 검출기가 죽은 상태다")
    if before["pytest_rc"] not in _PYTEST_SANE_RC:
        warn.append(f"⚠️ 병합 전부터 pytest가 비정상 종료(rc={before['pytest_rc']}) — 테스트 검사는 무력하다")
    if before["failed"]:
        warn.append(f"ℹ️ 병합 전 이미 실패 {len(before['failed'])}건 (기준선으로 통과시킴)")
    return warn


def compare(before, after):
    """기준선 대비 **새로** 깨진 것만 문제로 센다. 빈 리스트 = 통과."""
    problems = []

    if before["compile_ok"] and not after["compile_ok"]:
        problems.append("문법 오류가 새로 생겼다 (compileall 실패)")

    if before["import_ok"] and not after["import_ok"]:
        problems.append(f"import 체인이 새로 깨졌다 (import {TARGET}.app 실패)")

    before_sane = before["pytest_rc"] in _PYTEST_SANE_RC
    after_sane = after["pytest_rc"] in _PYTEST_SANE_RC
    if before_sane and not after_sane:
        problems.append(
            f"pytest가 아예 못 돌았다 (rc={after['pytest_rc']} — 수집 오류 등). "
            "실패 목록이 비어 있어도 통과가 아니다."
        )

    new_failed = sorted(set(after["failed"]) - set(before["failed"]))
    if new_failed:
        shown = "\n".join(f"    - {t}" for t in new_failed[:20])
        more = f"\n    ... 외 {len(new_failed) - 20}건" if len(new_failed) > 20 else ""
        problems.append(f"새로 깨진 테스트 {len(new_failed)}건:\n{shown}{more}")

    return problems


def _print_report(before, after, problems):
    for w in baseline_warnings(before):
        print(w)
    if problems:
        print("\n❌ 게이트 실패 — 병합이 새로 깨뜨린 것:\n")
        for p in problems:
            print(f"  • {p}")
        if not after["import_ok"]:
            print(f"\n--- import 출력 ---\n{after['import_out']}")
        if after["pytest_rc"] not in _PYTEST_SANE_RC:
            print(f"\n--- pytest 출력 ---\n{after['pytest_out']}")
    else:
        print(f"\n✅ 게이트 통과 — 새로 깨진 것 없음 (기존 실패 {len(before['failed'])}건은 그대로)")


def main(argv=None):
    make_output_safe()
    parser = argparse.ArgumentParser(description="병합 게이트")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="지금 상태를 파일로 찍는다 (병합 전)")
    p_snap.add_argument("--out", required=True)

    p_check = sub.add_parser("check", help="기준선과 비교한다 (병합 후)")
    p_check.add_argument("--baseline", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "snapshot":
        snap = snapshot()
        Path(args.out).write_text(
            json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        for w in baseline_warnings(snap):
            print(w)
        print(f"기준선 저장: {args.out} (실패 {len(snap['failed'])}건)")
        return 0

    before = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    after = snapshot()
    problems = compare(before, after)
    _print_report(before, after, problems)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
