# -*- coding: utf-8 -*-
"""저장 층(C/D) 관제 v2 — SSD(C) 에는 코드가 도는 것만, 나머지는 외장 HDD(D:\\숏템) 로. 지도 관제/storage.json.

실측(2026-09-29): C = SSD 232GB(여유 5~9GB) · D = USB HDD 3.7TB(여유 3,555GB).
  D 큰 파일 쓰기 124MB/s — 영상·보관엔 충분. 4KB 파일 2000개 쓰기 C 0.9초 vs D 8.9초 — 코드·pytest 는 D 에서 못 돈다.
그래서: 활성 트랙(7일 안에 손댄 것)·DB·병합 임시 = C. 식은 트랙은 **폴더를 D 로 옮기고 C 에 정션** → 경로가 그대로라
세션이 열 수 있고(느릴 뿐), 다시 일할 땐 `warm` 으로 C 로 되돌린다. 정션 뒤 git worktree 동작은 실측으로 확인했다.

★판단의 주인: 이 파일의 plan() 하나. "옮겨도 되나"를 다른 곳에서 계산하지 마라(0순위-C).
★apply 는 D 가 꽂혀 있고 규칙 파일(D:/숏템/_저장규칙.txt)이 보일 때만. D 가 빠지면 정션이 죽는다 — status 가 빨강으로 알린다.

사용:
    py tools/storage.py status                 # C/D 여유 · 소비 상위 · 죽은 정션 · 경보선
    py tools/storage.py plan                   # 지도 기준으로 지금 D 로 보낼 것 + GB (실행 없음)
    py tools/storage.py apply --tracks         # 7일+ 무활동 트랙 폴더 → D:/숏템/00_트랙(정션)/<트랙>, C 에 정션
    py tools/storage.py apply --stages         # 끊긴 _merge-* 잔해 삭제
    py tools/storage.py apply --out            # out/ 30일+ 안 연 파일 → D 90_보관/out/<YYYY-MM>/
    py tools/storage.py apply --research       # research/ → D + C 정션
    py tools/storage.py apply --auto           # 위 넷(research 제외) — 작업 스케줄러가 매일 돈다
    py tools/storage.py warm <트랙>            # D 에 있는 트랙 폴더를 C 로 되돌린다(다시 일할 때)
    py tools/storage.py schedule               # Windows 작업 스케줄러에 매일 04:40 --auto 등록
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MAP_REL = "관제/storage.json"
_REPARSE = 0x400


def _git(cwd, *args):
    p = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main_worktree():
    rc, out = _git(Path(__file__).resolve().parent, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if rc == 0 and out.strip():
        return Path(out.strip()).resolve().parent
    return Path(__file__).resolve().parent.parent


def load_map(repo):
    p = Path(repo) / MAP_REL
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def gb(n):
    return n / 2 ** 30


def dir_size(path):
    t = 0
    for r, _ds, fs in os.walk(path):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return t


def free_gb(path):
    try:
        return gb(shutil.disk_usage(str(path)).free)
    except OSError:
        return None


def is_junction(p):
    try:
        return bool(os.lstat(p).st_file_attributes & _REPARSE)
    except (OSError, AttributeError):
        return False


def dead_junction(p):
    """정션은 있는데 목적지가 없다(D 가 빠졌거나 옮겨짐)."""
    return is_junction(p) and not os.path.exists(p)


def make_junction(link, target):
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    return r.returncode == 0


def remove_junction(link):
    """정션만 지운다(목적지 내용은 그대로). rmdir 는 정션에 안전하다."""
    os.rmdir(link)


def external_ok(smap):
    ext = smap.get("외장", {})
    root = Path(ext.get("root", "D:/숏템"))
    rule = Path(ext.get("규칙", str(root / "_저장규칙.txt")))
    if not root.exists():
        return False, "외장 %s 가 없다(안 꽂혔거나 드라이브 문자가 바뀜)" % root
    if not rule.exists():
        return False, "규칙 파일 %s 이 없다 — 다른 디스크가 D 에 물렸을 수 있다. 옮기지 않는다" % rule
    return True, "외장 %s (여유 %.0fGB)" % (root, free_gb(root) or 0)


def _dest(smap, key, default):
    return Path(smap["외장"]["root"]) / smap["외장"].get(key, default)


# ── 후보 (트랙 판단은 track.py 의 것을 부른다) ─────────────────────────────

def idle_tracks(repo, days):
    import track
    out = []
    for br in track.track_branches(repo):
        name = br[len(track.BRANCH_PREFIX):]
        wt = track.worktree_path(name, repo)
        if not os.path.lexists(wt):
            continue
        if is_junction(wt):
            continue                                   # 이미 D 에 있다
        age = track._last_touch_days(repo, name)
        if age is None or age < days:
            continue
        _, st = track.run(["git", "status", "--porcelain"], wt)
        dirty = [p for p in track.parse_status(st) if not track.is_ignorable(p)]
        out.append({"name": name, "age": age, "dirty": len(dirty), "size": dir_size(wt), "wt": wt})
    return out


def cold_tracks(repo):
    """이미 D 에 있는(정션) 트랙 — status 가 보여준다."""
    root = Path(repo) / ".tracks"
    if not root.exists():
        return []
    return [d.name for d in root.iterdir() if is_junction(d) and not d.name.startswith("_")]


def stale_stages(repo):
    root = Path(repo) / ".tracks"
    if not root.exists():
        return []
    return [{"name": d.name, "size": dir_size(d), "path": d} for d in root.iterdir()
            if d.is_dir() and not is_junction(d) and d.name.startswith("_merge-")]


def old_files(root, days):
    """root 아래 days 일 넘게 안 연(atime·mtime 중 늦은 쪽) 파일."""
    cut = time.time() - days * 86400
    out = []
    root = Path(root)
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            try:
                st = p.stat()
            except OSError:
                continue
            if max(st.st_mtime, st.st_atime) < cut:
                out.append({"path": p, "size": st.st_size, "mtime": st.st_mtime})
    return out


def plan(repo, smap, idle_days=7):
    """지도 기준 '지금 D 로 보낼 것' — 실행은 안 한다. 항목: what · size · how · block(막힘 이유) · ref."""
    items = []
    tiers = {t["경로"]: t for t in smap.get("층", [])}
    for t in idle_tracks(repo, idle_days):
        note = "미커밋 %d개(폴더 통째로 가므로 유실 없음)" % t["dirty"] if t["dirty"] else ""
        items.append({"what": ".tracks/%s (%.0f일)" % (t["name"], t["age"]), "size": t["size"],
                      "how": "move+junction", "block": "", "note": note, "ref": t})
    for s in stale_stages(repo):
        items.append({"what": ".tracks/%s (끊긴 병합 잔해)" % s["name"], "size": s["size"], "how": "delete", "block": "", "note": "", "ref": s})
    rs = Path(repo) / "research"
    if "research/" in tiers and rs.exists() and not is_junction(rs):
        items.append({"what": "research/", "size": dir_size(rs), "how": "junction", "block": "", "note": "", "ref": None})
    out_t = tiers.get("out/", {})
    days = int(out_t.get("나이_일", 30))
    olds = old_files(Path(repo) / "out", days)
    if olds:
        items.append({"what": "out/ %d일+ 안 연 파일 %d개" % (days, len(olds)), "size": sum(o["size"] for o in olds),
                      "how": "move → 90_보관/out", "block": "", "note": "", "ref": olds})
    return items


# ── 실행 ────────────────────────────────────────────────────────────

def _require_external(smap):
    ok, why = external_ok(smap)
    if not ok:
        raise SystemExit("중단: " + why)


def move_track_to_external(repo, smap, name, printer=print):
    """트랙 폴더 → D:/숏템/00_트랙(정션)/<트랙>, C 에 정션. 실패하면 되돌린다."""
    import track
    wt = track.worktree_path(name, repo)
    if is_junction(wt):
        printer("   %s: 이미 D 에 있다" % name)
        return False
    dest_root = _dest(smap, "트랙", "00_트랙(정션)")
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / name
    if dest.exists():
        printer("   건너뜀 %s: %s 가 이미 있다 — 합치는 판단은 사람이" % (name, dest))
        return False
    try:
        shutil.move(str(wt), str(dest))
    except (OSError, shutil.Error) as e:
        printer("   건너뜀 %s: 못 옮김(열린 창·터미널?) %s" % (name, str(e)[:100]))
        if dest.exists() and not wt.exists():
            shutil.move(str(dest), str(wt))           # 반쯤 옮겨진 것 되돌림
        return False
    if not make_junction(wt, dest):
        shutil.move(str(dest), str(wt))
        printer("   건너뜀 %s: 정션 생성 실패 — 되돌렸다" % name)
        return False
    rc, out = _git(wt, "status", "--porcelain")
    if rc != 0:                                        # 정션 뒤에서 git 이 안 되면 되돌린다(조용히 넘기지 않는다)
        remove_junction(wt)
        shutil.move(str(dest), str(wt))
        printer("   건너뜀 %s: 정션 뒤 git 실패 — 되돌렸다: %s" % (name, out.strip()[:100]))
        return False
    printer("   → D  %s (%.2fGB)" % (name, gb(dir_size(dest))))
    return True


def warm_track(repo, smap, name, printer=print):
    """D 에 있는 트랙 폴더를 C 로 되돌린다(다시 일할 때)."""
    import track
    wt = track.worktree_path(name, repo)
    if not is_junction(wt):
        printer("%s 는 이미 C 에 있다" % name)
        return False
    if dead_junction(wt):
        raise SystemExit("중단: %s 정션의 목적지가 없다 — D 가 꽂혀 있나?" % name)
    real = Path(os.path.realpath(wt))
    need = gb(dir_size(real))
    have = free_gb(repo) or 0
    if have - need < smap.get("경보", {}).get("refuse_gb", 3):
        raise SystemExit("중단: C 여유 %.1fGB 인데 %.1fGB 가 필요하다 — 먼저 다른 트랙을 D 로" % (have, need))
    remove_junction(wt)
    shutil.move(str(real), str(wt))
    rc, out = _git(wt, "status", "--porcelain")
    printer("← C  %s (%.2fGB)%s" % (name, need, "" if rc == 0 else "  ⚠️ git status 실패: " + out.strip()[:80]))
    return True


def apply_tracks(repo, smap, idle_days=7, printer=print):
    _require_external(smap)
    before = free_gb(repo)
    moved = 0
    for t in idle_tracks(repo, idle_days):
        if move_track_to_external(repo, smap, t["name"], printer):
            moved += 1
    printer("트랙 %d개 → D · C 여유 %.1fGB → %.1fGB" % (moved, before or 0, free_gb(repo) or 0))
    return moved


def apply_stages(repo, printer=print):
    import track
    with track._finish_gate_lock():          # 살아 있는 finish 가 있으면 기다린다 — 그 stage 를 지우면 병합이 깨진다
        removed = track._clean_dead_stages(repo)
    printer("잔해 %d개 정리" % len(removed))
    return len(removed)


def apply_out(repo, smap, printer=print):
    _require_external(smap)
    tiers = {t["경로"]: t for t in smap.get("층", [])}
    days = int(tiers.get("out/", {}).get("나이_일", 30))
    dest_root = _dest(smap, "보관", "90_보관") / "out"
    n = tot = 0
    for o in old_files(Path(repo) / "out", days):
        ym = time.strftime("%Y-%m", time.localtime(o["mtime"]))
        rel = o["path"].relative_to(Path(repo) / "out")
        dst = dest_root / ym / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst = dst.with_name(dst.stem + "_" + str(int(o["mtime"])) + dst.suffix)
        shutil.move(str(o["path"]), str(dst))
        n += 1
        tot += o["size"]
    printer("out/ %d일+ 파일 %d개 %.2fGB → %s" % (days, n, gb(tot), dest_root))
    return n


def apply_research(repo, smap, printer=print):
    _require_external(smap)
    src = Path(repo) / "research"
    if is_junction(src):
        printer("research/ 는 이미 정션이다")
        return False
    dst = Path(smap["외장"]["root"]) / "80_강의·참고" / "research"
    if dst.exists():
        raise SystemExit("중단: %s 가 이미 있다 — 합치는 판단은 사람이" % dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    if not make_junction(src, dst):
        shutil.move(str(dst), str(src))
        raise SystemExit("중단: 정션 생성 실패 — 되돌렸다")
    printer("research/ → %s (C 에는 정션)" % dst)
    return True


def status(repo, smap, printer=print):
    c = free_gb(repo)
    ok, why = external_ok(smap)
    warn, refuse = smap.get("경보", {}).get("warn_gb", 15), smap.get("경보", {}).get("refuse_gb", 3)
    flag = "❌ finish 거절선 아래" if c is not None and c < refuse else ("⚠️ 경고선 아래" if c is not None and c < warn else "정상")
    printer("C 여유 %.1fGB (%s: 경고 %dGB · 거절 %dGB) · %s" % (c or 0, flag, warn, refuse, why))
    root = Path(repo)
    dead = [d.name for d in (root / ".tracks").iterdir() if dead_junction(d)] if (root / ".tracks").exists() else []
    if dead_junction(root / "research"):
        dead.append("research")
    if dead:
        printer("❌ 죽은 정션 %d개(D 가 빠졌나?): %s" % (len(dead), ", ".join(dead)))
    cold = cold_tracks(repo)
    if cold:
        printer("D 에 있는 트랙 %d개: %s   (되돌리기: py tools/storage.py warm <트랙>)" % (len(cold), ", ".join(cold)))
    rows = []
    for d in root.iterdir():
        if d.is_dir() and d.name != ".tracks" and not is_junction(d):
            rows.append((d.name, dir_size(d)))
    tr = root / ".tracks"
    if tr.exists():
        hot = [x for x in tr.iterdir() if x.is_dir() and not is_junction(x)]
        rows.append((".tracks C 에 %d개" % len(hot), sum(dir_size(x) for x in hot)))
    for name, sz in sorted(rows, key=lambda x: -x[1])[:10]:
        printer("  %-28s %6.2f GB" % (name, gb(sz)))


def schedule(repo, smap, printer=print):
    a = smap.get("자동", {})
    name, at = a.get("작업이름", "숏템_저장층_정리"), a.get("시각", "04:40")
    py = shutil.which("python") or sys.executable
    cmd = 'cmd /c "cd /d \\"%s\\" && \\"%s\\" tools\\storage.py apply --auto >> \\"%s\\" 2>&1"' % (
        repo, py, Path(repo) / "관제" / "storage_auto.log")
    r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", at, "/TN", name, "/TR", cmd],
                       capture_output=True, text=True, encoding="cp949", errors="replace")
    printer(("✅ 작업 스케줄러 등록: %s 매일 %s" % (name, at)) if r.returncode == 0 else ("❌ 등록 실패: " + (r.stdout + r.stderr).strip()[:200]))
    return r.returncode == 0


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="저장 층(C/D) 관제")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("plan")
    p.add_argument("--days", type=float, default=7)
    p = sub.add_parser("apply")
    for f in ("tracks", "stages", "out", "research", "auto"):
        p.add_argument("--" + f, action="store_true")
    p.add_argument("--days", type=float, default=7)
    p = sub.add_parser("warm")
    p.add_argument("name")
    sub.add_parser("schedule")
    args = ap.parse_args(argv)
    repo = main_worktree()
    smap = load_map(repo)
    if smap is None:
        print("지도가 없다: %s" % MAP_REL, file=sys.stderr)
        return 2
    if args.cmd == "status":
        status(repo, smap)
    elif args.cmd == "plan":
        items = plan(repo, smap, args.days)
        total = 0
        for it in items:
            extra = ("  · " + it["note"]) if it.get("note") else ""
            print("  %-46s %6.2f GB  %s%s" % (it["what"], gb(it["size"]), it["how"], extra))
            total += it["size"]
        print("\n지금 D 로 보낼 수 있는 것 %.1fGB (%d항목). 실행: py tools/storage.py apply --tracks --stages --out [--research]" % (gb(total), len(items)))
    elif args.cmd == "warm":
        warm_track(repo, smap, args.name)
    elif args.cmd == "schedule":
        schedule(repo, smap)
    else:
        print("[%s] 저장 층 정리 시작" % time.strftime("%Y-%m-%d %H:%M"))
        if args.tracks or args.auto:
            apply_tracks(repo, smap, args.days)
        if args.stages or args.auto:
            apply_stages(repo)
        if args.out or args.auto:
            apply_out(repo, smap)
        if args.research:
            apply_research(repo, smap)
        if not (args.tracks or args.stages or args.out or args.research or args.auto):
            print("무엇을 옮길지 골라라: --tracks / --stages / --out / --research / --auto")
        status(repo, smap)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
