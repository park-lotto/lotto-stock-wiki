"""
Remotion 제작 직원 + 영상 검수 직원
- 대본 화면설명 → 씬별 TSX 파일 자동 생성
- tsc 에러 자동 수정 (최대 3회)
"""
import re, json, subprocess
from pathlib import Path
from . import gemini_client as G

ROOT      = Path(__file__).parent.parent.parent
REMOTION  = ROOT / 'remotion-stock'
SRC_AGENTS= REMOTION / 'src' / 'agents'
ROOT_TSX  = REMOTION / 'src' / 'Root.tsx'

# ── BRAIN SIGNAL 스타일 핵심 요약 (프롬프트 삽입용) ─────────────────
STYLE_SNIPPET = """
=== BRAIN SIGNAL 스타일 규칙 ===
배경: #080c14 / 포인트: C.main=#00FFD0(민트) / 보조: #FFA502(앰버) #FF4757(레드)
FONT = 문자열 상수 (FONT.bold 같은 속성 없음 — 그냥 FONT 사용)
숫자 폰트: "Consolas","Menlo",monospace

공통 헬퍼 (모든 씬에 복사):
function ip(f: number, a: number, b: number, from=0, to=1, ease=(t:number)=>t) {
  return interpolate(f,[a,b],[from,to],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:ease});
}

⚠️ Easing 팩토리 함수 주의 — 반드시 파라미터를 넣어 호출해야 함:
  올바름: Easing.out(Easing.back(1.7))   ← back(1.7) 호출해서 함수 전달
  올바름: Easing.out(Easing.elastic(1))  ← elastic(1) 호출해서 함수 전달
  올바름: Easing.out(Easing.poly(4))     ← poly(4) 호출해서 함수 전달
  잘못됨: Easing.out(Easing.back)        ← back 자체는 팩토리, 타입 에러!

⚠️ JSX style 속성 — 각 속성은 반드시 별도 키로 분리:
  올바름: style={{ textShadow: dynGlow, opacity: glowOp }}
  잘못됨: style={{ textShadow: dynopacity: glowOp }}  ← 합치면 문법 에러!

자막바 (모든 씬 필수):
<div style={{position:'absolute',bottom:0,left:0,right:0,height:'16%',
  display:'flex',alignItems:'center',justifyContent:'center',paddingInline:80,
  background:'linear-gradient(to top,rgba(8,12,20,0.88) 0%,transparent 100%)'}}>
  {sub&&<div style={{color:'#FFF',fontSize:40,fontWeight:700,textAlign:'center',
    opacity:sub.op,textShadow:'0 2px 8px rgba(0,0,0,0.9)'}}>{sub.text}</div>}
</div>

Phase 전환 원칙: 1씬 내 최소 2~3개 Phase / 정적 5초 이상 금지
dynGlow = `0 0 ${gSz}px #00FFD0, 0 0 ${gSz*2}px rgba(0,255,208,0.5)`

⚠️ import 규칙 — 실제 사용하는 것만 import (미사용 시 컴파일 에러):
import { AbsoluteFill, Easing, Html5Audio, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT } from '../constants';  // C 미사용이면 FONT만, GLOW는 import 금지
"""

# ── 예시 컴포넌트 (few-shot) ─────────────────────────────────────────
def _load_example() -> str:
    ex = SRC_AGENTS / 'AG_S03_Declaration.tsx'
    if ex.exists():
        return f"=== 참고 컴포넌트 예시 (AG_S03_Declaration.tsx) ===\n{ex.read_text(encoding='utf-8')[:3000]}"
    return ''

REMOTION_SYSTEM = """당신은 Remotion (React) 영상 컴포넌트 전문 개발자입니다.
대본의 화면 설명을 읽고 BRAIN SIGNAL 스타일로 TSX 컴포넌트를 작성하세요.

규칙:
- export const {컴포넌트명}: React.FC = () => {{ ... }} 형태
- Html5Audio src=staticFile('voice/{씬파일명}.m4a') 항상 포함
- SUBS 배열: 녹음 전이므로 추정 타이밍 사용 (Whisper 싱크 후 교체)
- TypeScript 에러 없이 컴파일 가능해야 함
- padStart 대신 h < 10 ? '0'+h : ''+h 사용
- React import 불필요 (새 JSX 변환)
- 파일 첫 줄: // {컴포넌트명} — {씬명} ({추정프레임}프레임 / {추정초}초)

출력: TSX 코드만 (마크다운 코드블록 없이)
"""

def _parse_scenes(script_text: str) -> list[dict]:
    """대본에서 씬 목록 추출"""
    scenes = []
    pattern = re.compile(r'##\s*씬\s*(\d+[\-\d]*)\s*[—–-]\s*([^\n(]+)(?:\(([^)]+)\))?', re.M)
    for m in pattern.finditer(script_text):
        num  = m.group(1).strip()
        name = m.group(2).strip()
        dur  = m.group(3).strip() if m.group(3) else '30초'
        # 해당 씬 블록 추출
        start = m.start()
        next_m = pattern.search(script_text, m.end())
        end = next_m.start() if next_m else len(script_text)
        block = script_text[start:end]
        scenes.append({'num': num, 'name': name, 'duration': dur, 'block': block})
    return scenes

SCENE_NAME_MAP = {
    '훅': 'Hook', '공감': 'Empathy', '선언': 'Declaration',
    '데모': 'Demo', '클라이맥스': 'Climax', '자각': 'Awareness',
    '여운': 'Tease', 'CTA': 'CTA', '소개': 'Intro',
    '브리핑': 'Brief', '배포': 'Deploy', '수집': 'Collect',
}

def _scene_to_component_name(prefix: str, num: str, name: str) -> str:
    """씬 → 컴포넌트명 (영문만, 예: YT_AI10_S01_Hook)"""
    num_clean = num.replace('-', '_')
    # 한글 → 영문 매핑 우선
    name_en = name.strip()
    for kr, en in SCENE_NAME_MAP.items():
        if kr in name_en:
            name_en = en
            break
    else:
        # 매핑 없으면 한글 제거 후 영문/숫자만
        name_en = re.sub(r'[^a-zA-Z0-9]', '', name_en)[:10] or f"S{num_clean}"
    return f"{prefix}_S{num_clean.zfill(2)}_{name_en}"

def _sec_from_duration(dur_str: str) -> int:
    """"20~30초" → 25 (중간값)"""
    nums = re.findall(r'\d+', dur_str)
    if len(nums) >= 2:
        return (int(nums[0]) + int(nums[1])) // 2
    if len(nums) == 1:
        return int(nums[0])
    return 30

def _run_tsc() -> str:
    """tsc --noEmit 실행 → 에러 문자열 반환 (없으면 '')"""
    try:
        r = subprocess.run(
            ['npx', 'tsc', '--noEmit'],
            cwd=str(REMOTION), capture_output=True, text=True, timeout=60,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return str(e)

def generate_scene(scene: dict, prefix: str, feedback: str = '') -> tuple[str, str]:
    """씬 1개 TSX 생성 → (컴포넌트명, tsx코드)"""
    comp_name = _scene_to_component_name(prefix, scene['num'], scene['name'])
    sec = _sec_from_duration(scene['duration'])
    frames = sec * 30 + 30
    # ASCII only — 한글 있으면 URL 인코딩 후 404 에러
    voice_file = re.sub(r'[^a-z0-9_]', '', comp_name.lower()) + '.m4a'

    example = _load_example()
    fb_note = f"\n\n이전 TypeScript 에러 (반드시 수정):\n{feedback}" if feedback else ''

    prompt = f"""{STYLE_SNIPPET}

{example}

=== 생성할 씬 ===
컴포넌트명: {comp_name}
음성 파일: voice/{voice_file}
추정 시간: {sec}초 ({frames}프레임)

씬 내용:
{scene['block']}
{fb_note}

위 씬의 TSX 컴포넌트를 작성하세요. 코드만 출력하세요."""

    code = G.call(prompt, REMOTION_SYSTEM, temperature=0.4)
    # 코드블록 제거
    code = re.sub(r'^```(?:tsx?|typescript)?\s*\n?', '', code, flags=re.M)
    code = re.sub(r'\n?```\s*$', '', code, flags=re.M).strip()
    return comp_name, code

def write_scene_file(comp_name: str, code: str) -> Path:
    """TSX 파일 저장"""
    path = SRC_AGENTS / f"{comp_name}.tsx"
    path.write_text(code, encoding='utf-8')
    return path

def register_in_root(comp_name: str, frames: int):
    """Root.tsx에 import + Composition 추가"""
    import re as _re
    root_text = ROOT_TSX.read_text(encoding='utf-8')
    import_line = f"import {{ {comp_name} }} from './agents/{comp_name}';"
    # ID: 한글/특수문자 제거, 영문+숫자+-만 허용
    comp_id = _re.sub(r'[^a-zA-Z0-9\-]', '', comp_name.replace('_', '-'))
    comp_line = f'      <Composition id="{comp_id}" component={{{comp_name}}} durationInFrames={{{frames}}} fps={{30}} width={{1920}} height={{1080}} />'

    if import_line in root_text:
        return  # 이미 등록됨

    # import 삽입 (마지막 agents import 뒤)
    root_text = root_text.replace(
        "import { GB01_Hook }",
        f"{import_line}\nimport {{ GB01_Hook }}"
    )
    # Composition 삽입 (GB01 앞)
    root_text = root_text.replace(
        "      {/* ─── 국민성장펀드",
        f"{comp_line}\n\n      {{/* ─── 국민성장펀드"
    )
    ROOT_TSX.write_text(root_text, encoding='utf-8')

def run(script_text: str, pipeline_dir: Path, prefix: str, feedback: str = '') -> dict:
    """전체 씬 생성 → {scenes: [...], files: [...]}"""
    scenes = _parse_scenes(script_text)
    if not scenes:
        raise ValueError("대본에서 씬을 파싱할 수 없음 — '## 씬 N — 씬명' 형식 확인")

    result = {'scenes': [], 'files': []}
    for scene in scenes:
        print(f"    🎬 씬 {scene['num']} ({scene['name']}) 코드 생성 중...")
        sec = _sec_from_duration(scene['duration'])
        frames = sec * 30 + 30

        comp_name, code = generate_scene(scene, prefix, feedback)

        # 자동 수정 루프 (TypeScript 에러)
        for attempt in range(3):
            f_path = write_scene_file(comp_name, code)
            tsc_errors = _run_tsc()
            scene_errors = [l for l in tsc_errors.splitlines() if comp_name in l]
            if not scene_errors:
                break
            print(f"    ⚠️ TSC 에러 {len(scene_errors)}개 → 자동 수정 중 ({attempt+1}/3)...")
            _, code = generate_scene(scene, prefix, feedback='\n'.join(scene_errors[:10]))
        else:
            print(f"    ❌ 씬 {scene['num']} TSC 에러 지속 — 계속 진행")

        register_in_root(comp_name, frames)
        result['scenes'].append({'num': scene['num'], 'name': scene['name'], 'comp': comp_name})
        result['files'].append(str(f_path))

    return result

def qc_technical(scene_files: list[str]) -> dict:
    """기술 검수: tsc + 파일 존재 + voice 파일 체크 + placeholder 자동 생성"""
    import subprocess as _sp
    issues = []
    VOICE_DIR = REMOTION / 'public' / 'voice'

    # 1. TSX 파일 존재 확인
    for f in scene_files:
        if not Path(f).exists():
            issues.append(f"TSX 파일 없음: {f}")

    # 2. voice 파일 존재 확인 + 없으면 자동 placeholder 생성
    for f in scene_files:
        p = Path(f)
        if not p.exists():
            continue
        code = p.read_text(encoding='utf-8')
        import re as _re
        # staticFile('voice/xxx.m4a') 패턴 추출
        matches = _re.findall(r"staticFile\(['\"]voice/([^'\"]+\.m4a)['\"]", code)
        for voice_fname in matches:
            vpath = VOICE_DIR / voice_fname
            if not vpath.exists() or vpath.stat().st_size < 100:
                # placeholder 자동 생성
                VOICE_DIR.mkdir(parents=True, exist_ok=True)
                vpath.write_bytes(
                    bytes.fromhex("0000001c667479706d703432000000006d703432697369736f6d") +
                    b"\x00" * 2048
                )
                print(f"    🔇 placeholder 생성: {voice_fname}")

    # 3. TypeScript 컴파일
    tsc_out = _run_tsc()
    tsc_errors = [l for l in tsc_out.splitlines() if 'error TS' in l]
    if tsc_errors:
        issues.extend(tsc_errors[:5])

    # 4. Composition ID에 한글 없는지 확인
    root_text = ROOT_TSX.read_text(encoding='utf-8') if ROOT_TSX.exists() else ''
    import re as _re2
    bad_ids = _re2.findall(r'id="([^"]*[가-힣][^"]*)"', root_text)
    if bad_ids:
        issues.append(f"Composition ID에 한글 포함: {bad_ids} → 영문으로 교체 필요")

    return {
        'passed': len(issues) == 0,
        'issues': issues,
        'tsc_clean': len(tsc_errors) == 0,
    }

def qc_creative(script_text: str, scene_files: list[str]) -> dict:
    """연출 검수: AI가 코드 읽고 판단"""
    codes = []
    for f in scene_files[:3]:  # 처음 3개만 샘플링
        p = Path(f)
        if p.exists():
            codes.append(f"=== {p.name} ===\n{p.read_text(encoding='utf-8')[:1500]}")

    system = """Remotion 영상 QC 전문가. 주관 금지. 코드에서 직접 확인 가능한 항목만 채점.

채점 (각 1점):
1. has_subtitle: 모든 씬 코드에 SUBS 배열과 하단 자막 div 있는가
2. has_fade_in: 모든 씬에 ip(f, 0, 18) fadeIn 있는가
3. has_audio: 모든 씬에 Html5Audio 태그 있는가
4. has_phase: 각 씬에 Phase 구분 주석 또는 분기 2개 이상 있는가
5. mint_color: C.main (#00FFD0) 포인트 컬러 사용됐는가
6. has_emoji: 이모지 3개 이상 사용됐는가
7. climax_elastic: 클라이맥스 씬에 Easing.elastic 있는가
8. dark_bg: 배경이 #080c14 계열 다크인가

반환:
{
  "scores": {"has_subtitle":1, "has_fade_in":0, ...},
  "total": 6,
  "passed": true,
  "feedback": "실패: has_fade_in — 씬3에 fadeIn 없음. opacity: ip(f, 0, 18) 추가 필요.",
  "weak_scenes": ["씬3: fadeIn 누락"]
}
passed = total >= 6"""

    prompt = f"대본 (요약):\n{script_text[:500]}\n\n씬 코드 샘플:\n{''.join(codes)}\n\n채점하세요."
    return G.call_json(prompt, system)
