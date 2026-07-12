"""믹스 job 백그라운드 오케스트레이션(설계 §2·§5).

run_mix_job: 다운로드→대본추출(병렬)→EDL생성→TTS까지 진행하고 ready_for_review로.
run_render: 사용자가 확인 후 최종 ffmpeg 렌더 → done.
각 단계에서 mix_jobs.status를 갱신하고, 예외는 status='failed'+error로 잡는다.
"""
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from shopping_shorts.store import Store
from shopping_shorts.frame_extract import download_video
from shopping_shorts.script_extract import extract_script
from shopping_shorts.edit_plan import build_edit_plan
from shopping_shorts.tts import synthesize_tts
from shopping_shorts.video_assemble import assemble


def _source_video_id(i):
    return f"s{i}"


def run_mix_job(job_id, db_path, work_root):
    """다운로드→추출→EDL→TTS. 완료 시 status='ready_for_review'."""
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job:
        return
    work = Path(work_root) / job_id
    work.mkdir(parents=True, exist_ok=True)
    try:
        # 1) 다운로드
        store.update_mix_job(job_id, status="downloading")
        video_paths = {}   # video_id -> mp4 path
        for i, url in enumerate(job["urls"]):
            vid = _source_video_id(i)
            d = work / vid
            d.mkdir(parents=True, exist_ok=True)
            video_paths[vid] = str(download_video(url, d))

        # 2) 대본 추출(병렬)
        store.update_mix_job(job_id, status="extracting")
        def _extract(item):
            vid, path = item
            r = extract_script(path, vid)
            r["video_id"] = vid
            return vid, r
        with ThreadPoolExecutor(max_workers=max(1, len(video_paths))) as ex:
            extracts = dict(ex.map(_extract, video_paths.items()))
        store.update_mix_job(job_id, extract=extracts)

        # 3) 통합 EDL
        store.update_mix_job(job_id, status="planning")
        source_scripts = list(extracts.values())
        plan = build_edit_plan(source_scripts, job["target_seconds"], structure=job["structure"])
        # 빈 EDL(추출 전량 실패 또는 파이프라인 중간 전용풀 소진)을 ready_for_review로
        # 오보고하지 않는다 — 성공처럼 보이는 빈 리뷰화면 대신 즉시 실패로 정상 종료
        # (2026-07-12 최종 전체리뷰 Important).
        if not plan["beats"]:
            raise RuntimeError("EDL 비어있음 — 대본 추출 실패 또는 Gemini 키 소진으로 편집안을 만들지 못함")

        # 4) 비트별 TTS
        store.update_mix_job(job_id, status="tts")
        tts_dir = work / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)
        for beat in plan["beats"]:
            out = tts_dir / f"beat_{beat['beat_idx']}.mp3"
            synthesize_tts(beat["narration"], str(out))
            beat["tts_path"] = str(out)

        store.update_mix_job(job_id, edit_plan=plan, status="ready_for_review")
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))


def run_render(job_id, db_path, work_root):
    """확인 완료된 EDL을 최종 mp4로 렌더. 완료 시 status='done'+video_path."""
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return
    work = Path(work_root) / job_id
    try:
        store.update_mix_job(job_id, status="rendering")
        plan = job["edit_plan"]
        tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
        # 다운로드된 소스 재사용
        source_video_paths = {}
        for i in range(len(job["urls"])):
            vid = _source_video_id(i)
            mp4 = next((work / vid).glob("*.mp4"), None)
            if mp4 is None:
                raise RuntimeError(f"소스 영상 없음: {vid} (다운로드 디렉터리에 mp4 없음)")
            source_video_paths[vid] = str(mp4)
        out_path = work / "final.mp4"
        assemble(plan, tts_paths, source_video_paths, str(out_path))
        store.update_mix_job(job_id, status="done", video_path=str(out_path))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))
