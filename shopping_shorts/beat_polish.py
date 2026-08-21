# -*- coding: utf-8 -*-
"""조립 대본 다듬기 — 틀은 조립이 잡고, 문장은 모델이 쓴다.

## 왜 필요한가 (2026-08-21 사장님 제보)

조립(`spine_fill.fill`)은 구조·순서·재료 근거를 보장한다. 그런데 **문장이 어색하다.**
뿌리는 하나다 — 빈칸에 들어오는 값의 형태가 제각각인데 템플릿 뒷말은 하나로 고정이다.

    템플릿: "저도 해보니까 진짜 {효과} 거 있죠"
      {효과} = "불꽃이 올라오는"        → "…진짜 불꽃이 올라오는 거 있죠"   ✅ 맞물림
      {효과} = "정리할 수 있다"          → "…진짜 정리할 수 있다 거 있죠"    ❌ 깨짐

템플릿을 고쳐도, 어미를 통일해도 다른 영상에서 또 깨진다. **재료 형태에 계약이 없기
때문**이다. 사장님 제보: "템플릿 전(=생성기)이 오히려 대본이 잘 나온 것 같다" —
재료가 잘 뽑힐수록 조립으로 가는데, 정작 조립이 문장은 더 나쁘다는 역설이었다.

## 그래서 각자 잘하는 것을 시킨다

    조립  → 구조·순서·재료 근거 (틀은 절대 안 흔들린다)
    모델  → 문장 (조사·어미·연결을 자연스럽게)
    검사  → 칸 수·수치·빈칸 잔존·길이. 어기면 **그 줄은 조립 원본을 쓴다**

★모델 결과를 그냥 믿지 않는다. 검사에 걸리면 원본으로 되돌린다(fail-safe).
  모델이 죽어도 대본은 그대로 나온다 — 다듬기 실패가 제작을 막으면 안 된다.
★어느 쪽으로 갔는지 반드시 남긴다(`note`). 조용한 폴백이 쳇바퀴의 뿌리였다
  (memory: reference_silent_fallback_pipeline_undo).
"""
import re

SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
    "required": ["lines"],
}

# 수치·단위 — 다듬다가 사라지거나 새로 생기면 그 줄은 버린다(지어내기 차단).
_NUM_RE = re.compile(
    r"\d[\d,.]*\s*(?:%|원|만원|배|개|초|분|시간|일|주|개월|년|kg|g|ml|L|cm|mm|m)?"
)

_PROMPT = """너는 한국 숏폼(릴스·쇼츠) 대본 교정자다.
아래 대본은 정해진 틀에 재료를 끼워 만든 것이라, 뜻은 맞지만 조사·어미가 어긋나
어색하게 읽히는 줄이 섞여 있다. **말로 읽었을 때 자연스럽게** 다듬어라.

[반드시 지킬 것]
· 줄 개수와 순서를 그대로 둔다. 합치거나 나누거나 새 줄을 만들지 마라.
· 각 줄의 **뜻을 바꾸지 마라**. 없는 내용을 지어내지 마라.
· 숫자·가격·수치·제품 이름은 **글자 그대로** 남긴다.
· 말투는 그 줄의 말투를 따른다(원본이 '~요'면 '~요', '~음'이면 '~음').
· 이미 자연스러운 줄은 **그대로 두어라**.
· 길이를 크게 늘리지 마라.

[특히 잘 볼 것 — 틀에 값을 끼우다 생긴 자국이다]
· 관형형이 갈 곳을 잃고 떠 있는 경우
  (예: "바람을 막는 방풍 기능이 있는, 그거였더라고요"
   → "알고 보니 바람을 막아주는 방풍 기능이 있더라고요")
· 명사형과 서술어가 부딞히는 경우("당기기, 그러면 끝")
· 조사가 중복되거나 빠진 경우, 문장이 중간에서 끊긴 경우
이런 줄은 반드시 고쳐라. 어색한데 그대로 두면 그게 제일 나쁘다.

[대본]
{body}

lines 배열로만 답하라."""


def polish(beats, spine_name=""):
    """조립 beats → (다듬은 beats, 무슨 일이 있었는지 한 줄).

    beats = [{"role":..., "text":...}] — 모양은 그대로 돌려준다.
    """
    if not beats:
        return beats, ""
    olds = [str(b.get("text") or "") for b in beats]
    try:
        from shopping_shorts.edit_plan import _vault_call
    except Exception:  # noqa: BLE001 — 다듬기 실패가 대본을 막지 않는다
        return beats, "다듬기 건너뜀(모듈 없음)"

    body = "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(olds))
    raw = _vault_call(_PROMPT.format(body=body), SCHEMA)
    got = (raw or {}).get("lines") if isinstance(raw, dict) else None
    if not got:
        return beats, "다듬기 건너뜀(모델 응답 없음)"
    if len(got) != len(olds):
        return beats, "다듬기 버림(줄 수가 %d→%d로 달라짐)" % (len(olds), len(got))

    out, changed, dropped = [], 0, 0
    for b, old, new in zip(beats, olds, got):
        new = re.sub(r"\s+", " ", str(new or "")).strip()
        text = old
        if new and new != old:
            why = _reject(old, new)
            if why:
                dropped += 1
            else:
                text = new
                changed += 1
        nb = dict(b)
        nb["text"] = text
        out.append(nb)

    if not changed:
        return out, "다듬기 결과 없음(원본 유지)"
    note = "%d줄 다듬음" % changed
    if dropped:
        note += " / %d줄은 검사에 걸려 원본 유지" % dropped
    return out, note


def _reject(old, new):
    """이 교정을 버려야 하나 → 이유 문자열(쓸 만하면 '')."""
    if "{" in new or "}" in new:
        return "빈칸이 남음"
    if sorted(_NUM_RE.findall(old)) != sorted(_NUM_RE.findall(new)):
        return "수치가 바뀜"
    if len(new) > len(old) * 1.35 + 6:
        return "너무 길어짐"
    if len(new) < len(old) * 0.55:
        return "너무 짧아짐"
    return ""
