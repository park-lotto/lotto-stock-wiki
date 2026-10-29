"""칼카피 판 → 회원 MCP 내보내기: '발행 대기 → 사장님 스위치' (관제 265).

  py tools/claude_portal/member_publish.py status                  # 엔진 모든 slug 의 단계·빠진 것·대기열 여부
  py tools/claude_portal/member_publish.py live <slug> --out <flow_episode 결과 파일> [--dir <편 폴더>]   # MCP 길 완주 기록(회원실측)
  py tools/claude_portal/member_publish.py approve <slug>          # 사장님이 그 완성본을 보고 '됐다' 하신 뒤에만
  py tools/claude_portal/member_publish.py queue <slug>            # 회원실측 완주 + 사장님 확인 된 판만 channel/발행대기.json 에(그 외 거절)
  py tools/claude_portal/member_publish.py open --dry              # 사장님 스위치 — 대기열 판마다 꾸러미→설치본→올리기 계획만 출력
  py tools/claude_portal/member_publish.py open --owner-ok         # 실제 실행(사장님이 켤 때만 — 없으면 거절)
  (공통 --engine <엔진 트랙 폴더>, 기본 ../칼카피숏템엔진)

판단 주인(한 곳): 발행해도 되나 = 이 파일 ready() — 사장님 10-29 '하나의 MCP·퀄리티만 나오면': MCP 길(설치 묶음 엔진+꾸러미+지시서+Claude)로
  실제 한 편 완주한 기록(channel/<slug>/_kal/회원실측.json ok — preset_card member_live 와 같은 파일) + 사장님 확인(owner_ok).
  옛 기준(preset_card 서류 단계 L2)은 status 에 참고로만. 열 때 첫 단계 = 고객 경로 점검(member_check) — 빠진 게 있으면 멈춘다. 엔진 모듈(tools·shopping_shorts)이 이 저장소와
  이름이 겹치므로 엔진 폴더에서 별도 프로세스로 부른다(card_levels).
실행 순서 주인: 기존 도구 그대로 — preset_pack.py build → installer/win/build_win.py → upload_release.py.
결과물 검사: shopping_shorts/tests/test_member_publish.py (L1 거절·L2 통과·스위치 없으면 거절·--dry 계획).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENGINE = ROOT        # 10-29 숏템MCP 를 엔진 트랙에 합쳐 같은 폴더(하나의 MCP)
QUEUE_REL = "channel/발행대기.json"
PUBLISH_LEVELS = ("L2", "L3", "L4")      # 표준 §6: L2 = 품질관문○·재현일치도○·눈검수 E1~E8 — 이 이름 앞머리만 본다(조건은 preset_card)

_PROBE = r"""
import json, sys
sys.path.insert(0, '.')
from tools.calcopy import preset_card as pc
out = {}
for s, pre in pc.presets().items():
    d = pc.build_card(s)["done"]
    out[s] = {"level": d["level"], "missing": d["missing"], "preset_dir": (pre.get("engine") or {}).get("preset_dir")}
sys.stdout.write(json.dumps(out, ensure_ascii=False))
"""


def card_levels(engine: Path) -> dict:
    """엔진 판정 주인(preset_card)을 엔진 폴더에서 불러 {slug: {level, missing, preset_dir}}."""
    r = subprocess.run([sys.executable, "-c", _PROBE], cwd=str(engine), capture_output=True,
                       env={**os.environ, "PYTHONUTF8": "1"}, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"[member_publish] preset_card 판정 실패:\n{r.stderr[-2000:]}")
    return json.loads(r.stdout)


def publishable(level: str) -> bool:
    return str(level).startswith(PUBLISH_LEVELS)


def live_path(engine: Path, slug: str) -> Path:
    return engine / "channel" / slug / "_kal" / "회원실측.json"


def live_record(engine: Path, slug: str) -> dict:
    p = live_path(engine, slug)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except ValueError:
        return {}


def ready(engine: Path, slug: str, d) -> tuple:
    """(판단 주인 — 발행해도 되나) MCP 길 완주 기록 ok + 사장님 확인 + 프리셋 폴더. (됨, 이유)."""
    if not d:
        return False, "엔진 channel/프리셋.json 에 없는 판"
    if not d.get("preset_dir"):
        return False, "프리셋.json engine.preset_dir 없음"
    rec = live_record(engine, slug)
    if not rec.get("ok"):
        return False, "MCP 길 완주 기록 없음(회원실측) — 고객 방식으로 한 편 끝까지 만든 뒤 live 로 기록"
    if not rec.get("owner_ok"):
        return False, f"사장님 확인 전 — 완성본 {rec.get('video') or '?'} 을 보시고 '됐다' 하시면 approve"
    return True, "MCP 완주 + 사장님 확인"


def cmd_live(engine: Path, slug: str, out_file: Path, run_dir) -> int:
    """flow_episode.js 결과(마지막 JSON) → 회원실측.json. ok = 완성본 파일이 있고 소리·길이가 있음."""
    t = out_file.read_text(encoding="utf-8", errors="replace")
    try:
        r = json.loads(t[t.find("{"):])
    except ValueError:
        print(f"[거절] {out_file}: 결과 JSON 을 못 읽었다")
        return 2
    vids = [v for v in r.get("videos") or [] if Path(v).is_file()]
    fin = r.get("final") or {}
    ok = bool(r.get("ok") and vids and fin.get("audio") and float(fin.get("sec") or 0) > 5)
    prev = live_record(engine, slug)
    rec = {"ok": ok, "video": vids[0] if vids else None, "final": fin, "run_dir": run_dir,
           "path": "MCP(설치 묶음 엔진+꾸러미+지시서+Claude, flow_episode.js)", "at": datetime.now().isoformat(timespec="seconds"),
           "owner_ok": False, "earlier": ({k: v for k, v in prev.items() if k != "earlier"} if prev else None)}   # 옛 기록은 이전 칸으로(섞지 않는다)
    p = live_path(engine, slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{slug}: 회원실측 {'완주' if ok else '실패'} 기록 → {p}")
    return 0 if ok else 1


def cmd_approve(engine: Path, slug: str) -> int:
    rec = live_record(engine, slug)
    if not rec.get("ok"):
        print(f"[거절] {slug}: MCP 길 완주 기록이 없어 확인할 완성본이 없다")
        return 2
    rec.update(owner_ok=True, owner_at=datetime.now().isoformat(timespec="seconds"))
    live_path(engine, slug).write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{slug}: 사장님 확인 기록 — 완성본 {rec.get('video')}")
    return 0


def queue_path(engine: Path) -> Path:
    return engine / QUEUE_REL


def load_queue(engine: Path) -> dict:
    p = queue_path(engine)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"made_by": "tools/claude_portal/member_publish.py queue (숏템MCP)", "queue": []}


def save_queue(engine: Path, q: dict) -> None:
    p = queue_path(engine)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(q, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_status(engine: Path) -> int:
    L = card_levels(engine)
    queued = {e["slug"] for e in load_queue(engine)["queue"]}
    print(f"{'slug':18} {'발행가능':8} {'대기열':6} 이유 (참고: 서류 단계)")
    n_pub = 0
    for s, d in L.items():
        ok, why = ready(engine, s, d)
        n_pub += ok
        print(f"{s:18} {'○' if ok else '-':8} {'○' if s in queued else '-':6} {why} (참고 {d['level']})")
    print(f"총 {len(L)}판 · 발행 가능 {n_pub} · 대기열 {len(queued)}")
    return 0


def cmd_queue(engine: Path, slug: str) -> int:
    L = card_levels(engine)
    d = L.get(slug)
    ok, why = ready(engine, slug, d)
    if not ok:
        print(f"[거절] {slug}: {why}")
        return 2
    q = load_queue(engine)
    if any(e["slug"] == slug for e in q["queue"]):
        print(f"{slug}: 이미 대기열에 있다")
        return 0
    q["queue"].append({"slug": slug, "level": d["level"], "preset_dir": d["preset_dir"],
                       "queued_at": datetime.now().isoformat(timespec="seconds")})
    save_queue(engine, q)
    print(f"{slug}: 대기열 추가 ({why}) → {QUEUE_REL}")
    return 0


def _version() -> str:
    return json.loads((ROOT / "installer/common/tools.lock.json").read_text(encoding="utf-8"))["installer_version"]


def plan(engine: Path, out: Path, version: str) -> tuple[list[list[str]], list[str]]:
    """대기열 판 → 실행할 명령 목록. 열 때 ready() 를 다시 재서 떨어진 판은 뺀다(사유는 skipped). 첫 단계 = 고객 경로 점검(member_check)."""
    L = card_levels(engine)
    py = sys.executable
    steps, skipped = [], []
    packs = out / "packs"
    for e in load_queue(engine)["queue"]:
        d = L.get(e["slug"])
        ok, why = ready(engine, e["slug"], d)
        if not ok:
            skipped.append(f"{e['slug']}: {why}")
            continue
        steps.append([py, "tools/claude_portal/preset_pack.py", "build", "--engine", str(engine), "--preset", d["preset_dir"], "--out", str(packs)])
    if steps:
        dirs = [x for c in steps for i, x in enumerate(c) if i and c[i - 1] == "--preset"]
        steps.insert(0, [py, "tools/claude_portal/member_check.py", *[a for d_ in dirs for a in ("--preset", d_)]])   # 고객 경로 점검 — 빠진 게 있으면 rc=1 로 멈춘다
        steps.append([py, "installer/win/build_win.py", "--out", str(out), "--engine", str(engine), "--version", version])
        steps.append([py, "tools/claude_portal/upload_release.py", "--dist", str(out / "dist"), "--packs", str(packs),
                      "--version", version, "--update-stage", str(out / "win-x64" / "Shortem")])
    return steps, skipped


def cmd_open(engine: Path, dry: bool, owner_ok: bool, out: Path, version: str) -> int:
    if not dry and not owner_ok:
        print("[거절] open 실행은 사장님 스위치(--owner-ok)가 있어야 한다. 계획만 보려면 --dry")
        return 2
    steps, skipped = plan(engine, out, version)
    for s in skipped:
        print(f"[제외] {s}")
    if not steps:
        print("대기열에 내보낼 판이 없다")
        return 0
    print(f"계획 ({'--dry, 실행 안 함' if dry else '실행'}) · 판 {len(steps) - 3} · 판(버전) {version}")
    for i, c in enumerate(steps, 1):
        print(f"{i}. " + " ".join(c))
    if dry:
        return 0
    for c in steps:
        r = subprocess.run(c, cwd=str(ROOT))
        if r.returncode != 0:
            print(f"[중단] rc={r.returncode}: {' '.join(c)}")
            return r.returncode
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001 - 콘솔이 못 바꾸면 그대로
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", default=str(DEFAULT_ENGINE))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    qp = sub.add_parser("queue")
    qp.add_argument("slug")
    lp = sub.add_parser("live")
    lp.add_argument("slug")
    lp.add_argument("--out", required=True, help="flow_episode.js 결과 파일(마지막 JSON)")
    lp.add_argument("--dir", default=None)
    apv = sub.add_parser("approve")
    apv.add_argument("slug")
    op = sub.add_parser("open")
    op.add_argument("--dry", action="store_true")
    op.add_argument("--owner-ok", action="store_true", help="사장님 스위치 — 없으면 실행 거절")
    op.add_argument("--out", default=str(ROOT / "build"))
    op.add_argument("--version", default=None)
    a = ap.parse_args(argv)
    engine = Path(a.engine)
    if a.cmd == "status":
        return cmd_status(engine)
    if a.cmd == "queue":
        return cmd_queue(engine, a.slug)
    if a.cmd == "live":
        return cmd_live(engine, a.slug, Path(a.out), a.dir)
    if a.cmd == "approve":
        return cmd_approve(engine, a.slug)
    return cmd_open(engine, a.dry, a.owner_ok, Path(a.out), a.version or _version())


if __name__ == "__main__":
    raise SystemExit(main())
