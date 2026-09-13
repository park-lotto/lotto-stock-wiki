"""라이브러리 전수 점검(파일 층). 원본 미디어와 미리보기(_thumbs) 전부를 ffprobe/PIL로 열어본다.
결과: library/_audit.json + 요약 출력. 뷰어를 사람에게 보여주기 전에 돌린다.
쓰는 법: py tools/effect_packs/audit.py <library 폴더>
"""
import json, os, subprocess, sys, hashlib, concurrent.futures as cf

LIB = os.path.abspath(sys.argv[1])
THUMB = os.path.join(LIB, "_thumbs")
IMG = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VID = {".mov", ".mp4", ".webm"}
AUD = {".mp3", ".wav", ".ogg"}
MOGRT = {".mogrt"}


def probe_ok(path):
    """ffprobe로 열리고 첫 프레임을 실제로 디코드할 수 있는지."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False, "없음/0바이트"
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name", "-of", "csv=p=0", path],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.strip():
        return False, "ffprobe 실패: " + (r.stderr or "")[-120:].strip()
    # 실제 디코드(첫 0.5초) — 헤더만 멀쩡한 깨진 파일을 잡는다
    d = subprocess.run(["ffmpeg", "-v", "error", "-t", "0.5", "-i", path, "-f", "null", "-"], capture_output=True, text=True, timeout=60)
    errs = [ln for ln in d.stderr.splitlines() if ln.strip() and "chapter track not found" not in ln]   # QT 챕터 경고는 무해
    if errs:
        return False, "디코드 오류: " + errs[-1][-120:]
    return True, r.stdout.strip().replace("\n", "|")


def img_ok(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            im.load()
            return True, f"{im.mode} {im.size[0]}x{im.size[1]}"
    except Exception as e:
        return False, "PIL 오류: " + str(e)[:100]


def check(item):
    pack_dir, pack_id, f = item
    src = os.path.join(pack_dir, f["file"]); ext = f["ext"]
    key = hashlib.md5(f["file"].encode("utf-8")).hexdigest()[:10]
    thumb = os.path.join(THUMB, pack_id, key + ".png"); prev = os.path.join(THUMB, pack_id, key + ".mp4")
    row = {"pack": pack_id, "file": f["file"], "ext": ext, "bytes": os.path.getsize(src) if os.path.exists(src) else -1}
    if ext in IMG:
        row["src_ok"], row["src_info"] = img_ok(src)
        row["thumb_ok"], row["thumb_info"] = img_ok(thumb) if os.path.exists(thumb) else (False, "썸네일 없음")
    elif ext in VID:
        row["src_ok"], row["src_info"] = probe_ok(src)
        row["thumb_ok"], row["thumb_info"] = img_ok(thumb) if os.path.exists(thumb) else (False, "포스터 없음")
        row["prev_ok"], row["prev_info"] = probe_ok(prev) if os.path.exists(prev) else (False, "미리보기 mp4 없음")
    elif ext in AUD:
        row["src_ok"], row["src_info"] = probe_ok(src)
    elif ext in MOGRT:
        row["src_ok"] = os.path.getsize(src) > 0
        row["thumb_ok"], row["thumb_info"] = img_ok(thumb) if os.path.exists(thumb) else (False, "썸네일 없음(mogrt에 thumb.png 없음?)")
        row["prev_ok"], row["prev_info"] = probe_ok(prev) if os.path.exists(prev) else (False, "미리보기 없음(mogrt에 thumb.mp4 없음?)")
    else:
        row["src_ok"] = os.path.getsize(src) > 0; row["src_info"] = "미디어 아님(점검 생략)"
    return row


def main():
    lib = json.load(open(os.path.join(LIB, "library.json"), encoding="utf-8"))
    items = []
    for p in lib["packs"]:
        pd = os.path.join(LIB, p["category"], p["id"])
        pj = json.load(open(os.path.join(pd, "pack.json"), encoding="utf-8"))
        for f in pj["inventory"]:
            if f["file"].endswith(".ENCRYPTED") or f["file"].endswith(".part"):
                continue
            items.append((pd, p["id"], f))
    with cf.ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(check, items))
    bad = [r for r in rows if r.get("src_ok") is False or r.get("thumb_ok") is False or r.get("prev_ok") is False]
    json.dump({"total": len(rows), "bad": bad}, open(os.path.join(LIB, "_audit.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print(f"점검 {len(rows)}개 파일 → 문제 {len(bad)}개")
    reasons = Counter()
    for r in bad:
        for k in ("src", "thumb", "prev"):
            if r.get(k + "_ok") is False:
                reasons[f"{k}:{(r.get(k + '_info') or '')[:40]}"] += 1
    for k, n in reasons.most_common(25):
        print(f"  {n:4d}  {k}")
    print("\n예시:")
    for r in bad[:15]:
        print("  ", r["pack"][:26], r["file"][-50:], {k: r.get(k) for k in ("src_ok", "thumb_ok", "prev_ok")})


if __name__ == "__main__":
    main()
