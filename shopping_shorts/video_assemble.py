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
import re
import shutil
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

from PIL import ImageFont

# 출력 규격(숏폼 세로). 소스 해상도가 달라도 여기로 통일해야 concat -c copy가 안전.
_OUT_W, _OUT_H = 720, 1280
_FONT_DIR = Path(__file__).parent / "static" / "fonts"
# 반중복탐지 회피(2026-07-14) — 말 안 해도 항상 적용. 화질 오염 없는(비가역 손상X)
# 것만 자동화: ①전 비트 기본 크롭+줌(살짝 확대, 원본과 프레임 구도가 달라짐)
# ②중요 비트(훅·반전)만 서서히 확대되는 켄번즈 줌(더 눈에 띄는 변형+시선 유도 효과 겸함).
# 좌우반전은 제외 — 원본 화면 속 글자·로고가 있으면 뒤집혀서 오염돼 보일 위험이 있어
# "화질 오염 없이"라는 기준에 안 맞는다고 판단(2026-07-14).
_BASE_ZOOM = 1.04          # 전 비트 기본 확대율(정적, 저비용)
_KENBURNS_ZOOM = 1.10       # 중요 비트 최종 확대율(동적)
_IMPORTANT_ROLES = {"훅", "반전"}  # edit_plan.py _REQUIRED_ROLES와 동일 어휘


def _important_beat_indices(beats):
    """훅·반전 롤 비트만 켄번즈 대상. 스크립트모드(produce.html 2단계)는 role이
    안 채워지므로(edit_plan._SCRIPTED_PROMPT가 role을 요구 안 함) 그때는 첫 비트
    (오프닝 훅 역할)만 켄번즈로 폴백한다."""
    idxs = {b["beat_idx"] for b in beats if (b.get("role") or "") in _IMPORTANT_ROLES}
    if not idxs and beats:
        idxs = {beats[0]["beat_idx"]}
    return idxs


def _kenburns_vf(duration_sec, fps=30, zoom_end=_KENBURNS_ZOOM):
    """서서히 확대되는 줌(켄번즈) vf. zoompan은 self-referencing 'zoom+step' 방식이
    비디오 입력(정지이미지 아님)에서 상태가 안 이어져 매 프레임 그대로 있는 버그가
    있어(2026-07-14 로컬 실측: 89px→89px, 안 움직임), 출력 프레임번호 'on'을 직접
    식에 넣는 방식으로 고쳤다('on' 사용 시 89px→97px로 실제 확대 확인됨)."""
    frames = max(1, round(duration_sec * fps))
    step = (zoom_end - 1) / frames
    pre_w, pre_h = int(_OUT_W * 1.3), int(_OUT_H * 1.3)  # zoompan 전에 여유있게 확대해둬야 크롭 여백이 남는다
    return (
        f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
        f"zoompan=z='min(1+{step:.8f}*on,{zoom_end})':d=1:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={_OUT_W}x{_OUT_H}:fps={fps}"
    )


def _base_zoom_vf():
    """일반 비트 기본 크롭+줌(정적, 저비용) — 원본과 프레임 구도만 살짝 달라지게."""
    w, h = int(_OUT_W * _BASE_ZOOM), int(_OUT_H * _BASE_ZOOM)
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"
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
    """나레이션 한 비트의 자막(하단 바 + 순차 drawtext)을 필터 문자열 리스트로 반환한다.
    _segmented_drawtext 기반: highlight_rules가 있으면 단어별 강조, 없으면 세그먼트 1개
    (기존과 동일 산출물). 각 구절 enable 구간은 t0(전체 타임라인 오프셋)만큼 밀린다."""
    segs = _caption_segments(narration)
    if not segs:
        return []
    style = style or {}
    durs = _caption_durations(segs, dur)
    size = max(10, int(style.get("size") or _CAP_FONTSIZE))
    ypct = style.get("y_pct")
    if ypct is None:
        # 기존 폴백 "h-text_h-100"의 근사치를 %로 환산(문자 높이는 size*1.2로 근사)
        ypct = max(0.0, min(100.0, (_OUT_H - 100 - size * 0.6) / _OUT_H * 100.0))
    use_box = bool(style.get("box"))
    show_bar = style.get("bar", True) and not use_box
    effect = style.get("effect") or "none"
    parts = []
    if show_bar:
        parts.append(f"drawbox=x=0:y=ih-{_BAR_H}:w=iw:h={_BAR_H}:color=black@0.82:t=fill")
    t = 0.0
    for i, (seg, d) in enumerate(zip(segs, durs)):
        start = t + t0
        t += d
        end = (dur + 0.5 if i == len(segs) - 1 else t) + t0
        seg_parts = _segmented_drawtext(
            seg, style, work, f"cap_{idx}_{i}", 50, ypct,
            highlight_rules=style.get("highlight_rules"), default_color="0xFFFFFF",
        )
        enable_clause = f"enable='between(t,{start:.2f},{end:.2f})'"
        for sp in seg_parts:
            if effect == "slide":
                # _segmented_drawtext가 만든 "y=<정수>"를 시간기반 슬라이드 표현식으로 치환.
                # 기존 로직과 동일하게 등장 0.25초 동안 +30px 아래에서 위로 미끄러짐.
                sp = re.sub(
                    r"y=(-?\d+)",
                    lambda m: f"y=({m.group(1)}+30*(1-min(1\\,(t-{start:.2f})/0.25)))",
                    sp, count=1,
                )
            elif effect in ("fade", "pop"):
                spd = 0.18 if effect == "fade" else 0.12
                sp = sp + f":alpha='min(1,max(0,(t-{start:.2f})/{spd}))'"
            parts.append(sp + ":" + enable_clause)
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
    -vf는 우리 자막 vf가 아니라 규격 통일용 base(scale/crop)만 쓴다.
    반중복탐지 회피(항상 자동): 훅·반전 비트는 켄번즈 줌, 나머지는 기본 크롭+줌."""
    important = _important_beat_indices(edit_plan["beats"])
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
        vf = _kenburns_vf(tts_dur) if idx in important else _base_zoom_vf()
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
            "-vf", vf, "-r", "30",
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


def _motion_layer_filters(layers, next_input_idx, vcur):
    """해석완료 레이어 리스트(_abspath 보유) → filter_complex 조각.
    각 레이어를 vcur 위에 투명 오버레이로 얹는다. dur=None이면 enable 생략(전체 재생).
    반환: (input_args, fc_parts, vcur_out, next_input_idx_out).
    - input_args: ffmpeg에 추가할 ["-i", path, ...]
    - fc_parts: filter_complex 세미콜론 조각 리스트
    - vcur_out: 마지막 비디오 스트림 라벨(다음 필터가 이어받음)
    """
    input_args = []
    fc = []
    idx = next_input_idx
    for i, L in enumerate(layers or []):
        path = L.get("_abspath")
        if not path:
            continue
        input_args += ["-i", path]
        w = L.get("width")
        scale = f"scale={int(w)}:-1," if w else ""
        aa = max(0.0, min(1.0, float(L.get("alpha", 1))))
        xf = min(1.0, max(0.0, float(L.get("x", 50)) / 100.0))
        yf = min(1.0, max(0.0, float(L.get("y", 50)) / 100.0))
        lab, out = f"ml{i}", f"mlv{i}"
        fc.append(f"[{idx}:v]{scale}format=rgba,colorchannelmixer=aa={aa:.2f}[{lab}]")
        start = float(L.get("start") or 0)
        dur = L.get("dur")
        en = f":enable='between(t,{start:.3f},{start + float(dur):.3f})'" if dur is not None else ""
        fc.append(f"[{vcur}][{lab}]overlay=x=W*{xf:.4f}-w/2:y=H*{yf:.4f}-h/2{en}[{out}]")
        vcur = out
        idx += 1
    return input_args, fc, vcur, idx


def _hex_to_ff(c, default="0xFFFFFF"):
    """'#FF8800' → '0xFF8800' (ffmpeg drawtext color). 이상하면 default."""
    c = (c or "").strip().lstrip("#")
    return f"0x{c.upper()}" if len(c) == 6 and all(ch in "0123456789ABCDEFabcdef" for ch in c) else default


def _resolve_seg_font(base_style, work, key_prefix):
    """세그먼트 폰트파일 경로(work에 복사된 실제 경로)와 ffmpeg fontfile 참조명을 함께 반환.
    _fixed_drawtext/_caption_drawtexts의 폰트 해석 로직과 동일 규칙(있으면 그 폰트, 없으면 font.ttf)."""
    fontref = "font.ttf"
    fname = os.path.basename((base_style or {}).get("font") or "")
    if fname:
        fpath = _FONT_DIR / fname
        if fpath.exists():
            shutil.copy(fpath, work / f"font_{key_prefix}.ttf")
            fontref = f"font_{key_prefix}.ttf"
    real_path = work / fontref if (work / fontref).exists() else _FONT_DIR.parent.parent / fontref
    return fontref, str(work / fontref)


def _match_highlight(word, highlight_rules):
    """word가 highlight_rules의 keyword와 정확히 일치하면 그 규칙(dict) 반환, 아니면 None."""
    for rule in (highlight_rules or []):
        if rule.get("keyword") and word == rule["keyword"]:
            return rule
    return None


def _build_segments(line, base_color, highlight_rules):
    """한 줄 텍스트를 공백 기준 토큰화하고, 연속된 동일 스타일(강조 or 기본) 토큰을 묶어
    [(text, color, box, box_color), ...] 세그먼트 리스트로 반환. 사이 공백은 각 세그먼트
    텍스트에 뒤따르는 공백으로 포함시켜(마지막 세그먼트 제외) 폭 계산 시 자연스럽게 처리한다."""
    words = line.split(" ")
    segs = []
    cur_text, cur_style = "", None
    for i, w in enumerate(words):
        rule = _match_highlight(w, highlight_rules)
        style = (rule["color"], bool(rule.get("box")), rule.get("box_color")) if rule else (base_color, False, None)
        piece = w + (" " if i < len(words) - 1 else "")
        if cur_style is None:
            cur_text, cur_style = piece, style
        elif style == cur_style:
            cur_text += piece
        else:
            segs.append((cur_text, *cur_style))
            cur_text, cur_style = piece, style
    if cur_text:
        segs.append((cur_text, *cur_style))
    return segs


def _segmented_drawtext(text, base_style, work, key_prefix, x_pct, y_pct,
                          highlight_rules=None, default_color="0xFFFFFF"):
    """헤드카피/자막 한 블록을 줄 단위로 나누고, highlight_rules에 매칭되는 단어만
    별도 색·배지로 세그먼트를 쪼개 나란히 이어붙인 drawtext 필터 리스트를 반환한다.
    규칙이 없거나 매칭 0건이면 줄마다 세그먼트 1개 = 기존 _fixed_drawtext/_caption_drawtexts와
    동일한 산출물(하위호환). 폭 측정은 Pillow로 실제 폰트파일 기준 수행."""
    base_style = base_style or {}
    lines = (text or "").split("\n")
    if not any(l.strip() for l in lines):
        return []
    fontref, font_disk_path = _resolve_seg_font(base_style, work, key_prefix)
    size = max(8, int(base_style.get("size") or 64))
    try:
        pil_font = ImageFont.truetype(font_disk_path, size)
    except OSError:
        pil_font = ImageFont.load_default()
    base_color_raw = base_style.get("color")  # 원시 #hex(또는 None) — _hex_to_ff는 drawtext 빌드에서 1회만 적용(이중변환 방지)
    x_center = x_pct / 100.0 * _OUT_W
    y_top = y_pct / 100.0 * _OUT_H
    line_h = size * 1.2
    total_h = line_h * len(lines)
    parts = []
    for li, line in enumerate(lines):
        segs = _build_segments(line, base_color_raw, highlight_rules or [])
        if not segs:
            continue
        widths = [pil_font.getlength(s[0]) for s in segs]
        line_w = sum(widths)
        start_x = x_center - line_w / 2
        line_y = y_top - total_h / 2 + li * line_h
        run_x = start_x
        for (seg_text, seg_color, seg_box, seg_box_color), w in zip(segs, widths):
            if not seg_text.strip():
                run_x += w
                continue
            key = f"{key_prefix}_{li}_{len(parts)}"
            (work / f"txt_{key}.txt").write_text(seg_text.rstrip(), encoding="utf-8")
            seg_parts = [
                f"drawtext=fontfile={fontref}:textfile=txt_{key}.txt",
                f"fontcolor={_hex_to_ff(seg_color, default_color)}",
                f"fontsize={size}",
                f"x={int(run_x)}", f"y={int(line_y)}",
            ]
            if base_style.get("outline"):
                seg_parts.append(f"borderw={max(1, int(base_style.get('outline_w') or 6))}")
                seg_parts.append(f"bordercolor={_hex_to_ff(base_style.get('outline_color'), '0x000000')}")
            if seg_box:
                bc = _hex_to_ff(seg_box_color, "0x000000")
                seg_parts += ["box=1", f"boxcolor={bc}@0.90", "boxborderw=8"]
            elif base_style.get("box") and not seg_box:
                bc = _hex_to_ff(base_style.get("box_color"), "0x000000")
                op = max(0.0, min(1.0, (base_style.get("box_opacity") or 80) / 100.0))
                pad = max(0, int(base_style.get("box_pad") if base_style.get("box_pad") is not None else 16))
                seg_parts += ["box=1", f"boxcolor={bc}@{op:.2f}", f"boxborderw={pad}"]
            parts.append(":".join(seg_parts))
            run_x += w
    return parts


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


def _headcopy_drawtext_parts(hc, work, enable=None):
    """헤드카피 drawtext 필터 리스트 — _segmented_drawtext 래퍼(기본색 오렌지).
    hc['highlight_rules']가 있으면 단어별 강조, 없으면 세그먼트 1개(기존과 동일).
    enable(ffmpeg between 식)이 주어지면 노출 구간을 제한한다(팩 headcopy.policy=hook_only).
    None이면 기존대로 영상 전체 고정 표시.
    """
    parts = _segmented_drawtext(
        hc.get("text", ""), hc, work, "hc", hc.get("x", 50), hc.get("y", 14),
        highlight_rules=hc.get("highlight_rules"), default_color="0xFF8800",
    )
    if not enable:
        return parts
    return [f"{p}:enable='{enable}'" for p in parts]


def _merge_highlight_rules(headcopy, caption_style, deco):
    """강조 단어 규칙(deco.highlight_rules)을 헤드카피·자막 스타일 dict 양쪽에 주입한다.
    규칙은 UI에서 deco에 저장되지만 렌더는 headcopy/caption_style에서 읽으므로 여기서 잇는다.
    각 dict가 이미 자체 highlight_rules를 가지면 그것을 우선(덮어쓰지 않음).
    원본 dict를 변형하지 않고 얕은 복사본을 반환한다."""
    hl = (deco or {}).get("highlight_rules")
    if not hl:
        return headcopy, caption_style
    if headcopy is not None and not headcopy.get("highlight_rules"):
        headcopy = {**headcopy, "highlight_rules": hl}
    if not (caption_style or {}).get("highlight_rules"):
        caption_style = {**(caption_style or {}), "highlight_rules": hl}
    return headcopy, caption_style


def _beat_timeline(edit_plan, tts_paths):
    """비트별 전체 타임라인 [{beat_idx, t0, dur, narration, role}, ...].

    자막(_burn_captions)과 모션(motion_packs)이 **같은 경계**를 쓰도록 하는 단일 출처.
    여기서 중복 계산하면 전환이 자막과 어긋난다. tts 없는 비트는 건너뛴다(기존 동작).
    """
    timeline = []
    t0 = 0.0
    for beat in edit_plan["beats"]:
        idx = beat["beat_idx"]
        tts = tts_paths.get(idx)
        if not tts:
            continue
        dur = _probe_duration(tts)
        timeline.append({
            "beat_idx": idx,
            "t0": t0,
            "dur": dur,
            "narration": beat.get("narration", ""),
            "role": beat.get("role", ""),
        })
        t0 += dur
    return timeline


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
        print("[motion] 폰트 미해결 — 자막·모션·색감·오버레이·BGM 전부 스킵하고 원본 복사",
              file=sys.stderr)
        shutil.copy(in_video, out_path)
        return str(out_path)
    headcopy, caption_style = _merge_highlight_rules(headcopy, caption_style, deco)
    filters = [f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"]
    # 색감 필터는 drawtext보다 **앞**에 온다 — 뒤에 두면 자막·헤드카피까지 색보정에 물든다.
    _color_filter = ((deco or {}).get("motion") or {}).get("color_filter") or ""
    if _color_filter.strip():
        filters.append(_color_filter.strip())
    timeline = _beat_timeline(edit_plan, tts_paths)
    for b in timeline:
        filters.extend(_caption_drawtexts(b["narration"], b["dur"], work, b["beat_idx"],
                                          b["t0"], caption_style))
    if headcopy and (headcopy.get("text") or "").strip():
        # enable 없으면 전체 표시(기존). 팩이 hook_only면 렌더 파생값 _headcopy_enable이 온다.
        hc_enable = ((deco or {}).get("motion") or {}).get("_headcopy_enable")
        filters.extend(_headcopy_drawtext_parts(headcopy, work, enable=hc_enable))
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
    # 모션(전환·스티커 등 타임드 투명 레이어)과 색감 필터
    motion = deco.get("motion") or {}
    motion_layers = [L for L in (motion.get("layers") or []) if L.get("_abspath")]
    has_motion = bool(motion_layers)
    if not has_bgm and not has_overlay and not has_motion:
        base_vf = vf
        _run_ffmpeg(["ffmpeg", "-y", "-i", str(in_video), "-vf", base_vf, "-r", "30",
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
    if has_motion:                                    # 전환·스티커 등 타임드 투명 레이어
        m_inputs, m_fc, vcur, idx = _motion_layer_filters(motion_layers, idx, vcur)
        inputs += m_inputs
        fc += m_fc
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
