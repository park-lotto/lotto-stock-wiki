# -*- coding: utf-8 -*-
"""영상 스토리 태깅 — 1단계에서 영상마다 "순서 있는 대본 문장 + 그 문장을 보여주는 컷"을 만든다 (2026-10-01 사장님).

★왜: 사장님 "태깅부터 대본화 — 태깅 문구를 대본에도 쓰고 장면 매칭에도 그대로 쓴다. 설명문이 아니라 말맛."
  종전엔 2단계가 태그를 읽어 특징 묶음을 다시 만들고(build_groups·extract_feats = AI 호출) 문장을 새로 지어 쓴 뒤
  매처가 컷을 **찾았다**. 스토리가 있으면 문장과 컷이 태깅 때 이미 짝이라 매칭은 **확인**이 된다.
  실측(tools/story_tag_trial.py, 파스타 job 4a1d44721e8a): 스토리 8편 31줄 → 대본 11줄 전부 스토리 문장에서, 10/11 줄 컷이 말과 같은 그림.

판단 주인: 이 모듈 한 곳. 1단계(script_extract·frame_script)가 `make_story` 로 만들어 extract["story"] 에 저장하고,
2단계 백본(backbone_assemble.assemble)과 이야기작가(story_writer.make_drafts)는 `groups_from_stories` / `feats_from_stories` 로
스토리를 **특징 묶음 자리에 그대로** 쓴다(스토리가 없는 옛 추출본이면 종전 경로 — note 에 이유).
★씨앗 영상은 매칭에 안 쓴다(사장님 10-01 "씨앗 대본은 장면매칭에 쓰지 않는다 원래") — 호출부가 _drop_seed 로 뺀 뒤 넘긴다.
"""
from shopping_shorts import script_generate as _sg

KINDS = ("문제", "기능", "특징", "장점", "효과", "외관", "활용", "구성", "반응")
MAX_LINES = 6

SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
        "text": {"type": "string"}, "cuts": {"type": "array", "items": {"type": "string"}},
        "kind": {"type": "string"}, "point": {"type": "string"},
    }, "required": ["text", "cuts"]}}},
    "required": ["lines"],
}

PROMPT = """너는 쇼핑 쇼츠 **대본 작가 겸 편집자**다. 아래는 제품 영상 한 편의 컷 태그다
(컷마다: 번호 | 길이 | 화면에 보이는 것 | 쓰임 | 소구점(이 장면 위에 읽힐 말) | 종류 | 훅).

이 영상의 **스토리**를 써라 — 시청자에게 보여줄 순서대로 3~%d줄. 줄마다:
- text: 대본에 **그대로 읽을** 한 문장(12~30자). ★설명문이 아니다 — 쇼핑 쇼츠 **말맛**으로 써라: 구어체, 리듬, 과장·감탄·의성어 OK
  (예 "물만 붓고 돌리면 끝, 냄비 설거지 안녕" / "거름망 하나로 물만 쏙, 손 델 일이 없어요" / "소스 부어 쓱쓱, 바로 한 끼 완성").
  "~하는 모습이다" "~을 보여준다" 같은 묘사·보고 문장은 금지. 단, 그 줄에 붙은 컷 위에서 읽히므로 **화면에 보이는 것만** 말한다.
- cuts: 그 문장을 보여주는 컷 번호들(1개 이상, 같은 장면 연속 컷은 같이). 줄 길이(초)를 생각해 2~3초는 되게 모아라.
- kind: 문제/기능/특징/장점/효과/외관/활용/구성/반응 중 하나.
- point: 이 줄이 파는 포인트 한 구절(예 "1인분 딱 맞는 계량", "거름망 배수 = 쉬운 조리").
규칙: 컷 번호는 목록에 있는 것만. 한 컷은 한 줄에만. 뒷컷(인사·채널 화면·링크)은 쓰지 마라. 불편·기존 방식 장면이 있으면 '문제' 줄을 맨 앞에.
출력 JSON만: {"lines":[{"text":"...","cuts":["..."],"kind":"...","point":"..."}]}

[제품] %s
[컷 목록]
%s
"""


def _rows(segments):
    rows = []
    for s in segments or []:
        if not isinstance(s, dict) or not s.get("seg_id"):
            continue
        try:
            secs = float(s.get("end") or 0) - float(s.get("start") or 0)
        except (TypeError, ValueError):
            secs = 0.0
        if secs < 0.8:
            continue
        if s.get("is_outro") and not (s.get("hook_type") or s.get("product_benefits")):
            continue                                   # 뒷컷(제품 안 보임)은 목록에서 뺀다
        rows.append("  %s | %.1f초 | %s | 쓰임:%s | 소구점:%s | 종류:%s | 훅:%s" % (
            s["seg_id"], secs, (s.get("scene_desc") or "")[:60], s.get("label") or "-", (s.get("use_point") or "")[:40] or "-",
            s.get("appeal_kind") or "-", s.get("hook_type") or "-"))
    return rows


def normalize(lines, seg_ids):
    """모델 응답 → 검증된 스토리 줄 목록(순수함수). 없는 컷·중복 컷·빈 문장은 버린다. '문제' 줄을 앞으로."""
    out, used = [], set()
    for L in lines or []:
        if not isinstance(L, dict):
            continue
        text = str(L.get("text") or "").strip()
        cuts = []
        for c in L.get("cuts") or []:
            c = str(c).strip()
            if c in seg_ids and c not in used:
                cuts.append(c); used.add(c)
        if not text or not cuts:
            continue
        kind = str(L.get("kind") or "").strip()
        out.append({"text": text[:60], "cuts": cuts, "kind": kind if kind in KINDS else "",
                    "point": str(L.get("point") or "").strip()[:30]})
    out.sort(key=lambda L: 0 if L["kind"] == "문제" else 1)
    return out[:MAX_LINES]


def make_story(product, segments, call=None, note=None):
    """영상 한 편 → 스토리 줄 목록. 실패하면 [] (호출부 fail-open — 스토리 없는 영상은 종전 경로)."""
    rows = _rows(segments)
    if len(rows) < 2:
        if note is not None:
            note["story_reason"] = "컷 부족"
        return []
    prompt = PROMPT % (MAX_LINES, product or "(제품명 미상 — 컷에서 읽어라)", "\n".join(rows))
    seg_ids = {s.get("seg_id") for s in segments if isinstance(s, dict)}
    fn = call or (lambda p: _sg._call_json(p, SCHEMA, note=note, vertex=False))
    lines = []
    for _try in range(2):                              # 빈 응답은 한 번 더(실측: 8편 중 1편 빈 응답)
        try:
            out = fn(prompt) or {}
        except Exception as e:      # noqa: BLE001 — 스토리 실패가 추출을 막으면 안 된다(이유는 note 에)
            if note is not None:
                note["story_reason"] = "호출 실패 %s" % repr(e)[:80]
            return []
        lines = normalize(out.get("lines") if isinstance(out, dict) else [], seg_ids)
        if lines:
            break
    if not lines and note is not None:
        note["story_reason"] = "빈 응답"
    return lines


def has_stories(sources):
    """스토리를 특징 묶음으로 쓸 만큼 있나 — 비씨앗 소스의 **절반 이상**에 스토리가 있고 줄이 3개 이상.
    (처음엔 '전부'로 했더니 한 편이 빈 응답이면 통째로 옛 경로로 떨어졌다 — 2026-10-01 파스타 8편 중 1편 빈 응답.)
    스토리 없는 소스의 컷은 assign_cuts 채우기에서 그대로 쓰인다."""
    srcs = [s for s in (sources or []) if isinstance(s, dict)]
    if not srcs:
        return False
    with_story = [s for s in srcs if (s.get("story") or [])]
    n_lines = sum(len(s.get("story") or []) for s in with_story)
    return len(with_story) * 2 >= len(srcs) and n_lines >= 3


def feats_from_stories(sources, seg_index):
    """스토리 줄 → 이야기작가 특징 후보(extract_feats 와 같은 모양). 영상별 줄을 번갈아 섞어 한 영상이 독점하지 않게."""
    per = []
    for s in sources or []:
        vid = s.get("video_id")
        rows = []
        for L in (s.get("story") or []):
            cuts = [c for c in (L.get("cuts") or []) if c in seg_index]
            if not cuts:
                continue
            rows.append({"name": L.get("point") or L.get("text") or "", "claim": L.get("text") or "",
                         "from_cuts": cuts, "pain": L.get("text") if L.get("kind") == "문제" else "",
                         "kind": L.get("kind") or "", "seed_quote": "", "seed_point": 0, "video": vid})
        per.append(rows)
    out, k = [], 0
    while any(per):
        for rows in per:
            if rows:
                out.append(rows.pop(0))
        k += 1
        if k > MAX_LINES:
            break
    return out


def groups_from_stories(sources, seg_index, max_groups=4):
    """스토리 줄 → 백본 특징 묶음(build_groups 와 같은 반환 모양). '문제' 줄은 묶음에 안 넣는다(미끼 줄은 assign_cuts 가 문제 컷을 찾는다).
    같은 point 끼리는 컷을 합친다(영상 여러 편이 같은 장점을 보여주면 한 묶음에 컷이 여럿)."""
    feats = feats_from_stories(sources, seg_index)
    groups, by_point = [], {}
    for f in feats:
        if f.get("kind") == "문제":
            continue
        key = (f.get("name") or f.get("claim") or "").replace(" ", "")[:12]
        if key in by_point:
            g = groups[by_point[key]]
            g["cuts"] += [c for c in f["from_cuts"] if c not in g["cuts"]]
            continue
        by_point[key] = len(groups)
        groups.append({"name": f.get("name") or "", "claim": f.get("claim") or "", "cuts": list(f["from_cuts"]),
                       "kind": f.get("kind") or "", "where": "둘다", "doubt": False})
    groups = groups[:max_groups]
    product = next(((s.get("source_brief") or {}).get("product") or "" for s in (sources or []) if isinstance(s, dict)), "")
    return {"product": product, "groups": groups, "order": list(range(len(groups))), "alt_use": False, "groups_from": "story"}
