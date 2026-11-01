"""결과 확인 — 한 편 출력 폴더(프로젝트)에서 잰다. `status` 는 이 PC 의 도구·글꼴·열쇠 점검.

  python preset.py check <프로젝트>   → <프로젝트>/sseol_check.json
  검사: ① 규격 1080x1920 · 30fps · H.264 · AAC   ② 길이 25~75초(참고 채널 최신 5편 33~50초)
        ③ 굽기 전 agy 판정 — 렌더 영수증에 실린 판정(review.json · tools/review.py)이 통과이고 그 대본·타이밍이 영수증의 것과 같은가
  그리고 렌더 영수증(render_receipt.json)의 영상 sha256 이 지금 out.mp4 와 같은가(receipt: bound).
  렌더 뒤에는 프로그램 측정만 한다 — 완성본을 agy 에 보이지 않는다(전역 규칙 «렌더 뒤 AGY 금지»).
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL, REPORT, RECEIPT = "out.mp4", "sseol_check.json", "render_receipt.json"
LENGTH = (25.0, 75.0)
FONTS = ("DoHyeon-Regular.ttf", "Paperlogy-6SemiBold.ttf", "Paperlogy-7Bold.ttf", "Paperlogy-9Black.ttf")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
                        "-of", "json", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(r.stdout or "{}")


def check(proj):
    proj = os.path.abspath(proj)
    mp4 = os.path.join(proj, FINAL)
    if not os.path.isfile(mp4):
        raise SystemExit(f"{FINAL} 가 없습니다 — 먼저 `python preset.py render {proj}`")
    j = probe(mp4)
    st = j.get("streams") or []
    v = next((s for s in st if s.get("codec_type") == "video"), {})
    a = next((s for s in st if s.get("codec_type") == "audio"), {})
    num, _, den = str(v.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1)
    dur = float((j.get("format") or {}).get("duration") or 0)
    spec_ok = v.get("width") == 1080 and v.get("height") == 1920 and abs(fps - 30) < 0.01 and v.get("codec_name") == "h264" and a.get("codec_name") == "aac"
    checks = [
        {"id": 1, "name": "규격 1080x1920·30fps·H.264·AAC", "status": "pass" if spec_ok else "fail",
         "detail": f"{v.get('width')}x{v.get('height')} {fps:.2f}fps {v.get('codec_name')}/{a.get('codec_name')}"},
        {"id": 2, "name": f"길이 {LENGTH[0]:.0f}~{LENGTH[1]:.0f}초", "status": "pass" if LENGTH[0] <= dur <= LENGTH[1] else "fail",
         "detail": f"{dur:.2f}초"},
    ]
    vs = sha(mp4)
    rp = os.path.join(proj, RECEIPT)
    rec = json.load(open(rp, encoding="utf-8")) if os.path.isfile(rp) else None
    receipt = "missing" if rec is None else ("bound" if rec.get("video_sha256") == vs else "unbound")
    pr = (rec or {}).get("pre_render_review") or {}
    reviewed = (pr.get("verdict") == "pass" and pr.get("script_sha256") == (rec or {}).get("script_sha256")
                and pr.get("timing_sha256") == (rec or {}).get("timing_sha256"))
    checks.append({"id": 3, "name": "굽기 전 agy 판정(review.json · 렌더 영수증)", "status": "pass" if reviewed else "fail",
                   "detail": (f"{pr.get('verdict')} · 대본 {str(pr.get('script_sha256') or '')[:12]}" if pr
                              else "렌더 영수증에 굽기 전 판정이 없음 — `python preset.py review <프로젝트>` 뒤 render")})
    rep = {"video": FINAL, "sha256": vs, "receipt": receipt, "checks": checks,
           "technical_pass": all(c["status"] == "pass" for c in checks) and receipt == "bound"}
    json.dump(rep, open(os.path.join(proj, REPORT), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep["technical_pass"] else 1


def _key(name):
    if os.environ.get(name.upper() + "_API_KEY"):
        return "found"
    for d in (os.path.join(ROOT, "keys"), os.path.join(os.path.expanduser("~"), ".volcano", "keys")):
        p = os.path.join(d, name)
        if os.path.isfile(p) and open(p, encoding="utf-8-sig").read().strip():
            return "found"
    return "missing"


def status():
    fdir = os.path.join(ROOT, "assets", "fonts")
    st = {
        "python": sys.version.split()[0],
        "ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe")),
        "agy": bool(shutil.which("agy")),
        "modules": {m: bool(importlib.util.find_spec(m)) for m in ("numpy", "cv2", "PIL", "yt_dlp")},
        "fonts": [f for f in FONTS if not os.path.isfile(os.path.join(fdir, f))] or "ok",
        "sfx": len([f for f in os.listdir(os.path.join(ROOT, "assets", "sfx")) if f.endswith(".mp3")]) if os.path.isdir(os.path.join(ROOT, "assets", "sfx")) else 0,
        "typecast_key": _key("typecast"), "speechmatics_key": _key("speechmatics"),
    }
    print(json.dumps(st, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if "--status" in sys.argv:
        sys.exit(status())
    sys.exit(check(sys.argv[1]))
