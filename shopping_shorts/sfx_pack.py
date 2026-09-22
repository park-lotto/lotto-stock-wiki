# -*- coding: utf-8 -*-
"""썰채널 효과음팩 자동배치 (2026-09-22, 이븐쇼핑 12편 실측 규칙).

실측 원문: 바탕화면 `이븐쇼핑_효과음_벤치마크/이븐쇼핑_효과음_규칙_분석.md` · 도구 `tools/sfx_bench/`.

★기준점은 컷이 아니라 **자막 한 줄이 바뀌는 순간**이다(휙·둥·띠링 93~94%, 우연 16%).
  그래서 시각은 렌더가 자막을 띄우는 함수(video_assemble.caption_schedule)에서 **그대로** 받는다.
  따로 계산하면 자막과 어긋난다(0순위-B). 회원이 자막을 쪼개거나 합쳐도 소리가 따라간다.

규칙(12편 실측):
  영상 시작 0.06초       오프너 1발 (12/12). 제목 칸 안에서는 다른 소리 없음.
  첫 칸 → 둘째 칸 넘김   휙(넘김 0.035초 전) + 틱(0.07초 뒤)  (틱 12/12, 휙 8/12)
  그 뒤 자막 줄 교체마다  문구가 소리를 정한다:
      둥   반전·강조("충격적인", "말도 안 되는", "근데 이걸", "진짜는", "종결급")
      띠링 결과·감탄("변신", "끝판왕", "99.9%", "해결" …) · 마지막 칸 첫 줄
      뽁   동작(action_dict — 넣어/발라/잘라 …)
      딸깍딸깍 시연 넘김 일부(실측 8%)
      휙   나머지 기본값
  밀도  초당 약 1.1발(이븐쇼핑 실측). 넘치면 **휙부터** 고르게 뺀다(둥·띠링·뽁은 남긴다).

회원마다 팩 하나를 고정 배정한다(20종, 두 팩 사이 7칸 중 최소 4칸 다름) — 회원끼리 소리가 달라진다.
켜는 조건: 관리자 설정 sfx_pack_enabled=1 **그리고** 썰쇼핑 계열 채널 틀을 쓴 영상.
"""
import os
import re
import zlib

PACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sfx_packs")
SLOTS = ("opener", "pop", "dung", "ding", "whoosh", "tick", "click2")

OPENER_AT = 0.06          # 실측: 12편 전부 0.03~0.07초
WHOOSH_LEAD = 0.035       # 첫 넘김: 휙이 넘김보다 먼저(8편 중앙)
TICK_LAG = 0.07           # 첫 넘김: 틱이 넘김보다 뒤(12편 중앙)
TARGET_PER_SEC = 1.1      # 실측 밀도(떡밥 1.19 · 시연 1.23 · 반전 1.12 · 마무리 1.06)
CLICK2_EVERY = 12         # 기본값(휙) 자리 중 이 간격마다 딸깍딸깍(실측 시연 8%)
# 팩 소리 보정(배) — 실렌더에서 목소리 대비 크기를 이븐쇼핑과 맞춘 값(tools/sfx_bench/render_check.py).
#   기본 효과음 볼륨 60%만으로는 이븐쇼핑보다 약 8dB 작았다(휙 -10.6 vs -2.7dB). 7.0으로 올리니 7종 모두
#   +2.4~2.8dB 컸다(나레이션 차감 잔여로 잰 값) → 4.3.
PACK_GAIN_DB = 4.3

_DUNG = re.compile(r"충격|말도\s*안|근데\s*이걸|근데\s*진짜|진짜는|종결급|반전")
_DING = re.compile(r"변신|끝판왕|완벽|원상\s*복구|뚝딱|해결|99|%|새\s*(것|걸|거)|반짝|야무지|대박|떼돈|돈방석|"
                   r"매출|폭등|품절|난리|역대급|환장|감탄")
# 동작(뽁) 보충 — 공용 action_dict에 없는데 이븐쇼핑 시연 자막에 뽁이 붙은 동사(실측 문구 예:
#   "페이퍼로 칼을 감싸", "한쪽을 꺾어주면", "흔들어주면"). action_dict는 다른 기능도 쓰는
#   통제어휘라 여기서만 보탠다.
_POP_EXTRA = re.compile(r"감싸|꺾|흔들|달아|걸어|띄워|말아|쌓|집어|꽂아|돌리|채워|갈아|털어")


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


def pack_for(customer_id, override=None):
    """회원 → 팩 (이름, 폴더). override(1부터)가 있으면 그 팩. 팩이 없으면 None.
    crc32라 파이썬 hash()처럼 프로세스마다 바뀌지 않는다 — 미리보기와 최종본이 같은 팩을 쓴다."""
    packs = list_packs()
    if not packs:
        return None
    try:
        if override is not None and str(override).strip() not in ("", "auto"):
            i = int(override) - 1
            if 0 <= i < len(packs):
                return packs[i]
    except (TypeError, ValueError):
        pass
    return packs[zlib.crc32(str(customer_id or 0).encode()) % len(packs)]


def is_sul_deco(deco):
    """이 영상이 썰쇼핑 계열 채널 틀을 쓰는가.

    장면꾸미기 틀은 두 화면 모두 유튜브 썰쇼핑 계열이다(app.py 프리셋 목록 주석:
    "현재 장면꾸미기 채널 틀은 전부 유튜브 썰쇼핑 계열"). 새 편집기=deco.scene_style,
    옛 피팅룸=deco.template.frame. 틀에 copy_family가 따로 박혀 있고 유튜브 계열이 아니면 뺀다
    (인스타 틀이 추가될 때를 대비 — 그때 이 값만 보면 된다).
    """
    if not isinstance(deco, dict):
        return False
    if deco.get("scene_style"):
        return True
    frame = (deco.get("template") or {}).get("frame") if isinstance(deco.get("template"), dict) else None
    if not isinstance(frame, dict) or not frame:
        return False
    try:
        from shopping_shorts import deco_frame
        p = deco_frame.PRESETS.get(frame.get("preset") or deco_frame.DEFAULTS["preset"]) or {}
        return p.get("copy_family", "youtube_reveal") == "youtube_reveal"
    except Exception:      # noqa: BLE001 — 판정 실패는 '끔'으로(조용히 켜지지 않게)
        return False


def resolve(store, job):
    """이 job에 쓸 팩 {"name","dir"} 또는 None. 렌더·미리보기·캡컷이 전부 여기 하나를 거친다."""
    if not job:
        return None
    deco = job.get("deco") or {}
    choice = deco.get("sfx_pack") if isinstance(deco, dict) else None
    if choice == "off":
        return None
    try:
        if str(store.get_setting("sfx_pack_enabled", "") or "") != "1":
            return None
    except Exception:      # noqa: BLE001
        return None
    if not is_sul_deco(deco):
        return None
    got = pack_for(job.get("customer_id", 0), override=choice)
    return {"name": got[0], "dir": got[1]} if got else None


def classify(text):
    """자막 한 줄 → 칸 이름(dung/ding/pop) 또는 None(=기본값 자리)."""
    t = text or ""
    if _DUNG.search(t):
        return "dung"
    if _DING.search(t):
        return "ding"
    if _POP_EXTRA.search(t):
        return "pop"
    try:
        from shopping_shorts.action_dict import tag_action
        if tag_action(t):
            return "pop"
    except Exception:      # noqa: BLE001
        pass
    return None


def plan_events(timeline, manual_beats=()):
    """[(칸, 절대초, 문구)] — 파일 경로 없이 '무엇을 언제'만. 테스트·검증이 이걸 본다.

    timeline: video_assemble._beat_timeline 결과. manual_beats: 사람이 고른 효과음이 있는
    비트 번호 — 그 비트 안에는 팩 소리를 넣지 않는다(사람이 고른 것이 이긴다).
    """
    from shopping_shorts.video_assemble import caption_schedule
    tl = [b for b in (timeline or []) if float(b.get("dur") or 0) > 0]
    if not tl:
        return []
    manual = set(manual_beats or ())
    total = sum(float(b["dur"]) for b in tl)
    ev = [("opener", OPENER_AT, "")]
    if len(tl) >= 2 and tl[1]["beat_idx"] not in manual:
        t = float(tl[1]["t0"])
        ev += [("whoosh", max(0.0, t - WHOOSH_LEAD), ""), ("tick", t + TICK_LAG, "")]
    last_idx = tl[-1]["beat_idx"]
    body = []           # (칸 또는 None, 시각, 문구, 비트)
    for bi, b in enumerate(tl):
        if bi == 0 or b["beat_idx"] in manual:
            continue    # 제목 칸 안은 오프너만(실측 12/12)
        sched = caption_schedule(b)
        for k, (seg, start, _end) in enumerate(sched):
            if bi == 1 and k == 0:
                continue    # 첫 넘김은 휙+틱이 이미 맡았다
            slot = classify(seg)
            if slot is None and b["beat_idx"] == last_idx and k == 0:
                slot = "ding"   # 마무리 칸 첫 줄
            body.append([slot, start, seg])
    # 기본값(휙) 자리 중 일부를 딸깍딸깍으로 — 결정적(같은 대본이면 같은 결과)
    d = 0
    for row in body:
        if row[0] is None:
            d += 1
            row[0] = "click2" if d % CLICK2_EVERY == CLICK2_EVERY // 2 else "whoosh"
    # 밀도 맞추기: 초당 TARGET_PER_SEC를 넘으면 휙을 고르게 뺀다
    budget = int(round(TARGET_PER_SEC * max(0.0, total - float(tl[0]["dur"]))))
    fixed = len(ev) + sum(1 for r in body if r[0] != "whoosh")
    whooshes = [i for i, r in enumerate(body) if r[0] == "whoosh"]
    keep_n = max(0, budget - fixed)
    if len(whooshes) > keep_n:
        drop = len(whooshes) - keep_n
        step = len(whooshes) / drop
        gone = {whooshes[int(j * step + step / 2) % len(whooshes)] for j in range(drop)}
        body = [r for i, r in enumerate(body) if i not in gone]
    ev += [(r[0], r[1], r[2]) for r in body]
    ev = [e for e in ev if e[1] < total]
    ev.sort(key=lambda e: e[1])
    return ev


def events(timeline, pack, manual_beats=()):
    """[(경로, 절대초, 보정배)] — sfx_events_for가 부른다. pack: resolve()의 결과.
    세 번째 칸(보정배)은 렌더·캡컷이 효과음 볼륨에 곱한다(없으면 1.0 — 종전 이벤트와 호환)."""
    if not pack or not pack.get("dir"):
        return []
    g = round(10 ** (PACK_GAIN_DB / 20), 4)
    return [(os.path.join(pack["dir"], slot + ".wav"), t, g) for slot, t, _ in plan_events(timeline, manual_beats)]
