"""장면꾸미기 단어 강조 — 완성 영상까지 구워서 잰다(관제 102).

무엇을 재나 (계산이 아니라 결과물):
  ① 완성본  scene_style.compose 로 '강조 켬'·'강조 끔' 두 벌을 굽고, 단어마다 그 단어가 말해지는 순간의 프레임을
            뽑아 두 벌을 대조한다. 달라진 자리(강조가 그려진 곳)가 **있어야** 하고, 한 구절 안에서 단어 순서대로
            **왼쪽→오른쪽**으로 옮겨가야 한다. 단어가 바뀌기 직전 프레임은 앞 단어 자리에 있어야 한다(시각 대조).
  ② 캡컷    scene_style.overlay_spans 가 단어 상태 수만큼 구간을 내고, 구간이 장면을 빈틈없이 덮는지.
  ③ 썸네일  render_layer_one 한 장에도 강조가 그려지는지(강조 끈 것과 다른지).
강조를 끄면 두 벌이 같아 ①이 전부 실패한다 = 이 검사는 기능이 없을 때 실패한다(--selftest 로 확인).

  py tools/word_fx_check.py --job-dir <tts/·src/·data.json 이 있는 표본 작업 폴더> [--beats 2] [--style box|color] [--grow]
표본: main 폴더 tools/scene_lab/out/<job>(git 추적 밖 — 이 PC 로컬). tts/beat_N.mp3 + beat_N.align.json 이 있어야 한다.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

from shopping_shorts import mix_pipeline, scene_style, video_assemble  # noqa: E402


def build_timeline(job_dir, work, beats_n):
    data = json.loads((job_dir / "data.json").read_text(encoding="utf-8"))
    tts_dir = work / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    beats, tts_paths = [], {}
    for beat in data["beats"][:beats_n]:
        i = beat["beat_idx"]
        mp3 = tts_dir / f"beat_{i}.mp3"
        shutil.copyfile(job_dir / "tts" / f"beat_{i}.mp3", mp3)
        shutil.copyfile(job_dir / "tts" / f"beat_{i}.align.json", str(mp3) + ".align.json")   # 라이브 사이드카 이름
        beat = {k: v for k, v in beat.items() if k not in ("caption_lines", "cap_durs", "cap_lead")}   # 표본의 옛 줄·초는 버린다
        beat["tts_path"] = str(mp3)
        dur = video_assemble._probe_duration(str(mp3))
        words, _src = mix_pipeline._beat_words_src(str(mp3), dur)
        if not words or not mix_pipeline._apply_cap_timing(beat, beat["narration"], words, dur):
            raise SystemExit(f"beat {i}: 구절 시각을 못 쟀다(정렬 사이드카 확인)")
        beats.append(beat)
        tts_paths[i] = str(mp3)
    return video_assemble._beat_timeline({"beats": beats}, tts_paths)


def frame(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", str(out)], check=True)
    return Image.open(out).convert("RGB")


def diff_box(a, b, threshold=40):
    d = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > threshold else 0)
    return d.getbbox()


FX_COLOR = (255, 45, 111)      # 검사용 강조색(#FF2D6F) — 바탕 영상에 거의 없는 색


def color_box(on, off, tolerance=70):
    """강조색이 '켬' 프레임에만 있는 자리의 상자. 전체 대조(diff_box)는 어절을 감쌀 때 생기는 1px 글자 밀림까지
    잡아 줄 전체가 달라졌다고 나온다(실측) — 강조가 **어느 단어에** 그려졌는지는 강조색 자리로 잰다.
    바탕 영상의 분홍빛(손·과자)과 압축 잡티를 거르려고 ①자막 줄 높이(전체 대조가 달라진 세로 범위) 안에서만
    ②세로로 8픽셀 이상 강조색이 이어진 열만 센다."""
    band = diff_box(on, off)
    if not band:
        return None
    def mask(im):
        px = np.asarray(im.crop((0, band[1], im.width, band[3])), dtype=np.int16)
        return (np.abs(px - np.array(FX_COLOR)).max(axis=2) <= tolerance)
    cols = (mask(on) & ~mask(off)).sum(axis=0)
    xs = np.nonzero(cols >= 8)[0]
    return (int(xs[0]), band[1], int(xs[-1]) + 1, band[3]) if len(xs) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--beats", type=int, default=2)
    ap.add_argument("--style", default="box", choices=["box", "color"])
    ap.add_argument("--grow", default="", choices=["", "hold", "pop"])
    ap.add_argument("--work", default=str(ROOT / "out" / "_word_fx_check"))
    ap.add_argument("--selftest", action="store_true", help="강조를 끈 스냅샷을 '켬' 자리에 넣는다 — 검사가 실패해야 정상")
    args = ap.parse_args()
    job_dir, work = Path(args.job_dir).resolve(), Path(args.work).resolve()
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    timeline = build_timeline(job_dir, work, args.beats)
    total = timeline[-1]["t0"] + timeline[-1]["dur"]
    base = {"mode": "story", "presetId": "plain", "plainCaption": 2}
    on = dict(base) if args.selftest else {**base, "wordFx": {"style": args.style, "color": "#FF2D6F", "grow": args.grow}}
    scenes = scene_style.context_for(timeline, None, on)["scenes"]
    with_words = [s for s in scenes if s.get("words")]
    print(f"장면 {len(scenes)} · 단어 시각 붙은 장면 {len(with_words)} · 길이 {total:.2f}초")
    if len(with_words) != len([s for s in scenes if s.get('caption')]):
        print("FAIL 단어 시각이 안 붙은 자막 장면이 있다")
        return 1

    src = work / "in.mp4"      # 바탕 영상: 표본 소스를 길이만큼 1080×1920 으로
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(job_dir / "src" / "s1.mp4"), "-t", f"{total:.3f}", "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30", "-an", "-c:v", "libx264", "-preset", "veryfast", str(src)], check=True)
    outs = {}
    for name, snap in (("on", on), ("off", base)):
        w = work / name
        w.mkdir()
        outs[name] = scene_style.compose(str(src), timeline, snap, str(work / f"{name}.mp4"), str(w))
    layers = json.loads((work / "on" / "scene-style-layers.json").read_text(encoding="utf-8"))

    bad, states = 0, 0
    shots = work / "frames"
    shots.mkdir()
    for index, scene in enumerate(scenes):
        words = scene.get("words")
        if not words:
            continue
        centers = []
        for k, at in enumerate(words):
            nxt = words[k + 1] if k + 1 < len(words) else scene["end"]
            if nxt - at < 0.12:        # 4프레임 미만 단어는 가운데 프레임을 못 고른다
                continue
            mid = (at + nxt) / 2
            a = frame(outs["on"], mid, shots / f"s{index}w{k}_on.png")
            b = frame(outs["off"], mid, shots / f"s{index}w{k}_off.png")
            box = color_box(a, b)
            states += 1
            if not box:
                bad += 1
                print(f"  BAD 장면{index} 단어{k} {mid:.2f}초: 완성본에 강조가 없다")
                continue
            centers.append((k, (box[0] + box[2]) / 2, box))
        xs = [c[1] for c in centers]
        ok = all(x2 > x1 for x1, x2 in zip(xs, xs[1:]))
        if not ok:
            bad += 1
        print(f"  {'OK ' if ok else 'BAD'} 장면{index} 「{scene['caption']}」 강조 가운데 x = {[round(x) for x in xs]}")

    # ② 캡컷 구간
    spans = scene_style.overlay_spans(scenes, layers, work / "on")
    want = sum(len(set(s["words"])) for s in with_words)
    missing = [s["path"] for s in spans if not Path(s["path"]).is_file()]
    gaps = sum(1 for a, b in zip(spans, spans[1:]) if abs(a["end"] - b["start"]) > 1 / 30 + 1e-6)
    cap_ok = len(spans) >= len(scenes) and not missing and not gaps and (args.selftest or len(spans) > len(scenes))
    print(f"  {'OK ' if cap_ok else 'BAD'} 캡컷 구간 {len(spans)}개(장면 {len(scenes)} · 단어 상태 최대 {want}) · 없는 파일 {len(missing)} · 빈틈 {gaps}")
    bad += 0 if cap_ok else 1

    # ③ 썸네일 한 장
    target = next(i for i, s in enumerate(scenes) if s.get("words"))
    t_on = Image.open(scene_style.render_layer_one(timeline, on, str(work / "thumb_on"), target)).convert("RGB")
    t_off = Image.open(scene_style.render_layer_one(timeline, base, str(work / "thumb_off"), target)).convert("RGB")
    thumb_ok = bool(diff_box(t_on, t_off))
    print(f"  {'OK ' if thumb_ok else 'BAD'} 썸네일(장면 {target}) 강조 {'있음' if thumb_ok else '없음'}")
    bad += 0 if thumb_ok else 1

    print(f"{'PASS' if not bad else 'FAIL'} — 단어 상태 {states}개 대조, 어긋남 {bad} · 결과 {work}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
