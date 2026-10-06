"""구매링크용 롱폼(가로) 판 — 완성 쇼츠를 1920x1080 화면 가운데에 넣고 안내 문구를 얹는다.

왜(2026-10-05 고객 황선희 → 사장님 "오른쪽에 롱폼으로 렌더를 활성화해줘", 관제 132):
  쇼츠에는 누를 수 있는 구매링크를 못 단다. 대신 쇼츠 아래 '관련 동영상'에 내 롱폼을 걸 수 있고,
  롱폼은 설명란·댓글 링크가 눌린다. 그래서 같은 쇼츠를 가로 영상으로 한 벌 더 만들어
  "구매링크 댓글에 있습니다"를 띄운다. 고객들은 이걸 캡컷에서 손으로 만들고 있었다.

★판단의 주인(0순위-C): 가로 화면 구도·문구 자리·파일 이름·"지금 것이 최신인가"는 전부 이 파일이 정한다.
  app.py 라우트와 화면은 여기 함수를 부르기만 한다.
★재렌더가 아니다: 이미 만든 final.mp4 한 편만 입력으로 받는다. 컷·자막·음성 판단을 다시 하지 않는다
  ★쇼츠의 소리는 넣지 않는다(2026-10-06 사장님 "롱폼은 무음으로") — 3단계 목록 곡은 쇼츠 전용(관제 146)이라 롱폼에 실리면 안 된다.
    대신 문구 띠마다 **읽어 줄 말(TTS)** 을 둘 수 있다(사장님 "tts 문구로 하나씩 지정 — 고정댓글에 링크를 눌러주세요! 행복한 하루 되세요~").
    작업의 성우(voice)로 한 번 합성해 영상 머리(0.4초)에 얹는다. 글이 비면 무음.
★표식: 만든 파일 옆에 link_longform.json 을 남긴다(규칙 판·문구·원본 수정시각). 표식이 지금과 다르면 옛 파일로 본다.
"""
import json
import os
import sys
import time
from pathlib import Path

from shopping_shorts import video_assemble

OUT_W, OUT_H = 1920, 1080
RULE = "link_longform_v4"                 # 구도·문구 그리는 법이 바뀌면 올린다 → 옛 파일은 자동으로 다시 만든다
OUT_NAME = "final_longform.mp4"
META_NAME = "link_longform.json"
_TMP_NAME = "final_longform.tmp.mp4"
_ERR_NAME = "link_longform.err"
_STALE_TMP_SEC = 15 * 60                  # 만드는 중 표시가 이보다 오래됐으면 죽은 작업으로 본다

# 안내 문구 — 링크를 어디에 둘지는 고객마다 다르다(댓글 / 설명란). 자유 입력은 받지 않는다(화면 밖으로 넘친다).
TEXTS = {
    "comment": "구매링크 댓글에 있습니다",
    "desc": "구매링크 설명란에 있습니다",
}
DEFAULT_WHERE = "comment"

# ── 꾸민 안내(관제 133, 2026-10-06 사장님 "문구 띠 + 큰 화살표, 자유롭게 놓기") ──────────────────────────
#   장면꾸미기 「롱폼」 탭에서 놓은 항목 목록. 작업 폴더의 LAYOUT_NAME 에 둔다. 있으면 고정 문구 대신 이 항목을 굽는다.
#   ★범위 검사는 여기 한 곳(normalize_layout). 그리기는 화면과 같은 코드(out/link-longform-stage.html)를 헤드리스로 찍는다.
LAYOUT_NAME = "link_longform_layout.json"
FPS = 30
LOOP_FRAMES = 72                          # 움직임 한 바퀴 = 2.4초(out/link-longform-blocks.js LOOP_MS) — 시계가 없으면 이만큼만 찍어 돌린다
_BLOCKS = ("band", "arrow")
_TONES = ("red", "yellow", "black", "blue", "purple", "green")
_ITEM_MAX = 8
_TEXT_MAX = 24
_TTS_MAX = 80                              # 읽어 줄 말 글자 수 상한(한 숨에 읽을 길이)
TTS_DELAY_MS = 400                        # 영상 머리에서 이만큼 뒤에 말이 시작된다
_CLOCK_MAX = 99 * 60 + 59
_ROOT = Path(__file__).resolve().parents[1]


def normalize_layout(raw):
    """화면이 보낸 항목 목록 → 저장·렌더에 쓸 목록. 모르는 블록·이상한 값은 통째로 버린다(엉뚱한 자리에 그리느니 안 그린다)."""
    out = []
    for m in (raw or [])[:_ITEM_MAX]:
        if not isinstance(m, dict) or m.get("block") not in _BLOCKS:
            continue
        try:
            l, t, w = float(m.get("l", 0)), float(m.get("t", 0)), float(m.get("w", 0))
        except (TypeError, ValueError):
            continue
        if not (3 <= w <= 110 and -20 <= l <= 100 and -20 <= t <= 100):
            continue
        item = {"kind": "block", "block": m["block"], "l": round(l, 2), "t": round(t, 2), "w": round(w, 2),
                "tone": m.get("tone") if m.get("tone") in _TONES else "red"}
        if m["block"] == "band":
            for k in ("pre", "hot", "post"):
                item[k] = str(m.get(k) or "")[:_TEXT_MAX]
            try:
                clock = int(m.get("clock") or 0)
            except (TypeError, ValueError):
                clock = 0
            if 0 < clock <= _CLOCK_MAX:
                item["clock"] = clock
            tts = " ".join(str(m.get("tts") or "").split())[:_TTS_MAX]
            if tts:
                item["tts"] = tts
            if not (item["pre"] or item["hot"] or item["post"] or item.get("clock")):
                continue
        out.append(item)
    return out


def load_layout(job_dir):
    """저장해 둔 항목 목록(없거나 깨졌으면 빈 목록 = 고정 문구로 굽는다)."""
    try:
        return normalize_layout(json.loads((Path(job_dir) / LAYOUT_NAME).read_text(encoding="utf-8")).get("items"))
    except (OSError, ValueError, AttributeError):
        return []


def save_layout(job_dir, raw):
    """항목 목록 저장. 빈 목록이면 파일을 지운다(고정 문구로 돌아간다). 저장된 목록을 돌려준다."""
    items = normalize_layout(raw)
    p = Path(job_dir) / LAYOUT_NAME
    if items:
        p.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    elif p.exists():
        p.unlink()
    return items


def overlay_frames(items, out_dir, frames, timeout=900):
    """항목을 투명 PNG(1920x1080)로 찍는다 — frames = 프레임 번호 목록(30fps). 파일 이름 = 번호 5자리.
    검사 도구(tools/link_longform_check.py)도 같은 함수로 '그 시각의 안내 그림'을 다시 뽑아 완성본과 대조한다."""
    import subprocess
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    req = out_dir / "request.json"
    req.write_text(json.dumps({"items": items, "output": str(out_dir), "frames": [int(f) for f in frames], "fps": FPS},
                              ensure_ascii=False), encoding="utf-8")
    env = os.environ.copy()
    if sys.platform.startswith("linux"):
        env.setdefault("SCENE_STYLE_NO_SANDBOX", "1")      # scene_style.render_layers 와 같은 까닭(운영 Ubuntu AppArmor)
    run = subprocess.run(["node", str(_ROOT / "tools/render_link_longform.js"), str(req)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    if run.returncode:
        raise RuntimeError("롱폼 안내 그림 생성 실패: " + run.stderr[-800:])
    return out_dir


def tts_text(items):
    """읽어 줄 말 — 문구 띠에 적힌 것. 띠가 여럿이면 첫 띠의 것. 없으면 빈 글(무음)."""
    for m in items:
        if m.get("block") == "band" and m.get("tts"):
            return m["tts"]
    return ""


def synthesize_tts(text, out_path, voice=None, customer_id=0):
    """읽어 줄 말을 작업의 성우로 합성한다 — 렌더·미리듣기와 같은 길(mix_pipeline.synthesize_line). 실패는 그대로 올린다(조용히 무음으로 가지 않는다)."""
    from shopping_shorts import mix_pipeline
    mix_pipeline.synthesize_line(text, Path(out_path), voice=voice, customer_id=customer_id)
    return Path(out_path)


def frame_count(items, dur):
    """찍을 프레임 수 — 시계가 있으면 영상 길이만큼(초마다 숫자가 다르다), 없으면 한 바퀴(LOOP_FRAMES)만 찍어 돌린다."""
    if any(m.get("clock") for m in items):
        return int(float(dur) * FPS) + 2             # 끝 프레임까지 덮는다(모자라면 되풀이돼 시계가 30:00 으로 튄다)
    return LOOP_FRAMES


_FONT = video_assemble._FONT_DIR / "GmarketSansBold.otf"
_YELLOW = (255, 236, 0, 255)
_RED = (235, 28, 36, 255)
_BLACK = (0, 0, 0, 255)


def text_for(where):
    """고른 자리(comment/desc) → 화면 문구. 모르는 값이면 기본(댓글)."""
    return TEXTS.get(str(where or ""), TEXTS[DEFAULT_WHERE])


def fg_width(src_w, src_h):
    """가운데 쇼츠의 가로 폭(짝수). 높이를 1080에 맞춘다. 검사 도구도 이 값을 쓴다."""
    w = int(round(OUT_H * float(src_w) / float(src_h)))
    return max(2, w - (w % 2))


def band_box():
    """문구 띠의 세로 범위 (y0, y1) — 검사 도구가 '가운데가 원본과 같은가'를 띠 밖에서 잰다."""
    return 500, 700


def paths(job_dir):
    d = Path(job_dir)
    return {"out": d / OUT_NAME, "meta": d / META_NAME, "tmp": d / _TMP_NAME, "err": d / _ERR_NAME}


def _arrow(draw, cx, top, w=150, h=190):
    """아래를 가리키는 빨간 화살표(검은 테두리)."""
    sw, hh = w * 0.42, h * 0.48                      # 몸통 폭, 머리 높이
    pts = [(cx - sw / 2, top), (cx + sw / 2, top), (cx + sw / 2, top + h - hh),
           (cx + w / 2, top + h - hh), (cx, top + h), (cx - w / 2, top + h - hh),
           (cx - sw / 2, top + h - hh)]
    draw.polygon(pts, fill=_RED, outline=_BLACK)
    draw.line(pts + [pts[0]], fill=_BLACK, width=6, joint="curve")


def draw_overlay(out_png, text, fg_w):
    """문구+화살표를 투명 PNG(1920x1080)로 그린다. ffmpeg drawtext 대신 그림으로 얹는다 —
    글꼴 경로 이스케이프가 윈도우·리눅스에서 달라 어긋나던 길을 아예 안 탄다."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y0, y1 = band_box()
    # 글자: 화면 폭의 62% 안에 들어가는 가장 큰 크기(문구가 길어져도 안 넘친다)
    size = 120
    while size > 40:
        font = ImageFont.truetype(str(_FONT), size)
        l, t, r, b = d.textbbox((0, 0), text, font=font, stroke_width=max(6, size // 10))
        if (r - l) <= OUT_W * 0.62 and (b - t) <= (y1 - y0) - 20:
            break
        size -= 4
    sw = max(6, size // 10)
    l, t, r, b = d.textbbox((0, 0), text, font=font, stroke_width=sw)
    tx = (OUT_W - (r - l)) / 2 - l
    ty = (y0 + y1) / 2 - (b - t) / 2 - t
    d.text((tx, ty), text, font=font, fill=_YELLOW, stroke_width=sw, stroke_fill=_BLACK)
    # 화살표: 양옆 흐린 여백 한가운데. 여백이 좁으면(정사각에 가까운 원본) 글자와 겹치니 그리지 않는다.
    side = (OUT_W - fg_w) / 2
    text_left = (OUT_W - (r - l)) / 2
    cx = min(side / 2, text_left / 2)
    if cx >= 90:
        _arrow(d, cx, 250)
        _arrow(d, OUT_W - cx, 250)
    img.save(str(out_png))
    return {"font_px": size, "arrows": cx >= 90}


def _src_sig(src):
    st = os.stat(src)
    return {"src_mtime_ns": st.st_mtime_ns, "src_size": st.st_size}


def is_fresh(job_dir, src, where):
    """만들어 둔 롱폼이 '지금 완성본 + 지금 문구 + 지금 규칙'으로 만든 것인가. 판단은 여기 한 곳."""
    p = paths(job_dir)
    if not (p["out"].exists() and p["meta"].exists() and src and Path(src).exists()):
        return False
    try:
        meta = json.loads(p["meta"].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    want = dict(_src_sig(src), rule=RULE, text=text_for(where), layout=load_layout(job_dir))
    return all(meta.get(k) == v for k, v in want.items())


def state(job_dir, src, where):
    """화면이 물어볼 상태: ready / running / error / none (+ 사유)."""
    p = paths(job_dir)
    if is_fresh(job_dir, src, where):
        return {"state": "ready"}
    if p["tmp"].exists() and (time.time() - p["tmp"].stat().st_mtime) < _STALE_TMP_SEC:
        return {"state": "running"}
    if p["err"].exists():
        try:
            return {"state": "error", "error": p["err"].read_text(encoding="utf-8")[:300]}
        except OSError:
            return {"state": "error", "error": "만들지 못했어요"}
    return {"state": "none"}


def mark_running(job_dir):
    """'만드는 중' 표시를 먼저 세운다 — 굽기가 실제로 시작되기 전에 화면이 물어도 running 으로 답하게."""
    p = paths(job_dir)
    if p["err"].exists():
        p["err"].unlink()
    p["tmp"].touch()


def render_link_longform(src, job_dir, where=DEFAULT_WHERE, voice=None, customer_id=0):
    """완성 쇼츠(src) → 구매링크용 가로 영상. 만든 파일 경로를 돌려준다. 실패하면 예외(사유를 .err 에도 남긴다).

    화면 구성: 뒤 = 같은 영상을 화면 가득 키워 흐리게 / 가운데 = 원본 쇼츠(높이 1080) / 위 = 문구+화살표.
    소리 = 읽어 줄 말(TTS)이 있으면 그것만(영상 머리에 한 번), 없으면 무음. 길이·프레임 수는 원본과 같다(30fps 고정은 완성본과 같은 규격).
    """
    from shopping_shorts import mix_pipeline
    p = paths(job_dir)
    text = text_for(where)
    items = load_layout(job_dir)                      # 꾸민 안내가 있으면 그걸 굽는다(없으면 고정 문구)
    frames_dir = Path(job_dir) / "link_longform_frames"
    tts_mp3 = Path(job_dir) / "link_longform_tts.mp3"
    speech = tts_text(items)
    sig = _src_sig(src)                               # 굽기 **전** 원본 서명 — 굽는 중 재렌더되면 표식이 어긋나 옛 것으로 판정된다
    w, h, dur = mix_pipeline._probe_wh_dur(src)
    fg_w = fg_width(w, h)
    png = Path(job_dir) / "link_longform_overlay.png"
    try:
        if p["err"].exists():
            p["err"].unlink()
        if items:
            n = frame_count(items, dur)
            overlay_frames(items, frames_dir, range(n), timeout=int(min(900, 180 + n * 0.6)))
            info = {"frames": n}
            # 프레임 묶음을 끝까지 되풀이해 얹는다(시계가 있으면 영상 길이만큼 찍었으므로 되풀이되지 않는다)
            overlay_in = ["-stream_loop", "-1", "-framerate", str(FPS), "-i", str(frames_dir / "%05d.png")]
        else:
            info = draw_overlay(png, text, fg_w)
            overlay_in = ["-loop", "1", "-framerate", "30", "-i", str(png)]
        fc = (
            # 흐린 배경: 작게 줄여 흐리고 다시 키운다(1920 폭에서 직접 흐리는 것보다 몇 배 빠르다)
            "[0:v]split=2[a][b];"
            "[a]scale=480:270:force_original_aspect_ratio=increase,crop=480:270,boxblur=10:2,"
            f"scale={OUT_W}:{OUT_H},eq=brightness=-0.06[bg];"
            f"[b]scale={fg_w}:{OUT_H}[fg];"
            "[bg][fg]overlay=(W-w)/2:0[v1];"
            # ★문구 그림은 한 장이라 끝까지 반복해 줘야 한다(-loop 1) — 안 하면 앞 몇 초만 뜨고 사라진다
            #   (2026-10-05 실측: 0.5초엔 있고 12초엔 없었다. 검사 도구가 잡았다). 길이는 영상이 정한다(shortest).
            "[v1][1:v]overlay=0:0:shortest=1,format=yuv420p[v]"
        )
        audio_in, audio_map = [], ["-an"]
        if speech:
            synthesize_tts(speech, tts_mp3, voice=voice, customer_id=customer_id)
            info["tts"] = speech
            audio_in = ["-i", str(tts_mp3)]
            # 말은 머리에 한 번. apad 로 끝까지 무음을 채우고 길이는 영상이 정한다(-shortest)
            fc += f";[2:a]adelay={TTS_DELAY_MS}|{TTS_DELAY_MS},apad[a]"
            audio_map = ["-map", "[a]", "-c:a", "aac", "-b:a", "128k", "-shortest"]
        cmd = ["ffmpeg", "-y", "-i", str(src), *overlay_in, *audio_in,
               "-filter_complex", fc,
               "-map", "[v]", *audio_map, "-r", "30",
               "-c:v", "libx264", "-preset", video_assemble._preset(), "-crf", video_assemble._crf(),
               *video_assemble._threads_args(), "-movflags", "+faststart", str(p["tmp"])]
        video_assemble._run_ffmpeg(cmd)
        os.replace(str(p["tmp"]), str(p["out"]))
        p["meta"].write_text(json.dumps(dict(sig, rule=RULE, text=text, fg_w=fg_w, layout=items, **info),
                                        ensure_ascii=False), encoding="utf-8")
        return p["out"]
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        try:
            p["err"].write_text(str(e)[:300], encoding="utf-8")
        except OSError:
            pass
        raise
    finally:
        for f in (p["tmp"], png, tts_mp3):
            try:
                if f.exists():
                    f.unlink()
            except OSError:
                pass
        import shutil
        shutil.rmtree(frames_dir, ignore_errors=True)
