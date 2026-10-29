# -*- coding: utf-8 -*-
"""고객 경로 점검 — 회원 PC 에 실제로 가는 것(엔진 묶음 + 프리셋 꾸러미)만으로 만들기가 도는가(사장님 10-29 절대규칙 '하나의 MCP').

  PYTHONUTF8=1 py tools/claude_portal/member_check.py [--bundle <묶음 폴더>] [--preset channel/<slug>/preset/<틀> ...]
    --bundle 없으면 이 엔진으로 묶음을 새로 만든다(engine_bundle.build). --preset 없으면 line.json(hybrid) 있는 프리셋 전부.
  → 프리셋마다 ✓/✗ 와 빠진 것. 하나라도 ✗ 면 rc=1 — 발행(member_publish) 전 관문.

10-29 하루에 회원 길로 한 편씩 만들어 보고서야 찾은 구멍 9개(렌더 파일·글꼴·완성본 검사 모듈·의존의 의존·판 설정 안 빌림·
상속 판·벤치 줄판독·판 없음 SystemExit 등)를 만들기 전에 한 번에 잡는 것이 목적이다.
판정(무엇이 묶음에 들어가나 = engine_bundle, 무엇이 꾸러미에 들어가나 = preset_pack)은 다시 적지 않는다 — 그 결과물을 놓고 잴 뿐.
  ① 코드: 실행기(runner_ops)에서 시작해 함수 안 import 까지 따라간 우리 모듈이 묶음에 다 있나(서버 전용 명시 목록은 경고만)
  ② 판: 꾸러미를 묶음에 푼 상태로 styles.load(판) 가 되나 · 렌더 코드가 불러오는 순간 읽는 판(render_itssum·render_jaemi)이 되나
  ③ 자료: 판 bench 의 줄판독·효과음 실측 · 판 그림(band·logo·watermark) · 판이 쓰는 글꼴이 묶음+꾸러미에 있나
  ④ 실행: 꾸러미를 푼 묶음에서 실제로 runner_ops·render_bench·quality_gate·checks 를 불러 본다(다른 프로세스)
"""
from __future__ import annotations

import ast
import io
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.claude_portal import engine_bundle as EB, preset_pack as PP  # noqa: E402

START = ("tools/calcopy/hybrid/runner_ops.py",)
OURS = ("shopping_shorts", "tools", "pipeline")
H = "tools/calcopy/hybrid"

PROBE = r"""
import json, sys, traceback
sys.path.insert(0, '.')
out = {"import": {}, "styles": None}
for m in ("tools.calcopy.hybrid.runner_ops", "tools.calcopy.hybrid.render_bench", "tools.calcopy.hybrid.quality_gate",
          "tools.calcopy.hybrid.checks", "tools.calcopy.hybrid.render_itssum"):   # render_jaemi(옛 재미썸홈판)는 실행기에서 안 닿는다(① 사슬로 확인)
    try:
        __import__(m); out["import"][m] = "ok"
    except BaseException as e:          # SystemExit(판 없음)도 — 10-29 실측 꼴
        out["import"][m] = f"{type(e).__name__}: {str(e)[:200]}"
try:
    from tools.calcopy.hybrid import styles as ST
    st = ST.load(sys.argv[1]); out["styles"] = "ok"; out["fonts"] = sorted({str(v) for v in json.dumps(st, ensure_ascii=False).split('"') if v.lower().endswith((".ttf", ".otf"))})
except BaseException as e:
    out["styles"] = f"{type(e).__name__}: {str(e)[:200]}"
print(json.dumps(out, ensure_ascii=False))
"""


def mod_file(base: Path, name: str) -> str | None:
    q = base / Path(*name.split("."))
    for c in (q.with_suffix(".py"), q / "__init__.py"):
        if c.is_file():
            return c.relative_to(base).as_posix()
    return None


def code_closure(engine: Path, bundle: Path) -> tuple[list[str], list[str]]:
    """실행기에서 시작한 import 사슬(함수 안 포함) — (묶음에 없는 것, 서버 전용이라 일부러 뺀 것)."""
    missing, server_only, seen, todo = [], [], set(), list(START)
    while todo:
        r = todo.pop()
        if r in seen:
            continue
        seen.add(r)
        src = bundle / r if (bundle / r).is_file() else engine / r
        if not src.is_file():
            continue
        pkg = r[:-3].replace("/", ".")
        pkg = pkg if r.endswith("__init__.py") else pkg.rsplit(".", 1)[0]
        try:
            tree = ast.parse(src.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            names = []
            if isinstance(n, ast.Import):
                names = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                base = (pkg.split(".")[:len(pkg.split(".")) - (n.level - 1)] if n.level else [])
                mod = ".".join(base + ([n.module] if n.module else []))
                names = [mod] + [f"{mod}.{a.name}" for a in n.names]
            for x in names:
                if x.split(".")[0] not in OURS:
                    continue
                m = mod_file(engine, x)
                if not m or m in seen:
                    continue
                if m in EB.HAND_SERVER_ONLY or EB.forbidden(m):
                    if m not in server_only:
                        server_only.append(m)
                    continue
                if not (bundle / m).is_file():
                    if not any(x.startswith(m + " ←") for x in missing):
                        missing.append(f"{m} ← {r}")
                    continue
                todo.append(m)
    return missing, server_only


def presets(engine: Path) -> list[str]:
    out = []
    for lp in sorted(engine.glob("channel/*/preset/*/line.json")):
        try:
            if json.loads(lp.read_text(encoding="utf-8")).get("line") == "hybrid":
                out.append(lp.parent.relative_to(engine).as_posix())
        except ValueError:
            continue
    return out


def check_preset(engine: Path, bundle: Path, preset: str) -> dict:
    v = json.loads((engine / preset / "line.json").read_text(encoding="utf-8"))["version"]
    probs, fixed = [], []
    # ⓪ 판 준비 — 빈칸은 벤치 실측으로 **채우고 다시 잰다**(주인 hybrid/pan_ready, 사장님 10-29 '멈추는 게 아니라 다시 되게'). 꾸러미는 고친 판으로 묶는다
    if engine.resolve() == ROOT.resolve():
        from tools.calcopy.hybrid import pan_ready as PR
        left = PR.repair(v, log=fixed.append)
        probs += [f"판 준비 못 함: {g['what']}" for g in left]
    data, meta = PP.build(engine, preset)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    # ③ 자료 — 판 사슬(위 판이 이긴다)의 bench 자리가 꾸러미에 있나
    st, name, chain = {}, v, []
    while name and name not in chain:
        chain.append(name)
        f = engine / H / "styles" / f"{name}.json"
        if not f.is_file():
            probs.append(f"판 파일 없음(엔진): {name}")
            break
        raw = json.loads(f.read_text(encoding="utf-8"))
        st = {**raw, **st}
        name = raw.get("base")
    for n in chain + ["잇썸홈판", "재미썸홈판"]:
        if (engine / H / "styles" / f"{n}.json").is_file() and f"{H}/styles/{n}.json" not in names:
            probs.append(f"꾸러미에 판 없음: {n}")
    b = st.get("bench") or {}
    if b.get("line_reads") and not any(x.startswith(b["line_reads"].rstrip("/") + "/") for x in names):
        probs.append(f"꾸러미에 벤치 줄판독 없음: {b['line_reads']}")
    if b.get("sfx_events") and b["sfx_events"] not in names:
        probs.append(f"꾸러미에 효과음 실측 없음: {b['sfx_events']}")
    for k in ("band", "logo", "watermark"):
        fr = (st.get("frame") or {}).get(k)
        src = fr.get("src") if isinstance(fr, dict) else None
        if src and (engine / src).is_file() and src not in names and not (bundle / src).is_file():
            probs.append(f"판 그림 없음: {src}")
    # ②④ 꾸러미를 묶음에 풀고 실제로 불러 본다(회원 PC preset_rent 와 같은 자리: channel/ · hybrid/styles/)
    tmp = Path(tempfile.mkdtemp(prefix="member_check_"))
    try:
        for d in ("channel", f"{H}/styles"):
            if (bundle / d).exists():
                probs.append(f"묶음에 빌림 자리가 이미 있음: {d}(진짜 코드 막음에 걸린다)")
        zf = zipfile.ZipFile(io.BytesIO(data))
        for nm in names:
            if not (nm.startswith("channel/") or nm.startswith(f"{H}/styles/")):
                probs.append(f"꾸러미가 빌림 자리 밖에 파일을 둔다: {nm}")
                continue
            dst = bundle / nm
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(zf.read(nm))
        r = subprocess.run([sys.executable, "-c", PROBE, v], cwd=str(bundle), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600, env={**__import__("os").environ, "PYTHONUTF8": "1", "CALCOPY_CUSTOMER_MODE": "1"})
        try:
            pr = json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
        except ValueError:
            pr = {"import": {}, "styles": f"점검 실행 실패: {r.stderr[-300:]}"}
        probs += [f"불러오기 실패 {m}: {why}" for m, why in (pr.get("import") or {}).items() if why != "ok"]
        if pr.get("styles") != "ok":
            probs.append(f"판 불러오기 실패: {pr.get('styles')}")
        fonts_dir = bundle / "shopping_shorts" / "static" / "fonts"
        probs += [f"글꼴 없음: {fn}" for fn in pr.get("fonts") or [] if not (fonts_dir / Path(fn).name).is_file()]
    finally:
        for d in ("channel", f"{H}/styles"):
            shutil.rmtree(bundle / d, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
    return {"preset": preset, "version": v, "pack_files": len(names), "problems": probs, "fixed": fixed}


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    engine = ROOT
    a = {argv[i]: argv[i + 1] for i in range(0, len(argv) - 1) if argv[i].startswith("--")}
    want = [argv[i + 1] for i in range(len(argv) - 1) if argv[i] == "--preset"]
    own = not a.get("--bundle")
    bundle = Path(a["--bundle"]) if not own else Path(tempfile.mkdtemp(prefix="member_bundle_"))
    if own:
        EB.build(engine, ROOT / "installer" / "common" / "engine_traces", bundle)
    try:
        missing, server_only = code_closure(engine, bundle)
        print(f"① 코드: 실행기에서 닿는 우리 모듈 중 묶음에 없음 {len(missing)} · 서버 전용(일부러 뺌) {len(server_only)}")
        for m in missing:
            print("   ✗", m)
        rows = [check_preset(engine, bundle, p) for p in (want or presets(engine))]
        for r in rows:
            mark = "✓" if not r["problems"] else "✗"
            print(f"{mark} {r['preset']} (판 {r['version']} · 꾸러미 {r['pack_files']}개)")
            for f in r.get("fixed") or []:
                print("   ↻", f.strip(), "— 판 파일이 바뀌었다: 커밋할 것")
            for p in r["problems"]:
                print("   -", p)
        bad = bool(missing) or any(r["problems"] for r in rows)
        print("판정:", "막음 — 고치기 전 발행 금지" if bad else "통과")
        return 1 if bad else 0
    finally:
        if own:
            shutil.rmtree(bundle, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
