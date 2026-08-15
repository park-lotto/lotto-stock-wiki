# -*- coding: utf-8 -*-
"""롱폼 영상 하나를 쇼츠 여러 편으로 자르는 파이프라인(2026-08-15 신설).

흐름은 4단계다. 각 단계는 앞 단계의 산출만 보고 돈다 — 중간에서 끊어 다시 시작할 수 있다.

    ① transcribe_longform : 롱폼 → 타임코드가 붙은 전사 구간 목록
    ② plan_shorts         : 전사 → 쇼츠 N편의 설계(구간·훅·콜드오픈·자막)
    ③ snap_captions       : 자막 시각을 실제 전사 경계에 맞춘다(순수 계산, 무과금)
    ④ render_short        : 설계 하나 → 9:16 mp4

★왜 ①이 조각내서 도는가(2026-08-15 실측). 12분(741초) 영상을 통째로 올리니 Gemini가
  504 DEADLINE_EXCEEDED로 죽었다. 150초씩 5조각으로 나눠 병렬로 올리고 타임코드에
  오프셋을 더해 이어붙이니 139구간이 정상으로 나왔다. 롱폼은 정의상 길기 때문에
  "통째로 한 번"은 성공하는 게 우연이고, 조각내기가 기본 경로다.

★왜 ③이 따로 있는가. ②의 자막 시각은 LLM이 눈대중으로 5초씩 균등 배분한 값이라
  실제 말이 끊기는 지점과 어긋난다. 전사(①)에 진짜 경계가 이미 있으므로 거기에
  붙이면 된다 — 추가 호출도 과금도 없다. LLM에게 "정확히 맞춰라"를 시키는 것보다
  계산으로 맞추는 쪽이 항상 정확하다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHUNK_SECONDS = 150          # 조각 길이. 이보다 길면 504가 나기 시작한다(실측 741초=사망)
CHUNK_WORKERS = 3            # 동시 업로드 수. 늘리면 429가 몰린다(autoload와 같은 이유)
COLD_OPEN_MIN_OFFSET = 8.0   # 콜드오픈은 구간 시작에서 이만큼 뒤에서 고른다(아래 설명)
HOLD_SECONDS = 1.5           # 맨 앞 '하이라이트 카드' 정지 시간(_hold 주석 참고)
BUMPER_SECONDS = 0.8         # 하이라이트와 본문 사이에 끼우는 로고 범퍼(_bumper 주석 참고)


# ────────────────────────────────────────────────────────────
# ① 전사
# ────────────────────────────────────────────────────────────
def _cut(src, start, dur, dst):
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "34", "-vf", "scale=480:-2",
         "-r", "8", "-c:a", "aac", "-b:a", "48k", str(dst), "-loglevel", "error"],
        check=True)


def transcribe_longform(video_path, work_dir=None, chunk_seconds=CHUNK_SECONDS):
    """롱폼 → [{start,end,text,scene_desc,motion_level,...}] (전체 기준 초).

    조각별 실패는 그 조각만 버리고 나머지를 살린다 — 12분 중 2분이 안 되는 것보다
    10분이라도 확보하는 게 낫다. 어느 조각이 빠졌는지는 stderr로 남긴다.
    """
    from shopping_shorts.script_extract import extract_script

    work = Path(work_dir or tempfile.mkdtemp(prefix="lfshorts_"))
    work.mkdir(parents=True, exist_ok=True)
    total = _duration(video_path)
    n = max(1, int(total // chunk_seconds) + (1 if total % chunk_seconds else 0))

    def one(i):
        dst = work / f"chunk{i}.mp4"
        try:
            _cut(video_path, i * chunk_seconds, chunk_seconds, dst)
            return i, extract_script(str(dst), f"lf{i}")
        except Exception as exc:                      # noqa: BLE001 — 조각 하나가 전체를 죽이지 않는다
            print(f"[longform] chunk {i} 실패: {exc}", file=sys.stderr)
            return i, None

    with ThreadPoolExecutor(max_workers=min(CHUNK_WORKERS, n)) as ex:
        got = dict(ex.map(one, range(n)))

    segs = []
    for i in range(n):
        r = got.get(i)
        if not r:
            continue
        off = i * chunk_seconds
        for s in (r.get("segments") or []):
            s = dict(s)
            s["start"] = round(float(s.get("start") or 0) + off, 1)
            s["end"] = round(float(s.get("end") or 0) + off, 1)
            segs.append(s)
    segs.sort(key=lambda s: s["start"])
    return segs


def _duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


# ────────────────────────────────────────────────────────────
# ② 설계
# ────────────────────────────────────────────────────────────
# ★콜드오픈 제약이 왜 프롬프트에 박혀 있나(2026-08-15 실측). 제약 없이 시켰더니 5편 중
#   2편이 cold_open을 **구간 시작과 같은 지점**으로 골랐다(0.0~5.4, 352~358). 그러면
#   같은 화면이 연달아 두 번 나올 뿐 콜드오픈이 아니다. "뒤쪽에서 고르라"를 문장으로
#   못박고, 아래 _fix_cold_open이 계산으로 한 번 더 강제한다(LLM이 어겨도 결과가 옳게).
_PROMPT = """아래는 유튜브 롱폼의 전사문이다. [시작초-끝초] 타임코드가 붙어 있고,
일부 줄에는 (화면: ...) 로 그 순간 화면에 무엇이 보이는지 적혀 있다.

이 영상에서 **쇼츠로 잘라 올렸을 때 가장 잘 터질 구간 {n}개**를 골라라.

선별 기준(중요도 순):
1. 그 구간만 떼어 봐도 말이 되는가 — 앞뒤 맥락 없이 이해되는가
2. 첫 3초에 사람을 멈추게 할 문장이 있는가
3. 숫자·대비·반전·단정적 주장이 있는가
4. 감정이 실렸는가 — 답답함·놀람·확신
5. **화면이 볼 만한가** — (화면: ...) 설명을 보고, 검은 배경에 글자만 뜨거나
   변화 없이 정지된 구간은 피하라. 사람이 나오거나 화면이 움직이는 구간을 우선하라.

각 구간은 25~45초. 서로 겹치지 마라.

각 구간마다 아래를 내라:
- start, end: 초 (전사문 타임코드 기준)
- why: 왜 이 구간인가 (한 문장)
- screen: 이 구간 화면이 볼 만한 이유 (한 문장)
- cold_open: {{start, end}} — 맨 앞에 복제해 붙일 가장 센 3~7초.
  ★반드시 구간 시작보다 {off}초 이상 뒤에서 골라라. 구간 앞부분을 그대로 고르면
  같은 장면이 두 번 나와 아무 효과가 없다. 구간 후반의 결정적 순간을 골라라.
- headline: [1줄, 2줄] — 상단 헤드카피. 각 줄 12자 이내. 2줄째가 훅
- captions: [{{start, end, line1, line2}}] — 요약 자막. 각 줄 12자 이내,
  둘째 줄이 없으면 빈 문자열. 전사를 그대로 옮기지 말고 짧게 압축하라.

반드시 {{"shorts":[...]}} 형태의 JSON만 출력하라.

전사문:
"""


def _transcript_block(segs):
    out = []
    for s in segs:
        t = (s.get("text") or "").strip()
        if not t:
            continue
        line = f"[{s['start']}-{s['end']}] {t}"
        sd = (s.get("scene_desc") or "").strip()
        if sd:
            line += f"  (화면: {sd})"
        out.append(line)
    return "\n".join(out)


def plan_shorts(segs, n_shorts=5, api_key=None, model=None):
    """전사 구간 → {"shorts":[...]}. 콜드오픈은 반환 전에 계산으로 교정한다.

    ★키를 하나만 쓰지 않는다(2026-08-15 실측). 처음엔 SHORTS_GEMINI_KEYS[0]만 썼는데
      429 RESOURCE_EXHAUSTED로 막혔다 — 무료 등급은 모델별 일일 20건이라 키 하나로는
      금방 닿는다. 키가 여러 개 있는데 첫 번째만 보는 것은 그냥 낭비다. 다른 경로
      (script_extract·comment_gen)도 전부 로테이션을 쓴다 — 여기만 다르게 짤 이유가 없다.
    """
    from google import genai
    from shopping_shorts.config import SHORTS_GEMINI_KEYS
    from shopping_shorts.video_analysis import _MODEL

    keys = [api_key] if api_key else list(SHORTS_GEMINI_KEYS)
    if not keys:
        raise RuntimeError("longform_shorts: SHORTS_GEMINI_KEY가 설정되지 않았습니다")
    prompt = _PROMPT.format(n=n_shorts, off=int(COLD_OPEN_MIN_OFFSET)) + _transcript_block(segs)
    last = None
    for i, key in enumerate(keys):
        try:
            cl = genai.Client(api_key=key)
            r = cl.models.generate_content(
                model=model or _MODEL, contents=prompt,
                config={"response_mime_type": "application/json"})
            break
        except Exception as exc:                  # noqa: BLE001 — 다음 키로 넘어간다
            last = exc
            print(f"[longform] key #{i} 실패({type(exc).__name__}), 다음 키로", file=sys.stderr)
    else:
        raise RuntimeError(f"longform_shorts: 키 {len(keys)}개 모두 실패 — {last}")
    plan = json.loads(r.text)
    for sh in plan.get("shorts") or []:
        _fix_cold_open(sh)
        sh["captions"] = snap_captions(sh.get("captions") or [], segs, sh["start"], sh["end"])
    return plan


def _fix_cold_open(sh):
    """콜드오픈이 구간 앞부분이면 뒤쪽으로 밀어낸다(LLM이 제약을 어겨도 결과는 옳게).

    앞부분을 복제하면 같은 화면이 연달아 두 번 나온다 — 콜드오픈의 목적(뒤의 결정적
    장면을 먼저 보여줘 끝까지 보게 만들기)이 통째로 사라진다. 그래서 규칙을 말로만
    두지 않고 여기서 강제한다.
    """
    s, e = float(sh["start"]), float(sh["end"])
    co = sh.get("cold_open") or {}
    cs, ce = float(co.get("start", s)), float(co.get("end", s + 5))
    dur = max(3.0, min(7.0, ce - cs))
    if cs < s + COLD_OPEN_MIN_OFFSET:
        # 구간 후반부(뒤에서 1/3 지점)로 옮긴다. 끝은 넘지 않는다.
        cs = max(s + COLD_OPEN_MIN_OFFSET, e - (e - s) / 3.0)
        cs = min(cs, e - dur)
        sh["cold_open_fixed"] = True        # 조용히 고치지 않는다 — 화면이 알 수 있게
    sh["cold_open"] = {"start": round(cs, 1), "end": round(min(cs + dur, e), 1)}
    return sh


# ────────────────────────────────────────────────────────────
# ③ 자막 스냅
# ────────────────────────────────────────────────────────────
def snap_captions(caps, segs, win_start, win_end, tol=2.5):
    """자막 시각을 가장 가까운 전사 경계에 붙인다(순수 계산·무과금).

    LLM은 자막 시각을 5초씩 균등 배분하는 버릇이 있어 실제 말이 끊기는 지점과 어긋난다
    (2026-08-15 실측: 572/577/582/588/592/597 — 전부 5초 간격). 전사에는 진짜 경계가
    이미 있으므로 tol초 안에 경계가 있으면 그리로 당긴다. 없으면 원래 값을 둔다
    (억지로 붙이면 오히려 더 어긋난다).
    """
    marks = sorted({float(s["start"]) for s in segs} | {float(s["end"]) for s in segs})
    marks = [m for m in marks if win_start - tol <= m <= win_end + tol]
    if not marks:
        return caps

    def snap(v):
        best = min(marks, key=lambda m: abs(m - v))
        return round(best, 1) if abs(best - v) <= tol else round(float(v), 1)

    out = []
    for c in caps:
        cs, ce = snap(c.get("start", win_start)), snap(c.get("end", win_end))
        if ce <= cs:                       # 스냅이 순서를 뒤집으면 원본을 쓴다
            cs, ce = round(float(c.get("start", win_start)), 1), round(float(c.get("end", win_end)), 1)
        out.append({**c, "start": cs, "end": ce})
    return out


# ────────────────────────────────────────────────────────────
# ④ 렌더
# ────────────────────────────────────────────────────────────
# 템플릿은 '코드'가 아니라 '값'이다 — 새 디자인 추가는 이 사전에 항목 하나를 더하는 일이고
# 아래 렌더 함수는 손대지 않는다(2026-08-15 사장님: "템플릿은 갈아끼우면 되는 거니").
TEMPLATES = {
    "cinema_gold": {
        "label": "블러시네마 · 금",
        "blur_bg": True, "bg": None,
        "line": "0xF5C451", "h1": "white", "h2": "0xF5C451",
        "cap1": "white", "cap2": "0x3EE0BF", "ch": "white",
        "head_x": 60, "head_align": "left",
    },
    "dark_yellow": {
        "label": "형광강조 · 노랑",
        "blur_bg": False, "bg": "black",
        "line": None, "h1": "white", "h2": "0xFFE14D",
        "cap1": "white", "cap2": "0xFFE14D", "ch": "white",
        "head_x": 100, "head_align": "left",
    },
    "dark_red": {
        "label": "레드임팩트",
        "blur_bg": False, "bg": "black",
        "line": None, "h1": "0xE01B24", "h2": "white",
        "cap1": "white", "cap2": "0xE01B24", "ch": "0xAAAAAA",
        "head_x": None, "head_align": "center",
    },
    "terminal_mint": {
        "label": "터미널 · 민트",
        "blur_bg": False, "bg": "0x0A1220",
        "line": "0x3EE0BF", "h1": "white", "h2": "0x3EE0BF",
        "cap1": "white", "cap2": "0x3EE0BF", "ch": "0x3EE0BF",
        "head_x": 60, "head_align": "left",
    },
}
DEFAULT_TEMPLATE = "cinema_gold"

_FONT = os.environ.get("LFSHORTS_FONT", r"C\:/Windows/Fonts/malgunbd.ttf")
VIDEO_TOP = 656          # 1080x608(16:9)을 1920 캔버스 정중앙에 놓는 y좌표


def _txtfile(work, name, text):
    p = Path(work) / f"{name}.txt"
    p.write_text(text or "", encoding="utf-8")
    # ffmpeg 필터 인자에 들어가므로 슬래시로 통일하고 드라이브 콜론을 이스케이프한다
    return str(p).replace("\\", "/").replace(":", chr(92)+":", 1)


def render_short(video_path, short, out_path, template=DEFAULT_TEMPLATE,
                 channel_name="", work_dir=None, cta="SUBSCRIBE", logo_path=None):
    """설계 1편 → 9:16 mp4. 콜드오픈을 앞에 붙이고 템플릿을 입힌다."""
    tpl = TEMPLATES.get(template) or TEMPLATES[DEFAULT_TEMPLATE]
    work = Path(work_dir or tempfile.mkdtemp(prefix="lfrender_"))
    work.mkdir(parents=True, exist_ok=True)
    s, e = float(short["start"]), float(short["end"])
    co = short.get("cold_open") or {}
    cs, ce = float(co.get("start", s)), float(co.get("end", s))
    cold_len = max(0.0, round(ce - cs, 1))

    # 4-1) 조각을 잘라 이어붙인다(훅 카드 + 콜드오픈 + 본편). 재인코딩해야 concat이 안전하다.
    parts = []
    if HOLD_SECONDS > 0:
        _hold(video_path, cs if cold_len > 0 else s, HOLD_SECONDS, work / "hold.mp4")
        parts.append("hold.mp4")
    if cold_len > 0:
        _reenc(video_path, cs, cold_len, work / "co.mp4")
        parts.append("co.mp4")
        # 하이라이트 → 본문 사이 로고 범퍼. 이게 없으면 같은 장면이 두 번 이어져
        # "영상이 되감겼나?"로 읽힌다(잘 되는 채널들이 여기에 로고·전환을 끼운다).
        if BUMPER_SECONDS > 0:
            _bumper(BUMPER_SECONDS, work / "bump.mp4", channel_name, tpl, logo_path)
            parts.append("bump.mp4")
    _reenc(video_path, s, e - s, work / "main.mp4")
    parts.append("main.mp4")
    (work / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    joined = work / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"),
                    "-c", "copy", str(joined), "-loglevel", "error"], check=True)

    bump_len = BUMPER_SECONDS if cold_len > 0 else 0.0
    total = HOLD_SECONDS + cold_len + bump_len + (e - s)
    fg = _filtergraph(work, short, tpl, cold_len, s, total, channel_name, cta, bump_len)
    (work / "fg.txt").write_text(fg, encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-i", str(joined), "-filter_complex_script", str(work / "fg.txt"),
                    "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "23", "-c:a", "aac", str(out_path), "-loglevel", "error"], check=True)
    return {"path": str(out_path), "seconds": round(total, 1), "cold_open_seconds": cold_len,
            "hold_seconds": HOLD_SECONDS, "bumper_seconds": bump_len}


def _hold(src, at, dur, dst):
    """맨 앞에 세울 '훅 카드' — 그 지점의 정지 화면 + 무음을 dur초.

    ★왜 필요한가(2026-08-15 사장님 지적). 이게 없으면 0초부터 영상이 곧바로 움직이는데,
      상단 훅 문구를 읽기도 전에 화면이 튀어 **재생 오류처럼 보인다**. 1.5초만 정지해
      두면 눈이 훅을 먼저 읽고, 그 다음 콜드오픈이 시작되는 것으로 읽힌다.
      검은 화면이 아니라 **그 장면의 첫 프레임을 세워두는** 이유: 검은 화면은 '아직
      로딩 중'으로 보이고, 정지 프레임은 '멈춰 있다가 시작한다'로 보인다.

    ★한 번에 만들려다 틀렸다(2026-08-15). `-frames:v 1`을 출력 옵션으로 걸면 **결과가
      1프레임짜리**가 되어 홀드가 사실상 0초가 된다(실측: 0.3초와 1.0초 프레임이 서로
      달랐다 = 정지가 아니라 그냥 재생 중이었다). 그래서 두 단계로 나눈다:
      프레임을 png로 뽑고 → 그 png를 dur초 동안 반복해 영상으로 만든다.
    """
    still = Path(dst).with_suffix(".png")
    subprocess.run(["ffmpeg", "-y", "-ss", str(at), "-i", str(src), "-frames:v", "1",
                    str(still), "-loglevel", "error"], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-t", str(dur), "-i", str(still),
         "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v:0", "-map", "1:a:0", "-r", "30",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "48000", "-shortest", str(dst), "-loglevel", "error"],
        check=True)


def _bumper(dur, dst, channel_name, tpl, logo_path=None):
    """하이라이트와 본문 사이에 끼우는 짧은 로고 화면.

    ★왜 넣나(2026-08-15 사장님 지적). 하이라이트를 앞에 복제해 붙이면 그 장면이 본문에서
      곧 다시 나온다 — 사이에 아무것도 없으면 "영상이 되감겼나?"로 읽혀 오류처럼 보인다.
      잘 되는 채널들은 여기에 로고나 전환 장면을 0.5~1초 끼워 "여기서부터 본편"이라는
      구분을 준다. 로고 이미지가 있으면 그걸 쓰고, 없으면 채널명 카드로 대신한다.
    """
    bg = tpl.get("bg") or "black"
    accent = tpl.get("line") or tpl.get("h2") or "white"
    if logo_path and Path(logo_path).exists():
        vin = ["-loop", "1", "-t", str(dur), "-i", str(logo_path)]
        vf = (f"scale=560:-1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:{bg},"
              f"format=yuv420p")
    else:
        card = Path(dst).with_suffix(".txt")
        card.write_text(channel_name or " ", encoding="utf-8")
        tf = str(card).replace("\\", "/").replace(":", chr(92) + ":", 1)
        vin = ["-f", "lavfi", "-t", str(dur), "-i", f"color=c={bg}:s=1080x1920:r=30"]
        vf = (f"drawtext=fontfile='{_FONT}':textfile='{tf}':fontsize=64:fontcolor=white"
              f":x=(w-tw)/2:y=(h-th)/2,"
              f"drawbox=x=390:y=1080:w=300:h=8:color={accent}:t=fill,format=yuv420p")
    subprocess.run(
        ["ffmpeg", "-y", *vin,
         "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v:0", "-map", "1:a:0", "-r", "30", "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "48000", "-shortest", str(dst), "-loglevel", "error"],
        check=True)


def _reenc(src, start, dur, dst):
    subprocess.run(["ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-ar", "48000", str(dst), "-loglevel", "error"], check=True)


def _dt(src, dst, tf, size, color, x, y, enable=None, border=(4, "black")):
    b = f":borderw={border[0]}:bordercolor={border[1]}" if border else ""
    en = f":enable='{enable}'" if enable else ""
    return (f"[{src}]drawtext=fontfile='{_FONT}':textfile='{tf}':fontsize={size}"
            f":fontcolor={color}:x={x}:y={y}{b}{en}[{dst}];")


def _filtergraph(work, short, tpl, cold_len, win_start, total, channel_name, cta, bump_len=0.0):
    L = []
    if tpl["blur_bg"]:
        L += ["[0:v]split=2[a][b];",
              "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "gblur=sigma=50,eq=brightness=-0.55:saturation=0.4[bgb];",
              "[b]scale=1080:-2[fg];",
              f"[bgb][fg]overlay=0:{VIDEO_TOP}[p0];"]
    else:
        L += [f"[0:v]scale=1080:-2,pad=1080:1920:0:{VIDEO_TOP}:{tpl['bg']}[p0];"]
    cur = "p0"
    k = 0

    def nxt():
        nonlocal cur, k
        k += 1
        return f"z{k}"

    if tpl["line"]:
        for y in (0, 1912):
            d = nxt()
            L.append(f"[{cur}]drawbox=x=0:y={y}:w=1080:h=8:color={tpl['line']}:t=fill[{d}];")
            cur = d
    head = short.get("headline") or ["", ""]
    hx = "(w-tw)/2" if tpl["head_align"] == "center" else str(tpl["head_x"])
    for i, (line, col, y) in enumerate([(head[0], tpl["h1"], 300),
                                        (head[1] if len(head) > 1 else "", tpl["h2"], 400)]):
        if not line:
            continue
        d = nxt()
        L.append(_dt(cur, d, _txtfile(work, f"h{i}", line), 78, col, hx, y, border=(3, "black")))
        cur = d
    # 진행바 — "얼마나 남았나"가 보이면 이탈이 준다
    if tpl["line"]:
        d = nxt()
        L.append(f"[{cur}]drawbox=x=0:y=1330:w='1080*t/{total}':h=10:color={tpl['line']}:t=fill[{d}];")
        cur = d
    # 콜드오픈 구간 배지 — 같은 장면이 뒤에 또 나오는 이유를 보는 사람이 알게
    if cold_len > 0:
        d = nxt()
        # 배지는 훅 카드가 끝난 뒤(콜드오픈 구간)에만 뜬다
        _b0, _b1 = HOLD_SECONDS, HOLD_SECONDS + cold_len
        L.append(f"[{cur}]drawbox=x=60:y=170:w=210:h=64:color=0xE23B3B:t=fill"
                 f":enable='between(t,{_b0},{_b1})'[{d}];")
        cur = d
        d2 = nxt()
        L.append(_dt(cur, d2, _txtfile(work, "cobadge", "다시 보기"), 38, "white", 95, 182,
                     enable=f"between(t,{_b0},{_b1})", border=None))
        cur = d2
    # 자막 — 원본 타임라인 → 새 타임라인(콜드오픈 길이만큼 밀림)
    for i, c in enumerate(short.get("captions") or []):
        _off = HOLD_SECONDS + cold_len + bump_len
        a = float(c.get("start", win_start)) - win_start + _off
        b = float(c.get("end", win_start)) - win_start + _off
        for j, (line, col, y) in enumerate([(c.get("line1", ""), tpl["cap1"], 1420),
                                            (c.get("line2", ""), tpl["cap2"], 1500)]):
            if not line:
                continue
            d = nxt()
            L.append(_dt(cur, d, _txtfile(work, f"c{i}_{j}", line), 58, col,
                         "(w-tw)/2", y, enable=f"between(t,{a:.1f},{b:.1f})"))
            cur = d
    if channel_name:
        d = nxt()
        L.append(_dt(cur, d, _txtfile(work, "ch", channel_name), 46, tpl["ch"], 60, 1740, border=None))
        cur = d
    if cta:
        d = nxt()
        L.append(f"[{cur}]drawbox=x=700:y=1730:w=320:h=72:color=0xE23B3B:t=fill[{d}];")
        cur = d
        d2 = nxt()
        L.append(_dt(cur, d2, _txtfile(work, "cta", cta), 34, "white", 737, 1750, border=None))
        cur = d2
    # 마지막 출력 라벨을 [v]로 바꾼다
    L[-1] = L[-1].rsplit("[", 1)[0] + "[v]"
    return "\n".join(L)
