"""
렌더링 + 배포 직원 + 배포 검수 직원
"""
import subprocess, time, re
from pathlib import Path

ROOT     = Path(__file__).parent.parent.parent
REMOTION = ROOT / 'remotion-stock'
OUT_DIR  = ROOT / 'out'

def run(composition_ids: list[str], output_name: str, pipeline_dir: Path) -> dict:
    """씬별 렌더 → 파일 리스트 반환"""
    rendered = []

    for comp_id in composition_ids:
        out_file = pipeline_dir / f"{comp_id}.mp4"
        print(f"    🎞 렌더링: {comp_id} → {out_file.name}")

        cmd = [
            'npx', 'remotion', 'render',
            comp_id,
            str(out_file),
            '--log=error',
        ]
        r = subprocess.run(
            cmd, cwd=str(REMOTION),
            capture_output=True, text=True, timeout=300,
            creationflags=0x08000000,
        )

        if r.returncode == 0:
            print(f"    ✓ {comp_id} 렌더 완료 ({out_file.stat().st_size // 1024 // 1024}MB)")
            rendered.append({'comp': comp_id, 'file': str(out_file), 'ok': True})
        else:
            err = (r.stdout + r.stderr).strip()[-300:]
            print(f"    ❌ {comp_id} 렌더 실패: {err}")
            rendered.append({'comp': comp_id, 'error': err, 'ok': False})

    return {'rendered': rendered}

def qc(render_result: dict) -> dict:
    """렌더 품질 체크"""
    issues = []
    for r in render_result.get('rendered', []):
        if not r['ok']:
            issues.append(f"{r['comp']}: 렌더 실패 — {r.get('error','')[:100]}")
            continue
        p = Path(r['file'])
        if not p.exists():
            issues.append(f"{r['comp']}: 출력 파일 없음")
            continue
        size_mb = p.stat().st_size / 1024 / 1024
        if size_mb < 0.1:
            issues.append(f"{r['comp']}: 파일 크기 너무 작음 ({size_mb:.1f}MB)")

    passed_count = sum(1 for r in render_result.get('rendered', []) if r['ok'])
    total_count  = len(render_result.get('rendered', []))

    return {
        'passed': len(issues) == 0,
        'issues': issues,
        'rendered_ok': f"{passed_count}/{total_count}",
    }

def open_studio():
    """Remotion Studio 열기 (미리보기)"""
    subprocess.Popen(
        ['npm', 'run', 'dev'],
        cwd=str(REMOTION),
        creationflags=0x08000000,
    )
    print("    🎬 Remotion Studio 열리는 중... (localhost:3000)")
