"""소스에 없는 4초 제품 장면을 Veo로 보추한다.

인증·UI·편집안 배정은 app/worker가 담당하고, 이 모듈은
  대사 -> 영상 프롬프트 -> Vertex Veo -> 장면 자산 저장
의 한 경로만 가진다.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from shopping_shorts import edit_plan, scene_assets
from shopping_shorts.store import Store


PROMPT_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string"},
        "shot_label": {"type": "string"},
    },
    "required": ["prompt", "shot_label"],
}

INTENTS = {
    "auto": "Infer the single clearest physical demonstration from the narration.",
    "use": "Show one natural real-world use of the exact product.",
    "wash": "Show the exact product being gently rinsed with clean running water.",
    "fit": "Show the exact product remaining securely fitted during one natural movement.",
    "result": "Show one believable visible result after using the exact product.",
    "detail": "Show a restrained macro product detail shot with one slow camera move.",
}


def vertex_config():
    """서버에 심는 비밀값은 코드에 놓지 않는다."""
    project = (os.getenv("AI_SCENE_VERTEX_PROJECT")
               or os.getenv("GOOGLE_CLOUD_PROJECT")
               or os.getenv("GCP_PROJECT") or "").strip()
    return {
        "project": project,
        "location": (os.getenv("AI_SCENE_VERTEX_LOCATION") or "us-central1").strip(),
        "model": (os.getenv("AI_SCENE_VERTEX_MODEL") or "veo-3.1-generate-001").strip(),
    }


def configured():
    return bool(vertex_config()["project"])


def _fallback_prompt(narration: str, intent: str) -> str:
    action = INTENTS.get(intent) or INTENTS["auto"]
    return (
        "Create a 4-second vertical photorealistic product demonstration. "
        "The supplied first frame is the visual source of truth. Preserve the exact product's "
        "shape, color, material, thickness, proportions and fitted parts in every frame. "
        f"{action} "
        f"Narration context: {narration}. "
        "One continuous close-up smartphone shot, natural available light, real skin and material "
        "texture, subtle handheld movement and autofocus breathing. Use only one simple action. "
        "No text, captions, labels, added logo, extra product, color change, duplicated parts, "
        "morphing, deformed fingers, glossy CGI, dramatic commercial lighting or impossible motion."
    )


def build_prompt(narration: str, intent: str = "auto"):
    """제품 외형 고정 규칙은 코드가 넣고, 대사의 한 동작만 Gemini가 고른다."""
    narration = re.sub(r"\s+", " ", str(narration or "")).strip()[:500]
    intent = intent if intent in INTENTS else "auto"
    instruction = f"""You design realistic four-second product B-roll for Korean shopping shorts.
Return JSON only. Write one English Veo prompt and a short Korean shot_label.

Narration: {narration}
Direction: {INTENTS[intent]}

Hard rules:
- The supplied first frame is the source of truth for the product identity.
- Preserve exact geometry, color, material, thickness, proportions and fitted parts.
- One continuous close-up shot and only one simple physical action.
- Natural smartphone footage, available light, real textures, restrained camera motion.
- Do not invent performance evidence beyond what can be visibly demonstrated.
- No text, captions, labels, extra product, duplicated parts, morphing, CGI gloss or deformed anatomy.
- Duration is exactly four seconds and aspect ratio is 9:16.
"""
    try:
        got = edit_plan._vault_call(instruction, PROMPT_SCHEMA) or {}
    except Exception:  # 프롬프트 설계 실패로 유료 영상 생성을 죽이지 않는다
        got = {}
    prompt = str(got.get("prompt") or "").strip() or _fallback_prompt(narration, intent)
    # 모델이 바꿨도 제품 고정/금지 규칙은 항상 뒤에 다시 박힌다.
    guard = (
        " The supplied first frame is the visual source of truth. Keep the exact same product "
        "geometry, color, material and proportions in every frame. Single continuous shot. "
        "No text, no additional product, no morphing, no disappearing parts, no CGI appearance."
    )
    return prompt + guard, str(got.get("shot_label") or "AI 보추 장면").strip()[:80]


def status_path(work_root, job_id: str, request_id: str) -> Path:
    return Path(work_root) / job_id / "ai_scenes" / f"{request_id}.json"


def write_status(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def read_status(work_root, job_id: str, request_id: str):
    p = status_path(work_root, job_id, request_id)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run(job_id: str, request_id: str, beat_idx: int, reference_path: str,
        narration: str, intent: str, db_path, work_root):
    """독립 워커에서 실행. 성공하면 현재 비트의 cutaway로 즉시 연결한다."""
    path = status_path(work_root, job_id, request_id)
    write_status(path, {"state": "running", "phase": "프롬프트 설계 중"})
    try:
        cfg = vertex_config()
        if not cfg["project"]:
            raise RuntimeError("AI_SCENE_VERTEX_PROJECT가 설정되지 않았습니다")
        ref = Path(reference_path)
        if not ref.exists():
            raise RuntimeError("제품 기준 프레임을 찾지 못했습니다")

        store = Store(db_path)
        job = store.get_mix_job(job_id)
        if not job:
            raise RuntimeError("영상 작업을 찾지 못했습니다")
        cid = int(job.get("customer_id") or 0)

        from shopping_shorts import keyctx
        with keyctx.owner(cid):
            prompt, label = build_prompt(narration, intent)
        write_status(path, {"state": "running", "phase": "4초 영상 생성 중",
                            "prompt": prompt, "label": label})

        from google import genai
        from google.genai import types
        client = genai.Client(vertexai=True, project=cfg["project"], location=cfg["location"])
        operation = client.models.generate_videos(
            model=cfg["model"], prompt=prompt,
            image=types.Image.from_file(location=str(ref)),
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16", duration_seconds=4, number_of_videos=1,
                generate_audio=False,
                negative_prompt=("text captions labels extra objects duplicated product product morphing "
                                 "deformed hands deformed ears CGI plastic render"),
            ))
        while not operation.done:
            time.sleep(10)
            operation = client.operations.get(operation)
        if getattr(operation, "error", None):
            raise RuntimeError(str(operation.error)[:300])

        out_dir = Path(work_root) / job_id / "ai_scenes"
        out_dir.mkdir(parents=True, exist_ok=True)
        raw = out_dir / f"{request_id}_raw.mp4"
        operation.response.generated_videos[0].video.save(str(raw))
        final = out_dir / f"{request_id}.mp4"
        # 장면 라이브러리·렌더와 동일한 규격으로 정규화한다.
        scene_assets.make_clip(raw, 0, 4, final)
        poster = out_dir / f"{request_id}.jpg"
        scene_assets.make_poster(final, poster)

        aid = store.add_scene_asset({
            "asset_type": "clip", "render_mode": "replace",
            "media_path": str(final), "poster_path": str(poster) if poster.exists() else None,
            "duration": scene_assets.probe_duration(final), "keep_original_audio": 0,
            "title": label, "scene_desc": narration, "role": "훅" if int(beat_idx) == 0 else "강조",
            "keywords": ["생성장면", intent], "source_kind": "vertex_veo",
            "source_ref": f"{job_id}:{beat_idx}:{request_id}", "source_origin": "촬영원본",
        }, customer_id=cid)

        plan = (store.get_mix_job(job_id) or {}).get("edit_plan") or {}
        hit = next((b for b in (plan.get("beats") or [])
                    if int(b.get("beat_idx", -1)) == int(beat_idx)), None)
        if hit is None:
            raise RuntimeError("생성한 영상을 넣을 멘트 칸을 찾지 못했습니다")
        hit["cutaway"] = {"asset_id": aid, "match_type": "ai_generated"}
        store.update_mix_job(job_id, edit_plan=plan)
        write_status(path, {"state": "done", "asset_id": aid, "prompt": prompt,
                            "label": label, "duration": scene_assets.probe_duration(final)})
    except Exception as exc:  # noqa: BLE001 - 워커는 실패를 상태 파일에 남기고 다음 큐를 계속 처리해야 한다
        write_status(path, {"state": "failed", "error": str(exc)[:500]})
        raise
