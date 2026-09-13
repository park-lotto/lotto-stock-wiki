"""로로의 첫 연결: 근거 기록 취합. AI 요약이나 실행 상태 판정이 아니다."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()
REPORT_DIR = Path(__file__).resolve().parent / '.artifacts' / 'rolo-reports'


def build_report(root: Path) -> str:
    source_dir = root.resolve() / 'handoff'
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    lines = ['# 로로 · 작업 기록 취합 보고서', '', f'- 생성 시각: {now}',
             '- 방식: 기록 원문 발췌 · AI 모델 미연결', f'- 읽은 저장소: {root.resolve()}',
             '- 현재 실행 상태 미확인: 기록의 완료·실패 주장을 코드/서버/결과물로 재검증하지 않았습니다.',
             '- 범위: 설정된 저장소 handoff 폴더의 최근 수정 파일 최대 10건, 파일별 앞 40줄.',
             '- 수정시각은 작업 완료시각이 아닙니다. 전체 회사·전체 프로젝트 목록이 아닙니다.',
             '- 음성·자유 대화·팀장 판단·워커 호출은 아직 연결되지 않았습니다.', '']
    files = []
    for path in source_dir.glob('*.md'):
        if path.is_symlink() or path.resolve().parent != source_dir.resolve():
            continue
        try:
            files.append((path.stat().st_mtime, path))
        except OSError:
            continue
    files.sort(key=lambda item: (-item[0], item[1].name))
    lines.append(f'- 발견한 기록 파일: {len(files)}개 / 이번 취합: {min(10, len(files))}개')
    if not files:
        lines.append('\n기록을 찾지 못했습니다. 진행 업무가 없다는 뜻이 아닙니다.')
    for modified, path in files[:10]:
        lines.extend(['', f'## {path.stem}', f'출처: handoff/{path.name}',
                      f'파일 수정시각: {datetime.fromtimestamp(modified, timezone.utc).isoformat(timespec="seconds")}', ''])
        try:
            with path.open(encoding='utf-8-sig') as handle:
                excerpt = [handle.readline(2000) for _ in range(40)]
                truncated = bool(handle.read(1))
            lines.extend('> ' + line.rstrip('\r\n') for line in excerpt if line)
            if truncated:
                lines.append('\n[이하 생략 — 전체 맥락은 원본 확인 필요]')
        except (OSError, UnicodeError):
            lines.append('읽기 실패 — 내용 미확인')
    lines.extend(['', '## 대표 확인이 필요한 범위',
                  '- 오래된 기록과 최신 실제 상태의 차이',
                  '- 보고에 포함되지 않은 프로젝트와 다른 트랙의 미커밋 작업',
                  '- 업무 담당자·검수 결과·실행 세션의 실제 연결', ''])
    return '\n'.join(lines)


@router.post('/api/rolo/reports', status_code=201)
def create_report():
    configured = os.environ.get('COMPANY_ROLO_ROOT')
    if not configured or not (Path(configured) / 'handoff').is_dir():
        return JSONResponse({'detail': '보고할 저장소가 연결되지 않았습니다.'}, status_code=503)
    content = build_report(Path(configured))
    report_id = str(uuid4())
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f'{report_id}.md').write_text(content, encoding='utf-8', newline='\n')
    return {'id': report_id, 'content': content, 'download': f'/api/rolo/reports/{report_id}'}


@router.get('/api/rolo/reports/{report_id}')
def download_report(report_id: UUID):
    path = REPORT_DIR / f'{report_id}.md'
    if not path.is_file():
        return JSONResponse({'detail': '보고서가 없습니다.'}, status_code=404)
    return FileResponse(path, media_type='text/markdown; charset=utf-8', filename=f'rolo-report-{report_id}.md')
