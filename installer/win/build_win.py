"""숏템 윈도 설치팩 빌드 — 실행도구 내려받기(버전·해시 고정) → Shortem 폴더 구성 → shortem.mcpb → 설치 exe(NSIS).

실행(저장소 루트에서):
    py installer/win/build_win.py --out <빌드 폴더>
      [--client <shortem_client 폴더>]   기본: installer/../shortem_client
      [--version 1.0.0]                  기본: common/tools.lock.json installer_version
      [--skip-exe]                       설치 exe 는 만들지 않음(폴더·mcpb 만)

출력: <out>/win-x64/Shortem/ (설치될 폴더 그대로) · <out>/dist/shortem-setup-win-x64-<ver>.exe · shortem.mcpb ·
      SHA256SUMS.txt · build_report.json
서명: 환경변수 SHORTEM_SIGN_PFX(+SHORTEM_SIGN_PASSWORD, SHORTEM_SIGNTOOL, SHORTEM_SIGN_TIMESTAMP) 가 있을 때만
      signtool 로 설치 exe·제거 프로그램을 서명한다. 없으면 '미서명' 이라고 출력한다.
판단 주인: 도구 버전·출처·해시 = common/tools.lock.json 하나. 이 파일은 그 값을 읽기만 한다.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001 - 콘솔이 못 바꾸면 그대로 둔다
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # installer/
LOCK = json.loads((ROOT / "common" / "tools.lock.json").read_text(encoding="utf-8"))
PLAT = "win-x64"
# 설치 폴더 맨 위에 둘 이름(이것만 exe 에 들어간다 — 시험이 남긴 _engine_test 같은 것이 섞인 사고, 10-19)
STAGE_TOP = {"app_version.json", "claude-plugin", "engine", "models", "packs", "postinstall.js", "server",
             "shortem.mcpb", "tools", "설치안내.html", "시작.template.md"}


def log(msg: str) -> None:
    print(f"[build_win] {msg}", flush=True)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_b64(p: Path) -> str:
    h = hashlib.md5()  # noqa: S324 - GCS 가 주는 검증값이 md5 라 대조용으로만 쓴다
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()


def download(name: str, spec: dict, dl_root: Path) -> Path:
    """내려받고 lock 의 sha256 / md5 / size 로 대조. 이미 있고 맞으면 재사용."""
    url = spec["url"]
    fname = url.rsplit("/", 1)[-1].replace("%2B", "+")
    d = dl_root / name
    d.mkdir(parents=True, exist_ok=True)
    dst = d / fname

    def ok(p: Path) -> bool:
        if not p.exists():
            return False
        if spec.get("size") and p.stat().st_size != spec["size"]:
            return False
        if spec.get("sha256") and sha256_file(p) != spec["sha256"]:
            return False
        if spec.get("md5_b64") and md5_b64(p) != spec["md5_b64"]:
            return False
        return True

    if ok(dst):
        log(f"{name}: 받아 둔 파일 재사용 ({dst.stat().st_size/1e6:.1f}MB)")
        return dst
    for attempt in range(1, 4):
        tmp = dst.with_suffix(dst.suffix + ".part")
        try:
            log(f"{name}: 내려받는 중 {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "shortem-build/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(dst)
        except Exception as e:  # noqa: BLE001
            log(f"{name}: 실패 {attempt}/3 — {e}")
            time.sleep(3 * attempt)
            continue
        if ok(dst):
            log(f"{name}: 검증 통과 ({dst.stat().st_size/1e6:.1f}MB)")
            return dst
        got = sha256_file(dst)
        dst.unlink()
        raise SystemExit(f"[build_win] {name}: 검증 실패 — 내려받은 sha256 {got} 이 고정값과 다릅니다. 중단합니다.")
    raise SystemExit(f"[build_win] {name}: 3번 다 내려받기 실패")


def fresh(p: Path) -> Path:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    return p


def safe_extract_zip(zp: Path, dst: Path) -> None:
    root = dst.resolve()
    with zipfile.ZipFile(zp) as z:
        for m in z.infolist():
            target = (dst / m.filename).resolve()
            if not str(target).startswith(str(root)):
                raise SystemExit(f"[build_win] 압축 안 경로가 밖을 가리킴: {m.filename}")
        z.extractall(dst)


def safe_extract_tar(tp: Path, dst: Path) -> None:
    with tarfile.open(tp) as t:
        t.extractall(dst, filter="data")


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    return subprocess.run([str(c) for c in cmd], **kw)


# 고객 PC 에 필요 없는 파이썬 부분(시험 묶음·GUI·설치 도구·바이트코드 캐시). 지우면 용량이 줄고
# NSIS 의 260자 경로 한계에 걸리던 깊은 경로(numpy/_core/tests/__pycache__/…)도 사라진다.
PY_DROP_DIRS = {"__pycache__", "tests", "test", "idlelib", "tkinter", "turtledemo", "ensurepip", "tcl", "pip"}
PY_DROP_TOP = {"Scripts"}


def slim_python(pyroot: Path) -> None:
    before = sum(p.stat().st_size for p in pyroot.rglob("*") if p.is_file())
    for p in sorted(pyroot.rglob("*"), key=lambda x: -len(x.parts)):
        if p.is_dir() and p.name in PY_DROP_DIRS:
            shutil.rmtree(p, ignore_errors=True)
    for name in PY_DROP_TOP:
        shutil.rmtree(pyroot / name, ignore_errors=True)
    for p in pyroot.glob("Lib/site-packages/pip-*.dist-info"):
        shutil.rmtree(p, ignore_errors=True)
    after = sum(p.stat().st_size for p in pyroot.rglob("*") if p.is_file())
    log(f"python 정리: {before/1e6:.1f}MB → {after/1e6:.1f}MB")


def longest_path(stage: Path) -> tuple[int, str]:
    best = (0, "")
    for p in stage.rglob("*"):
        rel = p.relative_to(stage).as_posix()
        if len(rel) > best[0]:
            best = (len(rel), rel)
    return best


def build_tools(out: Path, stage: Path, report: dict) -> dict:
    spec = LOCK[PLAT]
    dl, ex = out / "downloads", out / "extract"
    tools = stage / "tools"
    fresh(tools)
    info: dict = {}
    srcs: dict = {}

    # node — node.exe 만(npm 은 고객 PC 에 필요 없다)
    z = download("node", spec["node"], dl)
    srcs["node"] = z
    e = fresh(ex / "node")
    safe_extract_zip(z, e)
    src = next(e.iterdir())
    (tools / "node").mkdir()
    shutil.copy2(src / "node.exe", tools / "node" / "node.exe")
    shutil.copy2(src / "LICENSE", tools / "node" / "LICENSE")
    info["node"] = {"version": spec["node"]["version"], "exe": "tools/node/node.exe"}

    # chrome-headless-shell
    z = download("chrome-headless-shell", spec["chrome-headless-shell"], dl)
    srcs["chrome-headless-shell"] = z
    e = fresh(ex / "chrome-headless-shell")
    safe_extract_zip(z, e)
    shutil.copytree(next(e.iterdir()), tools / "chrome-headless-shell")
    info["chrome-headless-shell"] = {"version": spec["chrome-headless-shell"]["version"],
                                     "exe": "tools/chrome-headless-shell/chrome-headless-shell.exe"}

    # ffmpeg + ffprobe (gyan essentials — libass 포함)
    z = download("ffmpeg", spec["ffmpeg"], dl)
    srcs["ffmpeg"] = z
    e = fresh(ex / "ffmpeg")
    safe_extract_zip(z, e)
    src = next(e.iterdir())
    (tools / "ffmpeg").mkdir()
    for f in ("ffmpeg.exe", "ffprobe.exe"):
        shutil.copy2(src / "bin" / f, tools / "ffmpeg" / f)
    shutil.copy2(src / "LICENSE", tools / "ffmpeg" / "LICENSE")
    info["ffmpeg"] = {"version": spec["ffmpeg"]["version"], "exe": "tools/ffmpeg/ffmpeg.exe",
                      "ffprobe": "tools/ffmpeg/ffprobe.exe"}

    # python(standalone) + Pillow·numpy
    t = download("python", spec["python"], dl)
    srcs["python"] = t
    e = fresh(ex / "python")
    safe_extract_tar(t, e)
    shutil.copytree(e / "python", tools / "python")
    py = tools / "python" / "python.exe"
    # 엔진 패키지 목록(Pillow·numpy 포함 상위 집합 — 관제 234 5판). 없으면 예전처럼 Pillow·numpy 만.
    req = ROOT / "common" / "requirements-engine-py312-win.txt"
    if not req.exists():
        req = ROOT / "common" / "requirements-py312.txt"
    log(f"python: {req.name} 설치(해시 고정)")
    r = run([py, "-I", "-m", "pip", "install", "--no-cache-dir", "--disable-pip-version-check",
             "--no-warn-script-location", "--no-compile", "--only-binary=:all:", "--require-hashes", "-r", req], cwd=out)
    if r.returncode != 0:
        raise SystemExit(f"[build_win] pip 실패:\n{r.stdout}\n{r.stderr}")
    slim_python(tools / "python")
    info["python"] = {"version": spec["python"]["version"], "exe": "tools/python/python.exe"}

    # yt-dlp
    f = download("yt-dlp", spec["yt-dlp"], dl)
    srcs["yt-dlp"] = f
    (tools / "yt-dlp").mkdir()
    shutil.copy2(f, tools / "yt-dlp" / "yt-dlp.exe")
    info["yt-dlp"] = {"version": spec["yt-dlp"]["version"], "exe": "tools/yt-dlp/yt-dlp.exe"}

    for k, v in info.items():
        v["source_url"] = spec[k]["url"]
        v["source_sha256"] = sha256_file(srcs[k])
    report["downloads"] = {k: {"url": v["source_url"], "sha256": v["source_sha256"]} for k, v in info.items()}
    return info


def probe_versions(stage: Path, info: dict) -> dict:
    """설치될 바이너리를 실제로 돌려 버전·ass 필터를 잰다(빌드 쪽 1차 확인)."""
    t = stage
    got = {}
    got["node"] = run([t / info["node"]["exe"], "-v"]).stdout.strip()
    got["chrome-headless-shell"] = run([t / info["chrome-headless-shell"]["exe"], "--version"]).stdout.strip()
    got["ffmpeg"] = run([t / info["ffmpeg"]["exe"], "-hide_banner", "-version"]).stdout.splitlines()[0]
    filters = run([t / info["ffmpeg"]["exe"], "-hide_banner", "-filters"]).stdout
    got["ffmpeg_ass_filter"] = " ass " in filters
    r = run([t / info["python"]["exe"], "-I", "-c",
             "import sys,PIL,numpy,cv2,faster_whisper,yt_dlp,requests,dotenv;from google import genai;"
             "print(sys.version.split()[0],PIL.__version__,numpy.__version__,cv2.__version__,faster_whisper.__version__)"], cwd=t)
    got["python"] = r.stdout.strip() or r.stderr.strip()
    got["yt-dlp"] = run([t / info["yt-dlp"]["exe"], "--version"]).stdout.strip()
    if not got["ffmpeg_ass_filter"]:
        raise SystemExit("[build_win] ffmpeg 에 ass 필터가 없습니다 — 자막 굽기가 안 되는 빌드라 중단합니다.")
    return got


def build_server(stage: Path, client: Path, report: dict) -> None:
    srv = stage / "server"
    if srv.exists():
        shutil.rmtree(srv)
    for p in ("package.json", "package-lock.json"):
        (stage / p).unlink(missing_ok=True)
    if (stage / "node_modules").exists():
        shutil.rmtree(stage / "node_modules")
    entry = client / "server" / "index.js"
    if not entry.exists():
        log(f"주의: {entry} 없음 → 자리표시 서버로 빌드합니다(조율자가 서버 완성 뒤 다시 빌드)")
        srv.mkdir()
        shutil.copy2(ROOT / "common" / "placeholder_server" / "index.js", srv / "index.js")
        report["server"] = {"placeholder": True, "client": str(client)}
        return
    ignore = shutil.ignore_patterns("node_modules", ".git", "test", "tests", "__tests__", "*.test.js", "*.log", ".env*")
    shutil.copytree(client / "server", srv, ignore=ignore)
    # package.json 이 server 안에 있으면 거기, 아니면 shortem_client 루트 것을 설치 폴더 루트에 둔다(위로 올라가며 찾는다)
    if (client / "server" / "package.json").exists():
        pkg_dir, dst = client / "server", srv
    elif (client / "package.json").exists():
        pkg_dir, dst = client, stage
        shutil.copy2(client / "package.json", stage / "package.json")
        if (client / "package-lock.json").exists():
            shutil.copy2(client / "package-lock.json", stage / "package-lock.json")
    else:
        pkg_dir, dst = None, None
    deps = None
    if dst is not None:
        npm = shutil.which("npm")
        if not npm:
            raise SystemExit("[build_win] npm 이 없어 서버 의존성을 설치할 수 없습니다")
        has_lock = (dst / "package-lock.json").exists()
        cmd = [npm, "ci" if has_lock else "install", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"]
        env = dict(os.environ, PUPPETEER_SKIP_DOWNLOAD="1", PUPPETEER_SKIP_CHROMIUM_DOWNLOAD="1")
        log(f"서버 의존성: {' '.join(cmd[1:])} ({dst})")
        r = run(cmd, cwd=dst, env=env)
        if r.returncode != 0:
            raise SystemExit(f"[build_win] npm 실패:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
        deps = "npm ci" if has_lock else "npm install(락 파일 없음)"
        # 실행에 안 쓰는 소스맵·타입 선언은 뺀다(용량·경로 길이)
        dropped = 0
        for pat in ("*.map", "*.d.ts", "*.d.mts", "*.d.cts"):
            for f in (dst / "node_modules").rglob(pat):
                if f.is_file():
                    f.unlink()
                    dropped += 1
        log(f"서버 node_modules 정리: 소스맵·타입 선언 {dropped}개 제거")
    files = sum(1 for _ in srv.rglob("*") if _.is_file())
    report["server"] = {"placeholder": False, "client": str(client), "files": files, "deps": deps,
                        "package_dir": str(pkg_dir) if pkg_dir else None}


PUPPETEER_SHIM = """// 엔진 렌더러(tools/render_scene_style.js)의 require('puppeteer') → 설치본 크롬(chrome-headless-shell)으로 띄우는 얇은 연결(관제 234).
//   puppeteer 본체(크롬 내려받기 포함)를 싣지 않고 서버의 puppeteer-core 를 쓴다(NODE_PATH = 설치/server/node_modules).
const core = require('puppeteer-core');
const shim = Object.create(core);
shim.launch = (o = {}) => core.launch({ executablePath: process.env.PUPPETEER_EXECUTABLE_PATH, ...o });
module.exports = shim;
module.exports.default = shim;
"""


def build_engine(stage: Path, engine: Path, report: dict) -> None:
    """엔진 묶음(만들기 전용 — engine_bundle 검사 통과분) + 받아쓰기 모델 + 렌더러 연결. 프리셋(channel/)은 넣지 않는다(편마다 빌린다)."""
    sys.path.insert(0, str(ROOT.parent / "tools" / "claude_portal"))
    import engine_bundle as EB
    if not (engine / "tools" / "calcopy" / "make.py").exists():
        raise SystemExit(f"[build_win] 엔진 폴더가 아닙니다: {engine}")
    dst = stage / "engine"
    man = EB.build(engine, ROOT / "common" / "engine_traces", dst)
    bad = EB.check(dst)
    if bad:
        raise SystemExit("[build_win] 엔진 묶음 검사 빨강 — " + " / ".join(bad[:5]))
    shim = dst / "node_modules" / "puppeteer"
    shim.mkdir(parents=True, exist_ok=True)
    (shim / "index.js").write_text(PUPPETEER_SHIM, encoding="utf-8")
    (shim / "package.json").write_text('{"name":"puppeteer","version":"0.0.0-shortem","main":"index.js"}' + chr(10), encoding="utf-8")
    # 받아쓰기 모델(faster-whisper small, CT2) — 첫 설치에 다 깔려 있어야 한다(사장님 10-19). 엔진은 SHORTEM_WHISPER_DIR/<이름>
    src = os.environ.get("SHORTEM_WHISPER_SRC") or next(iter(sorted((Path.home() / ".cache" / "huggingface" / "hub" /
                                                                       "models--Systran--faster-whisper-small" / "snapshots").glob("*"))), None)
    if not src or not (Path(src) / "model.bin").exists():
        raise SystemExit("[build_win] 받아쓰기 모델(faster-whisper-small)이 없습니다 — SHORTEM_WHISPER_SRC 로 폴더를 주세요")
    wd = stage / "models" / "whisper" / "small"
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        shutil.copy2(Path(src) / name, wd / name)          # 캐시는 링크일 수 있다 — copy2 가 실제 파일로 복사
    report["engine"] = {"files": len(man["files"]), "dropped": len(man["dropped"]), "missing": man["missing"],
                        "whisper_mb": round(sum(p.stat().st_size for p in wd.iterdir()) / 1e6, 1), "check": "통과"}
    log(f"엔진 묶음 {len(man['files'])}파일(뺀 것 {len(man['dropped'])}) · 받아쓰기 모델 {report['engine']['whisper_mb']}MB")


def build_packs(stage: Path, engine: Path, report: dict) -> None:
    """효과음 팩(숏템메이커 팩01~09) → <설치>/packs/sfx/팩NN/ + packs_manifest.json(엔진 calcopy_make._pack_assets 가 읽는 꼴).
    10-19 실측: 우리 PC 의 팩 장부가 없어 완성본 효과음이 file=None 으로 빠졌다 — 설치본은 동봉 팩을 가리키는 장부를 직접 갖는다.
    어느 칸을 시작·강조·끝에 쓰나는 엔진 preview_request.default_pack 한 곳이 정한다(여기는 파일·번호만)."""
    src = engine / "shopping_shorts" / "assets" / "sfx_packs"
    dst = stage / "packs"
    if dst.exists():
        shutil.rmtree(dst)
    man, n = [], 0
    for pk in sorted(p for p in src.iterdir() if p.is_dir()):
        for f in sorted(pk.iterdir()):
            if f.suffix.lower() not in (".wav", ".mp3"):
                continue
            n += 1
            (dst / "sfx" / pk.name).mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst / "sfx" / pk.name / f.name)
            man.append({"id": 10000 + n, "kind": "sfx", "pack": pk.name, "slot": f.stem, "file": f.name,
                        "media_path": f"scene_assets/{pk.name}/{f.name}", "title": f"{pk.name} {f.stem}"})
    (dst / "packs_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=0), encoding="utf-8")
    report["packs"] = {"sfx": len(man)}
    log(f"효과음 팩 {len(man)}개 → packs/")


def build_mcpb(out: Path, dist: Path, stage: Path, report: dict) -> Path:
    ms = fresh(out / "mcpb_stage")
    for f in ("manifest.json", "launcher.js", "icon.png"):
        shutil.copy2(ROOT / "mcpb" / f, ms / f)
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("[build_win] npx 가 없어 .mcpb 를 만들 수 없습니다")
    cli = LOCK["mcpb_cli"]
    v = run([npx, "-y", cli, "validate", ms / "manifest.json"], cwd=out)
    log(f"mcpb validate rc={v.returncode}: {(v.stdout + v.stderr).strip()[-400:]}")
    if v.returncode != 0:
        raise SystemExit("[build_win] mcpb validate 실패")
    target = dist / "shortem.mcpb"
    target.unlink(missing_ok=True)
    p = run([npx, "-y", cli, "pack", ms, target], cwd=out)
    if p.returncode != 0 or not target.exists():
        raise SystemExit(f"[build_win] mcpb pack 실패:\n{p.stdout}\n{p.stderr}")
    i = run([npx, "-y", cli, "info", target], cwd=out)
    report["mcpb"] = {"file": str(target), "bytes": target.stat().st_size, "sha256": sha256_file(target),
                      "validate": (v.stdout + v.stderr).strip()[-400:], "info": (i.stdout + i.stderr).strip()[-600:]}
    shutil.copy2(target, stage / "shortem.mcpb")
    log(f"shortem.mcpb {target.stat().st_size/1024:.1f}KB")
    return target


def build_plugin(stage: Path, report: dict) -> None:
    dst = stage / "claude-plugin"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / "plugin", dst)
    shutil.copy2(ROOT / "mcpb" / "launcher.js", dst / "shortem" / "launcher.js")
    claude = shutil.which("claude")
    res = {}
    if claude:
        for name, p in (("plugin", dst / "shortem"), ("marketplace", dst)):
            r = run([claude, "plugin", "validate", p])
            res[name] = (r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:])
    report["plugin"] = {"validate": res or "claude 없음 — 검사 생략"}


def build_code_kit(dist: Path, stage: Path, version: str, report: dict) -> Path:
    """Claude Code 용 시작 꾸러미(exe 없이, 스타터킷처럼 md 한 장 끌어다 놓기) — 플러그인 + 시작_코드.md + node.
    ★설치 전 PC 엔 node 가 없을 수 있다 → 꾸러미 플러그인은 함께 든 node 로 연결 파일을 띄운다(설치 폴더 안 플러그인은 그대로 SHORTEM_NODE)."""
    import zipfile
    kit = dist / f"shortem-claude-code-{PLAT}-{version}.zip"
    plug = stage / "claude-plugin"
    pj_rel = Path("shortem") / ".claude-plugin" / "plugin.json"
    pj = json.loads((plug / pj_rel).read_text(encoding="utf-8"))
    pj["mcpServers"]["shortem"]["command"] = "${CLAUDE_PLUGIN_ROOT}/node/node.exe"
    tmp = kit.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(plug.rglob("*")):
            rel = p.relative_to(plug)
            if p.is_file() and rel != pj_rel:
                z.write(p, ("숏템시작/claude-plugin" / rel).as_posix())
        z.writestr(("숏템시작/claude-plugin" / pj_rel).as_posix(), json.dumps(pj, ensure_ascii=False, indent=2) + "\n")
        z.write(stage / "tools" / "node" / "node.exe", "숏템시작/claude-plugin/shortem/node/node.exe")
        z.write(ROOT / "시작_코드.md", "숏템시작/시작.md")
    os.replace(tmp, kit)
    report["code_kit"] = {"file": str(kit), "mb": round(kit.stat().st_size / 1e6, 1), "sha256": sha256_file(kit)}
    log(f"Claude Code 시작 꾸러미 {report['code_kit']['mb']}MB → {kit}")
    return kit


def make_pack_zip(stage: Path, zp: Path) -> dict:
    """설치 폴더 → zip(윈도 내장 tar 가 푼다 — 한글 이름은 UTF-8 표시로). 내용은 STAGE_TOP 안의 것만."""
    import hashlib
    import zipfile
    tmp = zp.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for p in sorted(stage.rglob("*")):
            rel = p.relative_to(stage)
            if p.is_file() and rel.parts[0] in STAGE_TOP:
                z.write(p, rel.as_posix())
    os.replace(tmp, zp)
    h = hashlib.sha256()
    with open(zp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {"path": str(zp), "sha256": h.hexdigest(), "mb": round(zp.stat().st_size / 1e6, 1)}


def write_manifest(stage: Path, version: str) -> dict:
    """tools.manifest.json 은 common/write_manifest.js 한 곳이 쓴다(맥 빌드와 같은 주인). 동봉 node 로 돌린다."""
    node = stage / "tools" / "node" / "node.exe"
    r = run([node, ROOT / "common" / "write_manifest.js", "--stage", stage, "--plat", PLAT,
             "--version", version, "--lock", ROOT / "common" / "tools.lock.json"], cwd=stage.parent)
    if r.returncode != 0:
        raise SystemExit(f"[build_win] manifest 쓰기 실패:\n{r.stdout}\n{r.stderr}")
    return json.loads((stage / "tools" / "tools.manifest.json").read_text(encoding="utf-8"))


def nsis(out: Path) -> Path:
    spec = LOCK[PLAT]["nsis"]
    z = download("nsis", spec, out / "downloads")
    e = out / "extract" / "nsis"
    mk = next(e.glob("*/makensis.exe"), None) if e.exists() else None
    if not mk:
        fresh(e)
        safe_extract_zip(z, e)
        mk = next(e.glob("*/makensis.exe"))
    return mk


def short_stage(stage: Path) -> tuple[Path, Path | None]:
    ln, _ = longest_path(stage)
    if len(str(stage)) + 1 + ln < 240:
        return stage, None
    import tempfile
    j = Path(tempfile.gettempdir()) / f"shb{os.getpid()}"
    if len(str(j)) + 1 + ln >= 240:
        raise SystemExit(f"[build_win] 임시 폴더 경로도 너무 깁니다: {j}")
    r = run(["cmd", "/c", "mklink", "/J", str(j), str(stage)])
    if r.returncode != 0:
        raise SystemExit(f"[build_win] 정션 만들기 실패: {r.stdout} {r.stderr}")
    log(f"NSIS 용 짧은 경로: {j} → {stage}")
    return j, j


def sign_cmd() -> str | None:
    pfx = os.environ.get("SHORTEM_SIGN_PFX")
    if not pfx:
        return None
    tool = os.environ.get("SHORTEM_SIGNTOOL", "signtool")
    ts = os.environ.get("SHORTEM_SIGN_TIMESTAMP", "http://timestamp.digicert.com")
    pw = os.environ.get("SHORTEM_SIGN_PASSWORD", "")
    pw_part = f' /p "{pw}"' if pw else ""
    return f'"{tool}" sign /fd SHA256 /f "{pfx}"{pw_part} /tr {ts} /td SHA256 "%1"'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "build"))
    ap.add_argument("--client", default=str(ROOT.parent / "shortem_client"))
    ap.add_argument("--engine", default=str(ROOT.parent.parent / "칼카피숏템엔진"), help="엔진 트랙 폴더(엔진 묶음 원본)")
    ap.add_argument("--version", default=LOCK["installer_version"])
    ap.add_argument("--skip-exe", action="store_true")
    ap.add_argument("--skip-zip", action="store_true")
    a = ap.parse_args()

    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    dist = out / "dist"
    dist.mkdir(exist_ok=True)
    stage = out / PLAT / "Shortem"
    stage.mkdir(parents=True, exist_ok=True)
    report: dict = {"version": a.version, "started": datetime.now().isoformat(timespec="seconds")}
    t0 = time.time()

    info = build_tools(out, stage, report)
    report["probe"] = probe_versions(stage, info)
    log(f"버전 실측: {json.dumps(report['probe'], ensure_ascii=False)}")
    build_server(stage, Path(a.client).resolve(), report)
    build_engine(stage, Path(a.engine).resolve(), report)
    build_packs(stage, Path(a.engine).resolve(), report)
    shutil.copy2(ROOT / "common" / "postinstall.js", stage / "postinstall.js")
    shutil.copy2(ROOT / "시작.md", stage / "시작.template.md")
    shutil.copy2(ROOT / "guide" / "설치안내.html", stage / "설치안내.html")
    build_plugin(stage, report)
    build_mcpb(out, dist, stage, report)
    build_code_kit(dist, stage, a.version, report)
    (stage / "app_version.json").write_text(json.dumps({"version": a.version}), encoding="utf-8")   # 켤 때 자동 업데이트가 비교하는 판(관제 234)
    # 설치 폴더는 다시 빌드할 때 통째로 비우지 않는다 → 정한 이름 밖(시험 파일 등)은 exe 에 넣기 전에 걷어낸다
    extra = sorted(p.name for p in stage.iterdir() if p.name not in STAGE_TOP)
    for name in extra:
        p = stage / name
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    report["stage_removed"] = extra
    if extra:
        log(f"설치 폴더에서 걷어낸 것(정한 이름 밖): {extra}")
    man = write_manifest(stage, a.version)
    report["manifest_files"] = len(man["files"])
    stage_bytes = sum(p.stat().st_size for p in stage.rglob("*") if p.is_file())
    report["stage_mb"] = round(stage_bytes / 1e6, 1)
    log(f"설치 폴더 {report['stage_mb']}MB · 바이너리 {len(man['files'])}개 sha 기록")
    ln, lp = longest_path(stage)
    report["longest_rel_path"] = {"chars": ln, "path": lp}
    log(f"가장 긴 상대 경로 {ln}자: {lp}")
    if ln > 160:
        raise SystemExit("[build_win] 설치 폴더 안 경로가 160자를 넘습니다 — 고객 PC(MAX_PATH 260)에서 깨질 수 있어 중단합니다.")
    report["stage_path_chars"] = len(str(stage))

    # exe 없이 까는 묶음(사장님 10-20 "인증서 없이 스타터킷처럼") — 연결 파일(launcher.js installPack)이 받아 푼다.
    #   설치 폴더 통째 = exe 와 같은 내용. 서버에 올리기: tools/claude_portal/publish_update.py --install
    if not a.skip_zip:
        zp = dist / f"shortem-{PLAT}-{a.version}.zip"
        log("설치 묶음 zip 만드는 중(exe 없이 까는 길)")
        report["zip"] = make_pack_zip(stage, zp)
        log(f"설치 묶음 {report['zip']['mb']}MB → {zp}")

    if not a.skip_exe:
        mk = nsis(out)
        exe = dist / f"shortem-setup-win-x64-{a.version}.exe"
        exe.unlink(missing_ok=True)
        # NSIS 는 260자 넘는 경로를 못 읽는다 → 빌드 폴더가 길면 짧은 임시 연결(정션)을 거쳐 읽힌다
        nsis_stage, junction = short_stage(stage)
        defines = [f"/DSTAGE={nsis_stage}", f"/DOUTFILE={exe}", f"/DVERSION={a.version}", f"/DVERSION4={a.version}.0"]
        sc = sign_cmd()
        if sc:
            defines.append(f"/DSIGN_CMD={sc}")
        log("설치 exe 만드는 중(NSIS, LZMA solid — 몇 분 걸린다)")
        try:
            r = run([mk, "/V2", "/INPUTCHARSET", "UTF8", *defines, HERE / "shortem.nsi"])
        finally:
            if junction:
                os.rmdir(junction)  # 정션만 지운다(대상 폴더는 그대로)
        if r.returncode != 0 or not exe.exists():
            raise SystemExit(f"[build_win] makensis 실패:\n{r.stdout[-4000:]}\n{r.stderr[-2000:]}")
        report["exe"] = {"file": str(exe), "bytes": exe.stat().st_size, "mb": round(exe.stat().st_size / 1e6, 1),
                         "sha256": sha256_file(exe), "signed": bool(sc)}
        report["nsis"] = {"makensis": str(mk), "version": LOCK[PLAT]["nsis"]["version"]}
        log(f"설치 exe {report['exe']['mb']}MB → {exe}")
        if sc:
            log("코드서명: SHORTEM_SIGN_PFX 로 서명함(설치 exe·제거 프로그램)")
        else:
            log("코드서명: 미서명 — 인증서 없음(SHORTEM_SIGN_PFX 를 주면 signtool 로 서명). SmartScreen 경고가 뜬다.")

    sums = []
    for p in sorted(dist.glob("*")):
        if p.is_file() and p.suffix in (".exe", ".mcpb"):
            sums.append(f"{sha256_file(p)}  {p.name}")
    (dist / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    report["seconds"] = round(time.time() - t0, 1)
    (dist / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"끝 ({report['seconds']}초). 보고서: {dist / 'build_report.json'}")


if __name__ == "__main__":
    main()
