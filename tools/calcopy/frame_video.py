"""틀 설명서(frame.json) + 뜯기(뜯기.json) + 원본 영상 → 라이브 렌더 경로(scene_style.compose)로 만든 우리 영상 한 편.

대조(engine/compare.py)용 — 원본과 **같은 자막 시각·같은 장면 재료**를 넣고 틀만 우리 렌더러가 그리게 한다.
그래서 차이표에 남는 차이는 틀·글자(설명서와 렌더러)의 차이다.
  - 자막 장면 = 뜯기 captions.spans · items.text (OCR)
  - 제목 = 설명서 title 층 text
  - 영상 칸 재료 = 원본의 영상 창 부분(틀 있는 구간) / 원본 전체 화면(설명서 template_off 꼬리 구간)
    compose 는 재료를 칸에 cover 로 채우고 가운데를 자른다 — 그래서 창 부분을 1080×1920 한가운데 붙여 두면 그 부분만 정확히 남는다.

    PYTHONUTF8=1 py tools/calcopy/frame_video.py <frame.json> <뜯기.json> <출력폴더> [--src-window]
    --src-window: 원본의 실제 창(뜯기 layout.window)을 오려 우리 창에 cover — 프리셋 기본값처럼 창 자리가 원본과 다를 때
"""
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style, video_assemble as va  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402


def timeline_from(J: dict, tail_start: float | None) -> list[dict]:
    items = {i["i"]: i for i in (J.get("captions") or {}).get("items") or []}
    spans = (J.get("captions") or {}).get("spans") or []
    dur = float((J.get("probe") or {}).get("duration") or 0)
    beats, t = [], 0.0
    for k, (a, b) in enumerate(spans):
        if a > t + 0.05:
            beats.append((t, a, ""))
        if tail_start is not None:
            b = min(b, tail_start)
        text = " ".join((items.get(k) or {}).get("text") or [])
        if b > a:
            beats.append((a, b, text)); t = b
    end = tail_start if tail_start is not None else dur
    if end > t + 0.05:
        beats.append((t, end, ""))
    if tail_start is not None and dur > tail_start + 0.05:
        beats.append((tail_start, dur, ""))          # 틀 꺼지는 꼬리 — 자막 없음
    return [{"beat_idx": i, "t0": round(a, 3), "dur": round(b - a, 3), "narration": txt, "caption_lines": [txt] if txt else [],
             "role": "hook" if i == 0 else "body", "primary": {"video_id": "s0", "start": a, "end": b}}
            for i, (a, b, txt) in enumerate(beats)]


def material(src: str, spec: dict, tail_start: float | None, dur: float, out: pathlib.Path, src_window=None) -> pathlib.Path:
    """src_window = 원본의 실제 영상 창 [x,y,w,h](뜯기 layout.window). 주면 그 부분을 우리 창 크기로 cover 맞춤
    (새 소재 시험: 프리셋 창이 원본 창과 다를 때 원본의 제목·자막 띠가 재료에 섞이지 않게). 안 주면 우리 창 자리 그대로 오린다."""
    # 틀 여러 장(훅+본문)이면 영상 한가운데 시각의 틀(본문)의 영상 칸 — 틀 고르기는 schema.layers_at 한 곳
    v = next(l for l in schema.layers_at(spec, t=dur / 2) if l["kind"] == "video")
    W, H = spec["canvas"]
    top = (H - v["h"]) // 2
    if src_window:
        x, y, w, h = src_window
        win = (f"crop={w}:{h}:{x}:{y},scale={v['w']}:{v['h']}:force_original_aspect_ratio=increase,crop={v['w']}:{v['h']},"
               f"scale={W}:{v['h']},pad={W}:{H}:0:{top}:black,setsar=1")
    else:
        win = f"crop={v['w']}:{v['h']}:{v['x']}:{v['y']},scale={W}:{v['h']},pad={W}:{H}:0:{top}:black,setsar=1"
    if tail_start is None:
        fc = f"[0:v]{win}[v]"
    else:
        fc = (f"[0:v]split[a][b];[a]trim=0:{tail_start},setpts=PTS-STARTPTS,{win}[a2];"
              f"[b]trim={tail_start}:{dur},setpts=PTS-STARTPTS,scale={W}:{H},setsar=1[b2];[a2][b2]concat=n=2:v=1:a=0[v]")
    va._run_ffmpeg(["ffmpeg", "-y", "-i", src, "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-r", "30",
                    "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)])
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    frame_p, J_p, out = args[0], args[1], pathlib.Path(args[2]).resolve()
    src_win_auto = "--src-window" in sys.argv   # 원본 창(뜯기 layout.window)을 재료로
    shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    frame = json.loads(pathlib.Path(frame_p).read_text(encoding="utf-8"))
    J = json.loads(pathlib.Path(J_p).read_text(encoding="utf-8"))
    spec = schema.validate(frame)
    dur = float(J["probe"]["duration"])
    tail = (spec.get("template_off") or {}).get("tail_sec")
    tail_start = round(dur - tail, 3) if tail else None
    tl = timeline_from(J, tail_start)
    title = next((l for l in schema.all_layers(spec) if l["kind"] == "text" and l["role"] == "title"), None)
    head = {"text": (title or {}).get("text") or ""}
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
    mat = material(J["source"], spec, tail_start, dur, out / "material.mp4",
                   (J.get("layout") or {}).get("window") if src_win_auto else None)
    ours = out / "ours.mp4"
    scene_style.compose(str(mat), tl, snap, str(ours), out / "work", head)
    ctx = scene_style.context_for(tl, head, snap)
    (out / "timeline.json").write_text(json.dumps({"beats": tl, "scenes": [(s["start"], s["end"], s["caption"]) for s in ctx["scenes"]],
                                                   "tail_start": tail_start}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ours:", ours)


if __name__ == "__main__":
    main()
