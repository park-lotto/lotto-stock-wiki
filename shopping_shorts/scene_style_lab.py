"""관리자용 장면꾸미기 실데이터 시험 공간.

원본 mix job은 읽기만 하고, 저장과 산출물은 항상
``<work root>/_scene_style_lab/<lab id>`` 안에만 남긴다.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
from pathlib import Path

from . import frame_extract, mix_pipeline, video_assemble


_LAB_ID_RE = re.compile(r"lab_[0-9a-f]{12}\Z")
_MANIFEST_NAME = "manifest.json"
FRAME_TOLERANCE = 0.034


class LabPreconditionError(RuntimeError):
    """시험을 시작하기 전에 사용자가 해결해야 하는 조건 오류."""


def contract_from_context(context: dict, clean_signature: str) -> dict:
    """한 출구가 지켜야 할 훅/본문/청소본 계약을 실제 장면 컨텍스트에서 뽑는다."""
    scenes = (context or {}).get("scenes") or []
    visible_speech = [
        scene for scene in scenes
        if str(scene.get("caption") or "").strip() and scene.get("caption_visible") is not False
    ]
    hook_count = sum(1 for scene in visible_speech if scene.get("kind") == "hook")
    body = [scene for scene in visible_speech if scene.get("kind") == "body"]
    return {
        "hook_caption_count": hook_count,
        "body_first_start": float(body[0]["start"]) if body else None,
        "clean_signature": str(clean_signature or ""),
    }


def compare_contract(expected: dict, actual: dict) -> dict:
    """두 출구의 핵심 배선을 30fps 한 프레임 허용치로 비교한다."""
    expected_start = expected.get("body_first_start")
    actual_start = actual.get("body_first_start")
    body_start_ok = expected_start is None and actual_start is None
    if expected_start is not None and actual_start is not None:
        body_start_ok = abs(float(actual_start) - float(expected_start)) <= FRAME_TOLERANCE
    checks = {
        "hook_caption_count": int(actual.get("hook_caption_count", -1)) == 0,
        "body_first_start": body_start_ok,
        "clean_signature": str(actual.get("clean_signature") or "") ==
                           str(expected.get("clean_signature") or ""),
    }
    return {"ok": all(checks.values()), "checks": checks}


def clean_plan_signature(plan: dict | None) -> str:
    """라이브 청소본 파일명이 쓰는 편성 서명을 그대로 반환한다."""
    return mix_pipeline._plan_signature(plan or {})


def timing_signature(plan: dict | None) -> str:
    """TTS 파일 내용과 말자막 분할·시작을 묶은 LAB 전용 freshness 서명."""
    fields = (
        "beat_idx", "narration", "tts_path", "target_seconds", "duration", "head_trim",
        "caption_lines", "cap_durs", "cap_lead", "cap_offset", "tts_ver",
    )
    rows = []
    for beat in (plan or {}).get("beats") or []:
        row = {name: copy.deepcopy(beat.get(name)) for name in fields}
        path = Path(str(beat.get("tts_path") or ""))
        row["tts_sha256"] = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
        rows.append(row)
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def lab_dir(work_root: Path | str, lab_id: str) -> Path:
    """경로순회가 불가능한 시험 폴더 경로를 만든다."""
    if not _LAB_ID_RE.fullmatch(str(lab_id or "")):
        raise ValueError("잘못된 시험 번호")
    return Path(work_root) / "_scene_style_lab" / lab_id


def _manifest_path(work_root: Path | str, lab_id: str) -> Path:
    return lab_dir(work_root, lab_id) / _MANIFEST_NAME


def write_manifest(target: Path, manifest: dict) -> None:
    """완전한 JSON만 보이도록 임시 파일을 거쳐 교체한다."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    final = target / _MANIFEST_NAME
    temporary = target / (_MANIFEST_NAME + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(final)


def read_manifest(work_root: Path | str, lab_id: str) -> dict:
    return json.loads(_manifest_path(work_root, lab_id).read_text(encoding="utf-8"))


def _snapshot_signature(snapshot: dict | None) -> str:
    raw = json.dumps(snapshot or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def merge_generated_fields(work_root: Path | str, started: dict, **fields: dict) -> dict:
    """생성 시작 뒤 설정이 그대로일 때 산출 필드만 최신 manifest에 합친다."""
    current = read_manifest(work_root, started["lab_id"])
    if _snapshot_signature(current.get("scene_style")) != _snapshot_signature(started.get("scene_style")):
        raise LabPreconditionError("렌더 중 장면꾸미기 설정이 바뀌었습니다")
    started_generation = ((started.get("render_state") or {}).get("generation"))
    current_generation = ((current.get("render_state") or {}).get("generation"))
    if started_generation is not None and started_generation != current_generation:
        raise LabPreconditionError("새 렌더 요청이 시작되어 이전 결과를 버렸습니다")
    for name, value in fields.items():
        if name in {"outputs", "receipts", "contracts"}:
            current.setdefault(name, {}).update(copy.deepcopy(value))
        else:
            current[name] = copy.deepcopy(value)
    write_manifest(lab_dir(work_root, started["lab_id"]), current)
    return current


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_receipt(path: Path | str) -> dict:
    """실제로 생성된 MP4 파일의 내용과 재생시간을 고정한다."""
    target = Path(path)
    duration = float(video_assemble._probe_duration(str(target)) or 0.0)
    if not target.is_file() or target.stat().st_size <= 0 or duration <= 0:
        raise RuntimeError("시험 MP4를 재생 가능한 파일로 확인하지 못했습니다")
    return {
        "sha256": _file_sha256(target),
        "bytes": target.stat().st_size,
        "duration": duration,
        "verified_by": "artifact-receipt",
    }


def output_path(work_root: Path | str, lab_id: str, output_name: str) -> Path:
    """manifest가 가리키는 산출물이 해당 LAB 폴더 안의 실제 파일인지 확인한다."""
    manifest = read_manifest(work_root, lab_id)
    raw = (manifest.get("outputs") or {}).get(output_name)
    if not raw:
        raise LabPreconditionError("시험 산출물이 아직 없습니다")
    target = Path(str(raw)).resolve()
    allowed = lab_dir(work_root, lab_id).resolve()
    if target == allowed or allowed not in target.parents or not target.is_file():
        raise LabPreconditionError("시험 산출물 경로가 올바르지 않습니다")
    receipt = ((manifest.get("receipts") or {}).get(output_name) or {})
    if output_name == "mp4":
        if not receipt.get("sha256"):
            raise LabPreconditionError("시험 산출물 검증 기록이 없습니다")
        if _file_sha256(target) != receipt["sha256"] or target.stat().st_size != receipt.get("bytes"):
            raise LabPreconditionError("시험 산출물 파일이 바뀌었습니다")
    return target


def resolve_clean_contract(job: dict, job_work: Path | str) -> dict | None:
    """현재 편성에 쓸 수 있는 청소본만 반환한다.

    ``preview_path``와 ``video_path``는 의도적으로 보지 않는다. 이 함수의
    ``None``은 시험 차단이지 원본 영상 폴백 신호가 아니다.
    """
    job = job or {}
    signature = clean_plan_signature(job.get("edit_plan") or {})
    clean_sources = dict(job.get("clean_sources") or {})
    if clean_sources:
        paths = {str(video_id): str(path) for video_id, path in clean_sources.items()}
        if paths and all(Path(path).is_file() for path in paths.values()):
            return {"kind": "sources", "paths": paths, "signature": signature}
        return None

    clean_final = mix_pipeline.clean_final_path_for_plan(job, Path(job_work))
    if clean_final is not None and Path(clean_final).is_file():
        return {"kind": "final", "path": str(clean_final), "signature": signature}
    return None


def create_copy(job_id: str, job: dict, work_root: Path | str) -> dict:
    """원본 job을 바꾸지 않고 독립 시험 manifest를 만든다."""
    source_job = job or {}
    edit_plan = copy.deepcopy(source_job.get("edit_plan") or {})
    if not edit_plan.get("beats"):
        raise LabPreconditionError("편집안이 없습니다")

    clean = resolve_clean_contract(source_job, Path(work_root) / job_id)
    if clean is None:
        raise LabPreconditionError("현재 편성과 일치하는 자막제거 청소본이 없습니다")

    from .scene_style import validate_snapshot

    snapshot = copy.deepcopy((source_job.get("deco") or {}).get("scene_style") or {
        "version": 1,
        "mode": "story",
        "presetId": "t11",
    })
    snapshot["hookCaptionMode"] = "hidden"
    try:
        snapshot = validate_snapshot(snapshot)
    except (TypeError, ValueError) as exc:
        raise LabPreconditionError(f"저장된 장면꾸미기 설정을 읽을 수 없습니다: {exc}") from exc

    lab_id = "lab_" + secrets.token_hex(6)
    manifest = {
        "version": 1,
        "lab_id": lab_id,
        "source_job_id": str(job_id),
        "source_plan_signature": clean_plan_signature(edit_plan),
        "source_timing_signature": timing_signature(edit_plan),
        "edit_plan": edit_plan,
        "headcopy": copy.deepcopy(source_job.get("headcopy")),
        "caption_style": copy.deepcopy(source_job.get("caption_style")),
        "deco": copy.deepcopy(source_job.get("deco") or {}),
        "clean": copy.deepcopy(clean),
        "hook_caption_mode": "hidden",
        "scene_style": snapshot,
        "outputs": {},
    }
    target = lab_dir(work_root, lab_id)
    target.mkdir(parents=True, exist_ok=False)
    write_manifest(target, manifest)
    return manifest


def assert_fresh(manifest: dict, source_job: dict) -> None:
    """복사 뒤 원본 편성이 바뀌었으면 산출을 차단한다."""
    expected = str((manifest or {}).get("source_plan_signature") or "")
    actual = clean_plan_signature((source_job or {}).get("edit_plan") or {})
    if not expected or expected != actual:
        raise LabPreconditionError("복사 후 원본 편성이 바뀌었습니다")
    expected_timing = str((manifest or {}).get("source_timing_signature") or "")
    actual_timing = timing_signature((source_job or {}).get("edit_plan") or {})
    if not expected_timing or expected_timing != actual_timing:
        raise LabPreconditionError("복사 후 원본 음성 또는 자막 타이밍이 바뀌었습니다")


def save_snapshot(work_root: Path | str, lab_id: str, snapshot: dict) -> dict:
    """시험 스냅샷만 갱신하고 원본 job은 건드리지 않는다."""
    from .scene_style import validate_snapshot

    candidate = copy.deepcopy(snapshot or {})
    candidate["hookCaptionMode"] = "hidden"
    saved = validate_snapshot(candidate)
    manifest = read_manifest(work_root, lab_id)
    changed = saved != manifest.get("scene_style")
    manifest["scene_style"] = saved
    manifest["hook_caption_mode"] = "hidden"
    if changed:
        manifest["outputs"] = {}
        manifest["contracts"] = {}
        manifest["receipts"] = {}
        manifest["render_state"] = {"status": "idle", "error": None}
    write_manifest(lab_dir(work_root, lab_id), manifest)
    return saved


def _tts_paths(edit_plan: dict) -> dict:
    beats = (edit_plan or {}).get("beats") or []
    paths = {beat["beat_idx"]: str(beat["tts_path"]) for beat in beats
             if beat.get("tts_path") and Path(beat["tts_path"]).is_file()}
    if not beats or len(paths) != len(beats):
        raise LabPreconditionError("음성 파일이 완전하지 않습니다")
    return paths


def _clean_sources_for_render(manifest: dict, timeline: list, target: Path) -> tuple[dict, dict]:
    """시험 manifest의 청소본을 라이브 assemble 입력으로 변환한다."""
    clean = manifest.get("clean") or {}
    expected_signature = str(manifest.get("source_plan_signature") or "")
    if clean.get("signature") != expected_signature:
        raise LabPreconditionError("청소본 편성 서명이 다릅니다")
    if clean.get("kind") == "sources":
        paths = {str(key): str(value) for key, value in (clean.get("paths") or {}).items()}
        if not paths or not all(Path(path).is_file() for path in paths.values()):
            raise LabPreconditionError("자막제거 청소본 파일이 없습니다")
        return copy.deepcopy(manifest["edit_plan"]), paths
    if clean.get("kind") == "final":
        clean_final = Path(str(clean.get("path") or ""))
        if not clean_final.is_file():
            raise LabPreconditionError("자막제거 청소본 파일이 없습니다")
        clips = mix_pipeline.split_final_into_beat_clips(
            str(clean_final), timeline, target, prefix="lab"
        )
        if not clips:
            raise LabPreconditionError("자막제거 청소본을 장면별로 나누지 못했습니다")
        plan = mix_pipeline.plan_using_beat_clips(
            manifest["edit_plan"], clips, timeline, prefix="lab"
        )
        return plan, dict(clips)
    raise LabPreconditionError("자막제거 청소본 정보가 올바르지 않습니다")


def render_copy(manifest: dict, source_job: dict, work_root: Path | str) -> Path:
    """라이브 assemble 경로를 쓰되 출력은 LAB 폴더에만 만든다."""
    assert_fresh(manifest, source_job)
    edit_plan = copy.deepcopy(manifest.get("edit_plan") or {})
    tts_paths = _tts_paths(edit_plan)
    target = lab_dir(work_root, manifest["lab_id"])
    target.mkdir(parents=True, exist_ok=True)
    timeline = video_assemble._beat_timeline(edit_plan, tts_paths)
    render_plan, source_paths = _clean_sources_for_render(manifest, timeline, target)

    snapshot = copy.deepcopy(manifest.get("scene_style") or {})
    snapshot["hookCaptionMode"] = "hidden"
    deco = copy.deepcopy(manifest.get("deco") or {})
    deco["scene_style"] = snapshot
    generation = ((manifest.get("render_state") or {}).get("generation"))
    output = target / (f"lab-final-{generation}.mp4" if generation else "lab-final.mp4")
    video_assemble.assemble(
        render_plan,
        tts_paths,
        source_paths,
        str(output),
        headcopy=copy.deepcopy(manifest.get("headcopy")),
        caption_style=copy.deepcopy(manifest.get("caption_style")),
        deco=deco,
    )
    if not output.is_file():
        raise RuntimeError("시험 MP4가 생성되지 않았습니다")

    updated = copy.deepcopy(manifest)
    updated.setdefault("outputs", {})["mp4"] = str(output)
    receipt = artifact_receipt(output)
    updated.setdefault("receipts", {})["mp4"] = receipt
    from .scene_style import context_for
    render_contract = contract_from_context(
        context_for(timeline, manifest.get("headcopy"), snapshot, manifest.get("lab_id")),
        (manifest.get("clean") or {}).get("signature"),
    )
    updated.setdefault("contracts", {})["mp4"] = render_contract
    updated["contracts"]["mp4"].update({
        "artifact_sha256": receipt["sha256"],
        "verified_by": receipt["verified_by"],
    })
    updated["contracts"]["landing"] = copy.deepcopy(render_contract)
    updated["contracts"]["landing"].update({
        "artifact_sha256": receipt["sha256"],
        "verified_by": "same-file",
    })
    updated = merge_generated_fields(
        work_root,
        manifest,
        outputs={"mp4": updated["outputs"]["mp4"]},
        receipts={"mp4": updated["receipts"]["mp4"]},
        contracts={
            "mp4": updated["contracts"]["mp4"],
            "landing": updated["contracts"]["landing"],
        },
    )
    manifest.clear()
    manifest.update(updated)
    return output


def clean_preview_for(manifest: dict, source_job: dict, work_root: Path | str) -> Path:
    """편집기 배경에 쓸 청소 영상. 원본 폴백은 없다."""
    assert_fresh(manifest, source_job)
    clean = manifest.get("clean") or {}
    if clean.get("signature") != manifest.get("source_plan_signature"):
        raise LabPreconditionError("청소본 편성 서명이 다릅니다")
    if clean.get("kind") == "final":
        path = Path(str(clean.get("path") or ""))
        if not path.is_file():
            raise LabPreconditionError("자막제거 청소본 파일이 없습니다")
        return path
    if clean.get("kind") != "sources":
        raise LabPreconditionError("자막제거 청소본 정보가 올바르지 않습니다")

    source_paths = {str(key): str(value) for key, value in (clean.get("paths") or {}).items()}
    if not source_paths or not all(Path(path).is_file() for path in source_paths.values()):
        raise LabPreconditionError("자막제거 청소본 파일이 없습니다")
    target = lab_dir(work_root, manifest["lab_id"])
    target.mkdir(parents=True, exist_ok=True)
    output = target / "lab-clean-preview.mp4"
    if output.is_file() and output.stat().st_size:
        return output
    video_assemble.assemble(
        copy.deepcopy(manifest.get("edit_plan") or {}),
        _tts_paths(manifest.get("edit_plan") or {}),
        source_paths,
        str(output),
        deco={},
        burn_captions=False,
    )
    if not output.is_file():
        raise RuntimeError("시험용 청소 미리보기가 생성되지 않았습니다")
    return output


def frame_for_scene(
    manifest: dict,
    source_job: dict,
    work_root: Path | str,
    scene_index: int,
) -> Path:
    """같 자막 장면의 중앙 프레임을 반드시 청소 영상에서 뽑는다."""
    from .scene_style import context_for

    edit_plan = manifest.get("edit_plan") or {}
    timeline = video_assemble._beat_timeline(edit_plan, _tts_paths(edit_plan))
    context = context_for(
        timeline,
        manifest.get("headcopy"),
        manifest.get("scene_style") or {},
        manifest.get("lab_id"),
    )
    try:
        scene = context["scenes"][int(scene_index)]
    except (IndexError, TypeError, ValueError):
        raise LabPreconditionError("장면 번호가 올바르지 않습니다") from None
    source = clean_preview_for(manifest, source_job, work_root)
    target = lab_dir(work_root, manifest["lab_id"]) / "frames"
    at = (float(scene["start"]) + float(scene["end"])) / 2
    frame = frame_extract.extract_frame_at(
        str(source), target, at, filename=f"scene-{int(scene_index):04d}.jpg"
    )
    if not frame:
        raise RuntimeError("시험용 청소 프레임을 추출하지 못했습니다")
    return Path(frame)


def verify_capcut_overlay_draft(draft: dict, expected_layers: list[dict]) -> None:
    """CapCut JSON을 다시 읽어 장면 레이어의 개수와 μs 타이밍을 역검증한다."""
    track = next(
        (item for item in (draft or {}).get("tracks", [])
         if item.get("name") == "scene-style-overlay"),
        None,
    )
    if track is None:
        raise LabPreconditionError("CapCut 장면꾸미기 트랙이 없습니다")
    actual = [segment.get("target_timerange") for segment in track.get("segments", [])]
    expected = [
        {"start": round(float(layer["start"]) * 1_000_000),
         "duration": round((float(layer["end"]) - float(layer["start"])) * 1_000_000)}
        for layer in expected_layers
    ]
    if actual != expected:
        raise LabPreconditionError("CapCut 장면꾸미기 타이밍이 실제 자막 타임라인과 다릅니다")


def _checked_layer_path(layer_dir: Path, name: str) -> Path:
    target = (layer_dir / str(name or "")).resolve()
    if layer_dir.resolve() not in target.parents or not target.is_file():
        raise LabPreconditionError("장면 레이어 파일이 없거나 경로가 올바르지 않습니다")
    return target


def overlay_specs_for_scene(scene: dict, layer: dict, layer_dir: Path | str) -> list[dict]:
    """브라우저가 뽑은 모션 PNG를 CapCut 30fps 구간으로 펼친다."""
    layer_dir = Path(layer_dir)
    if layer.get("camera"):
        raise LabPreconditionError(
            "CapCut 시험 초안은 화면 전체 카메라 모션을 아직 정확히 옮길 수 없습니다"
        )
    start = float(scene["start"])
    end = float(scene["end"])
    common = {
        "caption_visible": scene.get("caption_visible") is not False,
    }
    static_path = _checked_layer_path(layer_dir, layer.get("file"))
    animation = layer.get("animation") or {}
    count = int(animation.get("count") or 0)
    pattern = str(animation.get("pattern") or "")
    specs = []
    for frame in range(count):
        frame_start = start + frame / 30
        frame_end = min(end, start + (frame + 1) / 30)
        if frame_start >= end:
            break
        try:
            frame_name = pattern % frame
        except (TypeError, ValueError):
            raise LabPreconditionError("장면 모션 프레임 이름이 올바르지 않습니다") from None
        specs.append({
            "path": str(_checked_layer_path(layer_dir, frame_name)),
            "start": frame_start,
            "end": frame_end,
            "t0": frame_start,
            "dur": frame_end - frame_start,
            **common,
        })
    covered_until = specs[-1]["end"] if specs else start
    if covered_until < end:
        specs.append({
            "path": str(static_path),
            "start": covered_until,
            "end": end,
            "t0": covered_until,
            "dur": end - covered_until,
            **common,
        })
    return specs


def build_capcut_copy(
    manifest: dict,
    source_job: dict,
    work_root: Path | str,
    base_abs: str,
) -> Path:
    """같은 청소본·타임라인·스냅샷으로 관리자용 CapCut 시험 초안을 만든다."""
    if not str(base_abs or "").strip():
        raise LabPreconditionError("캡컷 Drafts 폴더의 절대경로가 필요합니다")
    assert_fresh(manifest, source_job)
    from . import capcut_draft, scene_style

    edit_plan = copy.deepcopy(manifest.get("edit_plan") or {})
    tts_paths = _tts_paths(edit_plan)
    target = lab_dir(work_root, manifest["lab_id"])
    target.mkdir(parents=True, exist_ok=True)
    timeline = video_assemble._beat_timeline(edit_plan, tts_paths)
    capcut_plan, source_paths = _clean_sources_for_render(manifest, timeline, target)

    snapshot = copy.deepcopy(manifest.get("scene_style") or {})
    snapshot["hookCaptionMode"] = "hidden"
    layer_dir = target / "capcut-overlay-source"
    layer_dir.mkdir(parents=True, exist_ok=True)
    context = scene_style.context_for(
        timeline, manifest.get("headcopy"), snapshot, manifest.get("lab_id")
    )
    rendered = scene_style.render_layers(
        timeline, snapshot, layer_dir,
        headcopy=manifest.get("headcopy"), job_id=manifest.get("lab_id"),
    )
    if len(rendered) != len(context["scenes"]):
        raise LabPreconditionError("장면 레이어 개수가 실제 자막 타임라인과 다릅니다")
    overlay_layers = []
    for scene, layer in zip(context["scenes"], rendered, strict=True):
        overlay_layers.extend(overlay_specs_for_scene(scene, layer, layer_dir))

    out_root = target / "capcut"
    project_name = f"장면꾸미기시험 {manifest['lab_id'][-4:]}"
    project, _, _ = capcut_draft.assemble_draft_folder(
        out_root,
        str(base_abs),
        plan=capcut_plan,
        timeline=timeline,
        source_video_paths=source_paths,
        tts_paths=tts_paths,
        project_name=project_name,
        caption_style=None,
        deco={},
        scene_overlay_layers=overlay_layers,
    )
    draft_path = Path(project) / "draft_content.json"
    if not draft_path.is_file():
        raise RuntimeError("CapCut 시험 초안이 생성되지 않았습니다")
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    verify_capcut_overlay_draft(draft, overlay_layers)

    updated = copy.deepcopy(manifest)
    updated.setdefault("outputs", {})["capcut_project"] = str(project)
    updated.setdefault("contracts", {})["capcut"] = contract_from_context(
        context, (manifest.get("clean") or {}).get("signature")
    )
    updated = merge_generated_fields(
        work_root,
        manifest,
        outputs={"capcut_project": updated["outputs"]["capcut_project"]},
        contracts={"capcut": updated["contracts"]["capcut"]},
    )
    manifest.clear()
    manifest.update(updated)
    return Path(project)
