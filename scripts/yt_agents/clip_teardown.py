"""YouTube 레퍼런스 해체와 주제 확정 카드 생성.

영상 원문을 베끼는 도구가 아니라, 근거가 붙은 성공 장치를 추출하고
우리 영상에서 채택·변형·버릴 항목을 결정하기 위한 분석기다.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone

import gemini_client


_VIDEO_ID = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:[^#]*&)?v=|shorts/|live/|embed/))"
    r"([A-Za-z0-9_-]{11})"
)


def parse_video_id(value: str) -> str:
    value = (value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    match = _VIDEO_ID.search(value)
    return match.group(1) if match else ""


def _json_object(text: str) -> dict:
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        value = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", clean)
        if not match:
            raise RuntimeError("AI 분석 결과에서 JSON을 찾지 못했습니다")
        value = json.loads(match.group())
    if not isinstance(value, dict):
        raise RuntimeError("AI 분석 결과가 객체 형식이 아닙니다")
    return value


def _metadata(video_id: str) -> dict:
    """yt-dlp 메타데이터. 실패해도 영상 분석 자체는 계속한다."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        sys.executable, "-m", "yt_dlp", "--skip-download",
        "--dump-single-json", "--no-warnings", url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60,
        )
        if result.returncode != 0:
            return {}
        raw = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return {}
    return {
        "title": raw.get("title") or "",
        "channel": raw.get("channel") or raw.get("uploader") or "",
        "duration": int(raw.get("duration") or 0),
        "view_count": int(raw.get("view_count") or 0),
        "like_count": int(raw.get("like_count") or 0),
        "comment_count": int(raw.get("comment_count") or 0),
        "upload_date": raw.get("upload_date") or "",
        "thumbnail": raw.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def _analysis_prompt(title: str, channel: str, context: dict) -> str:
    return f"""당신은 유튜브 레퍼런스 영상 분석가다. 영상을 실제로 보고 아래 JSON만 반환하라.

[레퍼런스]
- 제목: {title}
- 채널: {channel}

원문을 베끼기 위한 요약이 아니다. 성과 장치가 무엇인지 판단할 근거를 추출한다.
특정 제작자의 상황에 맞춘 적용 판단은 하지 않는다. 영상에서 확인할 수 없는 값은
추측하지 말고 빈 문자열이나 빈 배열로 둔다.
핵심 판단에는 반드시 HH:MM:SS 타임스탬프를 붙인다.

{{
  "click_device": {{
    "title_formula": "대상+문제/욕망+구체성+긴장의 공식",
    "thumbnail_promise": "썸네일이 약속하는 한 가지",
    "information_gap": "제목과 썸네일 사이의 궁금증"
  }},
  "hook": {{
    "type": "경고|기회|비밀|반전|공감|결과선공개 중 하나",
    "first_line": "실제 첫 핵심 문장",
    "keep_watching_reason": "30초 안에 계속 볼 이유",
    "proof": "30초 안에 제시한 증거",
    "drop_risk": "군더더기 또는 이탈 위험",
    "evidence": [{{"at":"00:00:00","quote":"짧은 근거 문구"}}]
  }},
  "story_beats": [
    {{
      "start":"00:00:00", "end":"00:00:30",
      "role":"문제|약속|증거|방법|반론|전환|CTA",
      "claim":"핵심 주장", "proof":"증거", "visual":"화면 방식",
      "bridge":"다음 구간 연결"
    }}
  ],
  "viewer_needs": ["영상이 해결하는 시청자 욕구"],
  "visual_grammar": {{
    "delivery":"말의 속도와 문장 길이",
    "screen_mix":"얼굴·화면녹화·도표·B-roll 비중",
    "pattern_interrupt":"화면 변화 간격과 방식",
    "proof_display":"숫자·사례·비교를 보여주는 방식",
    "cta":"CTA 위치와 대가"
  }},
  "strengths": ["성과에 기여한 것으로 보이는 장치"],
  "risks": ["과장·낡은 정보·근거 부족·모방 위험"]
}}"""


def teardown(video_id: str, title: str = "", channel: str = "",
             stats: dict | None = None, context: dict | None = None) -> dict:
    video_id = parse_video_id(video_id)
    if not video_id:
        raise ValueError("올바른 YouTube 영상 ID가 아닙니다")
    context = context or {}
    supplied = stats or {}
    meta = _metadata(video_id)
    title = title or meta.get("title") or "제목 확인 불가"
    channel = channel or meta.get("channel") or "채널 확인 불가"
    url = f"https://www.youtube.com/watch?v={video_id}"
    analysis = _json_object(
        gemini_client.call_video(url, _analysis_prompt(title, channel, context))
    )
    metrics = {
        "view_count": int(supplied.get("view_count") or meta.get("view_count") or 0),
        "view_pct_above_avg": supplied.get("view_pct_above_avg"),
        "contribution_grade": supplied.get("contribution_grade") or "",
        "like_count": int(meta.get("like_count") or 0),
        "comment_count": int(meta.get("comment_count") or 0),
        "duration": int(meta.get("duration") or 0),
        "upload_date": meta.get("upload_date") or "",
    }
    return {
        "video_id": video_id,
        "url": url,
        "title": title,
        "channel": channel,
        "thumbnail": supplied.get("thumbnail") or meta.get("thumbnail")
        or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "metrics": metrics,
        "click_device": analysis.get("click_device") or {},
        "hook": analysis.get("hook") or {},
        "story_beats": analysis.get("story_beats") or [],
        "viewer_needs": analysis.get("viewer_needs") or [],
        "visual_grammar": analysis.get("visual_grammar") or {},
        "strengths": analysis.get("strengths") or [],
        "risks": analysis.get("risks") or [],
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _synthesis_prompt(cards: list[dict], context: dict) -> str:
    compact = json.dumps(cards, ensure_ascii=False)[:50000]
    return f"""당신은 Astra가 설계한 유튜브 편집장 규칙을 실행한다.
여러 레퍼런스의 요약을 다시 요약하지 말고, 우리 영상에 무엇을 어디에 쓸지 결정하라.

[우리 조건]
{json.dumps(context, ensure_ascii=False)}

[영상 분석 카드]
{compact}

아래 JSON만 반환하라. 원문 문장 복사는 금지하며 감정 순서와 정보 구조만 활용한다.
근거가 약하거나 우리 채널과 맞지 않으면 버린다.

{{
  "topic":"확정할 영상 주제 한 문장",
  "audience":"핵심 시청자",
  "promise":"시청 후 얻게 되는 변화 한 문장",
  "why_now":"지금 올려야 하는 이유",
  "differentiation":"경쟁 영상과 다른 한 문장",
  "score":{{"timeliness":0,"demand":0,"channel_fit":0,"difference":0,"evidence":0,"feasibility":0,"total":0}},
  "decisions":[
    {{"kind":"채택|변형|버림","device":"분석된 장치","reason":"판단 이유","use_at":"대본 또는 장면의 사용 위치"}}
  ],
  "titles":["제목 후보 5개"],
  "thumbnails":["썸네일 문구 3개"],
  "hooks":["첫 30초 훅 3개"],
  "outline":[{{"role":"장면 역할","content":"담을 내용","reference_device":"사용할 장치"}}],
  "research_tasks":["다음 단계에서 확인할 숫자·사례·반론"],
  "needed_assets":["필요한 화면·자료·녹음"],
  "guardrails":["사용하면 안 되는 주장·표현"]
}}"""


def synthesize(cards: list[dict], context: dict | None = None) -> dict:
    if not cards:
        raise ValueError("분석 카드가 필요합니다")
    context = context or {}
    return _json_object(gemini_client.call(_synthesis_prompt(cards, context), temperature=0.2))


def mix(cards: list[dict], category: str = "") -> str:
    """기존 레퍼런스 창고 API 하위호환."""
    decision = synthesize(cards, {"seed_topic": category})
    return json.dumps(decision, ensure_ascii=False, indent=2)
