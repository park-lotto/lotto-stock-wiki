"""제작소 최종물 → 캡컷 편집용 에셋 번들 (설계 2026-07-20 §2, T1).

웹앱이라 캡컷 자동실행/로컬 폴더쓰기는 불가 → 다운로드 ZIP과 SRT를 만든다.
비트 타임라인(video_assemble._beat_timeline)을 **단일 출처**로 SRT·스크립트를 만들고,
비트별 primary 구간을 잘라 sources/에 담는다(캡컷에서 장면 순서대로 재배열·편집).

없는 재료(소스 mp4 없음·SEO 없음·최종렌더 전)는 **조용히 건너뛴다** — 내보내기는 렌더 전에도
가능해야 하고, 하나 없다고 500을 내지 않는다(설계 §6). 무엇이 빠졌는지는 README가 알린다.
"""
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# zip에 담을 구성요소 키. 개별 다운로드(?part=)는 이 중 일부만 켠다.
ALL_PARTS = ("final", "sources", "tts", "srt", "script", "seo")

_README = """캡컷에서 편집하는 법

1. sources 폴더의 장면 영상들을 번호 순서(beat_00, beat_01 ...)대로 타임라인에 올리세요.
2. tts 폴더의 음성을 같은 순서로 오디오 트랙에 올리세요.
3. captions.srt 를 자막으로 가져오면 대사가 타이밍대로 들어갑니다.

* final.mp4 는 제작소가 만든 완성본입니다(참고용).
* script.txt 는 장면별 대본 전문, seo.txt 는 제목·태그입니다.
"""


def _srt_ts(sec):
    """초 → SRT 타임스탬프 'HH:MM:SS,mmm'. 음수는 0으로."""
    ms = int(round(max(0.0, float(sec)) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(timeline):
    """_beat_timeline 결과 → SRT 문자열(비트 단위 큐). narration 빈 비트는 건너뛴다.

    편집 목적엔 씬(비트) 단위 자막이 유리하므로 구절 분할 대신 비트당 1큐로 둔다.
    타이밍은 렌더와 같은 t0·dur(콘폼·여운 반영값)를 그대로 써 어긋나지 않는다."""
    out, n = [], 0
    for b in timeline:
        text = (b.get("narration") or "").strip()
        if not text:
            continue
        n += 1
        start = float(b.get("t0", 0.0))
        end = start + float(b.get("dur", 0.0))
        out += [str(n), f"{_srt_ts(start)} --> {_srt_ts(end)}", text, ""]
    return "\n".join(out)


def build_script_text(timeline):
    """비트별 '[역할] 나레이션' 전문."""
    lines = []
    for b in timeline:
        text = (b.get("narration") or "").strip()
        if not text:
            continue
        role = (b.get("role") or "").strip()
        lines.append(f"[{role}] {text}" if role else text)
    return "\n\n".join(lines)


def build_seo_text(seo):
    """SEO dict(제목·설명·태그) → 텍스트. 없으면 빈 문자열."""
    if not seo:
        return ""
    parts = []
    if seo.get("title"):
        parts.append("[제목]\n" + str(seo["title"]).strip())
    if seo.get("description"):
        parts.append("[설명]\n" + str(seo["description"]).strip())
    tags = seo.get("tags") or seo.get("hashtags")
    if tags:
        if isinstance(tags, (list, tuple)):
            tags = " ".join(str(t) for t in tags)
        parts.append("[태그]\n" + str(tags).strip())
    return "\n\n".join(parts)


def safe_name(s, default="export"):
    """파일명 안전화 — 영숫자·공백·_- 만 남기고 60자 제한."""
    s = "".join(c for c in (s or "") if c.isalnum() or c in " _-").strip()
    return (s or default)[:60]


def _cut_clip(src, start, end, out_path):
    """소스에서 [start,end] 구간을 잘라 out_path(mp4)로. 프레임 정확 재인코딩(짧은 클립).
    실패하면 예외를 삼키고 False — 한 클립 실패가 번들 전체를 막지 않는다."""
    dur = max(0.1, float(end) - float(start))
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{float(start):.3f}", "-i", str(src),
             "-t", f"{dur:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
             "-r", "30", str(out_path)],
            check=True, capture_output=True, stdin=subprocess.DEVNULL)
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def _beat_source_clips(plan, timeline, source_video_paths, out_dir):
    """비트별 primary 구간을 잘라 out_dir/beat_NN_<역할>.mp4 로. 잘린 경로 리스트 반환.
    소스 mp4가 없는(스킵된) 비트는 조용히 건너뛴다(_resolve_sources 스킵 일관성)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    beats_by_idx = {b["beat_idx"]: b for b in plan.get("beats", [])}
    clips = []
    for b in timeline:
        beat = beats_by_idx.get(b["beat_idx"])
        prim = (beat or {}).get("primary") or {}
        src = source_video_paths.get(prim.get("video_id"))
        if not src or prim.get("start") is None or prim.get("end") is None:
            continue
        role = safe_name(b.get("role") or "", default="scene")
        out = out_dir / f"beat_{b['beat_idx']:02d}_{role}.mp4"
        if _cut_clip(src, prim["start"], prim["end"], out):
            clips.append(out)
    return clips


def build_export_zip(out_zip, *, plan, timeline, source_video_paths, tts_paths,
                     final_video=None, seo=None, parts=ALL_PARTS):
    """캡컷 편집용 ZIP을 out_zip 경로에 쓴다. parts로 담을 구성요소를 고른다(개별 다운로드용).
    없는 재료는 건너뛴다. 반환: zip에 담긴 arcname 리스트(테스트·로깅용)."""
    parts = set(parts)
    written = []
    tmp = Path(tempfile.mkdtemp(prefix="export_"))
    try:
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            def _add(path, arc):
                zf.write(path, arc)
                written.append(arc)

            def _add_text(text, arc):
                zf.writestr(arc, text.encode("utf-8"))
                written.append(arc)

            if "final" in parts and final_video and Path(final_video).exists():
                _add(final_video, "final.mp4")
            if "sources" in parts:
                for clip in _beat_source_clips(plan, timeline, source_video_paths, tmp / "sources"):
                    _add(clip, f"sources/{clip.name}")
            if "tts" in parts:
                for idx, tp in sorted(tts_paths.items()):
                    if tp and Path(tp).exists():
                        _add(tp, f"tts/beat_{idx:02d}.mp3")
            if "srt" in parts:
                srt = build_srt(timeline)
                if srt.strip():
                    _add_text(srt, "captions.srt")
            if "script" in parts:
                script = build_script_text(timeline)
                if script.strip():
                    _add_text(script, "script.txt")
            if "seo" in parts:
                seo_txt = build_seo_text(seo)
                if seo_txt.strip():
                    _add_text(seo_txt, "seo.txt")
            # README는 항상(전체 번들일 때) — 개별 다운로드엔 불필요
            if parts == set(ALL_PARTS):
                _add_text(_README, "README.txt")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return written
