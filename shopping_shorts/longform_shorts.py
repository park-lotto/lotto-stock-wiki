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
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHUNK_SECONDS = 150          # 조각 길이. 이보다 길면 504가 나기 시작한다(실측 741초=사망)
CHUNK_WORKERS = 3            # 동시 업로드 수. 늘리면 429가 몰린다(autoload와 같은 이유)


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
# ★콜드오픈(하이라이트 복제)은 2026-08-15에 폐기했다. 이 롱폼은 상당 부분이 '검은 배경 +
#   큰 자막'이라 "가장 센 구간"이 시각적으로는 글자 카드다. 그걸 앞에 복제해 붙이면 훅이
#   아니라 맥락 없는 도청이 되고, 같은 장면이 곧 또 나와 "되감겼나?"로 읽힌다. 문장 훅은
#   영상 복제가 아니라 **상단 헤드카피 텍스트**로 보여주는 게 이음매 0개로 같은 효과를 낸다.
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
- layout: "textcard" 또는 "screencast" — (화면: ...) 설명상 '검은 배경에 큰 자막이
  뜨는 화면'이면 textcard, 프로그램·웹 화면 녹화면 screencast.
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
    prompt = _PROMPT.format(n=n_shorts) + _transcript_block(segs)
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
        sh["captions"] = snap_captions(sh.get("captions") or [], segs, sh["start"], sh["end"])
    return plan


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
# ④ 렌더 (2026-08-15 전면 재작성)
# ────────────────────────────────────────────────────────────
# ★왜 갈아엎었나. 1차 설계는 "실사 영상"을 전제했다 — 하이라이트 정지 카드, 콜드오픈
#   복제, 로고 범퍼. 그런데 실제 롱폼은 **검은 배경 + 대형 자막**과 **자막이 이미 구워진
#   화면녹화**로 이뤄져 있었다. 그래서 전제가 통째로 어긋났다(실측된 증상):
#     - 자막 3중첩: 헤드카피 + 원본에 구워진 자막 + 우리 요약자막이 한 화면에
#     - 콜드오픈이 '검은 글자카드 7초'가 되어 훅이 아니라 맥락 없는 도청
#     - 정지 카드 1.2초: 오디오 완전 무음(-163 LUFS) + 1.05→1.00 역방향 줌 점프
#     - 로고 스팅이 9:16 화면 속 작은 16:9 띠 안에 갇힘
#     - 화면의 68%가 빈 검정 (잘 되는 채널들의 '여백 최소'와 정반대)
#   그래서 콜드오픈·정지카드·범퍼를 **전부 버리고** 아래 구조로 다시 짰다.
#
# 새 구조 — 이음매가 하나뿐이다(엔드카드 진입). 이음매가 적을수록 어색할 자리가 없다.
#     [ 본문 그대로 ] + [ 엔드카드 2초 ]
#       └ 첫 HEADLINE_SECONDS 동안만 상단에 헤드카피가 얹힌다(별도 클립이 아니다)
#       └ 오디오는 0.00초부터 나온다
#
# 화면은 원본 장면 성격에 따라 두 모드로 갈린다(_pick_layout):
#     textcard  : 원본이 '검은 배경 + 큰 자막' → 9:16으로 **꽉 채워** 크롭. 자막 안 얹는다
#                 (원본 글자가 이미 크게 살아난다. 여기에 또 얹으면 3중첩)
#     screencast: 원본이 화면녹화 UI → 5:4로 크롭해 **크게** 배치. 요약자막을 얹는다
#                 (1080x608로 줄이면 UI 글자가 뭉갠다 — 원본 픽셀을 살린다)

HEADLINE_SECONDS = 2.2       # 상단 헤드카피가 떠 있는 시간
ENDCARD_SECONDS = 2.0        # 마지막 채널 카드
SETTLE_FRAMES = 5            # 컷 직후 1.03→1.00 정착(하드컷을 매끄럽게)
LUFS_TARGET = -14.0          # 쇼츠 표준. 데드에어·볼륨 널뛰기를 여기서 잡는다

# 템플릿은 '값'이다 — 새 디자인은 항목 하나 추가, 렌더 함수는 안 건드린다.
TEMPLATES = {
    "mono_gold": {
        "label": "검정 · 금색",
        "bg": "black", "h1": "white", "h2": "0xF5C451",
        "cap1": "white", "cap2": "0xF5C451", "ch": "0xF5C451",
    },
    "mono_yellow": {
        "label": "검정 · 형광노랑",
        "bg": "black", "h1": "white", "h2": "0xFFE14D",
        "cap1": "white", "cap2": "0xFFE14D", "ch": "0xFFE14D",
    },
    "mono_red": {
        "label": "검정 · 레드",
        "bg": "black", "h1": "0xE01B24", "h2": "white",
        "cap1": "white", "cap2": "0xE01B24", "ch": "0xAAAAAA",
    },
    "mono_mint": {
        "label": "검정 · 민트",
        "bg": "black", "h1": "white", "h2": "0x3EE0BF",
        "cap1": "white", "cap2": "0x3EE0BF", "ch": "0x3EE0BF",
    },
}
DEFAULT_TEMPLATE = "mono_gold"

_FONT = os.environ.get("LFSHORTS_FONT", r"C\:/Windows/Fonts/malgunbd.ttf")
W, H = 1080, 1920


def _txtfile(work, name, text):
    p = Path(work) / f"{name}.txt"
    p.write_text(text or "", encoding="utf-8")
    return str(p).replace("\\", "/").replace(":", chr(92) + ":", 1)


# ── 레이아웃 판정 ────────────────────────────────────────────
_TEXTCARD_HINTS = ("검은 배경", "검정 배경", "검은색 배경", "텍스트가", "문구가", "자막이",
                   "글씨가", "흰색 텍스트", "타이포")


def _pick_layout(short, segs):
    """이 구간이 '글자카드'인가 '화면녹화'인가.

    전사에 이미 있는 scene_desc를 센다 — 새로 AI를 부르지 않는다(무과금·즉시).
    애매하면 screencast로 둔다: 자막을 얹어도 원본에 글자가 없으면 손해가 없지만,
    반대로 글자카드에 자막을 얹으면 곧바로 3중첩이 된다(더 나쁜 쪽을 피한다).
    """
    if short.get("layout") in ("textcard", "screencast"):
        return short["layout"]                     # 사람이 지정했으면 그대로
    s, e = float(short["start"]), float(short["end"])
    hit = tot = 0
    for g in segs:
        if float(g.get("end", 0)) < s or float(g.get("start", 0)) > e:
            continue
        tot += 1
        d = (g.get("scene_desc") or "")
        if any(k in d for k in _TEXTCARD_HINTS):
            hit += 1
    return "textcard" if tot and hit / tot >= 0.6 else "screencast"


def _source_chain(layout):
    """원본 프레임 → 1080x1920 화면. 레터박스를 쓰지 않는다.

    ★1차 설계는 16:9를 1080x608로 줄여 화면 한가운데 놓았다(세로의 31.7%). 나머지
      68%가 빈 검정이었고, 화면녹화 UI 글자는 1920→1080 축소로 뭉갰다. 두 모드 다
      **크롭**으로 바꿔 원본 픽셀을 그대로 쓴다.
    """
    if layout == "textcard":
        # 9:16 꽉 채우기. 글자카드는 가운데에 글자가 있으므로 좌우를 잘라도 안전하다.
        return (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},setsar=1")
    # 화면녹화: 아래 20%(원본 자막이 구워진 띠)를 잘라내고, 가로도 5:4가 되게 좁혀
    # **화면을 크게** 만든다. 1차 설계처럼 16:9를 1080x608로 줄이면 UI 글자가 뭉갠다.
    #   2560x1440 기준: 1440x1152 크롭 → 1080x864 (1차의 608px보다 42% 큼)
    return (f"crop=w='min(iw,ih*0.8*1.25)':h='ih*0.8':x='(iw-ow)/2':y=0,"
            f"scale={W}:-2,setsar=1,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black")


def render_short(video_path, short, out_path, template=DEFAULT_TEMPLATE,
                 channel_name="", work_dir=None, logo_path=None, segs=None,
                 layout=None, gate=True):
    """설계 1편 → 9:16 mp4 + 품질 게이트 결과.

    gate=True면 렌더 뒤 shorts_gate로 검사하고, 걸리면 결과에 실패 목록을 담는다.
    (파일은 남긴다 — 뭐가 틀렸는지 눈으로도 봐야 고칠 수 있다. 다만 ok=False다.)
    """
    tpl = TEMPLATES.get(template) or TEMPLATES[DEFAULT_TEMPLATE]
    work = Path(work_dir or tempfile.mkdtemp(prefix="lfrender_"))
    work.mkdir(parents=True, exist_ok=True)
    segs = segs or []
    lay = layout or _pick_layout(short, segs)

    # ★컷은 문장 경계에 붙인다. 정수 초로 자르면 말 중간에 켜지고 말 중간에 죽는다
    #   (1차 결과물의 "이어지는 구간이 이상하다"의 한 축).
    s, e = _snap_cut(float(short["start"]), float(short["end"]), segs)
    body = round(e - s, 2)

    _reenc(video_path, s, body, work / "body.mp4")
    _endcard(ENDCARD_SECONDS, work / "end.mp4", channel_name, tpl, logo_path)

    total = body + ENDCARD_SECONDS
    # 오디오 게인을 **미리 재서 고정값으로** 건다(아래 _filtergraph 주석 참고).
    gain = _gain_to_target(work / "body.mp4")
    fg = _filtergraph(work, short, tpl, s, total, body, channel_name, lay, gain)
    (work / "fg.txt").write_text(fg, encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(work / "body.mp4"), "-i", str(work / "end.mp4"),
         "-filter_complex_script", str(work / "fg.txt"),
         "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-level", "4.2", "-movflags", "+faststart",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         str(out_path), "-loglevel", "error"], check=True)

    info = {"path": str(out_path), "seconds": round(total, 1), "layout": lay,
            "body_seconds": body, "endcard_seconds": ENDCARD_SECONDS,
            "cut": {"start": s, "end": e}}
    if gate:
        from shopping_shorts import shorts_gate
        # 끝 = 페이드아웃 0.6초 + 무음 엔드카드. 의도한 마무리라 검사에서 뺀다.
        g = shorts_gate.run(out_path, ignore_tail=ENDCARD_SECONDS + 0.8)
        info["gate"] = g.to_dict()
        info["ok"] = g.ok
        if not g.ok:
            print("[longform] 품질 게이트 불합격:\n" + g.report(), file=sys.stderr)
    return info


def _snap_cut(s, e, segs, tol=2.0):
    """구간 시작·끝을 전사 경계로 당긴다. 붙일 경계가 없으면 원래 값을 둔다."""
    if not segs:
        return round(s, 2), round(e, 2)
    starts = sorted({float(g["start"]) for g in segs})
    ends = sorted({float(g["end"]) for g in segs})

    def near(v, pool):
        c = min(pool, key=lambda x: abs(x - v))
        return c if abs(c - v) <= tol else v

    ns, ne = near(s, starts), near(e, ends)
    return (round(ns, 2), round(ne, 2)) if ne - ns > 8 else (round(s, 2), round(e, 2))


def _reenc(src, start, dur, dst):
    # 중간 산출물은 넉넉히 — 최종에서 한 번 더 인코딩되므로 여기서 아끼면 손실이 겹친다.
    subprocess.run(["ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    str(dst), "-loglevel", "error"], check=True)


def _endcard(dur, dst, channel_name, tpl, logo_path=None):
    """마지막 채널 카드. 여기만 소리를 뺀다(본문 페이드아웃이 이 앞에서 끝난다)."""
    bg = tpl.get("bg") or "black"
    accent = tpl.get("ch") or "white"
    tf = _txtfile(Path(dst).parent, "endname", channel_name or " ")
    vf = (f"drawtext=fontfile='{_FONT}':textfile='{tf}':fontsize=64:fontcolor=white"
          f":x=(w-tw)/2:y=(h-th)/2,"
          f"drawbox=x={W // 2 - 130}:y={H // 2 + 70}:w=260:h=6:color={accent}:t=fill,"
          f"format=yuv420p")
    ins = ["-f", "lavfi", "-t", str(dur), "-i", f"color=c={bg}:s={W}x{H}:r=30"]
    subprocess.run(
        ["ffmpeg", "-y", *ins,
         "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v:0", "-map", "1:a:0", "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "48000", "-shortest", str(dst), "-loglevel", "error"],
        check=True)


def _dt(src, dst, tf, size, color, x, y, enable=None, border=(5, "black")):
    b = f":borderw={border[0]}:bordercolor={border[1]}" if border else ""
    en = f":enable='{enable}'" if enable else ""
    return (f"[{src}]drawtext=fontfile='{_FONT}':textfile='{tf}':fontsize={size}"
            f":fontcolor={color}:x={x}:y={y}{b}{en}[{dst}];")


def _gain_to_target(path):
    """이 오디오를 LUFS_TARGET에 맞추려면 몇 dB 올려야 하나(정적 게인).

    ★loudnorm을 쓰다 걷어냈다(2026-08-15 실측). loudnorm 단일 패스는 **적응형**이라
      스스로 볼륨을 올렸다 내렸다 한다 — 원본 구간의 라우드니스 점프가 7.9 LU였는데
      loudnorm을 통과하니 19.0 LU가 됐다. 목표는 '레벨 맞추기'지 '압축'이 아니므로,
      한 번 재서 **고정 게인**을 건다. 고정 게인은 정의상 점프를 만들 수 없다.
    """
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-af", "loudnorm=print_format=json",
         "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", out, re.S)
    if not m:
        return 0.0
    try:
        cur = float(json.loads(m.group(0))["input_i"])
    except Exception:                              # noqa: BLE001
        return 0.0
    if cur < -70:                                  # 사실상 무음이면 건드리지 않는다
        return 0.0
    return max(-12.0, min(12.0, LUFS_TARGET - cur))


def _filtergraph(work, short, tpl, win_start, total, body, channel_name, layout, gain=0.0):
    L = []
    # 본문·엔드카드를 같은 규격으로 맞춘 뒤 이어붙인다.
    # ★concat 디먹서(-c copy)를 쓰지 마라 — 조각들 파라미터가 달라 타임스탬프가 망가진다
    #   (실측: 38초여야 할 결과가 58.3초, 스팅이 통째로 소멸).
    L.append(f"[0:v]{_source_chain(layout)},fps=30,format=yuv420p[b0];")
    L.append(f"[1:v]scale={W}:{H},fps=30,format=yuv420p,setsar=1[e0];")
    # 오디오: 본문은 끝 0.6초 페이드아웃, 엔드카드는 무음
    L.append(f"[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
             f"afade=t=out:st={max(0.0, body - 0.6):.2f}:d=0.6[ba];")
    L.append("[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[ea];")
    L.append("[b0][ba][e0][ea]concat=n=2:v=1:a=1[cv][ca];")
    # 라우드니스 정규화 — 데드에어·볼륨 널뛰기를 여기서 잡는다(쇼츠 표준 -14 LUFS)
    # ★dynaudnorm을 걸었다가 뺐다(2026-08-15 실측). 원본 구간의 라우드니스 점프는
    #   7.9 LU로 이미 기준(12) 안이었는데, dynaudnorm이 조용한 부분을 끌어올리다
    #   창 경계에서 튀어 **17.5 LU로 악화**시켰다. 멀쩡한 것을 건드려 망친 경우다.
    #   레벨만 맞추면 된다 — 원본의 강약(LRA)은 화자의 연기라 뭉개면 안 된다.
    L.append(f"[ca]volume={gain:.2f}dB,alimiter=limit=0.89[a];")

    cur, k = "cv", 0

    def nxt():
        nonlocal k
        k += 1
        return f"z{k}"

    # 컷 직후 정착 — 하드컷이 툭 끊기지 않게 5프레임만 1.03→1.00
    d = nxt()
    L.append(f"[{cur}]scale=w='iw*(1+0.03*max(0,1-t*{30 / SETTLE_FRAMES:.2f}))':"
             f"h=-2:eval=frame,crop={W}:{H}[{d}];")
    cur = d

    # 상단 헤드카피 — 처음 몇 초만. 화면에 계속 두면 영상을 가린다.
    # ★두 줄이 시차를 두고 **아래에서 올라온다**. 이유가 둘이다:
    #   ㉠ 글자가 0프레임에 통째로 박혀 있으면 '정지 화면'으로 읽힌다 — 게이트의
    #      '첫 3초 정지' 검사가 실제로 이걸 잡았다(0.57초, 기준 0.5초 초과).
    #   ㉡ 시차 등장은 읽는 순서를 만든다(1줄 상황 → 2줄 훅).
    head = short.get("headline") or ["", ""]
    for i, (line, col, y) in enumerate([(head[0], tpl["h1"], 150),
                                        (head[1] if len(head) > 1 else "", tpl["h2"], 250)]):
        if not line:
            continue
        t0 = 0.10 + i * 0.22                       # 줄마다 시차
        d = nxt()
        # y가 t0부터 0.35초 동안 아래(+70px)에서 제자리로 온다
        yexpr = f"{y}+70*max(0{chr(92)},1-(t-{t0:.2f})/0.35)"
        L.append(_dt(cur, d, _txtfile(work, f"h{i}", line), 76, col,
                     "(w-tw)/2", yexpr,
                     enable=f"between(t,{t0:.2f},{HEADLINE_SECONDS})", border=(6, "black")))
        cur = d

    # 요약 자막 — 화면녹화 모드에서만. 글자카드에 또 얹으면 자막 3중첩이 된다.
    if layout != "textcard":
        for i, c in enumerate(short.get("captions") or []):
            a = float(c.get("start", win_start)) - win_start
            b = float(c.get("end", win_start)) - win_start
            if b <= 0 or a >= body:
                continue
            for j, (line, col, y) in enumerate([(c.get("line1", ""), tpl["cap1"], 1560),
                                                (c.get("line2", ""), tpl["cap2"], 1650)]):
                if not line:
                    continue
                d = nxt()
                L.append(_dt(cur, d, _txtfile(work, f"c{i}_{j}", line), 60, col,
                             "(w-tw)/2", y, enable=f"between(t,{a:.2f},{b:.2f})"))
                cur = d

    # 채널 워터마크 — 범퍼 대신 상시 노출. 우상단 작게.
    if channel_name:
        d = nxt()
        L.append(_dt(cur, d, _txtfile(work, "wm", channel_name), 34, "0xFFFFFF",
                     f"{W}-tw-40", 56, enable=f"lt(t,{body:.2f})", border=(4, "black")))
        cur = d

    L[-1] = L[-1].rsplit("[", 1)[0] + "[v]"
    return "\n".join(L)
