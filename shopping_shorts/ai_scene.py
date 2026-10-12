# -*- coding: utf-8 -*-
"""AI 장면 생성(Veo) — 없는 장면을 **소스 프레임 베이스**로 4·6·8초 만든다 (2026-09-23).

사장님 전제: 장면을 처음부터 새로 만들지 않는다. 영상 소스에서 베이스(프레임)를 가져와
형태는 유지하고 동작만 자연스럽게. 훅은 임팩트 있게 가능.

스파이크 실측(2026-09-22 20:10~21:00, Veo 3.1 Lite, 7편):
  · 프롬프트는 "첫 프레임 묘사 + 초 단위 사건 순서 + 재질·조명 + 금지 목록" 형태여야 결과가 지시대로 나온다.
    결과 상태만 적으면(예: "세탁 후 뽀송") 베이스에서 안 움직이거나 끊긴다.
  · 베이스 프레임이 곧 결과다 — 아기가 있는 프레임을 주면 세탁기 안에 아기가 같이 들어간다.
    제품만 나와야 하는 장면은 **제품만 있는 컷**(scene_desc에 사람·아기 없음)을 베이스로 고른다.
  · 베이스에 원본 자막이 있으면 첫 1초에 글자가 남는다 → 청소본(clean_base) 프레임을 우선 쓴다.
  · 새 물건(세탁기)이 들어오면 가짜 로고·글자가 생긴다 → 금지 목록에 넣는다.

흐름: 화면 버튼 → POST /api/produce/mix/{job}/ai_scene → job_queue "ai_scene" → run_ai_scene
      → 베이스 프레임 → 프롬프트(Gemini가 대사→동작 3줄) → Veo → 장면 자산 저장 → beat["cutaway"] 붙임.
★판정은 한 곳: 베이스 프레임 자리 = pick_base_material/base_frame_path, 프롬프트 = build_prompt.
★파생물을 원본 키에 안 쓴다: 클립은 scene_assets에, 상태는 beat["ai_scene"]에만.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MODEL = "veo-3.1-lite-generate-001"
STYLES = ("natural", "impact")
PERSON_WORDS = ("아기", "아이", "사람", "여성", "남성", "얼굴", "손", "엄마", "아빠", "모델", "인물", "여자", "남자")
FORBID = ("no text, no subtitles, no captions, no logos, no brand names, no watermark, "
          "no baby, no human face, no new people, no second copy of the product, "
          "no change of the product's shape, color or design, no cartoon style, no cut, no dissolve, "
          "no speed lines, no comic effect lines, no drawn lines or strokes, no motion streaks, no overlays")


def pick_seconds(dur):
    """비트 실길이 → Veo 길이(4|6|8). ≤4→4, ≤6→6, 그 외 8."""
    try:
        d = float(dur or 0)
    except (TypeError, ValueError):
        d = 0.0
    return 4 if d <= 4.0 else (6 if d <= 6.0 else 8)


def _segments(extract):
    out = []
    for vid, v in (extract or {}).items():
        for s in (v or {}).get("segments") or []:
            if s.get("start") is None or s.get("end") is None:
                continue
            out.append({"video_id": vid, **s})
    return out


def product_only_segments(extract, product_words=()):
    """사람·아기·손 없이 제품만 보이는 세그먼트(scene_desc 기준). 제품어가 있으면 그것도 요구."""
    from shopping_shorts.edit_plan import auto_sources
    # 베이스 프레임도 자동으로 고르는 화면이다 — 씨앗 영상에서는 안 뜬다(관제 138, 판단은 edit_plan.auto_sources)
    _ok = {vid for vid, v in (extract or {}).items() if auto_sources([v])}
    got = []
    for s in _segments(extract):
        if s.get("video_id") not in _ok:
            continue
        d = str(s.get("scene_desc") or "")
        if not d or any(w in d for w in PERSON_WORDS):
            continue
        if product_words and not any(w in d for w in product_words):
            continue
        got.append(s)
    return got


def pick_base_material(beat, extract, *, product_only=True, product_words=()):
    """베이스 프레임을 뜰 (video_id, 초). product_only면 제품만 나오는 컷의 가운데를 우선,
    없으면 비트 primary 시작+0.2초."""
    if product_only:
        cands = product_only_segments(extract, product_words)
        if cands:
            s = max(cands, key=lambda x: float(x["end"]) - float(x["start"]))
            return s["video_id"], round((float(s["start"]) + float(s["end"])) / 2.0, 3)
    prim = (beat or {}).get("primary") or {}
    over = (beat or {}).get("scene_override") or []
    m = over[0] if over else prim
    try:
        return m.get("video_id"), round(float(m.get("start") or 0.0) + 0.2, 3)
    except (TypeError, ValueError):
        return m.get("video_id"), 0.2


def extract_frame(video_path, t, out_png):
    """9:16 720x1280 프레임 1장."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{float(t):.3f}", "-i", str(video_path), "-frames:v", "1",
                    "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280", str(out_png)],
                   check=True, stdin=subprocess.DEVNULL)
    return str(out_png)


def base_frame_path(job, work, beat, extract, *, product_only=True, product_words=(), resolve_sources=None):
    """베이스 프레임 PNG 경로. 청소본(clean_base)이 있고 그 비트가 청소본에 있으면 청소본에서(글자 없음),
    아니면 원본 소스의 제품만 컷/primary에서."""
    from shopping_shorts import clean_base as cb
    work = Path(work)
    out = work / f"ai_scene_base_{int(beat.get('beat_idx', 0))}.png"
    base = cb.load_base(work)
    if base is not None and not product_only:
        t = cb.time_in_clean(base, beat.get("beat_idx"), 0.5)
        if t is not None:
            return extract_frame(base["path"], t, out)
    vid, t = pick_base_material(beat, extract, product_only=product_only, product_words=product_words)
    # ★제품만 컷이 청소본 어딘가에 있으면 청소본에서 뜬다 — 원본은 자막·워터마크가 남아 Veo가 가짜 글자·로고를
    #   본뜬다(2026-09-23 실측 'beeitem' 로고·헛글자). 조각 판정은 clean_base.piece_map 하나(0순위-B).
    if base is not None and product_only:
        for seg in product_only_segments(extract, product_words):
            if seg["video_id"] != vid or not (float(seg["start"]) <= t <= float(seg["end"])):
                continue
            pieces = cb.piece_map(base, {"video_id": vid, "start": seg["start"], "end": seg["end"]})
            if pieces:
                mid = pieces[0]["start"] + (pieces[0]["end"] - pieces[0]["start"]) / 2.0
                return extract_frame(base["path"], mid, out)
            break
    srcs = resolve_sources(job, work) if resolve_sources else {}
    src = srcs.get(vid)
    if not src:
        # 제품만 컷을 못 찾았거나 소스가 없다 → 청소본 → primary 순으로 물러선다
        if base is not None:
            t2 = cb.time_in_clean(base, beat.get("beat_idx"), 0.5)
            if t2 is not None:
                return extract_frame(base["path"], t2, out)
        vid, t = pick_base_material(beat, extract, product_only=False)
        src = srcs.get(vid)
        if not src:
            raise RuntimeError("베이스 프레임을 뜰 소스 영상이 없습니다")
    return extract_frame(src, t, out)


_MOTION_SCHEMA = {
    "type": "object",
    "properties": {
        "subject_desc_en": {"type": "string"},
        "motion_steps_en": {"type": "array", "items": {"type": "string"}},
        "forbid_extra": {"type": "array", "items": {"type": "string"}},
        # 관제 117 — 구체 항목(환경·카메라·효과)과 한글 번역. 화면에 영어·한글을 나란히 보여 준다.
        "environment_en": {"type": "string"},
        "camera_en": {"type": "string"},
        "effects_en": {"type": "string"},
        "subject_desc_ko": {"type": "string"},
        "environment_ko": {"type": "string"},
        "camera_ko": {"type": "string"},
        "effects_ko": {"type": "string"},
        "motion_steps_ko": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["subject_desc_en", "motion_steps_en"],
}
_DETAIL_KEYS = ("environment_en", "camera_en", "effects_en",
                "subject_desc_ko", "environment_ko", "camera_ko", "effects_ko")


def motion_request(narration, subject_hint="", style="natural", call=None, frame_path=None, flow=None, direction=""):
    """대사 한 줄 + **베이스 프레임 이미지** → (영어) 피사체·환경·카메라·초 단위 동작 3단계·효과 + 한글 번역. Gemini JSON 호출; 실패하면 기본값.

    ★이미지를 반드시 같이 준다(2026-09-23 실측): 텍스트만 주면 "뒤집으면 핑크가 되는 리버시블 인형"처럼
      제품에 없는 기능을 지어내고 Veo가 그대로 만든다(훅 실측 — 노란 인형이 핑크로 뒤집힘).
    ★관제 117(2026-10-04 사장님 "사물·환경·카메라 각도·효과 등 아주 구체적으로 / 대충 하면 장면 잘 안 나와"):
      flow = 대본 흐름(앞 줄·이 줄·뒤 줄), direction = 사장님이 한글로 적은 방향. 구체 항목은 **보이는 것만** 적게 한다."""
    if call is None:
        from shopping_shorts.edit_plan import _vault_call, _vault_call_image
        call = (lambda p, s: _vault_call_image(p, s, frame_path)) if frame_path else _vault_call
    _flow = flow or {}
    _dir = str(direction or "").strip()[:600]
    prompt = (
        "You write shot directions for a 4-8 second product video clip that starts from the attached still frame (FRAME 0).\n"
        "Describe ONLY what is visible in the frame. Do not invent product features, colors, parts or mechanisms that are not visible.\n"
        f"Product / subject hint (Korean): {subject_hint or '(unknown)'}\n"
        f"Narration line (Korean) this shot must match: {narration}\n"
        + ((f"Script flow (Korean). Line before: {_flow.get('prev') or '(none - this is the opening)'} | "
            f"THIS line: {_flow.get('this') or narration} | Line after: {_flow.get('next') or '(none - this is the ending)'}. "
            "The motion must show what THIS line says, at this point of the story.\n") if flow else "")
        + ((f"DIRECTOR'S NOTE (Korean, written by the editor). Follow it as far as it is physically possible with what is "
            f"visible in the frame; it overrides the default style: {_dir}\n") if _dir else "")
        + f"Style: {'energetic hook (quick dolly-in toward the subject, one bold physical action; still real handheld phone footage - no drawn, animated or graphic effects)' if style == 'impact' else 'natural subtle motion (breathing, gentle hand, slow push-in)'}\n"
        + ("HOOK ORDER: the FIRST of the three sentences must already contain the single boldest moment. "
           "Do not build up to it and do not save it for the end; the viewer only sees the opening.\n"
           if style == "impact" else "")
        + "BE CONCRETE. Vague directions give bad video. Name the exact objects, where they sit in the frame, what they are made of, "
        "which direction things move, how far and how fast. No generic phrases like 'the product moves nicely'.\n"
        + "Return JSON: subject_desc_en (2-3 sentences: every visible object exactly as it appears - shape, color, material, size "
        "relation, where it sits in the frame, how it is held or placed), "
        "environment_en (1-2 sentences: the visible background, the surface it rests on, the kind of place, light direction and "
        "quality, time-of-day feel - only what the frame shows), "
        "camera_en (1-2 sentences: shot size (macro / close-up / medium), camera height and angle (eye-level, high angle, top-down...), "
        "lens feel and depth of field, and the exact camera move with direction and speed), "
        "motion_steps_en (exactly 3 short sentences: what happens in the first third, middle third, last third; "
        "only movements that could physically happen to what is visible in this frame — camera moves, gentle hand contact, "
        "soft parts swaying, light changes; the product must keep its exact shape, color, material and design; it must not "
        "transform, flip inside out, change color or reveal hidden parts; NO person, face or body may appear or enter - "
        "prefer camera moves and self-motion of soft parts; if a hand is needed, it is only a hand already visible at the frame edge, "
        "never an arm, body or face; no text), "
        "effects_en (1 sentence: real in-camera effects only - focus pull, light glint or reflection change, shadow movement, "
        "natural motion blur; never drawn or graphic effects), "
        "forbid_extra (0-3 short English phrases to forbid, e.g. 'no washing machine'), "
        "subject_desc_ko, environment_ko, camera_ko, effects_ko (faithful, complete Korean translations of the matching English fields), "
        "motion_steps_ko (exactly 3 Korean sentences, faithful translations of the 3 motion_steps_en in the same order)."
    )
    res = {}
    for attempt in range(3):          # 네트워크 끊김(RemoteProtocolError 실측 2026-09-23)은 한두 번 더 시도
        try:
            res = call(prompt, _MOTION_SCHEMA) or {}
        except Exception:      # noqa: BLE001 — 지시 생성 실패는 기본 동작으로
            res = {}
        if res.get("motion_steps_en"):
            break
        time.sleep(2)
    steps = [str(x).strip() for x in (res.get("motion_steps_en") or []) if str(x).strip()][:3]
    steps_ko = [str(x).strip() for x in (res.get("motion_steps_ko") or []) if str(x).strip()][:3]
    if len(steps) < 3:
        steps_ko = []           # 영어가 기본 문장으로 바뀌면 모델의 한글 번역은 못 쓴다(짝이 안 맞는다)
        steps = (["The camera holds on the subject with a slight natural handheld sway.",
                  "A slow gentle push-in toward the subject; soft parts move subtly.",
                  "The push-in continues; the subject stays centered and unchanged."]
                 if style != "impact" else
                 # ★훅은 보이는 구간이 짧다(실측 2.42초) — 큰 순간을 첫 문장에 둔다(2026-09-24).
                 ["A fast push-in slams toward the subject and the boldest moment lands at once.",
                  "The motion carries through and starts to settle in the centre of the frame.",
                  "The camera holds steady; the subject is centred, sharp and unchanged."])
    out = {"subject_desc_en": str(res.get("subject_desc_en") or subject_hint or "the product in the input image").strip(),
           "motion_steps_en": steps,
           "forbid_extra": [str(x).strip() for x in (res.get("forbid_extra") or []) if str(x).strip()][:3]}
    # 구체 항목·한글 번역은 **모델이 준 것만** 싣는다(없으면 키도 없다 — 프롬프트는 종전 모양 그대로)
    for k in _DETAIL_KEYS:
        v = str(res.get(k) or "").strip()
        if v:
            out[k] = v
    if len(steps_ko) == 3:
        out["motion_steps_ko"] = steps_ko
    return out


def _visible_window(sec, visible):
    """(보이는 길이, 1/3 지점, 2/3 지점) — build_prompt·build_prompt_ko 가 같은 숫자를 쓴다."""
    sec = int(sec)
    try:
        vis = float(visible) if visible else float(sec)
    except (TypeError, ValueError):
        vis = float(sec)
    vis = max(1.2, min(vis, float(sec)))
    return vis, round(vis / 3.0, 1), round(vis * 2 / 3.0, 1)


def build_prompt_ko(motion, sec, style="natural", visible=None):
    """영어 프롬프트(build_prompt)의 **한글 번역본** — 같은 항목·같은 순서(사물·환경·시간표·카메라·효과·금지). 만들기 전에
    화면에 같이 보여 준다(관제 117). Veo 에는 영어만 간다. 한글 번역이 없는 항목은 영어 원문을 그대로 보여 준다(지어내지 않는다)."""
    vis, a, b = _visible_window(sec, visible)
    en = motion.get("motion_steps_en") or ["", "", ""]
    ko = motion.get("motion_steps_ko") or en
    g = lambda k_ko, k_en: (motion.get(k_ko) or motion.get(k_en) or "").strip()
    lines = [f"[출발 화면 = 첫 프레임] {g('subject_desc_ko', 'subject_desc_en')} — 이 모습(모양·색·재질·디자인) 그대로 유지합니다."]
    if g("environment_ko", "environment_en"):
        lines.append(f"[환경] {g('environment_ko', 'environment_en')}")
    lines.append(f"[한 번에 이어 찍은 한 컷 · 컷 전환 없음 · {int(sec)}초]"
                 + (f" 화면에는 앞 {vis:.1f}초만 쓰입니다 — 중요한 건 그 안에 다 나옵니다." if vis < int(sec) - 0.05 else ""))
    if style == "impact":
        lines.append(f"[훅] 가장 강한 순간이 처음 {a}초 안에 나옵니다.")
    lines += [f"0.0~{a}초  {ko[0]}", f"{a}~{b}초  {ko[1]}", f"{b}~{vis:.1f}초  {ko[2]}"]
    if vis < int(sec) - 0.05:
        lines.append(f"{vis:.1f}~{int(sec)}.0초  그대로 머뭅니다(새 동작 없음).")
    cam = g("camera_ko", "camera_en")
    lines.append("[카메라·빛] " + (cam + " " if cam else "")
                 + ("손으로 든 휴대폰 영상, 세로 9:16, 출발 화면과 같은 자연광, " + ("빠르게 다가가기(실제 손 움직임만)." if style == "impact" else "살짝 흔들리는 손떨림.")))
    if g("effects_ko", "effects_en"):
        lines.append(f"[효과] {g('effects_ko', 'effects_en')}")
    lines.append("[사실감] 실제 휴대폰으로 찍은 실사. 그리거나 덧입힌 효과 없음. 사람·얼굴·몸이 화면에 들어오지 않음.")
    lines.append("[금지] 글자·자막·로고·워터마크 / 아기·사람 얼굴·새 사람 / 제품 복제·모양·색·디자인 변화 / 만화풍·컷 전환·디졸브 / 속도선·그린 선·덧씌우기"
                 + "".join(" / " + f for f in (motion.get("forbid_extra") or [])))
    return chr(10).join(lines)


def beat_visible_dur(beat):
    """이 칸이 화면에 나오는 길이(초) — 음성 길이(앞뒤 다듬기 반영), 없으면 target_seconds."""
    tts = (beat or {}).get("tts_path")
    try:
        from shopping_shorts import video_assemble as _va
        return float(_va._beat_effective_dur(beat, tts)) if tts and os.path.exists(tts) else float(beat.get("target_seconds") or 4)
    except Exception:      # noqa: BLE001
        return float((beat or {}).get("target_seconds") or 4)


def draft_scene(job, work, beat, style="natural", *, call=None, resolve_sources=None,
                base=None, sec=None, direction="", only_frame=False):
    """AI 장면 **초안** — 출발 화면 + 프롬프트(영어·한글 설명)를 만든다. Veo 는 부르지 않는다(관제 117, 2026-10-04 사장님
    "어떤 프롬프트로 하는지 한글과 영어를 같이 보여주고 / 기존 영상 조각을 활용 — 새로 창조하는 게 아니다").
    ★출발 화면은 **그 칸에 담은 장면**에서 뜬다(product_only=False — 청소본이 있으면 그 칸의 청소본 자리, 없으면 칸 첫 장면).
      종전엔 작업 전체에서 '제품만 나오는 가장 긴 조각'을 골라 칸과 무관한 화면에서 시작할 수 있었다.
    화면(초안 API)과 워커(run_ai_scene)가 이 함수 하나를 쓴다."""
    style = style if style in STYLES else "natural"
    extract = (job or {}).get("extract") or {}
    product = ((job.get("product") or {}).get("name") if isinstance(job.get("product"), dict) else "") or ""
    # 출발 화면 = 사장님이 고른 (영상, 초) — 안 골랐으면 이 칸 첫 장면의 시작 0.2초 뒤
    vid, t = None, None
    if isinstance(base, dict) and base.get("video_id") is not None:
        try:
            vid, t = str(base.get("video_id")), round(float(base.get("t")), 3)
        except (TypeError, ValueError):
            vid, t = None, None
    if vid is None:
        vid, t = pick_base_material(beat, extract, product_only=False)
    png = frame_at(job, work, beat, vid, t, resolve_sources=resolve_sources)
    dur = beat_visible_dur(beat)
    # 길이 = 사장님이 고른 4·6·8초 — 안 골랐으면 칸 길이에 맞춘 값. 화면에 나오는 건 칸 길이까지다.
    try:
        sec = int(sec) if int(sec) in (4, 6, 8) else pick_seconds(dur)
    except (TypeError, ValueError):
        sec = pick_seconds(dur)
    out = {"png": png, "sec": sec, "visible": round(min(dur, float(sec)), 2), "style": style, "product": product,
           "base": {"video_id": vid, "t": t}}
    if only_frame:
        return out
    motion = motion_request(beat.get("narration") or "", product or "", style, call=call, frame_path=png,
                            flow=script_flow(job, beat), direction=direction)
    out["prompt_en"] = build_prompt(motion, sec, style, visible=dur)
    out["prompt_ko"] = build_prompt_ko(motion, sec, style, visible=dur)
    return out


def script_flow(job, beat):
    """대본 흐름 — 이 칸의 앞 줄·이 줄·뒤 줄(역할 포함). 초안이 대본 흐름에 맞게 동작을 쓰도록 준다(관제 117)."""
    beats = (((job or {}).get("edit_plan") or {}).get("beats")) or []
    k = next((i for i, b in enumerate(beats) if b is beat or b.get("beat_idx") == (beat or {}).get("beat_idx")), None)
    if k is None:
        return {}
    line = lambda b: ("[%s] %s" % (b.get("role") or "", (b.get("narration") or "").strip())).strip()
    return {"prev": line(beats[k - 1]) if k > 0 else "", "this": line(beats[k]),
            "next": line(beats[k + 1]) if k + 1 < len(beats) else ""}


def frame_at(job, work, beat, vid, t, *, resolve_sources=None):
    """출발 화면 PNG — (영상, 초) 한 순간. 그 순간이 청소본(글자 지운 영상)에 있으면 청소본에서 뜬다
    (원본은 자막·워터마크가 남아 Veo가 가짜 글자를 본뜬다 — 2026-09-23 실측). 없으면 원본에서."""
    from shopping_shorts import clean_base as cb
    work = Path(work)
    out = work / f"ai_scene_base_{int(beat.get('beat_idx', 0))}.png"
    try:
        base = cb.load_base(work)
        if base is not None:
            pieces = cb.piece_map(base, {"video_id": vid, "start": float(t), "end": float(t) + 0.1})
            if pieces:
                return extract_frame(base["path"], pieces[0]["start"], out)
    except Exception as e:      # noqa: BLE001 — 청소본을 못 읽으면 원본에서 뜬다(알린다)
        print(f"[ai-scene] 청소본 자리 찾기 실패 → 원본에서: {e!r}", file=sys.stderr)
    srcs = resolve_sources(job, work) if resolve_sources else {}
    src = srcs.get(vid)
    if not src:
        raise RuntimeError("출발 화면을 뜰 소스 영상이 없습니다")
    return extract_frame(src, t, out)


def build_prompt(motion, sec, style="natural", visible=None):
    """스파이크에서 확인된 형식: 첫 프레임 묘사 + 초 단위 사건 + 재질·조명 + 금지 목록.

    ★visible = 화면에 실제로 나오는 길이(칸 길이). Veo는 4·6·8초만 만드는데 훅 칸은 그보다
      짧다(실측 2026-09-23: 훅 2.42초인데 4초를 만들어 뒤 1.58초를 버렸다). 종전엔 4초를
      3등분해 **큰 동작을 1.3~2.7초에** 뒀고, 그래서 제일 중요한 순간이 반쯤 잘린 채 끝났다.
      이제 3단계를 **보이는 구간 안에서** 나누고, 안 보이는 뒤쪽은 '가만히 있는다'로 채운다.
    """
    sec = int(sec)
    vis, a, b = _visible_window(sec, visible)     # 너무 짧으면(1.2초 미만) Veo가 3단계를 못 나눈다
    steps = motion["motion_steps_en"]
    cam = ("Handheld phone video, vertical 9:16, natural lighting as in the input image, slight handheld sway."
           if style != "impact" else
           "Handheld phone video, vertical 9:16, natural lighting as in the input image, quick dolly-in, real handheld movement only.")
    forbid = FORBID + "".join(", " + f for f in motion.get("forbid_extra") or [])
    return (
        f"INPUT IMAGE = FRAME 0: {motion['subject_desc_en']} Keep this subject exactly the same in shape, color, material and design.\n"
        + (f"SCENE AND ENVIRONMENT: {motion['environment_en']}\n" if motion.get("environment_en") else "")
        + "\n"
        f"CONTINUOUS SINGLE SHOT, ONE TAKE, NO CUT, NO DISSOLVE, {sec}.0 seconds.\n"
        + (f"ONLY THE FIRST {vis:.1f} SECONDS ARE USED. Everything that matters happens before {vis:.1f}s.\n"
           if vis < sec - 0.05 else "")
        + (f"HOOK TIMING: the boldest moment lands within the first {a}s. Do not save it for later.\n"
           if style == "impact" else "")
        + f"0.0-{a}s  {steps[0]}\n"
        f"{a}-{b}s  {steps[1]}\n"
        f"{b}-{vis:.1f}s  {steps[2]}\n"
        + (f"{vis:.1f}-{sec}.0s  The shot simply holds; nothing new happens.\n" if vis < sec - 0.05 else "")
        + "\n"
        f"CAMERA AND LIGHT: {(motion['camera_en'] + ' ') if motion.get('camera_en') else ''}{cam}\n"
        + (f"IN-CAMERA EFFECTS: {motion['effects_en']}\n" if motion.get("effects_en") else "")
        + f"REALISM: photorealistic live-action smartphone footage. Nothing is drawn, painted or animated on top of the image. "
        f"No person, face or body enters the frame at any moment.\n\n"
        f"NEGATIVE: {forbid}."
    )


def generate(png_path, prompt, sec, out_mp4, *, project=None, location=None, client=None):
    """Vertex Veo 호출(시작 이미지 보간). 실패는 예외. 실측 40~45초."""
    from shopping_shorts import config
    from google import genai
    from google.genai import types
    project = project or config.GCP_PROJECT
    location = location or config.GCP_LOCATION
    cl = client or genai.Client(vertexai=True, project=project, location=location)
    op = cl.models.generate_videos(
        model=MODEL, prompt=prompt, image=types.Image.from_file(location=str(png_path)),
        config=types.GenerateVideosConfig(aspect_ratio="9:16", duration_seconds=int(sec),
                                          number_of_videos=1, generate_audio=False))
    t0 = time.time()
    while not op.done:
        if time.time() - t0 > 600:
            raise RuntimeError("Veo 생성이 10분 안에 끝나지 않았습니다")
        time.sleep(8)
        op = cl.operations.get(op)
    if getattr(op, "error", None):
        raise RuntimeError("Veo 실패: %s" % str(op.error)[:200])
    op.response.generated_videos[0].video.save(str(out_mp4))
    if not Path(out_mp4).exists() or Path(out_mp4).stat().st_size < 10_000:
        raise RuntimeError("Veo 결과 파일이 비었습니다")
    return str(out_mp4)


def _set_state(store, job_id, beat_idx, **fields):
    """beat["ai_scene"] 갱신(+cutaway). 원본 edit_plan에 상태만 얹는다 — 파생 사본 아님."""
    job = store.get_mix_job(job_id)
    plan = (job or {}).get("edit_plan") or {}
    for b in plan.get("beats") or []:
        if int(b.get("beat_idx", -1)) == int(beat_idx):
            st = dict(b.get("ai_scene") or {})
            cut = fields.pop("_cutaway", None)
            st.update(fields)
            b["ai_scene"] = st
            if cut is not None:
                b["cutaway"] = cut
            break
    store.update_mix_job(job_id, edit_plan=plan)
    return plan


def run_ai_scene(job_id, beat_idx, style, db_path, work_root, *, gen=None, call=None):
    """워커 태스크. 성공: 자산 저장 + beat.cutaway(ai) + ai_scene.state=done. 실패: state=failed(error)."""
    from shopping_shorts.store import Store
    from shopping_shorts import mix_pipeline as mp
    from shopping_shorts import scene_assets
    style = style if style in STYLES else "natural"
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return None
    if job.get("status") == "rendering":
        _set_state(store, job_id, beat_idx, state="failed", error="렌더 중에는 만들 수 없어요 — 끝난 뒤 다시 눌러 주세요")
        return None
    beat = next((b for b in job["edit_plan"]["beats"] if int(b.get("beat_idx", -1)) == int(beat_idx)), None)
    if beat is None:
        return None
    # ★누구 비용으로 만들지 **먼저** 본다(2026-09-26) — 작업 주인이 자기 Vertex를 등록했으면 그 프로젝트, 관리자면
    #   사장님 프로젝트, 그 외는 만들지 않는다(사장님 크레딧으로 회원 영상을 대신 태우지 않는다). 프레임 추출·Gemini
    #   동작 호출을 하고 나서 거절하면 헛돈이다. 판정은 vertex_route 한 곳(API와 같은 veo_allowed).
    vcl = None
    if gen is None:
        from shopping_shorts import vertex_route
        vcl = vertex_route.veo_client(job.get("customer_id") or 0)
        if vcl is None:
            _set_state(store, job_id, beat_idx, state="failed", error=vertex_route.VEO_NEEDS_MEMBER)
            return None
    work = Path(work_root) / job_id
    work.mkdir(parents=True, exist_ok=True)
    _set_state(store, job_id, beat_idx, state="running", style=style, error=None, started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    try:
        # ★출발 화면·프롬프트는 draft_scene 한 곳(관제 117). 화면에서 사장님이 확인(또는 고친) 프롬프트가 있으면
        #   **그 문장 그대로** 만든다 — 출발 화면만 같은 규칙으로 다시 뜬다(Gemini 동작 호출 없음).
        _st = beat.get("ai_scene") or {}
        _confirmed = str(_st.get("prompt_en") or "").strip() if _st.get("confirmed") else ""
        product = ((job.get("product") or {}).get("name") if isinstance(job.get("product"), dict) else "") or ""
        if _confirmed:
            _f = draft_scene(job, work, beat, style, resolve_sources=mp._resolve_sources,
                             base=_st.get("base"), sec=_st.get("sec_pick"), only_frame=True)
            png, sec = _f["png"], _f["sec"]
            prompt = _confirmed
        else:
            _d = draft_scene(job, work, beat, style, call=call, resolve_sources=mp._resolve_sources)
            png, sec, prompt = _d["png"], _d["sec"], _d["prompt_en"]
        ts = time.strftime("%Y%m%d_%H%M%S")
        from shopping_shorts.app import _SCENE_ASSETS_DIR
        _SCENE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        out = _SCENE_ASSETS_DIR / f"veo_{job_id}_{int(beat_idx)}_{ts}.mp4"
        if gen is None:
            generate(png, prompt, sec, out, client=vcl)
        else:
            gen(png, prompt, sec, out)
        poster = _SCENE_ASSETS_DIR / f"veo_{job_id}_{int(beat_idx)}_{ts}_poster.jpg"
        try:
            poster = scene_assets.make_poster(out, poster)
        except Exception:      # noqa: BLE001 — 포스터는 안내용
            poster = None
        aid = store.add_scene_asset({
            "asset_type": "clip", "render_mode": "cutaway", "media_path": str(out),
            "poster_path": str(poster) if poster else None,
            "duration": scene_assets.probe_duration(out),
            "title": "AI 장면 · " + (beat.get("narration") or "")[:20],
            "scene_desc": beat.get("narration") or "", "category": None, "role": None,
            "subject": product or None, "tone": None,
            "source_kind": "veo", "source_ref": f"{job_id}:{int(beat_idx)}:{style}",
        }, customer_id=job.get("customer_id") or 0)
        (work / f"ai_scene_prompt_{int(beat_idx)}.txt").write_text(prompt, encoding="utf-8")
        _set_state(store, job_id, beat_idx, state="done", asset_id=int(aid), sec=sec, style=style, error=None,
                   _cutaway={"asset_id": int(aid), "match_type": "ai"})
        print(f"[ai-scene] {job_id} beat{beat_idx} {style} {sec}s → asset {aid}", file=sys.stderr)
        return int(aid)
    except Exception as e:      # noqa: BLE001 — 실패는 상태로 남긴다(워커가 죽지 않게)
        print(f"[ai-scene] {job_id} beat{beat_idx} 실패: {e!r}", file=sys.stderr)
        _set_state(store, job_id, beat_idx, state="failed", error=str(e)[:160])
        return None
