# -*- coding: utf-8 -*-
"""PC 세팅 점검 — 집 PC·회사 PC 어디서든 칼카피·숏템 MCP 일을 시작하기 전에 한 번(사장님 10-29 '집 PC·회사 PC 모두 동일하게').

  PYTHONUTF8=1 py tools/calcopy/pc_check.py            # ✓/✗ 목록 — ✗ 가 있으면 rc=1
  PYTHONUTF8=1 py tools/calcopy/pc_check.py --pull     # 트랙이 원격보다 뒤면 먼저 받는다(git pull)

코드는 git 이 두 PC 를 맞춘다. 이 점검은 git 에 없는 PC 마다의 것(키·로그인·렌더용 크롬·도구·글꼴·디스크)과 트랙이 최신인지만 본다.
키는 '있다/없다'만 — 값은 읽어 출력하지 않는다. 10-29 실측 사고: ~/.cache/puppeteer 가 통째 지워져 렌더·시험 실패 · mcp* 유튜브 프로필 없음 ·
쿠팡 키가 제작 도구에 안 넘어감 — 셋 다 이 점검이면 시작 전에 보였다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
rows: list[tuple[bool, str, str]] = []


def add(ok: bool, what: str, note: str = "") -> None:
    rows.append((bool(ok), what, note))


def git(*a) -> str:
    r = subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip()


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, str(ROOT))
    # 트랙 최신
    br = git("branch", "--show-current")
    git("fetch", "-q", "origin")
    behind = git("rev-list", "--count", f"HEAD..origin/{br}") or "0"
    if "--pull" in argv and behind != "0":
        git("pull", "-q", "--no-rebase")
        behind = git("rev-list", "--count", f"HEAD..origin/{br}") or "0"
    add(behind == "0", f"트랙 최신({br})", "원격보다 뒤 " + behind + "커밋 — --pull" if behind != "0" else "")
    dirty = [l for l in git("status", "--porcelain").splitlines() if l.strip()]
    add(True, "미커밋 파일", f"{len(dirty)}개" + (" — 남의 창 것이면 건드리지 말 것(🛑16)" if dirty else ""))
    # 도구
    for t in ("ffmpeg", "ffprobe", "yt-dlp", "node", "git"):
        add(bool(shutil.which(t)), f"도구 {t}")
    add(sys.version_info >= (3, 11), "파이썬", sys.version.split()[0])
    # 렌더용 크롬(장면 꾸미기 렌더러·고객 프로그램 개발 모드)
    pc = HOME / ".cache" / "puppeteer"
    add(any((pc / "chrome").glob("*/*/chrome.exe")), "렌더용 크롬(puppeteer chrome)", "없으면: npx puppeteer browsers install chrome")
    add(any((pc / "chrome-headless-shell").glob("*/*/chrome-headless-shell.exe")), "렌더용 크롬(headless shell)",
        "없으면: npx puppeteer browsers install chrome-headless-shell")
    nm = Path(ROOT).parents[1] / "node_modules" / "puppeteer"
    add(nm.exists() or (ROOT / "node_modules" / "puppeteer").exists(), "puppeteer 모듈(node_modules)")
    # 키(있다/없다만)
    env = ROOT / ".env"
    n_env = sum(1 for l in env.read_text(encoding="utf-8", errors="ignore").splitlines() if "=" in l and not l.strip().startswith("#")) if env.is_file() else 0
    add(n_env > 0, ".env 키", f"{n_env}줄")
    vk = HOME / ".volcano" / "keys"
    for k in ("speechmatics", "typecast"):
        add((vk / k).is_file(), f"키 {k}", "~/.volcano/keys/" + k)
    add((HOME / ".claude" / "coupang_partners_key.txt").is_file(), "키 쿠팡 파트너스", "~/.claude/coupang_partners_key.txt")
    # 유튜브 로그인 프로필
    try:
        from shopping_shorts.media_download import _firefox_profile_paths
        from tools.calcopy.origin_find import _yt_logged_in
        for pre in ("yt", "mcp"):
            ps = _firefox_profile_paths(pre)
            live = sum(1 for p in ps if _yt_logged_in(p))
            add(live > 0 or pre == "mcp", f"유튜브 프로필 {pre}*", f"로그인 {live}/{len(ps)}" + (" (mcp* 는 회원 시험 전용 — 없으면 SHORTEM_YT_PROFILES=yt)" if pre == "mcp" else ""))
    except Exception as e:  # noqa: BLE001 — 점검 자체가 못 돌면 그 사실을 보인다
        add(False, "유튜브 프로필", f"점검 실패: {type(e).__name__}: {e}"[:120])
    for f in ("out/tiktok_session.json", "out/instagram_session.json"):
        add((ROOT / f).is_file() or (ROOT.parents[1] / f).is_file(), f"로그인 파일 {Path(f).name}")
    # 글꼴·디스크
    fd = ROOT / "shopping_shorts" / "static" / "fonts"
    nf = len([p for p in fd.glob("*") if p.suffix.lower() in (".ttf", ".otf")]) if fd.is_dir() else 0
    add(nf >= 40, "글꼴", f"{nf}개")
    free = shutil.disk_usage("C:/").free / 1e9
    add(free > 15, "C 디스크 여유", f"{free:.0f}GB")
    for ok, what, note in rows:
        print(f"{'✓' if ok else '✗'} {what}" + (f" — {note}" if note else ""))
    bad = sum(1 for ok, *_ in rows if not ok)
    print(f"판정: {'준비 끝' if not bad else f'✗ {bad}개 — 고친 뒤 시작'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
