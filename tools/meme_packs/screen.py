"""받은 밈 클립을 규격으로 걸러 '후보'를 뽑는다. 판정은 사람이 최종 확인한다.

★왜 자동 판정만으로 끝내지 않나: 2026-09-15 실측으로 세 가지가 드러났다.
  1. 팩 이름이 "Green screen memes"인데 18개 중 8개가 **영화 화면 그대로**(그린 0%)
  2. 그린스크린인데 **글자가 박힌 것**이 있다("Thug Life") → 자막과 겹쳐 못 쓴다
  3. 대표 프레임을 0.5초·0.8초에서 뽑으면 **빈 초록**이 나온다(등장 타이밍이 클립마다 다름)
  → 그래서 프레임은 '초록이 가장 적은 = 피사체가 가장 큰' 지점에서 뽑고,
     최종 채택은 사람이 눈으로 본다.

★규격 근거(실측): 밈 슬롯은 spec.SLOT_W/H = 1028×786 이고 frames.compose 가
  _contain_h(im, 786) 로 **높이를 786에 맞춰 확대**한다 → 높이 786 미달은 깨진다.
  (의뢰서의 "최소 512"는 부족한 기준이다. 현재 페페 팩도 57장 중 49장이 786 미달)

쓰는 법:
  python tools/meme_packs/screen.py <밈원본폴더> <후보저장폴더>
"""
import json
import os
import subprocess
import sys

SLOT_H = 786                 # brainbulb spec.SLOT_H — 이 아래면 확대되어 깨진다
SLOT_W = 1028
PROBES = 9                   # 클립당 훑어볼 지점 수
VIDEO = (".mp4", ".mov", ".webm", ".gif", ".mkv", ".avi")


def ffprobe(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
           "stream=width,height,duration,nb_frames", "-show_entries",
           "format=duration", "-of", "json", path]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        d = json.loads(p.stdout or "{}")
    except Exception:
        return None
    st = (d.get("streams") or [{}])[0]
    dur = st.get("duration") or (d.get("format") or {}).get("duration")
    try:
        dur = float(dur)
    except (TypeError, ValueError):
        dur = 0.0
    try:
        w, h = int(st.get("width") or 0), int(st.get("height") or 0)
    except (TypeError, ValueError):
        w = h = 0
    return {"w": w, "h": h, "dur": dur}


def grab(path, t, out):
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", path,
           "-frames:v", "1", out]
    try:
        subprocess.run(cmd, capture_output=True, timeout=90)
    except subprocess.TimeoutExpired:
        return False
    return os.path.exists(out) and os.path.getsize(out) > 0


def analyze(png):
    """→ (초록비율%, 레터박스여부) — 초록=크로마키 배경.

    ★레터박스 검사를 같이 한다(2026-09-15 실측): "El Risitas" 클립은 그린스크린
      **안에 또 검은 액자**가 있었다. 그대로 쓰면 검은 띠가 화면에 박힌다.
      테두리 네 변이 어두우면(초록도 아니고) 액자로 본다.
    """
    from PIL import Image
    im = Image.open(png).convert("RGB")
    im.thumbnail((160, 160))
    w, h = im.size
    px = im.load()
    n = w * h or 1

    def is_green(c):
        r, g, b = c
        return g > 90 and g > r * 1.35 and g > b * 1.35

    green = sum(1 for y in range(h) for x in range(w) if is_green(px[x, y]))

    # 테두리 2px 띠가 '어둡다'면 레터박스
    band = []
    for x in range(w):
        band += [px[x, 0], px[x, h - 1]]
    for y in range(h):
        band += [px[0, y], px[w - 1, y]]
    dark = sum(1 for r, g, b in band if r < 45 and g < 45 and b < 45)
    letterbox = dark * 100 // (len(band) or 1) > 55
    return green * 100 // n, letterbox


def main():
    src_root, out_root = sys.argv[1], sys.argv[2]
    os.makedirs(out_root, exist_ok=True)
    rows = []
    clips = []
    for root, _, files in os.walk(src_root):
        for f in sorted(files):
            if f.lower().endswith(VIDEO):
                clips.append(os.path.join(root, f))
    print(f"클립 {len(clips)}개 검사", flush=True)

    tmp = os.path.join(out_root, "_frames")
    os.makedirs(tmp, exist_ok=True)

    for i, c in enumerate(clips, 1):
        meta = ffprobe(c)
        if not meta or meta["h"] == 0:
            rows.append({"file": c, "verdict": "읽기실패"})
            continue
        # 여러 지점을 훑어 '초록이 가장 적은' = 피사체가 가장 큰 프레임을 고른다
        best = None
        dur = meta["dur"] or 1.0
        for k in range(PROBES):
            t = dur * (k + 1) / (PROBES + 1)
            p = os.path.join(tmp, f"c{i:03d}_{k}.png")
            if not grab(c, t, p):
                continue
            try:
                g, lb = analyze(p)
            except Exception:
                continue
            if best is None or g < best[0]:
                if best:
                    try:
                        os.remove(best[1])
                    except OSError:
                        pass
                best = (g, p, t, lb)
            else:
                try:
                    os.remove(p)
                except OSError:
                    pass
        if not best:
            rows.append({"file": c, "verdict": "프레임실패", **meta})
            continue
        green, frame, t, letterbox = best

        # 판정 — 통과/보류 사유를 갈라서 적는다.
        # ★높이 기준을 2단으로 나눈다(2026-09-15 실측): 786 미달이라고 다 버리면
        #   18개 중 후보가 1개뿐이었다. 실제로 640×360을 2.18배 확대해 눈으로 보니
        #   **단순 그래픽은 확대에 강하고** 실사 얼굴만 뭉개진다. 그래서 786 미달은
        #   '보류'가 아니라 '확대필요'로 따로 표시해 사람이 보고 고르게 한다.
        reasons = []
        soft = []
        if meta["h"] < SLOT_H // 2:                    # 393 미달 = 2배 넘게 확대 → 위험
            reasons.append(f"높이{meta['h']}(2배↑확대)")
        elif meta["h"] < SLOT_H:
            soft.append(f"높이{meta['h']}→{SLOT_H} {meta['h'] and round(SLOT_H/meta['h'],2)}배")
        if green < 15:
            reasons.append(f"그린{green}%(크로마키아님=원본화면)")
        if green > 88:
            reasons.append(f"그린{green}%(피사체못찾음)")
        if letterbox:
            reasons.append("검은액자(레터박스)")
        verdict = "보류" if reasons else ("확대필요" if soft else "후보")
        reasons = reasons or soft
        rows.append({"file": os.path.relpath(c, src_root), "w": meta["w"], "h": meta["h"],
                     "dur": round(meta["dur"], 2), "green": green, "letterbox": letterbox,
                     "frame": os.path.relpath(frame, out_root), "at": round(t, 2),
                     "verdict": verdict, "reasons": reasons})
        print(f"[{i}/{len(clips)}] {verdict} {meta['w']}x{meta['h']} "
              f"{meta['dur']:.1f}s 그린{green}% {os.path.basename(c)}"
              + (f" ← {'; '.join(reasons)}" if reasons else ""), flush=True)

    out = os.path.join(out_root, "_screen_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    ok = [r for r in rows if r.get("verdict") == "후보"]
    up = [r for r in rows if r.get("verdict") == "확대필요"]
    print()
    print(f"=== 후보 {len(ok)} + 확대필요 {len(up)} = 쓸만한 것 {len(ok)+len(up)} / 전체 {len(rows)} ===")
    print("※ '후보'도 사람이 눈으로 봐야 한다 — 글자 박힘·부적절 내용은 자동으로 못 가른다")
    print(f"리포트: {out}")
    print(f"프레임: {tmp}")


if __name__ == "__main__":
    main()
