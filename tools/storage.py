# -*- coding: utf-8 -*-
"""저장 층(C/D) 관제 — 무엇이 C 를 먹고, 지도(관제/storage.json)대로 무엇을 D 로 보낼 수 있는지 재고, 확인 뒤 옮긴다.

왜(2026-09-27~29 실측): 트랙 폴더 34개 44.8GB 가 C 232GB 의 1/5 를 먹어 finish 임시 폴더가 끊기고 코덱스 업데이트까지 깨졌다.
외장 D:\\숏템 은 3.7TB 중 3.55TB 가 비어 있다. "만드는 동안은 C, 다 만들면 D" — 그 판단을 사람이 매번 하지 않게 지도 한 곳 + 도구.

★판단의 주인: 이 파일의 plan() 하나. 옮겨도 되는지를 다른 도구가 따로 계산하지 마라(0순위-C).
★apply 는 D 가 꽂혀 있고 규칙 파일(D:/숏템/_저장규칙.txt)이 보일 때만, 그리고 사장님 확인 뒤에만.

사용:
    py tools/storage.py status            # C/D 여유 · 소비 상위 · 경보선
    py tools/storage.py plan              # 지도 기준으로 지금 D 로 보낼 수 있는 것과 GB
    py tools/storage.py apply --tracks    # 7일+ 무활동·미커밋 0 트랙: bundle → D, 폴더 주차
    py tools/storage.py apply --stages    # 끊긴 _merge-* 잔해 삭제
    py tools/storage.py apply --research  # research/ → D + C 에 정션
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


def external_ok(smap):
    """D 가 꽂혀 있고 규칙 파일이 보이나 → (ok, 이유)."""
    ext = smap.get("외장", {})
    root = Path(ext.get("root", "D:/숏템"))
    rule = Path(ext.get("규칙", str(root / "_저장규칙.txt")))
    if not root.exists():
        return False, "외장 %s 가 없다(안 꽂혔거나 드라이브 문자가 바뀜)" % root
    if not rule.exists():
        return False, "규칙 파일 %s 이 없다 — 다른 디스크가 D 에 물렸을 수 있다. 옮기지 않는다" % rule
    return True, "외장 %s (여유 %.0fGB)" % (root, free_gb(root) or 0)


# ── 트랙 후보 (track.py 의 판단을 부른다 — 여기서 다시 적지 않는다) ───────────────

def idle_tracks(repo, days):
    import track
    out = []
    for br in track.track_branches(repo):
        name = br[len(track.BRANCH_PREFIX):]
        wt = track.worktree_path(name, repo)
        if not wt.exists():
            continue
        age = track._last_touch_days(repo, name)
        if age is None or age < days:
            continue
        _, st = track.run(["git", "status", "--porcelain"], wt)
        dirty = [p for p in track.parse_status(st) if not track.is_ignorable(p)]
        out.append({"name": name, "age": age, "dirty": len(dirty), "size": dir_size(wt), "wt": wt})
    return out


def stale_stages(repo):
    root = Path(repo) / ".tracks"
    if not root.exists():
        return []
    return [{"name": d.name, "size": dir_size(d), "path": d} for d in root.iterdir()
            if d.is_dir() and d.name.startswith("_merge-")]


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
                out.append({"path": p, "size": st.st_size})
    return out


def plan(repo, smap, idle_days=7):
    """지도 기준 '지금 D 로 보낼 수 있는 것' — 실행은 안 한다. 항목마다 (무엇, GB, 방법, 막힘 이유)."""
    items = []
    tiers = {t["경로"]: t for t in smap.get("층", [])}
    for t in idle_tracks(repo, idle_days):
        block = "미커밋 %d개 — 건너뜀" % t["dirty"] if t["dirty"] else ""
        items.append({"what": ".tracks/%s (%.0f일)" % (t["name"], t["age"]), "size": t["size"],
                      "how": "park+bundle", "block": block, "ref": t})
    for s in stale_stages(repo):
        items.append({"what": ".tracks/%s (끊긴 병합 잔해)" % s["name"], "size": s["size"], "how": "delete", "block": "", "ref": s})
    if "research/" in tiers and not (Path(repo) / "research").is_symlink() and not _is_junction(Path(repo) / "research"):
        items.append({"what": "research/", "size": dir_size(Path(repo) / "research"), "how": "junction", "block": "", "ref": None})
    out_t = tiers.get("out/", {})
    olds = old_files(Path(repo) / "out", int(out_t.get("나이_일", 30)))
    if olds:
        items.append({"what": "out/ %d일+ 안 연 파일 %d개" % (int(out_t.get("나이_일", 30)), len(olds)), "size": sum(o["size"] for o in olds),
                      "how": "move → 90_보관/out", "block": "", "ref": olds})
    return items


def _is_junction(p):
    try:
        return p.exists() and bool(os.stat(p, follow_symlinks=False).st_file_attributes & 0x400)   # REPARSE_POINT
    except (OSError, AttributeError):
        return False


# ── 실행 ────────────────────────────────────────────────────────────

def apply_tracks(repo, smap, idle_days=7, printer=print):
    import track
    ok, why = external_ok(smap)
    if not ok:
        raise SystemExit("중단: " + why)
    dest = Path(smap["외장"]["root"]) / smap["외장"].get("보관", "90_보관") / "트랙"
    dest.mkdir(parents=True, exist_ok=True)
    before = free_gb(repo)
    done = 0
    for t in idle_tracks(repo, idle_days):
        if t["dirty"]:
            printer("   건너뜀 %s: 미커밋 %d개" % (t["name"], t["dirty"]))
            continue
        b = dest / ("%s.bundle" % t["name"])
        rc, out = _git(repo, "bundle", "create", str(b), "track/%s" % t["name"])
        if rc != 0:
            printer("   건너뜀 %s: bundle 실패 %s" % (t["name"], out.strip()[:120]))
            continue
        try:
            track.park(t["name"], repo=repo)
            done += 1
        except track.TrackError as e:
            printer("   건너뜀 %s: %s" % (t["name"], str(e).splitlines()[0]))
    printer("주차 %d개 · C 여유 %.1fGB → %.1fGB · bundle: %s" % (done, before or 0, free_gb(repo) or 0, dest))


def apply_stages(repo, printer=print):
    import track
    with track._finish_gate_lock():          # 살아 있는 finish 가 있으면 기다린다 — 그 stage 를 지우면 병합이 깨진다
        removed = track._clean_dead_stages(repo)
    printer("잔해 %d개 정리" % len(removed))


def apply_research(repo, smap, printer=print):
    ok, why = external_ok(smap)
    if not ok:
        raise SystemExit("중단: " + why)
    src = Path(repo) / "research"
    if _is_junction(src):
        printer("research/ 는 이미 정션이다")
        return
    dst = Path(smap["외장"]["root"]) / "80_강의·참고" / "research"
    if dst.exists():
        raise SystemExit("중단: %s 가 이미 있다 — 합치는 판단은 사람이" % dst)
    shutil.move(str(src), str(dst))
    rc = subprocess.run(["cmd", "/c", "mklink", "/J", str(src), str(dst)], capture_output=True, text=True).returncode
    if rc != 0:
        shutil.move(str(dst), str(src))
        raise SystemExit("중단: 정션 생성 실패 — 되돌렸다")
    printer("research/ → %s (C 에는 정션)" % dst)


def status(repo, smap, printer=print):
    c = free_gb(repo)
    ok, why = external_ok(smap)
    warn, refuse = smap.get("경보", {}).get("warn_gb", 15), smap.get("경보", {}).get("refuse_gb", 3)
    flag = "❌ finish 거절선 아래" if c is not None and c < refuse else ("⚠️ 경고선 아래" if c is not None and c < warn else "정상")
    printer("C 여유 %.1fGB (%s: 경고 %dGB · 거절 %dGB) · %s" % (c or 0, flag, warn, refuse, why))
    root = Path(repo)
    rows = []
    for d in root.iterdir():
        if d.is_dir() and d.name != ".tracks":
            rows.append((d.name, dir_size(d)))
    tr = root / ".tracks"
    if tr.exists():
        rows.append((".tracks (%d개)" % sum(1 for x in tr.iterdir() if x.is_dir()), dir_size(tr)))
    for name, sz in sorted(rows, key=lambda x: -x[1])[:10]:
        printer("  %-28s %6.2f GB" % (name, gb(sz)))


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
    p.add_argument("--tracks", action="store_true")
    p.add_argument("--stages", action="store_true")
    p.add_argument("--research", action="store_true")
    p.add_argument("--days", type=float, default=7)
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
            mark = "  ✋ " + it["block"] if it["block"] else ""
            print("  %-46s %6.2f GB  %s%s" % (it["what"], gb(it["size"]), it["how"], mark))
            if not it["block"]:
                total += it["size"]
        print("\n지금 회수 가능 %.1fGB (%d항목). 실행: py tools/storage.py apply --tracks|--stages|--research  (사장님 확인 뒤)" % (gb(total), len(items)))
    else:
        if args.tracks:
            apply_tracks(repo, smap, args.days)
        if args.stages:
            apply_stages(repo)
        if args.research:
            apply_research(repo, smap)
        if not (args.tracks or args.stages or args.research):
            print("무엇을 옮길지 골라라: --tracks / --stages / --research")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
