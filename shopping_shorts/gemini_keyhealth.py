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
                "계속 유료로 쓰실 거면 AI Studio → Billing에서 충전하면 다시 살아나요. "
                "충전·수정하셨으면 설정 화면의 [전체 확인]을 눌러 주세요(안 누르셔도 하루 안에 자동으로 다시 확인돼요)."),
    },
    key_vault.UNUSABLE_SPEND_CAP: {
        "title": "월 지출 한도에 닿았어요",
        "fix": ("이 키의 프로젝트에 걸어둔 '월 지출 한도'를 다 써서 구글이 요청을 막고 있어요. "
                "결제가 연결된 유료 키라 쓰는 만큼 요금이 나가는 키예요 — 무료 키로 교체하시길 권해요. "
                "계속 쓰실 거면 AI Studio → Spend → Monthly spend cap에서 한도를 올려 주세요(반영까지 10분쯤). "
                "충전·수정하셨으면 설정 화면의 [전체 확인]을 눌러 주세요(안 누르셔도 하루 안에 자동으로 다시 확인돼요)."),
    },
    key_vault.UNUSABLE_NO_QUOTA: {
        "title": "구글 요청 한도가 0이에요",
        "fix": ("구글이 이 키가 속한 프로젝트의 요청 한도를 0으로 두고 있어 모든 요청이 거절돼요. "
                "기다려도 풀리지 않았어요. 새 프로젝트에서 키를 새로 만들어 교체해 주세요."),
    },
    key_vault.UNUSABLE_AUTH: {
        "title": "구글이 이 키를 거부해요",
        "fix": ("키가 삭제·비활성화됐거나 잘못된 값이에요. 새 키를 만들어 교체해 주세요. "
                "2026년 5월 28일 이전에 만든 옛 방식 키는 9월부터 구글이 받지 않아요. "
                "구글 쪽 문제가 풀렸다면 [전체 확인]을 눌러 주세요 — 살아 있으면 바로 돌아와요."),
    },
    # DB엔 'bad'인데 멈춘 이유 기록이 없는 키 — 옛 확인이 구글 붐빔(503·429)까지 '틀림'으로 찍었을 수
    # 있다(회원 603 실사고). '멈췄다'고 단정하지 않고 다시 확인을 부탁한다(반박 검토에서 발견).
    "recheck": {
        "title": "확인이 필요한 키예요",
        "fix": ("지난번 확인에 실패했어요(구글이 붐빌 때도 이렇게 될 수 있어요). 설정 화면의 [전체 확인]을 "
                "눌러 주세요 — 그래도 멈춤으로 나오면 새 키로 교체해 주세요."),
    },
}

# 등록 확인 때 구글이 붐비면(503·일반 429·응답 없음) — 키 잘못이 아니다. bad로 찍지 않는다.
BUSY_TEXT = ("구글이 지금 붐벼서 확인을 끝내지 못했어요. 키는 등록됐고, "
             "쓰면서 자동으로 다시 확인돼요. 잠시 뒤 [확인]을 다시 눌러 보셔도 돼요.")

# 예비 키 당부 — 설정 화면 제미니 칸과 사이드바 팝업이 함께 쓴다.
# ★공용 풀 구조대로 말한다(2026-09-25 반박 검토): 회원 작업은 자기 키가 아니라 **공용 묶음 전체**로 돈다.
#   그래서 "내 키가 막히면 내 작업이 끊긴다"는 틀린 말이다 — 키가 멈추면 묶음이 줄어 **모두가** 느려진다.
SPARE_KEY_TIP = ("등록하신 제미니 키는 모든 회원이 함께 쓰는 공용 키 묶음에 들어가요. 키가 멈추면 그만큼 "
                 "묶음이 줄어 모두의 작업이 느려지거나 실패할 수 있어요. 예비로 2~3개 등록해 두시면 하나가 "
                 "멈춰도 묶음이 버텨요. 구글 사용 한도는 키가 아니라 '프로젝트' 단위라, 같은 프로젝트에서 "
                 "만든 키는 함께 멈춰요 — 서로 다른 프로젝트에서 만든 키로 등록해 주세요. "
                 "결제를 연결하지 않은 무료 키로 등록해 주세요(유료 키는 쓰는 만큼 요금이 나가요). "
                 f"새 키: {AISTUDIO_KEY_URL} → Create API key")
# 팝업용 짧은 당부 — 휴대폰 화면에서 버튼이 잘리지 않게(반박 검토: 긴 본문에 [나중에]가 화면 밖으로).
SPARE_KEY_TIP_SHORT = ("예비로 2~3개, 서로 다른 프로젝트에서 만든 무료 키로 등록해 주세요. "
                       "자세한 방법은 설정 화면에 있어요.")

RECOMMENDED_KEYS = 2          # 문구의 '2~3개'와 짝 — 쓸 수 있는 키가 이보다 적으면 당부한다


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
            why = "recheck"          # 이유 기록 없는 bad — 옛 확인이 붐빔까지 bad로 찍었을 수 있다
        # 'paused'인데 정지 기록이 없으면 재시험·확인에서 살아난 것이다 — 쓸 수 있는 키로 친다.
        meta = REASONS.get(why)
        out.append({"id": kid, "label": r.get("label", ""), "status": st,
                    "reason": why or "",
                    "title": meta["title"] if meta else "",
                    "fix": meta["fix"] if meta else ""})
    n_bad = sum(1 for k in out if k["reason"])
    only_recheck = n_bad > 0 and all(k["reason"] in ("", "recheck") for k in out)
    n_off = sum(1 for k in out if k["status"] == "off")
    n_usable = len(out) - n_bad - n_off
    return {"keys": out, "n_total": len(out), "n_usable": max(0, n_usable), "n_bad": n_bad,
            "recommended": RECOMMENDED_KEYS, "tip": SPARE_KEY_TIP, "tip_short": SPARE_KEY_TIP_SHORT,
            "headline": (f"등록하신 제미니 키 {n_bad}개를 확인해 주세요" if only_recheck
                         else f"등록하신 제미니 키 {n_bad}개가 멈췄어요"),
            "has_dead": n_bad > 0,
            "few_keys": bool(out) and max(0, n_usable) < RECOMMENDED_KEYS}
