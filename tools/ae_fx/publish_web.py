"""에펙 견본을 숏템메이커 '효과 견본' 화면(관리자 전용, 관제 118)에 올린다.

1) D:\\ae_fx_work 의 견본(스크립트 30 + 프리셋 300)을 웹용(540×960·소리 없음)으로 줄여
   D:\\ae_fx_work\\web\\fx_samples\\<번호>.mp4 + manifest.json 을 만든다.
2) --upload 를 주면 서버의 shopping_shorts/data/fx_samples/ 로 보낸다(git 밖 데이터 폴더 — 코드 배포와 무관).
   서버가 읽는 자리는 app.py:_fx_samples_dir 한 곳.

분류·이름은 견본 페이지 도구(make_showcase.CATS · make_presets_page.KO/ORDER)와 같은 표를 쓴다 — 여기서 새로 적지 않는다.
사용: py tools/ae_fx/publish_web.py [--upload]
"""
import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import make_presets_page as presets   # noqa: E402
import make_showcase as showcase      # noqa: E402

WORK = Path(r"D:\ae_fx_work")
WEB = WORK / "web" / "fx_samples"
KEY = Path(r"C:\Users\CH\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem")
HOST = "shoppingshorts.duckdns.org"          # IP 는 바뀐다 — 도메인으로 간다
REMOTE = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/fx_samples"
TAG = {"얹기": "lay", "글자": "text", "영상": "video"}


def shrink(src, dst):
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and dst.stat().st_size > 1000:
        return True
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-vf", "scale=540:960", "-r", "30",
           "-c:v", "libx264", "-preset", "slow", "-crf", "29", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)]
    return subprocess.run(cmd).returncode == 0


def build():
    WEB.mkdir(parents=True, exist_ok=True)
    groups, missing, count = [], [], 0
    for key, name, desc, items in showcase.CATS:
        out = []
        for vid, title, how in items:
            src = WORK / f"{vid}.mp4"
            if not src.exists() or not shrink(src, WEB / f"{vid}.mp4"):
                missing.append(vid)
                continue
            out.append({"id": vid, "title": title, "tag": TAG[how], "note": ""})
        if out:
            groups.append({"key": key, "name": name, "desc": desc, "items": out})
            count += len(out)
    rows = [ln.split("\t") for ln in (WORK / "presets_manifest.txt").read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    by = {}
    for r in rows:
        vid, folder, title, font, size = r[0], r[1], r[2].strip(), r[3], r[4]
        src = WORK / "presets" / f"{vid}.mp4"
        if not src.exists() or not shrink(src, WEB / f"{vid}.mp4"):
            missing.append(vid)
            continue
        note = "" if (font == "NotoSansKR-Black" and size == "100") else "프리셋이 글꼴·문구를 바꿈"
        by.setdefault(folder, []).append({"id": vid, "title": title, "tag": "text", "note": note})
    for folder in [k for k in presets.ORDER if k in by] + [k for k in by if k not in presets.ORDER]:
        groups.append({"key": "P-" + folder, "name": "프리셋 · " + presets.KO.get(folder, folder),
                       "desc": "에펙 기본 글자 프리셋 " + folder, "items": by[folder]})
        count += len(by[folder])
    (WEB / "manifest.json").write_text(
        json.dumps({"updated": datetime.date.today().isoformat(), "groups": groups}, ensure_ascii=False), encoding="utf-8")
    size = sum(f.stat().st_size for f in WEB.glob("*.mp4")) / 1024 ** 2
    print(f"견본 {count}개 · 묶음 {len(groups)}개 · {size:.0f}MB → {WEB}")
    if missing:
        print(f"빠진 것 {len(missing)}개: " + ", ".join(missing[:20]))
    return count


def upload():
    ssh = ["ssh", "-i", str(KEY), "-o", "StrictHostKeyChecking=accept-new", f"ubuntu@{HOST}"]
    if subprocess.run(ssh + [f"mkdir -p {REMOTE}"]).returncode:
        return 1
    rc = subprocess.run(["scp", "-q", "-i", str(KEY), "-r", str(WEB) + "/.", f"ubuntu@{HOST}:{REMOTE}/"]).returncode
    if rc:
        return rc
    run = subprocess.run(ssh + [f"ls {REMOTE}/*.mp4 | wc -l; du -sh {REMOTE} | cut -f1; test -f {REMOTE}/manifest.json && echo manifest-ok"],
                         capture_output=True, text=True)
    print("서버:", " / ".join(run.stdout.split()))
    return run.returncode


def main():
    n = build()
    if "--upload" in sys.argv:
        return upload()
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
