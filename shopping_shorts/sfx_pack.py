# -*- coding: utf-8 -*-
"""썰채널 효과음팩 자동배치 (2026-09-22, 이븐쇼핑 12편 실측 규칙).

실측 원문: 바탕화면 `이븐쇼핑_효과음_벤치마크/이븐쇼핑_효과음_규칙_분석.md` · 도구 `tools/sfx_bench/`.

★기준점은 컷이 아니라 **자막 한 줄이 바뀌는 순간**이다(휙·둥·띠링 93~94%, 우연 16%).
  그래서 시각은 렌더가 자막을 띄우는 함수(video_assemble.caption_schedule)에서 **그대로** 받는다.
  따로 계산하면 자막과 어긋난다(0순위-B). 회원이 자막을 쪼개거나 합쳐도 소리가 따라간다.

규칙(12편 실측):
  영상 시작 0.06초       오프너 1발 (12/12). 제목 칸 안에서는 다른 소리 없음.
  첫 칸 → 둘째 칸 넘김   휙(넘김 0.035초 전) + 틱(0.07초 뒤)  (틱 12/12, 휙 8/12)
  그 뒤 **칸(장면)마다 2발**, 첫 자막 줄과 가운데 줄에 — 소리는 **그 칸의 역할**이 정한다(ROLE_GROUPS → GROUP_SOUNDS).

회원마다 팩 하나를 고정 배정한다(20종, 두 팩 사이 7칸 중 최소 4칸 다름) — 회원끼리 소리가 달라진다.
켜는 조건: 관리자 설정 sfx_pack_enabled("1"=전 회원 · "admin"=사장님 계정만) + 영상별 스위치(deco.sfx_pack).
  스위치를 손댄 적 없으면 **기본값**만 대본으로 정한다(썰 구조=켜짐 / 아니면 꺼짐) — 사람이 켜면 어떤 대본이든 들어간다.
  ★채널 틀로 판정하지 않는다(2026-09-22 사장님 "썰대본을 골랐을경우만"). 라이브 최근 400건 실측:
    썰 틀 262건 중 썰 대본은 28건뿐 — 틀 기준이면 234건에 잘못 켜지고 틀 없는 썰 대본 5건은 빠졌다.
"""
import os
import re
import sys
import zlib

PACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sfx_packs")
SLOTS = ("opener", "pop", "dung", "ding", "whoosh", "tick", "click2")

OPENER_AT = 0.06          # 실측: 12편 전부 0.03~0.07초
WHOOSH_LEAD = 0.035       # 첫 넘김: 휙이 넘김보다 먼저(8편 중앙)
TICK_LAG = 0.07           # 첫 넘김: 틱이 넘김보다 뒤(12편 중앙)

# ★소리는 **대본 틀의 칸 역할**이 정한다(2026-09-22 사장님: "억지로 넣는 게 아니라 들어갈 수밖에 없는 구조").
#   썰 대본은 틀(스파인)의 칸 역할대로 쓰이고, 그 역할이 곧 이븐쇼핑에서 소리를 가르던 문구 종류다
#   ("이게 말도 안 되는 게"=limit → 둥 · "진짜 충격적인 포인트는"=twist → 둥 · 결과=more/benefit → 띠링 ·
#    쓰는 법=solve/how/cases → 뽁·딸깍 · 떡밥=bait/fame → 휙). 단어 검색·순환·밀도 깎기는 없다.
#   역할 이름은 틀마다 영어/한글이 섞여 있어 같은 구간끼리 묶는다(라이브 썰 대본 33편에서 나온 이름 전부).
ROLE_GROUPS = {
    "떡밥": ("bait", "fame", "story", "origin", "pain", "problem", "setup", "notice", "미끼", "상황 제시"),
    "공개": ("reveal", "공개"),
    "반박": ("limit", "대비"),
    "시연": ("solve", "how", "demo", "cases", "escalate", "escalation", "고조", "기능 실증", "사용법 차별화", "제품 특징"),
    "결과": ("more", "benefit"),
    "반전": ("twist", "반전"),
    "마무리": ("land", "cta", "마무리", "마무리 cta"),
}
# 구간별 소리 — **이븐쇼핑 12편 구간별 실측 건수 그대로**(짐작·반올림 없음). 순서는 _spread가 고르게 편다.
RING_COUNTS = {
    "떡밥": {"whoosh": 23, "pop": 21, "tick": 15, "ding": 10, "dung": 9, "click2": 3},     # 떡밥 100건
    "시연": {"pop": 58, "whoosh": 29, "tick": 19, "click2": 17, "dung": 10, "ding": 10},  # 시연 202건
    "반전": {"whoosh": 9, "pop": 9, "dung": 7, "ding": 3, "tick": 2, "click2": 2},        # 반전 43건
    "마무리": {"whoosh": 12, "ding": 4, "pop": 2, "tick": 1, "click2": 1},                # 마무리 25건
    "공개": {"whoosh": 4, "tick": 1, "dung": 1, "click2": 1},                             # 정체공개 12건
}


def _spread(counts, n=16):
    """실측 건수 → 길이 n 순서. 각 소리가 제 비율만큼, 한 소리가 몰리지 않게 고르게 펴진다(결정적)."""
    tot = sum(counts.values())
    quota = {k: v * n / tot for k, v in counts.items()}
    out, got = [], {k: 0 for k in counts}
    for i in range(n):
        k = max(counts, key=lambda x: (quota[x] * (i + 1) / n - got[x], counts[x]))
        out.append(k); got[k] += 1
    return tuple(out)


RINGS = {g: _spread(c) for g, c in RING_COUNTS.items()}
# 구간 → (칸 첫 자막에 고정되는 소리 또는 None, 나머지 자막이 도는 순서)
#   첫 자막 고정은 **문구 종류가 소리를 정한 것만**(실측): 반전 "진짜 충격적인 포인트는"=둥 6/10 ·
#   반박 "이게 말도 안 되는 게"=둥 · 결과("변신시켜버렸다는 거"·"끝판왕")=띠링.
GROUP_SOUNDS = {
    "떡밥": (None, "떡밥"),
    "공개": (None, "공개"),
    "반박": ("dung", "시연"),
    "시연": (None, "시연"),
    "결과": ("ding", "시연"),
    "반전": ("dung", "반전"),
    "마무리": (None, "마무리"),
}
DEFAULT_SOUNDS = (None, "떡밥")     # 표에 없는 역할
_ROLE_TO_GROUP = {r: g for g, rs in ROLE_GROUPS.items() for r in rs}


def sounds_for_role(role):
    """칸 역할 → (첫 자막 고정 소리|None, 나머지가 도는 순서). 번호 붙은 역할("고조1")은 번호를 떼고 본다."""
    r = re.sub(r"\d+$", "", str(role or "").strip().lower())
    first, ring = GROUP_SOUNDS.get(_ROLE_TO_GROUP.get(r), DEFAULT_SOUNDS)
    return first, RINGS[ring]


# 팩 소리 보정(배) — 실렌더에서 목소리 대비 크기를 이븐쇼핑과 맞춘 값(tools/sfx_bench/render_check.py).
#   기본 효과음 볼륨 60%만으로는 이븐쇼핑보다 약 8dB 작았다(휙 -10.6 vs -2.7dB). 7.0으로 올리니 7종 모두
#   +2.4~2.8dB 컸다(나레이션 차감 잔여로 잰 값) → 4.3.
PACK_GAIN_DB = 4.3
# 칸별 목표 크기(20ms 최대, dBFS) — 이븐쇼핑 12편 실측(목소리 중앙 -17.5 기준). 파일마다 실제 크기를 재서
#   이 값에 맞춘다 → 팩·파일이 바뀌어도 크기가 저절로 맞는다(2026-09-22: 팩10 둥 파일이 목표보다 3dB 작아
#   라이브 영상에서 둥이 약했다 — 팩을 만들 때 찢어짐 방지로 최대값을 눌러 뾰족한 소리만 작아졌던 것).
# ★작은 소리는 바닥을 올린다(2026-09-22 사장님 "잘 안 들린다"): 이븐쇼핑 실측대로면 휙·틱·딸깍이
#   목소리 중앙(-17.5)보다 작아 우리 목소리에 묻혔다. -14.5로 올려도 그 순간 목소리가 큰 곳에서 13발 중 6발이
#   묻혔다(tools/sfx_bench/audible.py) → -11.0. 이 크기면 덕킹(-14dBFS 이상)도 함께 걸려 목소리가 살짝 비켜 준다.
_AUDIBLE_FLOOR_DB = -11.0
LEVEL_TARGET_DB = {k: max(v, _AUDIBLE_FLOOR_DB) for k, v in {
    "opener": -8.8, "dung": -7.0, "pop": -11.9, "ding": -14.7,
    "whoosh": -20.2, "tick": -22.4, "click2": -20.6}.items()}
_LEVEL_CACHE = {}


def _peak20_db(path):
    """wav 파일의 20ms 창 최대 세기(dBFS). 한 번 잰 파일은 기억한다."""
    if path in _LEVEL_CACHE:
        return _LEVEL_CACHE[path]
    import wave
    import numpy as np
    try:
        with wave.open(path, "rb") as w:
            sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
            raw = w.readframes(w.getnframes())
        x = np.frombuffer(raw, dtype={2: np.int16, 4: np.int32}[sw]).astype(float) / (2 ** (8 * sw - 1))
        if ch > 1:
            x = x.reshape(-1, ch).mean(1)
        k = max(1, int(0.02 * sr))
        v = float(20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(k) / k, "valid")).max() + 1e-9))
    except Exception:      # noqa: BLE001 — 못 재면 보정 없이(종전 크기 그대로)
        v = None
    _LEVEL_CACHE[path] = v
    return v


def _gain_for(path, slot):
    """이 파일을 칸 목표 크기로 맞추고 팩 보정까지 곱한 배율."""
    g = PACK_GAIN_DB
    cur = _peak20_db(path)
    if cur is not None and slot in LEVEL_TARGET_DB:
        g += LEVEL_TARGET_DB[slot] - cur
    return round(10 ** (g / 20), 4)

def list_packs():
    """[(팩이름, 폴더)] — 7칸이 다 있는 팩만. 이름순 = 배정이 실행마다 같다."""
    try:
        names = sorted(n for n in os.listdir(PACK_DIR) if os.path.isdir(os.path.join(PACK_DIR, n)))
    except OSError:
        return []
    out = []
    for n in names:
        d = os.path.join(PACK_DIR, n)
        if all(os.path.isfile(os.path.join(d, s + ".wav")) for s in SLOTS):
            out.append((n, d))
    return out


# 지금 쓰는 팩 — 2026-09-22 사장님 확정("이런 구성으로 가자"): 사장님이 고른 소리(바탕화면 '새 폴더 (2)')로
#   만든 팩 하나를 전 회원에게. 팩01~20(이븐쇼핑 대조로 고른 조합)은 지우지 않고 보관 — 회원마다 다르게
#   하고 싶으면 이 목록에 이름을 넣으면 그 안에서 회원별로 돌린다.
ACTIVE_PACKS = ("팩21_사장님",)


SLOT_LABEL = {"opener": "시작(두둥)", "pop": "뽁", "dung": "둥", "ding": "띠링", "whoosh": "휙", "tick": "틱", "click2": "딸깍"}


def pack_label(name):
    """팩 폴더 이름 → 회원에게 보여줄 이름. 팩21_사장님=기본(전 회원 배정), 나머지는 '소리 묶음 N'."""
    if name in ACTIVE_PACKS:
        return "기본"
    m = re.match(r"팩(\d+)", str(name))
    return "소리 묶음 %d" % int(m.group(1)) if m else str(name)


def pack_for(customer_id, override=None):
    """회원 → 팩 (이름, 폴더). override(1부터, 전체 목록 기준)가 있으면 그 팩. 팩이 없으면 None.
    기본은 ACTIVE_PACKS 안에서 고른다(없으면 전체). crc32라 프로세스마다 안 바뀐다 — 미리보기=최종본."""
    allp = list_packs()
    active = [x for x in allp if x[0] in ACTIVE_PACKS]
    try:
        if override is not None and str(override).strip() not in ("", "auto"):
            i = int(override) - 1
            if 0 <= i < len(allp):
                return allp[i]
    except (TypeError, ValueError):
        pass
    packs = active or allp
    if not packs:
        return None
    return packs[zlib.crc32(str(customer_id or 0).encode()) % len(packs)]


def script_family(store, job):
    """이 job의 대본이 고른 틀(스파인)의 갈래 목록. 모르면 [].

    job.script_structure.script_style_id(없으면 제작 작업 produce_works.job_id → state.script_style_id)
    = 2단계에서 고른 스파인 id(app.py record_script_usage(spine_id=dr["style_id"])와 같은 값) → fit_categories.
    """
    # ① job 자체에 박힌 번호(3단계 시작 때 produce.html이 script_structure에 싣는다 — 끊기지 않는다)
    sid = ((job or {}).get("script_structure") or {}).get("script_style_id")         if isinstance((job or {}).get("script_structure"), dict) else None
    # ② 옛 job(번호를 안 싣던 때)은 제작 기록에서 찾는다 — 기록이 지워졌으면 모른다(=끔)
    if sid is None:
        try:
            st = store.get_work_state_by_job((job or {}).get("job_id"))
        except Exception:      # noqa: BLE001
            return []
        sid = (st or {}).get("script_style_id")
    if sid is None or not str(sid).strip().isdigit():
        return []
    try:
        sp = next((x for x in store.list_spines() if int(x.get("id") or -1) == int(sid)), None)
    except Exception:      # noqa: BLE001
        return []
    return list((sp or {}).get("fit_categories") or [])


TITLE_CARD = 1.5           # 영상 앞 제목 카드 — 이 구간엔 오프너 1발만(이븐쇼핑 12/12)
MAX_SILENCE = 2.2          # 이 초를 넘는 자막 줄은 한가운데에 한 발 더(이븐쇼핑 최장 무음 1.7~2.5초)
ROLE_MATCH_MIN = 0.8      # 칸 역할이 이만큼 썰 구조면 썰 대본으로 본다


def looks_sul_by_roles(job):
    """칸 역할이 썰 구조인가 — 틀 번호가 없는 대본(직접 쓰기·씨앗 기반)을 위한 판정.

    ★2026-09-23 사장님 제보("대본 새로 뽑았는데 스위치가 없다"): 2단계 틀 목록으로 고르지 않은 대본은
      script_style_id가 없어 갈래를 모른다. 그런데 그런 job도 칸 역할은 훅·미끼·공개·고조·반전·마무리
      (=썰 틀 그대로)였다. 효과음이 어차피 이 역할을 보고 들어가니 판정도 같은 근거를 쓴다.
      라이브 300건 실측: 썰 갈래 27건은 전부 역할 일치 80%+ · 갈래 없는 80%+ 15건은 확인해 보니 전부
      썰 대본("천재가 만들어 떼돈"…) · 나머지 254건은 80% 미만(인스타·후기 등)이라 갈리는 선이 뚜렷하다.
    """
    beats = ((job or {}).get("edit_plan") or {}).get("beats") or []
    if len(beats) < 4:
        return False
    roles = [re.sub(r"\d+$", "", str(b.get("role") or "").strip().lower()) for b in beats[1:]]
    if not roles:
        return False
    known = {r for rs in ROLE_GROUPS.values() for r in rs}
    return sum(r in known for r in roles) / len(roles) >= ROLE_MATCH_MIN


def is_sul_script(store, job):
    """썰 대본인가 — ①고른 틀의 갈래(오용형·제품정체형·발명품형) 또는 ②칸 역할이 썰 구조."""
    from shopping_shorts import script_genre
    fam = script_family(store, job)
    if script_genre.is_context("", [{"fit_categories": fam}], script_genre.YOUTUBE_SUL_FAMILY):
        return True
    return looks_sul_by_roles(job)


# ★사용자 조절(2026-10-01 관제 059, 사장님 "효과음 탭 4개 사용자 선택") — 값의 뜻은 **여기 한 곳**이 정한다.
#   deco.sfx_density  : "low"(칸 첫 줄만) · "normal"(자막 줄마다 1발, 긴 줄 2발=지금) · "high"(줄마다 1발, 1.4초 넘는 줄 2발)
#   deco.sfx_level    : "low"(-3dB) · "normal" · "high"(+3dB)   — PACK_GAIN_DB 위에 더한다
#   deco.sfx_pack     : "off" · "auto"(회원 배정) · "7"(전체 팩 목록 번호, 1부터)
#   deco.sfx_mute_beats: [beat_idx, …] 이 칸은 효과음 없음(사람이 고른 효과음은 그대로)
DENSITY_MAX_SILENCE = {"low": None, "normal": MAX_SILENCE, "high": 1.4}
LEVEL_DB = {"low": -3.0, "normal": 0.0, "high": 3.0}
DENSITY_LABEL = {"low": "적게", "normal": "보통", "high": "많이"}
LEVEL_LABEL = {"low": "작게", "normal": "보통", "high": "크게"}


def settings_of(deco):
    """deco → {"pack","density","level","mute_beats"} 정규화. 모르는 값은 기본으로."""
    d = deco if isinstance(deco, dict) else {}
    pack = str(d.get("sfx_pack") or "").strip()
    if pack not in ("off", "auto") and not pack.isdigit():
        pack = ""
    density = str(d.get("sfx_density") or "normal")
    level = str(d.get("sfx_level") or "normal")
    mute = set()
    for x in (d.get("sfx_mute_beats") or []):
        try:
            mute.add(int(x))
        except (TypeError, ValueError):
            pass
    return {"pack": pack, "density": density if density in DENSITY_MAX_SILENCE else "normal",
            "level": level if level in LEVEL_DB else "normal", "mute_beats": sorted(mute)}


def resolve(store, job):
    """이 job에 쓸 팩 {"name","dir","density","level","mute_beats"} 또는 None.
    렌더·미리보기·캡컷이 전부 여기 하나를 거친다 — 사용자 조절값도 여기서만 읽는다."""
    if not job:
        return None
    deco = job.get("deco") or {}
    st = settings_of(deco)
    choice = st["pack"]
    if choice == "off":
        return None
    # 관리자 스위치 — ""=끔 · "admin"=사장님(cid 0) 영상에서만(시험용) · "1"=전 회원.
    #   2026-09-23 사장님 "관리자만 켜봐 테스트 해보게": 배포해도 고객 영상은 그대로 두고 먼저 시험한다.
    try:
        mode = str(store.get_setting("sfx_pack_enabled", "") or "").strip().lower()
    except Exception:      # noqa: BLE001
        return None
    if mode not in ("1", "on", "admin"):
        return None
    if mode == "admin" and int(job.get("customer_id") or 0) != 0:
        return None
    # ★스위치가 최종 결정이다(2026-09-23 사장님 "하고 싶은 사람은 체크하고 완성본 만들면 되잖아").
    #   사람이 켠 적 없으면(choice 비어 있음) **기본값만** 대본으로 정한다 — 썰 구조면 켜짐, 아니면 꺼짐.
    #   판정이 애매한 대본(틀 번호 없음 등)도 화면에서 켜면 그대로 들어간다.
    if not choice and not is_sul_script(store, job):
        return None
    got = pack_for(job.get("customer_id", 0), override=choice)
    if not got:
        return None
    return {"name": got[0], "dir": got[1], "density": st["density"], "level": st["level"],
            "mute_beats": st["mute_beats"]}


HOLD_PAD = 0.05     # 줄 효과음 꼬리 뒤 여유(초) — 바로 붙어 울리면 겹쳐 들린다


def plan_events(timeline, manual_beats=(), density="normal", first_beats=(), mute_beats=()):
    """[(소리, 절대초, 자막)] — 파일 경로 없이 '무엇을 언제'만. 테스트·검증이 이걸 본다.

    영상 시작 = 오프너 · 첫 칸→둘째 칸 넘김 = 휙+틱 · 그 뒤 자막 줄이 바뀔 때마다 1발(칸 첫 줄은 칸 역할의 소리).
    시각은 렌더 자막 함수(caption_schedule)에서 그대로 받는다. manual_beats(사람이 고른 칸·끈 칸)는 건너뛴다.
    density(2026-10-01 사용자 조절): "low"=칸 첫 줄만 · "normal"=지금 규칙 · "high"=1.4초 넘는 줄도 가운데 1발.
    mute_beats(deco.sfx_mute_beats — 3단계 칸 🔇·2단계 줄 끔): 그 칸 팩 소리 전부 없음 — 첫 칸이면 오프너도(10-07 사장님 "그 줄 효과음 전체").
    """
    from shopping_shorts.video_assemble import caption_schedule
    tl = [b for b in (timeline or []) if float(b.get("dur") or 0) > 0]
    if not tl:
        return []
    density = density if density in DENSITY_MAX_SILENCE else "normal"
    max_silence = DENSITY_MAX_SILENCE[density]
    mute = set(mute_beats or ())
    manual = set(manual_beats or ()) | mute
    # 줄 효과음(짤 리액션 등)이 그 줄 시작을 맡은 칸 — 그 순간의 팩 소리를 비운다.
    #   dict({칸: 줄 효과음 길이 초})로 오면 그 소리가 울리는 동안의 팩 소리도 비운다(10-07 사장님 "겹치는 거 빼고" —
    #   실측 951d050cc3df: 넷플 두둥 2.0초 끝 0.3초에 휙이 겹쳤다). 줄 효과음을 빼면 이 목록에서 빠져 팩 소리가 저절로 돌아온다.
    hold = dict(first_beats) if isinstance(first_beats, dict) else {}
    line_first = set(first_beats or ())
    total = sum(float(b["dur"]) for b in tl)
    ev = [] if (tl[0]["beat_idx"] in line_first or tl[0]["beat_idx"] in mute) else [("opener", OPENER_AT, "")]
    if len(tl) >= 2 and tl[1]["beat_idx"] not in manual and tl[1]["beat_idx"] not in line_first:
        t = float(tl[1]["t0"])
        ev += [("whoosh", max(0.0, t - WHOOSH_LEAD), ""), ("tick", t + TICK_LAG, "")]
    used = {}           # 순서별로 **영상 전체에서 이어 센다** — 칸마다 새로 세면 앞 몇 칸만 쓰인다(실측: 둥 19%)
    for bi, b in enumerate(tl):
        if b["beat_idx"] in manual:
            continue
        # 제목 카드(영상 앞 1.5초) 안은 오프너만 — 이븐쇼핑 12/12. 첫 칸이 그보다 길면
        # 나머지 자막 줄은 여느 칸과 똑같이 운다(2026-09-24: 첫 칸 5.3초짜리 대본에서 5.2초 무음이 났다).
        # ★자막 한 줄이 바뀔 때마다 1발 — 이븐쇼핑의 기준점이 컷이 아니라 자막 교체다(분석 §0-2).
        #   2026-09-24: '장면당 2발'은 칸이 길수록 구멍이 났다(실측 f3a57a316f6c 최장 3.36초 무음,
        #   이븐쇼핑 4편은 1.7~2.5초). 줄마다 울리면 최장 1.97초·초당 0.72로 이븐쇼핑 간격에 든다.
        sched = caption_schedule(b)
        if not sched:
            continue
        first, ring = sounds_for_role(b.get("role"))
        picks = list(range(len(sched)))
        for k in picks:
            seg, start, end = sched[k]
            if float(start) < TITLE_CARD:
                continue
            if density == "low" and k > 0:
                continue        # 적게: 칸의 첫 자막 줄에만
            if k == 0 and b["beat_idx"] in line_first:
                pass            # 줄 시작은 줄 효과음이 맡았다 — 긴 줄 한가운데 한 발은 아래에서 그대로 본다
            elif bi == 1 and k == 0:
                pass        # 둘째 칸 첫 줄은 첫 넘김 휙+틱이 맡았다 — 줄 한가운데는 아래에서 본다
            elif k == 0 and first:
                ev.append((first, start, seg))
            else:
                n = used.get(ring, 0); used[ring] = n + 1
                ev.append((ring[n % len(ring)], start, seg))
            # ★한 줄이 길면 그 줄 한가운데에 한 발 더 — 이븐쇼핑은 무음이 2.5초를 넘지 않는다(4편 실측).
            if max_silence is not None and float(end) - float(start) > max_silence:
                n = used.get(ring, 0); used[ring] = n + 1
                ev.append((ring[n % len(ring)], (float(start) + float(end)) / 2.0, seg))
    ev = [e for e in ev if e[1] < total]
    if hold:
        spans = [(float(b["t0"]), float(b["t0"]) + float(hold.get(b["beat_idx"]) or 0) + HOLD_PAD)
                 for b in tl if float(hold.get(b["beat_idx"]) or 0) > 0]
        ev = [e for e in ev if not any(a - 1e-6 <= float(e[1]) < z for a, z in spans)]
    ev.sort(key=lambda e: e[1])
    return ev


def _owner_of(tl, slot, t):
    """팩 소리 한 발이 어느 칸(줄) 몫인가 — 2단계 미리보기와 렌더가 **같이** 쓴다(줄 안 순번이 같은 규칙으로 세지게).
    휙은 둘째 칸 시작 직전(WHOOSH_LEAD)에 울리므로 둘째 칸 몫으로 센다. 어느 칸에도 안 들면 None."""
    at = float(t) + (WHOOSH_LEAD if slot == "whoosh" else 0.0)
    for b in tl:
        a = float(b["t0"])
        if a - 1e-6 <= at < a + float(b["dur"]):
            return b["beat_idx"]
    return None


def clean_pack_edit(v):
    """줄(칸) 하나의 '팩 소리 고름'을 정해진 모양으로만 남긴다 — 확정 길(storyboard.carry_picks)·미리보기·렌더가 이것만 믿는다.
    모양: {"off": [{"slot": 이름, "n": 그 줄 안 같은 이름의 순번(0부터)}], "swap": [{"slot", "n", "to": 다른 소리 이름}]}
    ★시각은 담지 않는다 — 2단계 시각은 말속도 어림값이라 3단계 실측과 다르다. 이름+순번으로만 가리킨다."""
    if not isinstance(v, dict):
        return None
    def _ref(x, need_to=False):
        if not isinstance(x, dict) or x.get("slot") not in SLOTS:
            return None
        try:
            n = int(x.get("n") or 0)
        except (TypeError, ValueError):
            return None
        if n < 0 or n > 50:
            return None
        r = {"slot": x["slot"], "n": n}
        if need_to:
            if x.get("to") not in SLOTS or x.get("to") == x["slot"]:
                return None
            r["to"] = x["to"]
        return r
    off = [r for r in (_ref(x) for x in (v.get("off") or [])[:30] if isinstance(v.get("off"), list)) if r]
    swap = [r for r in (_ref(x, True) for x in (v.get("swap") or [])[:30] if isinstance(v.get("swap"), list)) if r]
    out = {}
    if off:
        out["off"] = off
    if swap:
        out["swap"] = swap
    return out or None


def apply_pack_edit(events_per_beat, pack_edit, keep_off=False, log=None):
    """사람이 2단계에서 고른 '팩 소리 빼기·바꾸기'를 칸별 배치에 입힌다 — **주인 함수 하나**(미리보기·렌더·캡컷 공통).
    events_per_beat: {칸번호: [(소리, 절대초, 자막), ...]} (plan_events 를 칸별로 나눈 것, 시간순)
    pack_edit: {칸번호: clean_pack_edit 모양}
    keep_off: True 면 뺀 소리를 지우지 않고 4번째 칸에 표시("off")만 한다(화면이 회색 취소선·되돌리기를 그리게).
    돌려주는 것: 같은 모양 dict. 바꾼 소리는 이름이 바뀌고(시각 그대로), 4번째 칸이 {"from": 원래 이름} 또는 "off".

    ★가리키는 법 = '그 칸 안 같은 이름 소리의 n번째'. 2단계(어림 시각)와 3단계(TTS 실측)에서 칸 안 소리 개수가
      달라질 수 있어 '그 칸 k번째 소리'로 가리키면 엉뚱한 소리를 지운다. 이름+순번이면 같은 소리를 찾고,
      못 찾으면(실측에서 그 소리가 사라짐) **무시하고 로그만** 남긴다 — 조용히 다른 소리를 지우지 않는다."""
    log = log or (lambda m: print("[sfx_pack] " + m, file=sys.stderr))
    out = {}
    for bi, evs in (events_per_beat or {}).items():
        rows = [list(e[:3]) + [None] for e in evs]
        ed = clean_pack_edit((pack_edit or {}).get(bi))
        if ed:
            def _find(ref):
                seen = -1
                for r in rows:
                    orig = r[3]["from"] if isinstance(r[3], dict) else r[0]
                    if orig == ref["slot"]:
                        seen += 1
                        if seen == ref["n"]:
                            return r
                log("칸 %s: 고른 팩 소리 %s #%d 을(를) 못 찾아 무시(실측 배치에서 사라짐)" % (bi, ref["slot"], ref["n"]))
                return None
            for ref in ed.get("swap") or []:
                r = _find(ref)
                if r is not None and r[3] != "off":
                    r[3] = {"from": r[0] if not isinstance(r[3], dict) else r[3]["from"]}
                    r[0] = ref["to"]
            for ref in ed.get("off") or []:
                r = _find(ref)
                if r is not None:
                    if isinstance(r[3], dict):
                        r[0] = r[3]["from"]       # 뺀 소리는 원래 이름으로 보인다(되돌리면 원래 소리)
                    r[3] = "off"
        out[bi] = [tuple(r) for r in rows if keep_off or r[3] != "off"]
    return out


def plan_per_beat(timeline, manual_beats=(), density="normal", first_beats=(), pack_edit=None, keep_off=False, log=None, mute_beats=()):
    """plan_events → 칸별로 나눔 → apply_pack_edit. 미리보기(preview_lines)와 렌더(events)가 **이것 하나**를 부른다."""
    tl = [b for b in (timeline or []) if float(b.get("dur") or 0) > 0]
    per = {}
    for slot, t, seg in plan_events(timeline, manual_beats, density=density, first_beats=first_beats, mute_beats=mute_beats):
        owner = _owner_of(tl, slot, t)
        if owner is None:
            continue
        per.setdefault(owner, []).append((slot, t, seg))
    return apply_pack_edit(per, pack_edit, keep_off=keep_off, log=log)


def events(timeline, pack, manual_beats=(), first_beats=(), pack_edit=None):
    """[(경로, 절대초, 보정배)] — sfx_events_for가 부른다. pack: resolve()의 결과.
    세 번째 칸(보정배)은 렌더·캡컷이 효과음 볼륨에 곱한다(없으면 1.0 — 종전 이벤트와 호환).
    pack_edit: {칸번호: 2단계에서 고른 팩 소리 빼기·바꾸기} — 실제 TTS 시각으로 배치한 뒤 apply_pack_edit 가 입힌다."""
    if not pack or not pack.get("dir"):
        return []
    skip = set(manual_beats or ())
    mute = set(pack.get("mute_beats") or ())      # 끈 칸 — plan_events 가 그 칸 팩 소리를 전부(첫 칸이면 오프너도) 뺀다
    level_mul = 10 ** (LEVEL_DB.get(pack.get("level") or "normal", 0.0) / 20.0)
    density = pack.get("density") or "normal"
    if pack_edit:
        flat = [e for evs in plan_per_beat(timeline, skip, density, first_beats, pack_edit, mute_beats=mute).values() for e in evs]
        flat.sort(key=lambda e: e[1])
    else:
        flat = plan_events(timeline, skip, density=density, first_beats=first_beats, mute_beats=mute)     # 고름 없으면 종전 그대로(칸 밖 소리도 유지)
    out = []
    for e in flat:
        slot, t = e[0], e[1]
        path = os.path.join(pack["dir"], slot + ".wav")
        out.append((path, t, _gain_for(path, slot) * level_mul))
    return out


def preview_timeline(lines):
    """2단계(음성 없음)용 가짜 timeline — 줄 길이는 말속도 주인 edit_plan.narr_secs 로 어림.
    lines: [{"role","text"}]. beat_idx = 줄 번호(0부터). 실제 3단계는 TTS 실측 시각으로 다시 계산한다."""
    from shopping_shorts.edit_plan import narr_secs
    tl, t0 = [], 0.0
    for i, ln in enumerate(lines or []):
        text = str((ln or {}).get("text") or "").strip()
        if not text:
            continue
        dur = float(narr_secs(text))
        tl.append({"beat_idx": i, "t0": t0, "dur": dur, "narration": text,
                   "role": re.sub(r"_.*$", "", str((ln or {}).get("role") or "")), "caption_lines": None,
                   "cap_durs": None, "cap_lead": 0.0, "cap_offset": 0.0})
        t0 += dur
    return tl


def preview_lines(lines, pack, first_lines=()):
    """2단계 스토리보드 줄마다 '자동으로 들어갈 팩 소리'(관제 143 확장) — 배치 규칙은 plan_events 를 **그대로** 부른다(두 벌 금지).
    lines: [{"role","text"}] · pack: resolve() 결과(None 이면 전부 빈 목록=기본 효과음 없음)
    first_lines: 줄 효과음(짤·CTA)이 있는 줄 번호 — events 처럼 그 줄 첫 발을 비운다.
    lines 의 줄에 "pack_edit"(빼기·바꾸기 고름)이 있으면 렌더와 **같은 apply_pack_edit** 를 거친다(뺀 소리는 off 표시로 남김).
    돌려주는 것: 줄마다 [{"slot","label","t"(영상 기준 대략 초),"url","ref":{slot,n}, ["off"]|["from","from_label"]}].
    시각은 어림이라 화면은 '대략 위치'로 보인다."""
    out = [[] for _ in (lines or [])]
    if not pack or not pack.get("name"):
        return out
    nos = [n for n, _ in list_packs()]
    if pack["name"] not in nos:
        return out
    no = nos.index(pack["name"]) + 1
    tl = preview_timeline(lines)
    edits = {i: (ln or {}).get("pack_edit") for i, ln in enumerate(lines or []) if (ln or {}).get("pack_edit")}
    # 끈 줄(pack.mute_beats = deco.sfx_mute_beats, 2단계에선 줄 번호)은 렌더(events)와 같이 건너뛴다 → 빈 칩
    per = plan_per_beat(tl, (), pack.get("density") or "normal", first_lines, edits, keep_off=True,
                        mute_beats=pack.get("mute_beats") or ())
    for owner, evs in per.items():
        cnt = {}
        for slot, t, _, mark in evs:
            orig = mark["from"] if isinstance(mark, dict) else slot
            n = cnt.get(orig, 0); cnt[orig] = n + 1
            row = {"slot": slot, "label": SLOT_LABEL.get(slot, slot), "t": round(float(t), 1),
                   "url": "/api/produce/sfx_pack/sound/%d/%s" % (no, slot),
                   "ref": {"slot": orig, "n": n}}       # 화면이 빼기·바꾸기를 이 이름+순번으로 보낸다
            if mark == "off":
                row["off"] = True
            elif isinstance(mark, dict):
                row["from"] = orig
                row["from_label"] = SLOT_LABEL.get(orig, orig)
            out[owner].append(row)
    return out


def preview_pack(store, customer_id, roles, job=None, style_id=None, deco=None):
    """2단계용 팩 결정 — resolve 를 **그대로** 부른다. 3단계 job 이 있으면 그 job(꾸미기 선택 포함),
    없으면 작업 state 의 틀 번호(script_style_id)·줄 역할로 job 모양을 만들어 넘긴다(썰 판정도 resolve 몫).
    deco: 2단계 보드가 들고 있는 효과음 스위치({"sfx_pack": "auto"/"off", "sfx_mute_beats": [줄 번호]}) —
      확정 때 3단계 job deco 에 같은 키로 들어가는 값이다. job deco 위에 덮어 resolve 가 판단(판단 두 벌 금지)."""
    j = dict(job) if isinstance(job, dict) else {}
    if isinstance(deco, dict):
        _d = {k: deco[k] for k in ("sfx_pack", "sfx_mute_beats") if deco.get(k) not in (None, "")}
        if _d:
            j["deco"] = {**(j.get("deco") or {}), **_d}
    j["customer_id"] = int(customer_id or 0)
    if style_id is not None and not (j.get("script_structure") or {}).get("script_style_id"):
        j["script_structure"] = dict(j.get("script_structure") or {}, script_style_id=style_id)
    if not ((j.get("edit_plan") or {}).get("beats")):
        j["edit_plan"] = {"beats": [{"beat_idx": i, "role": re.sub(r"_.*$", "", str(r or ""))} for i, r in enumerate(roles or [])]}   # 2단계 칸 이름 'bait_1' → 'bait'(storyboard 관례)
    return resolve(store, j)
