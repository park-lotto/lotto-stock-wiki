"""관리자용 장면꾸미기 실데이터 시험 공간.

원본 mix job은 읽기만 하고, 저장과 산출물은 항상
``<work root>/_scene_style_lab/<lab id>`` 안에만 남긴다.
"""

from __future__ import annotations

import copy
import json
import re
import secrets
from pathlib import Path

from . import mix_pipeline


_LAB_ID_RE = re.compile(r"lab_[0-9a-f]{12}\Z")
_MANIFEST_NAME = "manifest.json"


class LabPreconditionError(RuntimeError):
    """시험을 시작하기 전에 사용자가 해결해야 하는 조건 오류."""


def clean_plan_signature(plan: dict | None) -> str:
    """라이브 청소본 파일명이 쓰는 편성 서명을 그대로 반환한다."""
    return mix_pipeline._plan_signature(plan or {})


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


def save_snapshot(work_root: Path | str, lab_id: str, snapshot: dict) -> dict:
    """시험 스냅샷만 갱신하고 원본 job은 건드리지 않는다."""
    from .scene_style import validate_snapshot

    candidate = copy.deepcopy(snapshot or {})
    candidate["hookCaptionMode"] = "hidden"
    saved = validate_snapshot(candidate)
    manifest = read_manifest(work_root, lab_id)
    manifest["scene_style"] = saved
    manifest["hook_caption_mode"] = "hidden"
    write_manifest(lab_dir(work_root, lab_id), manifest)
    return saved
