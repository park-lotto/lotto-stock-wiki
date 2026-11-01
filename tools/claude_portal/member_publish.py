"""칼카피 판 → 회원 MCP 내보내기: '발행 대기 → 사장님 스위치' (관제 265).

  py tools/claude_portal/member_publish.py status                  # 엔진 모든 slug 의 단계·빠진 것·대기열 여부
  py tools/claude_portal/member_publish.py queue <slug>            # L2 이상만 엔진 channel/발행대기.json 에 올린다(그 외 거절)
  py tools/claude_portal/member_publish.py open --dry              # 사장님 스위치 — 대기열 판마다 꾸러미→설치본→올리기 계획만 출력
  py tools/claude_portal/member_publish.py open --owner-ok         # 실제 실행(사장님이 켤 때만 — 없으면 거절)
  (공통 --engine <엔진 트랙 폴더>, 기본 ../칼카피숏템엔진)

판단 주인(한 곳): 판 단계 = 엔진 tools/calcopy/preset_card.py build_card(slug)["done"] (level() 결과 + 보류 표시).
  여기는 그 결과를 받아 'L2 이상인가'만 본다 — 합격 조건을 다시 적지 않는다. 엔진 모듈(tools·shopping_shorts)이 이 저장소와
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
DEFAULT_ENGINE = ROOT.parent / "칼카피숏템엔진"
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
    print(f"{'slug':18} {'단계':14} {'대기열':6} 빠진 것")
    for s, d in L.items():
        print(f"{s:18} {d['level']:14} {'○' if s in queued else '-':6} {' · '.join(d['missing']) or '-'}")
    n_pub = sum(publishable(d["level"]) for d in L.values())
    print(f"총 {len(L)}판 · L2 이상 {n_pub} · 대기열 {len(queued)}")
    return 0


def cmd_queue(engine: Path, slug: str) -> int:
    L = card_levels(engine)
    if slug not in L:
        print(f"[거절] {slug}: 엔진 channel/프리셋.json 에 없는 판")
        return 2
    d = L[slug]
    if not publishable(d["level"]):
        print(f"[거절] {slug}: 단계 {d['level']} — L2 이상만 대기열에 오른다. 빠진 것: {' · '.join(d['missing']) or '-'}")
        return 2
    q = load_queue(engine)
    if any(e["slug"] == slug for e in q["queue"]):
        print(f"{slug}: 이미 대기열에 있다 ({d['level']})")
        return 0
    q["queue"].append({"slug": slug, "level": d["level"], "preset_dir": d["preset_dir"],
                       "queued_at": datetime.now().isoformat(timespec="seconds")})
    save_queue(engine, q)
    print(f"{slug}: 대기열 추가 ({d['level']}) → {QUEUE_REL}")
    return 0


def _version() -> str:
    return json.loads((ROOT / "installer/common/tools.lock.json").read_text(encoding="utf-8"))["installer_version"]


def plan(engine: Path, out: Path, version: str) -> tuple[list[list[str]], list[str]]:
    """대기열 판 → 실행할 명령 목록. 열 때 단계를 다시 재서 L2 밑으로 떨어진 판은 뺀다(사유는 skipped)."""
    L = card_levels(engine)
    py = sys.executable
    steps, skipped = [], []
    packs = out / "packs"
    for e in load_queue(engine)["queue"]:
        d = L.get(e["slug"])
        if not d or not publishable(d["level"]):
            skipped.append(f"{e['slug']}: 지금 단계 {d['level'] if d else '없음'} — 빠진 것 {' · '.join(d['missing']) if d else '-'}")
            continue
        if not d["preset_dir"]:
            skipped.append(f"{e['slug']}: 프리셋.json engine.preset_dir 없음")
            continue
        steps.append([py, "tools/claude_portal/preset_pack.py", "build", "--engine", str(engine), "--preset", d["preset_dir"], "--out", str(packs)])
    if steps:
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
    print(f"계획 ({'--dry, 실행 안 함' if dry else '실행'}) · 판 {len(steps) - 2} · 판(버전) {version}")
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
    return cmd_open(engine, a.dry, a.owner_ok, Path(a.out), a.version or _version())


if __name__ == "__main__":
    raise SystemExit(main())
