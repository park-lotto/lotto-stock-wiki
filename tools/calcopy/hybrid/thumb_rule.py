# -*- coding: utf-8 -*-
"""썸네일 카드 판단의 주인 — 장면 찾는 순서 · 좋은 썸네일 조건 · 3안 검사 (관제 097, 2026-10-24 사장님).

사장님 10-24: 01b A안("회장님도 뚜껑 핥는다고?? ㅋㅋ")을 보고 "이런 거 너무 좋은데, 정말 재밌고 궁금한 거 / 각 영상마다 배치하는 규칙" ·
"영상 앞부터 아주 살짝, 거의 안 보일 정도" · "영상 안에 그런 장면이 없다면?" → "검색을 통해서 찾을 수 없나 구글 네이버" → "그것까지 엔진에".

부르는 곳: 썰템홈샷 make.py(thumbs·checks) · 회원 라인 서버 지시서 flow.py(썸네일 단계 질문·반려) · 워커 지시서는 이 글을 가리킨다.
그리기·맨 앞 2프레임 입히기 = thumb.py(card·stamp_video·THUMB_FRAMES) · 장면 찾기 = tools/calcopy/scene_search.py.
"""
from __future__ import annotations

import re
from pathlib import Path

AXES = ("인물순간", "물건근접", "정체숨김", "황당사실", "짤반응")
MOODS = ("funny", "wow")
TEXT_MAX = 12            # 한 줄 글자 수(공백 빼고) — 본보기 '뚜껑 핥는다고??' 8자
TAGS = ("ㅋㅋ", "ㅎㅎ", "ㄷㄷ")

FIND_ORDER = """썸네일·훅 장면 찾는 순서(위에서부터, 찾으면 멈춘다)
1. 본편에 이미 있는 장면 중 '아는 인물이 체면 깨는 결정적 순간'(axis 인물순간) — 앞뒤 0.05초 단위로 가장 우스운 한 장.
2. 없으면 검색으로 찾는다: `py tools/calcopy/scene_search.py "<소재>" --brand <브랜드>` — 구글·네이버 = 어떤 장면이 있는지 단서,
   유튜브 = 그 장면의 공식 원본(인증 채널·방송사). 단서 영상이 재편집 채널이면 엔진이 같은 장면의 공식 원본을 다시 찾아 붙인다.
   찾은 원본에서 그 구간만 받아 **훅에 넣고**(본편에 나와야 썸네일로 쓸 수 있다) 그 장면으로 썸네일을 만든다.
3. 검색해도 공식 원본이 없을 때만 본편 장면으로: 짤반응(본편 짤 중 가장 센 표정 + 상황 한 마디) → 물건근접(가장 이상한 한 곳 + 원 + ?) →
   정체숨김(hide 흐림 + '이게 뭐길래??') → 황당사실(자료 화면 + 놀라운 사실 + ㄷㄷ).
★훅·썸네일 장면은 그 장면 자체가 '잉' 질문이어야 한다(요플레: '재벌도 뚜껑 핥나?' = 요플레 이야기 그 자체). 같은 범주일 뿐 상관없는 장면을
   '근데'로 이어 붙이지 않는다(10-24 03b 상속자들 카레 → 'S&B 뜻'과 무관 — 반려). 말장난도 장면 그대로 참이어야 한다.
하지 않는 것: 인물이 하지 않은 행동 합성 · 검색 결과 사진(뉴스·블로그 캡처)을 그대로 쓰기 · 본편에 없는 장면."""

GOOD = """좋은 썸네일 조건(본보기 channel/banggu/썰템홈샷_하이브리드/01b_요플레/thumb/A.jpg)
① 장면 = 아는 인물·권위 있는 사람이 체면 깨는 결정적 순간 ② 빨간 원은 그 행동 지점 하나에만 ③ 글 = 그 장면을 되묻는 한 마디 + '??'
(설명하지 않는다, 한 줄 12자 안, 꼬리표 ㅋㅋ/ㅎㅎ/ㄷㄷ 는 엔진이 붙이니 쓰지 않는다) ④ 본편에 실제로 나오는 장면 ⑤ 로고·박힌 글·가격은 자르기 밖.
3안은 서로 다른 axis 로(인물순간 / 물건근접·정체숨김 / 황당사실·짤반응). 맨 앞 2프레임(0.067초)만 — 늘리지 않는다."""


def find_order(slug: str | None = None) -> str:
    """FIND_ORDER + 그 채널 상위 편 훅 3초 참고 한 줄(channel/<slug>/_kal/상위편_목표.json hook — placement.py count <판> --top 이 잰다, 지시서 15).
    판정 규칙(check)은 안 바뀐다 — 장면 고를 때 참고하는 추천일 뿐. 파일·칸이 없으면 FIND_ORDER 그대로."""
    import json
    p = Path(__file__).resolve().parents[3] / "channel" / str(slug or "_") / "_kal" / "상위편_목표.json"
    h = (json.loads(p.read_text(encoding="utf-8")).get("hook") or {}) if slug and p.exists() else {}
    if not h:
        return FIND_ORDER
    return FIND_ORDER + (f"\n참고(상위 편 {len(h.get('top_ids') or [])}편 훅 실측 — 판정 아님): 첫 컷 중앙 {h.get('first_cut_sec_p50')}초 · "
                         f"0초 화면 얼굴 비율 중앙 {h.get('face_or_object_frac')} · 첫 꾸밈 {h.get('first_fx_t')}초 — 0초부터 얼굴/물건이 크게 보이는 장면을 앞에.")


def _n(s: str) -> int:
    return len(re.sub(r"\s", "", s or ""))


def check(spec: dict, cuts: list[dict] | None = None, n_parts: int | None = None) -> list[str]:
    """3안 검사 → 문제 목록(빈 목록 = 통과).
    cuts = 본편 컷 [{src(파일 이름), ss, dur}] — src/ss 꼴 안(썰템홈샷) / n_parts = 렌더 컷 수 — part/t 꼴 안(공용 렌더러·회원 라인)."""
    bad = []
    ops = spec.get("options") or []
    if len(ops) != 3:
        bad.append(f"안이 {len(ops)}개 — 3안이어야 한다")
    ids = [o.get("id") for o in ops]
    if len(set(ids)) != len(ids):
        bad.append("안 id 가 겹친다")
    axes = [o.get("axis") for o in ops]
    for o in ops:
        i = o.get("id")
        if o.get("axis") not in AXES:
            bad.append(f"{i}: axis 가 없다/틀리다({o.get('axis')}) — {AXES} 중 하나")
        if o.get("mood") not in MOODS:
            bad.append(f"{i}: mood 는 funny|wow")
        tx = o.get("text") or []
        if not tx or not tx[0].get("lines"):
            bad.append(f"{i}: 글이 없다")
        for t in tx:
            for line in t.get("lines") or []:
                if _n(line) > TEXT_MAX:
                    bad.append(f"{i}: 글 '{line}' {_n(line)}자 > {TEXT_MAX}자 — 설명하지 말고 되묻는 한 마디로")
                if any(g in line for g in TAGS):
                    bad.append(f"{i}: 꼬리표(ㅋㅋ·ㅎㅎ·ㄷㄷ)는 엔진이 붙인다 — 글에서 뺀다")
        if not (o.get("circle") or o.get("arrow") or o.get("q") or o.get("hide")):
            bad.append(f"{i}: 궁금 장치(빨간 원·화살표·?·흐림)가 하나도 없다")
        if "part" in o:
            if n_parts is not None and not (0 <= int(o["part"]) < n_parts):
                bad.append(f"{i}: part {o['part']} — 렌더 컷은 0~{n_parts - 1}")
        elif o.get("src") is not None and cuts is not None:
            name, t = Path(str(o["src"])).name, float(o.get("ss", 0))
            if not any(Path(str(c["src"])).name == name and float(c["ss"]) - 0.05 <= t <= float(c["ss"]) + float(c["dur"]) + 0.05 for c in cuts):
                bad.append(f"{i}: 장면 {name}@{t} 이 본편 컷에 없다 — 본편에 그 구간을 넣거나 본편 장면을 고른다(낚시 금지)")
    if len(set(a for a in axes if a)) < 3 and len(ops) == 3:
        bad.append(f"3안의 axis 가 겹친다({axes}) — 서로 다른 축으로")
    if "인물순간" not in axes and not str(spec.get("no_person_why") or "").strip():
        bad.append("인물순간 안이 없다 — scene_search 로 찾아보고, 그래도 없으면 no_person_why 에 무엇을 검색했고 왜 없는지 적는다")
    return bad


def card_face_gate(st: dict, doc, T: dict, cand_dir) -> list[str]:
    """(렌더 전 관문 ⑥, 10-25) 연예인 채널 판(st["thumb_card_face"] = true)이면 카드 3안 **전부** 장면에 연예인 얼굴(thumb.judge 와 같은 자) —
    안은 무작위로 하나가 보이니 하나라도 얼굴이 없으면 반려. 렌더 전에 원본에서 잰다(thumb.card_faces). 문제 목록(빈 목록 = 통과).
    왜: 10-24 얜샷템 메디필(기미크림) 0프레임 카드 = 제품 튜브(얼굴 0개)인데 자동검사 10/10 — 얼굴 검사가 카드 뒤(0.077초)부터 재서 못 봤다(10-25 감사)."""
    if not st.get("thumb_card_face"):
        return []
    from tools.calcopy.hybrid import thumb
    return [f"썸네일 카드 {r['id']}: 연예인 얼굴 아님({r['why']} · {r['where']}) — 얼굴이 크게 나온 장면으로 바꾼다(얜샷템 썸네일 = 연예인 얼굴)"
            for r in thumb.card_faces(st, doc, T, cand_dir) if not r["ok"]]
