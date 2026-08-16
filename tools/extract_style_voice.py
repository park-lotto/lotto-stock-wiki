# -*- coding: utf-8 -*-
"""채널 히트작 전사 → **표현 사전**(말버릇)을 뽑아 spine.voice_json에 넣는다 (2026-08-17).

## 왜 표현 사전인가 — 사실과 표현을 가른다 (사장님 모델, 2026-08-16 확정)

    사실 = "녹는다"             ← 재료(대본·리뷰·상세페이지)에서 온다
    표현 = "사르르 / 퐁신퐁신"   ← 채널 말버릇. **스타일**이 갖는다. 어느 제품에나 쓴다
    결과 = "사르르 녹는데 퐁신퐁신해서"

합쳐진 완제품("입에서 사르르 녹는")을 **재료**로 주면 원본을 그대로 베낀다.
갈라 두면 원본에 없던 표현을 **새로 만들어** 쓴다.

3안 실측(계란+요거트 빵 3편 · 가족갈등 반전형):

    A 대본 통째(구 라이브) → 말버릇 4개(전부 원본에서 베낌) · 통과 · 383자
    B 사실만, 사전 없음    → 말버릇 1개 · 게이트 **실패**(고조) · 254자
    C 사실 + 표현사전      → 말버릇 **8개** · 통과 · **323자**  ← 채택

C만 원본에 없던 "퐁신퐁신·쫙"을 새로 만들었다. ★밀도 문제도 같이 풀렸다 —
억지로 늘린 게 아니라 말맛이 살면서 자연히 붙는다.

## 이 스크립트가 하는 일

    채널 username → channel_archive 조회수 상위 N편 → script_extracts의 전사 텍스트
      → 제미니 1회(채널당) → {onomatopoeia,intensifier,exclaim,endings,tone_note}
      → store.set_spine_style(spine_id, voice=...)

⚠️ **새 전사를 뜨지 않는다.** 이미 쌓인 전사만 쓴다(없으면 그 채널은 건너뛴다) —
   다운로드·전사는 비싸고, 스타일 시드는 이미 그 전사로 만들어졌다.
⚠️ 제미니 키는 서버에만 있다(`/etc/shopping-shorts.env`). 라이브 DB도 서버라
   **서버에서 실행하는 게 정상 경로**다.

실행:
    python3 tools/extract_style_voice.py --spine 52 --channel chae2home
    python3 tools/extract_style_voice.py --all          # 아래 STYLE_CHANNELS 전부
    python3 tools/extract_style_voice.py --all --dry     # 뽑아서 보여주기만(저장 안 함)
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402

# 라이브 스타일 ↔ 그 스타일을 뽑아낸 채널 (tools/seed_style_*.py 의 근거와 같은 짝).
# ★여기만 고치면 된다 — 스타일이 늘면 한 줄 추가.
STYLE_CHANNELS = [
    (52, "chae2home", "가족갈등 반전형"),
    (53, "homeditor_insta", "단정 명령형"),
    (54, "maison_homedino", "물건 발견형"),
]

TOP_N = 12          # 시드가 쓴 표본과 같은 수 — 근거를 갈라 두지 않는다
MAX_CHARS = 12000   # 프롬프트 상한(전사 12편이면 8~10천자 수준)

_SCHEMA = {
    "type": "object",
    "properties": {
        "onomatopoeia": {"type": "array", "items": {"type": "string"}},
        "intensifier": {"type": "array", "items": {"type": "string"}},
        "exclaim": {"type": "array", "items": {"type": "string"}},
        "endings": {"type": "array", "items": {"type": "string"}},
        "tone_note": {"type": "string"},
    },
    "required": ["onomatopoeia", "intensifier", "exclaim", "endings", "tone_note"],
}

_PROMPT = """아래는 한 채널의 히트작 대본 {n}편이다. 이 채널의 **말버릇**만 뽑아라.

★뽑는 것은 '표현'이지 '사실'이 아니다.
  - 뽑아라: "사르르"·"퐁신퐁신"·"진짜"·"~거 있죠?" 처럼 **어느 제품에나 쓸 수 있는 표현**
  - 뽑지 마라: "입에서 사르르 녹는 치즈" 처럼 **제품 사실이 섞인 완성 문구**
    (그건 다음 대본에 그대로 베끼게 된다 — 반드시 표현만 떼어내라)

- onomatopoeia: 의성어·의태어 (슥슥·쫙·퐁신퐁신 …)
- intensifier: 강조어 (진짜·완전·확·절대 …)
- exclaim: 감탄사 (와·헐 …)
- endings: 종결 말버릇 (~거 있죠?·~더라고요·~뻔했어요 …)
- tone_note: 이 채널 말투를 한 문장으로

각 배열은 **자주 나온 순서로 3~8개**. 한 번만 나온 표현은 말버릇이 아니니 빼라.

--- 대본 ---
{body}
"""


def _texts_for_channel(db_path, username, top_n=TOP_N):
    """그 채널 조회수 상위 N편 중 **이미 전사가 있는 것**의 본문. 없으면 빈 리스트."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT a.shortcode, e.script_json FROM channel_archive a "
            "JOIN script_extracts e ON e.shortcode = a.shortcode "
            "WHERE a.username = ? ORDER BY a.views DESC LIMIT ?",
            (username, top_n)).fetchall()
    finally:
        con.close()
    out = []
    for shortcode, raw in rows:
        try:
            d = json.loads(raw) if raw else {}
        except Exception:      # noqa: BLE001 — 깨진 행 하나로 전체를 죽이지 않는다
            continue
        # 전사는 저장 시점에 따라 full_text 또는 segments[].text 로 들어 있다(둘 다 실재).
        txt = (d.get("full_text") or "").strip()
        if not txt:
            txt = " ".join((s.get("text") or "").strip()
                           for s in (d.get("segments") or [])).strip()
        if txt:
            out.append((shortcode, txt))
    return out


def extract_voice(texts):
    """전사 목록 → 표현 사전 dict. 키가 없거나 실패하면 {} (호출부가 건너뛴다)."""
    from shopping_shorts import script_generate      # 키풀·모델을 한 곳에서만 정한다(0순위-B)
    body, used = [], 0
    for i, (_sc, txt) in enumerate(texts, 1):
        chunk = "[%d] %s" % (i, txt)
        if used + len(chunk) > MAX_CHARS:
            break
        body.append(chunk)
        used += len(chunk)
    if not body:
        return {}
    return script_generate._call_json(
        _PROMPT.format(n=len(body), body="\n\n".join(body)), _SCHEMA) or {}


def run_one(store, db_path, spine_id, username, label, dry=False):
    texts = _texts_for_channel(db_path, username)
    if not texts:
        print("  [건너뜀] %s — 쌓인 전사 0건 (새로 전사하지 않는다)" % username)
        return False
    voice = extract_voice(texts)
    if not voice or not any(voice.get(k) for k in ("onomatopoeia", "intensifier", "endings")):
        print("  [실패] %s — 표현 사전이 비어 돌아왔다(키 소진 또는 응답 오류)" % username)
        return False
    print("  전사 %d편 → %s" % (len(texts), json.dumps(voice, ensure_ascii=False)))
    if dry:
        print("  (dry — 저장 안 함)")
        return True
    store.set_spine_style(spine_id, voice=voice)
    print("  ✅ spine %d(%s)에 저장" % (spine_id, label))
    return True


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--spine", type=int)
    ap.add_argument("--channel")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)

    store = Store(DB_PATH)
    if a.all:
        targets = STYLE_CHANNELS
    elif a.spine and a.channel:
        targets = [(a.spine, a.channel, "")]
    else:
        ap.error("--all 또는 (--spine N --channel 아이디)")

    ok = 0
    for spine_id, username, label in targets:
        print("[%s] spine=%s" % (username, spine_id))
        if run_one(store, DB_PATH, spine_id, username, label, dry=a.dry):
            ok += 1
    print("\n완료 %d/%d" % (ok, len(targets)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
