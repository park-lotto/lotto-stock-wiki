# -*- coding: utf-8 -*-
"""원샷링크딸깍(사장님 2026-10-18 이름) — 엔진 대본 → 작품 폴더(정본 제작기 material_auto·preset_make 가 읽는 꼴).

    PYTHONUTF8=1 py tools/calcopy/oneshot/to_work.py <엔진 대본.json> <조사.json> 잇썸홈|재미썸홈 <작품 폴더>

판단 주인(여기서 새로 정하지 않고 부르기만):
  자막 조각 = tools/calcopy/narr_video.chunk_sentence(13자) · TTS 숫자 읽기 = shopping_shorts.narration_naturalize.normalize_reading
  장면 검색어(조각마다 query·kind) = 이 파일 shot_queries() 한 곳 — 제미나이 1회(gemini_free.ask)
  채널 값(프리셋·목소리·말속도·재료 규칙) = BRANDS 한 곳(10-17 작품 1~5 대본.json 값 그대로)
작품 대본.json 꼴 = 10-17 확정 대본(lines[].shots[].piece) — material_auto.norm_script 세 번째 꼴.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PIECE_CHARS = 13          # 잇썸홈 자막 한 칸 ≤13자(10-17 확정 대본 규칙)
BRANDS = {
    "잇썸홈": {"channel": "homedesignnote", "preset": "channel/homedesignnote/preset/전체화면_가운데자막",
             "voice": {"name": "박창수", "voice_id": "tc_6059dad0b83880769a50502f"}, "cps_target": 8.32,
             "재료_규칙": "재료 = 같은 제품 실영상만(짤·유사 0)", "kinds": ["제품"], "sfx": 0, "meme": 0},
    "재미썸홈": {"channel": "재미썸홈", "preset": "channel/evenshopping/preset/숏템템플릿/manifest.json",
              "voice": {"name": "필재", "voice_id": "tc_68257f68bc6e3c161ab5078d"}, "cps_target": 8.8,
              "재료_규칙": "재료 = 제품 실영상 + 유사·연상 영상 + 짤", "kinds": ["제품", "유사", "짤"],
              "sfx": "shopping_shorts/sfx_pack density=low", "bgm": None},
}

SHOT_PROMPT = """너는 쇼츠 영상 편집자다. 나레이션 자막 조각마다 화면에 깔 영상을 유튜브에서 찾을 **영어 검색어**를 정한다.
제품: {product}
제품 영상 검색어 예(조사): {queries}
채널 규칙: {rule}. 조각 종류(kind)는 {kinds} 중에서만.
- 원칙(사장님): 장면과 대사가 맞는 게 핵심 — 조각의 명사·동작이 화면에 그대로 보이게(예: '알람 끄고' → 'turning off alarm clock in bed').
- kind=제품: 그 제품이 나오는 실사용·리뷰·언박싱 장면 검색어(제품명 영어 포함). kind=유사: 말 내용을 보여주는 연상 장면(제품 아님). kind=짤: 감정 반응 짤.
- 이웃 조각은 검색어가 달라야 한다. 제목 줄(첫 줄)은 제품이 보이는 장면으로.
조각(번호: 줄번호 | 조각 | 그 줄 전체):
{pieces}
출력 JSON만: {{"shots":[{{"i":번호,"query":"영어 검색어","kind":"제품|유사|짤"}}, …]{title_req}}}"""


def shot_queries(product: str, research: dict, brand: str, rows: list[dict], title_line: str) -> dict:
    """(판단 주인) 조각마다 장면 검색어·종류 + 재미썸홈이면 제목 칸 2줄. 실패하면 멈춘다(조용히 빈 검색어로 넘기지 않는다)."""
    from tools.calcopy.engine import gemini_free as G
    B = BRANDS[brand]
    q = research.get("queries") or {}
    title_req = (', "title_slots":{"hook1":"제목 1줄(≤11자, 계기·감정)","hook2":"제목 2줄(≤11자, ~의 발명품/정체)","bodyTitle":"본문 제목(≤20자, ?로 끝)"}'
                 + f"  — 제목 원문: {title_line}") if brand == "재미썸홈" else ""
    prompt = SHOT_PROMPT.format(product=product, queries=" · ".join((q.get("en") or [])[:4]), rule=B["재료_규칙"], kinds="·".join(B["kinds"]),
                                pieces="\n".join(f"{k}: {r['line']} | {r['piece']} | {r['line_text']}" for k, r in enumerate(rows)),
                                title_req=title_req)
    for attempt in range(2):     # 10-18 실측: 응답이 shots 가 아닌 꼴(items·글)로 와 22조각 전부 빈칸 — 꼴을 넓혀 받고 1회 더
        d, err = G.ask([], prompt, tag="oneshot_shots")
        raw = (d or {}).get("shots") or (d or {}).get("items") or next((v for v in (d or {}).values() if isinstance(v, list)), [])
        shots = {int(s["i"]): s for s in raw if isinstance(s, dict) and str(s.get("i", "")).strip().isdigit()}
        miss = [k for k in range(len(rows)) if not (shots.get(k) or {}).get("query")]
        if d is not None and not miss:
            break
        print(f"[경보] 장면 검색어 {attempt + 1}회째 실패 {err or ''} · 빈 조각 {len(miss)}개 · 응답 키 {sorted(d)[:6] if isinstance(d, dict) else type(d)}")
    if d is None or miss:
        raise SystemExit(f"장면 검색어 실패 {err or ''} · 빈 조각 {miss}")
    for s in shots.values():
        if s.get("kind") not in B["kinds"]:
            s["kind"] = B["kinds"][0]
    return {"shots": shots, "title_slots": (d or {}).get("title_slots")}


def build(engine_json: Path, research_json: Path, brand: str, out: Path) -> Path:
    from shopping_shorts.narration_naturalize import normalize_reading
    from tools.calcopy import narr_video as N
    S = json.loads(Path(engine_json).read_text(encoding="utf-8"))
    R = json.loads(Path(research_json).read_text(encoding="utf-8"))
    if S.get("status") != "ok":
        raise SystemExit(f"엔진 대본이 통과 전이다({S.get('status')}) — 남은 줄을 고친 뒤 옮긴다: {S['final']['check'].get('global')}")
    B = BRANDS[brand]
    lines = S["final"]["lines"]
    rows = []
    for li, l in enumerate(lines):
        for p in N.chunk_sentence(l["text"], PIECE_CHARS):
            rows.append({"line": li, "piece": p.strip(" ,"), "line_text": l["text"]})
    product = R.get("product") or S["product"].get("name")
    sq = shot_queries(product, R, brand, rows, lines[0]["text"])
    out_lines = []
    for li, l in enumerate(lines):
        mine = [(k, r) for k, r in enumerate(rows) if r["line"] == li]
        shots = [{"piece": r["piece"], "query": sq["shots"][k]["query"], "kind": sq["shots"][k]["kind"]} for k, r in mine]
        out_lines.append({"i": li, "text": l["text"], "tts_text": normalize_reading(l["text"])[0], "role": l.get("fn") or l.get("node") or "",
                          "point": l.get("point") or "", "shot_query": [s["query"] for s in shots], "shots": shots,
                          "kind": shots[0]["kind"] if shots else B["kinds"][0]})
    chars = sum(len(x["text"].replace(" ", "")) for x in out_lines)
    doc = {"채널": brand, "channel": B["channel"], "preset": B["preset"], "topic": product, "목소리": B["voice"], "voice": B["voice"],
           "cps_target": B["cps_target"], "재료_규칙": B["재료_규칙"], "from": f"원샷링크딸깍 엔진({S.get('engine')}) · {engine_json}",
           "lines": out_lines, "chars": chars, "est_sec": round(chars / B["cps_target"], 2),
           "facts": {k: f"{v['text']} ({v.get('url', '')})" for k, v in S["facts"].items()}, "title_lines": [], "sfx": B["sfx"]}
    if brand == "재미썸홈":
        ts = sq.get("title_slots") or {}
        doc["title_slots"] = ts
        doc["title_lines"] = [ts.get("hook1", ""), ts.get("hook2", "")]
        doc["bgm"] = None
    else:
        doc["meme"] = 0
    out.mkdir(parents=True, exist_ok=True)
    p = out / "대본.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[작품] {p} · 줄 {len(out_lines)} · 조각 {len(rows)} · {chars}자 · 예상 {doc['est_sec']}초")
    return p


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
