"""장면 라이브러리(재사용 짤 뱅크) — 구간컷·오디오추출·썸네일·Gemini 자동태깅.

미디어 유틸(make_clip, extract_audio 등)은 순수 함수 또는 subprocess만 사용한다(DB 없음).
autotag는 Gemini API를 호출해 다축 태그 초안을 생성한다. frame_extract.py와 같은 골격:
ffmpeg는 subprocess로, 치명적 실패는 RuntimeError, 없어도 되는 것은 조용한 None.
"""
import json
import subprocess
from pathlib import Path

from google.genai import types

from . import edit_plan, frame_extract

# 페이즈2 concat이 -c copy(video_assemble.py:346)라 자산 클립도 비트 클립과
# **같은 규격**이어야 붙는다. video_assemble._OUT_W/_OUT_H와 같은 값.
_OUT_W, _OUT_H = 720, 1280
_SPEC_VF = (f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,"
            f"crop={_OUT_W}:{_OUT_H}")


def probe_duration(path):
    """미디어 길이(초). 실패하면 0.0 — 길이는 표시용이라 파이프라인을 끊지 않는다.

    ffprobe가 아예 없으면 subprocess.run은 returncode가 아니라 FileNotFoundError를
    던지므로 OSError도 삼킨다(ffprobe 없는 환경에서도 저장은 되어야 한다)."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, check=False)
    except OSError:
        return 0.0
    if r.returncode != 0:
        return 0.0
    try:
        return float((r.stdout or b"").decode().strip())
    except ValueError:
        return 0.0


def make_clip(src_path, start, end, out_path):
    """src_path의 [start,end] 구간을 잘라 규격(720x1280/30fps/libx264/aac)으로 통일.

    페이즈2에서 이 클립이 비트 클립들과 concat -c copy로 붙으므로 규격이
    어긋나면 렌더가 깨진다. 구간이 비었거나 뒤집혔으면 ValueError, ffmpeg
    실패면 RuntimeError."""
    dur = float(end) - float(start)
    if dur <= 0:
        raise ValueError(f"scene_assets: 구간이 잘못됨(start={start}, end={end})")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{float(start):.3f}", "-i", str(src_path),
        "-t", f"{dur:.3f}",
        "-vf", _SPEC_VF, "-r", "30",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 구간컷 실패: {r.stderr}")
    return out_path


def extract_audio(clip_path, out_path):
    """클립에서 오디오만 뽑아 mp3로(효과음 자산 소스). ffmpeg 실패면 RuntimeError."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(clip_path), "-vn",
           "-c:a", "libmp3lame", "-q:a", "2", str(out_path)]
    r = subprocess.run(cmd, capture_output=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 오디오 추출 실패: {r.stderr}")
    return out_path


def make_poster(media_path, out_path):
    """첫 프레임 썸네일. 실패해도 None(썸네일은 없어도 목록이 뜬다).
    프레임 1장 추출은 frame_extract.extract_frame_at이 이미 하는 일이라 위임."""
    out_path = Path(out_path)
    return frame_extract.extract_frame_at(media_path, out_path.parent, 0,
                                          filename=out_path.name)


# 스펙 §4 통제어휘 — 모델이 자유롭게 지어내면 매칭 키가 흩어진다.
_ROLES = ("훅", "반전", "CTA", "비법공개", "반응", "전환", "본문")

_AUTOTAG_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_desc": {"type": "string"},
        "role": {"type": "string"},
        "subject": {"type": "string"},
        "tone": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    # required를 빼면 Gemini가 필드를 생략한다(video_analysis.py:26).
    "required": ["scene_desc", "role", "subject", "tone", "keywords"],
}

_AUTOTAG_PROMPT = """너는 쇼츠 편집자다. 아래 이미지들은 저장하려는 **장면 클립의 대표 프레임**이다.
이 장면을 나중에 다른 영상에 재사용할 수 있도록 **다축 태그**를 만들어라.

맥락: 카테고리={category} / 원본 캡션={caption} / 원본 대본={script}

규칙:
- scene_desc: 화면에 실제로 보이는 것만 한 문장으로. 추측·해석 금지.
  (나쁜 예: "비법을 공개하는 장면" / 좋은 예: "흰 가루를 숟가락으로 떠 그릇에 넣음")
- subject: 소재·대상을 **구체적으로**. "한 스푼" 같은 모호한 말 금지 —
  가루인지 액체인지 세제인지 밥인지 구분되게 써라. (예: "가루(밀가루·설탕류)")
  이게 틀리면 나중에 세제 짤이 요리 영상에 들어간다.
- role: 반드시 다음 중 하나만: {roles}
- tone: 이 장면의 분위기(예: "비밀스러운·궁금", "놀라는·과장")
- keywords: 매칭 보조 키워드 3~6개(화면에 보이는 사물·동작·구도)
"""


def autotag(frame_paths, context):
    """대표 프레임 + 맥락 → 다축 태그 초안 dict. 사람이 확인·수정할 **초안**이다.

    무키·실패·프레임 없음 어떤 경우든 예외 없이 {scene_desc, role, subject, tone,
    keywords} 형태의 빈 값을 돌려준다(호출부가 특수처리 안 하게 — edit_plan의
    '형태가 온전한 빈 값' 폴백 관례)."""
    empty = {"scene_desc": "", "role": "", "subject": "", "tone": "", "keywords": []}
    if not frame_paths:
        return empty
    parts = []
    for p in frame_paths:
        try:
            with open(p, "rb") as fh:
                parts.append(types.Part.from_bytes(data=fh.read(), mime_type="image/jpeg"))
        except OSError:
            continue
    if not parts:
        return empty
    parts.append(_AUTOTAG_PROMPT.format(
        category=context.get("category") or "(모름)",
        caption=(context.get("caption") or "(없음)")[:300],
        script=(context.get("script") or "(없음)")[:1000],
        roles="|".join(_ROLES),
    ))
    # _vault_call은 contents=prompt로 그대로 넘기므로 파츠 리스트가 그대로 먹는다.
    # 키풀은 캐스케이드(general→ingest→embed→briefing) — 전용키 소진 회피.
    raw = edit_plan._vault_call(parts, _AUTOTAG_SCHEMA)
    if not raw or not isinstance(raw, dict):
        # _vault_call이 dict가 아닌 값(list/str/int 등)을 반환하면 raw.get() 호출에서
        # AttributeError 발생 → 후속 Task4의 /api/scene/save/prepare 라우트가 500 에러.
        # 형태가 온전한 빈 값을 반드시 보장해야 함(호출부 예외처리 없음)
        return empty
    kw = raw.get("keywords")
    if isinstance(kw, str):
        kw = [k.strip() for k in kw.split(",") if k.strip()]
    role = (raw.get("role") or "").strip()
    return {
        "scene_desc": (raw.get("scene_desc") or "").strip(),
        "role": role if role in _ROLES else "",
        "subject": (raw.get("subject") or "").strip(),
        "tone": (raw.get("tone") or "").strip(),
        "keywords": [str(k).strip() for k in (kw or []) if str(k).strip()],
    }
