"""맥 엔진 파이썬 부품 목록 만들기(관제 328) — 윈도 목록(requirements-engine-py312-win.txt)과 **같은 버전**을
맥 애플칩(arm64)·인텔(x86_64) 둘 다 실제로 받아 보고, 받은 wheel 의 sha256 을 한 파일에 적는다.

  py tools/claude_portal/mac_requirements.py            → installer/common/requirements-engine-py312-mac.txt
  py tools/claude_portal/mac_requirements.py --check    → 받기만 해 보고 파일은 안 쓴다

판단 주인: 어떤 버전인가 = 윈도 목록(같은 엔진이 같은 부품으로 돌아야 한다). 이 도구는 맥 wheel 이 있는지와 그 해시만 더한다.
  예외는 OVERRIDE 한 곳 — 그 판에 그 칩 wheel 이 아예 없을 때만(근거 = PyPI 파일 목록) 마지막으로 나온 판으로 내린다.
  칩마다 판이 다르면 줄 끝에 ; platform_machine == "arm64" 표시를 붙여 한 파일에 둔다.
결과물 검사: 두 칩 모두 받기가 실패 0 이어야 파일을 쓴다. 맥에 없는 의존성이 생기면 pip 가 여기서 알려 준다.
설치 쪽: installer/install.sh 가 이 파일을 --require-hashes 로 깐다.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WIN_REQ = ROOT / "installer" / "common" / "requirements-engine-py312-win.txt"
MAC_REQ = ROOT / "installer" / "common" / "requirements-engine-py312-mac.txt"
U2 = ["macosx_10_9_universal2", "macosx_10_13_universal2", "macosx_11_0_universal2"]
PLATS = {
    "arm64": ["macosx_11_0_arm64", "macosx_12_0_arm64", "macosx_13_0_arm64", "macosx_14_0_arm64", "macosx_15_0_arm64"] + U2,
    "x86_64": ["macosx_10_9_x86_64", "macosx_10_15_x86_64", "macosx_11_0_x86_64", "macosx_12_0_x86_64", "macosx_13_0_x86_64", "macosx_14_0_x86_64", "macosx_15_0_x86_64"] + U2,
}
# 칩별 예외 판(그 판에 그 칩 wheel 이 없을 때만). 근거를 같이 적는다.
OVERRIDE = {
    # PyPI 파일 목록 전수 조사(2026-11-05, 55개 중 인텔 없음 2개): 그 판 맥 wheel 이 arm64 뿐이라 마지막 인텔 판으로
    "x86_64": {"cryptography": "48.0.1", "onnxruntime": "1.23.2"},
}
PIN = re.compile(r"(?m)^([A-Za-z0-9_.\-]+)==([^\s\\]+)")


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pins(arch: str) -> list[tuple[str, str]]:
    ov = {norm(k): v for k, v in OVERRIDE.get(arch, {}).items()}
    return [(n, ov.get(norm(n), v)) for n, v in PIN.findall(WIN_REQ.read_text(encoding="utf-8"))]


def download(arch: str, req: Path, dest: Path) -> list[Path]:
    cmd = [sys.executable, "-m", "pip", "download", "--quiet", "--disable-pip-version-check", "--only-binary=:all:",
           "--python-version", "3.12", "--implementation", "cp", "-d", str(dest), "-r", str(req)]
    for p in PLATS[arch]:
        cmd += ["--platform", p]
    r = subprocess.run(cmd, text=True, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"[{arch}] 받기 실패:\n{r.stderr[-3000:]}")
    return sorted(dest.glob("*.whl"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    # got[arch][패키지] = (판, {sha256})
    got: dict[str, dict[str, tuple[str, set]]] = {}
    with tempfile.TemporaryDirectory() as td:
        for arch in PLATS:
            req = Path(td) / f"pins-{arch}.txt"
            req.write_text("".join(f"{n}=={v}\n" for n, v in pins(arch)), encoding="utf-8")
            got[arch] = {}
            wheels = download(arch, req, Path(td) / arch)
            for w in wheels:
                name, ver = w.name.split("-")[0], w.name.split("-")[1]
                got[arch].setdefault(norm(name), (ver, set()))[1].add(hashlib.sha256(w.read_bytes()).hexdigest())
            mins = [tuple(int(x) for x in m.groups()) for w in wheels for m in [re.search(r"macosx_(\d+)_(\d+)_", w.name)] if m]
            need = max(mins) if mins else (0, 0)
            print(f"{arch}: 최소 macOS {need[0]}.{need[1]} (가장 높은 wheel 기준)")
            want = {norm(n) for n, _ in pins(arch)}
            print(f"{arch}: wheel {len(wheels)}개 · 맥에서만 붙는 의존성 {sorted(set(got[arch]) - want) or '없음'}")
    if a.check:
        return 0
    lines = ["# 숏템 맥 엔진 패키지(애플칩 arm64 · 인텔 x86_64 · 파이썬 3.12) — installer/install.sh 가 pip --require-hashes 로 깐다(관제 328).",
             "# 버전 = requirements-engine-py312-win.txt 와 같다(칩별 예외는 mac_requirements.OVERRIDE). 만든 법: py tools/claude_portal/mac_requirements.py", ""]
    for key in sorted(set(got["arm64"]) | set(got["x86_64"])):
        a64, x64 = got["arm64"].get(key), got["x86_64"].get(key)
        if a64 and x64 and a64[0] == x64[0]:
            groups = [(a64[0], a64[1] | x64[1], "")]
        else:
            groups = [(v[0], v[1], f' ; platform_machine == "{arch}"') for arch, v in (("arm64", a64), ("x86_64", x64)) if v]
        for ver, hs, marker in groups:
            hs = sorted(hs)
            lines.append(f"{key}=={ver}{marker} \\")
            lines += [f"    --hash=sha256:{h}" + (" \\" if i < len(hs) - 1 else "") for i, h in enumerate(hs)]
    MAC_REQ.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"썼다: {MAC_REQ.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
