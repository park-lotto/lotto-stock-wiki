# -*- coding: utf-8 -*-
"""회원 제미니 키 건강 — '쓸 수 없는 키' 안내와 '예비 키 등록' 당부의 **유일한 자리**(2026-09-25).

왜 생겼나: 공용 풀에 선불 소진(402)·월 지출 한도·할당량 0·무효 키가 섞여 잠금 0번으로 계속
불렸는데, 회원 설정 화면엔 전부 '● 정상'이었다. 회원은 자기 키가 죽은 줄 몰랐고, 402·월 한도는
**결제가 연결된 유료 키**라 공용 풀이 그 회원 돈으로 다른 회원 작업을 돌리고 있었다.

판정은 여기서 하지 않는다 — pipeline.atoms.key_vault(unusable_reason·정지 표시)가 유일한 판단처다.
여기는 그 판정을 **회원 말로 옮기는 곳**이다. 설정 화면·등록 확인·안내 배너가 전부 이 문구를 쓴다
(문구가 두 곳에 있으면 한쪽만 고쳐진다 — 0순위-B).

문구 근거(구글 공식 문서, 2026-09-25 확인):
  - 한도는 키가 아니라 **프로젝트** 단위다(ai.google.dev/gemini-api/docs/rate-limits:
    "Rate limits are applied per project, not per API key.") → 같은 프로젝트의 키 여러 개는 함께 멈춘다
  - 402 = 선불 잔액 0, 충전 전까지 재시도해도 안 된다(docs/billing#prepay, docs/api-errors)
  - 월 지출 한도 = 프로젝트에 걸어둔 한도, AI Studio Spend에서 올린다(docs/billing#project-spend-caps)
  - 2026-05-28 이전 발급 옛 방식(standard) 키는 2026년 9월부터 거절된다(docs/api-key#api-key-types)
  ⚠️"다른 구글 계정을 여러 개 만드세요"는 쓰지 않는다 — 문서 근거가 없고 약관(한도 우회 금지)과
    가장 가깝게 읽힌다. '예비 키로 끊김 방지'까지만 말한다.
"""
import sys

from pipeline.atoms import key_vault

AISTUDIO_KEY_URL = "https://aistudio.google.com/apikey"

# 이유별 안내. title = 짧은 상태, fix = 무엇을 하면 되나(쉬운 말).
REASONS = {
    key_vault.UNUSABLE_PREPAY: {
        "title": "선불 잔액이 다 떨어졌어요",
        "fix": ("이 키의 구글 결제 계정에 선불 크레딧이 0이라 구글이 요청을 막고 있어요(오류 402). "
                "기다려도 풀리지 않아요. 결제가 연결된 유료 키라 쓰는 만큼 요금이 나가는 키예요 — "
                "결제를 연결하지 않은 새 프로젝트에서 무료 키를 만들어 교체해 주세요. "
                "계속 유료로 쓰실 거면 AI Studio → Billing에서 충전하면 다시 살아나요."),
    },
    key_vault.UNUSABLE_SPEND_CAP: {
        "title": "월 지출 한도에 닿았어요",
        "fix": ("이 키의 프로젝트에 걸어둔 '월 지출 한도'를 다 써서 구글이 요청을 막고 있어요. "
                "결제가 연결된 유료 키라 쓰는 만큼 요금이 나가는 키예요 — 무료 키로 교체하시길 권해요. "
                "계속 쓰실 거면 AI Studio → Spend → Monthly spend cap에서 한도를 올려 주세요(반영까지 10분쯤)."),
    },
    key_vault.UNUSABLE_NO_QUOTA: {
        "title": "구글 요청 한도가 0이에요",
        "fix": ("구글이 이 키가 속한 프로젝트의 요청 한도를 0으로 두고 있어 모든 요청이 거절돼요. "
                "기다려도 풀리지 않았어요. 새 프로젝트에서 키를 새로 만들어 교체해 주세요."),
    },
    key_vault.UNUSABLE_AUTH: {
        "title": "구글이 이 키를 거부해요",
        "fix": ("키가 삭제·비활성화됐거나 잘못된 값이에요. 새 키를 만들어 교체해 주세요. "
                "2026년 5월 28일 이전에 만든 옛 방식 키는 9월부터 구글이 받지 않아요."),
    },
}

# 등록 확인 때 구글이 붐비면(503·일반 429·응답 없음) — 키 잘못이 아니다. bad로 찍지 않는다.
BUSY_TEXT = ("구글이 지금 붐벼서 확인을 끝내지 못했어요. 키는 등록됐고, "
             "쓰면서 자동으로 다시 확인돼요. 잠시 뒤 [확인]을 다시 눌러 보셔도 돼요.")

# 예비 키 당부 — 설정 화면 제미니 칸과 '키가 죽었다' 배너에 함께 쓴다.
SPARE_KEY_TIP = ("제미니 키는 예비로 2~3개 등록해 두시길 권해요. 키가 하나뿐이면 그 키가 막히는 순간 "
                 "작업이 끊길 수 있어요. 구글 사용 한도는 키가 아니라 '프로젝트' 단위라, 같은 프로젝트에서 "
                 "만든 키는 함께 멈춰요 — 서로 다른 프로젝트에서 만든 키로 등록해 주세요. "
                 "결제를 연결하지 않은 무료 키로 등록해 주세요(유료 키는 쓰는 만큼 요금이 나가요). "
                 f"새 키: {AISTUDIO_KEY_URL} → Create API key")

RECOMMENDED_KEYS = 3


def explain(reason: str) -> str:
    """등록 확인 실패 사유 한 줄(제목 + 해결법). 모르는 이유면 빈 문자열."""
    r = REASONS.get(reason)
    return f"{r['title']} — {r['fix']}" if r else ""


def member_key_health(store, customer_id) -> dict:
    """회원 한 명의 제미니 키 상태 — 설정 화면·배너가 이것 하나만 본다.

    반환: {"keys": [{id, label, status, reason, title, fix}], "n_total", "n_usable",
           "n_bad", "recommended", "tip", "has_dead", "few_keys"}
      - reason은 key_vault 상태파일(정지·영구 사망)에서 온다. 없고 status가 'bad'면 'bad'.
      - has_dead = 쓸 수 없는 키가 하나라도 있다 → 강한 안내(교체 요청)
      - few_keys = 키를 등록했는데 쓸 수 있는 키가 권장 수보다 적다 → 부드러운 당부
        (키를 하나도 안 낸 회원에겐 띄우지 않는다 — 그 회원은 포인트로 쓰는 쪽이다)
    """
    rows = []
    try:
        rows = [r for r in store.list_customer_keys(customer_id, "gemini")]
    except Exception:                       # noqa: BLE001 — 화면이 죽으면 안 된다
        rows = []
    hashes = {}
    try:
        with store._conn() as c:
            for kid, kh in c.execute(
                    "SELECT id, key_hash FROM customer_keys WHERE customer_id=? AND service='gemini'",
                    (int(customer_id),)).fetchall():
                if kh:
                    hashes[int(kid)] = kh
    except Exception as e:                  # noqa: BLE001 — 지문을 못 읽으면 정지 표시만 못 붙인다
        print(f"[keyhealth] key_hash 조회 실패(무해): {e!r}", file=sys.stderr)
    try:
        info = key_vault.unusable_info_for(set(hashes.values()))
    except Exception:                       # noqa: BLE001
        info = {}
    out = []
    for r in rows:
        kid = int(r.get("id") or 0)
        st = (r.get("status") or "").strip()
        why = (info.get(hashes.get(kid, "")) or {}).get("reason")
        if not why and st == "bad":
            why = "bad"
        meta = REASONS.get(why) or ({"title": "확인에 실패한 키예요",
                                      "fix": "키 값을 다시 확인하시거나 새 키로 교체해 주세요."}
                                     if why == "bad" else None)
        out.append({"id": kid, "label": r.get("label", ""), "status": st,
                    "reason": why or "",
                    "title": meta["title"] if meta else "",
                    "fix": meta["fix"] if meta else ""})
    n_bad = sum(1 for k in out if k["reason"])
    n_off = sum(1 for k in out if k["status"] == "off")
    n_usable = len(out) - n_bad - n_off
    return {"keys": out, "n_total": len(out), "n_usable": max(0, n_usable), "n_bad": n_bad,
            "recommended": RECOMMENDED_KEYS, "tip": SPARE_KEY_TIP,
            "has_dead": n_bad > 0,
            "few_keys": bool(out) and max(0, n_usable) < RECOMMENDED_KEYS}
