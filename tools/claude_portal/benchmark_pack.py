"""고급반 벤치마킹 묶음(관제 304, 사장님 11-02 "기본형에는 채널 카피 노하우 엔진만 빼고 다 넣는다. 고급형은 그 노하우를 담아준다").

  py tools/claude_portal/benchmark_pack.py merge-trace --root <엔진 폴더> --from <추적 폴더>…   # 추적 → installer/common/engine_traces/benchmark/
  py tools/claude_portal/benchmark_pack.py build --engine <엔진 폴더> --out <폴더>              # <폴더>/benchmark_pack.zip + 파일 목록
  py tools/claude_portal/benchmark_pack.py check <zip 또는 폴더>                                 # 금지 파일·금지 글자가 하나라도 있으면 rc=1

설치본에 넣지 않고 서버가 고급반 이상에게만 빌려준다(claude_portal.benchmark_rent) — 프리셋과 같은 꼴, 쓰고 나면 회원 PC 에서 지운다.
회원 PC 는 엔진 폴더에 **없는 파일만** 풀고 끝나면 그것만 지운다(shortem_client/server/benchmark.js).

판단 주인:
  · 묶음 목록 = 실제로 돌린 추적(BENCH_TRACES) + 입구 맨 위 import — 짐작 목록 금지(engine_bundle 과 같은 방식).
  · 무엇이 금지인가 = engine_bundle.forbidden · 금지 글자 = engine_bundle.SECRETS 그대로(두 벌 금지). 여기는 '고급반에게 푸는 것(RELEASED)'만 적는다.
    서버 키·서버 주소가 든 파일(gemini_server·gemini_keys·_server_access·pull_pool_keys·server_ai)은 RELEASED 에 없으니 여전히 금지다.
  · channel_find*.py 는 일부러 안 푼다 — SSH 주소가 글자로 들어 있고(SECRETS 빨강), 회원은 채널 주소를 직접 주므로 찾기가 필요 없다(yt_channel 로 충분).
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_bundle as EB  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BENCH_TRACES = ROOT / "installer" / "common" / "engine_traces" / "benchmark"
# 2판(관제 319): 실행기 bm_* 명령이 함수 안에서 부르는 agy·agy_check·preset_brief 도 입구로 — 추적이 안 본 갈래가 빠지지 않게(preset_brief 는 기본 묶음에 없다)
ENTRY = ("tools/calcopy/engine/bench_member.py", "tools/calcopy/engine/preset_brief.py", "tools/calcopy/engine/agy.py", "tools/calcopy/engine/agy_check.py")
# 고급반에게 푸는 파일 — engine_bundle.FORBIDDEN 에 걸려 있던 것 중 추적에 잡힌 만드는 기술만.
RELEASED = ("tools/calcopy/engine/bench_member.py", "tools/calcopy/engine/analyze.py", "tools/calcopy/engine/to_frame.py", "tools/calcopy/engine/to_frame_multi.py",
            "tools/calcopy/engine/preset_save.py", "tools/calcopy/engine/fontmatch.py",
            "tools/calcopy/engine/agy.py", "tools/calcopy/engine/agy_check.py", "tools/calcopy/engine/preset_brief.py")
# hybrid/flow_bench.py(서버 지시서)·hybrid/jev_gate.py(Jev 판단) 는 서버 전용 — 위 목록에 절대 넣지 않는다(hybrid/* 금지 규칙이 막는다)
# 추적에 잡혀도 묶음에 안 넣는 것 — 설치본에 이미 있거나(글꼴·화면 파일) 추적 도구 자신. 회원 PC 는 설치본 것을 그대로 쓴다.
SKIP = ("shopping_shorts/static/fonts/*", "shopping_shorts/channel_presets/*", "out/*", "tools/claude_portal/*")
ZIP_NAME = "benchmark_pack.zip"
_MODEL_CACHE = ("__pycache__",)


def blocked(rel: str) -> str | None:
    """이 파일이 고급반 묶음에 있으면 안 되는 이유. 판단은 engine_bundle.forbidden 한 곳 — RELEASED 만 예외."""
    return None if rel in RELEASED else EB.forbidden(rel)


def merge_trace(root: Path, sources: list[Path]) -> Path:
    """추적 폴더들 → 한 파일(저장소에 커밋하는 근거). 경로는 root 기준 상대(추적기가 이미 그렇게 적는다)."""
    mods, opened, third = set(), set(), set()
    for s in sources:
        for f in s.glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            mods |= set(d.get("modules") or [])
            opened |= {x for x in d.get("opened") or [] if not any(c in x for c in _MODEL_CACHE)}
            third |= set(d.get("third_party") or [])
    BENCH_TRACES.mkdir(parents=True, exist_ok=True)
    out = BENCH_TRACES / "benchmark_trace.json"
    out.write_text(json.dumps({"root_note": "실제 실행 추적(관제 304)", "modules": sorted(mods), "opened": sorted(opened), "third_party": sorted(third)},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def wanted(engine: Path) -> list[str]:
    mods, data = EB.traced(BENCH_TRACES, engine)
    data = {d for d in data if (engine / d).is_file()}        # yt-dlp 가 찾아보기만 한 설정 파일 등 — 없는 것은 쓴 것이 아니다
    keep = mods | data | EB.top_imports(engine, ENTRY)
    return sorted(r for r in keep if not any(fnmatch.fnmatch(r, s) for s in SKIP))


def build(engine: Path, out: Path) -> dict:
    kept, dropped, missing = [], [], []
    for rel in wanted(engine):
        why = blocked(rel)
        if why:
            dropped.append({"file": rel, "rule": why})
        elif not (engine / rel).is_file():
            missing.append(rel)
        else:
            kept.append(rel)
    if missing:
        raise SystemExit(f"[benchmark_pack] 추적에는 있는데 엔진에 없는 파일: {missing}")
    bad = [f"{r} /{s}/" for r in kept for s in EB.SECRETS if re.search(s, (engine / r).read_text(encoding="utf-8", errors="ignore"))]
    if bad:
        raise SystemExit("[benchmark_pack] 금지 글자가 든 파일 — 묶지 않는다:\n  " + "\n  ".join(bad))
    out.mkdir(parents=True, exist_ok=True)
    z = out / ZIP_NAME
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in kept:
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))      # 같은 코드 = 같은 zip(시각이 안 들어가게)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, (engine / rel).read_bytes())
    man = {"files": {r: hashlib.sha256((engine / r).read_bytes()).hexdigest() for r in kept}, "dropped": dropped,
           "size": z.stat().st_size, "sha256": hashlib.sha256(z.read_bytes()).hexdigest()}
    (out / "benchmark_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def _items(target: Path):
    if target.is_file():
        with zipfile.ZipFile(target) as zf:
            for n in zf.namelist():
                if not n.endswith("/"):
                    yield n, zf.read(n)
        return
    for p in target.rglob("*"):
        if p.is_file():
            yield p.relative_to(target).as_posix(), p.read_bytes()


def check(target: Path) -> list[str]:
    """금지 파일·금지 글자 — 묶음(zip) 또는 풀어 놓은 폴더. 글자 판단 = engine_bundle.SECRETS."""
    bad = []
    n = 0
    for rel, data in _items(target):
        if rel in ("benchmark_manifest.json", ZIP_NAME):
            continue
        n += 1
        why = blocked(rel)
        if why:
            bad.append(f"금지 파일 {rel} ({why})")
            continue
        t = data.decode("utf-8", "ignore")
        bad += [f"금지 글자 /{s}/ in {rel}" for s in EB.SECRETS if re.search(s, t)]
    if not n:
        bad.append("묶음이 비었다")
    return bad


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if argv[:1] == ["check"]:
        bad = check(Path(argv[1]))
        for b in bad:
            print("★", b)
        print(f"검사: 금지 {len(bad)}건" + (" — 빨강" if bad else " — 통과"))
        return 1 if bad else 0
    if argv[:1] == ["build"]:
        a = dict(zip(argv[1::2], argv[2::2]))
        man = build(Path(a["--engine"]), Path(a["--out"]))
        print(f"묶음: 파일 {len(man['files'])} · 뺀 것 {len(man['dropped'])} · {man['size'] // 1024}KB · sha256 {man['sha256'][:12]}")
        for d in man["dropped"]:
            print("  뺌", d["file"], "←", d["rule"])
        return 0
    if argv[:1] == ["merge-trace"]:
        i = argv.index("--from")
        root = Path(argv[argv.index("--root") + 1])
        print(merge_trace(root, [Path(x) for x in argv[i + 1:] if not x.startswith("--")]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
