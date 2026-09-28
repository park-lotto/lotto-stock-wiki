# -*- coding: utf-8 -*-
"""편집 화면 미리보기 영상 vs '완성본 만들기' 영상 — 칸마다 장면·시각을 **영상 프레임으로** 비교한다(2026-09-27).

왜: 계산끼리 비교하면 같은 함수라 늘 같다(2026-09-26에 그걸로 '됐다'고 세 번 틀렸다). 고객이 보는 건 영상이다.
  ① 편집 화면 미리보기 = app._pvproxy_build(편집 화면 컷, 원본 소스) — 화면이 서버에 요청해 굽는 그 함수
  ② 완성본 만들기    = render_inputs_for(allow_clean=False) + assemble(preview_preset) — run_preview와 같은 조립
  두 영상을 한 번씩 저해상도(90x160, 30fps)로 통째 풀어 두고, 칸의 컷마다 한가운데를 ①에서 찍어
  ②의 같은 칸 같은 비율 지점 ±0.6초 안에서 가장 닮은 프레임을 찾는다.

판정(2026-09-27 개정 — 옛 판정 '전체 화면 0~255 평균 차 > 18'은 5개 작업에서 43칸 중 5칸 오탐):
  ②는 청소본(원본 자막 지운 영상)을 쓰는 작업이 있어 **원본에 박힌 자막 띠가 ①에만 있다** → 전체 화면 비교가 걸렸다.
  그래서 거리 = 가운데 띠(위 10%·아래 30% 제외)만 회색조로 → 5x5 칸 평균(흐림+축소) → 밝기·대비 정규화(z) →
  칸별 |차| 평균. 같은 장면이면 작고, 서로 무관한 장면이면 이론값 ~1.13(두 표준정규의 평균 절대차).
  SCENE_T 이상이면 '다른 장면'. 밀림 = 가장 닮은 시각 - 기대 시각(최소 거리 + SHIFT_TOL 안의 후보 중 0에 가장 가까운 것 —
  정지 화면에서 아무 데나 골라 가짜 밀림이 나는 걸 막는다).

★도구는 고객 파일을 바꾸지 않는다:
  - ①을 고객 pvproxy 폴더가 아니라 /tmp/evf/<job>/pv 에 굽는다(_pvproxy_build는 폴더의 **다른 mp4·json을 지운다** —
    고객 폴더에서 돌리면 고객의 편집 화면 합본이 지워졌다).
  - clean_base._write(청소본 기록 저장)를 막는다 — render_inputs_for 안의 calibrate가 고객 clean_base.json을 고쳐 쓴다.
  - job 하나 비교·사진이 끝나면 /tmp/evf/<job>/ 통째로 지운다(영상 수백 MB). 남는 건 report.txt·eye_<job>.jpg·samples.jsonl.

서버: cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \
      [PATCH_DIR=/tmp/cbpatch2] python3 tools/editor_vs_final_video.py [N최근작업=30] [job_id ...]
결과: /tmp/evf/report.txt (작업별·칸별) · eye_<job>.jpg(컷마다 위=화면·아래=완성본, 빨강=다른 장면·노랑=밀림)
"""
import json, subprocess, sys, sqlite3, hashlib, shutil, time
from pathlib import Path
sys.path.insert(0, ".")
import numpy as np
from PIL import Image, ImageDraw

import os, importlib.util
# 조각 경계 붙이기(seg_snap)의 장면 전환 캐시는 원래 소재 옆(고객 작업 폴더)에 쓴다 — 도구는 고객 폴더를 안 바꾸므로 /tmp 로 돌린다
os.environ.setdefault("SEG_SNAP_CACHE_DIR", "/tmp/evf_snapcache")
if os.getenv("PATCH_DIR"):          # 배포 전 대조: 고친 모듈을 먼저 얹는다
    import shopping_shorts
    # 폰트 후보 목록(video_assemble._FONT_CANDIDATES)은 **import 때** 파일 옆 assets 로 정해진다 — PATCH_DIR 에서 얹으면
    #   못 찾아 자막 없이 구워진다(2026-09-27 실측 '폰트 미해결'). 저장소 폰트를 첫 후보(환경 변수)로 준다.
    _bf = Path("shopping_shorts/assets/NanumGothic.ttf").resolve()
    if _bf.exists():
        os.environ.setdefault("SHORTS_CAPTION_FONT", str(_bf))
    for _n in ("frame_match", "seg_snap", "screen_clips", "video_assemble", "clean_base", "mix_pipeline"):
        _f = Path(os.getenv("PATCH_DIR")) / ("%s.py" % _n)
        if _f.exists():
            _sp = importlib.util.spec_from_file_location("shopping_shorts." + _n, str(_f))
            _m = importlib.util.module_from_spec(_sp); sys.modules["shopping_shorts." + _n] = _m
            _sp.loader.exec_module(_m); setattr(shopping_shorts, _n, _m)
            # ★파일 위치 기준 경로는 저장소로 되돌린다(2026-09-27 실측) — PATCH_DIR 에서 얹으면 video_assemble 의 폰트 폴더
            #   (_FONT_DIR = 파일 옆 static/fonts)를 못 찾아 완성본이 '폰트 미해결 — 자막·BGM 전부 스킵'으로 구워졌고,
            #   clean_base._ROOT(파일의 두 단계 위)가 /tmp 를 가리켰다. 비교 결과가 수리 전(자막 있음)과 조건이 달라졌다.
            _repo_pkg = Path("shopping_shorts").resolve()
            for _attr, _val in (("_FONT_DIR", _repo_pkg / "static" / "fonts"),
                                ("_BUNDLED_FONT", str(_repo_pkg / "assets" / "NanumGothic.ttf")),
                                ("_ROOT", _repo_pkg.parent)):
                if hasattr(_m, _attr):
                    setattr(_m, _attr, _val)
    _fa = Path(os.getenv("PATCH_DIR")) / "app.py"
    if _fa.exists():                 # app 은 통째로 못 얹는다(정적 파일 경로) — 미리보기 굽기 함수만 바꿔 끼운다
        from shopping_shorts import app as _app
        _src = _fa.read_text(encoding="utf-8")
        _i = _src.index("def _pvproxy_build("); _j = _src.index(chr(10) + "@app.", _i)
        exec(compile(_src[_i:_j], str(_fa), "exec"), _app.__dict__)
        # 조각 경계 붙이기(2026-09-27) — 화면에 조각을 내려주는 입구와 그 보조 함수도 바꿔 끼운다(데코레이터 뒤 몸통만)
        #   입구가 부르는 _lab_captions 도 같이(인자 모양이 바뀌면 옛 것과 섞여 TypeError — 서버 실측 2026-09-27)
        for _a, _b in (("CUT_FIT_MODES = (", chr(10) + "@app."),       # 컷 맞춤 방식(2026-09-28) — 입구가 부른다(없는 서버 app 에 얹기)
                       ("def _lab_scenecuts(", chr(10) + "def _with_film_segs("),
                       ("def _lab_captions(", chr(10) + "@app."),
                       ("def api_mix_scene_lab_data(", chr(10) + "@app.")):
            if _a in _src:
                _i = _src.index(_a); _j = _src.index(_b, _i)
                exec(compile(_src[_i:_j], str(_fa), "exec"), _app.__dict__)
OUT = Path("/tmp/evf"); OUT.mkdir(exist_ok=True)

# 프레임 특징·거리·후보 고르기 = 청소본 밀림 보정(clean_base.calibrate)과 **같은 함수**(0순위-B)
from shopping_shorts import frame_match as fm
from shopping_shorts.frame_match import FPS, W, H, Y0, Y1, SCENE_T, frames as _frames, feats as _feats
#   SCENE_T 측정(2026-09-27, 30작업 706컷): 같은 장면 최대 0.416(보통 컷)·0.452(정지 컷 — 켄번즈) / 사보타주 최소 0.63
SHIFT_WIN = 18                             # 찾는 범위 ±18프레임 = ±0.6초
SHIFT_T = 0.15                             # 밀림 보고 기준(초)
CUT_T = 0.40                               # ①에서 이 이상 튀는 프레임 사이 = 눈에 보이는 컷 경계(경계 대조 대상)


def _dur(p):
    try:
        return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                              "-of", "csv=p=0", str(p)]).strip())
    except Exception:
        return 0.0


def _gray_full(fr):
    return fr.astype(np.float32).mean(axis=-1)


def _match(fe, ff, ge, gf, ie, jf, span=None, fe2=None, ff2=None):
    """①의 프레임 ie 와 ②의 기대 프레임 jf 주변을 비교 → (거리, 밀림초, 고른 ②프레임, 옛 거리).
    span=(첫, 끝) ②프레임 — 정지 컷이면 찾는 범위를 **그 컷 구간 안**으로 좁힌다(2026-09-27).
      정지 컷은 앞 컷과 같은 원본을 읽으면 앞 컷 끝 프레임과 그림이 같다. 완성본 정지 몫엔 켄번즈가 얹혀
      제 구간보다 앞 컷 끝이 더 닮아 보여 −0.533초 같은 가짜 밀림이 났다(컷 경계가 밀린 게 아니다 — 경계는 따로 잰다)."""
    lo, hi = max(0, jf - SHIFT_WIN), min(len(ff) - 1, jf + SHIFT_WIN)
    if span is not None and span[0] <= jf <= span[1]:
        lo, hi = max(lo, int(span[0])), min(hi, int(span[1]))
    if hi < lo or ie >= len(fe):
        return 9.9, 0.0, max(0, min(jf, len(ff) - 1)), 255.0, [], 0
    js = np.arange(lo, hi + 1)
    # 거리 = 두 띠(가운데·아래) 중 가까운 쪽(frame_match.dist_any) — 청소본이 원본 위 글자 띠를 지워 채운 칸의 가짜 '다른 장면' 방지
    d = fm.dist_any(ff, ff2, js, fe[ie], fe2[ie]) if (fe2 is not None and ff2 is not None) else fm.dist(ff, js, fe[ie])
    jb, dmin, _ok = fm.pick(js, d, jf)
    # 옛 판정(전체 화면 회색 평균 차, ±4프레임 최소) — 비교용 기록만
    ol = np.arange(max(0, jf - 4), min(len(gf) - 1, jf + 4) + 1)
    old = float(np.abs(gf[ol] - ge[ie]).mean(axis=(1, 2)).min()) if len(ol) else 255.0
    return dmin, (jb - jf) / FPS, jb, old, [round(float(x), 3) for x in d], lo - jf


def _motion(fe):
    """프레임 i 가 i-1 과 얼마나 다른가 — 컷 경계에서 튄다."""
    m = np.zeros(len(fe), np.float32)
    if len(fe) > 1:
        m[1:] = np.abs(fe[1:] - fe[:-1]).mean(axis=(1, 2))
    return m


def _boundary(fe, ff, me, mf, ie_b, jf_b):
    """①의 컷 경계(ie_b 근처)가 ②의 어디에 있나 → (밀림초|None, ①의 튐). 튐이 작으면(같은 장면 이어짐) None, 0.
    ②에서 튐이 있는 후보 중 **경계 뒤 첫 프레임이 가장 닮은** 자리를 고른다(옆 컷 경계를 잘못 잡지 않게).
    ★앞 프레임까지 닮으라고 하면 앞 컷이 정지 컷(완성본만 켄번즈 확대)일 때 경계를 못 찾는다(62ed 9번 칸 실측)."""
    lo_e, hi_e = max(1, ie_b - 2), min(len(me) - 1, ie_b + 2)
    if hi_e < lo_e:
        return None, 0.0
    ieb = lo_e + int(np.argmax(me[lo_e:hi_e + 1]))
    if me[ieb] < CUT_T:
        return None, float(me[ieb])
    exp = jf_b + (ieb - ie_b)
    js = [j for j in range(max(1, exp - SHIFT_WIN), min(len(mf) - 1, exp + SHIFT_WIN) + 1) if mf[j] >= 0.5 * me[ieb]]
    if not js:
        return 9.9, float(me[ieb])            # ②에 그 자리 컷이 없다
    sc_ = [(round(float(np.abs(ff[j] - fe[ieb]).mean()), 2), abs(j - exp), j) for j in js]
    best = min(sc_)
    if best[0] >= SCENE_T:
        return 9.9, float(me[ieb])            # 튀는 자리는 있으나 앞뒤 장면이 다르다
    return (best[2] - exp) / FPS, float(me[ieb])


GHOST_MAX = 3                              # 컷 가장자리에서 찾는 잔상 길이(프레임) — 실측 1~3프레임(2026-09-27 다섯 job)
GHOST_JUMP = 3.0                           # 이음매 튐이 몸통 안 튐(중앙값)의 이 배수 이상이어야 잔상(움직임 오탐 거르기)
SHORT_CUT = 3                             # 이 프레임 수 이하 컷 = '짧은 컷'(가운데·잔상 검사를 못 한다 — 따로 센다)


def _edge_ghosts(fe, a, b, T=None):
    """①의 컷 [a, b](프레임, 양끝 포함) 머리·꼬리에 낀 **딴 장면 1~3프레임**(잔상) → (머리 N, 꼬리 N).

    왜 (2026-09-27): 가운데 검사는 0.2초 미만 구간을 건너뛰고, 경계 검사는 '②에 그 경계 없음(9.9)'으로만 남겨
      편집 화면 미리보기 컷 끝의 딴 장면 1~3프레임(원본의 다음 장면·입력 -t 1프레임 더 읽기)을 못 셌다.
    잔상 = 컷 안쪽 기준 프레임(꼬리면 b-GHOST_MAX, 머리면 a+GHOST_MAX)과도 다르고 **옆 컷**(b+1 / a-1)과도 다른 가장자리 연속 구간.
      옆 컷과 닮으면 경계가 1~2프레임 밀린 것(경계 밀림이 따로 잰다)이지 잔상이 아니다. 컷이 짧으면(≤ 2*GHOST_MAX+1) 안 본다."""
    T = SCENE_T if T is None else T
    n = b - a + 1
    if n <= 2 * GHOST_MAX + 1 or a < 0 or b >= len(fe):
        return 0, 0

    def _d(i, j):
        return float(np.abs(fe[i] - fe[j]).mean())

    def _run(edge, step, other):
        ref = edge - step * GHOST_MAX           # 안쪽 기준(같은 컷 몸통)
        for r in range(GHOST_MAX, 0, -1):
            ks = [edge - step * q for q in range(r)]
            if all(_d(k, ref) >= T for k in ks) and (other is None or all(_d(k, other) >= T for k in ks)) \
                    and _d(edge - step * r, ref) < T:
                spike, med = _ghost_jump(fe, a, b, "tail" if step > 0 else "head", r)
                # ★몸통↔잔상 이음매가 **뚝 끊겨야** 잔상이다 — 빠른 움직임(휙 돌리기·흔들림)은 몸통 안에서도 프레임마다 크게
                #   변해 기준 프레임과 멀어진다(서버 실측 2026-09-27: 이 판정 없이 돌리면 움직임 오탐이 눈으로 확인한 9곳 중 8곳).
                return r if (spike >= CUT_T and spike >= GHOST_JUMP * med) else 0
        return 0

    tail = _run(b, 1, b + 1 if b + 1 < len(fe) else None)
    head = _run(a, -1, a - 1 if a - 1 >= 0 else None)
    return head, tail


def _ghost_jump(fe, a, b, side, r, span=6):
    """잔상 후보(가장자리 r프레임)의 이음매 튐 → (이음매 튐, 몸통 안 프레임 간 튐 중앙값). 튐 = 이웃 프레임 특징 평균 |차|."""
    def _m(i):
        return float(np.abs(fe[i] - fe[i - 1]).mean()) if 1 <= i < len(fe) else 0.0
    if side == "tail":
        j = b - r + 1                            # 첫 잔상 프레임(몸통 → 잔상으로 넘어가는 자리)
        body = [_m(i) for i in range(max(a + 1, j - span), j)]
    else:
        j = a + r                                # 첫 몸통 프레임(잔상 → 몸통으로 넘어가는 자리)
        body = [_m(i) for i in range(j + 1, min(b, j + span) + 1)]
    return _m(j), (float(np.median(body)) if body else 0.0)


def _ghost_backed_by_cut(cut, side, n, cuts):
    """잔상 후보(화면 컷 cut={v,s,d,sd}의 머리|꼬리 n프레임)가 **원본의 실제 장면 전환**에서 온 것인가(2026-09-28).
    읽는 창 가장자리 (n+1)프레임(배속 반영) + 반 프레임 안에 전환(seg_snap.scene_cuts — 잔상 가드와 같은 목록)이 있으면 True.
    없으면 빠른 움직임(손이 휙 지나감·새우 흔들림)을 잔상으로 잘못 본 것 — '움직임 의심'으로 따로 센다."""
    try:
        s = float(cut["s"]); d = float(cut.get("d") or 0.0)
        sd = float(cut["sd"]) if cut.get("sd") is not None else d
    except (KeyError, TypeError, ValueError):
        return True                      # 컷을 모르면 보수적으로 잔상으로 센다
    k = sd / d if d > 1e-6 else 1.0
    span = (int(n) + 1) / FPS * max(k, 1.0) + 0.5 / FPS
    e = s + sd
    for c in cuts or []:
        c = float(c)
        if side == "꼬리" and e - span - 1e-3 <= c <= e + 0.5 / FPS:
            return True
        if side == "머리" and s - 0.5 / FPS <= c <= s + span + 1e-3:
            return True
    return False


def _ghost_in_final(fe, ff, k, jf, T=None, win=2):
    """①의 잔상 프레임 k 와 닮은 프레임이 ②의 같은 자리(jf±win)에도 있나 — 있으면 계획(원본 좌표) 쪽, 없으면 화면만."""
    T = SCENE_T if T is None else T
    js = np.arange(max(0, jf - win), min(len(ff) - 1, jf + win) + 1)
    return bool(len(js)) and float(fm.dist(ff, js, fe[k]).min()) < T


def _save_boundary_strip(path, rE, rF, ie_b, jf_b, ne=4, nf=8):
    """경계 눈 확인용 띠: 위 줄 = 편집 화면 ie_b-ne..ie_b+ne, 아래 줄 = 완성본 jf_b-nf..jf_b+nf(가운데 정렬). 프레임 번호를 적는다."""
    ei = [i for i in range(ie_b - ne, ie_b + ne + 1) if 0 <= i < len(rE)]
    fj = [j for j in range(jf_b - nf, jf_b + nf + 1) if 0 <= j < len(rF)]
    n = max(len(ei), len(fj), 1)
    im = Image.new("RGB", (W * n, 2 * H + 28), "black")
    dr = ImageDraw.Draw(im)
    xe = (n - len(ei)) // 2 * W
    for k, i in enumerate(ei):
        im.paste(Image.fromarray(rE[i]), (xe + k * W, 0))
        dr.text((xe + k * W + 3, 2), "E%d%s" % (i, "*" if i == ie_b else ""), fill=(255, 255, 0) if i == ie_b else (200, 200, 200))
    xf = (n - len(fj)) // 2 * W
    for k, j in enumerate(fj):
        im.paste(Image.fromarray(rF[j]), (xf + k * W, H + 14))
        dr.text((xf + k * W + 3, H + 16), "F%d%s" % (j, "*" if j == jf_b else ""), fill=(255, 255, 0) if j == jf_b else (200, 200, 200))
    im.save(path, quality=80)


def check(jid):
    from shopping_shorts import app, mix_pipeline as mp, video_assemble as va, screen_clips as sc, clean_base as cb
    from shopping_shorts.store import Store
    cb._write = lambda work, base: None      # ★고객 clean_base.json 보호(calibrate가 고쳐 쓴다) — 도구는 읽기만
    st = Store("shopping_shorts/data/reference.db"); job = st.get_mix_job(jid)
    w = Path("shopping_shorts/data/mix_jobs") / jid
    plan = (job or {}).get("edit_plan") or {}
    beats = [b for b in plan.get("beats") or [] if b.get("tts_path") and Path(b["tts_path"]).exists()]
    if not beats:
        return None, "음성 없음"
    wd = OUT / jid
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    try:
        return _check(jid, app, mp, va, sc, st, job, w, plan, wd)
    finally:
        _keep = os.getenv("EVF_KEEP_FINAL")       # 관문·매일 점검: 소리 대조(final_audio_audit)가 **같은 완성본**을 잰다 — 렌더 2번 금지
        if _keep and (wd / "final_preview.mp4").exists():
            try:
                Path(_keep).mkdir(parents=True, exist_ok=True)
                shutil.move(str(wd / "final_preview.mp4"), str(Path(_keep) / ("%s.mp4" % jid)))
            except OSError as _e:
                print("[evf] %s 완성본 넘기기 실패: %s" % (jid, _e), file=sys.stderr)
        if not os.getenv("EVF_KEEP"):             # 원인 조사 때만 EVF_KEEP=1 로 남긴다(끝나면 손으로 지워라)
            shutil.rmtree(wd, ignore_errors=True)     # ★영상(①·②) 즉시 삭제 — 사진·보고서만 남긴다


def _check(jid, app, mp, va, sc, st, job, w, plan, wd):
    t0 = time.time()
    # ① 편집 화면 미리보기 — 화면과 같은 컷(screen_clips 러너) → 화면이 부르는 굽기 함수
    if sc.warm(job) <= 0:
        return None, "화면 계산 실패"
    cuts, blens, holds, scr = [], [], [], []
    for b in plan["beats"]:
        r = sc._CACHE.get(sc.beat_key(b)) or {}
        scr.append(list(r.get("c") or []))          # 화면 컷(원본 좌표) — 잔상이 실제 전환에서 왔나 가를 때 쓴다
        # 정지 컷(읽는 길이 < 화면 길이, 속도 맞추기 아님) — 완성본은 여기에 켄번즈 확대를 얹는다(_extend_with_frozen_motion),
        #   편집 화면은 그냥 멈춘다. 이 컷의 '밀림'은 대개 그 확대 차이다 → 보고서에 h 로 따로 표시한다.
        holds.append([bool(c.get("sd") is not None and float(c["sd"]) < float(c["d"]) - 0.02 and not c.get("fit"))
                      for c in (r.get("c") or [])])
        cl = [{"video_id": c["v"], "start": round(float(c["s"]), 3), "dur": round(float(c["d"]), 3),
               "src_dur": round(float(c["sd"] if c["sd"] is not None else c["d"]), 3), **({"fit": 1} if c.get("fit") else {})}
              for c in (r.get("c") or [])]
        cuts += cl; blens.append(len(cl))
    sig = "evf" + hashlib.sha1(json.dumps([cuts, blens]).encode()).hexdigest()[:12]
    srcs = {k: v for k, v in (mp._resolve_sources(job, w) or {}).items() if v and Path(v).exists()}
    tts = {int(b["beat_idx"]): b["tts_path"] for b in plan["beats"] if b.get("tts_path") and Path(b["tts_path"]).exists()}
    pv = wd / "pv"
    _orig_dir = app._pvproxy_dir
    app._pvproxy_dir = lambda _j: pv          # ★고객 pvproxy 폴더 대신 임시 폴더에 굽는다(굽기가 폴더의 다른 합본을 지운다)
    try:
        app._pvproxy_build(jid, sig, cuts, srcs, blens, tts)
    finally:
        app._pvproxy_dir = _orig_dir
    E = pv / ("%s.mp4" % sig)
    if not E.exists():
        return None, "화면 미리보기 굽기 실패"
    meta = json.loads((pv / ("%s.json" % sig)).read_text(encoding="utf-8"))
    t1 = time.time()
    # ② 완성본 만들기(임시 파일)
    F = wd / "final_preview.mp4"
    plan_used, paths, _b = mp.render_inputs_for(st, job, jid, w, [], job.get("customer_id") or 0, allow_clean=False)
    with mp.preview_preset():
        mp.assemble(plan_used, tts, paths, str(F), clean_fn=None, deco={})
    if not F.exists():
        return None, "완성본 렌더 실패"
    t2 = time.time()
    rE, rF = _frames(E), _frames(F)
    fe, ff = _feats(rE), _feats(rF)
    fe2, ff2 = fm.feats_low(rE), fm.feats_low(rF)
    ge, gf = _gray_full(rE), _gray_full(rF)
    me, mf = _motion(fe), _motion(ff)
    clean_beats = {int(x.get("beat_idx")) for x in (plan_used.get("beats") or []) if x.get("clean_replay")} if _b else set()
    # 칸 경계: ① = 굽기 기록(offs), ② = 음성 길이 누적(자막과 같은 자 — _beat_timeline)
    offs = meta.get("offs") or []
    e_end = offs[1:] + [meta.get("dur") or _dur(E)]
    f_t, rows, tiles, samples = 0.0, [], [], []
    for k, b in enumerate(plan["beats"]):
        if int(b["beat_idx"]) not in tts or k >= len(offs):
            continue
        td = float(va._beat_effective_dur(b, tts[int(b["beat_idx"])]))
        e0, e1 = offs[k], e_end[k]
        worst, shifts, per, bsh = 0.0, [], [], []
        # ★컷 한가운데를 찍는다 — 칸 비율 지점은 컷 경계에 걸리면 몇 프레임 차이로 다른 컷이 찍혀 오탐이 났다
        co = (meta.get("cuts") or [])[k] if k < len(meta.get("cuts") or []) else [0.0]
        bounds = list(co) + [e1 - e0]
        mids = [(i, (bounds[i] + bounds[i + 1]) / 2) for i in range(len(co)) if bounds[i + 1] - bounds[i] > 0.2]
        for ci, m_off in mids or [(0, (e1 - e0) / 2)]:
            q = m_off / max(1e-3, (e1 - e0))
            ie = int(round((e0 + m_off) * FPS))
            jf = int(round((f_t + td * q) * FPS))
            hold = bool(ci < len(holds[k]) and holds[k][ci]) if k < len(holds) else False
            _sc = max(1e-3, (e1 - e0))      # 정지 컷: ②에서 이 컷이 차지하는 프레임(칸 비율) 안에서만 찾는다
            span = ((int(np.ceil((f_t + td * bounds[ci] / _sc) * FPS)),
                     int(np.floor((f_t + td * bounds[ci + 1] / _sc) * FPS)) - 1) if hold else None)
            d, s, jb, old, curve, c0 = _match(fe, ff, ge, gf, ie, jf, span, fe2, ff2)
            worst = max(worst, d); shifts.append((s, hold)); per.append(("%d%s" % (ci, "h" if hold else ""), round(d, 2), round(s, 3)))
            samples.append({"job": jid, "beat": int(b["beat_idx"]), "cut": ci, "hold": hold, "d": round(d, 3), "shift": round(s, 3),
                            "old": round(old, 1), "c0": c0, "curve": curve})
            flag = "scene" if d >= SCENE_T else ("shift" if abs(s) >= SHIFT_T else "")
            tiles.append((int(b["beat_idx"]), ci, rE[min(ie, len(rE) - 1)], rF[jb], flag))
        # ★컷 경계 대조 — 가운데만 보면 정지 장면 컷의 시작이 늦어져도 못 본다(경계 자체를 찾아 시각을 잰다)
        for ci, c_off in enumerate(co):
            ie_b = int(round((e0 + c_off) * FPS))
            jf_b = int(round((f_t + td * c_off / max(1e-3, (e1 - e0))) * FPS))
            bs, spike = _boundary(fe, ff, me, mf, ie_b, jf_b)
            samples.append({"job": jid, "beat": int(b["beat_idx"]), "cut": ci, "kind": "boundary",
                            "bshift": None if bs is None else round(bs, 3), "spike": round(spike, 3)})
            if bs is not None and bs >= 9.0:
                # ★"②에 그 경계 없음"(9.9)은 도구의 한계인지 진짜 컷 누락인지 숫자로는 못 가른다 — 눈으로 볼 띠를 남긴다
                #   (2026-09-27 30 job 대조에서 7곳이 이 표기로 남아 원인 미확인). 위 = 화면 경계 ±4프레임, 아래 = 완성본 예상 자리 ±8프레임.
                try:
                    _save_boundary_strip(OUT / ("bnd_%s_b%d_c%d.jpg" % (jid, int(b["beat_idx"]), ci)), rE, rF, ie_b, jf_b)
                except Exception as _e:      # noqa: BLE001 — 사진은 보조. 판정을 막지 않는다
                    print("[evf] 경계 띠 저장 실패 %s b%d c%d: %s" % (jid, int(b["beat_idx"]), ci, _e), file=sys.stderr)
            if bs is not None:
                bsh.append((ci, round(bs, 3)))
        # ★컷 가장자리 잔상(딴 장면 1~3프레임) — 짧은 컷·경계 9.9 로 묻히던 것을 프레임 단위로 센다(2026-09-27)
        ghosts, shorts, motion = [], 0, []
        for ci in range(len(co)):
            a_ = int(round((e0 + co[ci]) * FPS))
            b_ = int(round((e0 + (co[ci + 1] if ci + 1 < len(co) else (e1 - e0))) * FPS)) - 1
            if b_ - a_ + 1 <= SHORT_CUT:
                shorts += 1
                samples.append({"job": jid, "beat": int(b["beat_idx"]), "cut": ci, "kind": "short", "frames": b_ - a_ + 1})
                continue
            hn, tn = _edge_ghosts(fe, a_, b_)
            for side, cnt, ks in (("머리", hn, range(a_, a_ + hn)), ("꼬리", tn, range(b_ - tn + 1, b_ + 1))):
                if not cnt:
                    continue
                only = sum(1 for k in ks if not _ghost_in_final(
                    fe, ff, k, int(round((f_t + td * (k / FPS - e0) / max(1e-3, (e1 - e0))) * FPS))))
                # ★완성본에도 있는 몫('둘 다')은 원본 장면 전환이 그 가장자리에 있을 때만 잔상으로 센다(2026-09-28) —
                #   전환이 없으면 빠른 움직임 오탐(68b4 칸1 컷0 손·62ed 칸5 컷2 새우)이라 '움직임 의심'으로 따로.
                both = cnt - only
                if both > 0:
                    _sc_ = (scr[k] if k < len(scr) else [])
                    _cut = _sc_[ci] if ci < len(_sc_) else None
                    try:
                        from shopping_shorts import seg_snap as _ss
                        _cl = _ss.scene_cuts(srcs.get(_cut["v"])) if (_cut and srcs.get(_cut["v"])) else None
                    except Exception:      # noqa: BLE001 — 전환 목록을 못 재면 보수적으로 잔상으로 센다
                        _cl = None
                    if _cut is not None and _cl is not None and not _ghost_backed_by_cut(_cut, side, cnt, _cl):
                        motion.append((ci, side, both))
                        samples.append({"job": jid, "beat": int(b["beat_idx"]), "cut": ci, "kind": "motion", "side": side,
                                        "frames": both, "at": list(ks)})
                        cnt = only
                        if not cnt:
                            continue
                ghosts.append((ci, side, cnt, only))
                samples.append({"job": jid, "beat": int(b["beat_idx"]), "cut": ci, "kind": "ghost", "side": side,
                                "frames": cnt, "screen_only": only, "at": list(ks)})
                try:        # 눈 확인용 띠(경계 띠와 같은 모양 — 위 = 화면 잔상 자리 ±4, 아래 = 완성본 같은 자리 ±8)
                    k0 = ks[0]
                    _save_boundary_strip(OUT / ("ghost_%s_b%d_c%d_%s.jpg" % (jid, int(b["beat_idx"]), ci, "h" if side == "머리" else "t")),
                                         rE, rF, k0, int(round((f_t + td * (k0 / FPS - e0) / max(1e-3, (e1 - e0))) * FPS)))
                except Exception as _e:      # noqa: BLE001 — 사진은 보조
                    print("[evf] 잔상 띠 저장 실패 %s b%d c%d: %s" % (jid, int(b["beat_idx"]), ci, _e), file=sys.stderr)
        _nh = [x for x, h in shifts if not h]; _h = [x for x, h in shifts if h]
        rows.append((int(b["beat_idx"]), round(worst, 2), max(_nh, key=abs) if _nh else 0.0,
                     round((e1 - e0) - td, 3), per, max(bsh, key=lambda x: abs(x[1])) if bsh else None,
                     int(b["beat_idx"]) in clean_beats, max(_h, key=abs) if _h else 0.0, ghosts, shorts, motion))
        f_t += td
    # 눈 확인용 사진: 컷마다 위 = 편집 화면(컷 한가운데), 아래 = 완성본에서 가장 닮은 프레임. 빨강=다른 장면, 노랑=밀림
    try:
        im = Image.new("RGB", (W * len(tiles), 2 * H + 12), "black")
        dr = ImageDraw.Draw(im)
        for i, (bi, ci, a, c, flag) in enumerate(tiles):
            im.paste(Image.fromarray(a), (i * W, 0)); im.paste(Image.fromarray(c), (i * W, H))
            if flag:
                dr.rectangle([i * W, 0, i * W + W - 1, 2 * H - 1], outline=(255, 0, 0) if flag == "scene" else (255, 220, 0), width=3)
            dr.text((i * W + 2, 2 * H), "%d.%d" % (bi, ci), fill=(255, 255, 255))
        im.save(OUT / ("eye_%s.jpg" % jid), quality=85)
    except Exception as e:      # noqa: BLE001
        print("[evf] %s 사진 실패: %s" % (jid, e), file=sys.stderr)
    with open(OUT / "samples.jsonl", "a", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    return {"job": jid, "rows": rows, "E": _dur(E), "F": _dur(F), "tts": round(f_t, 3),
            "sec": (round(t1 - t0, 1), round(t2 - t1, 1), round(time.time() - t2, 1))}, ""


def main():
    args = sys.argv[1:]
    n = int(args[0]) if args and args[0].isdigit() else 30
    ids = [a for a in args if not a.isdigit()]
    if not ids:
        con = sqlite3.connect("shopping_shorts/data/reference.db")
        ids = [r[0] for r in con.execute("select job_id from mix_jobs where preview_status='ready' order by updated_at desc limit ?", (n,))]
    rep = open(OUT / "report.txt", "w", encoding="utf-8")
    (OUT / "samples.jsonl").write_text("", encoding="utf-8")
    print("판정: 가운데 띠(%d~%d%%) 5x5 z거리 >= %.2f = 다른 장면 / 밀림 >= %.2fs (찾는 범위 ±%.1fs)" % (
        Y0 * 100 // H, Y1 * 100 // H, SCENE_T, SHIFT_T, SHIFT_WIN / FPS), file=rep, flush=True)
    print("표기: 칸번호(*=청소본 칸) · 가운데 [(컷(h=정지컷), 거리, 밀림초)] · 경계 (컷, 밀림초 — 9.9=②에 그 경계 없음)"
          " · 정지컷밀림 = 정지 컷에서만 난 밀림(완성본 켄번즈 확대 vs 화면 그냥 정지 — 따로 센다)", file=rep, flush=True)
    bad_scene = bad_shift = bad_bound = bad_hold = tot = 0
    ghost_fr = ghost_only = ghost_cuts = short_cuts = motion_fr = motion_cuts = 0
    for jid in ids:
        t0 = time.time()
        try:
            r, why = check(jid)
        except Exception as e:      # noqa: BLE001
            r, why = None, "%s: %s" % (type(e).__name__, str(e)[:120])
        if not r:
            print(jid, "건너뜀", why, file=rep, flush=True); continue
        nm = lambda x: "%d%s" % (x[0], "*" if x[6] else "")
        bs = [x for x in r["rows"] if x[1] >= SCENE_T]
        sh = [x for x in r["rows"] if abs(x[2]) >= SHIFT_T and x[1] < SCENE_T]
        bd = [x for x in r["rows"] if x[5] and abs(x[5][1]) >= SHIFT_T and x[1] < SCENE_T]
        hs = [x for x in r["rows"] if abs(x[7]) >= SHIFT_T and abs(x[2]) < SHIFT_T and x[1] < SCENE_T]
        tot += len(r["rows"]); bad_scene += len(bs); bad_shift += len(sh); bad_bound += len(bd); bad_hold += len(hs)
        gh = [(nm(x), g) for x in r["rows"] for g in x[8]]
        ghost_cuts += len(gh); ghost_fr += sum(g[2] for _, g in gh); ghost_only += sum(g[3] for _, g in gh)
        short_cuts += sum(x[9] for x in r["rows"])
        mo = [(nm(x), m) for x in r["rows"] for m in (x[10] if len(x) > 10 else [])]
        motion_cuts += len(mo); motion_fr += sum(m[2] for _, m in mo)
        print("%s 칸%d(청소본 %d) 화면%.2fs 완성본%.2fs 음성%.2fs | 다른장면 %s | 밀림%.2f+ %s | 경계밀림 %s | 정지컷밀림 %s | 최대거리 %.2f | %.0fs(굽기%.0f 렌더%.0f 비교%.0f)" % (
            jid, len(r["rows"]), sum(1 for x in r["rows"] if x[6]), r["E"], r["F"], r["tts"],
            [(nm(x), x[1], x[4]) for x in bs], SHIFT_T, [(nm(x), round(x[2], 3), x[4]) for x in sh],
            [(nm(x), x[5]) for x in bd], [(nm(x), round(x[7], 3), x[4]) for x in hs], max([x[1] for x in r["rows"]] or [0]), time.time() - t0, *r["sec"])
            # 잔상 = (칸, (컷, 머리|꼬리, 프레임 수, 그중 화면에만 있는 수)) · 짧은컷 = 3프레임 이하 컷 수 — 줄 끝에 붙인다(관문 정규식은 줄 앞만 본다)
            + " | 잔상 %s | 짧은컷 %d | 움직임의심 %s" % (gh, sum(x[9] for x in r["rows"]), mo),
            file=rep, flush=True)
    print("== 칸 %d · 다른 장면 %d · %.2f초 이상 밀림(가운데) %d · 경계 밀림 %d · 정지컷만 밀림 %d" % (
          tot, bad_scene, SHIFT_T, bad_shift, bad_bound, bad_hold),
          file=rep, flush=True)
    # ★잔상은 **따로 한 줄**(2026-09-27) — 위 '== 칸' 줄은 tools/video_gate.py _SUMMARY 가 줄 끝($)까지 맞춰 읽는다.
    #   거기 덧붙이면 관문이 '요약 줄을 못 읽었다'로 실패한다. 판정에 넣으려면 video_gate 에 이 줄 파서를 같이 넣어라.
    print("== 잔상 %d프레임(컷 %d · 화면에만 %d프레임) · 짧은컷(%d프레임 이하) %d" % (
          ghost_fr, ghost_cuts, ghost_only, SHORT_CUT, short_cuts), file=rep, flush=True)
    # 움직임 의심 = 가장자리가 튀었지만 원본에 장면 전환이 없는 곳(빠른 움직임) — 잔상에서 빼고 보고만(관문 판정 밖)
    print("== 움직임 의심 %d프레임(컷 %d)" % (motion_fr, motion_cuts), file=rep, flush=True)


if __name__ == "__main__":
    main()
