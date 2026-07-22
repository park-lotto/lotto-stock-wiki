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
# 의존명사(홀로 자막이 되면 뜻이 없어 앞말에 붙어야 하는 말) — 1어절 꼬리로 남으면 앞 구절에 병합.
# "…식단" | "때문?" → "…식단 때문?". 글자수가 아니라 품사로 판별(독립명사 "대박"·"가루"는 안 붙임).
_CAP_BOUND_NOUN = {"때문", "때", "것", "수", "뿐", "등", "데", "줄", "채", "척", "터", "만큼", "대로", "듯"}
# ── 머리 단어(head-marker): 이 단어를 만나면 그 **앞에서** 끊고, 이 단어가 다음
#    구절의 머리가 된다(뒤 명사/서술어를 데려간다). "…일쑤였는데 | 이 방법은"처럼
#    관형어 "이"가 앞 구절 꼬리에 남지 않게 한다. 관형사·지시어·부사·수관형사.
_CAP_HEAD = {"이", "그", "저", "한", "두", "세", "네", "몇", "각", "매", "총",
             "이런", "저런", "그런", "무슨", "어떤", "온갖", "단", "딱", "약",
             "자세한", "확실한", "특별한", "간단한", "완벽한",
             "바로", "그냥", "그대로", "다시", "먼저", "이제", "지금", "꼭", "막",
             "가장", "제일", "훨씬", "더", "덜", "약간", "좀", "진짜", "정말",
             # 양태부사(뒤 서술어를 꾸며 반드시 앞에서 끊고 뒤로 붙는다): "뚝 떨어지다"
             "뚝", "확", "쭉", "싹", "푹", "팍", "툭", "쫙", "쓱", "훅"}
# ── 도입어(lead): 이 단어(로 끝나는 어절)는 한 호흡을 열고 **뒤에서** 끊는다.
#    호격("여러분")·연결 도입("남겨주시면") 등 그 자체로 한 박자.
_CAP_LEAD = {"여러분", "여러분,", "자"}
# 연결어미로 끝나는 절은 뒤에서 끊어 한 박자를 준다(…하면 | …했는데 |). 단 "-서"는
# 장소조사 "-에서/-께서"와 어미 "-아서/-어서"가 섞여 오탐이 잦아 제외한다. 또 이
# 끊기는 앞 절이 충분히 길 때(_CAP_LEAD_MINCHARS↑)만 적용해 "밭에서"(짧음)는 안 끊는다.
_CAP_LEAD_SUFFIX = ("면", "면서", "니까", "는데", "지만", "거든", "잖아")
_CAP_LEAD_MINCHARS = 4  # 연결어미 끊기 최소 글자수(공백 제외). 이보다 짧으면 이어붙임.
# 시간/빈도 도입 부사(아침마다·날마다·집집마다)는 자기 뒤에서 끊어 한 박자를 연다 →
# 뒤에 오는 '수식어+명사'가 3어절 하드캡에 밀려 쪼개지지 않는다("빵 달라는 아이"가 온전히
# 묶임, 2026-07-20 사장님 제보). "마다"는 항상 부사/보조사라 뒤에서 끊어도 안전(글자수 무관).
_CAP_OPENER_SUFFIX = ("마다",)
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


# ⚠️ ffmpeg/ffprobe는 stderr를 **UTF-8**로 낸다. text=True만 주면 파이썬이 로캘
# (윈도우=cp949)로 디코드하다 subprocess 리더 스레드에서 UnicodeDecodeError로 죽고,
# 그 결과 stdout/stderr가 **None**이 된다. 이 저장소는 한글 파일명이 도처에 있어
# 흔히 밟는 경로다(Task9 리포트 §5가 관측·기록). 재현(2026-07-16):
#   _run_ffmpeg(["ffmpeg","-i","없는영상_한글이름.mp4", ...])
#     → 리더 스레드 UnicodeDecodeError → r.stderr=None
#     → r.stderr[-1000:] → TypeError: 'NoneType' object is not subscriptable
#   = "원인을 삼키지 않는다"던 함수가 **정확히 원인을 삼켰다.**
# → 인코딩을 명시하고 못 읽는 바이트는 대체한다. 로그가 조금 깨질지언정 원인은 남는다.
_FF_TEXT = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"}


def _probe_duration(path):
    """ffprobe로 미디어 길이(초)."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    out = subprocess.run(cmd, stdin=subprocess.DEVNULL, check=True, **_FF_TEXT)
    return float(out.stdout.strip())


_TRIM_FLOOR = 0.4  # 비트 트림 후 남길 최소 길이(초). 과트림·역전 방지.


def _effective_dur(probe, head_trim=0.0, tail_trim=0.0, floor=_TRIM_FLOOR):
    """probe(원본 TTS 길이)에서 앞/뒤 트림을 뺀 실질 비트 길이. 하한 가드 포함.
    음수 트림은 0으로 취급. 결과가 floor 밑이면 floor로 고정한다."""
    d = probe - max(0.0, head_trim) - max(0.0, tail_trim)
    return max(floor, d)


def _beat_effective_dur(beat, tts_path):
    """비트 dict의 head_trim/tail_trim을 반영한 실질 길이(단일 출처)."""
    return _effective_dur(_probe_duration(tts_path),
                          beat.get("head_trim", 0.0), beat.get("tail_trim", 0.0))


def _run_ffmpeg(cmd, cwd=None):
    """ffmpeg 실행. 실패 시 stderr를 예외에 담아 원인을 삼키지 않는다.
    stdin=DEVNULL 필수(Windows): pytest 캡처 중에는 부모 stdin 핸들이 유효하지
    않아, 명시 안 하면 subprocess가 그 핸들을 상속하려다 OSError([WinError 6]
    핸들이 잘못되었습니다)로 죽는다(2026-07-18 Task2 grounding 테스트 실측 — 이미
    _probe_duration은 이 패턴을 쓰고 있었다, 여기만 누락돼 있었다)."""
    r = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, **_FF_TEXT)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패(exit {r.returncode}): {(r.stderr or '')[-1000:]}")
    return r


_MIN_CLIP = 0.8   # 초. 이보다 짧은 독립 클립은 만들지 않는다(깜빡임 방지).
# 연속도 아닌 짧은 클립을 흡수(=정지 유발)하는 하한. 0.5초 이상 움직이는 실클립은 흡수하지 않고
# 그대로 둔다 — 짧게 움직이는 게 정지프레임보다 낫다는 사장님 피드백(2026-07-21).
_MIN_CLIP_KEEP = 0.5

# 슬로우모션 상한. 소스가 나레이션보다 짧을 때 무제한으로 늘리면(옛 동작) 부자연스러운
# 슬로우크롤이 됐다(사장님 실측, 2026-07-19). 재생은 최대 이 배율까지만 늘리고, 그 이상
# 필요한 시간은 마지막 프레임 정지(freeze)로 떠안는다 → 요리 동작은 자연 속도, 남는 시간만 홀드.
_MAX_SLOWMO = 1.15

# 마지막 비트 '여운'(초) — 대사가 끝나도 화면을 이만큼 더 살려둔다(2026-07-20 콘폼루프 T4,
# 사장님 육안 피드백 "붙이면 바로 자르지 말고 대사 끝나고 1초 정도 더 냅두면").
_LAST_RUNOUT = 1.0


def _speed_and_freeze(src_dur, out_dur, max_slowmo=_MAX_SLOWMO):
    """소스 구간 src_dur초를 출력 out_dur초로 채울 때, (움직이는 재생 길이, 정지프레임 길이).

    - out_dur ≤ src_dur: 늘릴 필요 없음 → (out_dur, 0).
    - 필요한 배율이 상한 이내: 그대로 완만한 슬로우 → (out_dur, 0).
    - 상한 초과: 재생은 src_dur*max_slowmo까지만, 나머지는 freeze로 → (capped, out_dur-capped).

    항상 play_out + freeze == out_dur (총 길이·오디오/자막 싱크 보존)."""
    if src_dur <= 1e-9 or out_dur <= src_dur:
        return (out_dur, 0.0)
    capped = src_dur * max_slowmo
    if out_dur <= capped + 1e-9:
        return (out_dur, 0.0)
    return (capped, out_dur - capped)


def _extend_last_clip_for_runout(plan, segs, runout=_LAST_RUNOUT):
    """마지막 비트 계획의 끝에 여운 runout초를 붙인다(plan 제자리 수정, 반환 동일 객체).

    소스 구간 [start,end]에 실프레임 여유(slack)가 남았으면 그만큼 **1배속 실영상**으로
    연장하고, 부족분은 out_dur만 늘려 기존 _speed_and_freeze 기계(완만 슬로모→켄번즈 홀드)가
    흡수한다. 오디오는 tts 그대로라 마지막 1초는 자연스러운 무성 여운이 된다 —
    mux의 -t가 이 여운만큼 같이 늘어나야 화면에 실린다(assemble 쪽 runout 참조)."""
    if not plan or runout <= 0:
        return plan
    c = plan[-1]
    seg = next((s for s in segs
                if s.get("video_id") == c.get("video_id")
                and float(s.get("start", 0.0)) <= float(c.get("start", 0.0)) < float(s.get("end", 0.0))),
               None)
    slack = 0.0
    if seg:
        slack = max(0.0, float(seg["end"]) - (float(c["start"]) + float(c["src_dur"])))
    real_ext = min(runout, slack)
    c["src_dur"] += real_ext
    c["out_dur"] += runout
    return plan


def _plan_beat_clips(segments, tts_dur, min_clip=_MIN_CLIP, src_durs=None, max_shot=None):
    """비트의 순서 구간 리스트 → 나레이션 길이(tts_dur)에 맞춘 클립 계획.
    각 클립은 자기 구간 [start,end]를 절대 넘지 않는다(유출 0). 부족분은 아래 정책으로 채운다.
    반환: [{"video_id","start","src_dur","out_dur"}, ...]

    ★멈추지 말고 진짜 영상으로(2026-07-20 사장님): 배정 구간을 다 써도 모자라면, 소스 릴은
    보통 구간보다 훨씬 길어(구간 2초 vs 릴 30초) 뒤에 실프레임이 남아있다. `src_durs`
    ({video_id: 소스총길이})가 주어지면 마지막 클립의 읽기 창을 소스에 남은 만큼 더 늘려
    **1배속 실영상**으로 채운다 → freeze/억지슬로우 없음. 소스까지 소진돼야만 슬로모 폴백.
    src_durs 미제공(하위호환)이면 예전처럼 마지막 클립을 슬로모로 늘린다.

    max_shot(2026-07-22): 한 컷을 이보다 오래 안 끈다 — 세그먼트를 이 상한 청크로 **번갈아**
    재생(라운드로빈)해 긴 정지(7초 홀드) 대신 distinct 앵글로 컷한다(벤치마크 ~1.1초 컷 밀도).
    같은 세그먼트는 창을 앞으로 밀며 재생(정지 아님). None/0이면 옛 동작(세그 통째 재생)."""
    eps = 1e-3
    clips = []
    filled = 0.0
    if max_shot and max_shot > eps and len(segments) > 1:
        # 라운드로빈: distinct 세그먼트를 max_shot씩 번갈아 → 컷 밀도↑. 각 세그 읽기위치를 유지해
        # 다시 올 땐 이어서 재생(같은 프레임 반복 아님). 다 소진되면 아래 공통 shortfall로.
        pos = [seg["start"] for seg in segments]
        oi, guard0 = 0, 0
        while tts_dur - filled > eps and guard0 < 2000:
            guard0 += 1
            i = oi % len(segments); oi += 1
            seg = segments[i]
            avail = seg["end"] - pos[i]
            if avail <= eps:
                if all(segments[k]["end"] - pos[k] <= eps for k in range(len(segments))):
                    break                          # 전 세그 소진 → shortfall 정책으로
                continue
            take = min(avail, max_shot, tts_dur - filled)
            clips.append({"video_id": seg["video_id"], "start": pos[i],
                          "src_dur": take, "out_dur": take})
            pos[i] += take
            filled += take
    else:
        for seg in segments:
            remaining = tts_dur - filled
            if remaining <= eps:
                break
            seg_len = seg["end"] - seg["start"]
            if seg_len <= eps:
                continue
            take = min(seg_len, remaining)   # 1배속으로 이만큼 재생(구간 이내)
            clips.append({"video_id": seg["video_id"], "start": seg["start"],
                          "src_dur": take, "out_dur": take})
            filled += take

    if not clips:
        # 구간이 하나도 못 쓰였다(모두 길이 0). 첫 구간을 tts_dur로 슬로모(방어적 폴백).
        seg = segments[0]
        return [{"video_id": seg["video_id"], "start": seg["start"],
                 "src_dur": max(seg["end"] - seg["start"], eps), "out_dur": tts_dur}]

    shortfall = tts_dur - filled
    if shortfall > eps:
        # 1순위: 마지막 클립을 그 소스에 남은 실프레임으로 연장(1배속) — 릴이 배정 구간보다 길다.
        if src_durs:
            last = clips[-1]
            sdur = src_durs.get(last["video_id"], 0.0)
            avail = max(0.0, sdur - (last["start"] + last["src_dur"]))
            real_ext = min(shortfall, avail)
            if real_ext > eps:
                last["src_dur"] += real_ext
                last["out_dur"] += real_ext
                shortfall -= real_ext
        # 2순위(★멈춤·슬로우 없음, 2026-07-20 사장님 확정): 그래도 모자라면 실영상을 '한 장면
        #   더 붙여' 채운다. 비트 세그먼트를 순환하며 새 클립(1배속)으로 이어붙인다 — 릴을
        #   앞에서부터 다시 재생(루프)해서라도 화면은 진짜로 움직인다. 슬로모/정지프레임 금지.
        guard = 0
        while shortfall > eps and guard < 500:
            guard += 1
            progressed = False
            for seg in segments:
                if shortfall <= eps:
                    break
                seg_len = seg["end"] - seg["start"]
                if seg_len <= eps:
                    continue
                take = min(seg_len, shortfall)
                clips.append({"video_id": seg["video_id"], "start": seg["start"],
                              "src_dur": take, "out_dur": take})
                shortfall -= take
                progressed = True
            if not progressed:
                break
        # 3순위(극단 방어 — 쓸 실영상이 아예 0인 비정상 경로에서만): 최소한만 홀드.
        if shortfall > eps:
            clips[-1]["out_dur"] += shortfall

    # 0.8초 미만 독립 클립 제거: 그런 클립을 이웃에 흡수. 합계(sum out_dur)는 보존된다.
    # ★흡수를 정지프레임으로 떠넘기지 않는다(2026-07-21 사장님 "화면 멈춤"): 이웃이 같은 소스의
    #   연속 구간이면 src_dur도 늘려 **실프레임**으로 흡수한다. 안 그러면 2순위 루프가 실영상
    #   움직임으로 채운 짧은 클립들이 여기서 다시 out_dur만 부풀어 프리즈로 되돌아갔다(실측:
    #   b3 CTA 비트 0.97초 정지의 정체). 연속도 아니고 볼 만큼(≥_MIN_CLIP_KEEP) 움직이면 흡수
    #   안 하고 그대로 둔다 — 짧은 움직임이 정지보다 낫다.
    def _contig(nb, k):
        n, s = clips[nb], clips[k]
        return (n["video_id"] == s["video_id"]
                and abs((n["start"] + n["src_dur"]) - s["start"]) < 0.05)

    def _absorbable(k):
        if clips[k]["out_dur"] >= min_clip - eps:
            return False
        nb = k - 1 if k > 0 else k + 1
        return _contig(nb, k) or clips[k]["out_dur"] < _MIN_CLIP_KEEP - eps

    while len(clips) > 1:
        idx = next((k for k in range(len(clips)) if _absorbable(k)), None)
        if idx is None:
            break
        nb = idx - 1 if idx > 0 else idx + 1
        neigh = clips[nb]
        if _contig(nb, idx):
            neigh["src_dur"] += clips[idx]["src_dur"]   # 실프레임 연장 → 정지 안 생김
        neigh["out_dur"] += clips[idx]["out_dur"]
        clips.pop(idx)
    return clips


def _strip_punct(w):
    """조사·문장부호를 뗀 순수 단어(머리/도입어 판정용). '이,' → '이'."""
    return w.strip(".,!?…\"'()[]")


# 자막 각 줄 끝에서 뗄 문장부호(마침표·쉼표·말줄임). 감탄/의문(? !)·물결(~)은 톤이라 남긴다.
_CAP_TRIM_TAIL = ".,、，。…"


def _strip_cap_tail(s):
    """표시용 — 자막 한 줄 끝의 마침표·쉼표·말줄임만 뗀다('봤잖아요.'→'봤잖아요'). ?!~는 유지."""
    s = s.rstrip()
    while s and s[-1] in _CAP_TRIM_TAIL:
        s = s[:-1].rstrip()
    return s


def _wrap_long(segs):
    """구절 리스트에서 _CAP_WRAP를 크게 넘는 초장문만 줄바꿈으로 방어(대부분 그대로 1줄).
    각 줄은 표시용으로 끝 문장부호를 정리한다(2026-07-21 사장님 '봤잖아요.' 마침표 노출)."""
    out = []
    for s in segs:
        s = _strip_cap_tail(s)
        if not s:
            continue
        if len(s.replace(" ", "")) > _CAP_WRAP:
            out.extend(textwrap.wrap(s, _CAP_WRAP) or [s])
        else:
            out.append(s)
    return out


def _caption_segments(narration, preset=None):
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

    방어: 목표를 크게 넘는 아주 긴 단일 어절은 _CAP_WRAP로 강제 줄바꿈.

    preset: 대본을 쓴 AI가 미리 끊어준 호흡 줄(list). 이어붙였을 때 narration과 정확히
    같으면(공백만 무시) 그대로 채택 — 규칙기반 두더지잡기를 근본적으로 대체한다(2026-07-21).
    글자가 하나라도 다르면(모델이 문장을 바꿈) 무시하고 아래 규칙 폴백으로 안전하게 내려간다."""
    narr = (narration or "").strip()
    if not narr:
        return []
    if preset and isinstance(preset, (list, tuple)):
        lines = [str(x).strip() for x in preset if str(x).strip()]
        if lines and "".join(lines).replace(" ", "") == narr.replace(" ", ""):
            return _wrap_long(lines)
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
            prev.endswith(_CAP_LEAD_SUFFIX) and cur_chars >= _CAP_LEAD_MINCHARS
        ) or prev.endswith(_CAP_OPENER_SUFFIX)   # 도입 부사(…마다)는 글자수 무관 뒤에서 끊음
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
    # 고아 꼬리 병합: 마지막 구절이 1어절짜리 의존명사 파편이면 앞 구절에 붙인다.
    #   "…아이, 범인은 식단" | "때문?" → "…아이, 범인은 식단 때문?"
    # 품사로 판별하므로 뜻 있는 독립어("대박"·"떨어지거든요.")는 그대로 둔다.
    if len(out) >= 2 and len(out[-1].split()) == 1 \
            and _strip_punct(out[-1]) in _CAP_BOUND_NOUN:
        out[-2] = out[-2] + " " + out[-1]
        out.pop()
    # 목표를 크게 넘는 초장문 단일 구절만 줄바꿈으로 방어(대부분은 그대로 1줄).
    return _wrap_long(out) or [narr]


def _caption_durations(segs, dur, real_durs=None):
    """각 구절의 표시 시간(초) 리스트를 반환. 기본은 글자수 비례(균등분할 X)지만,
    아주 짧은 구절(2~3자)이 순식간에 지나가지 않도록 _CAP_MIN_DUR 하한을 준다.
    하한을 채우고 남은 시간을 나머지 구절에 글자수 비례로 재분배해, 총합은 항상
    dur를 넘지 않는다(하한들의 합이 dur를 초과하면 균등분할로 폴백).

    real_durs가 주어지고(ASR 실측) len(real_durs)==len(segs)이며 합이 0을 넘으면
    글자수 비례 대신 그 값을 base로 쓴다(총합을 dur로 정규화). 그 외(None/길이
    불일치/합0)에는 기존 글자수 비례 경로와 바이트 동일하게 폴백한다."""
    n = len(segs)
    if n == 0:
        return []
    if _CAP_MIN_DUR * n >= dur:      # 하한조차 못 채우면 균등분할
        return [dur / n] * n
    if real_durs is not None and len(real_durs) == len(segs) and sum(real_durs) > 0:
        s = sum(real_durs)
        raw = [dur * d / s for d in real_durs]
    else:
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


def _caption_drawtexts(narration, dur, work, idx, t0=0.0, style=None, real_durs=None, cap_offset=0.0, tail=0.5, cap_lines=None):
    """나레이션 한 비트의 자막(하단 바 + 순차 drawtext)을 필터 문자열 리스트로 반환한다.
    _segmented_drawtext 기반: highlight_rules가 있으면 단어별 강조, 없으면 세그먼트 1개
    (기존과 동일 산출물). 각 구절 enable 구간은 t0(전체 타임라인 오프셋)만큼 밀린다.
    real_durs가 주어지면 _caption_durations에 그대로 전달해 ASR 실측 타이밍을 쓴다.
    cap_lines가 있으면(AI가 끊어준 호흡 줄) 그 경계를 그대로 쓴다 — 규칙 폴백은 안전망."""
    segs = _caption_segments(narration, preset=cap_lines)
    if not segs:
        return []
    style = style or {}
    durs = _caption_durations(segs, dur, real_durs=real_durs)
    size = max(10, int(style.get("size") or _CAP_FONTSIZE))
    ypct = style.get("y_pct")
    if ypct is None:
        # 기존 폴백 "h-text_h-100"의 근사치를 %로 환산(문자 높이는 size*1.2로 근사)
        ypct = max(0.0, min(100.0, (_OUT_H - 100 - size * 0.6) / _OUT_H * 100.0))
    use_box = bool(style.get("box"))
    # 하단 자막 바 기본 OFF(2026-07-19) — 300px·black@0.82 바가 화면 하단 23%를
    # 덮어 "검정바"로 보인다는 제보. 그림자 자막만으로 가독성 확보. 원본 소각자막을
    # 덮어야 하는 경우엔 style.bar=True로 명시적으로 켠다(자막제거 ON이면 불필요).
    show_bar = style.get("bar", False) and not use_box
    # 자막 등장효과 기본값 = fade(2026-07-19). 예전 기본 "none"은 자막이 하드
    # 온/오프로 뚝뚝 끊겨 "딱딱하다"는 제보의 원인이었다. 미지정 시 은은한 페이드로
    # 등장시킨다. 끄려면 effect="none"을 명시(문자열이라 truthy → 아래 폴백 안 탐).
    effect = style.get("effect") or "fade"
    parts = []
    if show_bar:
        # ⚠️ enable= 없이는 이 바가 영상 전체 시간대에 걸쳐 그려진다. _burn_captions가
        # 비트마다 _caption_drawtexts를 호출해 필터체인에 이어붙이므로(613~616줄),
        # enable 없는 바 N개가 겹쳐 black@0.82가 누적되어 마지막 비트를 제외한 모든
        # 비트의 자막이 거의 안 보이게 된다(2026-07-15 Task9 실렌더 검증 결함2,
        # 실측 밝기 9/255). 이 비트의 자막 표시 구간(t0 ~ 마지막 세그먼트 종료시각인
        # t0+dur+0.5, 아래 end 계산과 동일)에만 바를 그려 자막 텍스트의 enable 창과
        # 정확히 맞춘다.
        _bs = max(0.0, t0 + cap_offset)
        parts.append(
            f"drawbox=x=0:y=ih-{_BAR_H}:w=iw:h={_BAR_H}:color=black@0.82:t=fill:"
            f"enable='between(t,{_bs:.2f},{t0 + dur + tail + cap_offset:.2f})'"
        )
    t = 0.0
    for i, (seg, d) in enumerate(zip(segs, durs)):
        start = max(0.0, t + t0 + cap_offset)
        t += d
        end = (dur + tail if i == len(segs) - 1 else t) + t0 + cap_offset
        seg_parts = _segmented_drawtext(
            seg, style, work, f"cap_{idx}_{i}", 50, ypct,
            highlight_rules=style.get("highlight_rules"), default_color="0xFFFFFF",
            single_line=True,   # 자막은 무조건 한 줄(폭 넘으면 폰트 자동축소)
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
            elif effect == "sparkle":
                # 반짝(CTA/훅): 등장 0.7초 동안 알파가 여러 번 깜빡여 시선을 끈 뒤 고정.
                # abs(sin)로 0↔1 진동(약 3회) → 이후 1로 유지. 단일 quote 안이라 콤마 이스케이프 불필요.
                sp = sp + (
                    f":alpha='if(lt(t,{start:.2f}+0.7),"
                    f"0.30+0.70*abs(sin(2*PI*3*(t-{start:.2f}))),1)'"
                )
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


def _extend_with_frozen_motion(sub_path, play_out, freeze, out_path):
    """움직이는 클립(sub) 뒤에 freeze초 정지 구간을 붙이되, '죽은 정지'가 아니라 완만한
    켄번즈 줌을 전체(play+freeze)에 얹어 정지 구간에도 화면이 살아있게 한다(2026-07-19,
    P1 후속). 사장님 육안 피드백 — tpad clone 단독 홀드는 마지막 프레임이 픽셀까지 동일해
    뚝 멈춰 어색하다.

    한 체인에서 tpad→zoompan 순서로 건다. 예전 주석의 'zoompan은 tpad와 한 체인에서
    안 된다(출력 잘림)'는 반대 순서(zoompan→tpad)의 문제였다 — tpad를 먼저 두면 출력이
    정상 길이로 나온다(실측 2026-07-19). zoompan은 출력 프레임번호 'on'으로 확대하므로
    tpad가 만든 정지 프레임에서도 줌이 계속 진행돼 움직임이 유지된다."""
    total = play_out + freeze
    _run_ffmpeg([
        "ffmpeg", "-y", "-i", str(sub_path),
        "-vf", f"tpad=stop_mode=clone:stop_duration={freeze:.3f},{_kenburns_vf(total)}",
        "-r", "30", "-an", "-t", f"{total:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path),
    ])
    return out_path


def _render_mix(edit_plan, tts_paths, source_video_paths, work, cutaway_paths=None):
    """각 비트를 [소스영상+TTS]로 렌더(우리 자막 없음) → concat → mix_raw.mp4 경로.
    자막을 굽지 않으므로 이후 VMake 자막제거가 우리 자막을 지우지 않는다.
    -vf는 우리 자막 vf가 아니라 규격 통일용 base(scale/crop)만 쓴다.
    반중복탐지 회피(항상 자동): 훅·반전 비트는 켄번즈 줌, 나머지는 기본 크롭+줌."""
    important = _important_beat_indices(edit_plan["beats"])
    beat_clips = []
    # 소스 실제 길이 캐시(2026-07-19). 약한 매칭이 소스 밖 구간(예: 60초 릴에 155초)을 잡으면
    # -ss가 끝을 넘어 0프레임 서브클립 → concat "no stream" → 미리보기 전체가 죽었다. 소스별 길이를
    # 한 번만 재서(ffprobe) start를 소스 안으로 당긴다.
    _src_dur_cache = {}
    def _src_dur(vid):
        if vid not in _src_dur_cache:
            try:
                _src_dur_cache[vid] = _probe_duration(source_video_paths[vid])
            except Exception:
                _src_dur_cache[vid] = 0.0
        return _src_dur_cache[vid]
    # 여운 대상 = TTS가 있는 마지막 비트(2026-07-20 T4). 그 비트만 대사 끝+_LAST_RUNOUT초를
    # 화면에 더 싣는다(-t 연장 포함). 세그먼트 전멸로 스킵되면 여운도 조용히 사라진다(치명 아님).
    _runout_idx = max((b["beat_idx"] for b in edit_plan["beats"]
                       if tts_paths.get(b["beat_idx"])), default=None)
    for beat in edit_plan["beats"]:
        idx = beat["beat_idx"]
        tts = tts_paths.get(idx)
        if not tts:
            continue
        tts_dur = _beat_effective_dur(beat, tts)
        _head_trim = beat.get("head_trim", 0.0)
        # 순서 구간 리스트 = [primary] + alternates. 소스에 실재하고 + 디코드 가능한 것만.
        # 손상/빈 소스(_src_dur=0)는 여기서 걸러야 아래 -ss 렌더가 예외로 죽지 않는다(2026-07-19).
        segs = [s for s in ([beat["primary"]] + list(beat.get("alternates", [])))
                if s and s.get("video_id") in source_video_paths
                and _src_dur(s["video_id"]) > 0.05]
        if not segs:
            continue
        # 소스별 총길이를 넘겨 '멈춤 대신 소스 실프레임 더 재생'을 켠다(2026-07-20).
        beat_src_durs = {s["video_id"]: _src_dur(s["video_id"]) for s in segs}
        # 컷 밀도(2026-07-22): 한 컷을 MAX_SHOT_SECONDS 넘게 안 끌고 distinct 세그먼트를 번갈아
        # 재생 → 긴 정지 대신 컷(벤치마크급). 포인트 비트는 홀드가 맞으니 라운드로빈 안 함.
        from shopping_shorts import backbone as _bb, config as _cfg
        _max_shot = None if _bb.is_point_beat(beat) else getattr(_cfg, "MAX_SHOT_SECONDS", 0) or None
        plan = _plan_beat_clips(segs, tts_dur, src_durs=beat_src_durs, max_shot=_max_shot)
        # 마지막 비트 여운: 실프레임 여유는 1배속으로, 부족분은 아래 slowmo/freeze 기계가 흡수.
        runout = _LAST_RUNOUT if idx == _runout_idx else 0.0
        if runout > 0:
            _extend_last_clip_for_runout(plan, segs, runout)
        vf = _kenburns_vf(tts_dur) if idx in important else _base_zoom_vf()
        # 비트당 다중 클립: 각 구간을 [start, start+src_dur]만큼만 잘라(유출 0) 이어붙이고,
        # 부족분은 마지막 클립을 슬로모(setpts)로 늘려 대사 길이에 맞춘다.
        sub_paths = []
        for j, c in enumerate(plan):
            src = source_video_paths[c["video_id"]]
            sub = work / f"beat_{idx}_{j}.mp4"
            # 슬로우 상한(1.15배)+정지프레임(2026-07-19): 무제한 슬로우크롤 제거.
            # 재생은 최대 _MAX_SLOWMO배까지만 늘리고, 남는 시간은 마지막 프레임 정지(freeze).
            # play_out+freeze == out_dur → 총 길이·오디오/자막 싱크 불변.
            play_out, freeze = _speed_and_freeze(c["src_dur"], c["out_dur"])
            # freeze 클립은 움직이는 부분을 정적 베이스줌으로 두고, 켄번즈 모션은 freeze
            # 패스에서 전체(play+freeze)에 한 번만 건다(정지 구간도 살아있게, 2026-07-19).
            # 안 그러면 pass1 줌 + freeze 켄번즈가 겹쳐 줌이 두 번 쌓인다.
            clip_vf = _base_zoom_vf() if freeze > 1e-3 else vf
            factor = play_out / c["src_dur"] if c["src_dur"] > 1e-6 else 1.0
            vf_full = f"{clip_vf},setpts={factor:.6f}*PTS" if factor > 1.0 + 1e-6 else clip_vf
            # start를 소스 안으로 당긴다(타트랙 병합, 2026-07-19). 약한 매칭이 소스 밖을 잡으면
            #   -ss가 끝을 넘어 0프레임이 나와 concat이 죽는다. [start, start+src_dur]가 소스
            #   안에 들어오게 당기되, 소스가 src_dur보다 짧으면 0에서 있는 만큼 읽는다.
            sdur = _src_dur(c["video_id"])
            start = c["start"]
            if sdur > 0:
                start = max(0.0, min(start, sdur - min(c["src_dur"], sdur)))
            # 1단계 — 움직임: 입력을 [start, start+src_dur]만 읽어(-ss+입력측 -t) 유출 차단.
            #   입력 제한이 핵심(P1) — 상한 배율이 out_dur/src_dur보다 작으면 setpts가 다음
            #   구간까지 끌어와 유출된다(다색 소스 실측). 잘라두면 이 구간만 play_out으로 늘어난다.
            sub = work / f"beat_{idx}_{j}.mp4"
            _run_ffmpeg([
                "ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{c['src_dur']:.3f}",
                "-i", str(src),
                "-vf", vf_full, "-r", "30", "-an", "-t", f"{play_out:.3f}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(sub),
            ])
            # 그래도 비면(소스 손상/범위밖) 이 클립만 버린다 — 하나가 미리보기 전체를 죽이지 않게.
            if not sub.exists() or _probe_duration(sub) <= 0.05:
                continue
            # 2단계 — 정지프레임(P1 후속, 2026-07-19): 마지막 프레임을 freeze초 홀드하되
            #   전체에 켄번즈를 얹어 '죽은 정지'가 아니라 움직이는 홀드로 만든다. tpad→zoompan
            #   순서면 한 체인에서 정상 동작(_extend_with_frozen_motion 주석 참조).
            if freeze > 1e-3:
                frozen = work / f"beat_{idx}_{j}f.mp4"
                _extend_with_frozen_motion(sub, play_out, freeze, frozen)
                sub_paths.append(frozen)
            else:
                sub_paths.append(sub)
        if not sub_paths:
            # 이 비트는 쓸 클립이 하나도 없다(모든 소스 손상/범위밖). 비트를 건너뛴다 —
            # 미리보기가 통째로 죽는 것보다 이 비트만 빠지는 게 낫다.
            continue
        # 비트의 클립들(동일 규격)을 concat → 비트 무음 영상(길이 ≈ tts_dur)
        beat_video = work / f"beat_{idx}_v.mp4"
        cat = work / f"beat_{idx}_list.txt"
        cat.write_text("".join(f"file '{p.as_posix()}'\n" for p in sub_paths), encoding="utf-8")
        _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(cat),
                     "-c", "copy", str(beat_video)])
        # 컷어웨이(장면라이브러리 페이즈2-B): 라이브러리 자산을 비트 영상 위에 풀프레임
        # 오버레이. 창=[0, min(자산길이, tts_dur)]. 비트 길이·TTS 오디오 불변 → 자막 t0 싱크
        # 불변. beat_video는 이미 규격(720x1280)·vf 적용 → 재-vf 없이 오버레이만 얹는다.
        clip = work / f"beat_{idx}.mp4"
        cutaway = (cutaway_paths or {}).get(idx)
        if cutaway:
            asset_dur = _probe_duration(cutaway)
            win = min(asset_dur, tts_dur)
            fc = (
                f"[1:v]scale=720:1280:force_original_aspect_ratio=increase,"
                f"crop=720:1280,setpts=PTS-STARTPTS[ov];"
                f"[0:v][ov]overlay=0:0:enable='between(t,0,{win:.3f})'[vout]"
            )
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-i", str(beat_video),   # 0: 내 다중클립 비트영상(이미 vf 적용)
                "-i", str(cutaway),      # 1: 컷어웨이 자산(오디오 버림 = b-roll)
                "-ss", f"{_head_trim:.3f}", "-i", str(tts),          # 2: 나레이션(앞트림 반영)
                "-filter_complex", fc, "-r", "30",
                "-map", "[vout]", "-map", "2:a:0",
                # 여운(runout): 마지막 비트만 대사 뒤 화면이 더 산다 — 오디오는 tts 길이에서
                # 자연 종료(무성 여운). 컷어웨이 창(win)은 tts_dur 기준 그대로(여운을 덮지 않음).
                "-t", f"{tts_dur + runout:.3f}",
                "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(clip),
            ])
        else:
            # 비트 나레이션(tts) 오디오를 얹고 길이를 tts_dur(+마지막 비트는 여운)로 맞춘다.
            _run_ffmpeg([
                "ffmpeg", "-y", "-i", str(beat_video),
                "-ss", f"{_head_trim:.3f}", "-i", str(tts),
                "-map", "0:v:0", "-map", "1:a:0", "-t", f"{tts_dur + runout:.3f}",
                "-c:v", "copy", "-c:a", "aac", str(clip),
            ])
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

    ⚠️ enable=은 "언제 그릴지"만 정할 뿐, 소스 스트림이 몇 초 지점을 재생 중인지는
    그대로 벽시계 시간(입력 스트림 자체의 PTS, t=0부터)을 따라간다. start>0인 레이어를
    enable만으로 게이팅하면, enable 창이 열릴 때 그 자산은 이미 자기 시간으로 그 이상
    지나 끝난 뒤라(짧은 전환/스티커는 정지 마지막 프레임) 재생이 아니라 정지 잔상만
    보인다(2026-07-15 Task9 실렌더 검증 결함1). setpts=PTS-STARTPTS+start/TB로 레이어
    자신의 PTS를 start초만큼 뒤로 밀어, enable 창이 열리는 순간 자산이 자기 0초부터
    재생되도록 맞춘다(ffmpeg 표준 "시간차 오버레이" 레시피).
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
        start = float(L.get("start") or 0)
        dur = L.get("dur")
        # start>0일 때만 setpts를 얹는다(start=0은 원점이라 이동이 no-op — 필터 문자열을
        # 불필요하게 늘리지 않고 기존 산출물과의 호환성도 유지).
        ts = f"setpts=PTS-STARTPTS+{start:.3f}/TB," if start > 0 else ""
        fc.append(f"[{idx}:v]{ts}{scale}format=rgba,colorchannelmixer=aa={aa:.2f}[{lab}]")
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


def _char_split(word, font, max_w):
    """공백 없는 한 단어를 폭 안에 들어가게 글자 단위로 쪼갠다(한글은 띄어쓰기가 적어
    단어 자체가 폭을 넘는 일이 흔하다)."""
    out, cur = [], ""
    for ch in word:
        if cur and font.getlength(cur + ch) > max_w:
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return out


def _wrap_to_width(line, font, max_w):
    """한 줄을 폭(max_w) 안에 들어가게 나눈다 — 단어(공백) 단위 그리디, 한 단어가 폭을
    넘으면 글자 단위로 쪼갠다. 빈 줄은 빈 줄로 보존. 미리보기의 자동 줄바꿈(CSS pre-wrap)과
    최종 렌더를 맞춰, 긴 헤드카피가 화면 밖으로 넘치지 않고 사용자가 본 그대로 나오게 한다."""
    if not line:
        return [""]
    out, cur = [], ""
    for w in line.split(" "):
        trial = w if not cur else cur + " " + w
        if not cur:
            if font.getlength(w) <= max_w:
                cur = w
            else:
                pieces = _char_split(w, font, max_w)
                out.extend(pieces[:-1])
                cur = pieces[-1]
        elif font.getlength(trial) <= max_w:
            cur = trial
        else:
            out.append(cur)
            if font.getlength(w) <= max_w:
                cur = w
            else:
                pieces = _char_split(w, font, max_w)
                out.extend(pieces[:-1])
                cur = pieces[-1]
    out.append(cur)
    return out


def _segmented_drawtext(text, base_style, work, key_prefix, x_pct, y_pct,
                          highlight_rules=None, default_color="0xFFFFFF", single_line=False):
    """헤드카피/자막 한 블록을 줄 단위로 나누고, highlight_rules에 매칭되는 단어만
    별도 색·배지로 세그먼트를 쪼개 나란히 이어붙인 drawtext 필터 리스트를 반환한다.
    규칙이 없거나 매칭 0건이면 줄마다 세그먼트 1개 = 기존 _fixed_drawtext/_caption_drawtexts와
    동일한 산출물(하위호환). 폭 측정은 Pillow로 실제 폰트파일 기준 수행.
    single_line=True(자막): 절대 줄바꿈하지 않고 **한 줄**로 두되, 폭을 넘으면 폰트를
    자동 축소해 한 줄에 맞춘다(사장님: 자막은 무조건 한 줄). 미리보기도 동일 비율로 축소."""
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
    max_w = 0.92 * _OUT_W
    if single_line:
        # 자막: 개행·연속공백을 한 칸으로 접어 한 줄로. 폭 초과 시 폰트 축소(줄바꿈 금지).
        one = " ".join(" ".join(lines).split())
        w = pil_font.getlength(one) if one else 0
        if w > max_w:
            size = max(8, int(size * max_w / w))
            try:
                pil_font = ImageFont.truetype(font_disk_path, size)
            except OSError:
                pass
        lines = [one]
    else:
        # 폭 초과 줄 자동 줄바꿈 — 미리보기(pre-wrap)와 맞춰 최종 영상도 화면 밖으로 안 넘게.
        lines = [seg for ln in lines for seg in _wrap_to_width(ln, pil_font, max_w)]
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
            if base_style.get("shadow"):
                # 은은한 드롭 그림자(레퍼런스 자막룩) — 두꺼운 테두리 대신 부드러운 가독성.
                sc = _hex_to_ff(base_style.get("shadow_color"), "0x000000")
                sd = max(1, int(base_style.get("shadow_d") or 3))
                seg_parts += [f"shadowcolor={sc}@0.55", f"shadowx={sd}", f"shadowy={sd}"]
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
    # 워터마크 등 spec.float가 켜지면 y를 시간표현식으로 만들어 위아래로 은은히 떠다니게 한다
    # (진폭=화면높이 0.6%, 주기 3s). ffmpeg 식평가는 sin/PI/t 지원(자막 슬라이드에서 검증됨).
    if spec.get("float"):
        y_expr = f"y=(h*{yf:.4f}-th/2+h*0.006*sin(2*PI*t/3))"
    else:
        y_expr = f"y=(h*{yf:.4f}-th/2)"
    parts = [
        f"drawtext=fontfile={fontref}:textfile=txt_{key}.txt",
        f"fontcolor={_hex_to_ff(spec.get('color'), default_color)}",
        f"fontsize={size}",
        f"x=(w*{xf:.4f}-tw/2)", y_expr,
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
    """비트별 전체 타임라인 [{beat_idx, t0, dur, narration, role, cap_durs}, ...].

    자막(_burn_captions)과 모션(motion_packs)이 **같은 경계**를 쓰도록 하는 단일 출처.
    여기서 중복 계산하면 전환이 자막과 어긋난다. tts 없는 비트는 건너뛴다(기존 동작).

    cap_durs: _synthesize_beats가 저장한 ASR 기반 구절 표시시간(list[float]|None).
    여기서 새 dict를 만들며 원본 beat를 복사하지 않으므로, 이 필드를 안 실어보내면
    저장위치(_synthesize_beats)≠읽기위치(_burn_captions)가 되어 seam이 끊긴다.
    """
    timeline = []
    t0 = 0.0
    for beat in edit_plan["beats"]:
        idx = beat["beat_idx"]
        tts = tts_paths.get(idx)
        if not tts:
            continue
        dur = _beat_effective_dur(beat, tts)
        timeline.append({
            "beat_idx": idx,
            "t0": t0,
            "dur": dur,
            "narration": beat.get("narration", ""),
            "role": beat.get("role", ""),
            "cap_durs": beat.get("cap_durs"),
            "cap_offset": beat.get("cap_offset", 0.0),
            "caption_lines": beat.get("caption_lines"),   # AI가 끊어준 자막 호흡 줄(있으면)
            "sfx": beat.get("sfx"),                        # 효과음 매칭(있으면) — position 읽기용
            "head_trim": beat.get("head_trim", 0.0),
        })
        t0 += dur
    return timeline


def _burn_captions(in_video, edit_plan, tts_paths, out_path, work, headcopy=None, caption_style=None, deco=None, sfx_paths=None):
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
        # 마지막 비트만 0.5초 여운(영상 끝에서 자막이 툭 사라지지 않게). 중간 비트는 tail=0 —
        # 여운을 주면 그 자막이 다음 비트로 0.5초 넘어가 다음 자막과 겹쳐 뭉갠다(전환 겹침, 실측).
        _tail = 0.5 if b is timeline[-1] else 0.0
        filters.extend(_caption_drawtexts(b["narration"], b["dur"], work, b["beat_idx"],
                                          b["t0"], caption_style, real_durs=b.get("cap_durs"),
                                          cap_offset=b.get("cap_offset", 0.0), tail=_tail,
                                          cap_lines=b.get("caption_lines")))
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
                   "x": wm.get("x", 50), "y": wm.get("y", 88),
                   "alpha": wm.get("alpha", 0.6),
                   "float": wm.get("float", True),
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
    # 효과음(sfx): 비트별 position → 절대 오프셋(초)을 캡션과 **같은 함수**로 계산한다
    # (별도 계산 금지 — 저장위치=읽기위치). first=0.0 / last=마지막 세그먼트 직전까지의 합
    # (세그먼트 1개면 0.0). 절대시각 = 비트 t0 + 오프셋. sfx_events=[(경로, 절대초), ...].
    sfx_paths = sfx_paths or {}
    sfx_events = []
    for b in timeline:
        sfx = b.get("sfx")
        path = sfx_paths.get(b["beat_idx"])
        if not sfx or not path:
            continue
        segs = _caption_segments(b["narration"], preset=b.get("caption_lines"))
        seg_durs = _caption_durations(segs, b["dur"], real_durs=b.get("cap_durs"))
        offset = 0.0 if sfx.get("position") == "first" else sum(seg_durs[:-1])
        sfx_events.append((path, b["t0"] + offset))
    has_sfx = bool(sfx_events)
    if not has_bgm and not has_overlay and not has_motion and not has_sfx:
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
    # 오디오 믹스: 나레이션(항상) + BGM(있으면) + 효과음(있으면)을 한 번에 amix.
    # duration=first → 첫 입력(나레이션) 길이로 잘린다. 효과음이 비트보다 길면 다음
    # 비트 위로 흘러넘치되 영상 끝에서만 잘린다(v1 알려진 한계, 스펙 §4.3).
    amap = None
    mix_labels = ["0:a"]                              # 나레이션(항상 있음, 첫 입력)
    if has_bgm:                                       # 배경음악(나레이션 위 낮은 볼륨)
        inputs += ["-i", bgm_path]
        vol = max(0.0, min(1.0, (bgm.get("volume", 15)) / 100.0))
        fc.append(f"[{idx}:a]aloop=loop=-1:size=2000000000,volume={vol:.3f}[bg]")
        mix_labels.append("bg")
        idx += 1
    if has_sfx:                                       # 효과음(비트별 오프셋에 adelay)
        sfx_vol = max(0.0, min(1.0, (deco.get("sfx_volume", 60)) / 100.0))
        for i, (sfx_path, offset_sec) in enumerate(sfx_events):
            inputs += ["-i", sfx_path]
            ms = max(0, round(offset_sec * 1000))
            fc.append(f"[{idx}:a]adelay={ms}:all=1,volume={sfx_vol:.3f}[sfx{i}]")
            mix_labels.append(f"sfx{i}")
            idx += 1
    if len(mix_labels) > 1:
        ins = "".join(f"[{lb}]" for lb in mix_labels)
        fc.append(f"{ins}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2[a]")
        amap = "[a]"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{vcur}]"]
    cmd += (["-map", amap, "-c:a", "aac"] if amap else ["-map", "0:a", "-c:a", "copy"])
    cmd += ["-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)]
    _run_ffmpeg(cmd, cwd=str(work))
    return str(out_path)


def assemble(edit_plan, tts_paths, source_video_paths, out_path, clean_fn=None, headcopy=None, caption_style=None, deco=None, cutaway_paths=None, sfx_paths=None, burn_captions=True):
    """EDL → 최종 mp4. 1)믹스(자막X) 2)clean_fn(있으면 자막제거) 3)우리 자막.
    clean_fn(mix_raw_path)->clean_path 를 주면 그 사이에 VMake 자막제거가 끼워진다
    (없으면 생략). 자막제거는 우리 자막을 굽기 전 깨끗한 믹스에 돌려야 우리 자막이
    함께 지워지지 않는다.
    sfx_paths: {beat_idx: media_path} — beat["sfx"]가 붙은 비트의 효과음 경로(컷어웨이와
    같은 seam). _burn_captions가 position→오프셋을 캡션과 같은 함수로 계산해 amix에 섞는다."""
    work = Path(out_path).parent / f"asm_{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    mix_raw = _render_mix(edit_plan, tts_paths, source_video_paths, work, cutaway_paths=cutaway_paths)
    base_video = clean_fn(mix_raw) if clean_fn else mix_raw
    if not burn_captions:
        # '자막 없는 clean 배경'용(썸네일 배경 등, 2026-07-22) — 우리 나레이션 자막·꾸미기를
        # 굽는 _burn_captions 패스를 통째로 건너뛴다. base_video(믹스[+원본자막제거])를 그대로
        # 확정하므로 ①썸네일에 나레이션 자막이 안 박히고 ②캡션 인코딩 패스가 없어 더 빠르다.
        import shutil
        shutil.copyfile(base_video, out_path)
        return out_path
    return _burn_captions(base_video, edit_plan, tts_paths, out_path, work, headcopy, caption_style, deco, sfx_paths=sfx_paths)
