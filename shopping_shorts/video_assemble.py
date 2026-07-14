"""EDL + 비트별 TTS → ffmpeg으로 컷 편집·오디오 교체·새 대본 자막을 구운 최종 mp4.

각 비트의 소스 구간을 그 비트 나레이션(TTS) 길이만큼 **정상 속도(1배속)** 로
재생한다. 자막이 정상 속도로 읽히도록, 영상 길이는 배속으로 압축하지 않고
나레이션 읽는 시간에 맞춰 늘린다(설계: 대본 못 줄이면 클립을 길게, 20~30초).
구간 원본이 나레이션보다 짧으면 소스를 루프(-stream_loop)해서 부족분을 채운다.

새 대본은 화면 하단 불투명 바 위에 **한 줄씩 순차로(progressive)** 굽는다. 바가
원본에 박힌 소각 자막을 가리고, 그 위에 새 나레이션이 읽는 속도로 한 줄씩 넘어간다.
한글 폰트가 없는 환경(폰트 미해결)에서는 자막을 생략하고 영상만 렌더한다.
concat 후 원본 오디오를 제거하고 비트별 TTS를 이어붙인 트랙으로 교체한다.
"""
import os
import shutil
import subprocess
import textwrap
import uuid
from pathlib import Path

# 출력 규격(숏폼 세로). 소스 해상도가 달라도 여기로 통일해야 concat -c copy가 안전.
_OUT_W, _OUT_H = 720, 1280
# 하단 자막 바(원본 소각 자막을 덮는다) + 한 줄 자막 스타일.
_BAR_H = 300
_CAP_FONTSIZE = 52      # 짧은 1줄 구절이라 여유 있음 → 키움
# 자막 리듬 목표: 한 구절 2~3어절, 무자막 없이 빠르게 순차 전환. 핵심은 글자수보다
# **의미(호흡) 단위** — 수식어(관형어·부사)는 뒤 단어와 붙어 한 호흡이 되어야 한다.
# 예) "이 방법은 진짜", "자세한 보관비법", "바로 알려드릴게요", "그냥 두지 마세요".
_CAP_TARGET = 9         # 한 구절 목표 글자수(공백 제외). 이 안이면 이어붙이려 시도.
_CAP_MAX_WORDS = 3      # 한 구절 최대 어절 수(하드리밋).
# ── 머리 단어(head-marker): 이 단어를 만나면 그 **앞에서** 끊고, 이 단어가 다음
#    구절의 머리가 된다(뒤 명사/서술어를 데려간다). "…일쑤였는데 | 이 방법은"처럼
#    관형어 "이"가 앞 구절 꼬리에 남지 않게 한다. 관형사·지시어·부사·수관형사.
_CAP_HEAD = {"이", "그", "저", "한", "두", "세", "네", "몇", "각", "매", "총",
             "이런", "저런", "그런", "무슨", "어떤", "온갖", "단", "딱", "약",
             "자세한", "확실한", "특별한", "간단한", "완벽한",
             "바로", "그냥", "그대로", "다시", "먼저", "이제", "지금", "꼭", "막",
             "가장", "제일", "훨씬", "더", "덜", "약간", "좀", "진짜", "정말"}
# ── 도입어(lead): 이 단어(로 끝나는 어절)는 한 호흡을 열고 **뒤에서** 끊는다.
#    호격("여러분")·연결 도입("남겨주시면") 등 그 자체로 한 박자.
_CAP_LEAD = {"여러분", "여러분,", "자"}
# 연결어미로 끝나는 절은 뒤에서 끊어 한 박자를 준다(…하면 | …했는데 |). 단 "-서"는
# 장소조사 "-에서/-께서"와 어미 "-아서/-어서"가 섞여 오탐이 잦아 제외한다. 또 이
# 끊기는 앞 절이 충분히 길 때(_CAP_LEAD_MINCHARS↑)만 적용해 "밭에서"(짧음)는 안 끊는다.
_CAP_LEAD_SUFFIX = ("면", "면서", "니까", "는데", "지만", "거든", "잖아")
_CAP_LEAD_MINCHARS = 4  # 연결어미 끊기 최소 글자수(공백 제외). 이보다 짧으면 이어붙임.
_CAP_HEAD_MINCHARS = 4  # 머리 단어 앞에서 끊는 최소(앞 구절) 글자수. 짧으면 이어붙임
                        # ("이것 한" 파편 방지, "…일쑤였는데 | 이" 는 앞이 길어 끊김).
_CAP_WRAP = 13          # 아주 긴 단일 어절 방어용(한 줄 최대 글자수, 720px 안)
_CAP_MIN_DUR = 0.25     # 한 구절 최소 표시시간(속도감).

# 한글 폰트 후보(먼저 발견되는 것 사용). repo에 NanumGothic을 번들하므로 서버·로컬
# 어디서든 별도 설치 없이 자막이 나온다(env로 다른 폰트 강제 가능).
_BUNDLED_FONT = str(Path(__file__).parent / "assets" / "NanumGothic.ttf")
_FONT_CANDIDATES = [
    os.environ.get("SHORTS_CAPTION_FONT"),
    _BUNDLED_FONT,
    "C:/Windows/Fonts/malgun.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def _resolve_font():
    """사용 가능한 한글 폰트 경로(첫 번째 존재하는 것). 없으면 None → 자막 생략."""
    for p in _FONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


def _probe_duration(path):
    """ffprobe로 미디어 길이(초)."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    out = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _run_ffmpeg(cmd, cwd=None):
    """ffmpeg 실행. 실패 시 stderr를 예외에 담아 원인을 삼키지 않는다."""
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패(exit {r.returncode}): {r.stderr[-1000:]}")
    return r


def _pick_segment(beat, tts_dur, source_video_paths):
    """primary→alternates 중 나레이션(tts_dur)을 1배속으로 담을 수 있는
    (구간길이 >= tts_dur) 첫 후보를 고른다. 아무도 못 담으면 가장 긴 후보를
    반환하고, 부족분은 assemble에서 소스 루프로 채운다. 반환: ref(dict).
    더 이상 배속 보정을 하지 않으므로 setpts rate는 반환하지 않는다."""
    candidates = [beat["primary"]] + list(beat.get("alternates", []))
    best = None
    best_len = -1.0
    for ref in candidates:
        if ref["video_id"] not in source_video_paths:
            continue
        seg_len = ref["end"] - ref["start"]
        if seg_len >= tts_dur:
            return ref  # 1배속으로 나레이션 전체를 담을 수 있는 첫 후보
        if seg_len > best_len:
            best, best_len = ref, seg_len
    return best if best else beat["primary"]


def _strip_punct(w):
    """조사·문장부호를 뗀 순수 단어(머리/도입어 판정용). '이,' → '이'."""
    return w.strip(".,!?…\"'()[]")


def _caption_segments(narration):
    """나레이션을 **의미(호흡) 단위**의 짧은 구절로 나눈다(2~3어절, 1줄).
    예) "여러분 / 오이 절대", "냉장고에 / 그냥 두지 마세요",
        "버리기 일쑤였는데 / 이 방법은 진짜", "남겨주시면 / 자세한 보관비법 / 바로 알려드릴게요".

    핵심은 글자수가 아니라 **수식어를 뒤 단어와 붙이는 것**:
    - 머리 단어(_CAP_HEAD: 관형어·부사 "이/그/자세한/바로/그냥/그대로"…)를 만나면 그
      **앞에서** 끊는다 → 그 단어가 다음 구절의 머리가 되어 뒤 명사/서술어를 데려간다.
      ("…일쑤였는데 | 이 방법은" — 관형어 "이"가 앞 꼬리에 안 남는다.)
    - 도입어(_CAP_LEAD "여러분"·연결어미 "…면/…는데"로 끝나는 어절)는 한 박자를 열고
      그 **뒤에서** 끊는다. ("여러분 |", "남겨주시면 |")
    - 그 밖에는 글자수(_CAP_TARGET) / 어절수(_CAP_MAX_WORDS) 목표 안에서 이어붙인다.

    방어: 목표를 크게 넘는 아주 긴 단일 어절은 _CAP_WRAP로 강제 줄바꿈."""
    narr = (narration or "").strip()
    if not narr:
        return []
    words = narr.split()
    out, cur = [], []
    for i, w in enumerate(words):
        if not cur:
            cur = [w]
            continue
        bare = _strip_punct(w)
        prev = _strip_punct(cur[-1])
        cur_chars = len("".join(cur))
        room = len("".join(cur + [w])) <= _CAP_TARGET   # 글자수 여유
        under_cap = len(cur) < _CAP_MAX_WORDS           # 어절 상한 이내(하드리밋)
        # 앞 단어가 수식어면(머리 단어이거나 관형격 "-의"로 끝남) 뒤 단어를 반드시
        # 데려가야 한다("마법의 | 가루" 방지) → 이땐 이어붙인다. 단 어절 상한(under_cap)
        # 은 지켜 "꼭 두 세개씩"이 4어절로 폭주하지 않게 한다.
        prev_pulls = (prev in _CAP_HEAD or prev.endswith("의")) and under_cap
        # (a) 다음 단어가 머리 단어면 그 앞에서 끊어 그 단어를 다음 구절 머리로 만든다.
        #     단 뒤에 데려갈 단어가 있고, 앞 구절이 이미 충분히 길 때만(짧으면 이어붙임 —
        #     "이것 한" 파편 방지). "…일쑤였는데(5자) | 이 방법은"은 앞이 길어 끊긴다.
        head_break = (bare in _CAP_HEAD and i + 1 < len(words)
                      and cur_chars >= _CAP_HEAD_MINCHARS)
        # (b) 현재 구절이 도입어/연결어미로 끝나면 여기서 끊어 한 박자를 준다. 단
        #     연결어미 끊기는 앞 절이 충분히 길 때만("밭에서" 같은 짧은 부사구는 이어붙임).
        lead_break = prev in _CAP_LEAD or (
            prev.endswith(_CAP_LEAD_SUFFIX) and cur_chars >= _CAP_LEAD_MINCHARS)
        # (c) 앞 어절이 문장부호로 끝났으면 문장 경계에서 끊는다.
        sent_break = cur[-1].endswith((".", "?", "!", "…"))
        if not prev_pulls and (head_break or lead_break or sent_break
                               or not room or not under_cap):
            out.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        out.append(" ".join(cur))
    # 목표를 크게 넘는 초장문 단일 구절만 줄바꿈으로 방어(대부분은 그대로 1줄).
    segs = []
    for s in out:
        if len(s.replace(" ", "")) > _CAP_WRAP:
            segs.extend(textwrap.wrap(s, _CAP_WRAP) or [s])
        else:
            segs.append(s)
    return segs or [narr]


def _caption_durations(segs, dur):
    """각 구절의 표시 시간(초) 리스트를 반환. 기본은 글자수 비례(균등분할 X)지만,
    아주 짧은 구절(2~3자)이 순식간에 지나가지 않도록 _CAP_MIN_DUR 하한을 준다.
    하한을 채우고 남은 시간을 나머지 구절에 글자수 비례로 재분배해, 총합은 항상
    dur를 넘지 않는다(하한들의 합이 dur를 초과하면 균등분할로 폴백)."""
    n = len(segs)
    if n == 0:
        return []
    if _CAP_MIN_DUR * n >= dur:      # 하한조차 못 채우면 균등분할
        return [dur / n] * n
    weights = [max(1, len(s.replace("\n", ""))) for s in segs]
    total_w = sum(weights)
    raw = [dur * w / total_w for w in weights]
    # 하한 미달인 구절은 하한으로 올리고, 그만큼을 하한 이상인 구절에서 비례로 회수.
    floored = [max(_CAP_MIN_DUR, r) for r in raw]
    over = sum(floored) - dur
    if over > 1e-6:
        slack_idx = [i for i, r in enumerate(floored) if r > _CAP_MIN_DUR]
        slack_total = sum(floored[i] - _CAP_MIN_DUR for i in slack_idx)
        if slack_total > 1e-6:
            for i in slack_idx:
                floored[i] -= over * (floored[i] - _CAP_MIN_DUR) / slack_total
    return floored


def _caption_drawtexts(narration, dur, work, idx, t0=0.0, style=None):
    """나레이션 한 비트의 자막(하단 바 + 순차 drawtext)을 필터 문자열 **리스트**로
    반환한다. 각 구절 enable 구간을 t0(전체 타임라인 시작 오프셋)만큼 밀어, 여러 비트를
    한 영상에 이어 구울 때(_burn_captions) 비트 경계에 맞게 배치된다.

    style(자막 스타일 dict, 없으면 기존 기본값 = 하단 바 + 흰색)로 폰트·색·크기·위치·
    외곽선·배경박스·효과를 제어한다. style이 None이면 하위호환(기존 렌더와 동일).
    반환 리스트를 그대로 필터그래프에 이어붙이면 되고, drawtext 값 안의
    between(t,a,b) 콤마를 나중에 split할 필요가 없다(요소 단위로 이미 분리됨).
    자막 구절이 없으면 빈 리스트. 텍스트는 work/cap_{idx}_{i}.txt 로 저장(cwd=work)."""
    segs = _caption_segments(narration)
    if not segs:
        return []
    style = style or {}
    durs = _caption_durations(segs, dur)
    # 폰트: style.font이 static/fonts의 실제 파일이면 그것, 아니면 기본 자막폰트(font.ttf)
    capfont = "font.ttf"
    fname = os.path.basename(style.get("font") or "")
    if fname and (_FONT_DIR / fname).exists():
        shutil.copy(_FONT_DIR / fname, work / "cap_font.ttf")
        capfont = "cap_font.ttf"
    color = _hex_to_ff(style.get("color"), "0xFFFFFF")
    size = max(10, int(style.get("size") or _CAP_FONTSIZE))
    # 세로 위치: y_pct(0~100) 지정 시 중심기준, 없으면 하단 기본
    ypct = style.get("y_pct")
    ypos = f"(h*{min(1.0, max(0.0, ypct / 100.0)):.4f}-text_h/2)" if ypct is not None else "h-text_h-100"
    # 효과: fade(알파 페이드-인)/pop(초반 살짝 확대는 drawtext 불가라 알파로 근사)/slide(y 위로)
    effect = style.get("effect") or "none"
    use_box = bool(style.get("box"))
    show_bar = style.get("bar", True) and not use_box
    parts = []
    if show_bar:
        parts.append(f"drawbox=x=0:y=ih-{_BAR_H}:w=iw:h={_BAR_H}:color=black@0.82:t=fill")
    t = 0.0
    for i, (seg, d) in enumerate(zip(segs, durs)):
        (work / f"cap_{idx}_{i}.txt").write_text(seg, encoding="utf-8")
        start = t + t0
        t += d
        # 마지막 구절은 비트 끝까지(+0.5) 유지. t0 오프셋을 함께 적용.
        end = (dur + 0.5 if i == len(segs) - 1 else t) + t0
        yexpr = ypos
        if effect == "slide":
            # 등장 0.25초 동안 아래→위로 미끄러짐
            yexpr = f"({ypos}+30*(1-min(1\\,(t-{start:.2f})/0.25)))"
        dt = [
            f"drawtext=fontfile={capfont}:textfile=cap_{idx}_{i}.txt",
            f"fontcolor={color}", f"fontsize={size}", "line_spacing=10",
            "x=(w-text_w)/2", f"y={yexpr}",
        ]
        if effect in ("fade", "pop"):
            spd = 0.18 if effect == "fade" else 0.12
            dt.append(f"alpha='min(1,max(0,(t-{start:.2f})/{spd}))'")
        if style.get("outline"):
            dt.append(f"borderw={max(1, int(style.get('outline_w') or 5))}")
            dt.append(f"bordercolor={_hex_to_ff(style.get('outline_color'), '0x000000')}")
        if use_box:
            bc = _hex_to_ff(style.get("box_color"), "0x000000")
            op = max(0.0, min(1.0, (style.get("box_opacity") or 80) / 100.0))
            pad = max(0, int(style.get("box_pad") if style.get("box_pad") is not None else 12))
            dt += ["box=1", f"boxcolor={bc}@{op:.2f}", f"boxborderw={pad}"]
        dt.append(f"enable='between(t,{start:.2f},{end:.2f})'")
        parts.append(":".join(dt))
    return parts


def _caption_vf(narration, dur, has_font, work, idx):
    """비트 영상용 -vf 필터 문자열. scale/crop으로 규격 통일 후, 폰트가 있으면
    하단 바 + 나레이션을 **짧은 구절 단위**로 순차 표시하는 drawtext들을 얹는다.
    각 구절의 표시 시간은 글자수 비례 + 최소 표시시간 하한(_caption_durations).

    ffmpeg 필터그래프는 값에 콜론(윈도 드라이브 'C:')을 못 넣으므로, 폰트·자막
    텍스트는 모두 work 폴더에 두고 **파일명만**(font.ttf / cap_*.txt) 참조한다.
    호출부는 반드시 cwd=work 로 ffmpeg를 실행해야 한다. 각 구절 텍스트는 임시
    파일(textfile=)로 넘겨 따옴표/쉼표 이스케이프 문제를 피한다."""
    base = f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"
    if not has_font:
        return base
    draws = _caption_drawtexts(narration, dur, work, idx)
    if not draws:
        return base
    return ",".join([base] + draws)


def _render_mix(edit_plan, tts_paths, source_video_paths, work):
    """각 비트를 [소스영상+TTS]로 렌더(우리 자막 없음) → concat → mix_raw.mp4 경로.
    자막을 굽지 않으므로 이후 VMake 자막제거가 우리 자막을 지우지 않는다.
    -vf는 우리 자막 vf가 아니라 규격 통일용 base(scale/crop)만 쓴다."""
    base_vf = f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"
    beat_clips = []
    for beat in edit_plan["beats"]:
        idx = beat["beat_idx"]
        tts = tts_paths.get(idx)
        if not tts:
            continue
        tts_dur = _probe_duration(tts)
        ref = _pick_segment(beat, tts_dur, source_video_paths)
        src = source_video_paths[ref["video_id"]]
        src_dur = _probe_duration(src)
        clip = work / f"beat_{idx}.mp4"
        # 나레이션 길이(tts_dur)만큼 소스를 ref["start"]부터 **이어서(연속)** 1배속
        # 재생. 시작점부터 tts_dur가 원본 끝을 넘으면 시작을 앞으로 당겨 연속 footage
        # 를 확보한다. 원본 전체가 나레이션보다 짧을 때만 루프한다.
        start = ref["start"]
        if start + tts_dur > src_dur:
            start = max(0.0, src_dur - tts_dur)
        loop = ["-stream_loop", "-1"] if src_dur + 0.05 < tts_dur else []
        cmd = [
            "ffmpeg", "-y",
            *loop, "-ss", f"{start:.3f}", "-i", str(src),
            "-i", str(tts),
            "-vf", base_vf, "-r", "30",
            "-map", "0:v:0", "-map", "1:a:0",
            "-t", str(tts_dur),
            "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(clip),
        ]
        _run_ffmpeg(cmd)
        beat_clips.append(clip)
    if not beat_clips:
        raise RuntimeError("video_assemble: 렌더할 비트가 없습니다")
    concat_txt = work / "concat_mix.txt"
    concat_txt.write_text("".join(f"file '{c.as_posix()}'\n" for c in beat_clips), encoding="utf-8")
    # 비트 클립들은 이미 동일 설정(720x1280 libx264/aac 30fps)이므로 -c copy로 붙인다
    # (재인코딩 concat은 2GB 서버에서 수십 초 → 배포 재시작에 걸려 죽던 원인, 2026-07-12).
    mix_raw = work / "mix_raw.mp4"
    _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                 "-c", "copy", str(mix_raw)])
    return str(mix_raw)


def _hex_to_ff(c, default="0xFFFFFF"):
    """'#FF8800' → '0xFF8800' (ffmpeg drawtext color). 이상하면 default."""
    c = (c or "").strip().lstrip("#")
    return f"0x{c.upper()}" if len(c) == 6 and all(ch in "0123456789ABCDEFabcdef" for ch in c) else default


_FONT_DIR = Path(__file__).parent / "static" / "fonts"


def _fixed_drawtext(spec, work, key, default_color="0xFFFFFF"):
    """고정 위치 drawtext 공용 생성기(헤드카피·추가텍스트·워터마크). text·폰트 파일은
    key로 유일화(txt_{key}.txt / font_{key}.ttf)해 여러 개를 한 필터그래프에 안전히 얹는다.
    x/y는 % 위치(가로·세로 중심). spec.alpha(0~1)로 전체 투명도(워터마크용). text 없으면 None.
    spec['font']이 static/fonts의 실제 파일이면 그 폰트, 아니면 기본 자막폰트(font.ttf)."""
    text = (spec.get("text") or "").strip()
    if not text:
        return None
    (work / f"txt_{key}.txt").write_text(text, encoding="utf-8")
    fontref = "font.ttf"  # _burn_captions가 work에 복사해둔 기본폰트
    fname = os.path.basename(spec.get("font") or "")
    if fname:
        fpath = _FONT_DIR / fname
        if fpath.exists():
            shutil.copy(fpath, work / f"font_{key}.ttf")
            fontref = f"font_{key}.ttf"
    size = max(8, int(spec.get("size") or 64))
    xf = min(1.0, max(0.0, (spec.get("x", 50)) / 100.0))
    yf = min(1.0, max(0.0, (spec.get("y", 14)) / 100.0))
    parts = [
        f"drawtext=fontfile={fontref}:textfile=txt_{key}.txt",
        f"fontcolor={_hex_to_ff(spec.get('color'), default_color)}",
        f"fontsize={size}",
        f"x=(w*{xf:.4f}-tw/2)", f"y=(h*{yf:.4f}-th/2)",
    ]
    if spec.get("alpha") is not None:
        parts.append(f"alpha={max(0.0, min(1.0, float(spec.get('alpha')))):.2f}")
    if spec.get("outline"):
        parts.append(f"borderw={max(1, int(spec.get('outline_w') or 6))}")
        parts.append(f"bordercolor={_hex_to_ff(spec.get('outline_color'), '0x000000')}")
    if spec.get("box"):
        bc = _hex_to_ff(spec.get("box_color"), "0x000000")
        op = max(0.0, min(1.0, (spec.get("box_opacity") or 80) / 100.0))
        pad = max(0, int(spec.get("box_pad") if spec.get("box_pad") is not None else 16))
        parts += ["box=1", f"boxcolor={bc}@{op:.2f}", f"boxborderw={pad}"]
    return ":".join(parts)


def _headcopy_drawtext(hc, work):
    """헤드카피(고정 타이틀) drawtext — _fixed_drawtext 래퍼(기본색 오렌지)."""
    return _fixed_drawtext(hc, work, "hc", default_color="0xFF8800")


def _burn_captions(in_video, edit_plan, tts_paths, out_path, work, headcopy=None, caption_style=None, deco=None):
    """완성된 믹스 영상(in_video) 위에 우리 자막을 비트 타이밍대로 굽는다.
    비트 경계는 각 비트 tts 길이 누적(t0)으로 계산해, drawtext enable 구간을 전체
    타임라인 기준으로 배치한다(_caption_drawtexts에 t0 오프셋 전달). drawtext 값 안의
    between(t,a,b) 콤마를 나중에 split할 필요가 없다(필터 요소 단위로 리스트 반환).
    폰트가 없으면 자막 없이 원본을 그대로 복사한다."""
    font = _resolve_font()
    if font:
        try:
            shutil.copy(font, work / "font.ttf")
        except OSError:
            font = None
    if not font:
        shutil.copy(in_video, out_path)
        return str(out_path)
    filters = [f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"]
    t0 = 0.0
    for beat in edit_plan["beats"]:
        idx = beat["beat_idx"]
        tts = tts_paths.get(idx)
        if not tts:
            continue
        dur = _probe_duration(tts)
        filters.extend(_caption_drawtexts(beat.get("narration", ""), dur, work, idx, t0, caption_style))
        t0 += dur
    if headcopy:
        hc_dt = _headcopy_drawtext(headcopy, work)
        if hc_dt:
            filters.append(hc_dt)  # 항상 표시(고정 타이틀) — enable 없음
    # 꾸미기 장식(deco): 추가 텍스트(여러 개) + 워터마크 닉네임. 모두 고정 drawtext.
    deco = deco or {}
    for i, t in enumerate(deco.get("extra_texts") or []):
        ex_dt = _fixed_drawtext(t, work, f"ex{i}")
        if ex_dt:
            filters.append(ex_dt)
    wm = deco.get("watermark") or {}
    if wm.get("text"):
        wm_spec = {"text": wm.get("text"), "font": wm.get("font"),
                   "color": wm.get("color", "#FFFFFF"),
                   "size": wm.get("size", 30),
                   "x": wm.get("x", 50), "y": wm.get("y", 95),
                   "alpha": wm.get("alpha", 0.6),
                   "outline": wm.get("outline", True),
                   "outline_color": wm.get("outline_color", "#000000"),
                   "outline_w": wm.get("outline_w", 3)}
        wm_dt = _fixed_drawtext(wm_spec, work, "wm", default_color="0xFFFFFF")
        if wm_dt:
            filters.append(wm_dt)
    vf = ",".join(filters)
    # cwd=work: 필터그래프의 font.ttf / cap_*.txt 상대경로 해석 기준(콜론 회피).
    # 오버레이 이미지·BGM 유무로 -vf(단순) 또는 filter_complex(합성) 선택. 둘 다 조합 가능.
    bgm = deco.get("bgm") or {}
    bgm_path = bgm.get("_abspath")
    has_bgm = bool(bgm_path and os.path.exists(bgm_path))
    overlay = deco.get("overlay") or {}
    ov_path = overlay.get("_abspath")
    has_overlay = bool(ov_path and os.path.exists(ov_path))
    if not has_bgm and not has_overlay:
        _run_ffmpeg(["ffmpeg", "-y", "-i", str(in_video), "-vf", vf, "-r", "30",
                     "-c:v", "libx264", "-c:a", "copy", "-pix_fmt", "yuv420p", str(out_path)],
                    cwd=str(work))
        return str(out_path)
    inputs = ["-i", str(in_video)]
    fc = [f"[0:v]{vf}[v0]"]
    vcur, idx = "v0", 1
    if has_overlay:                                   # 이미지 오버레이(로고·뱃지 등)
        inputs += ["-i", ov_path]
        w = overlay.get("width")                      # 1080px 기준 폭(없으면 원본)
        scale = f"scale={int(w)}:-1," if w else ""
        xf = min(1.0, max(0.0, overlay.get("x", 50) / 100.0))
        yf = min(1.0, max(0.0, overlay.get("y", 50) / 100.0))
        aa = max(0.0, min(1.0, overlay.get("alpha", 1)))
        fc.append(f"[{idx}:v]{scale}format=rgba,colorchannelmixer=aa={aa:.2f}[ov]")
        fc.append(f"[{vcur}][ov]overlay=x=W*{xf:.4f}-w/2:y=H*{yf:.4f}-h/2[v1]")
        vcur = "v1"
        idx += 1
    amap = None
    if has_bgm:                                       # 배경음악(나레이션 위 낮은 볼륨)
        inputs += ["-i", bgm_path]
        vol = max(0.0, min(1.0, (bgm.get("volume", 15)) / 100.0))
        fc.append(f"[{idx}:a]aloop=loop=-1:size=2000000000,volume={vol:.3f}[bg]")
        fc.append("[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]")
        amap = "[a]"
        idx += 1
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{vcur}]"]
    cmd += (["-map", amap, "-c:a", "aac"] if amap else ["-map", "0:a", "-c:a", "copy"])
    cmd += ["-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)]
    _run_ffmpeg(cmd, cwd=str(work))
    return str(out_path)


def assemble(edit_plan, tts_paths, source_video_paths, out_path, clean_fn=None, headcopy=None, caption_style=None, deco=None):
    """EDL → 최종 mp4. 1)믹스(자막X) 2)clean_fn(있으면 자막제거) 3)우리 자막.
    clean_fn(mix_raw_path)->clean_path 를 주면 그 사이에 VMake 자막제거가 끼워진다
    (없으면 생략). 자막제거는 우리 자막을 굽기 전 깨끗한 믹스에 돌려야 우리 자막이
    함께 지워지지 않는다."""
    work = Path(out_path).parent / f"asm_{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    mix_raw = _render_mix(edit_plan, tts_paths, source_video_paths, work)
    base_video = clean_fn(mix_raw) if clean_fn else mix_raw
    return _burn_captions(base_video, edit_plan, tts_paths, out_path, work, headcopy, caption_style, deco)
