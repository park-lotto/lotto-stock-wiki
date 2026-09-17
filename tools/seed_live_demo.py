"""라이브에서 뽑아온 실제 작업 1건으로 로컬 데모 DB를 만든다.

장면꾸미기(숏템메이커)를 **진짜 사진·자막**으로 보기 위한 로컬 전용 도구다.
합성 QA 데이터(.tmp/scene-style-qa)는 자막이 "첫 번째 자막 자리"라 실제 모습이 안 보인다.

전제: tools/pull_live_demo 로 아래가 이미 내려와 있어야 한다.
  .tmp/live-demo/job_export.json              ← mix_jobs 행 1개 (customer_id=0으로 바꿔서)
  .tmp/live-demo/mix_jobs/<job_id>/           ← 그 작업의 미디어(s0~sN·tts·beatframes)

tts_path·소스 경로는 서버 절대경로로 저장돼 있으므로 로컬 경로로 다시 쓴다.
"""
import json
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

WORK = BASE / '.tmp/live-demo'
EXPORT = WORK / 'job_export.json'
DB = WORK / 'demo.db'
SERVER_ROOT = '/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs'


def _relocate(obj, job_id):
    """서버 절대경로를 로컬 .tmp/live-demo/mix_jobs/<job> 아래로 다시 쓴다."""
    local_root = str((WORK / 'mix_jobs').resolve()).replace('\\', '/')
    if isinstance(obj, str):
        return obj.replace(SERVER_ROOT, local_root)
    if isinstance(obj, list):
        return [_relocate(x, job_id) for x in obj]
    if isinstance(obj, dict):
        return {k: _relocate(v, job_id) for k, v in obj.items()}
    return obj


def main():
    if not EXPORT.exists():
        raise SystemExit(f'{EXPORT} 가 없다 — 먼저 라이브에서 내려받아라')
    row = json.loads(EXPORT.read_text(encoding='utf-8'))
    job_id = row['job_id']
    media = WORK / 'mix_jobs' / job_id
    if not media.exists():
        raise SystemExit(f'{media} 가 없다 — 미디어를 먼저 내려받아라')

    # 경로가 박힌 컬럼만 다시 쓴다(edit_plan의 tts_path가 핵심).
    for col in ('edit_plan_json', 'clean_sources_json', 'candidates_json',
                'video_path', 'clean_video_path', 'preview_path', 'fx_path'):
        v = row.get(col)
        if not v:
            continue
        if col.endswith('_json'):
            row[col] = json.dumps(_relocate(json.loads(v), job_id), ensure_ascii=False)
        else:
            row[col] = _relocate(v, job_id)

    if DB.exists():
        DB.unlink()
    # 스키마는 앱이 직접 만들게 한다 — 손으로 적으면 실제와 어긋난다(0순위-B).
    from shopping_shorts.store import Store
    Store(str(DB))

    con = sqlite3.connect(DB)
    cols = [r[1] for r in con.execute('pragma table_info(mix_jobs)')]
    use = [c for c in cols if c in row]
    con.execute(f"insert into mix_jobs ({','.join(use)}) values ({','.join('?' * len(use))})",
                [row[c] for c in use])
    con.commit()

    plan = json.loads(row['edit_plan_json'])
    beats = plan.get('beats') or []
    missing = [b['beat_idx'] for b in beats
               if not Path(b.get('tts_path') or '').exists()]
    print(json.dumps({
        'db': str(DB), 'job_id': job_id, 'beats': len(beats),
        'tts_missing': missing,
        'narration_0': (beats[0].get('narration') or '')[:40] if beats else '',
    }, ensure_ascii=False))
    if missing:
        raise SystemExit(f'tts 파일 없음: beat {missing} — 장면꾸미기가 409로 막힌다')


if __name__ == '__main__':
    main()
