"""Pinned local ACNet runtime for source-video treatment (2026-10-05 사장님 결정 1 · Real-ESRGAN 교체).

■ 무엇 — ACNet F8B4 HDN(TianZerL/ACNetGLSL · MIT) 망을 onnxruntime 으로 돌린다 — 윈도우 DirectML 이 되면 그래픽카드,
  아니면 CPU(2026-10-19 사장님 결정 «GPU 가 있으면 최대한 활용» · 장치 판정은 onnx_providers 한 곳).
  배급하는 것은 원본 GLSL 파일 그대로(지문 고정)이고, 가중치는 그 파일에서 읽어 ONNX 그래프를
  이 모듈이 직접 짓는다(파생 모델 파일을 따로 두지 않는다 — 원본과 갈릴 자리가 없다).

■ 왜 GPU 셰이더(libplacebo/mpv)가 아닌가 (실측 · 근거는 docs/2026-10-05_롱폼-ACNet-교체.md)
  ① 같은 셰이더라도 맥 mpv ↔ 윈도우 ffmpeg libplacebo 결과가 Y PSNR 31.6dB 로 갈렸다(두 실행 경로가 다르다).
     libplacebo 가 든 맥 ffmpeg 공식 배포본은 없다(jellyfin 맥 빌드는 libplacebo 를 끈다 · Homebrew ffmpeg-full 은
     brew 설치·arm64 최근 macOS 병만 있다). 같은 경로로 두 OS 를 맞출 길이 GPU 쪽에는 없다.
  ② 맥 mpv 출력은 마지막 1장이 빠진다(249→248).
  ③ libplacebo 가 요구하는 Vulkan 판보다 낮은 드라이버(win-01 내장 그래픽)에서 실패 — 판 번호는 문서에.
  → CPU onnxruntime 은 맥·윈도우가 같은 코드·같은 그래프를 돈다(GPU·Vulkan·다운로드 불필요). 프레임은
    우리가 한 장씩 넣고 받으므로 수가 줄지 않는다. 속도는 실측표(문서)에 있다.

■ 지키는 것 — 유료 요청 없음 · 인터넷 다운로드 없음 · 망 파일은 배포 지문과 같을 때만 쓴다.
"""
from pathlib import Path
import json
import platform
import re
import struct
import atexit
import threading
from film_editor import file_digest, file_lock
from longform_state import ProductionError

MANIFEST = 'acnet.json'
SCHEMA = 'geumbit-acnet-v1'
NETWORK = 'acnet_f8b4_hdn'


def ensure_tools(assets, cache=None):
    """Return the pinned ACNet runtime description. `cache` is accepted for old call sites and unused (no download)."""
    folder = Path(assets) / 'video-treatment-models'
    try:
        manifest = json.loads((folder / MANIFEST).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ProductionError('video_tools_missing', '영상처리 망 설명(acnet.json)이 없습니다. 자산 팩을 다시 받으세요.',
                              action='repair_environment') from exc
    if manifest.get('schema') != SCHEMA or manifest.get('network') != NETWORK:
        raise ProductionError('video_tools_platform', '이 실행기가 모르는 영상처리 망입니다.', action='repair_environment')
    for name, expected in manifest['files'].items():
        if Path(name).name != name or not (folder / name).is_file() or file_digest(folder / name) != expected:
            raise ProductionError('video_model_integrity', '영상처리 망 파일이 배포 지문과 다릅니다.', action='repair_environment')
    try:
        import onnxruntime
    except ImportError as exc:
        raise ProductionError('video_runtime_missing', '영상처리에 onnxruntime 이 필요합니다(실행 환경 점검이 설치를 안내합니다).',
                              action='repair_environment') from exc
    from onnx_providers import choice
    # provider 는 처리법 열쇠에 든다 — GPU(DirectML)와 CPU 결과는 8비트 1단계까지 갈리므로 캐시·영수증을 섞지 않는다.
    return {'shader': str(folder / manifest['shader']), 'models': str(folder),
            'identity': {**manifest, 'onnxruntime': onnxruntime.__version__, 'provider': choice()}}


# ── GLSL → 가중치 ───────────────────────────────────────────────────────────
_HEAD = re.compile(r'(?m)^//!DESC ')
_BIAS = re.compile(r'vec4 result = vec4\(([^)]*)\);')
_TERM = re.compile(r'result \+= (vec4|mat4)\(([^)]*)\) \* (\w+)_texOff\(vec2\(([-0-9.]+), ([-0-9.]+)\)\)(\.x)?;')
_ACT = re.compile(r'result = max\(result, vec4\(0\.0\)\) \+ vec4\(([^)]*)\) \* min\(result, vec4\(0\.0\)\);')
_RESIDUAL = 'result = result + LUMA_texOff(vec2(0.0, 0.0)).x;'
_SHUFFLE = 'TMP2_TEX_0_tex(TMP2_TEX_0_pos + (vec2(0.5) - f0) * TMP2_TEX_0_pt)[i0.y * 2 + i0.x]'


def parse_shader(text):
    """ACNet F8B4 GLSL → [{'W':(3,3,cin,cout), 'b', 'a'|None, 'residual'}] — 모르는 모양이면 멈춘다.

    GLSL 의미(libplacebo/mpv 사용자 셰이더): `NAME_texOff(vec2(dx,dy))` 는 (x+dx, y+dy) 화소(가장자리는 늘려 씀) ·
    `mat4(16수)` 는 열 우선이라 `mat*v` 는 out[r] = Σ_c M[c][r]·v[c] · 활성은 PReLU · 마지막은 LUMA 잔차 + 2×2 화소 섞기
    (출력 화소 (2x+i, 2y+j) ← 채널 j*2+i) + [0,1] 자르기.
    """
    import numpy as np
    passes = []
    for chunk in _HEAD.split(text)[1:]:
        desc = chunk.splitlines()[0]
        if 'pixelshuff' in desc:
            if _SHUFFLE not in chunk or 'clamp(c0, 0.0, 1.0)' not in chunk:
                raise ValueError('ACNet pixel shuffle pass differs from the pinned shape')
            passes.append({'shuffle': True})
            continue
        if 'vec4 hook() {' not in chunk:
            raise ValueError('ACNet pass without a hook body: ' + desc)
        body = chunk.split('vec4 hook() {', 1)[1]
        bias = _BIAS.search(body)
        if not bias:
            raise ValueError('ACNet pass without a bias vector: ' + desc)
        terms = _TERM.findall(body)
        act = _ACT.search(body)
        passes.append({'desc': desc, 'bias': [float(x) for x in bias.group(1).split(',')],
                       'terms': [(k, [float(x) for x in n.split(',')], t, int(float(dx)), int(float(dy)))
                                 for k, n, t, dx, dy, _ in terms],
                       'act': [float(x) for x in act.group(1).split(',')] if act else None,
                       'residual': _RESIDUAL in body,
                       'statements': body.count(';') - 1})
    if not passes or not passes[-1].get('shuffle') or sum(1 for p in passes if p.get('shuffle')) != 1:
        raise ValueError('ACNet shader must end with exactly one pixel shuffle pass')
    convs = []
    i = 0
    passes = passes[:-1]
    while i < len(passes):
        # A 1→8 or 8→8 conv is split into «part 0»/«part 1» (4 channels each); the 8→4 upscale conv is one «part 0».
        parts = [passes[i]]
        if not passes[i]['desc'].endswith('part 0'):
            raise ValueError('ACNet conv pass must start at part 0: ' + passes[i]['desc'])
        if i + 1 < len(passes) and passes[i + 1]['desc'] == passes[i]['desc'][:-1] + '1':
            parts.append(passes[i + 1])
        i += len(parts)
        textures = sorted({t[2] for p in parts for t in p['terms']})
        cin = 1 if textures == ['LUMA'] else 4 * len(textures)
        cout = 4 * len(parts)
        W = np.zeros((3, 3, cin, cout), np.float32)
        b = np.zeros(cout, np.float32)
        acts = [p['act'] for p in parts]
        if any(a is None for a in acts) != all(a is None for a in acts):
            raise ValueError('ACNet conv parts disagree on activation')
        a = None if acts[0] is None else np.zeros(cout, np.float32)
        residual = {p['residual'] for p in parts}
        if len(residual) != 1:
            raise ValueError('ACNet conv parts disagree on residual')
        for pi, p in enumerate(parts):
            # Every statement must be accounted for: bias + 9×len(textures) terms + activation/residual.
            expected = 1 + 9 * len(textures) + (1 if p['act'] or p['residual'] else 0)
            if p['statements'] != expected or len(p['terms']) != 9 * len(textures):
                raise ValueError('ACNet conv pass has unexpected statements: ' + p['desc'])
            b[pi * 4:pi * 4 + 4] = p['bias']
            if a is not None:
                a[pi * 4:pi * 4 + 4] = p['act']
            for kind, nums, tex, dx, dy in p['terms']:
                if not (-1 <= dx <= 1 and -1 <= dy <= 1):
                    raise ValueError('ACNet tap outside 3x3')
                if kind == 'vec4':
                    if cin != 1 or len(nums) != 4:
                        raise ValueError('ACNet vec4 tap on a multi-channel input')
                    W[dy + 1, dx + 1, 0, pi * 4:pi * 4 + 4] += nums
                else:
                    if len(nums) != 16:
                        raise ValueError('ACNet mat4 tap must have 16 numbers')
                    ti = textures.index(tex)
                    W[dy + 1, dx + 1, ti * 4:ti * 4 + 4, pi * 4:pi * 4 + 4] += np.array(nums, np.float32).reshape(4, 4)
        convs.append({'W': W, 'b': b, 'a': a, 'residual': residual.pop()})
    shape = [(c['W'].shape[2], c['W'].shape[3], c['a'] is not None, c['residual']) for c in convs]
    if shape[0][:2] != (1, 8) or shape[-1] != (8, 4, False, True) or any(s != (8, 8, True, False) for s in shape[1:-1]):
        raise ValueError('ACNet layer shapes differ from F8 head/body/upscale: ' + repr(shape))
    return convs


def reference_upscale(y, convs):
    """Plain numpy reference of the same network (float32). Used to prove the runtime, not for production speed."""
    import numpy as np
    x = y[..., None].astype(np.float32)
    for c in convs:
        H, W, C = x.shape
        P = np.pad(x, ((1, 1), (1, 1), (0, 0)), mode='edge')
        out = np.empty((H, W, c['W'].shape[3]), np.float32)
        out[:] = c['b']
        for dy in range(3):
            for dx in range(3):
                out += P[dy:dy + H, dx:dx + W] @ c['W'][dy, dx]
        if c['a'] is not None:
            out = np.maximum(out, 0) + c['a'] * np.minimum(out, 0)
        if c['residual']:
            out = out + y[..., None]
        x = out
    H, W, _ = x.shape
    return np.clip(x.reshape(H, W, 2, 2).transpose(0, 2, 1, 3).reshape(H * 2, W * 2), 0, 1)


# ── 최소 ONNX 직렬화 (onnx 패키지 없이 · 필드 번호는 onnx/onnx.proto3) ───────────────────
def _varint(n):
    # Terminates only for n >= 0 (a negative int never shifts down to 0). Every caller passes a non-negative value
    # (_int masks negatives to 64 bits, lengths/keys are >= 0); refuse instead of looping forever (6-00).
    if n < 0:
        raise ValueError('varint needs a non-negative integer')
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _key(field, wire):
    return _varint(field << 3 | wire)


def _int(field, n):
    return _key(field, 0) + _varint(n & 0xFFFFFFFFFFFFFFFF if n < 0 else n)


def _bytes(field, data):
    data = data.encode('utf-8') if isinstance(data, str) else data
    return _key(field, 2) + _varint(len(data)) + data


def _tensor(name, array):
    import numpy as np
    array = np.ascontiguousarray(array)
    dtype = {np.dtype('float32'): 1, np.dtype('int64'): 7}[array.dtype]
    body = b''.join(_int(1, d) for d in array.shape) + _int(2, dtype) + _bytes(8, name)
    return body + _bytes(9, array.astype(array.dtype.newbyteorder('<')).tobytes())


def _node(op, inputs, outputs, **attrs):
    body = b''.join(_bytes(1, x) for x in inputs) + b''.join(_bytes(2, x) for x in outputs) + _bytes(4, op)
    for name, value in attrs.items():
        if isinstance(value, int):
            body += _bytes(5, _bytes(1, name) + _int(3, value) + _int(20, 2))
        else:
            body += _bytes(5, _bytes(1, name) + _bytes(4, value) + _int(20, 3))
    return body


def _value(name, height='h', width='w'):
    """float32 [1,1,height,width] — 크기는 이름 붙은 미지수(입력 h·w, 출력은 2배라 다른 이름 h2·w2 · 같은 이름이면 ORT 가 모양 불일치를 경고한다)."""
    dims = _bytes(1, _int(1, 1)) + _bytes(1, _int(1, 1)) + _bytes(1, _bytes(2, height)) + _bytes(1, _bytes(2, width))
    return _bytes(1, name) + _bytes(2, _bytes(1, _int(1, 1) + _bytes(2, dims)))


def onnx_model(convs):
    """ONNX opset 17 그래프 바이트 — Pad(edge)·Conv·PRelu·Add·DepthToSpace(CRD)·Clip. GLSL 과 같은 순서·같은 값."""
    import numpy as np
    nodes, inits = [], [_tensor('pads', np.array([0, 0, 1, 1, 0, 0, 1, 1], np.int64)),
                        _tensor('lo', np.array(0, np.float32)), _tensor('hi', np.array(1, np.float32))]
    x = 'y'
    for i, c in enumerate(convs):
        inits += [_tensor(f'w{i}', c['W'].transpose(3, 2, 0, 1)), _tensor(f'b{i}', c['b'])]
        nodes += [_node('Pad', [x, 'pads'], [f'p{i}'], mode='edge'), _node('Conv', [f'p{i}', f'w{i}', f'b{i}'], [f'c{i}'])]
        x = f'c{i}'
        if c['a'] is not None:
            inits.append(_tensor(f'a{i}', c['a'].reshape(-1, 1, 1)))
            nodes.append(_node('PRelu', [x, f'a{i}'], [f'r{i}']))
            x = f'r{i}'
        if c['residual']:
            nodes.append(_node('Add', [x, 'y'], [f's{i}']))
            x = f's{i}'
    nodes += [_node('DepthToSpace', [x], ['d'], blocksize=2, mode='CRD'), _node('Clip', ['d', 'lo', 'hi'], ['out'])]
    graph = (b''.join(_bytes(1, n) for n in nodes) + _bytes(2, NETWORK) + b''.join(_bytes(5, t) for t in inits)
             + _bytes(11, _value('y')) + _bytes(12, _value('out', 'h2', 'w2')))
    return _int(1, 8) + _bytes(2, 'volcano-geumbit') + _bytes(7, graph) + _bytes(8, _bytes(1, '') + _int(2, 17))


_SESSIONS = {}
_SESSION_LOCK = threading.Lock()


def _release_sessions():
    # onnxruntime 세션이 모듈 전역에 남은 채 인터프리터가 내려가면, 세션 소멸이 런타임 스레드 풀의 mutex 가 먼저 사라진 뒤에
    # 일어나 «libc++abi … recursive_mutex lock failed» 로 프로세스가 비정상 종료될 수 있다(2026-10-07 맥 교차 검사 1회 ·
    # 검사는 통과한 뒤 종료 때). 끝나기 전에 세션을 먼저 놓는다 — 실행기 프로세스가 영상처리 뒤 오류 코드로 끝나지 않게.
    with _SESSION_LOCK:
        _SESSIONS.clear()


atexit.register(_release_sessions)


def session(tools):
    """One inference session per pinned shader and provider per process (provider = tools identity · onnx_providers)."""
    from onnx_providers import Session
    provider = tools['identity'].get('provider', 'cpu')
    key = (tools['identity']['files'][Path(tools['shader']).name], provider)
    with _SESSION_LOCK:
        if key not in _SESSIONS:
            convs = parse_shader(Path(tools['shader']).read_text(encoding='utf-8'))
            # 기본 로그 수준 그대로 — 경고를 숨기지 않는다(출력 모양 선언이 틀렸던 것을 가렸다 · 검토 minor).
            _SESSIONS[key] = (Session(onnx_model(convs), provider), convs)
        return _SESSIONS[key]


def upscale_luma(tools, y8):
    """uint8 (H,W) 루마 → float32 (2H,2W) 0~1. 입력은 원본 Y 표본(libplacebo LUMA 와 같은 raw/255).

    DirectML 이 실패하면 onnx_providers.GpuFailed — 부르는 쪽이 그 일을 CPU 로 한 번 다시 한다(with_cpu_fallback)."""
    import numpy as np
    run, _ = session(tools)
    y = (np.asarray(y8, np.float32) / np.float32(255.0))[None, None]
    return run.run(None, {'y': y})[0][0, 0]


def probe_tools(assets, root):
    """Actually run the pinned network (this PC's provider) before narration and compare to the numpy reference."""
    from onnx_providers import with_cpu_fallback
    return with_cpu_fallback(lambda: _probe_tools(assets, root))


def _probe_tools(assets, root):
    import numpy as np
    from longform_state import Stages, save
    from onnx_providers import GpuFailed
    root = Path(root)
    tools = ensure_tools(assets)

    def produce(folder):
        y = (np.arange(48 * 32, dtype=np.uint32).reshape(32, 48) * 37 % 251).astype(np.uint8)
        out = upscale_luma(tools, y)
        _, convs = session(tools)
        error = float(np.abs(out - reference_upscale(y.astype(np.float32) / 255, convs)).max())
        if tools['identity']['provider'] == 'dml' and (out.shape != (64, 96) or not error < 1e-4):
            raise GpuFailed(f'DirectML 출력이 기준 계산과 다릅니다(최대 오차 {error})')
        if out.shape != (64, 96) or not error < 1e-4:
            raise ProductionError('video_tools_probe', '영상처리 망의 실제 출력이 기준 계산과 다릅니다.', action='repair_environment')
        proof = folder / 'probe.json'
        save(proof, {'os': platform.platform(), 'actual_inference': True, 'size': [96, 64], 'max_error': error,
                     'tools': tools['identity']})
        return {'os': platform.platform(), 'actual_inference': True, 'size': [96, 64], 'tools': tools}, [proof]
    with file_lock(root / 'probe.lock'):
        return Stages(root).run('native-model-probe', {'tools': tools['identity'], 'os': platform.platform()},
                                [tools['shader']], produce)
