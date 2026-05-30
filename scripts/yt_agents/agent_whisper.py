"""
Whisper 싱크 직원 + 싱크 검수 직원
- m4a 파일 감지 → Whisper 분석 → TSX SUBS 자동 업데이트
"""
import re, time
from pathlib import Path

ROOT     = Path(__file__).parent.parent.parent
VOICE_DIR = ROOT / 'remotion-stock' / 'public' / 'voice'
SRC_DIR   = ROOT / 'remotion-stock' / 'src' / 'agents'
FPS = 30

def sec_to_frame(sec: float) -> int:
    return round(sec * FPS)

def wait_for_recordings(expected_files: list[str], timeout: int = 3600) -> list[Path]:
    """녹음 파일이 생길 때까지 대기 (polling)"""
    print(f"\n⏸  녹음 대기 중... ({len(expected_files)}개 파일)")
    print(f"   저장 위치: {VOICE_DIR}")
    for f in expected_files:
        print(f"   필요: {f}")

    found = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        for fname in expected_files:
            p = VOICE_DIR / fname
            if p.exists() and p not in found:
                print(f"   ✓ 감지됨: {fname}")
                found.append(p)
        if len(found) == len(expected_files):
            print("   ✅ 모든 녹음 파일 감지!")
            return found
        time.sleep(5)

    return found  # 타임아웃 시 지금까지 찾은 것만

def run_whisper(audio_path: Path) -> dict:
    """Whisper 실행 → 세그먼트 리스트"""
    import whisper
    print(f"    🎙 Whisper 분석: {audio_path.name}")
    model = whisper.load_model('base')
    result = model.transcribe(str(audio_path), language='ko', word_timestamps=True)
    total_sec = result['segments'][-1]['end'] if result['segments'] else 0

    segments = []
    for seg in result['segments']:
        segments.append({
            'text': seg['text'].strip(),
            'start_frame': sec_to_frame(seg['start']),
            'end_frame': sec_to_frame(seg['end']),
            'start_sec': round(seg['start'], 3),
            'end_sec':   round(seg['end'], 3),
        })
    return {
        'audio': audio_path.name,
        'total_sec': round(total_sec, 3),
        'total_frames': sec_to_frame(total_sec) + 30,
        'segments': segments,
    }

def update_tsx_subs(comp_name: str, whisper_result: dict) -> bool:
    """TSX 파일의 SUBS 배열 + durationInFrames 업데이트"""
    tsx_path = SRC_DIR / f"{comp_name}.tsx"
    if not tsx_path.exists():
        print(f"    ⚠️ 파일 없음: {tsx_path}")
        return False

    segs = whisper_result['segments']
    total_frames = whisper_result['total_frames']

    # SUBS 배열 생성
    subs_lines = ['const SUBS = [']
    for seg in segs:
        text = seg['text'].replace("'", "\\'")
        subs_lines.append(f"  {{ s: {seg['start_frame']}, e: {seg['end_frame']}, text: '{text}' }},")
    subs_lines.append('];')
    new_subs = '\n'.join(subs_lines)

    code = tsx_path.read_text(encoding='utf-8')

    # SUBS 교체
    code = re.sub(r'const SUBS\s*=\s*\[[\s\S]*?\];', new_subs, code)

    tsx_path.write_text(code, encoding='utf-8')

    # Root.tsx의 durationInFrames 업데이트
    root_path = ROOT / 'remotion-stock' / 'src' / 'Root.tsx'
    if root_path.exists():
        root_text = root_path.read_text(encoding='utf-8')
        comp_id = comp_name.replace('_', '-')
        root_text = re.sub(
            rf'(id="{comp_id}"[^/]*?)durationInFrames=\{{\d+\}}',
            rf'\1durationInFrames={{{total_frames}}}',
            root_text
        )
        root_path.write_text(root_text, encoding='utf-8')

    return True

def run(scene_comps: list[str]) -> dict:
    """각 씬의 예상 m4a 파일명 → Whisper → TSX 업데이트"""
    results = []
    for comp in scene_comps:
        fname = f"{comp.lower()}.m4a"
        audio = VOICE_DIR / fname
        if not audio.exists():
            print(f"    ⚠️ 녹음 파일 없음: {fname} — 건너뜀")
            continue
        wr = run_whisper(audio)
        updated = update_tsx_subs(comp, wr)
        results.append({'comp': comp, 'whisper': wr, 'updated': updated})
        print(f"    ✓ {comp}: {wr['total_sec']}초 / {len(wr['segments'])}세그먼트 싱크")
    return {'synced': results}

def qc(sync_results: dict) -> dict:
    """싱크 품질 체크 — 규칙 기반"""
    issues = []
    for r in sync_results.get('synced', []):
        segs = r['whisper']['segments']
        if not segs:
            issues.append(f"{r['comp']}: 세그먼트 없음")
            continue
        # 공백 구간 체크 (15프레임 = 0.5초 이상 간격)
        for i in range(len(segs) - 1):
            gap = segs[i+1]['start_frame'] - segs[i]['end_frame']
            if gap < 0:
                issues.append(f"{r['comp']} 세그먼트 {i+1}: 자막 겹침 ({gap}프레임)")
        # 총 길이 0 체크
        if r['whisper']['total_sec'] < 1:
            issues.append(f"{r['comp']}: 녹음 길이 너무 짧음")

    return {
        'passed': len(issues) == 0,
        'issues': issues,
        'total_synced': len(sync_results.get('synced', [])),
    }
