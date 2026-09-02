"""EDL + 비트별 TTS → ffmpeg으로 컷 편집·오디오 교체·새 대본 자막을 구운 최종 mp4.

각 비트의 소스 구간을 그 비트 나레이션(TTS) 길이만큼 **정상 속도(1배속)** 로
재생한다. 자막이 정상 속도로 읽히도록, 영상 길이는 배속으로 압축하지 않고
나레이션 읽는 시간에 맞춰 늘린다(설계: 대본 못 줄이면 클립을 길게, 20~30초).
구간 원본이 나레이션보다 짧으면 소스를 루프(-stream_loop)해서 부족분을 채운다.

새 대본은 화면 하단 불투명 바 위에 **한 줄씩 순차로(progressive)** 굽는다. 바가
원본에 박힌 소각 자막을 가리고, 그 위에 새 나레이션이 읽는 속도로 한 줄씩 넘어간다.
한글 폰트가 없는 환경(폰트 미해결)에서는 자막을 생략하고 영상만 렌더한다.
concat 후 원본 오디오를 제거하고 비트별 TTS를 이어붙인 트랙으로 교체한다.
"""
import os
import re
import shutil
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

from PIL import ImageFont

# 출력 규격(숏폼 세로). 소스 해상도가 달라도 여기로 통일해야 concat -c copy가 안전.
_OUT_W, _OUT_H = 1080, 1920
# ★x264 프리셋: 기본 medium(최종). 미리보기는 preview_preset()가
# veryfast로 낮춰 6분→~1.5분. ★스레드로컬인 이유(오류검사에서 잡음): run_preview와
# run_render는 각각 BackgroundTasks 스레드에서 돈다 — 모듈 전역이면 미리보기가 켠
# veryfast가 동시에 도는 **최종 렌더**까지 저화질로 오염시키는 레이스가 난다.
# assemble 호출 트리는 스레드 내부 분기가 없으므로(실측: 이 모듈에 ThreadPool 없음)
# 스레드로컬이 정확히 "이 렌더만" 바꾼다.
import contextlib as _contextlib
import threading as _threading

_preset_local = _threading.local()
# CRF(화질): 낮을수록 고화질. 최종은 16(원본에 아주 가깝게), 미리보기는 28(빠르고 작게).
# ★CRF 미지정 시 libx264 기본이 23이라 최종도 흐릿하고, 자막 오버레이 재인코딩으로 세대손실이
#   더 쌓였다(2026-07-27 사장님: "최종이 원본보다 안 좋다"). 프리셋과 같은 스레드로컬로 둬
#   미리보기(veryfast/28)와 최종(slow/16)이 서로 오염되지 않게 한다.
#   2026-07-27 2차 상향: 18→16 + medium→slow(같은 CRF에서 압축효율↑=디테일 더 보존). 최종만
#   느려지고(미리보기는 veryfast 유지) 화질이 원본에 더 붙는다. 용량 크면 17~18로 되돌린다.
#
# ★2026-07-30 slow→medium 되돌림(사장님 지시 — 최종렌더 8~10분 체감).
#   preset은 "얼마나 오래 고민해 압축하나"이고 화질 목표는 CRF가 정한다 — CRF 16을 그대로
#   두므로 x264는 같은 품질을 노리고 인코딩한다. 차이는 **속도와 용량**에 나타난다:
#   medium은 1.5~2배 빠르고 파일이 10~20% 커진다. 07-27의 화질 상향분은 CRF 18→16이
#   대부분이고 그건 유지된다. 소셜 업로드는 플랫폼이 재인코딩하므로 체감차는 더 줄어든다.
#   ⚠️ 되돌릴 땐 이 한 줄만 "slow"로 바꾸면 된다(용량이 문제면 CRF 17~18이 먼저다).
_FINAL_CRF, _PREVIEW_CRF = "16", "28"
_FINAL_PRESET = "medium"


# ffmpeg 스레드 상한(2026-07-30) — 워커를 여러 개 띄워 고객 작업을 동시에 처리하려면
# 인코딩 하나가 코어를 다 먹어선 안 된다. 0은 "ffmpeg가 알아서 전부 사용"이라, 렌더 2건이
# 겹치면 서로를 굶기며 둘 다 느려진다. 워커 수만큼 코어를 나눠 갖게 상한을 둔다.
#
# ★2026-08-06 기본값을 코어수/워커수로 자동 산정한다. 예전 기본은 0(무제한)이었는데,
#   워커가 1개일 땐 그게 맞았지만 **워커 3개로 늘어난 뒤로는 셋이 각자 전 코어를 잡으려
#   들어 서로를 굶긴다**(4코어에 12스레드 요구 = 컨텍스트 스위칭 낭비). 서버 env에
#   FFMPEG_THREADS를 안 넣어두면 계속 0이라, 잊어도 안전하도록 코드가 기본을 준다.
#   env로 명시하면 그게 항상 이긴다(0을 넣으면 종전처럼 무제한).
#   ★하한 2: 코어÷워커를 그대로 쓰면 4코어/3워커 = 1스레드가 되는데, **셋이 동시에
#   렌더하는 건 드문 일**이라 평소 렌더까지 1스레드로 기어가면 손해가 더 크다. x264는
#   스레드 2개만 돼도 1개보다 확연히 빠르고, 겹칠 때의 과점유는 2 상한으로 충분히 막힌다.
#   ★2026-08-27 이름 어긋남 수정 — **워커 수를 정하는 곳과 읽는 곳이 달랐다.**
#   워커 개수를 실제로 정하는 건 deploy/worker_autoscale.sh이고 그건 SHORTS_WORKERS를
#   본다. 그런데 여기선 WORKER_COUNT를 봤다 — 서버 env에 그 이름은 없으므로 **워커가
#   8개인데 계속 3개인 줄 알고** 스레드를 산정했다(8÷3=2 → 8워커×2 = 16스레드 요구 vs
#   8코어 = 2배 과점유). 자동조정 스크립트와 **같은 이름을 같은 순서로** 읽어 한 군데서만
#   정해지게 한다(CLAUDE.md 0순위-B: 같은 결정을 두 번 적지 마라).
#   폴백 순서도 worker_autoscale.sh와 맞춘다: SHORTS_WORKERS → 없으면 코어-2(3~6로 묶음).
def _worker_count():
    """지금 서버에 떠 있을 워커 수 — deploy/worker_autoscale.sh와 **같은 규칙**으로 센다.

    우선순위: SHORTS_WORKERS(사람이 명시) → WORKER_COUNT(옛 이름, 하위호환)
              → 자동계산(코어-2, 3~6). 스크립트가 바뀌면 여기도 같이 고쳐야 한다."""
    for name in ("SHORTS_WORKERS", "WORKER_COUNT"):
        raw = os.getenv(name, "")
        if raw:
            try:
                n = int(raw)
            except ValueError:            # 오타는 무시하고 다음 후보로
                continue
            if n >= 1:
                return min(12, n)         # 스크립트의 오타 안전선(1~12)과 동일
    cores = os.cpu_count() or 1
    return max(3, min(6, cores - 2))      # 스크립트의 자동 정책과 동일


def _default_ffmpeg_threads():
    try:
        cores = os.cpu_count() or 1
        workers = _worker_count()
        return max(2, cores // max(1, workers))
    except Exception:                     # noqa: BLE001 — 산정 실패는 무제한으로(종전 동작)
        return 0


_FFMPEG_THREADS = int(os.getenv("FFMPEG_THREADS", "") or _default_ffmpeg_threads())


# ── 중간 산출물은 "빠르게", 최종 1회만 "품질"(2026-07-31 렌더 단축) ──────────────
# 지금까지 서브클립·비트클립까지 전부 최종 품질(CRF 16 · medium)로 인코딩했다. 그런데
# 자막 번인(_burn_captions)이 어차피 전체를 **다시** 인코딩하므로, 중간 결과의 압축률에
# 공들이는 시간은 그대로 버려진다. 화질을 정하는 건 마지막 패스다.
#   중간 = veryfast · CRF 14 → 인코딩 시간이 크게 줄고(세대손실은 CRF 14라 사실상 무시),
#   최종 = 기존 그대로(preset medium · CRF 16) → 산출물 화질 목표 불변.
# ⚠️ 중간 파일이 조금 커진다(CRF 14). 디스크가 빠듯하면 _MID_CRF를 16으로 올려라.
# 되돌리기: MID_PRESET=medium MID_CRF=16 (환경변수) — 코드 수정 없이 원복된다.
_MID_PRESET = os.getenv("MID_PRESET", "veryfast")
_MID_CRF = os.getenv("MID_CRF", "14")


def _mid_preset():
    """중간 패스 preset — 미리보기 모드처럼 전체 preset이 낮춰진 경우엔 그걸 따른다."""
    cur = getattr(_preset_local, "value", None)
    return cur if cur else _MID_PRESET


def _mid_crf():
    cur = getattr(_preset_local, "crf", None)
    return cur if cur else _MID_CRF


def _threads_args():
    """['-threads','N'] 또는 [] — 인코딩 명령에 끼워 넣는다."""
    return ["-threads", str(_FFMPEG_THREADS)] if _FFMPEG_THREADS > 0 else []


def _preset():
    return getattr(_preset_local, "value", _FINAL_PRESET)


def _crf():
    return getattr(_preset_local, "crf", _FINAL_CRF)


@_contextlib.contextmanager
def preview_preset(preset="veryfast", crf=_PREVIEW_CRF):
    """이 블록(현재 스레드) 안의 assemble 인코딩만 빠른 프리셋·낮은 화질로. 끝나면 원복."""
    prev = getattr(_preset_local, "value", None)
    prev_crf = getattr(_preset_local, "crf", None)
    _preset_local.value = preset
    _preset_local.crf = crf
    try:
        yield
    finally:
        if prev is None:
            del _preset_local.value
        else:
            _preset_local.value = prev
        if prev_crf is None:
            if hasattr(_preset_local, "crf"):
                del _preset_local.crf
        else:
            _preset_local.crf = prev_crf
from . import font_glyphs as _fg

_FONT_DIR = Path(__file__).parent / "static" / "fonts"
# 고른 폰트를 버리고 기본폰트로 되돌리는 문턱(못 그리는 글자 비율).
# 낮추면 희귀 글자 하나에 글꼴이 통째로 바뀌고, 1.0으로 두면 한 글자만 그려져도 통과한다.
# 0.5 = 절반 넘게 두부면 그 폰트는 이 문구에 못 쓰는 것으로 본다.
_FONT_FALLBACK_RATIO = 0.5
# 반중복탐지 회피(2026-07-14) — 말 안 해도 항상 적용. 화질 오염 없는(비가역 손상X)
# 것만 자동화: ①전 비트 기본 크롭+줌(살짝 확대, 원본과 프레임 구도가 달라짐)
# ②중요 비트(훅·반전)만 서서히 확대되는 켄번즈 줌(더 눈에 띄는 변형+시선 유도 효과 겸함).
# 좌우반전은 제외 — 원본 화면 속 글자·로고가 있으면 뒤집혀서 오염돼 보일 위험이 있어
# "화질 오염 없이"라는 기준에 안 맞는다고 판단(2026-07-14).
# ★2026-09-02 사장님 지시로 **꺼졌다**("반중복? 그 확대를 꺼").
#   이 확대는 사장님이 요청한 기능이 아니다 — 2026-07-14 커밋 424974989에서
#   "말 안 해도 항상 적용"으로 넣은 자동 효과였고, 그 결과:
#     · 원본 구도가 늘 잘려 나갔다(왼쪽·오른쪽 물건이 화면 밖으로).
#     · 5단계 자막제거 화면의 BEFORE(원본)/AFTER(조립본)가 서로 다른 배율이 돼
#       "자막제거를 하면 확대된다"로 보였다.
#   되돌리려면 SHORTS_ANTIDUP_ZOOM=1 (옛 값 1.04/1.10으로 복귀).
_ANTIDUP_ZOOM_ON = os.environ.get("SHORTS_ANTIDUP_ZOOM", "0") not in ("0", "", "off", "false")
_BASE_ZOOM = 1.04 if _ANTIDUP_ZOOM_ON else 1.0      # 전 비트 기본 확대율(정적, 저비용)
_KENBURNS_ZOOM = 1.10 if _ANTIDUP_ZOOM_ON else 1.0  # 중요 비트 최종 확대율(동적)
_IMPORTANT_ROLES = {"훅", "반전"}  # edit_plan.py _REQUIRED_ROLES와 동일 어휘


def _important_beat_indices(beats):
    """훅·반전 롤 비트만 켄번즈 대상. 스크립트모드(produce.html 2단계)는 role이
    안 채워지므로(edit_plan._SCRIPTED_PROMPT가 role을 요구 안 함) 그때는 첫 비트
    (오프닝 훅 역할)만 켄번즈로 폴백한다."""
    idxs = {b["beat_idx"] for b in beats if (b.get("role") or "") in _IMPORTANT_ROLES}
    if not idxs and beats:
        idxs = {beats[0]["beat_idx"]}
    return idxs


def _kenburns_vf(duration_sec, fps=30, zoom_end=_KENBURNS_ZOOM):
    """서서히 확대되는 줌(켄번즈) vf. zoompan은 self-referencing 'zoom+step' 방식이
    비디오 입력(정지이미지 아님)에서 상태가 안 이어져 매 프레임 그대로 있는 버그가
    있어(2026-07-14 로컬 실측: 89px→89px, 안 움직임), 출력 프레임번호 'on'을 직접
    식에 넣는 방식으로 고쳤다('on' 사용 시 89px→97px로 실제 확대 확인됨)."""
    # ★확대가 꺼져 있으면(SHORTS_ANTIDUP_ZOOM=0, 2026-09-02 기본) 켄번즈도 돌지 않는다.
    #   zoom_end=1로 두면 1.3배 확대했다가 다시 줄이는 헛일이라 화질만 손해다.
    #   판정은 여기 한 곳 — 호출부 3곳이 각자 분기하면 반드시 어긋난다(0순위-B).
    if zoom_end <= 1.0001:
        return _base_zoom_vf(None)
    frames = max(1, round(duration_sec * fps))
    step = (zoom_end - 1) / frames
    pre_w, pre_h = int(_OUT_W * 1.3), int(_OUT_H * 1.3)  # zoompan 전에 여유있게 확대해둬야 크롭 여백이 남는다
    return (
        f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
        f"zoompan=z='min(1+{step:.8f}*on,{zoom_end})':d=1:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={_OUT_W}x{_OUT_H}:fps={fps}"
    )


def scene_zoom_of(beat):
    """장면 하나에 사장님이 지정한 확대(6단계 미리보기에서 끌어 맞춘 것)를 꺼낸다.
    → (zoom, pan_x, pan_y). 지정이 없으면 (1.0, 0, 0) = 종전 그대로.

    ★값의 뜻은 **화면과 한 벌**이다(0순위-B). 미리보기는 배경에 scale(Z)+translate(t)를
      걸고, 저장할 때 이동을 **화면 폭 대비 비율**로 정규화해 보낸다:
          pan = (Z*t) / 컨테이너폭        (오른쪽·아래가 +)
      그래서 한계는 |pan| <= (Z-1)/2 이고, 이 함수도 같은 식으로 가둔다.
    ★여기서만 읽는다 — 크롭을 만드는 곳이 여럿이라 각자 파싱하면 반드시 어긋난다."""
    if not isinstance(beat, dict):
        return 1.0, 0.0, 0.0
    z = beat.get("scene_zoom")
    try:
        z = float(z) if z is not None else 1.0
    except (TypeError, ValueError):
        z = 1.0
    z = max(1.0, min(3.0, z))
    if z <= 1.0001:
        return 1.0, 0.0, 0.0
    lim = (z - 1.0) / 2.0
    def _pan(key):
        try:
            v = float(beat.get(key) or 0.0)
        except (TypeError, ValueError):
            v = 0.0
        return max(-lim, min(lim, v))
    return z, _pan("scene_pan_x"), _pan("scene_pan_y")


# ── 🔎 장면 강조(원형 돋보기 / 스포트라이트, 2026-08-30 사장님) ──────────────────
# 사장님 요청: "장면꾸미기에서 강조하고싶은것들 수동하게". 레퍼런스 화면처럼 **원 하나로
# 시선을 끄는** 연출이다. 확대(scene_zoom)와는 다른 물건 — 확대는 화면 전체 구도를 바꾸고,
# 강조는 구도를 그대로 둔 채 그 위에 원을 얹는다. 그래서 강조는 base 크롭 **다음**에 온다.
_HL_GROW = 0.35          # 등장할 때 원이 커지는 시간(초). 사장님 확정: "뜰 때 커지는 애니메이션까지"
_HL_DARK = 0.60          # 스포트라이트에서 원 **밖**을 어둡게 하는 정도(0~1)
_HL_RING = 3             # 흰 테두리 두께(px, 반지름 기준)


def scene_hl_of(beat):
    """장면 하나에 사장님이 지정한 강조를 꺼낸다 → dict 또는 None(=강조 없음).

    ★해석은 **여기 한 곳에서만** 한다(0순위-B) — 화면(미리보기)과 렌더가 같은 뜻으로
      읽어야 한다. 저장 형식은 화면 크기와 무관한 **비율**이다:
        cx, cy : 화면 폭·높이 대비 원 중심 (0~1)
        r      : 화면 **폭** 대비 반지름 (0~1) — 폭 기준이라 세로 영상에서도 원이 원이다
        zoom   : 원 안 확대 배율(mode=zoom일 때만 의미)
        mode   : 'zoom'(원 안을 확대) | 'spot'(원 밖을 어둡게)
    """
    if not isinstance(beat, dict):
        return None
    hl = beat.get("scene_hl")
    if not isinstance(hl, dict) or not hl.get("on"):
        return None
    def _f(key, dflt, lo, hi):
        try:
            v = float(hl.get(key))
        except (TypeError, ValueError):
            v = dflt
        return max(lo, min(hi, v))
    mode = "spot" if str(hl.get("mode") or "zoom") == "spot" else "zoom"
    shape = "round" if str(hl.get("shape") or "circle") == "round" else "circle"
    # 반지름 하한 0.06 — 이보다 작으면 화면에서 점으로 보여 아무것도 강조가 안 된다.
    return {"mode": mode, "shape": shape,
            "cx": _f("cx", 0.5, 0.0, 1.0), "cy": _f("cy", 0.5, 0.0, 1.0),
            "r": _f("r", 0.28, 0.06, 0.9), "zoom": _f("zoom", 2.0, 1.1, 4.0)}


# 모양 → 거리식의 지수. ★모양을 **하나의 식**으로 다룬다(0순위-B) — 모양마다 따로 식을 적으면
#   테두리·마스크·미리보기가 각자 다른 모양을 그리게 된다.
#     n=2 → 원,  n=4 → 둥근 네모(스퀘어클). 나중에 네모(n=12)를 더해도 이 표만 늘리면 된다.
_HL_SHAPE_N = {"circle": 2, "round": 4}


def _hl_dist(cx, cy, r, shape):
    """중심에서 얼마나 떨어졌나 — **테두리에서 정확히 1**이 되는 값(ffmpeg 식 문자열)."""
    n = _HL_SHAPE_N.get(shape, 2)
    return (f"pow(pow(abs(X-{cx})/{r},{n})+pow(abs(Y-{cy})/{r},{n}),{1.0 / n:.6f})")


def _hl_px(hl):
    """비율 → 픽셀(최종 출력 좌표계). 원이 화면 밖으로 나가도 ffmpeg가 알아서 자른다."""
    cx = int(round(hl["cx"] * _OUT_W))
    cy = int(round(hl["cy"] * _OUT_H))
    r = max(8, int(round(hl["r"] * _OUT_W)))
    return cx, cy, r


def highlight_fc(beat, base_vf, grow=True):
    """base_vf(기존 크롭/줌 체인) 뒤에 강조를 얹은 **filter_complex 문자열**. 강조가 없으면 None.

    반환값을 쓰는 쪽은 `-vf base_vf` 대신 `-filter_complex <이것> -map [out]`을 쓴다.

    ★왜 geq를 프레임마다 돌리지 않나 — 실측(2026-08-30): 1080x1920 전면 geq는 3초 소스에
      13.0초(4.3배 느림)였다. 마스크를 **한 장만** 만들고 loop로 재사용하니 0.86초
      (0.28배) — **15배** 빠르다. 라이브 렌더에 얹을 수 있는 유일한 형태다.
    ★등장 성장은 마스크를 다시 그리는 게 아니라 **다 만든 원을 scale로 키운다**(eval=frame).
      그래서 커지는 동안 비용이 0이다.
    grow=False — 한 비트가 컷 여러 개로 쪼개졌을 때 **두 번째 컷부터**. 안 그러면 컷마다
      원이 다시 톡톡 튀어 사장님이 "왜 여러 번 나오냐"고 보게 된다.
    """
    hl = scene_hl_of(beat)
    if not hl:
        return None
    cx, cy, r = _hl_px(hl)
    d = r * 2
    sh = hl["shape"]
    k = f"min(1,max(0.2,t/{_HL_GROW}))" if grow else "1"
    # 테두리·마스크 모두 **같은 거리식**을 쓴다 → 모양을 바꿔도 둘이 어긋날 수 없다.
    # (테두리 조각은 d×d 캔버스라 중심이 (r,r)이다)
    _dl = _hl_dist(r, r, r, sh)                     # 조각 안 좌표 기준
    _dg = _hl_dist(cx, cy, r, sh)                   # 전체 화면 좌표 기준
    ring = (f"color=c=white:s={d}x{d}:d=1,format=rgba,"
            f"geq=r=255:g=255:b=255:"
            f"a='255*clip(({_HL_RING}-abs((1-{_dl})*{r}))/1.5,0,1)',"
            f"loop=loop=-1:size=1,setpts=N/30/TB[ring0];"
            f"[ring0]scale=w='{d}*{k}':h='{d}*{k}':eval=frame[rg];")
    at = f"x='{cx}-{d}*{k}/2':y='{cy}-{d}*{k}/2'"
    parts = [f"[0:v]{base_vf}[base];", ring]
    if hl["mode"] == "spot":
        # 원 밖을 어둡게. 전면 마스크지만 **한 장만** 계산하고 loop로 돌린다(위 실측 참고).
        parts.append(
            f"color=c=black:s={_OUT_W}x{_OUT_H}:d=1,format=rgba,geq=r=0:g=0:b=0:"
            f"a='255*{_HL_DARK}*clip(({_dg}-1)*{r}/2+0.5,0,1)',"
            f"loop=loop=-1:size=1,setpts=N/30/TB"
            + (f",fade=t=in:st=0:d={_HL_GROW}:alpha=1" if grow else "") + "[dark];")
        parts.append("[base][dark]overlay=0:0:shortest=1[o1];")
    else:
        m = hl["zoom"]
        # 원 안만 확대 — 전체를 m배로 키운 뒤 **그 점 둘레만** d×d로 잘라 원 마스크를 씌운다.
        parts.append(
            f"[base]split[a][b];"
            f"[b]scale=iw*{m}:ih*{m},crop={d}:{d}:{m}*{cx}-{r}:{m}*{cy}-{r},format=rgba[pat];"
            f"color=c=black:s={d}x{d}:d=1,format=gray,"
            f"geq=lum='255*clip((1-{_dl})*{r}/2+0.5,0,1)',"
            f"loop=loop=-1:size=1[msk];"
            f"[pat][msk]alphamerge,scale=w='{d}*{k}':h='{d}*{k}':eval=frame[cut];"
            f"[a][cut]overlay={at}:shortest=1[o1];")
    parts.append(f"[o1][rg]overlay={at}:shortest=1[out]")
    return "".join(parts)


def _crop_xy(zoom, pan_x, pan_y, base_w, base_h):
    """확대된 화면(base_w×base_h)에서 잘라낼 위치. 중앙에서 pan 만큼 옮긴다.
    유도: 화면 폭 대비 pan 만큼 그림이 움직였으므로 잘라내는 창은 반대로 -pan 이동.
    ★검산 완료 — pan이 한계(±(Z-1)/2)일 때 crop이 정확히 0 또는 max에 닿는다."""
    max_x = max(0, base_w - _OUT_W)
    max_y = max(0, base_h - _OUT_H)
    x = max_x / 2.0 - _OUT_W * pan_x
    y = max_y / 2.0 - _OUT_H * pan_y
    return int(round(max(0, min(max_x, x)))), int(round(max(0, min(max_y, y))))


def _base_zoom_vf(beat=None):
    """일반 비트 기본 크롭+줌(정적, 저비용) — 원본과 프레임 구도만 살짝 달라지게.
    ★beat에 사장님이 6단계에서 맞춘 확대가 있으면 **그 구도 그대로** 잘라낸다
      (2026-08-30 "장면 바꾸기에서 수정한 대로 나오게"). 없으면 종전과 완전히 같다."""
    zoom, pan_x, pan_y = scene_zoom_of(beat)
    if zoom <= 1.0001:
        w, h = int(_OUT_W * _BASE_ZOOM), int(_OUT_H * _BASE_ZOOM)
        return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"
    # 사장님 지정 확대 — 기본 줌은 얹지 않는다(지정한 배율이 곧 최종 구도다)
    w, h = int(_OUT_W * zoom), int(_OUT_H * zoom)
    x, y = _crop_xy(zoom, pan_x, pan_y, w, h)
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={_OUT_W}:{_OUT_H}:{x}:{y}")
# 하단 자막 바(원본 소각 자막을 덮는다) + 한 줄 자막 스타일.
_BAR_H = 450
_CAP_FONTSIZE = 78      # 짧은 1줄 구절이라 여유 있음 → 키움

# ★꾸미기 UI가 쓰는 기준 폭(produce.html의 VIDEO_W). 미리보기·썸네일은 자막/헤드카피 px를
#   **이 폭 기준**으로 축소해 그린다(scale = PREVIEW_W/VIDEO_W).
_UI_REF_W = 720

# 글자가 화면 밖으로 잘리지 않게 남기는 안전 여백(2026-08-30). 플랫폼이 화면비에 맞춰
# 확대해 보여주므로 폭을 꽉 채우면 양끝이 잘린다 — 헤드카피·자막이 이 값을 함께 쓴다.
_SAFE_W = 0.86


def _ui_px(v, default, zero_ok=False):
    """꾸미기 화면에서 온 px 값을 출력 해상도로 환산한다(2026-07-30 사장님 제보:
    "썸네일 비율보다 실제 렌더 자막이 더 작게 나온다").

    뿌리: 2026-07-24 f08c18aec가 출력을 720x1280 → 1080x1920으로 올리면서 **내부 기본값은
    전부 ×1.5** 했지만(_CAP_FONTSIZE 52→78, size 64→96, outline_w 6→9, shadow_d 3→5,
    box_pad 16→24, _BAR_H 300→450) **UI에서 넘어온 값은 환산하지 않았고**, 프론트의
    VIDEO_W도 720에 남았다. 그래서 사장님이 슬라이더로 정한 크기는 미리보기에선 720폭
    기준으로 커 보이고 실제 렌더에선 1080폭에 그려져 정확히 720/1080=67%로 작아졌다.

    → UI 값만 ×(_OUT_W/_UI_REF_W). **기본값은 이미 1080 기준이라 환산하지 않는다**
      (여기서 같이 곱하면 기본값이 1.5배 더 커지는 이중 확대가 된다).

    zero_ok: box_pad처럼 0이 "여백 없음"이라는 뜻인 값은 True(0을 기본값으로 안 되돌린다).
    나머지(size·outline_w·shadow_d)는 종전 `or` 의미대로 0/None이면 기본값.
    """
    if v is None or v == "" or (not zero_ok and not v):
        return default
    try:
        return int(round(float(v) * _OUT_W / _UI_REF_W))
    except (TypeError, ValueError):
        return default
# 자막 리듬 목표: 한 구절 2~3어절, 무자막 없이 빠르게 순차 전환. 핵심은 글자수보다
# **의미(호흡) 단위** — 수식어(관형어·부사)는 뒤 단어와 붙어 한 호흡이 되어야 한다.
# 예) "이 방법은 진짜", "자세한 보관비법", "바로 알려드릴게요", "그냥 두지 마세요".
# 2026-07-25: 9→14 / 3→4로 상향. 9자·3어절은 이어지는 한 문장을 화면에서 너무 잘게
# 토막내(대본은 코헤런트인데 자막이 스타카토로 끊겨 보임) "연결이 끊긴다"는 제보의 실제
# 원인이었다. 실측(문장×설정 비교): 14/4가 자연스러운 호흡을 유지하면서 부정("안 됐는데")·
# 쉼표 끊김 등 품질을 지키는 지점(5어절은 부정을 갈라놓고, 16자↑는 짧은 문장이 통째 1줄이
# 돼 화면에 길게 참). _CAP_HEAD 수식어 붙이기 로직은 그대로라 "마법의|가루" 파편은 방지.
# ★단, 3어절 시절의 미세 그룹핑(예 "며칠 안 됐는데"를 3어절 통짜로)은 큰 상한에선 앞 어절이
#   먼저 채워 갈릴 수 있다 — 잘게 안 끊기는 전체 흐름과 맞바꾼 의도된 트레이드오프.
# 2026-08-06 사장님 "장면마다 자막이 너무 길다": 레퍼런스 실측(4~8자, 2~3어절)로
# 줄일 수 있게 env 스위치(핸드오프 대본퀄v3 '다음에 할 것 4번'). 7/25의 14/4는 스타카토
# 제보 대응이라 **기본값은 14/4 유지**(테스트도 이 리듬을 명세로 본다) — 서버는
# /etc/shopping-shorts.env 에 CAPTION_TARGET_CHARS=8 CAPTION_MAX_WORDS=3 으로 짧게 운용,
# 되돌리기는 그 두 줄 삭제.
_CAP_TARGET = int(os.environ.get("CAPTION_TARGET_CHARS", "14") or 14)
_CAP_MAX_WORDS = int(os.environ.get("CAPTION_MAX_WORDS", "5") or 5)   # 4→5(2026-08-29 B규칙 — 결합을 지키려면 한 어절 여유가 필요, 글자수 14가 실질 상한)
# 의존명사(홀로 자막이 되면 뜻이 없어 앞말에 붙어야 하는 말) — 1어절 꼬리로 남으면 앞 구절에 병합.
# "…식단" | "때문?" → "…식단 때문?". 글자수가 아니라 품사로 판별(독립명사 "대박"·"가루"는 안 붙임).
# "거·게·건·걸"은 "것"의 구어형(것+조사 축약) — 실렌더에서 "…사 드시는 | 거 이제
# 멈추셔야"로 끊긴 실사고(2026-08-06, 8자 상한에서 드러남).
_CAP_BOUND_NOUN = {"때문", "때", "것", "수", "뿐", "등", "데", "줄", "채", "척", "터", "만큼", "대로", "듯",
                   "거", "게", "건", "걸",
                   # ★2026-08-29 사장님 B규칙: "5분 | 만에"로 갈라지던 실사고 — 수량 뒤 의존명사.
                   "만", "만에", "만은", "만이"}
# 의존명사에 어미가 붙어 길어진 꼴("거였더라고요"·"것이었죠") — 앞말에 붙어야 하는 건 같다.
# ⚠️짧은 접두(예: "수")를 그대로 prefix로 쓰면 수건·수납이 걸린다 — 두 글자 이상 확정형만.
_CAP_BOUND_PREFIX = ("거였", "거예", "거죠", "거라", "거야", "거임", "것이", "것도", "것만",
                     "수가", "수는", "수도", "수밖", "줄은", "줄도", "줄을",
                     "만에", "만큼", "때문", "뿐이", "뿐만", "듯이", "듯한", "채로")
# ── 머리 단어(head-marker): 이 단어를 만나면 그 **앞에서** 끊고, 이 단어가 다음
#    구절의 머리가 된다(뒤 명사/서술어를 데려간다). "…일쑤였는데 | 이 방법은"처럼
#    관형어 "이"가 앞 구절 꼬리에 남지 않게 한다. 관형사·지시어·부사·수관형사.
_CAP_HEAD = {"이", "그", "저", "한", "두", "세", "네", "몇", "각", "매", "총",
             "이런", "저런", "그런", "무슨", "어떤", "온갖", "단", "딱", "약",
             "자세한", "확실한", "특별한", "간단한", "완벽한",
             "바로", "그냥", "그대로", "다시", "먼저", "이제", "지금", "꼭", "막",
             "가장", "제일", "훨씬", "더", "덜", "약간", "좀", "진짜", "정말",
             # 양태부사(뒤 서술어를 꾸며 반드시 앞에서 끊고 뒤로 붙는다): "뚝 떨어지다"
             "뚝", "확", "쭉", "싹", "푹", "팍", "툭", "쫙", "쓱", "훅",
             # ★2026-08-29 사장님 B규칙 표본에서 추가: "전혀 | 없어서"·"쏙 | 들어가서"류 방지
             "전혀", "쏙", "통째로", "살짝", "슬쩍", "꽉", "몽땅", "전부", "금방",
             "이미", "벌써", "아예",
             # 부정부사·수량부사 — 뒤 서술어와 한 몸("안 됐는데"·"다들 놀랐어요")
             "안", "못", "다들", "모두", "함께", "같이"}
# ── 도입어(lead): 이 단어(로 끝나는 어절)는 한 호흡을 열고 **뒤에서** 끊는다.
#    호격("여러분")·연결 도입("남겨주시면") 등 그 자체로 한 박자.
_CAP_LEAD = {"여러분", "여러분,", "자"}
# 연결어미로 끝나는 절은 뒤에서 끊어 한 박자를 준다(…하면 | …했는데 |). 단 "-서"는
# 장소조사 "-에서/-께서"와 어미 "-아서/-어서"가 섞여 오탐이 잦아 제외한다. 또 이
# 끊기는 앞 절이 충분히 길 때(_CAP_LEAD_MINCHARS↑)만 적용해 "밭에서"(짧음)는 안 끊는다.
_CAP_LEAD_SUFFIX = ("면", "면서", "니까", "는데", "지만", "거든", "잖아",
                    "려", "려고")   # 2026-08-29 B규칙: "꾸미려 | 이것저것…"도 한 박자
_CAP_LEAD_MINCHARS = 4  # 연결어미 끊기 최소 글자수(공백 제외). 이보다 짧으면 이어붙임.
# 시간/빈도 도입 부사(아침마다·날마다·집집마다)는 자기 뒤에서 끊어 한 박자를 연다 →
# 뒤에 오는 '수식어+명사'가 3어절 하드캡에 밀려 쪼개지지 않는다("빵 달라는 아이"가 온전히
# 묶임, 2026-07-20 사장님 제보). "마다"는 항상 부사/보조사라 뒤에서 끊어도 안전(글자수 무관).
_CAP_OPENER_SUFFIX = ("마다",)
_CAP_HEAD_MINCHARS = 4  # 머리 단어 앞에서 끊는 최소(앞 구절) 글자수. 짧으면 이어붙임
                        # ("이것 한" 파편 방지, "…일쑤였는데 | 이" 는 앞이 길어 끊김).
_CAP_WRAP = 19          # 아주 긴 단일 어절 방어용(한 줄 최대 글자수, 1080px 안)
# 한 구절 최소 표시시간. 0.25는 사람이 읽을 수 있는 하한이 아니라 사실상 없는 것과 같았다
# (2026-08-17 사장님 "자막 넘어가는 글자들이 너무 짧게 빠르게 넘어간다").
# 실측(칸 4.4초, "요거트, 계란, 전분으로 만드는 일본식 요거트 식빵, 지금 확인해보세요!"):
#   요거트 0.40s / 계란 0.27s / 식빵 0.27s ← 눈으로 못 읽고 번쩍인다.
# 하한을 채운 시간은 _caption_durations가 다른 구절에서 비례로 빼 오므로 **총 길이는 안 변한다**.
# 2026-08-17 2차: 0.7초도 "휙휙 지나간다"(사장님). 1.0초로 올린다.
_CAP_MIN_DUR = float(os.environ.get("CAPTION_MIN_DUR", "1.0") or 1.0)
# 쉼표에서 끊을 최소 글자수(공백 제외). 나열형("요거트, 계란, 전분으로…")에서 1~2자 파편이
# 쏟아지던 것을 막는다 — 앞 구절이 이 길이 미만이면 쉼표를 넘겨 이어붙인다.
# _CAP_LEAD_MINCHARS·_CAP_HEAD_MINCHARS와 **같은 방식의 방어**인데 쉼표에만 빠져 있었다.
# 문장 끝(. ? ! …)은 대상이 아니다 — 문장 경계는 짧아도 끊는 게 맞다.
_CAP_COMMA_MINCHARS = int(os.environ.get("CAPTION_COMMA_MINCHARS", "6") or 6)
# ★쉼표 나열은 통째로 묶는다(2026-08-17 2차). 위 최소글자수만으로는 항목이 4개 이상일 때
# 나열이 **중간에서** 잘렸다 — 실측 "아침, 풍신, | 빵, 나도 중 댓글 | 남겨주시면"
# (누적 6자에 도달하는 순간 끊겨서 나열이 두 동강 난다).
# 그래서 '쉼표로 이어진 짧은 항목들'은 이 글자수까지 한 덩어리로 붙인다.
# 한 줄 표시 폭(_CAP_WRAP)을 넘지 않는 선에서만 — 넘으면 종전 규칙대로 끊는다.
_CAP_LIST_MAXCHARS = int(os.environ.get("CAPTION_LIST_MAXCHARS", "18") or 18)
# 나열 항목 하나로 볼 최대 글자수. 이보다 길면 '짧은 나열'이 아니라 정상 절이므로 종전대로.
_CAP_LIST_ITEMCHARS = int(os.environ.get("CAPTION_LIST_ITEMCHARS", "4") or 4)

# 한글 폰트 후보(먼저 발견되는 것 사용). repo에 NanumGothic을 번들하므로 서버·로컬
# 어디서든 별도 설치 없이 자막이 나온다(env로 다른 폰트 강제 가능).
_BUNDLED_FONT = str(Path(__file__).parent / "assets" / "NanumGothic.ttf")
_FONT_CANDIDATES = [
    os.environ.get("SHORTS_CAPTION_FONT"),
    _BUNDLED_FONT,
    "C:/Windows/Fonts/malgun.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def _resolve_font():
    """사용 가능한 한글 폰트 경로(첫 번째 존재하는 것). 없으면 None → 자막 생략."""
    for p in _FONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


# ⚠️ ffmpeg/ffprobe는 stderr를 **UTF-8**로 낸다. text=True만 주면 파이썬이 로캘
# (윈도우=cp949)로 디코드하다 subprocess 리더 스레드에서 UnicodeDecodeError로 죽고,
# 그 결과 stdout/stderr가 **None**이 된다. 이 저장소는 한글 파일명이 도처에 있어
# 흔히 밟는 경로다(Task9 리포트 §5가 관측·기록). 재현(2026-07-16):
#   _run_ffmpeg(["ffmpeg","-i","없는영상_한글이름.mp4", ...])
#     → 리더 스레드 UnicodeDecodeError → r.stderr=None
#     → r.stderr[-1000:] → TypeError: 'NoneType' object is not subscriptable
#   = "원인을 삼키지 않는다"던 함수가 **정확히 원인을 삼켰다.**
# → 인코딩을 명시하고 못 읽는 바이트는 대체한다. 로그가 조금 깨질지언정 원인은 남는다.
_FF_TEXT = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"}


def _probe_duration(path):
    """ffprobe로 미디어 길이(초)."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    out = subprocess.run(cmd, stdin=subprocess.DEVNULL, check=True, **_FF_TEXT)
    return float(out.stdout.strip())


_TRIM_FLOOR = 0.4  # 비트 트림 후 남길 최소 길이(초). 과트림·역전 방지.


def _effective_dur(probe, head_trim=0.0, tail_trim=0.0, floor=_TRIM_FLOOR):
    """probe(원본 TTS 길이)에서 앞/뒤 트림을 뺀 실질 비트 길이. 하한 가드 포함.
    음수 트림은 0으로 취급. 결과가 floor 밑이면 floor로 고정한다."""
    d = probe - max(0.0, head_trim) - max(0.0, tail_trim)
    return max(floor, d)


def _beat_effective_dur(beat, tts_path):
    """비트 dict의 head_trim/tail_trim을 반영한 실질 길이(단일 출처)."""
    return _effective_dur(_probe_duration(tts_path),
                          beat.get("head_trim", 0.0), beat.get("tail_trim", 0.0))


def _run_ffmpeg(cmd, cwd=None):
    """ffmpeg 실행. 실패 시 stderr를 예외에 담아 원인을 삼키지 않는다.
    stdin=DEVNULL 필수(Windows): pytest 캡처 중에는 부모 stdin 핸들이 유효하지
    않아, 명시 안 하면 subprocess가 그 핸들을 상속하려다 OSError([WinError 6]
    핸들이 잘못되었습니다)로 죽는다(2026-07-18 Task2 grounding 테스트 실측 — 이미
    _probe_duration은 이 패턴을 쓰고 있었다, 여기만 누락돼 있었다)."""
    r = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, **_FF_TEXT)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패(exit {r.returncode}): {(r.stderr or '')[-1000:]}")
    return r


_MIN_CLIP = 0.8   # 초. 이보다 짧은 독립 클립은 만들지 않는다(깜빡임 방지).
# 연속도 아닌 짧은 클립을 흡수(=정지 유발)하는 하한. 0.5초 이상 움직이는 실클립은 흡수하지 않고
# 그대로 둔다 — 짧게 움직이는 게 정지프레임보다 낫다는 사장님 피드백(2026-07-21).
_MIN_CLIP_KEEP = 0.5

# 슬로우모션 상한. 소스가 나레이션보다 짧을 때 무제한으로 늘리면(옛 동작) 부자연스러운
# 슬로우크롤이 됐다(사장님 실측, 2026-07-19). 재생은 최대 이 배율까지만 늘리고, 그 이상
# 필요한 시간은 마지막 프레임 정지(freeze)로 떠안는다 → 요리 동작은 자연 속도, 남는 시간만 홀드.
_MAX_SLOWMO = 1.15

# 마지막 비트 '여운'(초) — 대사가 끝나도 화면을 이만큼 더 살려둔다(2026-07-20 콘폼루프 T4,
# 사장님 육안 피드백 "붙이면 바로 자르지 말고 대사 끝나고 1초 정도 더 냅두면").
_LAST_RUNOUT = 1.0


def _speed_and_freeze(src_dur, out_dur, max_slowmo=_MAX_SLOWMO):
    """소스 구간 src_dur초를 출력 out_dur초로 채울 때, (움직이는 재생 길이, 정지프레임 길이).

    - out_dur ≤ src_dur: 늘릴 필요 없음 → (out_dur, 0).
    - 필요한 배율이 상한 이내: 그대로 완만한 슬로우 → (out_dur, 0).
    - 상한 초과: 재생은 src_dur*max_slowmo까지만, 나머지는 freeze로 → (capped, out_dur-capped).

    항상 play_out + freeze == out_dur (총 길이·오디오/자막 싱크 보존)."""
    if src_dur <= 1e-9 or out_dur <= src_dur:
        return (out_dur, 0.0)
    capped = src_dur * max_slowmo
    if out_dur <= capped + 1e-9:
        return (out_dur, 0.0)
    return (capped, out_dur - capped)


def _extend_last_clip_for_runout(plan, segs, runout=_LAST_RUNOUT):
    """마지막 비트 계획의 끝에 여운 runout초를 붙인다(plan 제자리 수정, 반환 동일 객체).

    소스 구간 [start,end]에 실프레임 여유(slack)가 남았으면 그만큼 **1배속 실영상**으로
    연장하고, 부족분은 out_dur만 늘려 기존 _speed_and_freeze 기계(완만 슬로모→켄번즈 홀드)가
    흡수한다. 오디오는 tts 그대로라 마지막 1초는 자연스러운 무성 여운이 된다 —
    mux의 -t가 이 여운만큼 같이 늘어나야 화면에 실린다(assemble 쪽 runout 참조)."""
    if not plan or runout <= 0:
        return plan
    c = plan[-1]
    seg = next((s for s in segs
                if s.get("video_id") == c.get("video_id")
                and float(s.get("start", 0.0)) <= float(c.get("start", 0.0)) < float(s.get("end", 0.0))),
               None)
    slack = 0.0
    if seg:
        slack = max(0.0, float(seg["end"]) - (float(c["start"]) + float(c["src_dur"])))
    real_ext = min(runout, slack)
    c["src_dur"] += real_ext
    c["out_dur"] += runout
    return plan


def _beat_material(beat):
    """비트의 화면 재료(순서 구간 리스트)를 **한 곳에서** 정한다(0순위-B).

    ★장면실험실 배선(2026-08-15 사장님 "거기서 어떻게 되는지를 보고 판단해야해"):
    사람이 실험실에서 편성·트림한 결과(beat["scene_override"])가 있으면 그 구간들이 재료다.
    원본 primary/alternates는 **그대로 두고 얹는 형태**라, scene_override를 지우면 원래대로
    돌아간다(edit_plan.revert_scene_lab). 트림(✂ 가운데 잘라내기)은 적용 시점에 이미
    '구멍 뺀 두 토막'으로 갈라져 들어오므로 여기서는 그냥 구간 목록일 뿐이다 —
    아래 _plan_beat_clips의 계산 규칙은 아무것도 달라지지 않는다(재료만 바뀐다).
    override가 없는 기존 잡은 예전과 바이트 동일하게 동작한다."""
    over = beat.get("scene_override")
    if over:
        return [dict(s) for s in over if s]
    return [s for s in ([beat.get("primary")] + list(beat.get("alternates") or [])) if s]


def _apply_fixed_lens(plan, fixed, tts_dur, min_clip=0.6, eps=1e-3):
    """✋ 손으로 정한 컷 길이를 반영한다(2026-08-24). **총합은 tts_dur 그대로.**

    ★화면(scene_play.js applyFixedLens)과 **같은 규칙**이어야 한다 — 규칙이 갈리면
      미리보기와 결과가 어긋나고, 그게 이 작업을 시작한 이유다(0순위-B).
      정한 컷은 그 길이로, 나머지 컷은 남은 시간을 **원래 비율대로** 나눠 갖는다.

    fixed = {seg_id: 초}. plan 원소는 out_dur를 갖는다(src_dur는 안 건드린다 —
    입력에서 읽는 구간은 그대로 두고 출력 길이만 조절해 슬로모/freeze 기계가 흡수한다).
    """
    if not plan or not fixed:
        return plan
    fx = [c for c in plan if fixed.get(c.get("seg_id")) and fixed[c["seg_id"]] > 0]
    fr = [c for c in plan if c not in fx]
    if not fx:
        return plan
    want = sum(fixed[c["seg_id"]] for c in fx)
    room = tts_dur - len(fr) * min_clip          # 나머지 컷의 최소 몫은 남겨둔다
    cap = max(min_clip, room if fr else tts_dur)
    k = (cap / want) if want > cap else 1.0
    for c in fx:
        c["out_dur"] = max(min_clip * 0.5, fixed[c["seg_id"]] * k)
    want = sum(c["out_dur"] for c in fx)
    rest = max(0.0, tts_dur - want)
    if fr:
        tot = sum(c["out_dur"] for c in fr)
        if tot > eps:
            for c in fr:
                c["out_dur"] = c["out_dur"] / tot * rest
        else:
            for c in fr:
                c["out_dur"] = rest / len(fr)
    else:
        fx[-1]["out_dur"] += tts_dur - sum(c["out_dur"] for c in fx)
    return plan


def _spread_stretch(plan, eps=1e-3):
    """늘려 채우기(scene_lab 칸별 토글 beat["stretch_fill"]) — 재료가 모자라 화면을 늘려야
    할 때(out_dur 합 > src_dur 합), 그 부족분을 마지막 컷에 몰지 않고 **전 컷에 재료 길이
    비례로** 나눈다(2026-08-15 사장님 "마지막 컷에만 몰아주지 않기"). 총 out_dur 합은
    그대로라 오디오·자막 싱크 불변이고, 각 컷은 _speed_and_freeze가 균등하게 완만히
    늘린다. 플래그가 없는 기존 잡은 이 함수에 오지도 않는다(호출부 gate)."""
    if not plan or len(plan) < 2:
        return plan
    tot_out = sum(float(c.get("out_dur", 0.0)) for c in plan)
    tot_src = sum(float(c.get("src_dur", 0.0)) for c in plan)
    if tot_src <= eps or tot_out - tot_src <= eps:
        return plan                      # 부족분이 없으면 그대로(재배분할 것이 없다)
    sc = tot_out / tot_src
    acc = 0.0
    for c in plan[:-1]:
        c["out_dur"] = float(c["src_dur"]) * sc
        acc += c["out_dur"]
    plan[-1]["out_dur"] = max(eps, tot_out - acc)   # 반올림 오차는 마지막이 흡수(합 보존)
    return plan


def plan_beat_clips_for(beat, tts_dur, src_durs, *, runout=0.0):
    """비트 하나의 **화면 조각 계획**을 정한다 — 렌더·캡컷·ZIP이 **모두 이 함수를 쓴다**.

    반환: [{"video_id","start","src_dur","out_dur"}, ...] (없으면 [])

    ## 왜 이 함수가 생겼나 (2026-08-23 실사고)

    화면 조각을 정하는 판단이 **세 군데에 따로** 적혀 있었다:
      · 렌더(build_video)  — `_beat_material` 전부를 쓴다(정상)
      · 캡컷(capcut_draft) — `beat["primary"]` 하나만 (`capcut_draft.py:174`)
      · ZIP(export_bundle) — `beat["primary"]` 하나만 (`export_bundle.py:117`)

    라이브 실측: 화면 조각 19개인 job이 캡컷엔 **7개**만 갔다(3분의 1).
    → 캡컷에서 연 것과 완성본이 **다른 영상**이었다. CLAUDE.md 0순위-B 그대로다.

    ★고칠 때 `_plan_beat_clips`만 부르면 안 된다 — 그 앞뒤로 판단이 더 있다(손상 소스
      제외·포인트 비트 홀드·1장1컷·늘려채우기·마지막 여운). 그 6줄을 내보내기에 다시
      적으면 **또 두 벌**이 된다. 그래서 블록을 통째로 여기로 옮기고, 렌더도 이걸 부른다.

    src_durs: {video_id: 소스 총길이(초)}. 0.05 이하면 디코드 불가로 보고 그 구간을 뺀다
              (안 빼면 아래 -ss 렌더가 예외로 죽는다, 2026-07-19).
    runout:   마지막 비트 여운(초). 0이면 안 붙인다.
    """
    from shopping_shorts import backbone as _bb, config as _cfg
    # 순서 구간 리스트 = _beat_material(기본: [primary]+alternates / 실험실 편성이 있으면
    # scene_override). 소스에 실재하고 + 디코드 가능한 것만.
    segs = [s for s in _beat_material(beat)
            if s and (src_durs or {}).get(s.get("video_id"), 0.0) > 0.05]
    if not segs:
        return []
    beat_src_durs = {s["video_id"]: src_durs[s["video_id"]] for s in segs}
    # 컷 밀도(2026-07-22): 한 컷을 MAX_SHOT_SECONDS 넘게 안 끌고 distinct 세그먼트를 번갈아
    # 재생 → 긴 정지 대신 컷. 포인트 비트는 홀드가 맞으니 라운드로빈 안 한다.
    _max_shot = None if _bb.is_point_beat(beat) else getattr(_cfg, "MAX_SHOT_SECONDS", 0) or None
    # 1장=1컷 모드(기본 off). 켜면 담은 장면이 순서대로 한 번씩만 나온다(되돌아옴 없음).
    _one = bool(getattr(_cfg, "ONE_CLIP_PER_SEGMENT", False))
    # ★구절 맞춤(2026-08-29 사장님 "개수+길이까지 1:1") — 컷 경계 = 자막 구절 경계.
    #   화면(scene_play.js planClips의 phraseSync 분기)과 **같은 규칙의 서버판**이다:
    #   컷1이 리드인(첫말 전 무음)을 얹고 마지막 컷이 꼬리를 얹는다. 재료가 구절보다
    #   적으면 마지막 재료가 남은 구절을 이어 커버한다. ✋수동 길이가 있으면 수동이
    #   이기고(아래 fixed_lens), 그땐 이 분기를 타지 않는다.
    _phrase_plan = None
    if beat.get("phrase_sync"):          # 구절맞춤 켬 = 구절이 ✋보다 우선(화면과 같은 규칙)
        _phrase_plan = _plan_phrase_clips(beat, segs, tts_dur)
    if _phrase_plan:
        plan = _phrase_plan
    else:
        plan = _plan_beat_clips(segs, tts_dur, src_durs=beat_src_durs, max_shot=_max_shot,
                                one_per_seg=_one)
    # ✋ 손으로 정한 컷 길이가 있으면 먼저 반영한다(칸 총합은 안 바뀐다).
    #   단 구절맞춤 계획엔 덧입히지 않는다 — 구절 경계가 곧 정답이다.
    _fixed = {} if _phrase_plan else (beat.get("fixed_lens") or {})
    if _fixed:
        _apply_fixed_lens(plan, _fixed, tts_dur)
    # ★늘려 채우기(실험실 칸별 토글): 부족분을 전 컷에 고르게 — 여운보다 먼저.
    #   여운은 일부러 붙이는 무성 꼬리라 재배분 대상이 아니다. 플래그 없으면 그대로.
    if beat.get("stretch_fill"):
        _spread_stretch(plan)
    if runout > 0:
        _extend_last_clip_for_runout(plan, segs, runout)
    return plan


def _plan_phrase_clips(beat, segs, tts_dur):
    """구절 맞춤 계획 — 컷 k = k번째 재료, 길이 = k번째 자막 구절 표시시간.

    경계는 화면 자막과 같은 함수로 만든다(_caption_segments/_caption_durations/
    _adjust_caps_for_trim — _lab_captions와 동일 조합, 0순위-B). 시간표를 못 만들면
    None을 돌려 종전 배분으로 폴백한다(조용한 어긋남 대신 옛 동작)."""
    try:
        cap_segs = _caption_segments(beat.get("narration") or "",
                                     beat.get("caption_lines"))
        if not cap_segs or tts_dur <= 0.1 or not segs:
            return None
        lead, rd = _adjust_caps_for_trim(beat)
        durs = _caption_durations(cap_segs, tts_dur, real_durs=rd)
        if not durs:
            return None
        # 경계 [0, lead+d1, lead+d1+d2, …, tts_dur] — 리드인은 컷1, 꼬리는 마지막 컷 몫.
        bounds = [0.0]
        t = float(lead or 0.0)
        for d in durs[:-1]:
            t += d
            bounds.append(min(tts_dur, t))
        bounds.append(tts_dur)
        # ★구절이 재료보다 많으면 **담은 조각의 뒷부분을 한 바퀴 더 쓴다**(2026-08-31 사장님
        #   "대본이 길어지니까 뒤에까지 장면이 안 붙는다"). 화면(scene_play.js planClips의
        #   구절맞춤 분기)과 **같은 규칙의 서버판**이다 — 한쪽만 고치면 미리보기와 결과물이
        #   어긋난다(0순위-B). 종전 n_cut=min(구절, 재료)는 조각 3·구절 6이면 컷을 3개만
        #   만들고 마지막 컷이 남은 구절 전부를 덮어, 뒤쪽 말에 화면 전환이 없었다.
        #   실측(job 33377557599e): 칸 4개 모두 조각 3 < 구절 3~6인데 길이는 1.0~2.5초씩
        #   남았다 — 길이가 아니라 **개수**가 모자란 것이다.
        #   ★첫 바퀴는 종전 그대로 1:1(담은 장면이 하나도 빠지지 않게), 두 바퀴째부터만
        #     뒤가 남은 조각을 돌아가며 쓴다.
        plan = []
        pos = [float(g["start"]) for g in segs]
        ri = 0
        for k in range(len(durs)):
            end_b = bounds[-1] if k == len(durs) - 1 else bounds[k + 1]
            d = max(0.1, end_b - bounds[k])
            if k < len(segs):
                idx = k                                  # 첫 바퀴 = 담은 순서대로(종전과 같다)
            else:
                idx = -1
                for t2 in range(len(segs)):              # 두 바퀴째 = 뒤가 남은 조각을 돌아가며
                    j2 = (ri + t2) % len(segs)
                    # ★end를 모르는 재료는 '남은 게 없다'로 본다 → 종전 동작(마지막이 커버).
                    #   지어내서 조각 밖을 읽으면 엉뚱한 화면이 나온다.
                    _end = segs[j2].get("end")
                    if _end is None:
                        continue
                    if float(_end) - pos[j2] >= min(d, _MIN_CLIP) - 1e-3:
                        idx = j2
                        break
                if idx < 0:                              # 재료 소진 → 종전대로 마지막 컷이 커버
                    if plan:
                        plan[-1]["src_dur"] += bounds[-1] - bounds[k]
                        plan[-1]["out_dur"] = plan[-1]["src_dur"]
                    break
                ri = (idx + 1) % len(segs)
            plan.append({"video_id": segs[idx]["video_id"], "start": pos[idx],
                         "src_dur": d, "out_dur": d})
            pos[idx] += d
        return plan
    except Exception:      # noqa: BLE001 — 계획 실패가 렌더를 죽이면 안 된다(폴백이 있다)
        return None


def _plan_beat_clips(segments, tts_dur, min_clip=_MIN_CLIP, src_durs=None, max_shot=None,
                     one_per_seg=False):
    """비트의 순서 구간 리스트 → 나레이션 길이(tts_dur)에 맞춘 클립 계획.
    각 클립은 자기 구간 [start,end]를 절대 넘지 않는다(유출 0). 부족분은 아래 정책으로 채운다.
    반환: [{"video_id","start","src_dur","out_dur"}, ...]

    ★멈추지 말고 진짜 영상으로(2026-07-20 사장님): 배정 구간을 다 써도 모자라면, 소스 릴은
    보통 구간보다 훨씬 길어(구간 2초 vs 릴 30초) 뒤에 실프레임이 남아있다. `src_durs`
    ({video_id: 소스총길이})가 주어지면 마지막 클립의 읽기 창을 소스에 남은 만큼 더 늘려
    **1배속 실영상**으로 채운다 → freeze/억지슬로우 없음. 소스까지 소진돼야만 슬로모 폴백.
    src_durs 미제공(하위호환)이면 예전처럼 마지막 클립을 슬로모로 늘린다.

    max_shot(2026-07-22): 한 컷을 이보다 오래 안 끈다 — 세그먼트를 이 상한 청크로 **번갈아**
    재생(라운드로빈)해 긴 정지(7초 홀드) 대신 distinct 앵글로 컷한다(벤치마크 ~1.1초 컷 밀도).
    같은 세그먼트는 창을 앞으로 밀며 재생(정지 아님). None/0이면 옛 동작(세그 통째 재생)."""
    eps = 1e-3
    clips = []
    filled = 0.0
    if one_per_seg and segments:
        # ★1장 = 1컷 · 비례 배분(2026-08-14 사장님 "전체 시간을 보고 배분해서 맡기면 되는 건가").
        #   라운드로빈은 상한(2.2초) 때문에 긴 장면을 다 못 써서 시간이 모자라고, 그래서 앞 장면으로
        #   되돌아왔다(담김 3장인데 컷 4개). 확정 길이도 답이 아니다 — 담는 장면 길이도 칸별 나레이션
        #   길이도 매번 달라 어떤 칸은 남고 어떤 칸은 모자란다.
        #   그래서 **나레이션 시간을 담은 장면들에 길이 비례로 나눈다**: 남으면 비례로 줄이고,
        #   모자라면 비례로 늘린다(각 장면이 원본 뒤를 조금씩 더 쓴다). 담은 게 전부·순서대로·
        #   한 번씩 나오고 긴 장면은 길게, 짧은 장면은 짧게 원래 비율이 유지된다.
        usable = [g for g in segments if (g["end"] - g["start"]) > eps]
        # 비례로 나눴을 때 min_clip에 못 미치는 조각은 빼고 남은 것끼리 다시 나눈다(깜빡임 방지).
        while usable:
            total = sum(g["end"] - g["start"] for g in usable)
            scale = tts_dur / total if total > eps else 0.0
            too_small = [g for g in usable if (g["end"] - g["start"]) * scale < min_clip - eps]
            if not too_small or len(usable) == 1:
                break
            usable = [g for g in usable if g not in too_small]
        if usable:
            total = sum(g["end"] - g["start"] for g in usable)
            scale = tts_dur / total if total > eps else 0.0
            for k, seg in enumerate(usable):
                take = (seg["end"] - seg["start"]) * scale
                if k == len(usable) - 1:
                    take = max(0.0, tts_dur - filled)      # 반올림 오차는 마지막이 흡수
                if take <= eps:
                    continue
                # 원본 뒤에 남은 실프레임까지만 1배속으로 읽는다(넘으면 그만큼 늘려 재생).
                src_cap = take
                if src_durs:
                    room = max(0.0, src_durs.get(seg["video_id"], 0.0) - seg["start"])
                    if room > eps:
                        src_cap = min(take, room)
                clips.append({"video_id": seg["video_id"], "start": seg["start"],
                              "src_dur": src_cap, "out_dur": take})
                filled += take
    elif max_shot and max_shot > eps and len(segments) > 1:
        # 라운드로빈: distinct 세그먼트를 max_shot씩 번갈아 → 컷 밀도↑. 각 세그 읽기위치를 유지해
        # 다시 올 땐 이어서 재생(같은 프레임 반복 아님). 다 소진되면 아래 공통 shortfall로.
        pos = [seg["start"] for seg in segments]
        oi, guard0 = 0, 0
        while tts_dur - filled > eps and guard0 < 2000:
            guard0 += 1
            i = oi % len(segments); oi += 1
            seg = segments[i]
            avail = seg["end"] - pos[i]
            if avail <= eps:
                if all(segments[k]["end"] - pos[k] <= eps for k in range(len(segments))):
                    break                          # 전 세그 소진 → shortfall 정책으로
                continue
            take = min(avail, max_shot, tts_dur - filled)
            # ★깜빡임 방지(2026-07-29 사장님 "0.몇초마다 두서없이 바뀌어 눈아프고 집중안됨"):
            #   min_clip 미만 컷 금지. 실측(75f41e558957.mp4)에서 0.47~0.63초 컷이 수두룩했던 건
            #   이 라운드로빈이 세그 잔량(avail)이 짧아도 그대로 뱉었기 때문 — min_clip 파라미터가
            #   여기서 안 쓰였다. 잔량이 min_clip 미만이면 (a)min_clip 이상 낼 수 있는 다른 세그로
            #   전환, (b)그런 세그가 없으면 루프를 끝내 아래 shortfall(마지막 클립을 실프레임으로
            #   연장, 되풀이 없음)이 이어받게 한다. 단 남은 나레이션 자체가 min_clip 미만이면
            #   그 자투리는 새 tiny컷 대신 shortfall로 흡수.
            if take < min_clip - eps:
                if tts_dur - filled < min_clip - eps:
                    break
                j = next((k for k in range(len(segments))
                          if segments[k]["end"] - pos[k] >= min_clip - eps), -1)
                if j < 0:
                    break
                i = j; seg = segments[i]
                take = min(seg["end"] - pos[i], max_shot, tts_dur - filled)
            clips.append({"video_id": seg["video_id"], "start": pos[i],
                          "src_dur": take, "out_dur": take})
            pos[i] += take
            filled += take
    else:
        for seg in segments:
            remaining = tts_dur - filled
            if remaining <= eps:
                break
            seg_len = seg["end"] - seg["start"]
            if seg_len <= eps:
                continue
            take = min(seg_len, remaining)   # 1배속으로 이만큼 재생(구간 이내)
            clips.append({"video_id": seg["video_id"], "start": seg["start"],
                          "src_dur": take, "out_dur": take})
            filled += take

    if not clips:
        # 구간이 하나도 못 쓰였다(모두 길이 0). 첫 구간을 tts_dur로 슬로모(방어적 폴백).
        seg = segments[0]
        return [{"video_id": seg["video_id"], "start": seg["start"],
                 "src_dur": max(seg["end"] - seg["start"], eps), "out_dur": tts_dur}]

    shortfall = tts_dur - filled
    if shortfall > eps and one_per_seg:
        # ★1장=1컷에서는 **되돌아오지 않는다**. 남는 시간은 마지막 컷 하나로 흡수한다:
        #   소스에 실프레임이 남아 있으면 1배속으로 이어 붙이고(자연스럽다), 그것도 없으면
        #   마지막 컷을 늘린다. 새 컷을 만들면 담은 장수와 컷 수가 어긋나 이 모드의 뜻이 깨진다.
        last = clips[-1]
        if src_durs:
            sdur = src_durs.get(last["video_id"], 0.0)
            avail = max(0.0, sdur - (last["start"] + last["src_dur"]))
            real_ext = min(shortfall, avail)
            if real_ext > eps:
                last["src_dur"] += real_ext
                last["out_dur"] += real_ext
                shortfall -= real_ext
        if shortfall > eps:
            last["out_dur"] += shortfall      # 실프레임이 없으면 그 컷을 늘린다
            shortfall = 0.0
    if shortfall > eps:
        # 1순위: 마지막 클립을 그 소스에 남은 실프레임으로 연장(1배속) — 릴이 배정 구간보다 길다.
        if src_durs:
            last = clips[-1]
            sdur = src_durs.get(last["video_id"], 0.0)
            avail = max(0.0, sdur - (last["start"] + last["src_dur"]))
            real_ext = min(shortfall, avail)
            if real_ext > eps:
                last["src_dur"] += real_ext
                last["out_dur"] += real_ext
                shortfall -= real_ext
        # 2순위(★뒤에서 채우기, 2026-07-27 사장님: "같은 장면 반복 말고, 조금 미스 나도
        #   뒤 실프레임으로 자연스럽게"): 예전엔 seg["start"]로 되감아 재생해 같은 장면이
        #   2~3번 되풀이돼 보였다. 대신 각 소스 릴의 '아직 안 튼 뒷부분'을 이어서 소비한다 —
        #   릴은 배정 구간보다 훨씬 길어(구간 2초 vs 릴 30초) 뒤에 실프레임이 남아있다.
        #   소스별로 지금까지 소비한 최대 지점(head)부터 앞으로만 밀며 새 클립을 붙이므로
        #   같은 창을 다시 틀지 않는다. 배정 구간 [start,end]은 벗어나지만 새 프레임이라
        #   되풀이보다 자연스럽다. 모든 소스가 각자 끝까지 소진돼야만 3순위 홀드로.
        # 2a: 소스 릴의 '아직 안 튼 뒷부분'을 앞으로만 밀며 소비 → 같은 창을 다시 안 튼다.
        #   소스별 head(지금까지 소비한 최대 지점)부터 src 총길이까지 새 클립을 붙인다.
        #   릴이 배정 구간보다 길면(흔함) 여기서 대부분 채워져 되풀이가 사라진다.
        if src_durs:
            head = {}
            for cl in clips:
                end = cl["start"] + cl["src_dur"]
                if end > head.get(cl["video_id"], 0.0):
                    head[cl["video_id"]] = end
            chunk = max_shot if (max_shot and max_shot > eps) else shortfall
            guard = 0
            while shortfall > eps and guard < 2000:
                guard += 1
                progressed = False
                for seg in segments:
                    if shortfall <= eps:
                        break
                    vid = seg["video_id"]
                    h = head.get(vid, seg["end"])
                    avail = src_durs.get(vid, 0.0) - h
                    if avail <= eps:
                        continue
                    take = min(avail, chunk, shortfall)
                    clips.append({"video_id": vid, "start": h,
                                  "src_dur": take, "out_dur": take})
                    head[vid] = h + take
                    shortfall -= take
                    progressed = True
                if not progressed:
                    break
        # 2b: 소스 뒤까지 다 소진돼도 모자라면(짧은 릴), 슬로모/정지 대신 실영상 루프로 채운다
        #   (2026-07-20 사장님 "멈춤·슬로우 없음"). 되풀이는 남지만 이건 뒤가 진짜 없는 극단뿐.
        guard = 0
        while shortfall > eps and guard < 500:
            guard += 1
            progressed = False
            for seg in segments:
                if shortfall <= eps:
                    break
                seg_len = seg["end"] - seg["start"]
                if seg_len <= eps:
                    continue
                take = min(seg_len, shortfall)
                clips.append({"video_id": seg["video_id"], "start": seg["start"],
                              "src_dur": take, "out_dur": take})
                shortfall -= take
                progressed = True
            if not progressed:
                break
        # 3순위(극단 방어 — 쓸 실영상이 아예 0인 비정상 경로에서만): 최소한만 홀드.
        if shortfall > eps:
            clips[-1]["out_dur"] += shortfall

    # 0.8초 미만 독립 클립 제거: 그런 클립을 이웃에 흡수. 합계(sum out_dur)는 보존된다.
    # ★흡수를 정지프레임으로 떠넘기지 않는다(2026-07-21 사장님 "화면 멈춤"): 이웃이 같은 소스의
    #   연속 구간이면 src_dur도 늘려 **실프레임**으로 흡수한다. 안 그러면 2순위 루프가 실영상
    #   움직임으로 채운 짧은 클립들이 여기서 다시 out_dur만 부풀어 프리즈로 되돌아갔다(실측:
    #   b3 CTA 비트 0.97초 정지의 정체). 연속도 아니고 볼 만큼(≥_MIN_CLIP_KEEP) 움직이면 흡수
    #   안 하고 그대로 둔다 — 짧은 움직임이 정지보다 낫다.
    def _contig(nb, k):
        n, s = clips[nb], clips[k]
        return (n["video_id"] == s["video_id"]
                and abs((n["start"] + n["src_dur"]) - s["start"]) < 0.05)

    def _absorbable(k):
        if clips[k]["out_dur"] >= min_clip - eps:
            return False
        nb = k - 1 if k > 0 else k + 1
        return _contig(nb, k) or clips[k]["out_dur"] < _MIN_CLIP_KEEP - eps

    while len(clips) > 1:
        idx = next((k for k in range(len(clips)) if _absorbable(k)), None)
        if idx is None:
            break
        nb = idx - 1 if idx > 0 else idx + 1
        neigh = clips[nb]
        if _contig(nb, idx):
            neigh["src_dur"] += clips[idx]["src_dur"]   # 실프레임 연장 → 정지 안 생김
        neigh["out_dur"] += clips[idx]["out_dur"]
        clips.pop(idx)
    return clips


def _strip_punct(w):
    """조사·문장부호를 뗀 순수 단어(머리/도입어 판정용). '이,' → '이'."""
    return w.strip(".,!?…\"'()[]")


# 자막 각 줄 끝에서 뗄 문장부호(마침표·쉼표·말줄임). 감탄/의문(? !)·물결(~)은 톤이라 남긴다.
_CAP_TRIM_TAIL = ".,、，。…"


def _strip_cap_tail(s):
    """표시용 — 자막 한 줄 끝의 마침표·쉼표·말줄임만 뗀다('봤잖아요.'→'봤잖아요'). ?!~는 유지."""
    s = s.rstrip()
    while s and s[-1] in _CAP_TRIM_TAIL:
        s = s[:-1].rstrip()
    return s


def cap_preset_key(txt):
    """자막 줄 preset이 나레이션과 '같은 글자'인지 대조할 때 쓰는 정규화 키.

    ★대조 기준을 여기 한 곳에서만 정한다(0순위-B). 예전엔 저장(app.py caplines의 _cmp_key)이
      **끝 문장부호까지 무시**하고, 읽기(_caption_segments)는 **공백만** 무시해서 기준이 두 벌이었다.
      화면에 보이는 줄은 _strip_cap_tail로 마침표가 떼여 있으므로, 사장님이 그 줄을 그대로
      나눠 저장하면 저장은 통과하지만 렌더에서는 narration의 마침표 때문에 대조가 깨져
      **조용히 규칙 폴백**으로 내려갔다 = "저장은 되는데 최종렌더에 반영 안 됨"(2026-08-26 제보).
    """
    drop = set(_CAP_TRIM_TAIL) | set(chr(32)+chr(9)+chr(10)+chr(13))
    return "".join(ch for ch in (txt or "") if ch not in drop)


def _wrap_long(segs):
    """구절 리스트에서 _CAP_WRAP를 크게 넘는 초장문만 줄바꿈으로 방어(대부분 그대로 1줄).
    각 줄은 표시용으로 끝 문장부호를 정리한다(2026-07-21 사장님 '봤잖아요.' 마침표 노출)."""
    out = []
    for s in segs:
        s = _strip_cap_tail(s)
        if not s:
            continue
        if len(s.replace(" ", "")) > _CAP_WRAP:
            out.extend(textwrap.wrap(s, _CAP_WRAP) or [s])
        else:
            out.append(s)
    return out


def _caption_segments(narration, preset=None):
    """나레이션을 **의미(호흡) 단위**의 짧은 구절로 나눈다(2~3어절, 1줄).
    예) "여러분 / 오이 절대", "냉장고에 / 그냥 두지 마세요",
        "버리기 일쑤였는데 / 이 방법은 진짜", "남겨주시면 / 자세한 보관비법 / 바로 알려드릴게요".

    핵심은 글자수가 아니라 **수식어를 뒤 단어와 붙이는 것**:
    - 머리 단어(_CAP_HEAD: 관형어·부사 "이/그/자세한/바로/그냥/그대로"…)를 만나면 그
      **앞에서** 끊는다 → 그 단어가 다음 구절의 머리가 되어 뒤 명사/서술어를 데려간다.
      ("…일쑤였는데 | 이 방법은" — 관형어 "이"가 앞 꼬리에 안 남는다.)
    - 도입어(_CAP_LEAD "여러분"·연결어미 "…면/…는데"로 끝나는 어절)는 한 박자를 열고
      그 **뒤에서** 끊는다. ("여러분 |", "남겨주시면 |")
    - 그 밖에는 글자수(_CAP_TARGET) / 어절수(_CAP_MAX_WORDS) 목표 안에서 이어붙인다.

    방어: 목표를 크게 넘는 아주 긴 단일 어절은 _CAP_WRAP로 강제 줄바꿈.

    preset: 대본을 쓴 AI가 미리 끊어준 호흡 줄(list). 이어붙였을 때 narration과 정확히
    같으면(공백만 무시) 그대로 채택 — 규칙기반 두더지잡기를 근본적으로 대체한다(2026-07-21).
    글자가 하나라도 다르면(모델이 문장을 바꿈) 무시하고 아래 규칙 폴백으로 안전하게 내려간다."""
    narr = (narration or "").strip()
    if not narr:
        return []
    if preset and isinstance(preset, (list, tuple)):
        lines = [str(x).strip() for x in preset if str(x).strip()]
        if lines and cap_preset_key("".join(lines)) == cap_preset_key(narr):
            return _wrap_long(lines)
    words = narr.split()
    out, cur = [], []
    for i, w in enumerate(words):
        if not cur:
            cur = [w]
            continue
        bare = _strip_punct(w)
        prev = _strip_punct(cur[-1])
        cur_chars = len("".join(cur))
        room = len("".join(cur + [w])) <= _CAP_TARGET   # 글자수 여유
        under_cap = len(cur) < _CAP_MAX_WORDS           # 어절 상한 이내(하드리밋)
        # 앞 단어가 수식어면(머리 단어이거나 관형격 "-의"로 끝남) 뒤 단어를 반드시
        # 데려가야 한다("마법의 | 가루" 방지) → 이땐 이어붙인다. 단 어절 상한(under_cap)
        # 은 지켜 "꼭 두 세개씩"이 4어절로 폭주하지 않게 한다.
        # ★관형형(2026-08-29 사장님 B규칙): "-는/-된/-한/-던"이나 ㄹ받침(다칠·할·볼…)으로
        #   끝난 어절은 뒤 명사를 꾸미는 중이다 — "채 썰리는 | 모습"·"다칠 | 걱정"으로
        #   가르지 않는다. 명사가 우연히 걸려도(채칼·겨울) 붙는 쪽 오류라 안전하다.
        _jong_l = (lambda w2: bool(w2) and 0xAC00 <= ord(w2[-1]) <= 0xD7A3
                   and (ord(w2[-1]) - 0xAC00) % 28 == 8)
        # ㄹ받침 견인은 **글자수 여유가 있을 때만**(2026-08-29 2차 — '비밀'(명사)의 ㄹ받침이
        # '테이블이'를 14자 넘겨 끌어 "…비밀 테이블이 | 있어요"(17자+고아)를 만들었다.
        # ㄹ받침은 용언 관형형(다칠·쓸)과 명사(비밀·채칼)를 표면으로 못 가른다 → 넘칠 땐 양보).
        # 어미형(는/된/한…)은 확실한 관형형이라 종전대로 상한을 넘겨서라도 지킨다.
        tail_pull = (prev.endswith(("는", "된", "한", "던", "네", "인"))
                     or (_jong_l(prev) and not prev.endswith("들") and room))                     and not cur[-1].endswith((".", "?", "!", "…", ","))
        # 견인의 힘은 둘로 갈린다(2026-08-29 B규칙 실측):
        #  · 머리단어/-의(strong) — 구절 끝에 남으면 안 되는 말: 모든 끊기를 막는다(종전).
        #  · 관형형(tail, "-는/-된/ㄹ받침…") — **글자수 때문에 끊기**만 막는다. 머리단어·
        #    어미·문장 경계 같은 명시적 신호까지 막으면 "며칠 안 | 됐는데"처럼
        #    부정부사('안')가 앞 구절 꼬리에 남는다(실측). 상한은 한 어절까지 양보.
        strong_prev = (prev in _CAP_HEAD or prev.endswith("의")) and under_cap
        tail_hold = tail_pull and (under_cap or len(cur) <= _CAP_MAX_WORDS)
        # (a) 다음 단어가 머리 단어면 그 앞에서 끊어 그 단어를 다음 구절 머리로 만든다.
        #     단 뒤에 데려갈 단어가 있고, 앞 구절이 이미 충분히 길 때만(짧으면 이어붙임 —
        #     "이것 한" 파편 방지). "…일쑤였는데(5자) | 이 방법은"은 앞이 길어 끊긴다.
        head_break = (bare in _CAP_HEAD and i + 1 < len(words)
                      and cur_chars >= _CAP_HEAD_MINCHARS)
        # (b) 현재 구절이 도입어/연결어미로 끝나면 여기서 끊어 한 박자를 준다. 단
        #     연결어미 끊기는 앞 절이 충분히 길 때만("밭에서" 같은 짧은 부사구는 이어붙임).
        lead_break = prev in _CAP_LEAD or (
            prev.endswith(_CAP_LEAD_SUFFIX) and cur_chars >= _CAP_LEAD_MINCHARS
        ) or prev.endswith(_CAP_OPENER_SUFFIX) or (
            # ★절을 닫는 의존명사 뒤 = 좋은 숨 자리(2026-08-29 B규칙: "더 대박인 건 | 요리…").
            #   '채·거·데·때'는 수식으로도 쓰여(채 썰리는) 오탐 — 확실한 넷만.
            prev in ("건", "게", "것", "때문에") and cur_chars >= _CAP_LEAD_MINCHARS)
        # (c) 앞 어절이 문장부호로 끝났으면 문장 경계에서 끊는다. 쉼표도 자연 휴지라
        #     그 뒤에서 끊는다("빵 달라는 아이, | 아무 식빵이나" — 쉼표 넘겨 뭉치지 않게).
        #     ★단 쉼표는 앞 구절이 충분히 길 때만(2026-08-17). 나열형에서 1~2자 파편이
        #     쏟아졌다("요거트, | 계란, | 전분으로…" → 0.27초짜리가 번쩍인다).
        #     연결어미(_CAP_LEAD_MINCHARS)·머리단어(_CAP_HEAD_MINCHARS)와 같은 방어를
        #     쉼표에도 준다. 문장 끝(. ? ! …)은 짧아도 끊는다 — 문장 경계는 지켜야 한다.
        hard_break = cur[-1].endswith((".", "?", "!", "…"))
        comma_break = (cur[-1].endswith((",", "、"))
                       and cur_chars >= _CAP_COMMA_MINCHARS)
        # ★나열 이어가기(2026-08-17 2차): 위 최소글자수만으로는 항목이 4개 이상일 때
        #   나열이 **중간에서** 잘렸다("아침, 풍신, | 빵, 나도 중 댓글 | 남겨주시면").
        #   지금 구절이 '짧은 항목들이 쉼표로 이어진 나열'이면, 한 줄 폭(_CAP_LIST_MAXCHARS)
        #   까지는 계속 붙여 나열을 한 덩어리로 유지한다.
        #   판정: 구절 안의 모든 쉼표 항목이 짧고(_CAP_LIST_ITEMCHARS 이하), 붙여도 폭 이내.
        if comma_break:
            items = [x for x in " ".join(cur).replace("、", ",").split(",") if x.strip()]
            short_list = (len(items) >= 2
                          and all(len(x.replace(" ", "")) <= _CAP_LIST_ITEMCHARS
                                  for x in items))
            if short_list and len("".join(cur + [w])) <= _CAP_LIST_MAXCHARS:
                comma_break = False      # 나열을 이어간다
                # 나열을 이어가기로 했으면 글자수·어절수 상한도 이 폭까지 함께 풀어준다.
                # 안 그러면 not room / not under_cap 이 대신 끊어 같은 자리에서 잘린다
                # (실측: 상한만 남겨두면 "아침, 풍신," 뒤에서 그대로 끊겼다).
                room = True
                under_cap = True
        sent_break = hard_break or comma_break
        # ★의존명사는 구절 머리가 될 수 없다(2026-08-06 실렌더 "…사 드시는 | 거 이제"):
        #   끊을 자리라도 다음 단어가 의존명사면 상한을 한 어절 넘겨서라도 데려간 뒤 끊는다.
        #   기존 병합(아래)은 '마지막 1어절 꼬리'만 잡아 중간 구절 머리는 못 막았다.
        #   문장 경계(sent_break)는 예외 — 문장부호를 넘겨 붙이지 않는다.
        bound_pull = (bare in _CAP_BOUND_NOUN
                      or bare.startswith(_CAP_BOUND_PREFIX)) and not sent_break
        explicit = head_break or lead_break or sent_break
        lengthy = (not room or not under_cap) and not tail_hold
        if not strong_prev and not bound_pull and (explicit or lengthy):
            # ★넘쳐서 끊을 땐 **명사구 한가운데**가 아니라 닫힌 어절(조사·어미로 끝난 곳)
            #   까지 되짚어 끊는다(2026-08-29 사장님 "인테리어 고수들만 안다는 | 비밀
            #   테이블이 있어요 — 이게 맞는 거 아니야?"). 종전엔 넘친 그 자리에서 뚝 끊어
            #   "…안다는 비밀 | 테이블이"처럼 짝을 갈랐다. 명시적 신호(어미·머리단어·문장)로
            #   끊을 땐 이미 좋은 자리라 되짚지 않는다.
            if lengthy and not explicit and len(cur) >= 3:
                _closed = ("는", "은", "이", "가", "을", "를", "도", "에", "로",
                           "고", "서", "면", "요", "죠", "만", "데", "와", "과", "랑")
                for _j in range(len(cur) - 2, 0, -1):
                    _wj = _strip_punct(cur[_j])
                    if _wj.endswith(_closed) and len("".join(cur[:_j + 1])) >= 4:
                        out.append(" ".join(cur[:_j + 1]))
                        cur = cur[_j + 1:] + [w]
                        break
                else:
                    out.append(" ".join(cur))
                    cur = [w]
                if cur and cur[-1] is w and len(cur) > 1:
                    continue          # 룩백으로 나눴다 — w는 이미 cur에 실렸다
                # (룩백 실패 시 아래 기본 경로가 이미 처리됨)
            else:
                out.append(" ".join(cur))
                cur = [w]
        else:
            cur.append(w)
    if cur:
        out.append(" ".join(cur))
    # 고아 꼬리 병합: 마지막 구절이 1어절이면 앞 구절에 붙인다 —
    #   (a) 의존명사 파편이거나("…식단" | "때문?" → "…식단 때문?"), 또는
    #   (b) 붙여도 한 줄(_CAP_WRAP)을 안 넘으면. 어절 상한을 14/4로 키운 뒤 "…우리 | 아이",
    #       "…물러서 | 버렸거든요"처럼 마지막 명사·서술어가 홀로 떨어지는 고아가 생겨서다
    #       (2026-07-25). 화면 폭만 지키면 홀로 뜨는 1어절보다 앞에 붙는 게 늘 낫다.
    if len(out) >= 2 and len(out[-1].split()) == 1:
        merged = out[-2] + " " + out[-1]
        if _strip_punct(out[-1]) in _CAP_BOUND_NOUN \
                or len(merged.replace(" ", "")) <= _CAP_WRAP:
            out[-2] = merged
            out.pop()
    # 목표를 크게 넘는 초장문 단일 구절만 줄바꿈으로 방어(대부분은 그대로 1줄).
    return _wrap_long(out) or [narr]


def _caption_durations(segs, dur, real_durs=None):
    """각 구절의 표시 시간(초) 리스트를 반환. 기본은 글자수 비례(균등분할 X)지만,
    아주 짧은 구절(2~3자)이 순식간에 지나가지 않도록 _CAP_MIN_DUR 하한을 준다.
    하한을 채우고 남은 시간을 나머지 구절에 글자수 비례로 재분배해, 총합은 항상
    dur를 넘지 않는다(하한들의 합이 dur를 초과하면 균등분할로 폴백).

    real_durs가 주어지고(ASR 실측) len(real_durs)==len(segs)이며 합이 0을 넘으면
    글자수 비례 대신 그 값을 base로 쓴다(총합을 dur로 정규화). 그 외(None/길이
    불일치/합0)에는 기존 글자수 비례 경로와 바이트 동일하게 폴백한다."""
    n = len(segs)
    if n == 0:
        return []
    # ★실측(ASR)이 있으면 **하한 폴백보다 먼저** 쓴다(2026-09-01 사장님 "4장면으로 싱크 맞춰").
    #   종전엔 아래 하한 폴백이 위에 있어서, 짧고 구절 많은 칸(하한 1.0초 × 4구절 ≥ 칸 3.55초)은
    #   애써 잰 실측을 통째로 버리고 균등분할했다 — 실측 job 84b5f66a8e1f 칸0(hook):
    #     실측 0.58/0.78/1.13/0.78  →  균등 0.89/0.89/0.89/0.89
    #   구절 맞춤은 컷 경계를 이 값으로 잡으므로 **컷까지 균등**이 되어, 자막 4구절과
    #   화면 4컷이 서로 밀렸다(사장님 3단계↔6단계 캡처 대조로 발각).
    #   바로 아래 주석이 "실측이 있으면 하한을 건너뛴다"라고 이미 못박아 뒀는데, 그 위의
    #   폴백이 먼저 걸려 통째로 무력이었다(CLAUDE.md 0순위-B: 조건부 값을 위에서 덮어쓰기).
    if real_durs is not None and len(real_durs) == len(segs) and sum(real_durs) > 0:
        # ★실측값은 그대로 쓴다 — dur로 되늘리지 않는다(2026-08-06).
        # 예전 `dur * d / s` 정규화는 리드인(자막 밖 무음)까지 구절에 비례배분해 자막을
        # 늘려버려, 애써 실측한 타이밍을 도로 흐트러뜨렸다. 합이 dur를 넘을 때만 줄인다.
        s = sum(real_durs)
        raw = [dur * d / s for d in real_durs] if s > dur else list(real_durs)
        # ★실측이 있으면 하한(_CAP_MIN_DUR)도 건너뛴다(2026-08-29 사장님 "자막이 나오기
        #   전에 음성이 나온다" — 실측 job fa0f71a16a13 beat0: '충격 받았어요' 실발화
        #   0.68초를 하한이 1.0초로 늘려 다음 구절 자막이 0.32초 늦었고, 그만큼 음성이
        #   앞서 들렸다). 하한은 글자수 '추정'이 만든 찰나 구절을 막으려는 장치다 —
        #   실제로 그 길이로 말한 구절을 늘리면 싱크가 깨진다. 짧게 말했으면 짧게 띄운다.
        return raw
    if _CAP_MIN_DUR * n >= dur:      # 하한조차 못 채우면 균등분할 (실측이 없을 때만)
        return [dur / n] * n
    weights = [max(1, len(s.replace("\n", ""))) for s in segs]
    total_w = sum(weights)
    raw = [dur * w / total_w for w in weights]
    # 하한 미달인 구절은 하한으로 올리고, 그만큼을 하한 이상인 구절에서 비례로 회수.
    floored = [max(_CAP_MIN_DUR, r) for r in raw]
    over = sum(floored) - dur
    if over > 1e-6:
        slack_idx = [i for i, r in enumerate(floored) if r > _CAP_MIN_DUR]
        slack_total = sum(floored[i] - _CAP_MIN_DUR for i in slack_idx)
        if slack_total > 1e-6:
            for i in slack_idx:
                floored[i] -= over * (floored[i] - _CAP_MIN_DUR) / slack_total
    return floored


def _adjust_caps_for_trim(beat):
    """(lead_in, durs) — 저장된 cap_lead/cap_durs에 head_trim을 반영해 돌려준다.

    ★왜(2026-08-06): cap_durs·cap_lead는 **합성 시점에 한 번** 계산되고 그 뒤 무효화가
    없다(mix_pipeline). 그런데 사장님이 제작소에서 앞을 트림하면 오디오만 왼쪽으로
    당겨지고 자막 모양은 옛날 그대로 남아 또 어긋났다. 트림한 만큼 리드인에서 갚고,
    리드인으로 모자라면 첫 구절을 파고들어 깎는다(음수 시작 금지).
    """
    durs = beat.get("cap_durs")
    lead = float(beat.get("cap_lead") or 0.0)
    trim = float(beat.get("head_trim") or 0.0)
    if not durs or trim <= 0:
        return lead, (list(durs) if durs else durs)
    durs = list(durs)
    if trim <= lead:
        return lead - trim, durs
    # 리드인을 다 쓰고도 남으면 앞 구절부터 순서대로 깎아 없앤다.
    rest = trim - lead
    for i, d in enumerate(durs):
        if rest <= 0:
            break
        take = min(d, rest)
        durs[i] = d - take
        rest -= take
    return 0.0, durs


def _caption_drawtexts(narration, dur, work, idx, t0=0.0, style=None, real_durs=None, cap_offset=0.0, tail=0.5, cap_lines=None, lead_in=0.0):
    """나레이션 한 비트의 자막(하단 바 + 순차 drawtext)을 필터 문자열 리스트로 반환한다.
    _segmented_drawtext 기반: highlight_rules가 있으면 단어별 강조, 없으면 세그먼트 1개
    (기존과 동일 산출물). 각 구절 enable 구간은 t0(전체 타임라인 오프셋)만큼 밀린다.
    real_durs가 주어지면 _caption_durations에 그대로 전달해 ASR 실측 타이밍을 쓴다.
    cap_lines가 있으면(AI가 끊어준 호흡 줄) 그 경계를 그대로 쓴다 — 규칙 폴백은 안전망."""
    segs = _caption_segments(narration, preset=cap_lines)
    if not segs:
        return []
    style = style or {}
    durs = _caption_durations(segs, dur, real_durs=real_durs)
    size = max(10, _ui_px(style.get("size"), _CAP_FONTSIZE))
    ypct = style.get("y_pct")
    if ypct is None:
        # 기존 폴백 "h-text_h-150"의 근사치를 %로 환산(문자 높이는 size*1.2로 근사)
        # 150 = 1080p 기준 하단 여백(720p 100px ×1.5, 2026-07-24 1080p 업그레이드)
        ypct = max(0.0, min(100.0, (_OUT_H - 150 - size * 0.6) / _OUT_H * 100.0))
    # 자막 가로 위치(%): UI 드래그 결과가 style.x_pct로 온다. 미지정이면 종전대로 중앙(50).
    # 예전엔 아래 _segmented_drawtext 호출에 50이 하드코딩돼, 미리보기로 옮겨도 최종 렌더는
    # 항상 중앙이었다(2026-07-25 배선). 0~100 클램프.
    xpct = style.get("x_pct")
    xpct = 50.0 if xpct is None else max(0.0, min(100.0, float(xpct)))
    use_box = bool(style.get("box"))
    # 하단 자막 바 기본 OFF(2026-07-19) — 300px·black@0.82 바가 화면 하단 23%를
    # 덮어 "검정바"로 보인다는 제보. 그림자 자막만으로 가독성 확보. 원본 소각자막을
    # 덮어야 하는 경우엔 style.bar=True로 명시적으로 켠다(자막제거 ON이면 불필요).
    show_bar = style.get("bar", False) and not use_box
    # 자막 등장효과 기본값 = fade(2026-07-19). 예전 기본 "none"은 자막이 하드
    # 온/오프로 뚝뚝 끊겨 "딱딱하다"는 제보의 원인이었다. 미지정 시 은은한 페이드로
    # 등장시킨다. 끄려면 effect="none"을 명시(문자열이라 truthy → 아래 폴백 안 탐).
    effect = style.get("effect") or "fade"
    parts = []
    if show_bar:
        # ⚠️ enable= 없이는 이 바가 영상 전체 시간대에 걸쳐 그려진다. _burn_captions가
        # 비트마다 _caption_drawtexts를 호출해 필터체인에 이어붙이므로(613~616줄),
        # enable 없는 바 N개가 겹쳐 black@0.82가 누적되어 마지막 비트를 제외한 모든
        # 비트의 자막이 거의 안 보이게 된다(2026-07-15 Task9 실렌더 검증 결함2,
        # 실측 밝기 9/255). 이 비트의 자막 표시 구간(t0 ~ 마지막 세그먼트 종료시각인
        # t0+dur+0.5, 아래 end 계산과 동일)에만 바를 그려 자막 텍스트의 enable 창과
        # 정확히 맞춘다.
        _bs = max(0.0, t0 + cap_offset)
        parts.append(
            f"drawbox=x=0:y=ih-{_BAR_H}:w=iw:h={_BAR_H}:color=black@0.82:t=fill:"
            f"enable='between(t,{_bs:.2f},{t0 + dur + tail + cap_offset:.2f})'"
        )
    # lead_in = 비트 시작~첫 발화까지의 무음(ASR 실측). 0이면 종전과 동일하게 비트 머리에서 시작.
    # 예전엔 항상 0이라, 말이 늦게 시작하는 비트에서 자막이 먼저 떴다(2026-08-06 수정).
    t = max(0.0, float(lead_in or 0.0))
    for i, (seg, d) in enumerate(zip(segs, durs)):
        start = max(0.0, t + t0 + cap_offset)
        t += d
        end = (dur + tail if i == len(segs) - 1 else t) + t0 + cap_offset
        seg_parts = _segmented_drawtext(
            seg, style, work, f"cap_{idx}_{i}", xpct, ypct,
            highlight_rules=style.get("highlight_rules"), default_color="0xFFFFFF",
            single_line=True,   # 자막은 무조건 한 줄(폭 넘으면 폰트 자동축소)
        )
        enable_clause = f"enable='between(t,{start:.2f},{end:.2f})'"
        for sp in seg_parts:
            if effect == "slide":
                # _segmented_drawtext가 만든 "y=<정수>"를 시간기반 슬라이드 표현식으로 치환.
                # 기존 로직과 동일하게 등장 0.25초 동안 +30px 아래에서 위로 미끄러짐.
                sp = re.sub(
                    r"y=(-?\d+)",
                    lambda m: f"y=({m.group(1)}+30*(1-min(1\\,(t-{start:.2f})/0.25)))",
                    sp, count=1,
                )
            elif effect in ("fade", "pop"):
                spd = 0.18 if effect == "fade" else 0.12
                sp = sp + f":alpha='min(1,max(0,(t-{start:.2f})/{spd}))'"
            elif effect == "sparkle":
                # 반짝(CTA/훅): 등장 0.7초 동안 알파가 여러 번 깜빡여 시선을 끈 뒤 고정.
                # abs(sin)로 0↔1 진동(약 3회) → 이후 1로 유지. 단일 quote 안이라 콤마 이스케이프 불필요.
                sp = sp + (
                    f":alpha='if(lt(t,{start:.2f}+0.7),"
                    f"0.30+0.70*abs(sin(2*PI*3*(t-{start:.2f}))),1)'"
                )
            parts.append(sp + ":" + enable_clause)
    return parts


def _caption_vf(narration, dur, has_font, work, idx):
    """비트 영상용 -vf 필터 문자열. scale/crop으로 규격 통일 후, 폰트가 있으면
    하단 바 + 나레이션을 **짧은 구절 단위**로 순차 표시하는 drawtext들을 얹는다.
    각 구절의 표시 시간은 글자수 비례 + 최소 표시시간 하한(_caption_durations).

    ffmpeg 필터그래프는 값에 콜론(윈도 드라이브 'C:')을 못 넣으므로, 폰트·자막
    텍스트는 모두 work 폴더에 두고 **파일명만**(font.ttf / cap_*.txt) 참조한다.
    호출부는 반드시 cwd=work 로 ffmpeg를 실행해야 한다. 각 구절 텍스트는 임시
    파일(textfile=)로 넘겨 따옴표/쉼표 이스케이프 문제를 피한다."""
    base = f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"
    if not has_font:
        return base
    draws = _caption_drawtexts(narration, dur, work, idx)
    if not draws:
        return base
    return ",".join([base] + draws)


def _extend_with_frozen_motion(sub_path, play_out, freeze, out_path):
    """움직이는 클립(sub) 뒤에 freeze초 정지 구간을 붙이되, '죽은 정지'가 아니라 완만한
    켄번즈 줌을 전체(play+freeze)에 얹어 정지 구간에도 화면이 살아있게 한다(2026-07-19,
    P1 후속). 사장님 육안 피드백 — tpad clone 단독 홀드는 마지막 프레임이 픽셀까지 동일해
    뚝 멈춰 어색하다.

    한 체인에서 tpad→zoompan 순서로 건다. 예전 주석의 'zoompan은 tpad와 한 체인에서
    안 된다(출력 잘림)'는 반대 순서(zoompan→tpad)의 문제였다 — tpad를 먼저 두면 출력이
    정상 길이로 나온다(실측 2026-07-19). zoompan은 출력 프레임번호 'on'으로 확대하므로
    tpad가 만든 정지 프레임에서도 줌이 계속 진행돼 움직임이 유지된다."""
    total = play_out + freeze
    _run_ffmpeg([
        "ffmpeg", "-y", "-i", str(sub_path),
        "-vf", f"tpad=stop_mode=clone:stop_duration={freeze:.3f},{_kenburns_vf(total)}",
        "-r", "30", "-an", "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", _mid_preset(), "-crf", _mid_crf(), *_threads_args(), "-pix_fmt", "yuv420p", str(out_path),
    ])
    return out_path


# ── 3초 훅 In-Point 자동(P1, 2026-07-28) ──────────────────────────────
_MIN_HOOK_TAIL = 1.0  # 훅 클립이 최소 이만큼은 남아야(피크가 끝이라도) — 잘린 훅 방지


def pick_hook_start(orig_start, orig_end, base_time, delta=0.0, min_tail=_MIN_HOOK_TAIL):
    """훅 시작점 결정(순수·테스트대상). base_time(자동 모션피크)에 delta(초, UI가 ±0.2씩
    누적한 미세조정)를 더해 [orig_start, orig_end-min_tail]로 클램프. base_time None이면
    orig_start 기준. 윈도우가 좁으면(≤min_tail) orig_start."""
    if orig_end - orig_start <= min_tail:
        return orig_start
    base = base_time if base_time is not None else orig_start
    return max(orig_start, min(base + (delta or 0.0), orig_end - min_tail))


def _hook_delta(work):
    """work.state의 훅 미세조정 오프셋(초). UI [◀0.2s][0.2s▶]가 누적. 없으면 0.0."""
    try:
        st = work.get("state") if isinstance(work, dict) and "state" in work else work
        v = (st or {}).get("hook_inpoint_delta")
        return float(v) if v is not None else 0.0
    except Exception:
        return 0.0


def _apply_hook_inpoint(edit_plan, source_video_paths, work):
    """훅 비트(beats[0]) primary.start를 모션 피크(자동) + UI delta로 이동(P1).
    소스 밖/윈도우 좁음/실패 시 무변경(렌더 안 죽인다). peak_at·hook_delta를 primary에 실어
    프리뷰 UI가 현재 시작점·미세조정을 표시·조절하게 한다."""
    try:
        from shopping_shorts import scene_cut as _sc
        beats = edit_plan.get("beats") or []
        if not beats:
            return
        if (beats[0] or {}).get("scene_override"):
            return   # ★실험실 편성이 있으면 사람 선택이 이긴다 — 훅 시작점 자동이동 안 함
        prim = (beats[0] or {}).get("primary")
        if not prim or prim.get("video_id") not in source_video_paths:
            return
        # ★기준은 **원본 시작점**이다 — 현재 start를 기준으로 삼으면 부를 때마다 더 밀린다
        #   (2026-08-27 실측: 0.0 → 0.1 → 0.8). 멱등하지 않으면 두 가지가 깨진다:
        #     · 렌더를 두 번 하면 훅이 계속 뒤로 밀린다.
        #     · 편성 서명(_plan_signature)이 매번 달라져 **자막제거가 다시 돈다**(VMake 2콜).
        #   그래서 처음 값을 hook_orig_start에 남기고 항상 그것으로 계산한다.
        if prim.get("hook_orig_start") is None:
            prim["hook_orig_start"] = round(float(prim["start"]), 3)
        a, b = float(prim["hook_orig_start"]), float(prim["end"])
        peak_t = _sc.peak_time_in_window(source_video_paths[prim["video_id"]], a, b)
        delta = _hook_delta(work)
        prim["hook_peak_at"] = round(peak_t, 3)
        prim["hook_delta"] = round(delta, 3)
        prim["start"] = pick_hook_start(a, b, peak_t, delta)
    except Exception:
        pass


def _render_mix(edit_plan, tts_paths, source_video_paths, work, cutaway_paths=None):
    """각 비트를 [소스영상+TTS]로 렌더(우리 자막 없음) → concat → mix_raw.mp4 경로.
    자막을 굽지 않으므로 이후 VMake 자막제거가 우리 자막을 지우지 않는다.
    -vf는 우리 자막 vf가 아니라 규격 통일용 base(scale/crop)만 쓴다.
    반중복탐지 회피(항상 자동): 훅·반전 비트는 켄번즈 줌, 나머지는 기본 크롭+줌."""
    _apply_hook_inpoint(edit_plan, source_video_paths, work)  # 훅 시작점 자동/오버라이드(P1)
    important = _important_beat_indices(edit_plan["beats"])
    beat_clips = []
    # 소스 실제 길이 캐시(2026-07-19). 약한 매칭이 소스 밖 구간(예: 60초 릴에 155초)을 잡으면
    # -ss가 끝을 넘어 0프레임 서브클립 → concat "no stream" → 미리보기 전체가 죽었다. 소스별 길이를
    # 한 번만 재서(ffprobe) start를 소스 안으로 당긴다.
    _src_dur_cache = {}
    def _src_dur(vid):
        if vid not in _src_dur_cache:
            try:
                _src_dur_cache[vid] = _probe_duration(source_video_paths[vid])
            except Exception:
                _src_dur_cache[vid] = 0.0
        return _src_dur_cache[vid]
    # 여운 대상 = TTS가 있는 마지막 비트(2026-07-20 T4). 그 비트만 대사 끝+_LAST_RUNOUT초를
    # 화면에 더 싣는다(-t 연장 포함). 세그먼트 전멸로 스킵되면 여운도 조용히 사라진다(치명 아님).
    _runout_idx = max((b["beat_idx"] for b in edit_plan["beats"]
                       if tts_paths.get(b["beat_idx"])), default=None)
    for beat in edit_plan["beats"]:
        idx = beat["beat_idx"]
        tts = tts_paths.get(idx)
        if not tts:
            continue
        tts_dur = _beat_effective_dur(beat, tts)
        _head_trim = beat.get("head_trim", 0.0)
        # ★화면 조각 계획은 **공용 함수 하나**가 정한다(2026-08-23, 0순위-B).
        #   예전엔 이 블록이 여기에만 있어서 캡컷·ZIP 내보내기가 각자 `primary` 하나만
        #   보고 있었다(실측: 조각 19개인 job이 캡컷엔 7개). 이제 셋이 같은 함수를 부른다.
        #   손상/빈 소스 제외·포인트비트 홀드·1장1컷·늘려채우기·여운이 전부 그 안에 있다.
        _srcd = {s.get("video_id"): _src_dur(s.get("video_id"))
                 for s in _beat_material(beat)
                 if s and s.get("video_id") in source_video_paths}
        # 마지막 비트 여운: 실프레임 여유는 1배속으로, 부족분은 아래 slowmo/freeze 기계가 흡수.
        runout = _LAST_RUNOUT if idx == _runout_idx else 0.0
        plan = plan_beat_clips_for(beat, tts_dur, _srcd, runout=runout)
        if not plan:
            continue
        segs = [s for s in _beat_material(beat) if s and _srcd.get(s.get("video_id"), 0.0) > 0.05]
        # ★사장님이 6단계에서 구도를 맞춘 장면은 **켄번즈를 얹지 않는다**(2026-08-30).
        #   켄번즈는 중앙 기준으로 서서히 확대하는 연출이라, 지정한 구도를 밀어낸다 —
        #   "이 자리를 보여달라"는 지시가 연출보다 우선이다.
        _z, _, _ = scene_zoom_of(beat)
        if _z > 1.0001:
            vf = _base_zoom_vf(beat)
        else:
            vf = _kenburns_vf(tts_dur) if idx in important else _base_zoom_vf(beat)
        # 비트당 다중 클립: 각 구간을 [start, start+src_dur]만큼만 잘라(유출 0) 이어붙이고,
        # 부족분은 마지막 클립을 슬로모(setpts)로 늘려 대사 길이에 맞춘다.
        sub_paths = []
        # ★전환용 여유(2026-08-23): xfade는 두 컷을 overlap만큼 **겹치므로** 그냥 겹치면
        #   비트가 overlap*(n-1)만큼 짧아지고, 그러면 뒤 칸 자막이 통째로 밀린다(t0 누적).
        #   그래서 각 컷을 미리 overlap만큼 **길게** 만들어 둔다 → 겹친 뒤 원래 길이가 된다.
        #   컷이 1개면 겹칠 데가 없으니 0.
        # ★여유는 overlap 전부가 아니라 **overlap*(n-1)/n**이다(실측으로 잡은 오류).
        #   컷 n개를 각각 pad만큼 늘려 겹치면 총합 = n*(base+pad) - overlap*(n-1).
        #   이게 원래 n*base와 같으려면 pad = overlap*(n-1)/n.
        #   overlap을 통째로 얹으면 비트가 0.3초쯤 길어져 **뒤 자막이 전부 밀린다**.
        _n = len(plan)
        _pad = (_trans_sec() * (_n - 1) / _n) if _n > 1 else 0.0
        for j, c in enumerate(plan):
            src = source_video_paths[c["video_id"]]
            sub = work / f"beat_{idx}_{j}.mp4"
            # 슬로우 상한(1.15배)+정지프레임(2026-07-19): 무제한 슬로우크롤 제거.
            # 재생은 최대 _MAX_SLOWMO배까지만 늘리고, 남는 시간은 마지막 프레임 정지(freeze).
            # play_out+freeze == out_dur → 총 길이·오디오/자막 싱크 불변.
            # 전환 여유를 이 컷에 얹는다. 소스에 실프레임이 남아 있으면 그것으로(자연스럽다),
            # 없으면 out_dur만 늘려 슬로모/freeze 기계가 흡수한다.
            _c_src, _c_out = c["src_dur"], c["out_dur"]
            if _pad > 1e-3:
                _sd = _src_dur(c["video_id"])
                _room = max(0.0, _sd - (c["start"] + _c_src)) if _sd > 0 else 0.0
                _c_src = _c_src + min(_pad, _room)
                _c_out = _c_out + _pad
            play_out, freeze = _speed_and_freeze(_c_src, _c_out)
            # freeze 클립은 움직이는 부분을 정적 베이스줌으로 두고, 켄번즈 모션은 freeze
            # 패스에서 전체(play+freeze)에 한 번만 건다(정지 구간도 살아있게, 2026-07-19).
            # 안 그러면 pass1 줌 + freeze 켄번즈가 겹쳐 줌이 두 번 쌓인다.
            clip_vf = _base_zoom_vf(beat) if freeze > 1e-3 else vf
            factor = play_out / _c_src if _c_src > 1e-6 else 1.0
            vf_full = f"{clip_vf},setpts={factor:.6f}*PTS" if factor > 1.0 + 1e-6 else clip_vf
            # start를 소스 안으로 당긴다(타트랙 병합, 2026-07-19). 약한 매칭이 소스 밖을 잡으면
            #   -ss가 끝을 넘어 0프레임이 나와 concat이 죽는다. [start, start+src_dur]가 소스
            #   안에 들어오게 당기되, 소스가 src_dur보다 짧으면 0에서 있는 만큼 읽는다.
            sdur = _src_dur(c["video_id"])
            start = c["start"]
            if sdur > 0:
                start = max(0.0, min(start, sdur - min(_c_src, sdur)))
            # 1단계 — 움직임: 입력을 [start, start+src_dur]만 읽어(-ss+입력측 -t) 유출 차단.
            #   입력 제한이 핵심(P1) — 상한 배율이 out_dur/src_dur보다 작으면 setpts가 다음
            #   구간까지 끌어와 유출된다(다색 소스 실측). 잘라두면 이 구간만 play_out으로 늘어난다.
            sub = work / f"beat_{idx}_{j}.mp4"
            # 🔎 강조가 있으면 -vf 대신 filter_complex(오버레이가 필요해 단일 체인으로 안 된다).
            #   성장 애니메이션은 **첫 컷에서만** — 컷마다 다시 튀면 여러 번 나오는 것처럼 보인다.
            _hl_fc = highlight_fc(beat, vf_full, grow=(j == 0))
            _vf_args = (["-filter_complex", _hl_fc, "-map", "[out]"] if _hl_fc
                        else ["-vf", vf_full])
            _run_ffmpeg([
                "ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{_c_src:.3f}",
                "-i", str(src),
                *_vf_args, "-r", "30", "-an", "-t", f"{play_out:.3f}",
                "-c:v", "libx264", "-preset", _mid_preset(), "-crf", _mid_crf(), *_threads_args(), "-pix_fmt", "yuv420p", str(sub),
            ])
            # 그래도 비면(소스 손상/범위밖) 이 클립만 버린다 — 하나가 미리보기 전체를 죽이지 않게.
            if not sub.exists() or _probe_duration(sub) <= 0.05:
                continue
            # 2단계 — 정지프레임(P1 후속, 2026-07-19): 마지막 프레임을 freeze초 홀드하되
            #   전체에 켄번즈를 얹어 '죽은 정지'가 아니라 움직이는 홀드로 만든다. tpad→zoompan
            #   순서면 한 체인에서 정상 동작(_extend_with_frozen_motion 주석 참조).
            if freeze > 1e-3:
                frozen = work / f"beat_{idx}_{j}f.mp4"
                _extend_with_frozen_motion(sub, play_out, freeze, frozen)
                sub_paths.append(frozen)
            else:
                sub_paths.append(sub)
        if not sub_paths:
            # 이 비트는 쓸 클립이 하나도 없다(모든 소스 손상/범위밖). 비트를 건너뛴다 —
            # 미리보기가 통째로 죽는 것보다 이 비트만 빠지는 게 낫다.
            continue
        # 비트의 클립들(동일 규격)을 concat → 비트 무음 영상(길이 ≈ tts_dur)
        beat_video = work / f"beat_{idx}_v.mp4"
        # ★컷 전환(2026-08-23 사장님 "부자연스럽다 / 캡컷을 대체하고 싶다"):
        #   켜져 있으면 컷 사이를 xfade로 겹쳐 넘긴다.
        #   ★총 길이는 concat과 **같아야** 한다 — 자막이 비트 t0 누적으로 자리를 잡으므로
        #     비트가 조금이라도 길어지면 뒤 자막이 통째로 밀린다.
        #     그래서 컷을 미리 overlap만큼 길게 뽑아둔다(아래 out_dur 보정).
        #   실패하거나 여유가 없으면 조용히 하드컷으로 돌아간다 — 렌더를 죽이지 않는다.
        faded = None
        _tsec = _trans_sec()
        if _tsec > 1e-3 and len(sub_paths) > 1:
            faded = _xfade_concat(sub_paths, work / f"beat_{idx}_x.mp4",
                                  _tsec, _trans_kind())
        if faded is not None:
            beat_video = faded
        else:
            cat = work / f"beat_{idx}_list.txt"
            cat.write_text("".join(f"file '{p.as_posix()}'\n" for p in sub_paths), encoding="utf-8")
            _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(cat),
                         "-c", "copy", str(beat_video)])
        # 컷어웨이(장면라이브러리 페이즈2-B): 라이브러리 자산을 비트 영상 위에 풀프레임
        # 오버레이. 창=[0, min(자산길이, tts_dur)]. 비트 길이·TTS 오디오 불변 → 자막 t0 싱크
        # 불변. beat_video는 이미 규격(1080x1920)·vf 적용 → 재-vf 없이 오버레이만 얹는다.
        clip = work / f"beat_{idx}.mp4"
        cutaway = (cutaway_paths or {}).get(idx)
        if cutaway:
            asset_dur = _probe_duration(cutaway)
            win = min(asset_dur, tts_dur)
            fc = (
                f"[1:v]scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,"
                f"crop={_OUT_W}:{_OUT_H},setpts=PTS-STARTPTS[ov];"
                f"[0:v][ov]overlay=0:0:enable='between(t,0,{win:.3f})'[vout]"
            )
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-i", str(beat_video),   # 0: 내 다중클립 비트영상(이미 vf 적용)
                "-i", str(cutaway),      # 1: 컷어웨이 자산(오디오 버림 = b-roll)
                "-ss", f"{_head_trim:.3f}", "-i", str(tts),          # 2: 나레이션(앞트림 반영)
                "-filter_complex", fc, "-r", "30",
                "-map", "[vout]", "-map", "2:a:0",
                # 여운(runout): 마지막 비트만 대사 뒤 화면이 더 산다 — 오디오는 tts 길이에서
                # 자연 종료(무성 여운). 컷어웨이 창(win)은 tts_dur 기준 그대로(여운을 덮지 않음).
                "-t", f"{tts_dur + runout:.3f}",
                "-c:v", "libx264", "-preset", _mid_preset(), "-crf", _mid_crf(), *_threads_args(), "-c:a", "aac", "-pix_fmt", "yuv420p", str(clip),
            ])
        else:
            # 비트 나레이션(tts) 오디오를 얹고 길이를 tts_dur(+마지막 비트는 여운)로 맞춘다.
            _run_ffmpeg([
                "ffmpeg", "-y", "-i", str(beat_video),
                "-ss", f"{_head_trim:.3f}", "-i", str(tts),
                "-map", "0:v:0", "-map", "1:a:0", "-t", f"{tts_dur + runout:.3f}",
                "-c:v", "copy", "-c:a", "aac", str(clip),
            ])
        beat_clips.append(clip)
    if not beat_clips:
        raise RuntimeError("video_assemble: 렌더할 비트가 없습니다")
    concat_txt = work / "concat_mix.txt"
    concat_txt.write_text("".join(f"file '{c.as_posix()}'\n" for c in beat_clips), encoding="utf-8")
    # 비트 클립들은 이미 동일 설정(1080x1920 libx264/aac 30fps)이므로 -c copy로 붙인다
    # (재인코딩 concat은 2GB 서버에서 수십 초 → 배포 재시작에 걸려 죽던 원인, 2026-07-12).
    mix_raw = work / "mix_raw.mp4"
    _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                 "-c", "copy", str(mix_raw)])
    return str(mix_raw)


# ── 컷 전환 설정(2026-08-23) ─────────────────────────────────────────────────
# 정의처는 config 하나. 여기서 한 번 읽어 렌더 전체가 같은 값을 쓴다(0순위-B).
def _trans_sec():
    try:
        from shopping_shorts import config as _c
        return max(0.0, float(getattr(_c, "TRANSITION_SECONDS", 0.0) or 0.0))
    except Exception:
        return 0.0


def _trans_kind():
    try:
        from shopping_shorts import config as _c
        return str(getattr(_c, "TRANSITION_KIND", "fade") or "fade")
    except Exception:
        return "fade"


def _xfade_concat(clip_paths, out_path, overlap, kind="fade"):
    """컷들을 xfade로 겹쳐 이어 붙인다. **총 길이는 concat과 같다.**

    ★왜 길이가 같아야 하나: 자막·오디오는 비트 t0를 누적해서 자리를 잡는다
      (`t0 += dur`). 비트가 조금이라도 길거나 짧아지면 **그 뒤 자막이 통째로 밀린다**.
      xfade는 두 영상을 overlap만큼 **겹치므로** 이어붙인 총 길이가
      sum(len) - overlap*(n-1)이 된다. 그래서 각 컷을 미리 overlap만큼 길게 받아
      (호출부가 `+overlap`으로 뽑아준다) 겹친 뒤 원래 합계가 되게 맞춘다.

    겹칠 수 없으면(컷이 1개거나 너무 짧으면) None을 돌려준다 — 호출부가 하드컷으로 간다.
    """
    if len(clip_paths) < 2 or overlap <= 1e-3:
        return None
    durs = [_probe_duration(p) for p in clip_paths]
    if any(d <= overlap + 0.05 for d in durs):
        return None                      # 겹칠 여유가 없는 컷이 있으면 통째로 포기
    args, fc, cur = [], [], "0:v"
    for i, p in enumerate(clip_paths):
        args += ["-i", str(p)]
    acc = durs[0]
    for i in range(1, len(clip_paths)):
        off = acc - overlap              # 앞 영상이 끝나기 overlap초 전부터 겹친다
        lbl = f"x{i}"
        fc.append(f"[{cur}][{i}:v]xfade=transition={kind}:duration={overlap:.3f}"
                  f":offset={off:.3f}[{lbl}]")
        cur = lbl
        acc = off + durs[i]              # 겹친 만큼 총길이가 줄어든다
    try:
        _run_ffmpeg(["ffmpeg", "-y", *args, "-filter_complex", ";".join(fc),
                     "-map", f"[{cur}]", "-r", "30", "-an",
                     "-c:v", "libx264", "-preset", _mid_preset(), "-crf", _mid_crf(),
                     *_threads_args(), "-pix_fmt", "yuv420p", str(out_path)])
    except Exception:
        return None                      # 전환에 실패해도 렌더 전체를 죽이지 않는다
    if not out_path.exists() or _probe_duration(out_path) <= 0.05:
        return None
    return out_path


def _motion_layer_filters(layers, next_input_idx, vcur):
    """해석완료 레이어 리스트(_abspath 보유) → filter_complex 조각.
    각 레이어를 vcur 위에 투명 오버레이로 얹는다. dur=None이면 enable 생략(전체 재생).
    반환: (input_args, fc_parts, vcur_out, next_input_idx_out).
    - input_args: ffmpeg에 추가할 ["-i", path, ...]
    - fc_parts: filter_complex 세미콜론 조각 리스트
    - vcur_out: 마지막 비디오 스트림 라벨(다음 필터가 이어받음)

    ⚠️ enable=은 "언제 그릴지"만 정할 뿐, 소스 스트림이 몇 초 지점을 재생 중인지는
    그대로 벽시계 시간(입력 스트림 자체의 PTS, t=0부터)을 따라간다. start>0인 레이어를
    enable만으로 게이팅하면, enable 창이 열릴 때 그 자산은 이미 자기 시간으로 그 이상
    지나 끝난 뒤라(짧은 전환/스티커는 정지 마지막 프레임) 재생이 아니라 정지 잔상만
    보인다(2026-07-15 Task9 실렌더 검증 결함1). setpts=PTS-STARTPTS+start/TB로 레이어
    자신의 PTS를 start초만큼 뒤로 밀어, enable 창이 열리는 순간 자산이 자기 0초부터
    재생되도록 맞춘다(ffmpeg 표준 "시간차 오버레이" 레시피).
    """
    input_args = []
    fc = []
    idx = next_input_idx
    for i, L in enumerate(layers or []):
        path = L.get("_abspath")
        if not path:
            continue
        input_args += ["-i", path]
        w = L.get("width")
        scale = f"scale={int(w)}:-1," if w else ""
        aa = max(0.0, min(1.0, float(L.get("alpha", 1))))
        xf = min(1.0, max(0.0, float(L.get("x", 50)) / 100.0))
        yf = min(1.0, max(0.0, float(L.get("y", 50)) / 100.0))
        lab, out = f"ml{i}", f"mlv{i}"
        start = float(L.get("start") or 0)
        dur = L.get("dur")
        # start>0일 때만 setpts를 얹는다(start=0은 원점이라 이동이 no-op — 필터 문자열을
        # 불필요하게 늘리지 않고 기존 산출물과의 호환성도 유지).
        ts = f"setpts=PTS-STARTPTS+{start:.3f}/TB," if start > 0 else ""
        fc.append(f"[{idx}:v]{ts}{scale}format=rgba,colorchannelmixer=aa={aa:.2f}[{lab}]")
        en = f":enable='between(t,{start:.3f},{start + float(dur):.3f})'" if dur is not None else ""
        fc.append(f"[{vcur}][{lab}]overlay=x=W*{xf:.4f}-w/2:y=H*{yf:.4f}-h/2{en}[{out}]")
        vcur = out
        idx += 1
    return input_args, fc, vcur, idx


def _hex_to_ff(c, default="0xFFFFFF"):
    """'#FF8800' → '0xFF8800' (ffmpeg drawtext color). 이상하면 default."""
    c = (c or "").strip().lstrip("#")
    return f"0x{c.upper()}" if len(c) == 6 and all(ch in "0123456789ABCDEFabcdef" for ch in c) else default


def _outline_parts(style):
    """외곽선 drawtext 조각. **꺼져 있거나 두께 0이면 아무것도 안 붙인다.**

    ★2026-08-31 실사고: 종전 `borderw=max(1, _ui_px(outline_w, 9))`는 UI에서 두께를
      0으로 내려도 _ui_px가 0을 "값 없음"으로 보고 기본값 9를 되살렸다. 그래서
      미리보기엔 없는 **굵은 검정 테두리**가 최종렌더에만 붙었다(흰 자막에선 원래
      테두리처럼 보여 안 걸리고, 검정 자막에서 글자가 뭉개져 발각).
      0은 box_pad와 똑같이 "없음"이라는 뜻이다 → zero_ok로 읽는다.
    같은 판단이 자막·헤드카피 두 곳에 따로 적혀 있어 한 곳만 고치면 어긋난다 → 함수 하나."""
    if not style.get("outline"):
        return []
    w = max(0, _ui_px(style.get("outline_w"), 9, zero_ok=True))
    if w <= 0:
        return []
    return [f"borderw={w}",
            f"bordercolor={_hex_to_ff(style.get('outline_color'), '0x000000')}"]


def _missing_glyphs(font_path, text):
    """→ font_glyphs.missing_glyphs (판정은 한 곳에서만 — 0순위-B)."""
    return _fg.missing_glyphs(font_path, text)



def _font_ref(font_name, work, key, text=""):
    """폰트 파일명 → work에 복사한 뒤 쓸 ffmpeg fontfile 참조명(상대경로).

    폰트 해석 규칙의 **단일 출구**다(0순위-B) — _resolve_seg_font·_fixed_drawtext가
    같은 판단을 따로 적고 있어서 한쪽만 고치면 어긋난다. 규칙:
      ① 파일이 없으면              → 기본 자막폰트 font.ttf
      ② 문구를 **거의 다** 못 그리면 → 기본 자막폰트 font.ttf (두부 방지) + 경고
      ③ 그 외                      → 그 폰트 (몇 글자 빠져도 사장님이 고른 글꼴을 지킨다)

    ★왜 '한 글자라도'가 아니라 '거의 다'인가 (2026-08-26 실측)
      완성형 2350자 폰트 10종이 '뷁·똠·뎊'을 못 그린다. 한 글자만 없어도 폴백시키면
      자막에 '똠양꿍'이 들어간 순간 배민 주아를 골라도 통째로 다른 글꼴이 된다 —
      두부 한 글자보다 글꼴이 통째로 바뀌는 쪽이 더 큰 사고다.
      막으려는 건 '옥 말랑'처럼 **한글이 아예 없는 폰트**다(그 경우 100% 누락).
      실사용 글자 121자 점검에서 정상 폰트의 최대 누락은 3자(2.5%)였다.
    """
    fontref = "font.ttf"  # _burn_captions가 work에 복사해둔 기본폰트
    fname = os.path.basename(font_name or "")
    if not fname:
        return fontref
    fpath = _FONT_DIR / fname
    if not fpath.exists():
        return fontref
    body = "".join(dict.fromkeys((text or "").replace(" ", "")))
    miss = _missing_glyphs(fpath, text)
    if miss and body and len(miss) / len(body) >= _FONT_FALLBACK_RATIO:
        print(f"[폰트] {fname} 이 문구의 {len(miss)}/{len(body)}자를 못 그린다"
              f"({miss[:12]}) — 기본폰트로 대체한다(두부 방지)", file=sys.stderr)
        return fontref
    if miss:
        # 몇 글자만 빠졌다 — 글꼴은 지키고 흔적만 남긴다(그 글자만 두부가 된다).
        print(f"[폰트] {fname} 에 없는 글자 {len(miss)}자({miss[:12]}) — "
              f"글꼴은 그대로 쓴다", file=sys.stderr)
    shutil.copy(fpath, work / f"font_{key}.ttf")
    return f"font_{key}.ttf"


def _resolve_seg_font(base_style, work, key_prefix, text=""):
    """세그먼트 폰트파일 경로(work에 복사된 실제 경로)와 ffmpeg fontfile 참조명을 함께 반환."""
    fontref = _font_ref((base_style or {}).get("font"), work, key_prefix, text)
    return fontref, str(work / fontref)


def _lacks_space_glyph(pil_font):
    """→ font_glyphs.lacks_space_glyph (판정은 한 곳에서만 — 0순위-B)."""
    return _fg.lacks_space_glyph(pil_font)


def _space_px(pil_font, size):
    """→ font_glyphs.space_px"""
    return _fg.space_px(pil_font, size)


def _text_px(pil_font, text, size):
    """→ font_glyphs.text_px"""
    return _fg.text_px(pil_font, text, size)



def _build_segments(line, base_color, highlight_rules):
    """한 줄 텍스트를 highlight_rules 기준으로 [(text, color, box, box_color), ...]로 쪼갠다.

    ★부분 문자열 매칭(2026-08-30 사장님 "바꾸고 싶은 글자만 색"). 예전엔 공백으로 나눈
    **단어 전체**가 일치할 때만 색이 바뀌어서, "쿠팡꿀템"의 '꿀템'만 노랗게는 못 했다.
    이제 규칙의 글자열이 줄 안 어디에 있든 그 자리만 다른 색이 된다(긴 규칙 먼저 잡아
    짧은 규칙이 겹쳐 먹지 않게 한다).

    규칙이 없거나 매칭 0건이면 세그먼트 1개 = 기존과 같은 산출물(하위호환).
    ※단어 전체 일치도 부분 일치의 한 경우라 종전 동작을 그대로 포함한다."""
    if not line:
        return []
    base = (base_color, False, None)
    marks = [None] * len(line)
    rules = [r for r in (highlight_rules or []) if r.get("keyword")]
    # ★사람이 고른 낱말이 **틀(_fromFrame)보다 먼저** 자리를 잡는다(2026-09-02).
    #   틀(템플릿)은 2줄째 통째를 키워드로 규칙을 하나 넣는데(produce.html applyHeadcopySet),
    #   길이만으로 정렬하면 그 긴 규칙이 사람이 고른 짧은 낱말을 통째로 덮어
    #   **색을 바꿔도 안 바뀐다**(marks가 이미 찼으므로 나중 규칙이 못 들어간다).
    #   화면(hlSegments)과 **같은 규칙**이어야 미리보기와 렌더가 안 어긋난다(0순위-B).
    # 길이 우선은 같은 등급 안에서만 — 짧은 규칙이 먼저 자리를 잡으면 긴 규칙이 조각나 색이 튄다.
    for rule in sorted(rules, key=lambda r: (bool(r.get("_fromFrame")), -len(r["keyword"]))):
        kw = rule["keyword"]
        style = (rule.get("color"), bool(rule.get("box")), rule.get("box_color"))
        pos = line.find(kw)
        while pos >= 0:
            for i in range(pos, pos + len(kw)):
                if marks[i] is None:
                    marks[i] = style
            pos = line.find(kw, pos + len(kw))
    segs = []
    cur_text, cur_style = "", None
    for ch, st in zip(line, marks):
        st = st or base
        if cur_style is None:
            cur_text, cur_style = ch, st
        elif st == cur_style:
            cur_text += ch
        else:
            segs.append((cur_text, *cur_style))
            cur_text, cur_style = ch, st
    if cur_text:
        segs.append((cur_text, *cur_style))
    return segs


def _char_split(word, font, max_w):
    """공백 없는 한 단어를 폭 안에 들어가게 글자 단위로 쪼갠다(한글은 띄어쓰기가 적어
    단어 자체가 폭을 넘는 일이 흔하다)."""
    out, cur = [], ""
    for ch in word:
        if cur and font.getlength(cur + ch) > max_w:
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return out


def _wrap_to_width(line, font, max_w):
    """한 줄을 폭(max_w) 안에 들어가게 나눈다 — 단어(공백) 단위 그리디, 한 단어가 폭을
    넘으면 글자 단위로 쪼갠다. 빈 줄은 빈 줄로 보존. 미리보기의 자동 줄바꿈(CSS pre-wrap)과
    최종 렌더를 맞춰, 긴 헤드카피가 화면 밖으로 넘치지 않고 사용자가 본 그대로 나오게 한다."""
    if not line:
        return [""]
    out, cur = [], ""
    for w in line.split(" "):
        trial = w if not cur else cur + " " + w
        if not cur:
            if font.getlength(w) <= max_w:
                cur = w
            else:
                pieces = _char_split(w, font, max_w)
                out.extend(pieces[:-1])
                cur = pieces[-1]
        elif font.getlength(trial) <= max_w:
            cur = trial
        else:
            out.append(cur)
            if font.getlength(w) <= max_w:
                cur = w
            else:
                pieces = _char_split(w, font, max_w)
                out.extend(pieces[:-1])
                cur = pieces[-1]
    out.append(cur)
    return out


def _segmented_drawtext(text, base_style, work, key_prefix, x_pct, y_pct,
                          highlight_rules=None, default_color="0xFFFFFF", single_line=False,
                          fit_lines=False, block_box=False):
    """헤드카피/자막 한 블록을 줄 단위로 나누고, highlight_rules에 매칭되는 단어만
    별도 색·배지로 세그먼트를 쪼개 나란히 이어붙인 drawtext 필터 리스트를 반환한다.
    규칙이 없거나 매칭 0건이면 줄마다 세그먼트 1개 = 기존 _fixed_drawtext/_caption_drawtexts와
    동일한 산출물(하위호환). 폭 측정은 Pillow로 실제 폰트파일 기준 수행.
    single_line=True(자막): 절대 줄바꿈하지 않고 **한 줄**로 두되, 폭을 넘으면 폰트를
    자동 축소해 한 줄에 맞춘다(사장님: 자막은 무조건 한 줄). 미리보기도 동일 비율로 축소.
    fit_lines=True(헤드카피): 사장님이 넣은 줄바꿈을 **그대로 지킨다**. 폭을 넘으면 줄을
    늘리지 않고 폰트를 줄여 맞춘다 — 썸네일 쪽(produce.html thumbFit)과 같은 규칙이다.
    2026-08-19 사장님: "썸네일쪽처럼 두 줄로 정렬되게" — 2줄로 쓴 문구가 자동 줄바꿈에
    걸려 4줄로 깨져 나왔다(캡처). 줄 수는 사장님이 정하고, 크기는 기계가 맞춘다."""
    base_style = base_style or {}
    lines = (text or "").split("\n")
    if not any(l.strip() for l in lines):
        return []
    fontref, font_disk_path = _resolve_seg_font(base_style, work, key_prefix, text)
    size = max(8, _ui_px(base_style.get("size"), 96))
    try:
        pil_font = ImageFont.truetype(font_disk_path, size)
    except OSError:
        pil_font = ImageFont.load_default()
    # 안전 여백 — 글자는 화면 폭의 0.86까지만 쓴다(2026-08-30 사장님 "옆에가 짤리잖아").
    # 0.92는 좌우 여백이 4%뿐이라, 인스타·유튜브가 화면비에 맞춰 조금만 확대해도
    # 양끝 글자가 잘려 나간다(실측: "방충망 먼지 빨리 해결"은 원폭 1275px→993px로
    # 줄여도 폭을 꽉 채웠고, 외곽선 10px가 더 번져 사실상 여백이 없었다).
    # 자막도 같은 위험이라 같은 값을 쓴다 — 한 줄 강제라 길면 **항상** 폭을 꽉 채운다.
    # ★미리보기(produce.html _boxW·capAvail)와 **같은 값**이어야 한다(0순위-B).
    max_w = _SAFE_W * _OUT_W
    if single_line:
        # 자막: 개행·연속공백을 한 칸으로 접어 한 줄로. 폭 초과 시 폰트 축소(줄바꿈 금지).
        one = " ".join(" ".join(lines).split())
        w = _text_px(pil_font, one, size) if one else 0
        if w > max_w:
            size = max(8, int(size * max_w / w))
            try:
                pil_font = ImageFont.truetype(font_disk_path, size)
            except OSError:
                pass
        lines = [one]
    elif fit_lines:
        # 헤드카피: 줄 수는 그대로, 가장 넓은 줄이 폭에 들어가게 폰트만 줄인다.
        widest = max((_text_px(pil_font, ln, size) for ln in lines if ln), default=0)
        if widest > max_w:
            size = max(8, int(size * max_w / widest))
            try:
                pil_font = ImageFont.truetype(font_disk_path, size)
            except OSError as e:  # noqa: BLE001 — 폰트 재적재 실패는 축소만 못 할 뿐, 그리기는 계속한다
                print(f"[헤드카피] 폰트 축소 실패(무시): {e!r}", file=sys.stderr)
    else:
        # 폭 초과 줄 자동 줄바꿈 — 미리보기(pre-wrap)와 맞춰 최종 영상도 화면 밖으로 안 넘게.
        lines = [seg for ln in lines for seg in _wrap_to_width(ln, pil_font, max_w)]
    base_color_raw = base_style.get("color")  # 원시 #hex(또는 None) — _hex_to_ff는 drawtext 빌드에서 1회만 적용(이중변환 방지)
    x_center = x_pct / 100.0 * _OUT_W
    y_top = y_pct / 100.0 * _OUT_H
    # 줄 간격 — 1.2는 두꺼운 한글 폰트에서 윗줄 받침과 아랫줄 머리가 맞닿아 **겹쳐 보인다**
    # (2026-08-30 사장님 제보, job 36a02e5ad1ef '방충망 먼지 빨리 해결/다이소 꿀템').
    # 미리보기(produce.html #hcPreviewText line-height)와 **같은 값**이어야 한다(0순위-B).
    line_h = size * 1.34
    total_h = line_h * len(lines)
    parts = []
    # ── 🟨 배경 박스는 **블록 하나**로 (2026-08-30 사장님 "헤드커피 부분이 분리되서 나옴")
    # 종전엔 줄마다 drawtext에 box=1을 걸어, 두 줄짜리 헤드카피가 **박스 2개**로 갈라져
    # 나왔다(실측: 조각 2개, x=42 / x=272 — 줄 폭이 달라 시작점도 어긋난다). 그런데
    # 미리보기(produce.html updateHC)는 글자 덩어리 하나에 배경을 깔아 **한 덩어리**였다.
    # → 같은 판단이 두 곳에 다르게 적힌 것(0순위-B). 렌더를 미리보기 규칙에 맞춘다:
    #     세로 여백 = box_pad, 가로 여백 = box_pad*1.5, 모서리 = 30px(=10*3, 720 기준)
    if block_box and base_style.get("box"):
        _pad = max(0, _ui_px(base_style.get("box_pad"), 24, zero_ok=True))
        _widest = 0
        for _ln in lines:
            _segs = _build_segments(_ln, base_color_raw, highlight_rules or [])
            _widest = max(_widest, sum(_text_px(pil_font, s[0], size) for s in _segs))
        if _widest > 0:
            _bw = _widest + _pad * 3            # 좌우 각각 pad*1.5
            _bh = total_h + _pad * 2
            _bx = int(round(x_center - _bw / 2))
            _by = int(round(y_top - total_h / 2 - _pad))
            _bc = _hex_to_ff(base_style.get("box_color"), "0x000000")
            _op = max(0.0, min(1.0, (base_style.get("box_opacity") or 80) / 100.0))
            parts.append(f"drawbox=x={_bx}:y={_by}:w={int(round(_bw))}:h={int(round(_bh))}:"
                         f"color={_bc}@{_op:.2f}:t=fill")
    for li, line in enumerate(lines):
        segs = _build_segments(line, base_color_raw, highlight_rules or [])
        if not segs:
            continue
        widths = [_text_px(pil_font, s[0], size) for s in segs]
        line_w = sum(widths)
        start_x = x_center - line_w / 2
        line_y = y_top - total_h / 2 + li * line_h
        run_x = start_x
        # ★공백 글리프가 없는 폰트(빙그레·리디바탕)에서는 띄어쓰기를 drawtext에 **넘기지
        #   않는다** — 넘기면 ⊠(.notdef 네모)로 그려진다(2026-08-24 고객 제보 실측).
        #   대신 어절을 따로 그리고 사이는 좌표로 벌린다. 정상 폰트는 종전 그대로 한 번에
        #   그린다(회귀 0) — 어절을 쪼개면 box 스타일의 배경이 어절마다 끊기기 때문이다.
        no_space = _lacks_space_glyph(pil_font)
        gap = _space_px(pil_font, size)
        for (seg_text, seg_color, seg_box, seg_box_color), w in zip(segs, widths):
            if not seg_text.strip():
                run_x += w
                continue
            chunks = ([t for t in seg_text.split(" ") if t] if no_space
                      else [seg_text.rstrip()])
            cx = run_x
            for chunk in chunks:
                key = f"{key_prefix}_{li}_{len(parts)}"
                (work / f"txt_{key}.txt").write_text(chunk, encoding="utf-8")
                seg_parts = [
                    f"drawtext=fontfile={fontref}:textfile=txt_{key}.txt",
                    f"fontcolor={_hex_to_ff(seg_color, default_color)}",
                    f"fontsize={size}",
                    f"x={int(cx)}", f"y={int(line_y)}",
                ]
                seg_parts += _outline_parts(base_style)
                if base_style.get("shadow"):
                    # 은은한 드롭 그림자(레퍼런스 자막룩) — 두꺼운 테두리 대신 부드러운 가독성.
                    sc = _hex_to_ff(base_style.get("shadow_color"), "0x000000")
                    sd = max(1, _ui_px(base_style.get("shadow_d"), 5))
                    seg_parts += [f"shadowcolor={sc}@0.55", f"shadowx={sd}", f"shadowy={sd}"]
                if seg_box:
                    # ★강조 단어 박스도 **자막 박스와 같은 투명도·여백**을 쓴다(0순위-B).
                    #   종전엔 @0.90 / boxborderw=12 하드코딩이라 화면에서 정한 값이
                    #   통째로 무시됐다(2026-08-31). 색만 강조 규칙의 것을 쓴다.
                    bc = _hex_to_ff(seg_box_color, "0x000000")
                    _op = max(0.0, min(1.0, (base_style.get("box_opacity") or 90) / 100.0))
                    _pad = max(0, _ui_px(base_style.get("box_pad"), 12, zero_ok=True))
                    seg_parts += ["box=1", f"boxcolor={bc}@{_op:.2f}", f"boxborderw={_pad}"]
                elif base_style.get("box") and block_box:
                    pass          # 배경은 아래에서 **블록 하나**로 미리 그렸다(줄마다 안 그린다)
                elif base_style.get("box") and not seg_box:
                    bc = _hex_to_ff(base_style.get("box_color"), "0x000000")
                    op = max(0.0, min(1.0, (base_style.get("box_opacity") or 80) / 100.0))
                    pad = max(0, _ui_px(base_style.get("box_pad"), 24, zero_ok=True))
                    seg_parts += ["box=1", f"boxcolor={bc}@{op:.2f}", f"boxborderw={pad}"]
                parts.append(":".join(seg_parts))
                cx += pil_font.getlength(chunk) + gap
            run_x += w
    return parts


def _fixed_drawtext(spec, work, key, default_color="0xFFFFFF"):
    """고정 위치 drawtext 공용 생성기(헤드카피·추가텍스트·워터마크). text·폰트 파일은
    key로 유일화(txt_{key}.txt / font_{key}.ttf)해 여러 개를 한 필터그래프에 안전히 얹는다.
    x/y는 % 위치(가로·세로 중심). spec.alpha(0~1)로 전체 투명도(워터마크용). text 없으면 None.
    spec['font']이 static/fonts의 실제 파일이면 그 폰트, 아니면 기본 자막폰트(font.ttf)."""
    text = (spec.get("text") or "").strip()
    if not text:
        return None
    (work / f"txt_{key}.txt").write_text(text, encoding="utf-8")
    fontref = _font_ref(spec.get("font"), work, key, text)
    size = max(8, _ui_px(spec.get("size"), 96))
    xf = min(1.0, max(0.0, (spec.get("x", 50)) / 100.0))
    yf = min(1.0, max(0.0, (spec.get("y", 14)) / 100.0))
    # 워터마크 등 spec.float가 켜지면 y를 시간표현식으로 만들어 위아래로 은은히 떠다니게 한다
    # (진폭=화면높이 0.6%, 주기 3s). ffmpeg 식평가는 sin/PI/t 지원(자막 슬라이드에서 검증됨).
    if spec.get("float"):
        y_expr = f"y=(h*{yf:.4f}-th/2+h*0.006*sin(2*PI*t/3))"
    else:
        y_expr = f"y=(h*{yf:.4f}-th/2)"
    parts = [
        f"drawtext=fontfile={fontref}:textfile=txt_{key}.txt",
        f"fontcolor={_hex_to_ff(spec.get('color'), default_color)}",
        f"fontsize={size}",
        f"x=(w*{xf:.4f}-tw/2)", y_expr,
    ]
    if spec.get("alpha") is not None:
        parts.append(f"alpha={max(0.0, min(1.0, float(spec.get('alpha')))):.2f}")
    parts += _outline_parts(spec)
    if spec.get("box"):
        bc = _hex_to_ff(spec.get("box_color"), "0x000000")
        op = max(0.0, min(1.0, (spec.get("box_opacity") or 80) / 100.0))
        pad = max(0, _ui_px(spec.get("box_pad"), 24, zero_ok=True))
        parts += ["box=1", f"boxcolor={bc}@{op:.2f}", f"boxborderw={pad}"]
    return ":".join(parts)


def _default_headcopy_enable(timeline):
    """명시 enable(hook_only 팩)이 없을 때의 기본(2026-07-25) — 헤드카피를 **마지막 비트 시작
    전까지**만 노출해 끝의 CTA 자막과 두 줄로 겹치지 않게 한다(job 57ec653ba579: 상단 헤드카피
    + 하단 CTA 충돌). 비트가 2개 미만이면 제한하지 않는다(None=기존 전체표시)."""
    if not timeline or len(timeline) < 2:
        return None
    last_t0 = float(timeline[-1]["t0"])
    return f"lte(t,{last_t0:.2f})"


def _headcopy_drawtext_parts(hc, work, enable=None):
    """헤드카피 drawtext 필터 리스트 — _segmented_drawtext 래퍼(기본색 오렌지).
    hc['highlight_rules']가 있으면 단어별 강조, 없으면 세그먼트 1개(기존과 동일).
    enable(ffmpeg between 식)이 주어지면 노출 구간을 제한한다(팩 headcopy.policy=hook_only).
    None이면 기존대로 영상 전체 고정 표시.
    """
    parts = _segmented_drawtext(
        hc.get("text", ""), hc, work, "hc", hc.get("x", 50), hc.get("y", 14),
        highlight_rules=hc.get("highlight_rules"), default_color="0xFF8800",
        fit_lines=True, block_box=True,
    )
    if not enable:
        return parts
    return [f"{p}:enable='{enable}'" for p in parts]


def _merge_highlight_rules(headcopy, caption_style, deco):
    """강조 단어 규칙(deco.highlight_rules)을 헤드카피·자막 스타일 dict 양쪽에 주입한다.
    규칙은 UI에서 deco에 저장되지만 렌더는 headcopy/caption_style에서 읽으므로 여기서 잇는다.
    각 dict가 이미 자체 highlight_rules를 가지면 그것을 우선(덮어쓰지 않음).
    원본 dict를 변형하지 않고 얕은 복사본을 반환한다."""
    hl = (deco or {}).get("highlight_rules")
    if not hl:
        return headcopy, caption_style
    if headcopy is not None and not headcopy.get("highlight_rules"):
        headcopy = {**headcopy, "highlight_rules": hl}
    if not (caption_style or {}).get("highlight_rules"):
        caption_style = {**(caption_style or {}), "highlight_rules": hl}
    return headcopy, caption_style


def _beat_timeline(edit_plan, tts_paths):
    """비트별 전체 타임라인 [{beat_idx, t0, dur, narration, role, cap_durs}, ...].

    자막(_burn_captions)과 모션(motion_packs)이 **같은 경계**를 쓰도록 하는 단일 출처.
    여기서 중복 계산하면 전환이 자막과 어긋난다. tts 없는 비트는 건너뛴다(기존 동작).

    cap_durs: _synthesize_beats가 저장한 ASR 기반 구절 표시시간(list[float]|None).
    여기서 새 dict를 만들며 원본 beat를 복사하지 않으므로, 이 필드를 안 실어보내면
    저장위치(_synthesize_beats)≠읽기위치(_burn_captions)가 되어 seam이 끊긴다.
    """
    timeline = []
    t0 = 0.0
    for beat in edit_plan["beats"]:
        idx = beat["beat_idx"]
        tts = tts_paths.get(idx)
        if not tts:
            continue
        dur = _beat_effective_dur(beat, tts)
        # 트림(head_trim)을 자막 타이밍에 반영 — 저장된 cap_durs/cap_lead는 트림 전 기준이라
        # 그대로 쓰면 트림한 비트만 어긋난다(2026-08-06).
        _cap_lead, _cap_durs = _adjust_caps_for_trim(beat)
        timeline.append({
            "beat_idx": idx,
            "t0": t0,
            "dur": dur,
            "narration": beat.get("narration", ""),
            "role": beat.get("role", ""),
            "cap_durs": _cap_durs,
            "cap_lead": _cap_lead,
            "cap_offset": beat.get("cap_offset", 0.0),
            "caption_lines": beat.get("caption_lines"),   # AI가 끊어준 자막 호흡 줄(있으면)
            # 장면별 자막 자리(2026-08-25). 여기서 안 실으면 저장위치≠읽기위치가 되어
            # 사장님이 고친 자리가 렌더에 반영되지 않는다(위 cap_durs와 같은 함정).
            "cap_pos": beat.get("cap_pos"),
            "cap_xy": beat.get("cap_xy"),                  # 드래그로 옮긴 장면별 자유 좌표(2026-08-31)
            "sfx": beat.get("sfx"),                        # 효과음 매칭(있으면) — position 읽기용
            "head_trim": beat.get("head_trim", 0.0),
        })
        t0 += dur
    return timeline


# 장면별 자막 자리(2026-08-25 사장님 "장면당 자막 배치를 수정할 수 있게").
# 값의 뜻은 여기 한 곳에서만 %로 번역한다 — UI와 렌더가 각자 숫자를 들고 있으면
# 언젠가 어긋난다(0순위-B). UI는 'top|mid|bottom'만 저장한다.
#   top    = 18%  (화면 위쪽. 헤드카피와 겹치지 않게 너무 위로는 안 올린다)
#   mid    = 50%  (한가운데)
#   bottom = 전체 설정 그대로(=안 건드린 것과 같다)
_CAP_POS_PCT = {"top": 18.0, "mid": 50.0}


def _beat_cap_style(caption_style, beat):
    """이 비트에 쓸 자막 스타일.

    두 가지 장면별 덮어쓰기를 같은 곳에서 푼다(0순위-B — 해석은 한 군데):
      1) beat['cap_xy'] = {"x_pct","y_pct"}  드래그로 옮긴 자유 좌표(2026-08-31).
         가로·세로 둘 다 덮는다. **cap_pos보다 우선**한다(나중에 손댄 뜻).
      2) beat['cap_pos'] = top|mid          버튼으로 고른 세로 자리(2026-08-25).
    둘 다 없으면 **원본 객체를 그대로** 돌려준다(복사 비용도, 동작 변화도 없음)."""
    xy = (beat or {}).get("cap_xy") or None
    if isinstance(xy, dict) and (xy.get("x_pct") is not None or xy.get("y_pct") is not None):
        st = dict(caption_style or {})
        if xy.get("x_pct") is not None:
            st["x_pct"] = float(xy["x_pct"])
        if xy.get("y_pct") is not None:
            st["y_pct"] = float(xy["y_pct"])
        return st
    pos = (beat or {}).get("cap_pos")
    ypct = _CAP_POS_PCT.get(pos)
    if ypct is None:
        return caption_style
    st = dict(caption_style or {})
    st["y_pct"] = ypct
    return st



def sfx_events_for(timeline, sfx_paths):
    """효과음 타점 계산 — [(경로, 절대초), ...]. **렌더와 캡컷 내보내기가 같이 쓴다**(0순위-B).

    비트별 position → 절대 오프셋(초)을 캡션과 **같은 함수**로 계산한다(별도 계산 금지 —
    저장위치=읽기위치). 절대시각 = 비트 t0 + 오프셋.
    타점 3종(2026-08-21 사장님 "훅에서 다음 넘어갈 때"):
      first      = 칸 시작
      last       = 칸의 마지막 자막(기본)
      transition = **칸이 끝나는 순간** = 다음 칸이 시작하는 지점. 이븐쇼핑류가
                   장면 전환에 띠용을 얹는 그 자리다. 다음 칸의 t0와 같은 값이라
                   따로 더할 게 없다(마지막 칸이면 영상 끝이라 amix가 잘라준다).
    """
    sfx_paths = sfx_paths or {}
    events = []
    for b in timeline or []:
        sfx = b.get("sfx")
        path = sfx_paths.get(b["beat_idx"])
        if not sfx or not path:
            continue
        segs = _caption_segments(b["narration"], preset=b.get("caption_lines"))
        seg_durs = _caption_durations(segs, b["dur"], real_durs=b.get("cap_durs"))
        pos = sfx.get("position")
        if pos == "first":
            offset = 0.0
        elif pos == "transition":
            offset = b["dur"]
        else:
            offset = sum(seg_durs[:-1])
        events.append((path, b["t0"] + offset))
    return events


def headcopy_span(timeline):
    """머리카피가 화면에 떠 있는 구간 (t0, dur). **렌더의 노출 규칙과 한 벌**이다(0순위-B).

    렌더는 drawtext에 `_default_headcopy_enable`이 만든 `lte(t,마지막비트t0)`를 걸어
    마지막 비트 전까지만 보여준다(끝의 CTA 자막과 두 줄 충돌 방지). 캡컷은 enable 식이
    없으므로 **세그먼트 길이**로 같은 구간을 만든다 — 그래서 그 함수의 결과를 그대로 읽는다.
    """
    if not timeline:
        return 0.0, 0.0
    total = float(timeline[-1]["t0"]) + float(timeline[-1].get("dur") or 0.0)
    enable = _default_headcopy_enable(timeline)
    if not enable:
        return 0.0, total
    m = re.search(r"lte\(t,([0-9.]+)\)", enable)
    return (0.0, float(m.group(1))) if m else (0.0, total)


def headcopy_layer_png(headcopy, out_path, work, caption_style=None, deco=None):
    """머리카피를 **투명 PNG 한 장**으로 굽는다(캡컷 내보내기용) → out_path 또는 None.

    ★캡컷 텍스트로 다시 만들지 않는 이유: 머리카피는 여러 줄·배경박스·단어별 강조색·
      자동 축소가 얽혀 있고, 무엇보다 **위치(x·y%)를 캡컷 clip.transform으로 옮기려면
      좌표계 실측이 필요한데 아직 근거가 없다**(capcut_draft 주석 참조). 풀캔버스 PNG로
      구우면 좌표 변환이 아예 필요 없다 — 꾸미기 틀(template)이 이미 쓰는 방법과 같다.
    ★그림은 렌더와 **같은 함수**(_headcopy_drawtext_parts)가 그린다 — 화면과 캡컷이
      갈리지 않는다(0순위-B). enable은 걸지 않는다(구간은 headcopy_span이 정한다).
    실패하면 None을 돌려준다 — 머리카피 한 장 때문에 내보내기가 막히면 안 된다.
    """
    if not headcopy or not (headcopy.get("text") or "").strip():
        return None
    hc, _cs = _merge_highlight_rules(headcopy, caption_style, deco)
    try:
        # ★기본 폰트를 work에 깔아둔다 — drawtext는 `fontfile=font.ttf`(상대명)를 참조하고,
        #   그 파일을 두는 곳이 _burn_captions뿐이었다. 안 깔면 ffmpeg가 죽는다(실측:
        #   exit 3221225477 + "Fontconfig error"). 폰트 이름 해석은 _font_ref 한 곳이 한다.
        _font = _resolve_font()
        if not _font:
            print("[캡컷] 폰트 미해결 — 머리카피 건너뜀", file=sys.stderr)
            return None
        shutil.copy(_font, Path(work) / "font.ttf")
        parts = _headcopy_drawtext_parts(hc, Path(work))
        if not parts:
            return None
        _run_ffmpeg([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=black@0.0:s={_OUT_W}x{_OUT_H}:d=1,format=rgba",
            "-vf", ",".join(parts), "-frames:v", "1", str(out_path),
        ], cwd=str(work))
    except Exception as e:      # noqa: BLE001 — 머리카피 실패가 내보내기를 죽이면 안 된다
        print(f"[캡컷] 머리카피 PNG 실패(건너뜀): {e!r}", file=sys.stderr)
        return None
    return str(out_path) if Path(out_path).exists() else None


def _pre_compose_under_text(in_video, deco, work):
    """틀 그림을 자막·글자 **밑에** 깔아 영상에 미리 굽는다 → (새 영상, 틀을 뺀 deco).

    ★언제 도나: deco.template.under_text가 참일 때만(이미지 틀). 기존 틀은 안 탄다 —
      옛 작업의 그림이 한 픽셀도 안 바뀐다.
    ★왜 별도 패스인가: 자막은 -vf drawtext 체인이라 두 번째 입력(PNG)을 못 섞는다.
      순서를 바꾸려면 합성을 먼저 끝내고 그 결과를 자막 패스에 넘기는 수밖에 없다.
    실패하면 원본을 그대로 돌려준다 — 틀 하나 때문에 렌더가 죽으면 안 된다(fail-open).
    """
    tpl = (deco or {}).get("template") or {}
    png = tpl.get("_abspath")
    if not (tpl.get("under_text") and png and os.path.exists(png)):
        return in_video, deco
    out = Path(work) / "under_tpl.mp4"
    try:
        _run_ffmpeg([
            "ffmpeg", "-y", "-i", str(in_video), "-i", str(png),
            "-filter_complex", f"[1:v]scale={_OUT_W}:{_OUT_H}[tpl];[0:v][tpl]overlay=0:0[v]",
            "-map", "[v]", "-map", "0:a?", "-c:a", "copy",
            "-c:v", "libx264", "-preset", _mid_preset(), "-crf", _mid_crf(),
            *_threads_args(), "-pix_fmt", "yuv420p", str(out),
        ], cwd=str(work))
    except Exception as e:      # noqa: BLE001
        print(f"[틀] 밑에 깔기 실패 — 예전처럼 위에 얹는다: {e!r}", file=sys.stderr)
        return in_video, deco
    if not out.exists():
        return in_video, deco
    # ★틀 슬롯을 비운다 — 안 비우면 뒤에서 **또** 얹어 결국 글자를 덮는다(두 번 그리기 금지).
    deco = dict(deco or {})
    deco["template"] = {k: v for k, v in tpl.items() if k not in ("_abspath",)}
    return str(out), deco


def _burn_captions(in_video, edit_plan, tts_paths, out_path, work, headcopy=None, caption_style=None, deco=None, sfx_paths=None):
    """완성된 믹스 영상(in_video) 위에 우리 자막을 비트 타이밍대로 굽는다.
    비트 경계는 각 비트 tts 길이 누적(t0)으로 계산해, drawtext enable 구간을 전체
    타임라인 기준으로 배치한다(_caption_drawtexts에 t0 오프셋 전달). drawtext 값 안의
    between(t,a,b) 콤마를 나중에 split할 필요가 없다(필터 요소 단위로 리스트 반환).
    폰트가 없으면 자막 없이 원본을 그대로 복사한다."""
    font = _resolve_font()
    if font:
        try:
            shutil.copy(font, work / "font.ttf")
        except OSError:
            font = None
    if not font:
        print("[motion] 폰트 미해결 — 자막·모션·색감·오버레이·BGM 전부 스킵하고 원본 복사",
              file=sys.stderr)
        shutil.copy(in_video, out_path)
        return str(out_path)
    headcopy, caption_style = _merge_highlight_rules(headcopy, caption_style, deco)
    filters = [f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"]
    # 색감 필터는 drawtext보다 **앞**에 온다 — 뒤에 두면 자막·헤드카피까지 색보정에 물든다.
    _color_filter = ((deco or {}).get("motion") or {}).get("color_filter") or ""
    if _color_filter.strip():
        filters.append(_color_filter.strip())
    timeline = _beat_timeline(edit_plan, tts_paths)
    for b in timeline:
        # 마지막 비트만 0.5초 여운(영상 끝에서 자막이 툭 사라지지 않게). 중간 비트는 tail=0 —
        # 여운을 주면 그 자막이 다음 비트로 0.5초 넘어가 다음 자막과 겹쳐 뭉갠다(전환 겹침, 실측).
        _tail = 0.5 if b is timeline[-1] else 0.0
        filters.extend(_caption_drawtexts(b["narration"], b["dur"], work, b["beat_idx"],
                                          b["t0"], _beat_cap_style(caption_style, b),
                                          real_durs=b.get("cap_durs"),
                                          cap_offset=b.get("cap_offset", 0.0), tail=_tail,
                                          cap_lines=b.get("caption_lines"),
                                          lead_in=b.get("cap_lead", 0.0)))
    if headcopy and (headcopy.get("text") or "").strip():
        # enable 없으면 전체 표시(기존). 팩이 hook_only면 렌더 파생값 _headcopy_enable이 온다.
        hc_enable = ((deco or {}).get("motion") or {}).get("_headcopy_enable")
        if not hc_enable:
            # 명시 enable 없으면 끝 비트(CTA)와 겹치지 않게 마지막 비트 전까지만(2026-07-25).
            hc_enable = _default_headcopy_enable(timeline)
        filters.extend(_headcopy_drawtext_parts(headcopy, work, enable=hc_enable))
    # 꾸미기 장식(deco): 추가 텍스트(여러 개) + 워터마크 닉네임. 모두 고정 drawtext.
    deco = deco or {}
    for i, t in enumerate(deco.get("extra_texts") or []):
        ex_dt = _fixed_drawtext(t, work, f"ex{i}")
        if ex_dt:
            filters.append(ex_dt)
    wm = deco.get("watermark") or {}
    if wm.get("text"):
        wm_spec = {"text": wm.get("text"), "font": wm.get("font"),
                   "color": wm.get("color", "#FFFFFF"),
                   "size": wm.get("size", 30),
                   "x": wm.get("x", 50), "y": wm.get("y", 88),
                   "alpha": wm.get("alpha", 0.6),
                   "float": wm.get("float", True),
                   "outline": wm.get("outline", True),
                   "outline_color": wm.get("outline_color", "#000000"),
                   "outline_w": wm.get("outline_w", 3)}
        wm_dt = _fixed_drawtext(wm_spec, work, "wm", default_color="0xFFFFFF")
        if wm_dt:
            filters.append(wm_dt)
    vf = ",".join(filters)
    # cwd=work: 필터그래프의 font.ttf / cap_*.txt 상대경로 해석 기준(콜론 회피).
    # 오버레이 이미지·BGM 유무로 -vf(단순) 또는 filter_complex(합성) 선택. 둘 다 조합 가능.
    bgm = deco.get("bgm") or {}
    bgm_path = bgm.get("_abspath")
    has_bgm = bool(bgm_path and os.path.exists(bgm_path))
    overlay = deco.get("overlay") or {}
    ov_path = overlay.get("_abspath")
    has_overlay = bool(ov_path and os.path.exists(ov_path))
    # 모션(전환·스티커 등 타임드 투명 레이어)과 색감 필터
    motion = deco.get("motion") or {}
    motion_layers = [L for L in (motion.get("layers") or []) if L.get("_abspath")]
    # 🖼 꾸미기 템플릿 — 모션 레이어와 **같은 배관**에 얹는다(0순위-B: 합성 로직을
    # 두 벌로 만들지 않는다). dur이 있으면 그 구간만(첫 장면), 없으면 영상 전체.
    # ★deco.overlay(사장님이 올린 로고)와 **별도 슬롯**이다 — 둘 다 얹힌다.
    tpl = deco.get("template") or {}
    if tpl.get("_abspath"):
        tl = {"_abspath": tpl["_abspath"], "x": 50, "y": 50,
              "alpha": tpl.get("alpha", 1), "start": 0}
        if tpl.get("dur"):
            tl["dur"] = float(tpl["dur"])
        motion_layers = list(motion_layers) + [tl]
    has_motion = bool(motion_layers)
    # 효과음(sfx): 비트별 position → 절대 오프셋(초)을 캡션과 **같은 함수**로 계산한다
    # (별도 계산 금지 — 저장위치=읽기위치). first=0.0 / last=마지막 세그먼트 직전까지의 합
    # (세그먼트 1개면 0.0). 절대시각 = 비트 t0 + 오프셋. sfx_events=[(경로, 절대초), ...].
    sfx_events = sfx_events_for(timeline, sfx_paths)
    has_sfx = bool(sfx_events)
    if not has_bgm and not has_overlay and not has_motion and not has_sfx:
        base_vf = vf
        _run_ffmpeg(["ffmpeg", "-y", "-i", str(in_video), "-vf", base_vf, "-r", "30",
                     "-c:v", "libx264", "-preset", _preset(), "-crf", _crf(), *_threads_args(), "-c:a", "copy", "-pix_fmt", "yuv420p", str(out_path)],
                    cwd=str(work))
        return str(out_path)
    inputs = ["-i", str(in_video)]
    fc = [f"[0:v]{vf}[v0]"]
    vcur, idx = "v0", 1
    # 🩹 가림막의 **흐림** — 그림으로는 못 하는 일이라 여기서 영상에 직접 먹인다.
    #   ★자리는 deco_frame이 그린 마스크가 정한다(미리보기와 같은 모양 함수) — 여기서
    #     좌표를 다시 계산하면 화면과 어긋난다(0순위-B).
    #   ★틀 그림(가림막 색 막)보다 **먼저** 걸어야 한다. 색 막은 틀 안에 있고
    #     흐림은 그 아래 영상에 먹는 것이라 순서가 뒤집히면 흐림이 색 막을 흐린다.
    _bmask = tpl.get("blur_mask")
    _bsig = float(tpl.get("blur_sigma") or 0)
    if _bmask and _bsig > 0 and os.path.exists(_bmask):
        inputs += ["-i", _bmask]
        fc.append(f"[{vcur}]split[bb0][bb1]")
        fc.append(f"[bb1]gblur=sigma={_bsig}[bbl]")
        fc.append(f"[{idx}:v]scale={_OUT_W}:{_OUT_H},format=rgba,alphaextract[bmk]")
        fc.append("[bbl][bmk]alphamerge[bblm]")
        fc.append("[bb0][bblm]overlay=0:0[vblur]")
        vcur, idx = "vblur", idx + 1
    if has_overlay:                                   # 이미지 오버레이(로고·뱃지 등)
        inputs += ["-i", ov_path]
        w = overlay.get("width")                      # 1080px 기준 폭(없으면 원본)
        scale = f"scale={int(w)}:-1," if w else ""
        xf = min(1.0, max(0.0, overlay.get("x", 50) / 100.0))
        yf = min(1.0, max(0.0, overlay.get("y", 50) / 100.0))
        aa = max(0.0, min(1.0, overlay.get("alpha", 1)))
        fc.append(f"[{idx}:v]{scale}format=rgba,colorchannelmixer=aa={aa:.2f}[ov]")
        fc.append(f"[{vcur}][ov]overlay=x=W*{xf:.4f}-w/2:y=H*{yf:.4f}-h/2[v1]")
        vcur = "v1"
        idx += 1
    if has_motion:                                    # 전환·스티커 등 타임드 투명 레이어
        m_inputs, m_fc, vcur, idx = _motion_layer_filters(motion_layers, idx, vcur)
        inputs += m_inputs
        fc += m_fc
    # 오디오 믹스: 나레이션(항상) + BGM(있으면) + 효과음(있으면)을 한 번에 amix.
    # duration=first → 첫 입력(나레이션) 길이로 잘린다. 효과음이 비트보다 길면 다음
    # 비트 위로 흘러넘치되 영상 끝에서만 잘린다(v1 알려진 한계, 스펙 §4.3).
    amap = None
    mix_labels = ["0:a"]                              # 나레이션(항상 있음, 첫 입력)
    if has_bgm:                                       # 배경음악(나레이션 위 낮은 볼륨)
        inputs += ["-i", bgm_path]
        vol = max(0.0, min(1.0, (bgm.get("volume", 15)) / 100.0))
        fc.append(f"[{idx}:a]aloop=loop=-1:size=2000000000,volume={vol:.3f}[bg]")
        mix_labels.append("bg")
        idx += 1
    if has_sfx:                                       # 효과음(비트별 오프셋에 adelay)
        sfx_vol = max(0.0, min(1.0, (deco.get("sfx_volume", 60)) / 100.0))
        for i, (sfx_path, offset_sec) in enumerate(sfx_events):
            inputs += ["-i", sfx_path]
            ms = max(0, round(offset_sec * 1000))
            fc.append(f"[{idx}:a]adelay={ms}:all=1,volume={sfx_vol:.3f}[sfx{i}]")
            mix_labels.append(f"sfx{i}")
            idx += 1
    if len(mix_labels) > 1:
        ins = "".join(f"[{lb}]" for lb in mix_labels)
        fc.append(f"{ins}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2[a]")
        amap = "[a]"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{vcur}]"]
    cmd += (["-map", amap, "-c:a", "aac"] if amap else ["-map", "0:a", "-c:a", "copy"])
    cmd += ["-r", "30", "-c:v", "libx264", "-preset", _preset(), "-crf", _crf(), *_threads_args(), "-pix_fmt", "yuv420p", str(out_path)]
    _run_ffmpeg(cmd, cwd=str(work))
    return str(out_path)


def assemble(edit_plan, tts_paths, source_video_paths, out_path, clean_fn=None, headcopy=None, caption_style=None, deco=None, cutaway_paths=None, sfx_paths=None, burn_captions=True):
    """EDL → 최종 mp4. 1)믹스(자막X) 2)clean_fn(있으면 자막제거) 3)우리 자막.
    clean_fn(mix_raw_path)->clean_path 를 주면 그 사이에 VMake 자막제거가 끼워진다
    (없으면 생략). 자막제거는 우리 자막을 굽기 전 깨끗한 믹스에 돌려야 우리 자막이
    함께 지워지지 않는다.
    sfx_paths: {beat_idx: media_path} — beat["sfx"]가 붙은 비트의 효과음 경로(컷어웨이와
    같은 seam). _burn_captions가 position→오프셋을 캡션과 같은 함수로 계산해 amix에 섞는다.
    ★인코딩 프리셋은 모듈 _X264_PRESET(기본 medium). 미리보기는 호출부(run_preview)가
    preview_preset() 컨텍스트로 veryfast로 감싼다 — 최종은 그대로 medium 고화질."""
    work = Path(out_path).parent / f"asm_{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    # ★작업이 끝나면 이 폴더를 지운다(2026-08-23). 종전엔 지우는 코드가 아예 없어서
    #   렌더 1회마다 **195MB씩 영구히 쌓였다**(실측 2026-08-23: asm_ 321개 = 21GB,
    #   mix_jobs 31GB 중 3분의 2). 1기 100명이 쓰면 하루에도 수십 GB가 이 자리에 쌓인다.
    #   ⚠️finally로 감싸는 이유: 반환 지점이 둘(자막 굽기 생략/일반)이고 예외로도 빠져나간다 —
    #     한 군데만 지우면 나머지 경로가 계속 남긴다(0순위-B).
    #   ⚠️out_path는 work **밖**이라 안전하다(work는 out_path의 형제 폴더).
    #     실패해도 삼킨다 — 청소가 렌더를 죽이면 안 된다.
    try:
        mix_raw = _render_mix(edit_plan, tts_paths, source_video_paths, work, cutaway_paths=cutaway_paths)
        base_video = clean_fn(mix_raw) if clean_fn else mix_raw
        if not burn_captions:
            # '자막 없는 clean 배경'용(썸네일 배경 등, 2026-07-22) — 우리 나레이션 자막·꾸미기를
            # 굽는 _burn_captions 패스를 통째로 건너뛴다. base_video(믹스[+원본자막제거])를 그대로
            # 확정하므로 ①썸네일에 나레이션 자막이 안 박히고 ②캡션 인코딩 패스가 없어 더 빠르다.
            import shutil
            shutil.copyfile(base_video, out_path)
            return out_path
        # 🖼 이미지 틀은 **자막·글자보다 아래**여야 한다(2026-08-31 사장님: "그림위로
        #   올라가는게 해드카피만있고 자막 제목등 다 안된다").
        #   지금까지 틀은 맨 마지막에 얹혔다 — 기존 20종은 띠 말고 전부 투명이라 덮을 게
        #   없어 문제가 안 보였을 뿐이다. 화면을 꽉 채우는 이미지 틀에선 글자가 통째로 묻힌다.
        #   → 그림을 **자막 굽기 전에** 먼저 영상에 합성하고, 틀 슬롯은 비운다(두 번 얹으면
        #     또 덮는다). 순서를 정하는 곳은 여기 한 곳이다(0순위-B).
        base_video, deco = _pre_compose_under_text(base_video, deco, work)
        return _burn_captions(base_video, edit_plan, tts_paths, out_path, work, headcopy, caption_style, deco, sfx_paths=sfx_paths)
    finally:
        try:
            import shutil as _sh
            _sh.rmtree(work, ignore_errors=True)
        except Exception as e:      # noqa: BLE001 — 청소 실패가 제작을 막지 않는다
            # 삼키되 조용히 넘기지 않는다 — 이게 계속 실패하면 디스크가 다시 찬다.
            print(f"[assemble] 작업폴더 정리 실패(무해, 디스크만 남음): {e!r}", file=sys.stderr)


def _probe_audio_params(path):
    """final.mp4의 오디오 규격(샘플레이트·채널). 붙일 인트로를 여기 맞춰야 -c copy가 성립한다.

    ★규격이 다르면 concat -c copy는 에러 없이 통과하고도 뒷부분 소리가 깨진다 —
    그래서 기본값으로 찍지 않고 실제 파일에서 읽는다."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0",
           "-show_entries", "stream=sample_rate,channels",
           "-of", "csv=p=0", str(path)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stdout.strip()
        sr, ch = out.split(",")[:2]
        return int(sr), int(ch)
    except Exception:
        return 44100, 2


def prepend_still(video_path, image_path, seconds=1.2):
    """영상 맨 앞에 정지 이미지(썸네일) 구간을 붙인다. 성공하면 video_path를 덮어쓴다.

    왜 이렇게: 비트 클립을 잇는 기존 방식과 **같은 규격**(1080x1920 libx264/aac 30fps)으로
    인트로를 만들어 concat -c copy로 붙인다. 전체 재인코딩은 2GB 서버에서 수십 초가 걸려
    배포 재시작에 걸려 죽던 원인이다(2026-07-12 주석과 같은 이유).
    """
    video_path, image_path = Path(video_path), Path(image_path)
    if not video_path.exists() or not image_path.exists():
        return False
    sr, ch = _probe_audio_params(video_path)
    work = video_path.parent
    intro = work / "thumb_intro.mp4"
    _run_ffmpeg([
        "ffmpeg", "-y",
        "-loop", "1", "-t", f"{seconds:.3f}", "-i", str(image_path),
        "-f", "lavfi", "-t", f"{seconds:.3f}",
        "-i", f"anullsrc=channel_layout={'stereo' if ch >= 2 else 'mono'}:sample_rate={sr}",
        "-vf", (f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,"
                f"crop={_OUT_W}:{_OUT_H}"),
        "-r", "30", "-c:v", "libx264", "-preset", _preset(), "-crf", _crf(), *_threads_args(),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", str(sr), "-ac", str(ch),
        "-shortest", str(intro)])
    lst = work / "concat_intro.txt"
    lst.write_text(f"file '{intro.as_posix()}'\nfile '{video_path.as_posix()}'\n", encoding="utf-8")
    merged = work / "final_with_intro.mp4"
    _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                 "-c", "copy", str(merged)])
    merged.replace(video_path)      # 같은 폴더 = 원자적 교체
    return True
