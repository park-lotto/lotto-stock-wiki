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
          "no change of the product's shape, color or design, no cartoon style, no cut, no dissolve")


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
    got = []
    for s in _segments(extract):
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
    },
    "required": ["subject_desc_en", "motion_steps_en"],
}


def motion_request(narration, subject_hint="", style="natural", call=None, frame_path=None):
    """대사 한 줄 + **베이스 프레임 이미지** → (영어) 피사체 묘사 + 초 단위 동작 3단계. Gemini JSON 호출; 실패하면 기본값.

    ★이미지를 반드시 같이 준다(2026-09-23 실측): 텍스트만 주면 "뒤집으면 핑크가 되는 리버시블 인형"처럼
      제품에 없는 기능을 지어내고 Veo가 그대로 만든다(훅 실측 — 노란 인형이 핑크로 뒤집힘)."""
    if call is None:
        from shopping_shorts.edit_plan import _vault_call, _vault_call_image
        call = (lambda p, s: _vault_call_image(p, s, frame_path)) if frame_path else _vault_call
    prompt = (
        "You write shot directions for a 4-8 second product video clip that starts from the attached still frame (FRAME 0).\n"
        "Describe ONLY what is visible in the frame. Do not invent product features, colors, parts or mechanisms that are not visible.\n"
        f"Product / subject hint (Korean): {subject_hint or '(unknown)'}\n"
        f"Narration line (Korean) this shot must match: {narration}\n"
        f"Style: {'high-impact hook (fast push-in, one bold action, slight camera shake)' if style == 'impact' else 'natural subtle motion (breathing, gentle hand, slow push-in)'}\n"
        "Return JSON: subject_desc_en (one sentence describing the subject exactly as it appears, colors, materials), "
        "motion_steps_en (exactly 3 short sentences: what happens in the first third, middle third, last third; "
        "only movements that could physically happen to what is visible in this frame — camera moves, gentle hand contact, "
        "soft parts swaying, light changes; the product must keep its exact shape, color, material and design; it must not "
        "transform, flip inside out, change color or reveal hidden parts; no new people; no text), "
        "forbid_extra (0-3 short English phrases to forbid, e.g. 'no washing machine')."
    )
    try:
        res = call(prompt, _MOTION_SCHEMA) or {}
    except Exception:      # noqa: BLE001 — 지시 생성 실패는 기본 동작으로
        res = {}
    steps = [str(x).strip() for x in (res.get("motion_steps_en") or []) if str(x).strip()][:3]
    if len(steps) < 3:
        steps = (["The camera holds on the subject with a slight natural handheld sway.",
                  "A slow gentle push-in toward the subject; soft parts move subtly.",
                  "The push-in continues; the subject stays centered and unchanged."]
                 if style != "impact" else
                 ["A quick push-in toward the subject with a slight handheld shake.",
                  "One bold, clear action on the subject happens in the center of the frame.",
                  "The camera settles; the subject is centered, sharp and unchanged."])
    return {"subject_desc_en": str(res.get("subject_desc_en") or subject_hint or "the product in the input image").strip(),
            "motion_steps_en": steps,
            "forbid_extra": [str(x).strip() for x in (res.get("forbid_extra") or []) if str(x).strip()][:3]}


def build_prompt(motion, sec, style="natural"):
    """스파이크에서 확인된 형식: 첫 프레임 묘사 + 초 단위 사건 + 재질·조명 + 금지 목록."""
    sec = int(sec)
    a, b = round(sec / 3.0, 1), round(sec * 2 / 3.0, 1)
    steps = motion["motion_steps_en"]
    cam = ("Handheld phone video, vertical 9:16, natural lighting as in the input image, slight handheld sway."
           if style != "impact" else
           "Handheld phone video, vertical 9:16, natural lighting as in the input image, punchy fast push-in, slight shake.")
    forbid = FORBID + "".join(", " + f for f in motion.get("forbid_extra") or [])
    return (
        f"INPUT IMAGE = FRAME 0: {motion['subject_desc_en']} Keep this subject exactly the same in shape, color, material and design.\n\n"
        f"CONTINUOUS SINGLE SHOT, ONE TAKE, NO CUT, NO DISSOLVE, {sec}.0 seconds.\n"
        f"0.0-{a}s  {steps[0]}\n"
        f"{a}-{b}s  {steps[1]}\n"
        f"{b}-{sec}.0s  {steps[2]}\n\n"
        f"CAMERA AND LIGHT: {cam}\n\n"
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
    work = Path(work_root) / job_id
    work.mkdir(parents=True, exist_ok=True)
    _set_state(store, job_id, beat_idx, state="running", style=style, error=None, started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    try:
        extract = job.get("extract") or {}
        product = ((job.get("product") or {}).get("name") if isinstance(job.get("product"), dict) else "") or ""
        words = tuple(w for w in re.split(r"[\s,/]+", product) if len(w) >= 2)[:4]
        png = base_frame_path(job, work, beat, extract, product_only=True, product_words=words,
                              resolve_sources=mp._resolve_sources)
        tts = beat.get("tts_path")
        try:
            from shopping_shorts import video_assemble as _va
            dur = float(_va._beat_effective_dur(beat, tts)) if tts and os.path.exists(tts) else float(beat.get("target_seconds") or 4)
        except Exception:      # noqa: BLE001
            dur = float(beat.get("target_seconds") or 4)
        sec = pick_seconds(dur)
        motion = motion_request(beat.get("narration") or "", product or "", style, call=call, frame_path=png)
        prompt = build_prompt(motion, sec, style)
        ts = time.strftime("%Y%m%d_%H%M%S")
        from shopping_shorts.app import _SCENE_ASSETS_DIR
        _SCENE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        out = _SCENE_ASSETS_DIR / f"veo_{job_id}_{int(beat_idx)}_{ts}.mp4"
        (gen or generate)(png, prompt, sec, out)
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
