"""구매링크용 롱폼(가로) 판 — 완성 쇼츠를 1920x1080 화면 가운데에 넣고 안내 문구를 얹는다.

왜(2026-10-05 고객 황선희 → 사장님 "오른쪽에 롱폼으로 렌더를 활성화해줘", 관제 132):
  쇼츠에는 누를 수 있는 구매링크를 못 단다. 대신 쇼츠 아래 '관련 동영상'에 내 롱폼을 걸 수 있고,
  롱폼은 설명란·댓글 링크가 눌린다. 그래서 같은 쇼츠를 가로 영상으로 한 벌 더 만들어
  "구매링크 댓글에 있습니다"를 띄운다. 고객들은 이걸 캡컷에서 손으로 만들고 있었다.

★판단의 주인(0순위-C): 가로 화면 구도·문구 자리·파일 이름·"지금 것이 최신인가"는 전부 이 파일이 정한다.
  app.py 라우트와 화면은 여기 함수를 부르기만 한다.
★재렌더가 아니다: 이미 만든 final.mp4 한 편만 입력으로 받는다. 컷·자막·음성 판단을 다시 하지 않는다
  (소리는 그대로 복사). 그래서 완성본과 내용이 어긋날 수 없다.
★표식: 만든 파일 옆에 link_longform.json 을 남긴다(규칙 판·문구·원본 수정시각). 표식이 지금과 다르면 옛 파일로 본다.
"""
import json
import os
import sys
import time
from pathlib import Path

from shopping_shorts import video_assemble

OUT_W, OUT_H = 1920, 1080
RULE = "link_longform_v1"                 # 구도·문구 그리는 법이 바뀌면 올린다 → 옛 파일은 자동으로 다시 만든다
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
    want = dict(_src_sig(src), rule=RULE, text=text_for(where))
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


def render_link_longform(src, job_dir, where=DEFAULT_WHERE):
    """완성 쇼츠(src) → 구매링크용 가로 영상. 만든 파일 경로를 돌려준다. 실패하면 예외(사유를 .err 에도 남긴다).

    화면 구성: 뒤 = 같은 영상을 화면 가득 키워 흐리게 / 가운데 = 원본 쇼츠(높이 1080) / 위 = 문구+화살표.
    소리는 다시 굽지 않고 그대로 복사한다. 길이·프레임 수는 원본과 같다(30fps 고정은 완성본과 같은 규격).
    """
    from shopping_shorts import mix_pipeline
    p = paths(job_dir)
    text = text_for(where)
    sig = _src_sig(src)                               # 굽기 **전** 원본 서명 — 굽는 중 재렌더되면 표식이 어긋나 옛 것으로 판정된다
    w, h, _dur = mix_pipeline._probe_wh_dur(src)
    fg_w = fg_width(w, h)
    png = Path(job_dir) / "link_longform_overlay.png"
    try:
        if p["err"].exists():
            p["err"].unlink()
        info = draw_overlay(png, text, fg_w)
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
        cmd = ["ffmpeg", "-y", "-i", str(src), "-loop", "1", "-framerate", "30", "-i", str(png),
               "-filter_complex", fc,
               "-map", "[v]", "-map", "0:a?", "-r", "30",
               "-c:v", "libx264", "-preset", video_assemble._preset(), "-crf", video_assemble._crf(),
               *video_assemble._threads_args(), "-c:a", "copy", "-movflags", "+faststart", str(p["tmp"])]
        video_assemble._run_ffmpeg(cmd)
        os.replace(str(p["tmp"]), str(p["out"]))
        p["meta"].write_text(json.dumps(dict(sig, rule=RULE, text=text, fg_w=fg_w, **info),
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
        for f in (p["tmp"], png):
            try:
                if f.exists():
                    f.unlink()
            except OSError:
                pass
