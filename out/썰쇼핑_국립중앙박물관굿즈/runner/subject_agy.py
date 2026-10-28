"""Subject receipts from subscription-AGY reading only. No local inference.

Local work is limited to: one ffmpeg call per proxy (cut, shrink, retime, crop),
coordinate arithmetic, fingerprints and receipt files. This module must never
import a detector, tracker or array library (tests/test_subject_agy.py walks the
AST). The reader is injected by the caller; AGY receives a small mp4.

Measured basis (docs/2026-10-05_피사체-AGY-판독/README.md):
- AGY receives a video as one picture per second. The proxy therefore shows one
  chosen source frame per second, so "second k" is exactly sample k.
- Asked for per-picture boxes in time order, AGY repeated the first picture's
  position on a moving cut in 6 of 10 runs. Pictures are shown in a fixed
  non-chronological order so no continuous story can be assumed.
- ffmpeg's scene score missed two hard cuts inside one test cut (0.047, 0.055).
  The reader names which pictures share a shot; the score peak between two
  neighbouring samples then gives the exact frame.
- One AGY reading per cut (v4, owner decision 2026-10-06 night): the reading's
  boxes plus PAD go straight to the receipt. There is no second reading of the
  planned crop and no check of a non-16:9 source's full-frame window.
"""
import hashlib
import json
import math
import re

# v2 (2026-10-05 사장님 결정 5-3): 첫 판독이 주변 사람(주인공 아님)의 머리 상자도 받아, 확대 창 가장자리에 반쪽 얼굴이 걸리면
# 그 사람을 지킬 영역에 넣는다(주인공 영역은 그대로 · 배율이 덜 되는 컷이 늘어나는 것은 감수). 질문이 바뀌어 v1 답과 섞지 않는다.
# v3 (검토 2026-10-05): 반쪽 얼굴 판정이 다섯 배율 점만 보던 것을 렌더가 고를 수 있는 배율 구간 전체로(bystander_cuts).
#   같은 판독 답이어도 지키는 영역이 달라질 수 있어 v2 영수증과 섞지 않는다(v1·v2 는 배포된 적 없음).
# v4 (사장님 결정 2026-10-06 밤 «medium 한 번만»): 컷마다 AGY 호출은 첫 판독 1번뿐 — 크롭 재확인(check-N)과 16:9 아닌 원본의
#   전체 화면 창 재확인(frame-check-N)을 뺐다. 모델은 서버 POLICY 가 gemini-3.8-flash-medium 으로 준다. 첫 판독 질문·산수·여유(PAD 3%)는
#   v3 그대로다. 실측 근거(세션 fcd10043 agytok/결과.md · 8컷×2회 · 이 맥): 100컷 토큰 11.8M(v3: high·재확인) → 4.33M(medium·1번만) ·
#   5시간 한도 약 14.7 → 4.8점(추정 · 출력이 입력의 약 5배 무게) · 주인공 얼굴 잘림 0/740(v3 0/737 · 얼굴 자 YuNet — 재는 데만) ·
#   같은 AGY(high)+재확인 질문으로 크롭을 다시 본 판정 «잘림·사라짐» 2/15(v3 1/15) — 그 둘은 c10 액션 리플레이(여러 장면) 두 회뿐이다.
#   재확인이 없으니 답이 다른 영수증이다 — v3 영수증과 섞지 않는다(진행 중 작업의 끝난 v3 영수증은 subject_agy_run 이 «더 엄격한 옛 판»
#   으로 그대로 쓴다 · PRIOR_ALGORITHMS).
# v5 (사장님 결정 2026-10-07 «135~190%»): 렌더 배율 상한 170% → 190%(MAX_ZOOM). 첫 판독 질문의 배율 문구와, 주변 사람 머리를
#   반쪽으로 자르는지 보는 배율 구간(render_zooms · bystander_cuts)이 함께 넓어진다 — 같은 판독 답이어도 지키는 영역이 달라질 수 있어
#   새 이름이다. 영수증 selection_evidence.zoom_range 에 [135%, 190%] 를 적고, 렌더(longform_reframe.from_focus_receipt)는 그 칸이 없는
#   옛 영수증(v3·v4)을 그 판이 주변 사람을 확인한 170% 까지만 쓴다(PRIOR_ALGORITHMS 로 그대로 이어 쓴다 · 학생 AGY 한도를 다시 안 쓴다).
ALGORITHM = 'agy-direct-v5'
# 이어 쓸 수 있는 옛 판 — 같은 첫 판독 질문에 크롭 재확인(잘리면 넓혀 다시 · 못 풀면 전체 화면)까지 거친 영수증(v3). v4 가 하는 일의 상위
# 집합이라 그 결과를 그대로 받는다(학생 AGY 한도를 다시 쓰지 않는다 · 전역 규칙 6-2). 어느 영수증이 v3 인지는 서버가 준 옛 열쇠
# (agy_focus.PRIOR_POLICIES 로 지은 focus_key)와 영수증 engine 이 함께 정한다.
PRIOR_ALGORITHMS = ('agy-direct-v4', 'agy-direct-v3')
STEP_SECONDS = .5          # target spacing of the first reading's samples
MAX_PICTURES = 24          # per request; longer cuts widen the spacing
PROXY_HEIGHT = 360
PAD = .03                  # of the frame, added to every must-keep edge
# Hard shot changes are measured with the production cut check's own ruler (longform_video.inspect_cuts:
# 2 s of decoded context before the cut · 320 px wide · scene > 0.20). Starting the score at the cut's
# first frame inflates the second frame's score (ffmpeg compares against an empty previous difference):
# measured 0.153 vs 0.014 on the same frame of a one-shot dugout pan (review 1, 2026-10-05).
SCENE_THRESHOLD = .20
SCENE_CONTEXT_SECONDS = 2.
SCENE_WIDTH = 320
# Camera flashes (press conferences) cross the same threshold without changing the shot (review 2,
# 2026-10-05: 22 of 26 candidates in a press-conference file). Measured shape on the same ruler
# (320 px · signalstats YAVG on 0..255): the mean luma jumps by 22~55 for one source frame and returns
# within 0~5.1 of the level before. Same rule over 12 whole files · 134 candidates: 24 of 26 in the
# press conference (the other 2 change level and stay — real camera switches), 0 of 66 sports/interview
# cuts, 1 of 42 in a title animation (a luma pulse; its neighbours are refused anyway). A candidate of
# that shape is not a refusal on its own: the reading's shot numbers on both sides decide (different
# shots → a break), so a white-flash transition between two shots is still split.
FLASH_RISE = 12.           # luma units the flash frames must stay above the level before
FLASH_RETURN = .3          # back within max(3, 0.3 × rise) of the level before …
FLASH_SECONDS = .1         # … within this long after the first bright frame
MIN_ZOOM, MAX_ZOOM, ROI_MARGIN = 1.35, 1.90, .025   # same as longform_reframe.solve (v5 · 사장님 결정 2026-10-07 135~190%)
# AGY readings after the first one, per cut: none (v4). The server POLICY carries the same number ('max_checks') and
# subject_agy_run.check_policy refuses any other — the contract field stays so the two sides keep comparing it.
MAX_CHECKS = 0
# Bystanders: heads at least this share of the frame height are kept whole or left out — never cut in half by the
# window edge (decision 5-3). Same size rule as the measurement that counted the half faces (481/2140 · face height
# 6%, head = face + 25% up — docs/2026-10-05_피사체-AGY-판독). Smaller crowd heads are not chased.
BYSTANDER_MIN_H = .06
COVER_INSIDE, COVER_OUTSIDE = .999, .02    # share of a head inside the window: whole · gone (same as the measurement)
BYSTANDER_ZOOMS = 5        # zooms tried between 135% and the region's upper bound; the ends decide (bystander_cuts), the middle cross-checks
KINDS = ('person', 'people', 'animal', 'object', 'scene', 'absent')


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8')).hexdigest()


class Unresolved(ValueError):
    """One cut could not be read. Never a refusal of the service and never a centre crop."""
    def __init__(self, code, reason, **detail):
        super().__init__(reason)
        self.code, self.reason, self.detail = code, reason, detail


# ── which source frames each reading sees ─────────────────────────────────
def sample_grid(nframes, fps, *, step=STEP_SECONDS, cap=MAX_PICTURES):
    """The reading's samples: centres of n equal spans (n = one per `step` seconds, at most `cap`)."""
    if type(nframes) is not int or nframes < 1 or not _number(fps) or fps <= 0:
        raise ValueError('invalid frame grid')
    n = max(1, min(int(cap), math.ceil(nframes / fps / step - 1e-9), nframes))
    return sorted({min(nframes - 1, int((k + .5) * nframes / n)) for k in range(n)})


def show_order(n):
    """Fixed non-chronological order: shown picture k is sample order[k].

    Deterministic on every machine and Python (own generator, no random module).
    Neighbouring shown pictures are never neighbouring moments (from four
    pictures up), so neither a forward nor a reversed story can be assumed.
    """
    if n < 3:
        return list(range(n))
    state = (0x9E3779B9 ^ n) & 0xFFFFFFFF
    order = list(range(n))
    for _ in range(256):
        order = list(range(n))
        for i in range(n - 1, 0, -1):
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            j = (state >> 8) % (i + 1)
            order[i], order[j] = order[j], order[i]
        if n < 4 or min(abs(a - b) for a, b in zip(order, order[1:])) >= 2:
            break
    return order


def _terms(parts):
    """Balanced sum so a long list never becomes a deep expression."""
    parts = list(parts)
    while len(parts) > 1:
        parts = [f'({parts[i]}+{parts[i+1]})' if i + 1 < len(parts) else parts[i] for i in range(0, len(parts), 2)]
    return parts[0]


def proxy_filter(indices, order, *, grid='fps=60', height=PROXY_HEIGHT, scores=False, warmup=0.):
    """One filter chain: [scene scores →] output grid → chosen frames → small → shown order → one per second.

    scores: also print the scene score of every source frame on a separate 320 px branch that ends in
    a null sink (an ffmpeg metric; no picture file is written).
    warmup: seconds decoded before the cut (the input seek starts that much earlier). The score branch
    sees them; the picture branch trims them away so its frame clock is the same as without warm-up.
    """
    if not indices or sorted(set(indices)) != list(indices) or sorted(order) != list(range(len(indices))):
        raise ValueError('invalid proxy samples')
    warmup = float(warmup)
    if not math.isfinite(warmup) or warmup < 0 or (warmup and not scores):
        raise ValueError('warm-up is only for the scored reading proxy')
    head = ''
    if scores:
        head = (f"split[score][pictures];[score]scale={SCENE_WIDTH}:-2,signalstats,select='gte(scene,0)',"
                "metadata=mode=print:key=lavfi.scene_score,metadata=mode=print:key=lavfi.signalstats.YAVG,nullsink;[pictures]")
    chain = []
    if warmup:
        chain.append(f'trim=start={warmup:.6f},setpts=PTS-{warmup:.6f}/TB')
    chain += [grid, "select='" + _terms(f'eq(n,{i})' for i in indices) + "'"]
    chain.append(f'scale=-2:{int(height)}')
    if list(order) != sorted(order):
        chain.append('shuffleframes=' + ' '.join(str(v) for v in order))
    chain.append('setpts=N/TB')
    return head + ','.join(chain)


def warmup_for(start):
    """Seconds of context the scored proxy decodes before the cut (capped by the file start)."""
    return round(min(max(0., float(start)), SCENE_CONTEXT_SECONDS), 6)


def proxy_argv(ffmpeg, source, out, vf, *, input_options):
    return ([ffmpeg, '-y', '-hide_banner', '-nostats', '-v', 'info'] + list(input_options)
            + ['-i', source, '-an', '-vf', vf, '-r', '1', '-c:v', 'libx264', '-crf', '23', '-preset', 'veryfast',
               '-g', '1', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out])


def _score_log(log):
    """Score-branch log → [(source pts_time, scene score, mean luma or None)] in decode order."""
    score = {}; luma = {}; when = None
    for line in (log or '').splitlines():
        m = re.search(r'pts_time:([-+\d.eE]+)', line)
        if m:
            when = float(m[1])
        m = re.search(r'lavfi\.(scene_score|signalstats\.YAVG)=([-+\d.eE]+)', line)
        if m and when is not None:
            (score if m[1] == 'scene_score' else luma)[when] = float(m[2])
    return [(t, score[t], luma.get(t)) for t in sorted(score)]


def scene_scores(log, origin, fps, nframes, *, fresh_decode=False):
    """Scores ffmpeg printed while making the proxy → {output frame index: score} inside the cut.

    fresh_decode: the log starts where decoding started. The first decoded frame has no previous frame
    and the second is compared with an empty previous difference (inflated), so the two earliest are
    dropped. With the usual warm-up they lie before the cut anyway; this covers a cut at the file start.
    """
    return scene_readout(log, origin, fps, nframes, fresh_decode=fresh_decode)[0]


def scene_readout(log, origin, fps, nframes, *, fresh_decode=False):
    """(scores, flashes): scores as scene_scores; flashes = output frame indices of threshold
    crossings shaped like a camera flash (FLASH_*). Pure arithmetic on ffmpeg's printed metrics."""
    rows = _score_log(log)
    if fresh_decode:
        rows = rows[2:]
    scores = {}; flash = set(); covered = set()
    def index_of(t):
        return round((t - origin) * fps)
    for k, (when, value, _) in enumerate(rows):
        index = index_of(when)
        if 0 < index < nframes:
            scores[index] = max(scores.get(index, 0.), value)
    for k, (when, value, luma) in enumerate(rows):
        if value <= SCENE_THRESHOLD or k == 0 or k in covered or luma is None or rows[k - 1][2] is None:
            continue
        before = rows[k - 1][2]; peak = []
        for j in range(k, len(rows)):
            t, _, y = rows[j]
            if y is None or t - when > FLASH_SECONDS + 1e-6:
                break
            rise = min(peak) - before if peak else None
            if peak and rise >= FLASH_RISE and abs(y - before) <= max(3., FLASH_RETURN * rise):
                for m in range(k, j + 1):
                    covered.add(m)
                    index = index_of(rows[m][0])
                    if 0 < index < nframes and rows[m][1] > SCENE_THRESHOLD:
                        flash.add(index)
                break
            peak.append(y)
    return scores, flash


def hard_cuts(scores, threshold=SCENE_THRESHOLD):
    return sorted(i for i, s in scores.items() if s > threshold)


def boundary_between(scores, a, b):
    """The reader saw different shots at samples a < b: the frame with the highest score in (a, b]."""
    inside = {i: s for i, s in scores.items() if a < i <= b}
    if not inside:
        return None
    return max(sorted(inside), key=lambda i: inside[i])


# ── the two questions ─────────────────────────────────────────────────────
ONLY_THIS_FILE = 'RunCommand·셸·ffmpeg·웹 검색을 쓰지 마라. view_file 로 {path} 하나만 봐라(화면 그대로 · 소리 없음). 다른 파일(AGENTS.md·CLAUDE.md·README 등 어떤 것도)은 열지 마라.\n'


def subject_question(path, n, context):
    return (
        ONLY_THIS_FILE.replace('{path}', path or '첨부한 영상 파일') +
        f'이 영상은 원본 컷에서 뽑은 화면 {n}장을 «순서를 뒤섞어» 1초에 한 장씩 보여 준다. 영상의 0초 화면이 0번, 1초 화면이 1번, … 마지막이 {n-1}번이다. '
        '앞뒤 화면은 시간순으로 이어지지 않는다 — 화면마다 주인공의 위치와 크기가 서로 다르다고 생각하고 하나씩 처음 보는 사진처럼 재라.\n'
        f'이 컷 위에 입힐 내레이션·문맥: «{context}».\n'
        '이 컷을 135~190% 로 확대해서 쓴다. 확대하면 화면 가장자리가 잘린다. 그래서 화면마다 «잘리면 안 되는 것» 의 위치를 알아야 한다.\n'
        '주인공 = 문맥이 말하는 사람·동물·사물. 함께 보여야 뜻이 통하는 상대(투샷의 두 번째 사람·맞서는 상대 선수·대화 상대)도 주인공이다. 관중·배경 인물·심판·스태프는 주인공이 아니다. 가장 큰 얼굴이나 가운데 얼굴을 그냥 고르지 말고 문맥에 맞는 대상을 골라라. 얼굴 생김새로 이름을 추측하지 마라.\n'
        f'화면 {n}장을 하나씩 따로 보고, 화면마다 다음을 답하라.\n'
        ' - "see" = 그 화면에서 주인공이 화면의 어디쯤(왼쪽/가운데/오른쪽 · 위/아래)에서 무엇을 하는지 짧게.\n'
        ' - "shot" = 같은 카메라 구도로 이어지는 화면끼리 같은 번호(0부터). 다른 카메라·다른 구도·다른 장소로 바뀐 화면은 다른 번호.\n'
        ' - "heads" = 주인공 각자의 머리 상자 목록. 머리카락·모자 맨 위부터 턱 끝까지, 귀까지 포함해 한 사람(동물)에 상자 하나. 그 화면에 머리가 안 보이는 주인공은 뺀다.\n'
        ' - "action" = 문맥이 몸으로 하는 행동(던진다·친다·잡는다·달린다·건넨다·든다)을 말하는 컷에서만, 그 행동의 핵심(공·배트·글러브·행동하는 손·들고 있는 물건)을 담는 상자 하나. 말하거나 듣거나 가만히 있는 컷이면 null.\n'
        ' - "wide" = 가능하면 남기고 싶은 범위. 주인공의 상반신(행동 컷이면 몸 전체와 공·배트가 움직이는 범위)을 담는 상자 하나.\n'
        ' - "others" = 주인공이 아닌 사람(관중·배경 인물·심판·스태프·통역·지나가는 사람) 가운데 머리 높이가 화면 높이의 1/20 이상인 사람 각자의 머리 상자 목록(최대 8개 · 없으면 빈 목록). 확대해서 잘라 낼 때 그 사람 얼굴이 가장자리에 반쪽만 걸리지 않게 하려는 것이다. 주인공은 여기에 넣지 마라.\n'
        '좌표는 box_2d 형식 [ymin, xmin, ymax, xmax], 각 값은 0~1000 정수(화면 맨 위 0 · 맨 아래 1000 · 맨 왼쪽 0 · 맨 오른쪽 1000). 그 화면에 보이는 그대로 재라. 여유를 붙이지 마라(여유는 내가 더한다).\n'
        '그 화면에 주인공이 안 보이면 heads 는 빈 목록, action 과 wide 는 null 로 답하라. 화면 전체가 내용인 장면(풍경·표·그래픽·글자 화면·군중 전체)이면 kind 를 "scene" 으로, 문맥이 말하는 주인공이 어느 화면에도 없으면 kind 를 "absent" 로 하고 frames 는 빈 목록, 이유(대신 무엇이 보이는지)를 note 에 써라. 지어내지 마라.\n'
        '화면에 박혀 있는 자막·로고·점수판은 상자에 넣지 말고 burned_in 에 따로 적어라.\n'
        '설명 없이 JSON 하나만 출력하라: {"kind":"person|people|animal|object|scene|absent","who":"주인공이 누구/무엇이고 무엇을 하는지 한 줄",'
        '"frames":[{"i":0,"see":"","shot":0,"heads":[[0,0,0,0]],"action":null,"wide":[0,0,0,0],"others":[[0,0,0,0]]}],'
        '"burned_in":[{"box_2d":[0,0,0,0],"what":""}],"confidence":"high|medium|low","note":""}')


# 답 길이(2026-10-06 · 학생 실측: 길어서 끝이 잘린 답이 status ERROR 로 끝났다 — 오류 글 «exceeded the output token limit»).
# 설명 칸을 짧게 쓰라는 한 줄. 새 칸·괄호·따옴표가 없어 답의 칸·뜻·JSON 모양은 그대로다(subject_answer 는 바뀌지
# 않았다 — tests/test_subject_agy_cut_fallback.py 가 이 줄에 JSON 조각이 없고 질문 본문 밖에 있음을 잰다). 그래서 저장된 답의
# 묶음(subject_agy_run.measure_cut 의 bound = 질문 본문)에 넣지 않는다: 넣으면 진행 중 작업이 이미 받은 답을 버리고 AGY 에 다시
# 묻게 된다(전역 규칙 6-2). 실행기가 질문 끝에 붙여 보낸다. 길이 숫자는 정하지 않았다(잰 근거가 없다) — «한 줄» 만 말한다.
ANSWER_BREVITY = ('\n답은 짧게 써라: 설명 칸(see·what·who·note·burned_in 의 what)은 칸마다 한 줄로만 쓰고 까닭을 길게 늘어놓지 마라. '
                  '답이 길면 끝이 잘려 답 전체를 버린다. 위에서 말한 JSON 하나 밖의 글은 쓰지 마라.')


# ── reading the answers ───────────────────────────────────────────────────
def _box2d(value):
    """[ymin, xmin, ymax, xmax] 0..1000 → [x1, y1, x2, y2] 0..1, or None."""
    if not (isinstance(value, list) and len(value) == 4 and all(_number(v) for v in value)):
        return None
    y1, x1, y2, x2 = (float(v) / 1000 for v in value)
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        return None
    return [x1, y1, x2, y2]


def burned_in_boxes(answer):
    """판독 답의 burned_in(화면에 박힌 자막·로고·점수판) → 정규화 [x1, y1, x2, y2] 목록. 모양이 틀린 칸은 버린다(주인공 판정과 무관)."""
    items = answer.get('burned_in') if isinstance(answer, dict) else None
    if not isinstance(items, list):
        return []
    boxes = (_box2d(item.get('box_2d')) for item in items[:12] if isinstance(item, dict))
    return [[round(v, 4) for v in b] for b in boxes if b is not None]


def _union(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def subject_answer(answer, n):
    """Validate the first reading.

    Returns (kind, who, shown): shown[k] is None (no subject in that picture) or
    {'core', 'wide', 'heads', 'action', 'shot', 'others'} in normalised [x1, y1, x2, y2].
    Older two-box answers (core/wide) are read the same way.
    others: bystander heads of at least BYSTANDER_MIN_H, minus any that is really a subject head (IoU > .5).
    A malformed bystander entry is dropped and counted ('others_dropped') — bystanders never decide whether
    the subject can be read; the subject boxes stay strict.
    """
    if not isinstance(answer, dict) or answer.get('kind') not in KINDS:
        raise ValueError('answer kind missing')
    who = answer.get('who')
    if not isinstance(who, str) or not who.strip():
        raise ValueError('answer subject description missing')
    frames = answer.get('frames')
    if answer['kind'] in ('scene', 'absent'):
        # 질문은 frames 를 빈 목록으로 달라고 하지만, AGY 가 화면마다 설명(상자 없음)을 채워 오기도 한다
        # (실측 2026-10-05 4:3 경기장 컷: frames 6줄 · heads [] · wide null). 전체 화면은 아무것도 자르지 않는
        # 안전한 쪽이므로 kind 를 따르고 frames 는 읽지 않는다 — 모양 오류로 컷 전체를 버리지 않는다.
        if frames is not None and not isinstance(frames, list):
            raise ValueError('answer frames must be a list')
        return answer['kind'], who.strip(), [None] * n
    if not isinstance(frames, list) or len(frames) != n:
        raise ValueError('answer must describe every picture exactly once')
    shown = [None] * n; seen = set()
    for row in frames:
        if not isinstance(row, dict) or type(row.get('i')) is not int or not 0 <= row['i'] < n or row['i'] in seen:
            raise ValueError('answer picture numbers differ from the request')
        seen.add(row['i'])
        shot = row.get('shot', 0)
        if type(shot) is not int or shot < 0:
            raise ValueError('answer shot label is invalid')
        heads = row.get('heads')
        if 'core' in row and heads is None:            # two-box form
            heads = [] if row['core'] is None else [row['core']]
        if heads is None:
            heads = []
        if not isinstance(heads, list):
            raise ValueError('answer heads must be a list')
        boxes = [_box2d(v) for v in heads]
        action = row.get('action')
        if any(b is None for b in boxes) or (action is not None and _box2d(action) is None):
            raise ValueError('answer box is not a box_2d inside the picture')
        action = None if action is None else _box2d(action)
        must = boxes + ([action] if action else [])
        others, dropped = _others(row.get('others'), boxes)
        if not must:
            shown[row['i']] = {'core': None, 'shot': shot, 'see': row.get('see') if isinstance(row.get('see'), str) else '',
                               'others': others, 'others_dropped': dropped}
            continue
        core = must[0]
        for b in must[1:]:
            core = _union(core, b)
        wide = _box2d(row.get('wide'))
        wide = core if wide is None else _union(core, wide)
        shown[row['i']] = {'core': core, 'wide': wide, 'heads': boxes, 'action': action, 'shot': shot,
                           'see': row.get('see') if isinstance(row.get('see'), str) else '',
                           'others': others, 'others_dropped': dropped}
    if not any(s and s['core'] for s in shown):
        raise ValueError('answer has no visible subject and is not a scene')
    return answer['kind'], who.strip(), shown


def _iou(a, b):
    w = max(0., min(a[2], b[2]) - max(a[0], b[0])); h = max(0., min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - w * h
    return w * h / u if u > 0 else 0.


def _others(value, heads):
    """Bystander heads of one picture → (kept normalised boxes, dropped count)."""
    if not isinstance(value, list):
        return [], 0 if value is None else 1
    kept, dropped = [], 0
    for item in value[:8]:
        box = _box2d(item)
        if box is None:
            dropped += 1; continue
        if box[3] - box[1] < BYSTANDER_MIN_H or any(_iou(box, h) > .5 for h in heads):
            continue
        kept.append(box)
    return kept, dropped + max(0, len(value) - 8)


# ── arithmetic ────────────────────────────────────────────────────────────
def to_time_order(shown, order):
    """shown[k] belongs to sample order[k]."""
    result = [None] * len(shown)
    for k, value in enumerate(shown):
        result[order[k]] = value
    return result


def shot_boundaries(shown, order, indices, scores):
    """Samples the reader put in different shots → exact boundary frames (or None where no score peak exists)."""
    rows = to_time_order(shown, order)
    labelled = [(i, row['shot']) for i, row in zip(indices, rows) if row is not None]
    cuts = []
    for (a, shot_a), (b, shot_b) in zip(labelled, labelled[1:]):
        if shot_a != shot_b:
            cuts.append((a, b, boundary_between(scores, a, b)))
    return cuts


def flash_adjudication(flash_cuts, shown, order, indices):
    """Each flash-shaped candidate → the reading's shot numbers on the nearest samples each side.

    same_shot: ignored (a flash on one shot) · shot_change: shot_boundaries already breaks there ·
    no_reading: a scene/absent answer frames the whole picture, so nothing is cut · edge: no labelled
    sample on one side (within half a sample step of the cut edge) — ignored on the arithmetic alone.
    """
    rows = to_time_order(shown, order) if shown else []
    labelled = [(i, row['shot']) for i, row in zip(indices, rows) if row is not None]
    out = []
    for frame in flash_cuts:
        if not labelled:
            out.append({'frame': frame, 'verdict': 'no_reading'}); continue
        left = [s for i, s in labelled if i < frame]; right = [s for i, s in labelled if i >= frame]
        verdict = 'edge' if not left or not right else 'same_shot' if left[-1] == right[0] else 'shot_change'
        out.append({'frame': frame, 'verdict': verdict})
    return out


def _pad(box, size):
    """Normalised box + PAD on every side → source pixels, clamped to the frame.

    A padded edge that ends within PAD of the source edge is moved onto that edge: the renderer keeps
    a margin of 2.5% of the region around it (longform_reframe.solve), so a region stopping a few pixels
    short of the source top left those pixels outside the crop (measured c12: a head touching the source
    top lost its top 6 px). On the edge, the crop may start at the edge.
    """
    w, h = size
    x1, y1 = (box[0] - PAD) * w, (box[1] - PAD) * h
    x2, y2 = (box[2] + PAD) * w, (box[3] + PAD) * h
    x1 = 0. if x1 < PAD * w else x1; y1 = 0. if y1 < PAD * h else y1
    x2 = float(w) if x2 > w - PAD * w else x2; y2 = float(h) if y2 > h - PAD * h else y2
    return [x1, y1, x2, y2]


def _lerp(a, b, u):
    return [a[i] + (b[i] - a[i]) * u for i in range(4)]


def envelope(indices, boxes, nframes, breaks=()):
    """Per-frame region that holds a subject moving steadily between neighbouring samples.

    At a sample the region is that sample's box; halfway to the next it is the
    union of both; it changes linearly in between (no jumps for the crop to follow).
    breaks: frames where a new shot starts (the reader saw a different shot and the
    ffmpeg score peaks there). Across a break nothing is blended: the earlier box
    holds up to the break and the later box starts on it, so no frame is framed
    with a region from the other shot.
    Samples without a visible subject borrow the nearest visible one in the same
    shot (any shot when that shot shows none).
    """
    breaks = sorted(set(breaks))
    def shot_of(f):
        return sum(1 for c in breaks if c <= f)
    known = [(i, b) for i, b in zip(indices, boxes) if b is not None]
    if not known:
        raise ValueError('no sample shows the subject')
    filled = []
    for i, b in zip(indices, boxes):
        if b is None:
            same = [k for k in known if shot_of(k[0]) == shot_of(i)] or known
            b = min(same, key=lambda k: abs(k[0] - i))[1]
        filled.append((i, b))
    track = []
    for f in range(nframes):
        if f <= filled[0][0]:
            track.append(list(filled[0][1])); continue
        if f >= filled[-1][0]:
            track.append(list(filled[-1][1])); continue
        for (a, box_a), (b, box_b) in zip(filled, filled[1:]):
            if a <= f <= b:
                cut = next((c for c in breaks if a < c <= b), None)
                if cut is not None:
                    track.append(list(box_a if f < cut else box_b)); break
                u = (f - a) / (b - a); both = _union(box_a, box_b)
                track.append(_lerp(box_a, both, 2 * u) if u <= .5 else _lerp(both, box_b, 2 * u - 1))
                break
    return track


# 출력 창의 가로:세로. 롱폼은 16:9(기본 — 롱폼 영수증·열쇠는 그대로다). 숏폼(사장님 결정 2026-10-07 «숏폼 피사체도 AGY») 은
# 영상 창 비율을 컷의 'aspect' [가로, 세로] 로 받는다 — 같은 판독·같은 산수를 그 비율의 창으로 푼다(longform_reframe.solve(aspect=)).
WIDE = (16, 9)


def window(size, aspect=WIDE):
    """(base_w, base_h): 원본 안에 들어가는 가장 큰 `aspect` 창(배율 1.0)."""
    w, h = size; a = aspect[0] / aspect[1]
    base_w = min(float(w), float(h) * a)
    return base_w, base_w / a


def fit_zoom(track, size, aspect=WIDE):
    """Largest zoom whose `aspect` window still holds every frame's region (longform_reframe.solve's bound)."""
    w, h = size
    base_w, base_h = window(size, aspect)
    upper = float('inf')
    for b in track:
        px = (b[2] - b[0]) * ROI_MARGIN; py = (b[3] - b[1]) * ROI_MARGIN
        safe = [max(0, b[0] - px), max(0, b[1] - py), min(w, b[2] + px), min(h, b[3] + py)]
        upper = min(upper, base_w / (safe[2] - safe[0]), base_h / (safe[3] - safe[1]))
    return upper


def full_frame(nframes, size, exception, samples=None, aspect=WIDE):
    """확대하지 않는다(배율 1.0). 지키는 영역 = 원본에 들어가는 가장 큰 16:9 창.

    정확히 16:9 인 원본이면 원본 전체다. 반올림 탓에 16:9 에서 1px 미만 벗어난 원본(가로 854 처럼 2로 나누어지지 않는
    폭)도 그 창이어야 렌더(longform_reframe.solve)가 «16:9 창에 안 들어간다» 로 죽지 않는다(실측: c02 의 그런 원본 전체 화면
    영수증이 거기서 죽었다). ★배급 코드에 화면 규격 숫자를 적지 않는다(검사 «명세 숫자가 배급 코드에 박혀 있지 않다»).
    4:3 처럼 확실히 다른 원본은 16:9 출력이 어차피 위아래를 자른다 — 그때 창은 판독이 본 주인공 영역(samples)의
    한가운데에 둔다. 주인공 영역이 없으면 원본 한가운데이고, 그 사실을 예외 이름에 남긴다.
    """
    w, h = size
    base_w, base_h = window(size, aspect)
    known = [b for b in (samples or []) if b]
    if known:
        cx = (min(b[0] for b in known) + max(b[2] for b in known)) / 2
        cy = (min(b[1] for b in known) + max(b[3] for b in known)) / 2
    else:
        cx, cy = w / 2, h / 2
        if base_w < w - 1 or base_h < h - 1:
            exception = exception + '_source_not_16x9_centre'
    x = max(0., min(w - base_w, cx - base_w / 2)); y = max(0., min(h - base_h, cy - base_h / 2))
    # 창 안쪽으로 0.5px 들인다 — solve 의 ROI 여유(2.5%)를 더해도 창 하나에 들어가야 한다.
    inset_x = base_w * ROI_MARGIN / (1 + 2 * ROI_MARGIN); inset_y = base_h * ROI_MARGIN / (1 + 2 * ROI_MARGIN)
    box = [x + inset_x, y + inset_y, x + base_w - inset_x, y + base_h - inset_y]
    return {'tier': 'scene', 'fit': 1., 'exception': exception,
            'track': [list(box) for _ in range(nframes)], 'samples': samples or []}


def not_16x9(size, aspect=WIDE):
    """원본이 출력 창(기본 16:9) 하나에 다 안 들어가는가(1px 넘게) — 그러면 배율 1.0 이어도 출력이 원본 일부를 잘라 낸다."""
    w, h = size
    base_w, base_h = window(size, aspect)
    return base_w < w - 1 or base_h < h - 1


# 판독 답이 없는 전체 화면 영수증(status_error_receipt)의 «누구» 칸.
FULL_FRAME_WHO = '화면에 보이는 사람 모두(있다면)'


def plan(kind, shown, order, indices, nframes, size, breaks=(), aspect=WIDE):
    """Answer boxes → required region per output frame.

    Prefers the generous region when a 135% window still holds it for the whole
    cut; otherwise the largest mix of must-keep and generous regions that a 135%
    window holds (blend); otherwise the must-keep region (heads + named action). Below 135% the
    must-keep region is still preserved and the exception is named. A scene
    keeps the whole frame.
    breaks: frames where a new shot starts (see envelope).
    Then bystander heads the window edge would cut in half are added (avoid_bystanders · decision 5-3).
    """
    if kind == 'scene':
        return full_frame(nframes, size, 'scene_full_frame', aspect=aspect)
    if kind == 'absent':
        return full_frame(nframes, size, 'subject_absent_full_frame', aspect=aspect)
    outcome = _plan_subject(kind, shown, order, indices, nframes, size, breaks, aspect=aspect)
    others = [(r or {}).get('others') or [] for r in to_time_order(shown, order)]
    outcome, report = avoid_bystanders(outcome, others, indices, nframes, size, breaks, aspect=aspect)
    return dict(outcome, bystanders=report)


def keep_whole_heads(rows, size, aspect=WIDE):
    """배율 1.0 창(원본에 들어가는 가장 큰 `aspect` 창) 하나로 컷 전체에서 «온전히 담기는 주인공 머리» 가 가장 많은 자리 →
    그 머리들(여유 PAD 포함)을 합친 영역 [x1, y1, x2, y2] (원본 픽셀). 머리가 없으면 None.

    후보 자리는 머리 가장자리에 창 가장자리를 맞춘 곳뿐이다(창 한쪽 끝이 어떤 머리 끝에 닿지 않는 최적 자리는 그 머리 쪽으로 밀어도
    점수가 같다) · 가로·세로를 같이 본다. 같은 점수면 담긴 머리 넓이 합이 큰 쪽(앞에 있는 사람) → 전체 머리 영역 한가운데에 가까운 쪽.
    셈: 후보 (2H)² × 머리 H × 표본 — 표본은 컷당 MAX_PICTURES, 머리는 화면당 몇 개(판독 답)라 범위가 정해져 있다.
    """
    w, h = size
    base_w, base_h = window(size, aspect)
    heads = [_pad(b, size) for r in rows if r and r.get('heads') for b in r['heads']]
    if not heads:
        return None
    def spots(lo_hi, span, limit):
        out = set()
        for lo, hi in lo_hi:
            for v in (lo, hi - span):
                out.add(round(max(0., min(limit - span, v)), 6))
        return sorted(out)
    xs = spots([(b[0], b[2]) for b in heads], base_w, w)
    ys = spots([(b[1], b[3]) for b in heads], base_h, h)
    ux = (min(b[0] for b in heads) + max(b[2] for b in heads)) / 2
    uy = (min(b[1] for b in heads) + max(b[3] for b in heads)) / 2
    best = None
    for x in xs:
        for y in ys:
            inside = [b for b in heads if b[0] >= x - 1e-6 and b[2] <= x + base_w + 1e-6
                      and b[1] >= y - 1e-6 and b[3] <= y + base_h + 1e-6]
            if not inside:
                continue
            area = round(sum((b[2] - b[0]) * (b[3] - b[1]) for b in inside))   # 정수 픽셀² — 같은 크기 머리끼리 부동소수 찌꺼기로 갈리지 않게
            off = abs(x + base_w / 2 - ux) + abs(y + base_h / 2 - uy)
            score = (len(inside), area, -off)
            if best is None or score > best[0]:
                best = (score, inside)
    if best is None:
        return None
    inside = best[1]
    return [min(b[0] for b in inside), min(b[1] for b in inside), max(b[2] for b in inside), max(b[3] for b in inside)]


def _plan_subject(kind, shown, order, indices, nframes, size, breaks=(), aspect=WIDE):
    """plan() without the bystander step — subject regions only."""
    w, h = size
    if kind == 'absent':
        # 문맥의 주인공이 이 컷 어디에도 없다 — 아무 데나 확대하지 않고 전체 화면을 지키며 그 사실을 남긴다.
        return full_frame(nframes, size, 'subject_absent_full_frame', aspect=aspect)
    rows = to_time_order(shown, order)
    # Only the must-keep region carries the safety pad; the generous region is a
    # preference and is used as read, never smaller than the padded must-keep one.
    core = [None if not (r and r['core']) else _pad(r['core'], size) for r in rows]
    wide = [None if c is None else _union(c, [r['wide'][0] * w, r['wide'][1] * h, r['wide'][2] * w, r['wide'][3] * h])
            for r, c in zip(rows, core)]
    wide_track = envelope(indices, wide, nframes, breaks); wide_fit = fit_zoom(wide_track, size, aspect)
    if wide_fit >= MIN_ZOOM - 1e-9:
        return {'tier': 'wide', 'fit': wide_fit, 'exception': None, 'track': wide_track, 'samples': wide}
    core_track = envelope(indices, core, nframes, breaks); core_fit = fit_zoom(core_track, size, aspect)
    if core_fit < 1 - 1e-9:
        # The must-keep region is larger than any window of the output aspect: no crop holds every subject.
        # ★창을 그 영역의 한가운데에 두지 않는다 (2026-10-24 · 명화관 @…686455 «투샷에서 가운데 벽이 중심이 되고 두 얼굴이
        #   양끝에서 잘림»). 1920×816 원본 · 1:1 창(816px)에서 두 머리가 양끝이면 한가운데 창은 **어느 얼굴도** 온전히 담지 못한다
        #   (재현: 창 x 591~1368 · 머리 230~499 와 1459~1728). 배율 1.0 창을 «온전히 담기는 머리가 가장 많은» 자리에 둔다
        #   (keep_whole_heads) — 다 못 담으면 일부를 온전히, 반쪽 얼굴은 만들지 않는다.
        kept = keep_whole_heads(rows, size, aspect)
        return full_frame(nframes, size, 'required_region_exceeds_frame', [kept] if kept else core, aspect=aspect)
    exception = 'preserve_required_region_below_minimum' if core_fit < MIN_ZOOM - 1e-9 else None
    if exception is None:
        # 넉넉한 범위는 135% 에 안 들고 필수 영역은 든다 → 둘 사이에서 135% 에 꼭 맞는 만큼까지 넓힌다.
        # 실측: 같은 컷 두 번의 판독에서 넉넉한 범위가 조금만 달라도 «넉넉한 범위(1.45배)» ↔ «머리만(1.70배 상한)» 으로
        # 갈렸다(c04·c06). 사이 값을 쓰면 배율이 135% 근처로 모이고, 필수 영역은 언제나 들어 있다(필수 ⊂ 섞은 영역).
        lo, hi = 0., 1.
        for _ in range(30):
            mid = (lo + hi) / 2
            mixed = [None if c is None else _lerp(c, x, mid) for c, x in zip(core, wide)]
            if fit_zoom(envelope(indices, mixed, nframes, breaks), size, aspect) >= MIN_ZOOM:
                lo = mid
            else:
                hi = mid
        if lo > 1e-3:
            mixed = [None if c is None else _lerp(c, x, lo) for c, x in zip(core, wide)]
            track = envelope(indices, mixed, nframes, breaks)
            return {'tier': 'blend', 'fit': fit_zoom(track, size, aspect), 'exception': None, 'track': track, 'samples': mixed, 'blend': lo}
    return {'tier': 'core', 'fit': core_fit, 'exception': exception, 'track': core_track, 'samples': core}


def render_zooms(fit):
    """Zooms the renderer may pick for a region (longform_reframe.solve): one value below 135%, else 135%…min(190%, fit)."""
    if fit < MIN_ZOOM - 1e-9:
        return [max(1., fit)]
    top = min(MAX_ZOOM, fit)
    return [MIN_ZOOM + (top - MIN_ZOOM) * k / (BYSTANDER_ZOOMS - 1) for k in range(BYSTANDER_ZOOMS)]


def _cover_px(head, crop):
    """Share of a head box [x1,y1,x2,y2] (px) inside a crop [x,y,w,h]."""
    x, y, w, h = crop
    iw = max(0., min(head[2], x + w) - max(head[0], x)); ih = max(0., min(head[3], y + h) - max(head[1], y))
    area = (head[2] - head[0]) * (head[3] - head[1])
    return iw * ih / area if area > 0 else 1.


def bystander_cuts(track, size, indices, others, aspect=WIDE):
    """(sample position, bystander number) whose head some render window cuts (partly in, partly out).

    The renderer picks ONE zoom anywhere in [135%, min(190%, fit)] from a hash fraction (longform_reframe.solve), not one
    of a few steps. Review 2026-10-05: a head that is half-cut for every zoom 1.364~1.431 passed all five equal steps,
    because it was wholly inside at 1.35 and wholly outside at 1.438. In solve the window at a frame is nested as the zoom
    grows — its centre (a rolling median of the region) does not depend on the zoom, every left/top edge candidate
    (centre − half size · region's far edge − size · source size − size · 0 · region's near edge) is non-decreasing in zoom
    and every right/bottom candidate non-increasing — so a head's share inside the window is continuous and non-increasing
    in zoom (tests/test_subject_agy_zoom_continuity.py checks that premise against solve itself). Then some zoom of the
    range cuts the head exactly when the share is above COVER_OUTSIDE at the lowest zoom and below COVER_INSIDE at the
    highest: a partial share at a tried zoom, or wholly inside at one and wholly outside at another (it must pass the
    half-cut band in between). The steps between the ends are kept as a cross-check.
    """
    from longform_reframe import solve
    w, h = size
    fit = fit_zoom(track, size, aspect)
    if fit < 1 - 1e-9:
        return []
    samples = [{'time': f / 60, 'boxes': [track[f]]} for f in range(len(track))]
    covers = {}
    for zoom in render_zooms(fit):
        solved = solve(w, h, samples, 'bystanders', min_zoom=zoom, max_zoom=zoom, margin=ROI_MARGIN, aspect=aspect)
        for j, frame in enumerate(indices):
            crop = solved['samples'][frame]['crop']
            for k, b in enumerate(others[j] or []):
                head = [b[0] * w, b[1] * h, b[2] * w, b[3] * h]
                covers.setdefault((j, k), []).append(_cover_px(head, crop))
    found = set()
    for key, shares in covers.items():
        partial = any(COVER_OUTSIDE < c < COVER_INSIDE for c in shares)
        crosses = max(shares) >= COVER_INSIDE and min(shares) <= COVER_OUTSIDE
        if partial or crosses:
            found.add(key)
    return sorted(found)


def _filled(indices, boxes, breaks=()):
    """Each sample's own region, or the one envelope() borrows for it (nearest visible sample of the same shot)."""
    breaks = sorted(set(breaks))
    def shot_of(f):
        return sum(1 for c in breaks if c <= f)
    known = [(i, b) for i, b in zip(indices, boxes) if b is not None]
    out = []
    for i, b in zip(indices, boxes):
        if b is None and known:
            same = [k for k in known if shot_of(k[0]) == shot_of(i)] or known
            b = min(same, key=lambda k: abs(k[0] - i))[1]
        out.append(b)
    return out


def avoid_bystanders(outcome, others, indices, nframes, size, breaks=(), aspect=WIDE):
    """Decision 5-3: a bystander head the window edge would cut in half is added to the region to keep.

    The subject's region only grows (it stays inside every window), so subject protection is unchanged; the
    zoom drops when bystanders must be kept (below 135% the renderer keeps exactly that region). Repeats until
    no bystander head is cut at any render zoom, or the region no longer fits a 16:9 window (then the whole
    frame — a 16:9 source then shows everyone whole).
    others[j]: bystander heads (normalised) at sample position j. Returns (outcome, report).
    """
    report = {'included': [], 'cut_before': 0, 'rounds': 0}
    if outcome['tier'] == 'scene' or not any(others):
        return outcome, report
    samples = list(outcome['samples'])
    included = set()
    for number in range(1 + sum(len(o or []) for o in others)):
        track = envelope(indices, samples, nframes, breaks)
        fit = fit_zoom(track, size, aspect)
        if fit < 1 - 1e-9:
            report.update(rounds=number, included=sorted(included))
            return full_frame(nframes, size, 'bystanders_exceed_frame', samples, aspect=aspect), report
        cuts = bystander_cuts(track, size, indices, others, aspect)
        if number == 0:
            report['cut_before'] = len(cuts)
        new = [c for c in cuts if c not in included]
        if not cuts or not new:
            report['rounds'] = number
            report['cut_after'] = len(cuts)
            if number == 0:
                return outcome, report
            exception = outcome['exception']
            if fit < MIN_ZOOM - 1e-9 and exception is None:
                exception = 'preserve_bystanders_below_minimum'
            report['included'] = sorted(included)
            return dict(outcome, fit=fit, track=track, samples=samples, exception=exception,
                        bystanders_included=len(included)), report
        base = _filled(indices, samples, breaks)
        for j, k in new:
            head = _pad(others[j][k], size)
            samples[j] = head if base[j] is None else _union(base[j], head)
            base[j] = samples[j]
        included.update(new)
    raise AssertionError('bystander inclusion did not converge')     # unreachable: every round adds at least one head


# ── the receipt the renderer already reads ────────────────────────────────
def receipt(cut, source_sha, size, nframes, outcome, evidence, recipe_key, *, frame_clock=None, cuts=()):
    """Same fields longform_reframe.from_focus_receipt / focus_kernel.validate consume."""
    start, fps = float(cut['start']), float(cut['fps'])
    w, h = size
    kind = 'scene' if outcome['tier'] == 'scene' else 'object'
    track = [{'frame_index': i, 't': start + i / fps, 'bbox': [b[0], b[1], b[2] - b[0], b[3] - b[1]], 'cut': False}
             for i, b in enumerate(outcome['track'])]
    middle = track[len(track) // 2]['bbox']
    scene = {'status': 'ok', 'start': start, 'fps': fps, 'nframes': nframes, 'cuts': list(cuts), 'source_identity': source_sha}
    if frame_clock is not None:
        scene['frame_clock'] = frame_clock
    selection = dict(evidence, engine=ALGORITHM, review_scope='visual_subject_v1', identity_verified=False,
                     tier=outcome['tier'], fit_zoom=outcome['fit'], exception=outcome['exception'], local_inference=0,
                     zoom_range=[MIN_ZOOM, MAX_ZOOM], **({} if cut_aspect(cut) == WIDE else {'window_aspect': list(cut_aspect(cut))}))
    if kind == 'object':
        # 무엇이 «확인» 인가(v4 · 사장님 결정 2026-10-06 밤 «medium 한 번만»): 지킬 영역은 AGY 첫 판독이 화면마다 직접 그린 머리·행동
        # 상자이고, 그 판독이 곧 확인이다 — v3 의 크롭 재확인(object_review.checks)은 없다. 그래서 같은 영수증의 object_review 는
        # status 'not_applicable' · checks [] 이고 selection_evidence.readings 1 · crop_checks 0 이 «재확인 없이 첫 판독으로 확인» 을
        # 말한다(렌더 관문 volcano_framing.selection_evidence_error 는 이 값으로 object_unverified 를 가른다). 영수증 모양은 v3 와 같게
        # 둔다(새 필수 칸 없음 · 서버 커널·렌더·옛 판이 그대로 읽는다). 이 뜻은 tests/test_subject_agy.py Flow.test_object_verified_means_the_first_reading_in_v4 가 고정한다.
        selection['object_verified'] = True
    return {'focus_key': cut['focus_key'], 'focus_status': 'accepted', 'source_identity': source_sha,
            'size': [w, h], 'content': [0, 0, w, h], 'measurement_version': 3, 'by': 'subject',
            'subject': [(middle[0] + middle[2] / 2) / w, (middle[1] + middle[3] / 2) / h],
            'subject_detected': kind != 'scene', 'scene_evidence': scene, '_recipe': recipe_key,
            'framing_subject': {'bbox': list(middle), 'track': track, 'origin': start, 'complete': True,
                                'kind': kind, 'selection_evidence': selection}}


def cut_aspect(cut):
    """컷의 출력 창 비율(숏폼 'aspect' [가로, 세로] 양의 정수) — 없으면 16:9(롱폼). 틀린 값은 고쳐 쓰지 않고 멈춘다."""
    a = cut.get('aspect')
    if a is None:
        return WIDE
    if (not isinstance(a, (list, tuple)) or len(a) != 2 or not all(type(v) is int and v > 0 for v in a)):
        raise ValueError('cut aspect must be [width, height] positive integers')
    return (a[0], a[1])


# ── one cut, start to receipt ─────────────────────────────────────────────
def run_cut(cut, source_sha, size, nframes, recipe_key, *, make_proxy, ask, grid='fps=60', origin=0., frame_clock=None):
    """Proxy → one AGY reading → arithmetic → receipt. No local inference, no second AGY reading (v4).

    make_proxy(name, vf, warmup=0.) -> (path, log)     one ffmpeg call starting `warmup` s before the cut; the caller owns files and caching
    ask(name, question(path), path) -> answer dict     the caller owns transport, receipts, refusal and resume
    Raises Unresolved (with a code) when this cut cannot be read; the caller records it.
    Returns (receipt, report). report counts every reading and names any exception.
    """
    fps = float(cut['fps']); context = cut.get('context') or ''; aspect = cut_aspect(cut)
    centres = sample_grid(nframes, fps)
    order = show_order(len(centres))
    warm = warmup_for(cut['start'])
    path, log = make_proxy('reading', proxy_filter(centres, order, grid=grid, scores=True, warmup=warm), warmup=warm)
    scores, flashes = scene_readout(log, origin + warm, fps, nframes, fresh_decode=True)
    flash_cuts = [c for c in hard_cuts(scores) if c in flashes]
    # 운영 컷 검사와 같은 자(2초 예열·320px·>0.20)로 잰 컷 안 장면 전환(섬광 모양 아님). 사장님 결정 5-4(2026-10-05 «여러 장면 컷 →
    # 그대로 · 컷 전체 같은 확대»): 그 컷을 멈추지 않는다(10-06 전에는 AGY 0회로 scene_boundary_inside_cut — 결정과 반대였고, 학생은
    # 고칠 길이 없어 같은 막힘을 되풀이했다). 판독은 컷 전체를 보고, 이 프레임들은 판독이 «다른 장면» 이라고 한 경계와 똑같이
    # 상자를 끊는 자리(breaks)가 된다 — 앞 장면 상자는 전환 앞까지 · 뒤 장면 상자는 전환부터 · 섞지 않음(envelope). 배율은 컷 전체에
    # 하나(fit_zoom · 렌더 longform_reframe.solve 도 컷에 하나)이고, 그 영역이 16:9 창 하나에 안 들면 전체 화면이다(plan).
    cuts = [c for c in hard_cuts(scores) if c not in flashes]
    report = {'readings': 0, 'checks': 0, 'pictures': 0, 'local_inference': 0, 'samples': len(centres)}
    reply = ask('reading', subject_question(path, len(centres), context), path)
    report['readings'] += 1; report['pictures'] += len(centres)
    try:
        kind, who, shown = subject_answer(reply, len(centres))
    except ValueError as error:
        note = reply.get('note') if isinstance(reply, dict) else None
        raise Unresolved('subject_not_determined', str(note or error), report=report) from error
    breaks = []
    if kind not in ('scene', 'absent'):
        # The reader saw another shot between two samples although ffmpeg's threshold
        # did not (measured: scores 0.044~0.055). Place the change on the score peak
        # and frame each side with its own boxes instead of refusing the cut.
        # Hard cuts above the production threshold (`cuts`, flashes excluded) break the
        # track the same way whatever shot numbers the reader gave (owner decision 5-4).
        breaks = sorted({c for _, _, c in shot_boundaries(shown, order, centres, scores) if c is not None} | set(cuts))
    flash_verdicts = flash_adjudication(flash_cuts, shown if kind not in ('scene', 'absent') else None, order, centres)
    outcome = plan(kind, shown, order, centres, nframes, size, breaks=breaks, aspect=aspect)
    bystanders = outcome.get('bystanders')
    if outcome['tier'] == 'scene' and not_16x9(size, aspect):
        # 16:9 가 아닌 원본(4:3·16:10 아카이브)은 배율 1.0 이어도 16:9 출력이 위아래(또는 좌우)를 잘라 낸다. v4 는 그 창을 AGY 에게
        # 다시 보이지 않는다(사장님 결정 2026-10-06 밤 · 컷마다 AGY 1번) — 창은 full_frame 이 정한 자리(판독이 본 주인공 영역의 한가운데,
        # 없으면 원본 한가운데) 그대로이고, 확인하지 않은 창이라는 사실을 예외 이름에 남긴다(status_error_receipt 와 같은 이름).
        outcome = dict(outcome, exception=str(outcome['exception']) + '_frame_unchecked')
    rows = to_time_order(shown, order)
    decision_kind = 'scene' if outcome['tier'] == 'scene' else 'object'
    decisions = [{'sample': k, 'kind': decision_kind, 'face_ids': [], 'speaker': 'not_applicable', 'reason': who,
                  'engine': ALGORITHM, 'frame_index': centres[k],
                  **({'box_2d_core': rows[k]['core'], 'box_2d_wide': rows[k]['wide']} if rows[k] and rows[k]['core'] else {})}
                 for k in range(len(centres))]
    evidence = {'decisions': decisions, 'who': who, 'answer_kind': kind,
                # 화면에 박힌 자막·로고 상자(판독이 따로 적은 것) — 렌더(shorts_framing.resolve)가 쓸 영역 가장자리에서 뺀다.
                'burned_in_xyxy_norm': burned_in_boxes(reply),
                'answer_note': str(reply.get('note') or '')[:400] if isinstance(reply, dict) else '',
                # 화면마다 판독이 본 것(주인공이 둘 이상이면 각자 머리 상자) — 누구를 지켰는지 나중에 대조할 수 있게 남긴다.
                'samples': [{'sample': k, 'frame_index': i, 'video_time': i / fps, 'source_time': float(cut['start']) + i / fps,
                             'see': str((rows[k] or {}).get('see') or '')[:120],
                             'heads_xyxy_norm': [[round(v, 4) for v in b] for b in ((rows[k] or {}).get('heads') or [])]}
                            for k, i in enumerate(centres)],
                # 크롭 재확인 칸 — v4 는 재확인이 없다(컷마다 AGY 1번). 칸 모양은 v3 영수증과 같게 둔다(빈 목록·빈 묶음).
                'object_review': {'status': 'not_applicable', 'engine': ALGORITHM, 'checks': [], 'checked_frames': [], 'widened': {}},
                # 판독이 본 장면 가운데 주인공이 한 번도 안 보인 장면(관중·외야 컷 등) — 그 구간도 같은 배율로 확대된다.
                # 처리 방식(그 컷 전체 화면 · 장면 단위로 나누라는 진단 · 지금처럼 이웃 장면 상자)은 사장님 결정 사항이다(README §6).
                'shots_without_subject': sorted({r['shot'] for r in rows if r and not r.get('core')}
                                                - {r['shot'] for r in rows if r and r.get('core')}),
                'samples_without_subject': sum(1 for r in rows if not (r and r.get('core'))),
                'readings': report['readings'], 'crop_checks': 0,
                # 주변 사람 반쪽 얼굴 피하기(사장님 결정 5-3): 마지막 계획에서 지킬 영역에 넣은 주변 사람 머리 · 넣기 전 잘리던 수 ·
                # 판독 답에서 모양이 틀려 버린 주변 사람 상자 수(주인공 상자는 엄격 — 버리지 않는다).
                'bystanders': bystanders,
                'bystander_boxes_dropped': sum(int((r or {}).get('others_dropped') or 0) for r in rows),
                'shot_breaks': breaks, 'shot_break_seconds': [round(c / fps, 3) for c in breaks],
                # 운영 컷 검사의 자로 잰 컷 안 장면 전환(결정 5-4 · 멈추지 않고 shot_breaks 에 넣어 장면마다 상자를 끊음 · 배율은 컷에 하나).
                # 렌더(longform_reframe.from_focus_receipt)는 scene_evidence.cuts 가 비어 있어야 받는다 — 장면마다 끊어 계획한 영역이라
                # 판독이 찾은 경계(shot_breaks)와 같이 이 칸에만 남긴다.
                'scene_cuts': list(cuts), 'scene_cut_seconds': [round(c / fps, 3) for c in cuts],
                # 섬광 모양 장면 점수(밝기가 튀었다 0.1초 안에 돌아옴): 판독의 장면 번호가 앞뒤 같으면 무시 · 다르면 shot_breaks 로 끊긴다.
                'flash_candidates': [dict(v, seconds=round(v['frame'] / fps, 3)) for v in flash_verdicts]}
    report.update(breaks=breaks, tier=outcome['tier'], fit=outcome['fit'], exception=outcome['exception'], who=who, kind=kind, checks_detail=[])
    return receipt(cut, source_sha, size, nframes, outcome, evidence, recipe_key, frame_clock=frame_clock), report


# ── a cut that could not be read: that cut only, the rest continue (owner decision 5-1, 2026-10-05 · widened 2026-10-06) ──
STATUS_ERROR_EXCEPTION = 'agy_status_error_full_frame'
# 사람이 고칠 것이 없는 «그 컷 하나의» 실패 → 그 컷만 확대하지 않는 전체 화면 영수증으로 끝내고 작업은 다음 단계(제작)로 간다.
# 10-06 에 결정 5-1(status ERROR)의 처리를 이 실패들로 넓혔다 — 학생 실측: 이런 컷 하나가 작업 전체를 need_input 으로 세웠고,
# 학생은 고칠 것이 없어 «다시» 를 눌러도 같은 막힘이었다(최근 24시간 막힌 48명 중 증명 실패 12 · 답 형식 8 · 주인공 못 정함 6 ·
# 2일 동안 longform_seed 20번 넘게 오간 사람 95명). AGY 에 다시 묻지 않는다(전역 규칙 6-2) — 영수증이 남아 이어 할 때도 그대로 쓴다.
# 값 = 영수증 이유 글(사람 말 · {at} = 어느 판독). 여기 없는 실패(거부·관문·이 PC 의 AGY/ffmpeg 환경·원본 파일·실행기 규격)는
# 컷 탓이 아니거나 사람이 고칠 수 있어 지금처럼 막는다(subject_agy_run).
CUT_FAILURE_TEXT = {
    'agy_status_error': 'AGY 가 이 컷의 {at}을 오류(status ERROR)로 끝냈다',
    'agy_call_failed': 'AGY 의 {at} 호출이 쓸 답 없이 끝났다(시간 초과·빈 답 등 · 한도·로그인 거부 아님)',
    'agy_view_unproven': 'AGY 가 {at}에서 이 컷의 사본만 열었다는 도구 기록이 없다',
    'agy_answer_invalid': 'AGY 의 {at} 답이 규격과 달랐다',
    'subject_not_determined': 'AGY 가 {at}에서 주인공을 어느 화면에도 그리지 못했다',
    'proxy_failed': '{at}용 작은 사본을 ffmpeg 로 만들지 못했다',
    'proxy_timeout': '{at}용 작은 사본 만들기가 시간 안에 끝나지 않았다',
    'proxy_frames_short': '{at}용 작은 사본의 화면 수가 요청과 달랐다',
    'probe_failed': '{at}용 작은 사본을 ffprobe 로 읽지 못했다',
    'selection_invalid': '판독으로 만든 영수증이 검사를 통과하지 못했다',
    # 사장님 결정(10-06 16:4x «멈추면 안된다니까»): 한도·속도·로그인 거부(전송의 RunServiceRefused · 거부 표식 · 관문의 한도/로그인)
    # 뒤에도 피사체 단계를 멈추지 않는다 — 거부를 받은 순간부터 AGY 요청은 하나도 더 보내지 않고(전역 규칙 6-2) 남은 컷은 이 까닭으로
    # 전체 화면이다. 거부 종류는 영수증 cut_failure.refused_as 에 사실로 남긴다(subject_agy_run).
    'agy_refused': 'AGY 가 한도·속도·로그인 등의 이유로 거절해 이 컷은 판독하지 않았다(거절 뒤 AGY 요청 없음)',
}


def failure_exception(code):
    """실패 까닭 → 영수증 예외 이름(«까닭_full_frame» · status ERROR 는 10-05 이름 그대로)."""
    if code not in CUT_FAILURE_TEXT:
        raise ValueError(f'not a per-cut failure: {code!r}')
    return STATUS_ERROR_EXCEPTION if code == 'agy_status_error' else code + '_full_frame'


# 실패가 난 자리 → 사람 말. v4 의 AGY 호출은 첫 판독(reading) 하나뿐이다 — 그 밖의 자리는 판독 뒤 영수증 검사(validate · subject_agy_run)와
# 거절 뒤 시작하지 않은 컷(not_started)이다(v3 의 크롭 재확인·전체 화면 창 재확인 자리는 없어졌다).
AT_TEXT = {'reading': '첫 판독', 'validate': '영수증 검사', 'not_started': '판독 시작 전'}


def _at_text(at):
    at = str(at or 'reading')
    return AT_TEXT.get(at, at)


def status_error_receipt(cut, source_sha, size, nframes, recipe_key, reply=None, *, message='', at='reading', frame_clock=None,
                         code='agy_status_error', facts=None):
    """This cut could not be read for a reason nobody can fix by hand (code in CUT_FAILURE_TEXT · default: AGY status ERROR
    with quota and login still left — the 10-05 name is kept so the receipts of that day stay what they are).
    facts: what is known about the failure (e.g. the refusal kind `refused_as` and where it was seen `refusal_seen` for
    'agy_refused') — stored as they are in selection_evidence.cut_failure.

    Decision 5-1 says only that cut fails and production goes on. "Fails" here means: the cut is not zoomed —
    a full-frame (scene tier, 1.0×) receipt that the renderer already accepts — and the exception name says why.
    AGY is not asked again for this cut (global rule 6-2: no automatic retry); the receipt is reused on resume.
    reply: the first reading's answer if it had already arrived (the failure came after it — the receipt failed its
    check). Its subject boxes only place the 16:9 window on a non-16:9 source; they never zoom. A source that is not 16:9 is cut by
    the 16:9 output even at 1.0× and that window was not checked by AGY here, so the name says so.
    """
    fps = float(cut['fps'])
    centres = sample_grid(nframes, fps)
    order = show_order(len(centres))
    kind, who, shown = None, FULL_FRAME_WHO, [None] * len(centres)
    if isinstance(reply, dict):
        try:
            kind, who, shown = subject_answer(reply, len(centres))
        except ValueError:
            kind, who, shown = None, FULL_FRAME_WHO, [None] * len(centres)
    rows = to_time_order(shown, order)
    samples = [_pad(r['core'], size) for r in rows if r and r.get('core')]
    aspect = cut_aspect(cut)
    outcome = full_frame(nframes, size, failure_exception(code), samples or None, aspect=aspect)
    if not_16x9(size, aspect):
        outcome['exception'] = str(outcome['exception']) + '_frame_unchecked'
    reason = ('확대하지 않고 전체 화면을 지킨다(' + str(outcome['exception']) + ') — '
              + CUT_FAILURE_TEXT[code].replace('{at}', _at_text(at)) + '(사장님 결정 5-1 · 자동 재시도 없음)')[:400]
    decisions = [{'sample': k, 'kind': 'scene', 'face_ids': [], 'speaker': 'not_applicable', 'reason': reason,
                  'engine': ALGORITHM, 'frame_index': centres[k]} for k in range(len(centres))]
    evidence = {'decisions': decisions, 'who': who, 'answer_kind': code,
                'answer_note': '', 'reading_kind': kind,
                'samples': [{'sample': k, 'frame_index': i, 'video_time': i / fps, 'source_time': float(cut['start']) + i / fps,
                             'see': str((rows[k] or {}).get('see') or '')[:120],
                             'heads_xyxy_norm': [[round(v, 4) for v in b] for b in ((rows[k] or {}).get('heads') or [])]}
                            for k, i in enumerate(centres)],
                'object_review': {'status': 'not_applicable', 'engine': ALGORITHM, 'checks': [], 'checked_frames': [], 'widened': {}},
                # 실패 까닭 한 자리(subject_agy_run.status_error_notice 가 진단 알림으로 읽는다) · status ERROR 는 10-05 칸도 같이(옛 판독기).
                'cut_failure': dict(facts or {}, code=code, at=at, message=str(message or '')[:300], automatic_retry=False),
                **({'agy_status_error': {'at': at, 'message': str(message or '')[:300], 'automatic_retry': False}}
                   if code == 'agy_status_error' else {}),
                'readings': 1 if reply is not None else 0, 'crop_checks': 0, 'bystanders': None,
                'bystander_boxes_dropped': 0, 'shot_breaks': [], 'shot_break_seconds': [], 'flash_candidates': [],
                'shots_without_subject': [], 'samples_without_subject': sum(1 for r in rows if not (r and r.get('core')))}
    return receipt(cut, source_sha, size, nframes, outcome, evidence, recipe_key, frame_clock=frame_clock)
