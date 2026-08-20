# -*- coding: utf-8 -*-
"""다이소형 템플릿 조립 시험 — **모델 호출 0회**라 로컬에서 돈다.

슬롯 값은 서버 실측(insta_facts_probe, 욕실세정제 5편)에서 그대로 가져왔다.
템플릿을 고치고 이 파일을 돌려 조립 결과를 눈으로 본 뒤 확정한다.

실행: python tools/script_lab/daiso_assemble_probe.py
"""
import io
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))

from shopping_shorts import spine_fill                       # noqa: E402
from tools.script_lab.daiso_spine import DAISO_INSIDER       # noqa: E402

# ── 서버 실측값 (2026-08-19, 욕실세정제 5편 합본) ─────────────────────────
SLOTS_BATH = {
    "사용법": "욕실에 칙칙 뿌리고 물로 싹 뿌려주기",
    "적용대상": "욕실 수전 물때",
    "적용대상2": "오래된 욕실 곰팡이",
    "적용대상들": "욕실 수전 물때부터 안 지워지던 곰팡이까지",
    "효과": "완전 새 것처럼 닦이는",
    "수치": "5분",
    "차별점": "다이소 욕실 청소 세제 판매 1위 제품",
    "불편함": "아무리 닦아도 안 지워지던 곰팡이",
    "가격": "단돈 몇 천 원",
}
# 재료가 덜 찬 경우 — 슬롯이 적은 변형이 걸리는지 본다(pick_template 규약 확인).
SLOTS_THIN = {"사용법": "물에 한 스푼 풀어 담가두기",
              "적용대상": "누렇게 변한 흰 양말",
              "효과": "누런 때가 싹 빠지는"}


# ── 중국(샤오홍슈) 수전선반 3편 실측 (2026-08-19) — numbers·price가 안 나온다 ──
SLOTS_CN = {
    "사용법": "수전 뒤편에 그대로 끼워 설치하기",
    "적용대상": "어질러진 세면대 위 각종 병들",
    "적용대상2": "자주 쓰는 세안 용품",
    "적용대상들": "어질러진 세면대 위 각종 병들부터 양치용 컵까지",
    "효과": "복잡했던 세면대가 깔끔해지는",
    "차별점": "구멍을 뚫거나 접착할 필요 없는 방식",
    "불편함": "매번 물건들이 뒤엉켜 지저분해 보이는 세면대",
}


def _hangul(s):
    return len(re.sub(r"[^가-힣0-9]", "", s))


_DRAFTS = []


def show(name, spine, slots):
    """조립 결과를 화면에 찍고, **gen.py와 같은 모양**으로 모아둔다.
    새 뷰어를 만들지 않고 기존 build.py를 그대로 쓰기 위함이다(0순위-B: 보는 법을 두 벌 만들지 마라)."""
    beats, missing = spine_fill.fill(spine, slots)
    full = " ".join(b["text"] for b in beats)
    print("\n" + "=" * 72)
    print("[%s]  칸 %d/%d  ·  %d자" % (name, len(beats), len(spine["beat_roles"]), _hangul(full)))
    for b in beats:
        print("  [%-8s] %s" % (b["role"], b["text"]))
    if missing:
        print("  ⚠️ 못 채운 칸: %s  ← 이 칸만 모델에 맡긴다" % ", ".join(missing))
    _DRAFTS.append({
        "style_id": spine["id"], "style_name": name,
        "source": "슬롯 조립(모델 호출 0회)",
        "beats": beats, "full_text": full,
        "checks": [
            {"name": "칸 채움", "ok": not missing,
             "detail": "%d/%d칸%s" % (len(beats), len(spine["beat_roles"]),
                                      (" · 못 채운 칸: " + ", ".join(missing)) if missing else "")},
            {"name": "말 밀도", "ok": True,
             "detail": "%d자 (이 스타일 히트작 %d자/30초 → 약 %.0f초)"
                       % (_hangul(full), spine["chars_per_30s"],
                          _hangul(full) / spine["chars_per_30s"] * 30)},
            {"name": "쓴 슬롯", "ok": True, "detail": " · ".join("{%s}=%s" % (k, v) for k, v in slots.items())},
        ],
        "passed": not missing, "tries": [], "error": "", "sec": 0.0, "prompt": "",
    })


def main():
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stdout = out
    show("다이소 내부인형 · 재료 가득(욕실세정제 5편)", DAISO_INSIDER, SLOTS_BATH)
    show("다이소 내부인형 · 재료 부족(3종만)", DAISO_INSIDER, SLOTS_THIN)
    show("★중국 샤오홍슈 수전선반 3편", DAISO_INSIDER, SLOTS_CN)

    import json
    import time
    out_dir = BASE / "tools" / "script_lab" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    # ★파일명은 gen.py와 같은 정수 타임스탬프 — build.py가 최신 것을 고를 수 있어야 한다.
    path = out_dir / ("%d.json" % int(time.time()))
    path.write_text(json.dumps(
        {"topic": "다이소형 슬롯 조립 (모델 호출 0회)",
         "facts": "재료는 insta_facts가 영상 전사에서 뽑은 것 — 쿠팡 안 씀",
         "seconds": 25, "drafts": _DRAFTS}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n저장: %s" % path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
