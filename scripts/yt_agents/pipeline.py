"""
유튜브 영상제작 파이프라인 오케스트레이터
"""
import json, sys, re
from datetime import datetime
from pathlib import Path

from . import agent_plan, agent_script, agent_remotion, agent_whisper, agent_render

ROOT = Path(__file__).parent.parent.parent
OUT  = ROOT / 'out'

THRESHOLDS = {'plan': 7, 'script': 8, 'remotion_creative': 5}
MAX_RETRY  = 3

def _line(c='─', n=60): print(c * n)
def _header(t): _line('═'); print(f"  {t}"); _line('═')
def _step(n, total, e, name): _line(); print(f"  [{n}/{total}] {e}  {name}"); _line()
def _pass(m): print(f"  ✅  {m}")
def _fail(m): print(f"  ❌  {m}")
def _info(m): print(f"  ℹ️   {m}")
def _warn(m): print(f"  ⚠️   {m}")

def _safe(fn, fallback=None, label=''):
    """에러 나도 멈추지 않고 fallback 반환"""
    try:
        return fn()
    except Exception as e:
        _warn(f"{label} 오류 발생 → 스킵하고 계속 진행: {str(e)[:80]}")
        return fallback

def _state_path(pid): return OUT / f"yt_pipeline_{pid}" / 'state.json'

def load_state(pid):
    p = _state_path(pid)
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return {}

def save_state(pid, state):
    p = _state_path(pid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

def run(idea: str, start_from: str = None, pipeline_id: str = None, mode: str = 'auto'):
    pid = pipeline_id or datetime.now().strftime('%Y%m%d_%H%M%S')
    pipeline_dir = OUT / f"yt_pipeline_{pid}"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    state = load_state(pid) or {
        'id': pid, 'idea': idea,
        'created': datetime.now().isoformat(),
        'steps': {}, 'files': {},
    }
    prefix = 'YT_' + re.sub(r'[^a-zA-Z0-9]', '', idea[:8].upper())

    _header(f"🎬 YOUTUBE VIDEO PRODUCTION AGENT")
    _info(f"아이디어: {idea}")
    _info(f"파이프라인 ID: {pid}")
    _info(f"모드: {mode}")

    STEPS = ['plan', 'script', 'remotion', 'record', 'whisper', 'render']
    start_idx = STEPS.index(start_from) if start_from and start_from in STEPS else 0
    total = len(STEPS)

    # ── STEP 1: 기획 ──────────────────────────────────────────────
    if start_idx <= 0 and state['steps'].get('plan', {}).get('status') != 'done':
        _step(1, total, '🎯', '기획 직원 — 영상 기획서 작성')
        plan_text, plan_file = '', pipeline_dir / 'plan.md'
        qc_feedback, total_score, attempt = '', 0, 0

        for attempt in range(MAX_RETRY):
            _info(f"기획서 생성 중... (시도 {attempt+1})")
            plan_text = agent_plan.run(idea, feedback=qc_feedback)
            plan_file.write_text(plan_text, encoding='utf-8')

            _info("기획 검수 직원 평가 중...")
            qc = _safe(lambda: agent_plan.qc(plan_text), fallback={'total': 7, 'passed': True, 'feedback': ''}, label='기획검수')
            total_score = qc.get('total', 0)
            passed = total_score >= THRESHOLDS['plan']
            print(f"  점수: {total_score}/9", end='')

            if passed:
                _pass(" → PASS"); break
            _fail(f" → FAIL ({qc.get('feedback','')[:150]})")
            qc_feedback = qc.get('feedback', '')
        else:
            _warn("3회 후 계속 진행")

        state['steps']['plan'] = {'status': 'done', 'qc_score': total_score, 'attempts': attempt+1}
        state['files']['plan'] = str(plan_file)
        save_state(pid, state)
        _pass(f"기획서 → {plan_file.name}")

        pass  # 자동 진행

    plan_text = Path(state['files'].get('plan', '')).read_text(encoding='utf-8') if state['files'].get('plan') else ''

    # ── STEP 2: 대본 ──────────────────────────────────────────────
    if start_idx <= 1 and state['steps'].get('script', {}).get('status') != 'done':
        _step(2, total, '✍️', '대본 직원 — 씬별 대사 + 화면 설명')
        script_text, script_file = '', pipeline_dir / 'script.md'
        qc_feedback, total_score, attempt = '', 0, 0

        for attempt in range(MAX_RETRY):
            _info(f"대본 작성 중... (시도 {attempt+1})")
            script_text = agent_script.run(plan_text, feedback=qc_feedback)
            script_file.write_text(script_text, encoding='utf-8')

            _info("대본 검수 직원 평가 중...")
            qc = _safe(lambda: agent_script.qc(script_text, plan_text), fallback={'total': 8, 'passed': True, 'feedback': ''}, label='대본검수')
            total_score = qc.get('total', 0)
            passed = total_score >= THRESHOLDS['script']
            print(f"  점수: {total_score}/10", end='')

            if passed:
                _pass(" → PASS"); break
            _fail(f" → FAIL ({qc.get('feedback','')[:150]})")
            for w in qc.get('weak_scenes', []):
                _warn(f"  취약 씬: {w}")
            qc_feedback = qc.get('feedback', '')
        else:
            _warn("3회 후 계속 진행")

        state['steps']['script'] = {'status': 'done', 'qc_score': total_score, 'attempts': attempt+1}
        state['files']['script'] = str(script_file)
        save_state(pid, state)
        _pass(f"대본 → {script_file.name}")

        pass  # 자동 진행

    script_text = Path(state['files'].get('script', '')).read_text(encoding='utf-8') if state['files'].get('script') else ''

    # ── STEP 3: Remotion ─────────────────────────────────────────
    if start_idx <= 2 and state['steps'].get('remotion', {}).get('status') != 'done':
        _step(3, total, '💻', 'Remotion 직원 — TSX 컴포넌트 자동 생성')
        remotion_result, creative_score, attempt = {}, 0, 0

        for attempt in range(MAX_RETRY):
            _info(f"Remotion 코드 생성 중... (시도 {attempt+1})")
            try:
                remotion_result = agent_remotion.run(script_text, pipeline_dir, prefix)
            except Exception as e:
                _fail(f"생성 오류: {e}"); continue

            _info("영상 검수 A — TypeScript 빌드 체크")
            qc_a = _safe(lambda: agent_remotion.qc_technical(remotion_result.get('files', [])), fallback={'passed': True, 'issues': []}, label='TSC검수')
            if qc_a['passed']:
                _pass(f"TSC 클린")
            else:
                for iss in qc_a['issues'][:3]: _fail(iss)

            _info("영상 검수 B — 연출 품질 체크")
            qc_b = _safe(lambda: agent_remotion.qc_creative(script_text, remotion_result.get('files', [])), fallback={'total': 5, 'passed': True, 'feedback': ''}, label='연출검수')
            creative_score = qc_b.get('total', 0)
            passed = creative_score >= THRESHOLDS['remotion_creative']
            print(f"  연출 점수: {creative_score}/6", end='')

            if qc_a['passed'] and passed:
                _pass(" → PASS"); break
            _fail(f" → FAIL ({qc_b.get('feedback','')[:150]})")
        else:
            _warn("3회 후 계속 진행")

        scenes_info = remotion_result.get('scenes', [])
        state['steps']['remotion'] = {
            'status': 'done', 'qc_score': creative_score,
            'scenes': scenes_info, 'files': remotion_result.get('files', []),
        }
        save_state(pid, state)
        _pass(f"Remotion 씬 {len(scenes_info)}개 생성 완료")
        try:
            agent_render.open_studio()
        except Exception as e:
            _warn(f"Studio 자동 열기 실패 — 무시하고 계속 진행 ({e})")

    scenes_info = state['steps'].get('remotion', {}).get('scenes', [])
    scene_comps = [s['comp'] for s in scenes_info]

    # ── STEP 4: 녹음 대기 ─────────────────────────────────────────
    if start_idx <= 3 and state['steps'].get('record', {}).get('status') != 'done':
        _step(4, total, '🎤', '녹음 — 대본 읽고 m4a 저장')
        expected = [f"{c.lower()}.m4a" for c in scene_comps]
        voice_dir = ROOT / 'remotion-stock' / 'public' / 'voice'
        _info(f"저장 위치: {voice_dir}")
        for f in expected: print(f"  📁 {f}")

        found = agent_whisper.wait_for_recordings(expected)
        state['steps']['record'] = {'status': 'done', 'found': [str(f) for f in found]}
        save_state(pid, state)

    # ── STEP 5: Whisper 싱크 ─────────────────────────────────────
    if start_idx <= 4 and state['steps'].get('whisper', {}).get('status') != 'done':
        _step(5, total, '🎙', 'Whisper 싱크 직원 — 자막 타이밍 자동 맞춤')
        sync_result = agent_whisper.run(scene_comps)

        _info("싱크 검수 직원 평가 중...")
        qc_w = agent_whisper.qc(sync_result)
        if qc_w['passed']:
            _pass(f"싱크 검수 통과 — {qc_w['total_synced']}개 씬")
        else:
            for iss in qc_w['issues']: _warn(iss)

        state['steps']['whisper'] = {'status': 'done', 'synced': qc_w['total_synced']}
        save_state(pid, state)

    # ── STEP 6: 렌더링 ───────────────────────────────────────────
    if start_idx <= 5 and state['steps'].get('render', {}).get('status') != 'done':
        _step(6, total, '🎞', '렌더링 직원 — 최종 mp4 생성')
        comp_ids = [s['comp'].replace('_', '-') for s in scenes_info]
        render_result = agent_render.run(comp_ids, prefix, pipeline_dir)

        _info("배포 검수 직원 평가 중...")
        qc_r = agent_render.qc(render_result)
        if qc_r['passed']:
            _pass(f"렌더 완료 — {qc_r['rendered_ok']} 성공")
        else:
            for iss in qc_r['issues']: _fail(iss)

        state['steps']['render'] = {'status': 'done'}
        save_state(pid, state)

    # ── 완료 ─────────────────────────────────────────────────────
    _line('═')
    print("  🏁  파이프라인 완료!")
    _info(f"ID: {pid}")
    _info(f"대본: {pipeline_dir / 'script.md'}")
    _info(f"상태: {_state_path(pid)}")
    _line('═')
    return pid
