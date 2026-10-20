"""고객 설치팩 엔진 묶음 — '만들기 전용'만 담고, 만드는 과정·기술은 빼고, 섞였는지 검사한다(관제 234 5판, 2026-10-19 사장님
"프리셋 만드는 노하우가 자산 / 만드는 과정이나 기술들을 차단").

  py tools/claude_portal/engine_bundle.py build --engine <엔진 폴더> --traces <추적 폴더> --out <묶음 폴더>
  py tools/claude_portal/engine_bundle.py check <묶음 폴더>          # 금지 파일·금지 글자가 하나라도 있으면 rc=1

판단 주인(한 곳): FORBIDDEN(빼야 할 파일 꼴)·SECRETS(묶음에 있으면 안 되는 글자)·RENDERER_EXTRA(노드 렌더러가 여는 정적 파일).
- 목록 근거 = 실제로 돌린 추적(trace_site/sitecustomize.py 가 프로세스마다 남긴 JSON) — 짐작 목록 금지.
- channel/** (프리셋·분석 자료)는 묶음에 넣지 않는다 — 프리셋은 서버가 편마다 빌려준다(설계 '결정 추가' 2).
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

# 만드는 과정·기술 = 고객에게 안 간다. 추적에 잡혀도 넣지 않고, 묶음에 있으면 검사가 빨강.
FORBIDDEN = (
    "channel/*",                                   # 프리셋·뜯기·분석 문서 전부(서버가 편마다)
    "tools/calcopy/engine/analyze.py",            # 원본 뜯기
    "tools/calcopy/engine/to_frame*.py",          # 틀 설명서 만들기
    "tools/calcopy/engine/preset_*.py", "tools/calcopy/engine/loo_preset.py",
    "tools/calcopy/engine/channel_find*.py",      # 채널 찾기·판정
    "tools/calcopy/engine/recheck.py", "tools/calcopy/engine/fontmatch.py",   # layout1 = 완성본 대조(check 단계)가 쓰는 자 — 묶음에 둔다
    "tools/calcopy/engine/gemini_server.py", "tools/calcopy/engine/gemini_keys.py", "tools/calcopy/pull_pool_keys.py",
    "tools/calcopy/engine/_server_access.py",     # 우리 서버 SSH 정보
    "tools/calcopy/analyze*.py", "tools/calcopy/summarize*.py", "tools/calcopy/try_*.py", "tools/calcopy/check_*.py",
    "tools/calcopy/hybrid/*", "tools/calcopy/yanshot/*", "tools/calcopy/oneshot/*", "tools/calcopy/community_*.py",
    "tools/calcopy/transcribe_free.py", "tools/calcopy/*/README.md", "tools/calcopy/*.md",
    "research/*", "docs/*", "handoff/*", "wiki/*", "관제/*", "raw/*", "out/*.md",
    ".env*", "*.pem", "shopping_shorts/app.py", "shopping_shorts/claude_portal.py", "shopping_shorts/tests/*",
    # 서버 수집기(계정 돌리기·프록시 슬롯·유료 수집) — 회원 PC 받기는 회원 로그인 쿠키로 한다(media_download 는 이것들 없이 돈다, 10-19 실측)
    "shopping_shorts/channel_archive.py", "shopping_shorts/instagram_playwright.py", "shopping_shorts/apify_client.py", "shopping_shorts/store.py",
)
# 묶음 안 어디에도 있으면 안 되는 글자(서버 주소·접속 열쇠 꼴·키 이름)
#   duckdns 는 숏템 공개 주소(고객 프로그램이 라이선스 확인에 접속)라 숨길 대상이 아니다.
SECRETS = (r"3\.35\.251\.172", r"LightsailDefaultKey", r"ubuntu@", r"BEGIN (RSA |OPENSSH )?PRIVATE KEY",
           r"AIza[0-9A-Za-z_-]{30,}", r"SHORTS_GEMINI_KEY_\d+\s*=")
# 노드 렌더러(render_scene_style.js)가 file:// 로 여는 것 — 파이썬 추적에 안 잡힌다. showcase html 의 src/href 에서 더 읽는다.
RENDERER_EXTRA = ("tools/render_scene_style.js", "out/scene-style-ui-showcase.html")
# 파이썬 추적에 안 잡히는 데이터(ffmpeg·node 가 여는 것, 설정 화면만 쓰는 것) — 10-19 설치본 실측: 목소리 목록·배경음악이 빠져
#   설정 화면 목록이 죽고 완성본 배경음악이 비었다. 폴더는 그 아래 파일 전부.
DATA_EXTRA = ("shopping_shorts/assets/voice_presets.json", "shopping_shorts/assets/bgm_lib", "shopping_shorts/assets/sfx_packs",
              "shopping_shorts/calcopy_frame/my_packs.json", "shopping_shorts/static/caption-motions.js",
              "tools/calcopy/engine/warehouse_channels.json")


def data_extra(engine: Path) -> list[str]:
    out = []
    for rel in DATA_EXTRA:
        p = engine / rel
        if p.is_dir():
            out += [q.relative_to(engine).as_posix() for q in sorted(p.rglob("*")) if q.is_file()]
        elif p.is_file():
            out.append(rel)
    return out


# 만들기 경로의 입구 — 추적이 못 본 갈래(예: 나레형 렌더는 목소리 비용 때문에 시험에서 안 돌림)도 빠지지 않게,
# 이 모듈들과 그 '파일 맨 위' import 를 따라간 모듈은 늘 넣는다(함수 안 import 는 추적이 맡는다).
ENTRY = ("tools/calcopy/make.py", "shopping_shorts/calcopy_make.py", "tools/calcopy/engine/worker.py",
         "tools/calcopy/engine/worker_steps.py", "tools/calcopy/engine/remake.py", "tools/calcopy/remake_video.py",
         "tools/calcopy/narr_video.py", "tools/calcopy/engine/client_llm.py", "tools/calcopy/engine/asr_local.py",
         "tools/calcopy/engine/topic_find.py", "tools/calcopy/engine/script_engine.py", "tools/calcopy/engine/yt_channel.py",
         "shopping_shorts/scene_style.py", "tools/calcopy/preview_request.py",   # 설정 화면 미리보기·검사(관제 234)
         "shopping_shorts/media_download.py", "shopping_shorts/grab_domains.py", "shopping_shorts/frame_extract.py",   # 인스타·틱톡 등 받기(숏템메이커와 같은 주인, 관제 234)
         "shopping_shorts/instagram_parse.py", "shopping_shorts/douyin_fetch.py", "shopping_shorts/threads_parse.py",
         # 함수 안에서만 부르는 것(추적이 아직 못 본 것) — ★함수 안 import 를 통째로 따라가면 프리셋 기술·관리 도구까지 딸려 온다(10-20 시험:
         #   channel_presets·channelkit/bench·live_admin). 그래서 하나씩 적는다. 빠지면 test_engine_installed(변수 많은 프리셋)가 잡는다
         "shopping_shorts/calcopy_frame/per_video.py")


def top_imports(engine: Path, entries=ENTRY) -> set[str]:
    """입구 모듈의 모듈 맨 위 import 를 우리 패키지(shopping_shorts·tools·pipeline) 안에서 따라간 파일들."""
    import ast
    def mod_file(name):
        p = engine / Path(*name.split("."))
        for c in (p.with_suffix(".py"), p / "__init__.py"):
            if c.is_file():
                return c
        return None
    todo, seen = [engine / e for e in entries], set()
    while todo:
        f = todo.pop()
        rel = f.relative_to(engine).as_posix()
        if rel in seen or not f.is_file():
            continue
        seen.add(rel)
        tree = ast.parse(f.read_text(encoding="utf-8"))
        pkg = rel[:-3].replace("/", ".")
        pkg = pkg if f.name == "__init__.py" else pkg.rsplit(".", 1)[0]
        for n in tree.body:   # 맨 위 문장만(함수·클래스 안 import 는 제외)
            names = []
            if isinstance(n, ast.Import):
                names = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                base = (pkg.split(".")[:len(pkg.split(".")) - (n.level - 1)] if n.level else [])
                mod = ".".join(base + ([n.module] if n.module else []))
                names = [mod] + [f"{mod}.{a.name}" for a in n.names]
            for x in names:
                if x.split(".")[0] in ("shopping_shorts", "tools", "pipeline"):
                    m = mod_file(x)
                    if m:
                        todo.append(m)
    return seen


def forbidden(rel: str) -> str | None:
    for pat in FORBIDDEN:
        if fnmatch.fnmatch(rel, pat) or rel == pat:
            return pat
    return None


def showcase_deps(engine: Path) -> list[str]:
    """showcase html 의 script src·link href·@font-face url(../ 는 엔진 뿌리 기준으로 푼다)."""
    html = (engine / "out" / "scene-style-ui-showcase.html").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="([^"?#]+)', html) + re.findall(r'url\("([^"?#)]+)', html)
    out = []
    for r in refs:
        if r.startswith(("http:", "https:", "data:", "#")):
            continue
        p = (engine / "out" / r).resolve()
        try:
            rel = p.relative_to(engine.resolve()).as_posix()
        except ValueError:
            continue
        if p.is_file():
            out.append(rel)
    return sorted(set(out))


def _true_case(engine: Path) -> dict:
    """소문자 경로 → 실제 경로(옛 추적은 윈도우 normcase 로 소문자였다)."""
    out = {}
    for p in engine.rglob("*"):
        if ".git" in p.parts or not p.is_file():
            continue
        rel = p.relative_to(engine).as_posix()
        out[rel.lower()] = rel
    return out


def traced(traces: Path, engine: Path | None = None) -> tuple[set[str], set[str]]:
    mods, data = set(), set()
    for f in traces.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        mods |= set(d.get("modules") or [])
        data |= {x for x in d.get("opened") or [] if "__pycache__" not in x}
    if engine is not None:
        tc = _true_case(engine)
        mods = {tc.get(x.lower(), x) for x in mods}
        data = {tc.get(x.lower(), x) for x in data}
    return mods, data


def build(engine: Path, traces: Path, out: Path) -> dict:
    mods, data = traced(traces, engine)
    want = sorted(mods | data | top_imports(engine) | set(RENDERER_EXTRA) | set(showcase_deps(engine)) | set(data_extra(engine)))
    kept, dropped, missing = [], [], []
    if out.exists():
        shutil.rmtree(out)
    for rel in want:
        why = forbidden(rel)
        if why:
            dropped.append((rel, why))
            continue
        src = engine / rel
        if not src.is_file():
            missing.append(rel)
            continue
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        kept.append(rel)
    for pkg in {Path(r).parent for r in kept if r.endswith(".py")}:   # 패키지 __init__ (추적에서 빠질 수 있다)
        for p in [pkg, *pkg.parents]:
            if str(p) in (".", ""):
                break
            init = engine / p / "__init__.py"
            if init.is_file() and not (out / p / "__init__.py").exists() and not forbidden((p / "__init__.py").as_posix()):
                (out / p).mkdir(parents=True, exist_ok=True)
                shutil.copy2(init, out / p / "__init__.py")
                kept.append((p / "__init__.py").as_posix())
    man = {"files": {r: hashlib.sha256((out / r).read_bytes()).hexdigest() for r in sorted(set(kept))},
           "dropped": [{"file": r, "rule": w} for r, w in dropped], "missing": missing}
    (out / "engine_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def check(bundle: Path) -> list[str]:
    bad = []
    for p in bundle.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(bundle).as_posix()
        why = forbidden(rel)
        if why:
            bad.append(f"금지 파일 {rel} ({why})")
            continue
        if p.suffix.lower() in (".py", ".js", ".json", ".html", ".md", ".txt", ".css", ".env", ""):
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for s in SECRETS:
                if re.search(s, t):
                    bad.append(f"금지 글자 /{s}/ in {rel}")
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
        man = build(Path(a["--engine"]), Path(a["--traces"]), Path(a["--out"]))
        print(f"묶음: 파일 {len(man['files'])} · 뺀 것 {len(man['dropped'])} · 엔진에 없음 {len(man['missing'])}")
        for d in man["dropped"][:40]:
            print("  뺌", d["file"], "←", d["rule"])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
