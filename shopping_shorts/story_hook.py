# -*- coding: utf-8 -*-
"""썰 대본 첫 줄(훅) — **꼴 은행 + 씨앗의 '홀린 요인' + 베끼기 판정 + 결정적 폴백**을 여기 한 곳에서(0순위-B).

왜(2026-09-26 사장님): 씨앗 첫 줄을 꼴로 주니 모델이 낱말 하나만 바꿔 돌려줬다
  ("개발자도 예상 못한 한국 주부의 활용법" → "개발자도 예상 못한 한국 주부의 **미친** 활용법").
  실측(09-25 감사): 한국어 씨앗 대본 71편 중 18편(25%)이 씨앗 첫 줄과 60%↑ 겹침, 7편은 그대로.
노바 작가 방식(docs/nova_writer_script_2026-09-22.md): 씨앗은 **홀린 요인**(누가 놀랐나·무엇이 컸나·발명품/활용법/정체)을
  뽑는 재료지 문장 재료가 아니다. 7줄 씨앗을 **다른 제목 틀**로 18줄로 다시 쓴다.

세 겹:
  ① 꼴은 은행에서(썰 스파인 문형 + 히트작 25편 첫 줄 실측) — 회원·작업 키로 **순번 회전**(회원 100명이 같은 첫 줄 금지)
  ② 빈칸은 씨앗의 홀린 요인(extract_feats가 함께 뽑는 hook 슬롯)으로 — 씨앗 문장이 아니라 씨앗 **내용**
  ③ 판정: 씨앗 첫 줄과 연속 겹침 60%↑(pickup_script.hook_copied와 같은 잣대) → 다른 꼴로 1회 재작성 → 그래도면
     **결정적 채움**(꼴+슬롯) — 구조상 씨앗 문장이 될 수 없어 안이 사라지는 길이 없다.
"""
import re
import zlib


# 슬롯 이름 = 스파인 문형(templates.title)이 쓰는 이름 그대로. extract_feats의 hook 필드가 채운다.
SLOT_KEYS = ("권위자", "대상", "나라", "제품군", "불편함", "장소", "계기")

# 썰 첫 줄 꼴 은행 — 썰 스파인 문형(승인 13개·2026-09-26 서버 실측) + 히트작 25편 첫 줄 실측(YT_BRIEF).
# ★{나라}는 재료에 나온 나라만(없으면 그 꼴은 건너뜀). 슬롯 없는 꼴은 늘 채울 수 있는 예비.
MOLDS_YT = (
    "{권위자}도 예상 못한 미친 활용법",
    "{권위자}도 전혀 몰랐던 미친 사용법",
    "{권위자}도 놀라버린 {제품군} 활용법",
    "{권위자}도 감탄한 천재 아이디어",
    "{권위자}도 감탄한 뜻밖의 활용법",
    "{권위자}도 당황한 천재 주부의 활용법",
    "{권위자} 직원도 몰래 쓰는 활용법",
    "{대상} 환장한 {나라} 천재의 발명품",
    "{대상} 환장하게 만든 발명품",
    "{대상} 구원한 {나라} 천재의 발명품",
    "{대상} 구원한 {제품군}의 정체",
    "{대상} 기립박수 치게 만든 제품",
    "{대상} 눈물 나게 만드는 꿀템",
    "{대상}이 더 많이 쓰는 {제품군}의 정체",
    "{나라} 천재가 만들어 떼돈 번 제품의 정체",
    "{나라} 천재가 만들어 돈방석 앉은 제품",
    "{나라} 개발자도 무릎 탁 친 천재적인 아이디어",
    "{나라} 천재가 만든 정신 나간 발명품",
    "{나라}도 당황한 천재 발명품",
    "{불편함} 싫은 {대상}이 찾아낸 해답",
    "{불편함}에 빡쳐서 탄생한 {나라} 천재의 발명품",
    "{불편함} 때문에 고생했으면 이거 보면 됨",
    "이제 {제품군} 이걸로 끝났음",
    "{장소}에서 난리난 {제품군}의 정체",
    "{장소} 가면 무조건 사야 되는 필수템",
    "{계기}에서 대박 터트린 {제품군}",
    "역발상으로 돈방석 앉은 {대상} 천재의 발명품",
    "만든 사람도 예상 못한 뜻밖의 활용법",
    "도대체 누가 시작한 건지 모르겠는 엉뚱한 활용법",
    "제조사도 감탄한 뜻밖의 활용법",
)

_SLOT_RE = re.compile(r"\{(%s)\}" % "|".join(SLOT_KEYS))


def slots_of(mold):
    return tuple(dict.fromkeys(_SLOT_RE.findall(mold)))


def clean_slots(raw):
    """모델이 준 hook 슬롯 값 정리 — 문자열만, 20자 이내, '없음/미상/unknown'은 빈칸."""
    out = {}
    for k in SLOT_KEYS:
        v = re.sub(r"\s+", " ", str((raw or {}).get(k) or "")).strip(" .「」\"'")
        if not v or len(v) > 20 or v.lower() in ("없음", "미상", "unknown", "none", "n/a", "-"):
            continue
        out[k] = v
    return out


def fill(mold, slots):
    """빈칸을 전부 채울 수 있으면 문장, 아니면 None."""
    try:
        need = slots_of(mold)
        if any(k not in slots for k in need):
            return None
        return re.sub(r"\s+", " ", mold.format(**{k: slots[k] for k in need})).strip()
    except (KeyError, IndexError, ValueError):
        return None


def first_line(text):
    return re.split(r"[.!?\n]", (text or "").strip())[0].strip()[:80]


COPY_MIN_RUN = 8        # 연속 일치 최소 글자(pickup_script와 같은 값)
COPY_RATIO = 0.6        # ★훅 길이 대비 — 씨앗 쪽 길이 기준(pickup_script)은 구두점 없는 343자 씨앗에서 60%=200자가 되어
                        #   "낱말 하나만 바꾼 훅"(19자 중 13자 연속 일치)을 못 잡았다(2026-09-26 실측). "훅의 60%가 씨앗의 한
                        #   토막을 그대로 옮긴 것인가"가 베끼기의 뜻이다.


def copied(hook, seed_text):
    """훅이 씨앗 본문의 한 토막을 그대로 옮겼나 — 훅(공백·구두점 제거) 글자의 60%↑가 씨앗 안에 **연속으로** 있으면 베낀 것."""
    from shopping_shorts import script_gate
    a, b = script_gate.norm(hook or ""), script_gate.norm((seed_text or "")[:600])
    if not a or not b:
        return False
    if a in b:
        return True
    import difflib
    m = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return m.size >= max(COPY_MIN_RUN, len(a) * COPY_RATIO)


def _shape(text):
    """문장의 꼴 — 낱말 뭉치를 OO로. 씨앗 첫 줄과 **같은 꼴**의 몰드는 피한다(낱말만 바꾸면 그 꼴 자체가 베낀 느낌)."""
    t = re.sub(r"[가-힣A-Za-z0-9]+(도|들|이|가|을|를|의)(\s|$)", lambda m: "OO" + m.group(1) + " ", text or "")
    return re.sub(r"\s+", " ", t).strip()


def candidates(slots, seed_text="", molds=MOLDS_YT):
    """지금 슬롯으로 채울 수 있고, 씨앗 첫 줄을 베끼지 않는 (몰드, 채운 문장) 목록 — 은행 순서대로."""
    seed_first = first_line(seed_text)
    seed_shape = _shape(seed_first)
    out = []
    for m in molds:
        f = fill(m, slots)
        if not f:
            continue
        if seed_first and (copied(f, seed_text) or _shape(f) == seed_shape):
            continue
        out.append((m, f))
    return out


def pick(slots, key, nth=0, seed_text="", molds=MOLDS_YT):
    """(몰드, 채운 문장) — 회원·작업 키로 회전(신호어 세트 _pick과 같은 규칙: 해시 + 순번). 후보 없으면 (None, None)."""
    cands = candidates(slots, seed_text, molds)
    if not cands:
        return None, None
    i = (zlib.crc32(str(key).encode("utf-8")) % len(cands) + int(nth)) % len(cands)
    return cands[i]


def instruction(mold, slots):
    """write() 프롬프트에 넣는 훅 지시 — 씨앗 문장은 절대 보여주지 않는다(보여주면 베낀다, 09-23 실측)."""
    need = slots_of(mold)
    vals = ", ".join("%s=%s" % (k, slots.get(k, "")) for k in need) or "빈칸 없음"
    return ("첫 줄(hook)은 이 꼴로 **새로** 쓴다: 「%s」 (빈칸: %s). 빈칸을 채운 뒤 낱말을 더 세게 골라도 되지만 "
            "꼴은 지켜라. 씨앗 영상의 첫 문장을 옮겨 쓰지 마라." % (mold, vals))


def resolve(hook, slots, key, nth, seed_text, molds=MOLDS_YT):
    """모델이 쓴 첫 줄을 판정한다 → (통과한 훅 | 결정적 채움, 사유).
    사유: "" 통과 · "copied→deterministic" 씨앗 베낌이라 채움으로 교체 · "empty→deterministic" 빈 훅."""
    h = re.sub(r"\s+", " ", hook or "").strip()
    if h and not copied(h, seed_text):
        return h, ""
    _, filled = pick(slots, key, nth, seed_text, molds)
    if filled:
        return filled, ("copied→deterministic" if h else "empty→deterministic")
    # 슬롯이 하나도 없어 채울 몰드가 없을 때 — 슬롯 없는 예비 꼴(은행 마지막 셋)
    for m in molds:
        if not slots_of(m):
            return m, ("copied→deterministic" if h else "empty→deterministic")
    return h, "copied(no-mold)"
