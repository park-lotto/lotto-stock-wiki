# 시작 검수 — 제작 전에 필요한 도구·키·재료를 한 번에 확인한다. 전부 통과해야 시작한다.
# 사용: python -X utf8 preflight.py [--json]
# 키는 고객 것을 쓴다(keys.py). 값은 출력하지 않는다.
import hashlib, importlib.util, json, os, shutil, subprocess, sys, urllib.error, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.abspath(os.environ.get("SHORCL_WORK") or os.getcwd())
MIN_GB = 10
PY_MODS = ["PIL", "numpy", "scipy"]
sys.path.insert(0, os.path.join(HERE, "steps"))
import keys


key = keys.get


def http(url, headers=None):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"}), timeout=20)
        return r.status, r.read(2000)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""


def ck_ffmpeg():
    miss = [x for x in ("ffmpeg", "ffprobe") if not shutil.which(x)]
    return (not miss, "영상 도구 준비됨" if not miss else "영상 도구가 없습니다", "설치팩을 다시 실행해 주세요")


def ck_python():
    miss = [m for m in PY_MODS if importlib.util.find_spec(m) is None]
    return (not miss, "실행 도구 준비됨" if not miss else "실행 도구 일부가 없습니다", "설치팩을 다시 실행해 주세요")


def encoder():
    """NVENC 가 실제로 되는지 짧게 구워 본다. 안 되면 CPU 로 간다(실패가 아니라 시간만 는다)."""
    if not shutil.which("ffmpeg"): return "cpu"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"],
                       capture_output=True)
    return "gpu" if r.returncode == 0 else "cpu"


def ck_disk():
    gb = shutil.disk_usage(WORK).free / 1e9
    return (gb >= MIN_GB, f"디스크 여유 {gb:.1f}GB", f"작업 드라이브를 {MIN_GB}GB 이상 비워 주세요")


def ck_assets():
    sys.path.insert(0, HERE); os.environ.setdefault("SHORCL_WORK", WORK)
    from studio.cfg import load_cfg, missing_fonts   # 글꼴 목록은 studio/cfg.FONTS 한 곳
    miss = missing_fonts(load_cfg()) + [p for p in ("media/bgm/Bass_Walker.mp3",
                        "media/bgm/Thinking_Music.mp3", "media/bgm/Local_Forecast.mp3", "media/bgm/Pamgaea.mp3", "media/sfx/pop_appear.mp3")
            if not os.path.exists(os.path.join(HERE, p))]
    return (not miss, "글꼴·음악 준비됨" if not miss else f"글꼴·음악 {len(miss)}개가 없습니다", "프리셋 꾸러미를 다시 받아 주세요")


def ck_typecast():
    k = key("typecast")
    if not k: return False, "목소리 키가 없습니다", "내 채널 설정에 타입캐스트 키를 넣어 주세요"
    st, body = http("https://api.typecast.ai/v1/users/me/subscription", {"X-API-KEY": k})
    if st != 200: return False, "목소리 키를 쓸 수 없습니다", "타입캐스트 키를 다시 확인해 주세요"
    c = json.loads(body)["credits"]; left = c["plan_credits"] - c["used_credits"]
    return (left >= 30000, f"목소리 크레딧 {left:,} 남음", "타입캐스트 크레딧을 충전해 주세요")


def ck_pixabay():
    k = key("pixabay")
    if not k: return False, "실사 영상 키가 없습니다", "내 채널 설정에 Pixabay 키를 넣어 주세요"
    st, _ = http(f"https://pixabay.com/api/videos/?key={k}&q=city&per_page=3")
    return (st == 200, "실사 영상 연결됨" if st == 200 else "실사 영상 키를 쓸 수 없습니다", "Pixabay 키를 다시 확인해 주세요")


def ck_codex():
    import shutil, subprocess
    exe = shutil.which("codex")
    if not exe: return False, "코덱스가 설치되어 있지 않습니다", "npm install -g @openai/codex 로 설치해 주세요"
    r = subprocess.run([exe, "login", "status"], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "Logged in" not in r.stdout + r.stderr: return False, "코덱스에 로그인되어 있지 않습니다", "codex login 으로 로그인해 주세요"
    return True, "코덱스 로그인 확인됨", ""


def ck_gemini():
    """그림 1장을 실제로 만들어 본다. 결제 없는 키는 목록 조회는 되고 그림만 429 로 막힌다. 약 50원, 키마다 한 번만."""
    if (os.environ.get("SHORCL_IMAGE_ENGINE") or "codex") == "codex": return ck_codex()
    k = key("gemini")
    if not k: return False, "그림 키가 없습니다", "내 채널 설정에 제미나이 키를 넣어 주세요"
    mark = os.path.expanduser("~/.shortem/image_ok_" + hashlib.sha256(k.encode()).hexdigest()[:12])
    if os.path.exists(mark): return True, "그림 만들기 확인됨", ""
    if "--no-paid" in sys.argv: return False, "그림 만들기 확인 전입니다(약 50원)", "--no-paid 없이 다시 실행해 주세요"
    model = os.environ.get("SHORCL_IMAGE_MODEL") or "gemini-3.1-flash-lite-image"
    body = {"contents": [{"parts": [{"text": "A quiet street, photo"}]}], "generationConfig": {"responseModalities": ["IMAGE"]}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": k, "Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=90).read()
    except urllib.error.HTTPError as e:
        if e.code == 429: return False, "그림 사용량이 없는 키입니다", "구글 AI 스튜디오에서 결제를 등록해 주세요"
        return False, "그림 키를 쓸 수 없습니다", "제미나이 키를 다시 확인해 주세요"
    open(mark, "w").close()
    return True, "그림 만들기 확인됨", ""


def ck_typesafe():
    k = key("typesafe")
    if not k: return False, "소재 판정 키가 없습니다", "내 채널 설정에 TypeSafe 키를 넣어 주세요"
    st, _ = http("https://api.typesafe.ai/v1/models", {"Authorization": "Bearer " + k, "User-Agent": "Mozilla/5.0"})
    if st == 401: return False, "소재 판정 키를 쓸 수 없습니다", "TypeSafe 키를 다시 확인해 주세요"
    return True, "소재 판정 키 있음", ""


CHECKS = [("영상 도구", ck_ffmpeg), ("실행 도구", ck_python), ("디스크", ck_disk), ("글꼴·음악", ck_assets), ("목소리", ck_typecast),
          ("실사 영상", ck_pixabay), ("그림", ck_gemini), ("소재 판정", ck_typesafe)]


def main():
    rows = []
    for name, fn in CHECKS:
        try:
            ok, msg, fix = fn()
        except Exception:
            ok, msg, fix = False, "확인하지 못했습니다", "잠시 뒤 다시 시도해 주세요"
        rows.append(dict(name=name, ok=ok, msg=msg, fix="" if ok else fix))
    out = dict(ok=all(r["ok"] for r in rows), encoder=encoder(), checks=rows)
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for r in rows:
            print(("통과 " if r["ok"] else "막힘 ") + r["name"] + " — " + r["msg"] + ((" → " + r["fix"]) if r["fix"] else ""))
        print("렌더:", "GPU" if out["encoder"] == "gpu" else "CPU(시간이 더 걸립니다)")
        print("시작 가능" if out["ok"] else "시작 불가 — 위 막힘을 풀어 주세요")
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
