"""감정짤 밈팩 — candidates.json 의 후보 영상을 내려받고, 감정별 훑어보기 시트를 만든다.

    py tools/meme_pack/fetch.py <작업폴더>

<작업폴더>/raw/<id>.mp4        내려받은 원본(720p 이하). 이미 있으면 건너뜀
<작업폴더>/sheets/<감정>_NN.jpg  영상마다 6프레임 한 줄, 12편씩 한 장 (눈으로 고르는 용도)
<작업폴더>/fetch_log.json      id → 성공/실패 사유·길이·해상도
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

FRAMES, TILE_W, PER_SHEET = 6, 130, 12


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:format=duration", "-of", "json", path])
    try:
        j = json.loads(r.stdout)
        s = j["streams"][0]
        return float(j["format"]["duration"]), int(s["width"]), int(s["height"])
    except Exception as e:  # 깨진 파일은 실패로 기록하고 넘어간다(조용히 삼키지 않는다 — 로그에 남김)
        return None, f"ffprobe 실패: {e}", None


def download(vid, raw_dir):
    out = os.path.join(raw_dir, f"{vid}.mp4")
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return out, "있음"
    r = run(["yt-dlp", "-q", "--no-warnings", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
             "--merge-output-format", "mp4", "-o", out, f"https://www.youtube.com/watch?v={vid}"])
    if r.returncode != 0 or not os.path.exists(out):
        return None, (r.stderr.strip().splitlines() or ["알 수 없는 실패"])[-1][:200]
    return out, "받음"


def strip(path, dur, tmp):
    """영상 하나를 6프레임 가로 한 줄 이미지로."""
    ims = []
    for k in range(FRAMES):
        t = dur * (k + 0.5) / FRAMES
        r = run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
                 "-vf", f"scale={TILE_W}:-2", tmp])
        if r.returncode == 0 and os.path.exists(tmp):
            ims.append(Image.open(tmp).convert("RGB").copy())
    if not ims:
        return None
    h = max(i.height for i in ims)
    row = Image.new("RGB", (TILE_W * FRAMES, h), "black")
    for k, im in enumerate(ims):
        row.paste(im, (k * TILE_W, 0))
    return row


def main():
    work = sys.argv[1]
    raw_dir, sheet_dir = os.path.join(work, "raw"), os.path.join(work, "sheets")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(sheet_dir, exist_ok=True)
    cands = json.load(open(os.path.join(work, "candidates.json"), encoding="utf-8"))
    log, tmp = {}, os.path.join(work, "raw", "_f.jpg")
    for emo, rows in cands.items():
        strips = []
        for row in rows:
            vid = row["id"]
            path, note = download(vid, raw_dir)
            if not path:
                log[vid] = {"ok": False, "why": note}
                continue
            dur, w, h = probe(path)
            if dur is None:
                log[vid] = {"ok": False, "why": w}
                continue
            log[vid] = {"ok": True, "note": note, "duration": round(dur, 2), "w": w, "h": h, "emotion": emo}
            # 뷰어 표지(첫 프레임이 검정인 영상이 많다 → 30% 지점 그림)
            thumb = os.path.join(sheet_dir, "thumbs", f"{vid}.jpg")
            if not os.path.exists(thumb):
                os.makedirs(os.path.dirname(thumb), exist_ok=True)
                run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * 0.3:.2f}", "-i", path, "-frames:v", "1",
                     "-vf", "scale=-2:260", thumb])
            s = strip(path, dur, tmp)
            if s:
                strips.append((vid, dur, w, h, s))
        for i in range(0, len(strips), PER_SHEET):
            part = strips[i:i + PER_SHEET]
            cols = 2
            cell_w = TILE_W * FRAMES + 6
            row_h = max(s.height for *_, s in part) + 16
            rows_n = (len(part) + cols - 1) // cols
            sheet = Image.new("RGB", (cell_w * cols, row_h * rows_n), "black")
            dr = ImageDraw.Draw(sheet)
            for k, (vid, dur, w, h, s) in enumerate(part):
                x, y = (k % cols) * cell_w, (k // cols) * row_h
                dr.text((x + 2, y + 2), f"{vid}  {dur:.1f}s  {w}x{h}", fill="yellow")
                sheet.paste(s, (x, y + 16))
            sheet.save(os.path.join(sheet_dir, f"{emo}_{i // PER_SHEET:02d}.jpg"), quality=78)
        ok = sum(1 for r in rows if log.get(r["id"], {}).get("ok"))
        print(f"{emo}: 후보 {len(rows)} → 받음 {ok}")
    if os.path.exists(tmp):
        os.remove(tmp)
    json.dump(log, open(os.path.join(work, "fetch_log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fails = [v for v in log.values() if not v["ok"]]
    print(f"실패 {len(fails)}건")


if __name__ == "__main__":
    main()
