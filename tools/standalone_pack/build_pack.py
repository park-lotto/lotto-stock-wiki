# -*- coding: utf-8 -*-
"""프리셋 통꾸러미 만들기. 서버·고객 DB·키는 넣지 않고, 금지 파일과 비밀 글자를 검사한다.
사용: python -X utf8 build_pack.py <엔진 폴더> <프리셋 영문폴더> <판 이름> <형식> <출력 폴더>"""
import fnmatch, json, re, shutil, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
SRC, PRESET, VERSION, FMT, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], Path(sys.argv[5])
KEEP = ("tools/__init__.py", "tools/calcopy/**", "shopping_shorts/*.py", "shopping_shorts/channelkit/**", "shopping_shorts/calcopy_frame/**", "shopping_shorts/vmake_sdk/**",
        "shopping_shorts/static/fonts/**", "shopping_shorts/assets/voice_presets.json", "shopping_shorts/assets/bgm_lib/catalog.json", "shopping_shorts/assets/sfx_packs/**", "shopping_shorts/static/caption-motions.js",
        "tools/render_scene_style.js", f"channel/{PRESET}/**")
DROP = ("*/__pycache__/*", "*.pyc", "channel/*/*.png", "channel/*/뜯기/*", "channel/*/현장썰*/*", "channel/*/칼카피_*/*", "channel/*/원자료/*", "*/tests/*", "*.mp4", "*.env*", "*.pem", "*.db", "*.sqlite*",
        "shopping_shorts/app.py", "shopping_shorts/claude_portal.py", "shopping_shorts/claude_flow.py", "shopping_shorts/claude_live.py", "shopping_shorts/store.py", "shopping_shorts/channel_archive.py",
        "shopping_shorts/instagram_playwright.py", "shopping_shorts/apify_client.py", "shopping_shorts/config_secret*",
        "tools/calcopy/engine/_server_access.py", "tools/calcopy/engine/gemini_server.py", "tools/calcopy/engine/gemini_keys.py", "tools/calcopy/pull_pool_keys.py",
        "tools/calcopy/analyze*.py", "tools/calcopy/engine/analyze.py", "tools/calcopy/try_*.py", "tools/calcopy/*.md", "tools/calcopy/*/README.md")
SECRETS = (r"3\.35\.251\.172", r"LightsailDefaultKey", r"ubuntu@", r"BEGIN (RSA |OPENSSH )PRIVATE KEY", r"AIza[0-9A-Za-z_-]{30,}", r"apikey_[0-9a-f]{20,}",
           r"(?m)^\s*[A-Z][A-Z0-9_]*(?:API_KEY|_KEY|SECRET|TOKEN)\s*=\s*['\"]?[A-Za-z0-9_\-]{20,}['\"]?\s*$")


def wanted(rel):
    if any(fnmatch.fnmatch(rel, d) for d in DROP): return False
    return any(fnmatch.fnmatch(rel, k.replace("/**", "/*")) if "**" in k else fnmatch.fnmatch(rel, k) and "/" not in rel[len(k.rsplit("/", 1)[0]) + 1:] for k in KEEP)


if OUT.exists(): shutil.rmtree(OUT)
eng = OUT / "engine"; eng.mkdir(parents=True)
n = size = 0
for p in SRC.rglob("*"):
    if not p.is_file() or ".git" in p.parts: continue
    rel = p.relative_to(SRC).as_posix()
    if wanted(rel):
        q = eng / rel; q.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, q); n += 1; size += p.stat().st_size
style = json.loads((SRC / "tools/calcopy/hybrid/styles" / (VERSION + ".json")).read_text(encoding="utf-8"))
song = (style.get("bgm") or {}).get("id")
for f in (SRC / "shopping_shorts/assets/bgm_lib").glob(f"{song}.*"):   # 이 판이 쓰는 곡만
    q = eng / "shopping_shorts/assets/bgm_lib" / f.name; q.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, q)
pres = json.loads((SRC / "channel/프리셋.json").read_text(encoding="utf-8"))
pres["presets"] = {k: v for k, v in pres["presets"].items() if PRESET in json.dumps(v, ensure_ascii=False) or PRESET in k}   # 다른 프리셋은 넣지 않는다
(eng / "channel/프리셋.json").write_text(json.dumps(pres, ensure_ascii=False), encoding="utf-8")
for f in (HERE / "files").iterdir(): shutil.copy2(f, OUT / f.name)
shutil.copy2(SRC / "installer/common/tools.lock.json", OUT / "tools.lock.json")
req = re.sub(r"\s*\\\n\s*--hash=\S+", "", (SRC / "installer/common/requirements-engine-py312-win.txt").read_text(encoding="utf-8"))
(OUT / "requirements.txt").write_text(req, encoding="utf-8")
(OUT / "pack.json").write_text(json.dumps({"version": VERSION, "fmt": FMT, "preset": PRESET}, ensure_ascii=False), encoding="utf-8")

# 엔진 코드 안의 우리 서버 접속 정보는 지운다(회원 경로는 쓰지 않는 개발용 갈래)
scrub = 0
for p in eng.rglob("*.py"):
    t = p.read_text(encoding="utf-8", errors="ignore"); t2 = re.sub(r"3\.35\.251\.172|LightsailDefaultKey(?:\.pem)?|ubuntu@", "", t)
    if t2 != t: p.write_text(t2, encoding="utf-8"); scrub += 1
print("서버 정보 지운 파일", scrub)
bad = []
for p in eng.rglob("*"):
    if p.suffix.lower() in (".py", ".json", ".js", ".md", ".txt", ".html"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        bad += [(p.relative_to(OUT).as_posix(), s[:24]) for s in SECRETS if re.search(s, t)]
print(f"파일 {n}개, {size / 1e6:.0f}MB, 비밀 글자 {len(bad)}건")
for b in bad[:12]: print(" ", b)
sys.exit(1 if bad else 0)
