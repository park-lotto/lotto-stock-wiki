# -*- coding: utf-8 -*-
"""회원 라인 **서버 지시서**(볼케이노형, 관제 234·097 — 사장님 10-21 "볼케이노처럼 / 칼카피 노하우를 녹여서 지금처럼 영상이 나오게").

노하우(단계 순서·판정 질문·반려 규칙·함정)는 이 파일 한 곳. 회원 PC 는 손(runner_ops 가 do 를 실행)과 눈(회원 Claude 가 review 에 답)만.
서버(shopping_shorts/claude_flow.py)가 이 모듈을 불러 매 호출마다:

    resp = step(state, measure, replies, user)      # state = 지난 응답의 상태(서버 서명 payload 안), measure = do 결과, replies = review 답
    resp = {"status": execute|review|wait_user|reject|stop|done, "message": "OO 완료 → 다음 OO", "stage": {no,total,text},
            "do": [{id, cmd, …}], "review": [{id, model, ask, show[…], need[…]}], "traps": [...], "reject": {why, fix},
            "wait": {kind, script}, "video": "<PC 파일>", "state": {...}}

판단 주인(새로 적지 않고 부른다): 판 = styles · 대본 검사 = script_audit · 출처 규칙·자막↔목소리·제목 색·샷 끝·흐림 = rules ·
완성본 검사 = quality_gate.gate 1단(PC 가 재고) + 눈 2단 E1~E8(quality_gate.EYE_Q 질문 그대로, 회원 Claude) · 해외 원본 고르기 = origin_find.pick_origins ·
형식 = channel/프리셋.json presets[slug].member.flow_format(표준 §2-1 — flow_format_of 한 곳). 단계는 channel/칼카피_제작순서 00~13 과 같은 순서(바꾸면 문서와 같은 커밋).

형식별 단계표 FORMAT_STAGES(관제 263 지시서 08 · 표준 §7): 연예인형(원래 13단계) · 해외원본형(한국 재편집 → 렌즈로 해외 원본 → 같은 제품 다른 해외 반응 →
자막 지우기(회원 VMake 키 없으면 흐림) → 대본) · 쇼핑형(제품·썰 소재 → 쿠팡 → 근거 글 → 재료 영상) · 레시피형(연예인형 단계 + 판의 재료 스티커).
세부 단계 처리기는 형식별 표(FORMAT_PHASES[형식][세부 단계])가 있으면 그것, 없으면 공용(PHASES). 질문문도 형식별(_Q) — 연예인형 문장을 다른 형식에 쓰지 않는다.
회원 맞춤(customize) 자리 = 대본 검사 통과 뒤·사인 전(ph_customize — 지시서 12 가 채운다, 지금은 그대로 지나감).
"""
from __future__ import annotations

import json
import math
import re
import tempfile
from pathlib import Path

from tools.calcopy.hybrid import rules as RU

# ── 단계(회원에게 보이는 한 줄) — 제작순서 00~13 ──────────────────────────────
STAGES = [("setup", "준비 확인"), ("bench", "영상 확인"), ("origin", "원본 영상 찾기"), ("product", "제품 확인"), ("research", "자료 조사"),
          ("material", "재료 영상 모으기"), ("asr", "원음 정리"), ("script", "대본 쓰기"), ("sign", "대본 확인"), ("plan", "장면 맞추기"),
          ("render", "목소리·영상 만들기"), ("check", "완성본 검사"), ("done", "완성")]
STAGE_NO = {k: i + 1 for i, (k, _) in enumerate(STAGES)}
STAGE_TEXT = dict(STAGES)

# 형식별 단계표(회원에게 보이는 단계) — 주인: 이 표 한 곳. 형식 이름 = channel/프리셋.json member.flow_format 값
FORMAT_STAGES = {
    "연예인형": STAGES,
    "해외원본형": [("setup", "준비 확인"), ("bench", "영상 확인"), ("origin", "해외 원본 찾기"), ("product", "제품 확인"), ("research", "자료 조사"),
                ("material", "원본 정리"), ("asr", "원음 정리"), ("script", "대본 쓰기"), ("sign", "대본 확인"), ("plan", "장면 맞추기"),
                ("render", "글자 지우기·영상 만들기"), ("check", "완성본 검사"), ("done", "완성")],   # 글자 지우기 = 장면 맞추기 뒤 자막 있는 컷만(f_render, 사장님 10-26)
    "쇼핑형": [("setup", "준비 확인"), ("bench", "소재 확인"), ("product", "제품 확인"), ("research", "자료 조사"), ("material", "재료 영상 모으기"),
             ("script", "대본 쓰기"), ("sign", "대본 확인"), ("plan", "장면 맞추기"), ("render", "목소리·영상 만들기"), ("check", "완성본 검사"), ("done", "완성")],
    "레시피형": STAGES,          # 연예인형 단계 + 재료 스티커(판 placement·brief 가 정한다 — flow 는 판을 읽을 뿐)
}
PRESETS_FILE = Path(__file__).resolve().parents[3] / "channel" / "프리셋.json"


class FormatError(ValueError):
    """형식을 정할 수 없는 판 — 조용히 기본값(연예인형)으로 돌리지 않는다(관제 263 08 합격 검사 5). 서버(claude_flow)는 이 글을 회원에게 그대로."""


def flow_format_of(version: str) -> tuple[str, str]:
    """판 이름 → (형식, slug) — 주인 = channel/프리셋.json presets[slug] 의 engine.style_file(판 파일)·member.flow_format.
    업그레이드 판(잇템로그판_v2)은 base 를 따라 1차 판 이름으로 찾는다. 없거나 형식이 둘로 갈리거나 flow 표에 없는 형식이면 FormatError."""
    from tools.calcopy.hybrid import styles as STY
    pres = json.loads(PRESETS_FILE.read_text(encoding="utf-8")).get("presets") or {}
    chain, name = [], version
    for _ in range(6):
        if not name or name in chain:
            break
        chain.append(name)
        try:
            raw = json.loads(STY.path_of(name).read_text(encoding="utf-8"))
        except (SystemExit, OSError, ValueError):
            break
        name = raw.get("base")
    for nm in chain:
        hits = [(slug, (p.get("member") or {}).get("flow_format")) for slug, p in pres.items()
                if Path(str((p.get("engine") or {}).get("style_file") or "")).stem == nm]
        if not hits:
            continue
        fmts = sorted({f for _, f in hits if f})
        if len(fmts) != 1:
            raise FormatError(f"판 {version} 의 형식이 channel/프리셋.json 에서 정해지지 않았습니다({hits})")
        if fmts[0] not in FORMAT_STAGES:
            raise FormatError(f"판 {version} 의 형식 '{fmts[0]}' 은 회원 흐름이 아직 없습니다(지원: {', '.join(FORMAT_STAGES)})")
        return fmts[0], hits[0][0]
    if version in pres and (pres[version].get("member") or {}).get("flow_format") in FORMAT_STAGES:     # 프리셋 slug 를 그대로 준 경우(장부 키 — 정확히 일치할 때만)
        return pres[version]["member"]["flow_format"], version
    raise FormatError(f"판 {version} 이 channel/프리셋.json 에 없습니다 — 프리셋 장부에 판 파일·flow_format 을 먼저 적어야 합니다")

PHASE_STAGE = {   # 세부 단계 → 회원에게 보이는 단계
    "setup": "setup", "setup_check": "setup", "bench": "bench", "bench_got": "bench", "origin_read": "origin", "peer": "origin", "peer_read": "origin",
    "search": "origin", "search_got": "origin", "titles": "origin", "titles_got": "origin", "subs": "origin", "subs_got": "origin",
    "pick_got": "origin", "origin_got": "origin", "product_sheet": "product", "product_pick": "product", "product_cands": "product",
    "product_same": "product", "name_find": "product", "name_got": "product", "named_cands": "product", "named_same": "product",
    "best_same": "product", "product_done": "product", "research": "research", "research_got": "research", "material": "material",
    "material_got": "material", "material_pick": "material", "material_dl": "material", "asr": "asr", "asr_got": "asr", "shots_got": "asr",
    "script": "script", "script_got": "script", "script_saved": "script", "sign": "sign", "plan": "plan", "plan_got": "plan",
    "plan_look": "plan", "plan_saved": "plan", "thumb": "plan", "thumb_got": "plan", "render": "render", "render_got": "render", "render_fix": "render", "render_saved": "render",
    "check": "check", "check_got": "check", "check_look": "check", "check_fix": "check", "check_saved": "check", "done": "done",
}

LIMITS = {"script": 5, "plan": 8, "render": 3, "look": 2, "pick": 2, "review_bad": 2}
TITLE_CHUNK = 120     # 원본 후보 제목 한 묶음(질문 하나 약 6천 자 — 10-21 300편 통째 4.2만 자로 40분 멈춤)
ORIGIN_TRY = 16       # 자막 대조할 후보 수

TRAPS = {   # 단계별 함정(98_오류기록 번호) — 회원 Claude 판정에 같이 실린다
    "origin": ["설명란 '영상 속 제품'은 그 채널의 파트너스 상품일 뿐 근거가 아니다(02 §2)", "사람 이름은 화면 글자·이름표로만 — 얼굴로 짐작한 이름은 '불명'",
               "원본은 연예인 본인 채널이 1순위(#8) · 남의 쇼츠 '출처:' 글자도 단서(#9)", "유튜브 제목이 영어 번역으로 올 수 있다(#6)",
               "두세 줄 이상 같은 말이 맞아야 확정, 말한 사람이 본인이어야 한다(02 §4·§5)"],
    "product": ["원본 화면 포장·로고·모양·색이 같은 것만 '같은 제품' — 비슷한 제품 대체 금지(03 §4)", "남의 설명란 파트너스 상품은 근거가 아니다",
                "상표가 안 보이면 이름을 글에서 찾고, 그래도 없으면 같은 종류 중 후기 많은 것 + 대본에 그 사실(#10)", "의약품·의료기기는 만들지 않는다"],
    "research": ["다른 회사 숫자 금지 · 효능 해시태그 따라 쓰기 금지 · 질병 이름 금지", "남(PD·가족·다른 출연자)의 말은 원음 줄로 쓰지 않는다",
                 "원음 구간 시각은 받은 파일 초(잰 offset 기준) — 원본 초와 다르다(#16)"],
    "material": ["남의 리뷰 영상의 장면 전환·남의 손 근접은 쓰지 않는다 — 원본 안 제품 장면이 먼저(#1·#2)", "연예인이 나오는 남의 영상은 재료 금지(#3)"],
    "asr": ["자동자막·위스퍼는 '눈곱'을 '눈꽃'처럼 틀린다 — 문맥으로 바로잡는다(#12)", "방송 원본은 카메라가 1~2초마다 바뀐다 — 샷 표를 본다(#13)"],
    "script": ["자막(caps)은 읽는 말(tts) 그대로 — 발음 고침만 다르게(#17)", "제목 2줄째에 hi 금지인 판이 있다(틀에 있는 색만)",
               "줄 끝 문장부호 필수 · 숫자·영문은 읽는 대로 tts 에", "주인공 컷(face)은 원본 파일에서만, 그 샷 안에서(#14)"],
    "plan": ["확대는 1.0 — 원본 아래 박힌 자막·띠는 잘라서 피하지 말고 재료.blur 로 흐린다(사장님 10-22, 강주은 첫 컷 1.4배 뭉개짐)", "컷이 원본 샷보다 길면 렌더가 멈춘다"],
    "check": ["1초 시트 사이로 0.5초 장면 전환이 지나갈 수 있다(#1)", "0초 = 연예인 얼굴 크게"],
}

# ── 판정 질문(회원 Claude) — customer.py(10-21) 지시문을 옮겨 왔다 ─────────────────
ORIGIN_READ = """너는 쇼츠 원본 추적 담당이다. 아래는 남의 채널이 만든 연예인 쇼핑 쇼츠(벤치)의 1초 간격 장면 시트와 제목·설명·받아쓰기다.
이 쇼츠가 따온 **연예인 본인 원본 영상**(본인 유튜브·방송)을 찾기 위한 단서를 읽어라.
- 화면 위·아래의 '출처: ○○' 글자 = 원본 채널(★글자는 **둘째 그림(한 장면 크게)**에서 한 자씩 읽는다 — 시트 칸은 작아 잘못 읽는다, 98 #69). 화면에 없으면 **설명란**의 출처 표기(출처·원본·영상 출처 ○○). 둘 다 없으면 source_label ''. 방송 로고·프로그램 이름도 본다. 이름표·자막으로 말하는 사람을 확인(얼굴로 짐작한 이름은 '불명').
- 설명란 '영상 속 제품'은 그 채널의 파트너스 상품일 뿐 근거가 아니다.
- 연예인이 쓰는 물건(쇼핑 소재)이 아니면 is_shopping=false. 의약품·의료기기면 is_shopping=false.
JSON 하나: {"celeb": "이름 또는 불명", "source_label": "출처 글자 그대로(화면 → 설명란) 또는 ''",
 "source_kind": "channel(유튜브 채널 이름 — 개인 채널·'요정재형'처럼) | program(방송 프로그램 이름 — '옥탑방의 문제아들'·'유퀴즈'처럼, 방송사 로고·회차 표기가 단서) | sns(유튜브 밖 — '○○ 인스타그램'·틱톡·블로그처럼)", "channel_hint": "원본 채널 이름·핸들 추정 또는 ''",
 "product_words": ["제품을 가리키는 낱말"], "scene_words": ["원본 장면을 가리키는 장소·상황 낱말(제목·설명·화면 글자에서, 예 '서촌'·'마실') — 없으면 []"], "queries": ["유튜브 검색어 3~5개 — '<연예인> <제품 낱말>' 꼴"], "is_shopping": true}"""

PEER_READ = """너는 출처 글자 읽기 담당이다. 같은 연예인·제품을 다룬 **다른 채널 쇼츠**들의 장면 모음이다(쇼츠마다 한 줄, 왼쪽에 번호).
화면 위·아래의 '출처: ○○' 글자, 방송 로고·프로그램 이름을 그대로 읽어라. 안 보이면 빈 값. 지어내지 마라.
JSON 하나: {"labels": [{"n": 번호, "source": "출처 글자 그대로 또는 ''", "program": "방송·채널 이름 또는 ''"}]}"""

ORIGIN_TITLES = """너는 원본 후보 고르기 담당이다. 연예인 본인 채널의 영상 목록(제목)에서, 벤치 쇼츠가 따온 원본일 만한 영상을 최대 8개 골라라 —
제목에 그 제품·쓰임(주방·청소·살림템·추천템 등)·계절이 맞는 것. 벤치보다 먼저 올라온 것.
JSON 하나: {"ids": ["유튜브 id", …]}"""

ORIGIN_VISUAL = """너는 원본 판정 담당이다. 벤치 쇼츠가 **내레이션뿐**이라 말 지문으로는 원본을 못 찾았다. 첫 그림 = 벤치 1초 장면 시트,
둘째 그림 = 후보 원본(연예인 본인 채널) 전체를 고르게 훑은 시트(칸 간격은 아래).
**같은 사람·같은 옷·같은 제품·같은 장소**가 둘 다에 있어야 같다고 본다(비슷한 물건만으론 아니다). 같으면 그 제품이 잘 보이는 칸의 초를 적어라.
JSON 하나: {"same": true, "origin_t": [받은 파일 초, …], "why": "한 줄"}"""

ORIGIN_PICK = """너는 원본 판정 담당이다. 벤치 쇼츠의 말과 같은 말이 들어 있는 후보 원본 영상들이다(자막 지문 대조 결과).
두세 줄 이상 같은 말이 맞고, 그 제품을 말한 사람이 연예인 **본인**이어야 확정. 후보 제목·채널·날짜도 본다
(원본은 벤치보다 먼저 올라왔다). 확정 못 하면 origin_id 를 ''.
JSON 하나: {"origin_id": "유튜브 id 또는 ''", "matched": [{"bench": "벤치 말", "origin_t": 초}], "self_spoken": true, "why": "한 줄"}"""

PRODUCT_PICK = """너는 제품 특정 담당이다. 원본 영상 장면 시트에서 연예인이 쓰는 그 제품의 **전체 모양**이 보이는 장면을 2~4개 골라라
(포장 라벨·로고가 보이는 장면이 최고, 너무 작게 부분만 자르지 않는다). 시트는 1초 간격, 왼쪽 위부터 첫 칸 = 아래 적힌 시작 초.
JSON 하나: {"scenes": [{"t": 받은 파일 초, "crop": [x, y, w, h]  (원본 영상 픽셀)}], "brand_words": ["원본 대사·화면에 나온 브랜드·제품 이름"], "coupang_queries": ["쿠팡 검색어 2~4개"]}"""

PRODUCT_SAME = """너는 같은 제품 판정 담당이다(사장님 "쿠팡에서 정확한 거"). 원본 장면 사진과 쿠팡 후보(이름·대표 이미지)를 대조해
포장·로고·모양·색이 **같은 제품**인 후보 하나를 골라라. 비슷한 제품 대체 금지. 없으면 product_id ''.
JSON 하나: {"product_id": "쿠팡 상품번호 또는 ''", "name": "정식 제품명(브랜드·모델·색)", "why": "대조 근거 한 줄", "category": "화장품|식품|생활|의류|의약품|의료기기|기타"}"""

NAME_FIND = """너는 제품 이름 찾기 담당이다. 연예인이 방송·유튜브에서 쓴 제품의 이름을 포털(네이버)·유튜브 검색 글에서 찾아라.
그 연예인이 쓴 바로 그 제품을 가리키는 글만 근거다(다른 연예인·다른 제품 글 금지). 지어내지 마라. 못 찾으면 names 빈 목록.
JSON 하나: {"names": [{"name": "브랜드 제품명", "evidence": "글 그대로 한 줄", "where": "블로그|뉴스|유튜브 제목|본인 채널"}], "kind": "제품 종류 한 줄(예: 눈가 세정 티슈)"}"""

PRODUCT_NAMED = """너는 같은 제품 판정 담당이다(원본 화면에 상표가 안 보여 포털·유튜브 글로 제품 이름을 찾은 경우). 찾은 이름과 근거를 보고
쿠팡 후보 중 그 이름(브랜드·제품명)과 **같은 제품** 하나를 골라라. 근거가 '그 연예인이 쓴 그 제품'을 가리키지 않으면 고르지 마라. 없으면 product_id ''.
JSON 하나: {"product_id": "…", "name": "…", "why": "근거 한 줄(어느 글에 무엇이라고)", "category": "화장품|생활용품|식품|의류|의약품|의료기기|기타"}"""

PRODUCT_GIVEN = """너는 제품 확인 담당이다. 원본 영상에 제품이 화면으로 나오지 않아(말로만 소개) 고객이 쓸 쿠팡 제품을 정해 줬다.
쿠팡 후보 중 고객이 정한 그 제품(브랜드·제품명, 상품번호가 있으면 그 번호)과 같은 것 하나를 골라라. 용량·개수 묶음은 달라도 된다. 없으면 product_id ''.
JSON 하나: {"product_id": "…", "name": "…", "why": "근거 한 줄", "category": "화장품|생활용품|식품|의류|의약품|의료기기|기타"}"""

PRODUCT_BEST = """너는 대체 제품 고르기 담당이다(같은 제품이 없으면 쿠팡에서 후기 많고 제일 좋은 제품). 연예인이 쓴 것과 **같은 종류·같은 쓰임**인 쿠팡 후보 중
후기(rating 의 괄호 숫자) 많고 별점 높은 것 하나를 골라라. 광고(is_ad)·묶음 이상한 것은 뒤로. 같은 종류가 없으면 product_id ''.
JSON 하나: {"product_id": "…", "name": "…", "why": "고른 이유 한 줄(후기 수·별점)", "member_why": "회원에게 보일 쉬운 말 한 줄 — 종류·색·모양이 어떻게 비슷한지(예 '같은 기미 앰플이고 용량·병 모양이 비슷해요')", "category": "화장품|생활용품|식품|의류|의약품|의료기기|기타"}"""

RESEARCH_GIVEN = """

## ★고객이 정한 제품(given) — 연예인이 말한 제품과 다를 수 있다(98 #66 함익병: 원본은 병원 크림, 고객 제품은 화장품)
- 금지 품목 판정(4)은 **고객이 정한 제품** 기준이다. 연예인이 말한 제품이 의약품·다른 회사 제품이어도 그것만으로 멈추지 않는다.
- 원음 spans 는 연예인이 **다른 제품 이름(그 의약품 등)을 말하지 않는** 구간만 — 고민·관리법·원리처럼 그 사람 말 그대로 전할 수 있는 자리(예 '자외선 차단제부터').
- 사실(f)은 고객 제품 것만(브랜드·판매처 문구는 '브랜드 문구'). 연예인 말을 고객 제품의 효과로 잇지 않는다."""

RESEARCH = """너는 조사 담당이다. 이 편의 `조사.md` 한 파일 내용을 써라. 웹 검색으로 사실을 확인하고 출처 URL 을 적는다.
## 할 일
1. 원본 자막(원본 초·말)에서 연예인이 **본인 입으로 말한** 제품 구간을 전부 뽑아 표로(원본 초 · 말).
2. 제품 사실: 브랜드 공식·판매처 설명 · 리뷰 2개 이상 · 연예인 본인 말 — 출처별 표. 시험 수치가 아닌 것은 '브랜드 문구'로 표시. 최상급·범위 숫자 단정 금지.
3. 금지 품목(의약품·의료기기·기능성 화장품 효능 주장)인지 결론 1줄. 멈출 이유가 있으면 stop 에 적는다.
4. 재료 영상 검색어 5~8개(제품명·영문명·모델) + 뺄 단어(모음·TOP·가성비).
5. 원음으로 쓸 구간 spans: 연예인 본인이 그 제품을 말하는 자리만, **받은 파일 초**(= 원본 초 − 아래 offset). 남의 말·웅얼거림(작은 소리) 제외. 한 구간 2~6초, 2~4개(O1·O2…).
## 조사.md 머리글(이 순서 그대로)
## 0 결론 / ## 1 출처 / ## 2 원음 / ## 3 사실(f번호 + 출처 URL 또는 '원본 n초') / ## 4 금지 품목 / ## 5 검색어 / ## 6 확인 못 한 것
## 금지
지어내기 · 수치 어림 · 원본에 없는 말을 본인 말로 적기 · 다른 브랜드 제품을 같은 제품으로 적기 · 다른 회사 숫자(판매량 등) · 질병 이름.
JSON 하나: {"stop": "", "조사_md": "마크다운 전문", "keywords": ["제품명", "영문명", "모델"], "queries": ["…"], "exclude": ["모음", "TOP", "가성비"],
 "spans": [{"a": 받은 파일 초, "b": 초, "tag": "O1"}], "facts": [{"id": "f1", "fact": "…", "src": "URL 또는 '원본 n초'"}]}"""

SCREEN_PICK = """너는 제품 영상 고르기 담당이다. 같은 제품만, 1080 이상, 남의 글자가 가운데 상시면 뺀다, 제품 컷이 많은 것 앞으로, 2~4개.
★연예인이 나오는 영상은 찾은 원본(연예인 본인 채널·방송사 공식)에서만 쓴다 — 다른 채널(벤치 쇼츠·재편집·리뷰)에 나온 연예인 영상은 절대 금지. 후보에 그 연예인이 나오면 rejected.
★남의 리뷰 영상에 장면 전환 효과(별·와이프)·남의 손 근접이 많으면 뒤로. 원본 안에 제품 근접 장면이 있으면 그게 먼저다(재료가 모자랄 때만 이 후보).
각 후보의 시트(미리보기 = 영상 전체 약 5초 간격, 칸 왼쪽 위 노란 '분:초' = 그 영상 시각 · 미리보기가 없는 후보는 360p 토막)와 메타가 있다. sections 는 그 영상의 초. 쓸 게 없으면 chosen 빈 목록.
JSON 하나: {"chosen": [{"id": "…", "why": "…", "sections": [[a, b]]}], "rejected": [{"id": "…", "why": "…"}]}"""

SHOT_READ = """너는 원본 샷 판독 담당이다. 방송·영상 원본을 카메라가 바뀌는 곳마다 나눈 샷들의 가운데 장면이다(칸마다 '#번호 시작~끝초').
샷마다: who = "main"(주인공 {celeb} 혼자 또는 크게) · "both"({celeb}와 다른 사람 함께) · "other"({celeb} 없이 다른 사람만) · "none"(사람 없음),
product = 그 제품({kind})이 또렷이 보이면 true, text = 영상 위에 덧씌운 글자·자막·로고·프로그램 제목 띠마다 [x0,y0,x1,y1](0~1, 왼쪽 위 기준, 없으면 []), cx = 주인공 얼굴 가운데의 가로 위치(0=왼쪽 끝~1=오른쪽 끝, 주인공이 없으면 null), desc = 한국어 10자 안팎. 주인공은 옷·머리·얼굴로 알아본다(같은 영상 안 다른 칸과 비교).
JSON 하나: {{"shots": [{{"i": 번호, "who": "main", "product": false, "text": [[0.1, 0.85, 0.9, 0.95]], "cx": 0.5, "desc": "…"}}]}}"""

SCRIPT = """너는 대본 작가다(오푸스). 아래 판 규칙·결 기준 그대로 이 편의 대본·재료·근거를 써라. 대본 검사를 통과해야 한다 — 걸린 이유가 아래에 있으면 고쳐서 다시.
원음 줄(kind orig)의 src 는 원본 파일 이름, spans 는 그 파일 초. 원음 자막(caps_rel)은 받아쓰기 오류를 문맥으로 바로잡아 적는다(예: '눈꽃'→'눈곱').
재료의 cand_dir 는 비워 둔다(PC 가 채운다), 컷 src 는 재료 파일 이름.
## 결(내용) 기준 — 틀만 채우면 제품 소개문이 된다
- 연예인 훅 = [그 사람을 보여 주는 수식어(근거 있는 것)] + 이름 + [얼마나·어떻게 쓰나] + '~다는데(요)?' — 정체는 숨겨 잉?(답은 뒤 줄).
- 체험 첫 줄 = "저도 이거 보고 바로 따라 사 봤는데요" 꼴(말투 '따라 사 봤는데' — '따라 샀는데' 금지).
- 와우 3줄: 줄 머리에 강한 연결어('근데 진짜 놀라운 건'·'심지어'·'이게 미친 포인트인 게') + 근거 번호 있는 새 사실.
  ★와우·체험 줄의 근거 = **쿠팡 베스트 후기(r번호) 또는 네이버 후기·블로그 글(n번호 — 그 상품 이야기인 부분만)에 실제 사용자가 꼽은 셀링포인트·소구점**(수납·무게·어울림·끈·마감 등 — '후기 보니까 ~래요/~더라고요' 전언) 또는 조사 사실(f번호). (사장님 10-22)
  ★후기 개수·평점·별점 숫자는 쓰지 않는다(소구점이 아니다).
- 권위 1줄(브랜드 유래·연도·나라·판매 기록 — 조사.md 사실 번호, 전언 '~하더라고요/~대요') · 비유 1줄('~같아요') · 끝 줄 = 사회 반응(품절·기사·입소문).
  ★판 틀의 권위 칸에 성분·효능·과학 근거를 쓸 때는 **근거가 있을 때만**. 사회 반응·인기·사연은 과장·약간의 창작 허용(사장님 10-25)
  (10-22 강주은 실사고: '모양이 꼭 기본 흰 셔츠 같아요'·'가방 정리글까지 돈다니' — 근거 없음).
  ★비유는 같은 쓰임끼리만(가방↔가방·지갑, 화장품↔화장품). 다른 종류 물건에 빗대지 않는다(가방을 셔츠에 ✗).
- CTA 없음 · 금액 없음 · 질병·효능 단정 없음 · 다른 회사 숫자 없음. 창작 허용(사장님 10-25) = 화자의 계기·감상·비유·사연·회사 이야기·인기·반응 과장('떼돈·난리·품절 대란') / 근거 필수 = 성분·원료 · 효능·효과(건강·피부·의학) · 과학적 근거(원리·연구·실험·인증·기관) · 안전성(줄마다 facts).
## 읽는 글(tts)
- 렌더러가 읽는 칸은 tts 하나. 줄 끝 문장부호 필수. 숫자·영문·기호는 읽는 대로('100%'→'백 퍼센트', '2024년'→'이천이십사 년'), 자막(caps)은 원문.
- ★자막(caps 를 이은 글)은 읽는 말과 같게 — 다르게 해도 되는 건 숫자·영문 읽기와 발음 고침뿐.
- 미나 목소리가 자주 틀리게 들리는 말 → 대신 쓸 말(자막도 같이 바꾼다): '따라 사 봤는데요'→'하나 사서 따라 해 봤어요' · '대체'→'도대체' · '꾸덕'→'묵직해서' ·
  '울퉁불퉁'→'제각각이라' · 이름 뒤 '이'(김영옥이)→'선생님이/씨가' · 첫 낱말이 브랜드면 앞에 한 낱말('요즘 설화수…').
- 조사·어미를 빼지 않는다(명사 3개 이상 조사 없이 연속 금지). 판 길이를 넘치면 글을 줄인다(배속 아님).
## 재료(컷)
- 컷마다 see(무엇이 보이나) — 그 줄 대사의 동작·상태가 그 컷에 보여야 한다. 같은 소스 ±3초 재사용 금지 · A-B-A 끼움 금지 · 컷 ≥1.2초 · 끝 컷 ≥1.5초.
- ★연예인 장면(face 가 사람)은 원본 파일에서만. 제품 컷도 원본 안 제품 장면이 먼저.
- ★대체 제품(제품 판정 mode alt — 연예인 것과 다른 제품)이면 원음이 끝난 뒤 제품 이야기 줄에는 연예인 장면을 쓰지 않는다(연예인이 대체품을 말하는 것처럼 보인다) — 제품 사진·재료 영상만.
  같은 제품(exact·named)이면 연예인이 그 제품을 쓰는 장면을 함께 써도 된다(사장님 10-22). ★확대는 1.0(crop 높이 = 원본 높이, 'face' 가 기본) — 원본에 박힌 자막·워터마크·다른 브랜드 글자는 재료.blur {원본 파일: [[x, y, w, h, 시작초, 끝초]]} 로 흐린다(잘라서 피하지 않는다 — 사장님 10-22). 얼굴을 크게 보이려면 확대 말고 얼굴이 큰 샷을 고른다.
- 0초 첫 컷 = 연예인 얼굴 크게(제품 컷으로 시작 금지). 주인공 컷은 원본 샷 표의 who main·both 샷 안에서, 컷 길이가 그 샷 끝을 넘지 않게.
## 근거.md
'| 줄 | 말 | 근거 |' — 줄마다 한 줄(원본 초 · 사실 번호 · URL). 근거 줄 수 = 대본 줄 수. 쿠팡 상품번호도 적는다.
JSON 하나: {"대본": {…}, "재료": {"cuts": {…}}, "근거_md": "…"}"""

PLAN_LOOK = """너는 장면 검수 담당이다. 계획 시트를 보고 컷마다: 대사와 화면이 맞나 · 남의 신체 근접 · 남의 글자·원본 자막 띠 · 0초·훅 = 연예인 얼굴 · A-B-A 끼움.
★주인공은 칸 가운데. 원본 샷 표의 '글자'(박힌 글자 상자 — 0~1 **비율**)는 잘라서 피하지 말고 재료.blur 로 흐린다(확대 1.0, 사장님 10-22). ★crop 은 **원본 픽셀 정수**[x, y, w, h](비율 × 원본 가로·세로) — 숫자 crop 은 엔진이 바꾸지 않는다(정한 그대로 렌더).
★연예인이 나오는 영상은 찾은 원본에서만 — 다른 채널 연예인 영상 절대 금지. 사람 얼굴 컷(face)은 원본 파일만, 제품 컷도 원본 안 제품 장면이 먼저. 시트 칸 = 렌더러가 실제로 자를 화면 그대로다.
★crop 'face' 는 원본 **높이 전체**(확대 1.0)다 — 숫자 crop 으로 좁혀 확대하지 않는다(높이 < 원본 높이의 95% 면 반려). 원본에 편집 자막·제목 띠가 박혀 있으면 재료.blur {원본 파일: [[x, y, w, h, 시작초, 끝초]]}(원본 픽셀·원본 초)로 흐린다. 얼굴이 작으면 확대 말고 얼굴이 큰 샷으로 바꾼다.
고칠 것이 있으면 재료 전체를 고쳐서 돌려준다(없으면 null).
★우리 틀(결함 아님): 맨 위 제목 2줄 · 화면 왼쪽 위 '얜샷템' 로고 · 화면 아래 '출처: …' 줄 · 우리 자막(가운데 아래, 색 강조) — 이것들은 남의 글자·워터마크가 아니다.
JSON 하나: {"ok": true, "problems": ["…"], "재료": null}"""

FINAL_LOOK = """너는 완성본 검수 담당이다. 1초 시트를 보고: 틀·제목·자막 자리·출처 줄, 줄마다 화면이 대사와 맞나, 남의 얼굴·손·글자(원본 편집 자막·워터마크) 없나,
0초 = 연예인 얼굴 크게. 남의 채널 연예인 장면·장면 전환 효과(별·와이프)가 섞였나. 받아쓰기와 대본 글자도 대조한다(받아쓰기 한 모델만 틀린 건 결함이 아닐 수 있다).
★우리 틀(결함 아님): 맨 위 제목 2줄 · 화면 왼쪽 위 '얜샷템' 로고 · 화면 아래 '출처: …' 줄 · 우리 자막(가운데 아래, 색 강조) — 이것들은 남의 글자·워터마크가 아니다.
JSON 하나: {"ok": true, "problems": ["…"]}"""


# ── 응답 꼴 ────────────────────────────────────────────────────────────────
def _fmt(st: dict) -> str:
    return st.get("fmt") or "연예인형"        # fmt 칸이 없는 상태 = 08 이전에 시작한 편(전부 연예인형이었다) — 새 편은 start 가 꼭 적는다


def _stage_list(st: dict | None) -> list:
    return FORMAT_STAGES.get(_fmt(st or {}), STAGES)


def _stage(phase: str, st: dict | None = None) -> dict:
    lst = _stage_list(st)
    keys = [k for k, _ in lst]
    k = PHASE_STAGE.get(phase, "setup")
    if k not in keys:                     # 그 형식에 없는 단계(쇼핑형 asr 등) — 바로 앞 단계 이름으로
        order = [x for x, _ in STAGES]
        k = next((x for x in reversed(order[:order.index(k) + 1]) if x in keys), "setup") if k in order else "setup"
    return {"no": keys.index(k) + 1, "total": len(lst), "text": dict(lst)[k], "key": k}


def _msg(st: dict, phase: str) -> str:
    sg = _stage(phase, st)
    k, text = sg["key"], dict(_stage_list(st))
    prev = st.get("_shown_stage")
    st["_shown_stage"] = k
    now = text[k] + (" 중" if k not in ("done", "sign") else "")
    if prev and prev != k and prev in text:
        return f"{text[prev]} 완료 → {now}"
    return now


def _rv(rid: str, ask: str, show: list | None = None, model: str = "opus", need: tuple = ()) -> dict:
    return {"id": rid, "model": model, "ask": ask, "show": show or [], "need": list(need)}


def _img(rel: str) -> dict:
    return {"file": rel}


def _txt(s: str) -> dict:
    return {"text": s}


def _coupang_down(m: dict, key: str = "coupang") -> None:
    """쿠팡 검색이 아예 안 됐으면(runner c_coupang search_failed — 회선 막힘 등) '제품 없음'으로 고객에게 다른 영상을 권하지 않는다(사장님 10-26).
    멈춤 → 다시 시도(retry)하면 검색한 단계(_asker)부터 이어 간다."""
    if (m.get(key) or {}).get("search_failed"):
        raise _Stop("쿠팡 검색이 잠시 막혀 있어요", "몇 분 뒤 다시 시도해 주시면 제품 확인부터 이어 갈게요", auto=True)


class _Stop(Exception):
    """멈춤. retry = 다시 시도하면 이어 갈 세부 단계(받기 실패처럼 잠깐의 문제 — 앞 단계 유튜브 요청을 다시 쓰지 않게).
    auto = 잠깐의 문제라 회원에게 알리기 전에 **스스로 한 번** 다시 해 본다(사장님 10-26 '회원을 당황하게 하지 마라').
    detail = 속사정(검사 항목·오류 글) — 기록(st.log·stopped.detail)에만, 회원 문구에는 안 싣는다."""
    def __init__(self, why: str, fix: str = "", retry: str | None = None, final: bool = False, auto: bool = False, detail: str = "",
                 origin_missing: bool = False):
        super().__init__(why)
        self.why, self.fix, self.retry, self.final, self.auto, self.detail = why, fix, retry, final, auto, detail
        self.origin_missing = origin_missing


# ── 회원에게 가는 말(사장님 10-26 "회원을 당황하게 하면 안 된다 — 나는 대처가 되지만 회원은 못 한다") ──────────
# 판단 주인 = member_ok 한 곳: 내부 용어·'멈춤'·다음 행동 없는 문장을 거른다. 걸리면 _out 이 쉬운 일반 문구로 바꾸고 원문은 기록에만.
AGAIN = "다시 시도해 주시면 이어 갈게요"
MEMBER_BAD = ("멈춤", "검사", "retry", "shortem_", "렌더", "재료", "검수", "봇 확인", "지문", "개발팀", "부르세요", "확인 답", "판정", "세부 단계",
              "단계를", "phase", "look", "관문", "runner", "실행기", "Traceback", "error", "Error", "None", "{", "}")
MEMBER_NEXT = re.compile(r"(주세요|까요|게요|있어요|드릴게요|갑니다)")
NO_SIMILAR = ("쿠팡에서 비슷한 제품도 찾지 못했어요", "제품 이름을 알려 주시면 그 이름으로 찾아 이어 갈게요 · 다른 소재로 갈까요?")
NO_ORIGIN = ("원본을 못 찾았어요", "원본 영상 주소를 주시면 바로 만들 수 있어요 · 다른 소재로 갈까요?")
ALT_NOTICE = "같은 물건을 찾지 못해서 가장 비슷한 제품으로 골랐어요"


def member_ok(text: str, need_next: bool = False) -> bool:
    """회원에게 보여도 되는 문장인가 — 비어 있지 않고, 내부 용어·'멈춤'이 없고, (need_next 면) 다음 행동(…주세요·…까요·…게요)이 있다."""
    t = str(text or "").strip()
    if not t or any(b in t for b in MEMBER_BAD):
        return False
    return bool(MEMBER_NEXT.search(t)) if need_next else True


def member_stop(why: str, fix: str) -> tuple[str, str]:
    """멈춤 문구를 회원용으로 — 둘 다 괜찮으면 그대로, 아니면 쉬운 일반 문구(원문은 호출한 쪽이 기록에 남긴다)."""
    w = why if member_ok(why) else "만드는 중에 문제가 생겼어요"
    f = fix if member_ok(fix, need_next=True) else AGAIN + " · 계속 안 되면 숏템 피드백으로 알려 주세요"
    return w, f


ASKER_IN_MAX = 60_000   # 다시 시도용으로 기억할 입력 크기 상한(글자) — 넘으면 그 단계 입력 없이 다시(대개 do 를 다시 내는 단계라 입력이 필요 없다)


def start(ref: str, version: str, sid: str, product: str = "", fmt: str | None = None) -> dict:
    """product = 고객이 정한 쿠팡 제품(이름·상품 주소) — 원본에 제품이 화면으로 안 나올 때 쓴다(사장님 10-23 '실제 올린 채널의 상품을 참고').
    fmt = 형식(서버가 넘기면 그대로 — 단 프리셋 장부와 다르면 거절). 없으면 channel/프리셋.json 에서(flow_format_of). 못 정하면 FormatError."""
    f0, slug = flow_format_of(version)
    if fmt and fmt != f0:
        raise FormatError(f"형식 {fmt} 를 받았지만 판 {version} 은 프리셋 장부에서 {f0} 입니다")
    st = {"sid": sid, "ref": ref, "version": version, "fmt": f0, "slug": slug, "phase": "setup", "tries": {}, "log": []}
    if str(product or "").strip():
        st["given"] = str(product).strip()[:200]
    return st


def step(state: dict, measure: dict | None = None, replies: dict | None = None, user: dict | None = None) -> dict:
    """한 번 호출 = 지난 do·review 결과를 먹고 다음 할 일을 낸다. 같은 호출 안에서 바로 이어 갈 수 있는 단계(goto)는 계속 넘어간다."""
    st = state
    m, rp, user = dict(measure or {}), dict(replies or {}), dict(user or {})
    for _ in range(40):
        ph = st.get("phase") or "setup"
        h = FORMAT_PHASES.get(_fmt(st), {}).get(ph) or PHASES.get(ph)
        m_in, rp_in = m, rp
        if h is None:
            return _out(st, "stop", ph, why="만드는 중에 문제가 생겼어요", fix="숏템 피드백으로 알려 주시면 확인해 드릴게요", detail="알 수 없는 세부 단계 " + str(ph))
        try:
            r = h(st, m, rp, user)
        except _Stop as e:
            # 뿌리(10-22): 멈춤 34곳 중 5곳만 이어 가기 → 고칠 때마다 원본 찾기부터 20~50분 다시. 이제 정한 retry 가 없으면 **마지막으로 일을 시킨 단계**부터(같은 do·질문을 다시)
            retry = None if e.final else (e.retry or st.get("_asker"))
            if e.detail:
                st["log"].append(f"멈춤 속사정({ph}): {str(e.detail)[:400]}")
            ak = f"{retry}:{e.why}"
            if e.auto and retry and not (st.get("auto_tries") or {}).get(ak):      # 회원에게 알리기 전에 스스로 한 번(잠깐의 문제)
                st.setdefault("auto_tries", {})[ak] = 1
                st["log"].append(f"스스로 다시 시도: {e.why} → {retry}")
                st["phase"] = retry
                m, rp, user = {}, {}, {}
                if retry == st.get("_asker") and st.get("_asker_in"):
                    m, rp = st["_asker_in"].get("m") or {}, st["_asker_in"].get("rp") or {}
                continue
            st["phase"] = "stopped"
            st["stopped"] = {"why": e.why, "fix": e.fix, **({"retry": retry} if retry else {}), **({"detail": str(e.detail)[:400]} if e.detail else {}),
                             **({"origin_missing": True} if e.origin_missing else {})}
            return _out(st, "stop", ph, why=e.why, fix=e.fix, retry_ok=True if retry else None)
        m, rp, user = {}, {}, {}           # 한 번 먹은 입력은 다음 단계로 넘기지 않는다
        if "goto" in r:
            st["phase"] = r["goto"]
            if r.get("feed"):                 # 다시 시도 — 그 단계가 처음 받았던 입력을 다시 먹인다
                m, rp = r["feed"].get("m") or {}, r["feed"].get("rp") or {}
            continue
        if "do" in r or "review" in r:
            st["_asker"] = ph                 # 이 단계가 일을 시켰다 — 멈추면 여기부터 다시(받았던 입력도 함께 — 작을 때만, payload 가 커지지 않게)
            feed = {"m": m_in, "rp": rp_in} if (m_in or rp_in) else {}
            st["_asker_in"] = feed if len(json.dumps(feed, ensure_ascii=False)) <= ASKER_IN_MAX else None
        if "do" in r:
            st["phase"] = r["then"]
            return _out(st, "execute", r["then"], do=r["do"])
        if "review" in r:
            st["phase"] = r["then"]
            return _out(st, "reject" if r.get("reject") else "review", r["then"], review=r["review"], reject=r.get("reject"))
        if "wait" in r:
            st["phase"] = r["then"]
            return _out(st, "wait_user", r["then"], wait=r["wait"])
        if "done" in r:
            st["phase"] = "done"
            return _out(st, "done", "done", **r["done"])
    return _out(st, "stop", st.get("phase"), why="만드는 중에 문제가 생겼어요", fix="숏템 피드백으로 알려 주시면 확인해 드릴게요", detail="세부 단계가 40번 돌기만 함")


def _out(st: dict, status: str, phase: str, **kw) -> dict:
    stage = _stage(phase, st)
    traps = (TRAPS_FOREIGN if _fmt(st) == "해외원본형" else TRAPS).get(stage["key"], [])
    res = {"status": status, "stage": stage, "message": _msg(st, phase), "traps": traps, "state": st}
    for k, v in kw.items():
        if v is not None and k != "detail":
            res[k] = v
    if kw.get("detail"):
        st["log"].append(f"멈춤 속사정: {str(kw['detail'])[:400]}")
    if status == "stop":
        w, f = member_stop(str(kw.get("why") or ""), str(kw.get("fix") or ""))
        if (w, f) != (kw.get("why"), kw.get("fix")):
            st["log"].append(f"회원 문구로 바꿈: {kw.get('why')} / {kw.get('fix')}")
        res["why"], res["fix"] = w, f
        res["message"] = f"{w} — {f}"
    elif st.get("notice") and not st.get("_notice_shown"):     # 회원에게 한 번 알릴 것(비슷한 제품으로 골랐다 등) — 진행 한 줄 뒤에
        st["_notice_shown"] = True
        res["message"] = f"{res['message']} · {st['notice']}"
        res["notice"] = st["notice"]
    return res


def _tries(st: dict, key: str, limit: int) -> int:
    n = st["tries"].get(key, 0) + 1
    st["tries"][key] = n
    if n > limit:
        st["log"].append(f"고치기 한도: {key} {limit}번")
        raise _Stop("여러 번 고쳐 봤지만 아직 마무리가 안 됐어요", "다시 시도해 주시면 멈춘 곳부터 이어 갈게요")
    return n


def _reply(rp: dict, rid: str, need: tuple = ()) -> dict:
    a = rp.get(rid)
    if not isinstance(a, dict):
        raise _Stop("확인 결과를 받지 못했어요", "다시 시도해 주시면 멈춘 곳부터 이어 갈게요", auto=True)
    miss = [k for k in need if k not in a]
    if miss:
        raise _Stop("확인 결과가 덜 채워졌어요", "다시 시도해 주시면 멈춘 곳부터 이어 갈게요", auto=True)
    return a


def _style(version: str) -> dict:
    from tools.calcopy.hybrid import styles as STY
    return STY.load(version)


def _ar(version: str) -> float:
    _, _, ww, wh = _style(version)["frame"]["window"]
    return ww / wh


# ── 0 준비 ────────────────────────────────────────────────────────────────
def ph_setup(st, m, rp, u):
    return {"do": [{"id": "env", "cmd": "env", "version": st["version"]}], "then": "setup_check"}


def ph_setup_check(st, m, rp, u):
    env = m.get("env") or {}
    if env.get("error"):
        st["log"].append("준비 확인 실패: " + str(env["error"])[:300])
        raise _Stop("이 PC 준비가 아직 덜 됐어요", "숏템 준비 점검을 한 번 한 뒤 다시 시도해 주세요")
    voice = (_style(st["version"]).get("voice") or {}).get("voice_id", "")
    need = "elevenlabs" if voice.startswith("kr-mina") else "typecast"
    if not (env.get("keys") or {}).get(need) and not env.get("dev"):
        raise _Stop("목소리 키가 없어요", f"설정 화면 '소리' 칸에 {'일레븐랩스' if need == 'elevenlabs' else '타입캐스트'} 키를 넣어 주세요")
    if float(env.get("disk_gb") or 99) < 1.5:
        raise _Stop("PC 저장 공간이 모자라요(1편에 1.5GB)", "C 드라이브 공간을 비운 뒤 다시 시도해 주세요")
    st["env"] = {k: env.get(k) for k in ("keys", "dev", "cache", "asr")}
    return {"goto": "bench"}


# ── 1 소재(벤치) ──────────────────────────────────────────────────────────
def ph_bench(st, m, rp, u):
    return {"do": [{"id": "bench", "cmd": "bench", "url": st["ref"]}], "then": "bench_got"}


def ph_bench_got(st, m, rp, u):
    b = m.get("bench") or {}
    if b.get("error"):
        raise _Stop("영상을 받지 못했어요", "영상 주소가 맞는지, 유튜브 로그인 연결이 되어 있는지 확인해 주세요", auto=True)
    st["bench"] = {k: b.get(k) for k in ("id", "title", "channel", "date", "dur", "desc", "sheet", "big")}
    st["bench_lines"] = b.get("lines") or []
    return {"review": [_rv("origin_read", ORIGIN_READ + "\n\n제목: " + str(b.get("title")) + "\n채널: " + str(b.get("channel")) +
                           "\n설명: " + str(b.get("desc") or "")[:1500] + "\n받아쓰기: " + " / ".join(str(l.get("text")) for l in st["bench_lines"])[:3000],
                           ([_img(b["sheet"])] if b.get("sheet") else []) + ([_img(b["big"])] if b.get("big") else []),
                           need=("celeb", "queries", "is_shopping"))], "then": "origin_read"}


# ── 2 원본 찾기 ───────────────────────────────────────────────────────────
def ph_origin_read(st, m, rp, u):
    r = _reply(rp, "origin_read", ("celeb", "queries", "is_shopping"))
    if not r.get("is_shopping"):
        raise _Stop("연예인이 쓰는 물건이 나오는 영상이 아니에요", "연예인 쇼핑 쇼츠 주소를 주세요", final=True)
    st["read"] = r
    label = re.sub(r"^\s*출처\s*[:：]?\s*", "", r.get("source_label") or "").strip()
    if not label:      # 출처 표기 = 원본으로 가는 길(사장님 10-22 "무조건 표기해야 문제가 안 생긴다 · 없으면 패스")
        raise _Stop("화면과 설명란 어디에도 출처가 없는 쇼츠라 원본을 찾을 수 없어요", "출처가 적힌 다른 쇼츠 주소를 주세요 · 다른 소재로 갈까요?")
    celeb = str(r.get("celeb") or "")
    sk = str(r.get("source_kind") or "")
    if sk.startswith("sns") or re.search(r"인스타|instagram|틱톡|tiktok|블로그|blog", label, re.I):
        st["src"] = {"label": label, "kind": "sns"}     # 10-22 이영애 '이영애 인스타그램' → 엉뚱한 유튜브 채널(Famous Woman)을 뒤졌다
        st["log"].append(f"출처 '{label}' = SNS(원본이 아니다 — 사장님 10-22) → 검색 길로 진짜 원본")
        return {"goto": "search"}                       # 인스타 출처는 거쳐 온 곳 — '<연예인> <제품 낱말>' 검색·지문 대조로 진짜 원본을 찾는다
    kind = "program" if sk.startswith("program") else "channel"
    st["src"] = {"label": label, "kind": kind}         # 출처 = 채널 이름인가 프로그램 이름인가 — 편 상태·작업 기록에 남겨 다시 시도할 때도 같은 길(사장님 10-22). 고객 진행 줄에는 단계만(세부 금지)
    st["log"].append(f"출처 '{label}' = {'프로그램 이름' if kind == 'program' else '채널 이름'}")
    return {"do": [{"id": "src", "cmd": "channel_find", "label": label, "kind": kind, "celeb": "" if celeb == "불명" else celeb, "n": 60,
                    "words": [w for w in r.get("product_words") or [] if w][:2], "queries": _src_queries(r)}], "then": "src_got"}


def _src_queries(r: dict) -> list[str]:
    """출처 채널 안 검색어 — 원본 판독이 낸 검색어(연예인 + 제품·방법 낱말) 앞 2개. 없으면 연예인 + 제품 낱말(98 #65)."""
    qs = [q for q in r.get("queries") or [] if q][:2]
    celeb = "" if (r.get("celeb") or "") == "불명" else str(r.get("celeb") or "")
    return qs or [f"{celeb} {w}".strip() for w in (r.get("product_words") or [])[:2] if w]


SRC_PROBE = 10       # 출처 채널에서 조사할 후보 수(최신순, 벤치보다 먼저 올라온 것만)


def ph_src_got(st, m, rp, u):
    """출처 채널 영상 목록 → 후보 조사(origin_probe: 한 번 요청으로 날짜·자막·스토리보드). 채널을 못 찾으면 검색 길로."""
    f = m.get("src") or {}
    if f.get("blocked"):
        raise _Stop("유튜브가 잠시 요청을 막았어요", "잠시 뒤 다시 시도해 주시면 이어서 찾을게요 · 유튜브 로그인 연결도 확인해 주세요", auto=True)
    B, r = st["bench"], st["read"]
    cands = [t for t in f.get("titles") or [] if t["id"] != B.get("id") and (t.get("dur") or 0) > (B.get("dur") or 0) + 20]
    # 제목에 연예인 이름·장면·제품 낱말이 든 영상 먼저, 그다음 최신순(98 #58: 선우용여 '여주 아울렛' 원본은 반년 전 영상이라 최신 10편에 없었다 ·
    #   함익병은 남의 채널(이성미의 나는 꼰대다) 손님이라 최신 편은 전부 다른 손님 — 손님 편 제목엔 이름이 든다)
    tw = {RU.norm(w) for w in [r.get("celeb") or ""] + (r.get("scene_words") or []) + (r.get("product_words") or []) if len(RU.norm(w)) >= 2}
    # 채널 안 검색에 걸린 영상이 맨 앞(검색 순위대로) — 98 #65 셀코TV 함익병 기미: 원본이 최신 60편 밖
    srank = {v: i for i, v in enumerate(f.get("searched") or [])}
    cands = sorted(cands, key=lambda t: (srank.get(t["id"], 99), -sum(1 for w in tw if w in RU.norm(t.get("title") or ""))))[:SRC_PROBE]
    if not cands:
        st["log"].append("출처 채널을 못 찾아 검색 길로: " + json.dumps(f.get("channels") or [], ensure_ascii=False)[:300])
        return {"goto": "search"}
    ch = (f.get("picked") or [{}])[0]
    st["src_channel"] = {**ch, "how": f.get("how")}
    st["src"] = {**(st.get("src") or {}), "how": f.get("how"), "channel": ch.get("name") or ", ".join(sorted({c.get("channel") or "" for c in cands} - {""}))[:80]}
    st["mixed"] = [{**c, "channel": c.get("channel") or ch.get("name")} for c in cands]
    st["src_mixed"] = st["mixed"]
    st.setdefault("origin_tried", []).append("src")
    terms = [w for w in (r.get("scene_words") or []) + (r.get("product_words") or []) if w][:8]
    return {"do": [{"id": "probe", "cmd": "origin_probe", "ids": [c["id"] for c in cands], "before": str(B.get("date") or ""), "terms": terms,
                    "max_sheets": 4}], "then": "probe_got"}


ORIGIN_SB = """너는 원본 판정 담당이다. 벤치 쇼츠의 말이 원본 자막과 맞지 않았다(벤치 = 내레이션). 첫 그림 = 벤치 1초 장면 시트,
그 뒤 그림 = 출처 채널 후보 영상마다 **영상 전체 미리보기 시트**(칸 왼쪽 위 노란 글자 = 원본 분:초).
**같은 사람·같은 옷·같은 제품·같은 장소**가 벤치와 같은 후보 하나를 골라라(비슷한 물건만으론 아니다). 그 제품이 잘 보이는 칸의 시각을 초로 적어라.
없으면 origin_id ''.
JSON 하나: {"origin_id": "유튜브 id 또는 ''", "origin_t": [초, …], "why": "한 줄"}"""


def ph_probe_got(st, m, rp, u):
    p = m.get("probe") or {}
    if p.get("blocked") and not (p.get("matched") or p.get("sheets")):
        raise _Stop("유튜브가 잠시 요청을 막았어요", "잠시 뒤 다시 시도해 주시면 이어서 찾을게요 · 유튜브 로그인 연결도 확인해 주세요", auto=True)
    st["probe_sb"] = {"sheets": p.get("sheets") or {}, "hits": p.get("hits") or {}, "dates": p.get("dates") or {}}
    if p.get("matched"):                                     # 벤치 말 = 원본 말 → 지금까지의 판정 그대로
        return ph_subs_got(st, {"subs": {"matched": p["matched"], "hits": p.get("hits") or {}}}, rp, u)
    if not (p.get("sheets") or {}):
        st["log"].append("출처 채널 후보에 지문·미리보기가 없어 검색 길로")
        return {"goto": "search"}
    return _sb_review(st)


def _sb_review(st) -> dict:
    """출처 채널 후보의 미리보기(스토리보드) 시트로 같은 사람·옷·제품·장소 대조(02 §2-1 끝줄)."""
    pb = st.get("probe_sb") or {}
    sheets, hits, dates = pb.get("sheets") or {}, pb.get("hits") or {}, pb.get("dates") or {}
    st.setdefault("origin_tried", []).append("sb")
    order = sorted(sheets, key=lambda v: -len({h["term"] for h in hits.get(v) or []}))[:4]
    st["sb"] = {v: sheets[v] for v in order}
    B = st["bench"]
    title = {c["id"]: c.get("title") for c in (st.get("src_mixed") or st.get("mixed") or [])}
    return {"review": [_rv("origin_sb", ORIGIN_SB + f"\n\n벤치: {B.get('title')} ({B.get('date')})\n후보(그림 순서): " +
                           " / ".join(f"{v} {title.get(v)} ({dates.get(v)})" for v in order),
                           ([_img(B["sheet"])] if B.get("sheet") else []) + [_img(sheets[v]["file"]) for v in order],
                           need=("origin_id", "origin_t"))], "then": "sb_pick"}


def _origin_next(st, why: str) -> dict:
    """원본 찾기의 한 길이 빈손이면 **02_원본찾기 순서대로 다음 길**(사장님 10-26 '연예인 편은 출처가 다 있어 못 찾을 수가 없다 — 방법을 끝까지').
    ① 출처 채널 지문(src) → ② 출처 채널 미리보기 대조(sb) → ③ 검색 길(search: 본인 채널·방송사·그 밖) → ④ 화면 대조(vis) → 그래도 없을 때만 회원에게
    '원본을 못 찾았어요 — 주소를 주시면 바로 · 다른 소재?'(주소를 받으면 ph_stopped → _given_origin 으로 바로 이어 간다)."""
    st["log"].append(f"원본 찾기: {why} → 다음 길")
    tried = st.setdefault("origin_tried", [])
    st.pop("origin", None)
    pb = st.get("probe_sb") or {}
    left = {v: x for v, x in (pb.get("sheets") or {}).items() if v not in (st.get("sb") or {})}
    if "sb" not in tried and left:
        st["probe_sb"] = {**pb, "sheets": left}
        return _sb_review(st)
    if "search" not in tried:
        return {"goto": "search"}
    if "vis" not in tried and st.get("vis"):
        return {"goto": "vis_get"}
    raise _Stop(*NO_ORIGIN, origin_missing=True, detail="시도한 길: " + ", ".join(tried))


def ph_sb_pick(st, m, rp, u):
    a = rp.get("origin_sb") or {}
    oid = str(a.get("origin_id") or "")
    ts = [float(t) for t in a.get("origin_t") or [] if isinstance(t, (int, float))]
    if oid not in (st.get("sb") or {}) or not ts:
        return _origin_next(st, "출처 채널 미리보기 대조에서 같은 장면 없음")
    c = next((c for c in (st.get("src_mixed") or st.get("mixed") or []) if c["id"] == oid), {"id": oid})
    dur = float(c.get("dur") or max(ts) + 600)
    st["origin"] = {"id": oid, "url": f"https://www.youtube.com/watch?v={oid}", "matched": [{"bench": "(화면 대조)", "origin_t": t} for t in ts],
                    "window": [0.0, dur], "visual": True, "info": {k: c.get(k) for k in ("id", "title", "channel", "dur")}}
    st["log"].append(f"원본 = 출처 채널 미리보기 대조({oid}): {a.get('why')}")
    return {"do": [{"id": "origin", "cmd": "origin_get", "vid": oid, "a": 0.0, "b": dur, "ts": [], "full": True}], "then": "origin_got"}


def ph_peer(st, m, rp, u):
    p = m.get("peer") or {}
    if not p.get("sheet"):
        return {"goto": "search"}
    return {"review": [_rv("peer_read", PEER_READ + f"\n\n연예인: {st['read'].get('celeb')}", [_img(p["sheet"])], need=("labels",))],
            "then": "peer_read"}


def ph_peer_read(st, m, rp, u):
    a = rp.get("peer_read") or {}
    out = []
    for x in a.get("labels") or []:
        for k in ("source", "program"):
            v = re.sub(r"^\s*출처\s*[:：]?\s*", "", str((x or {}).get(k) or "")).strip()
            if v and v not in out:
                out.append(v)
    st["peers"] = out
    return {"goto": "search"}


def _queries(st) -> list[str]:
    r = st["read"]
    label = re.sub(r"^\s*출처\s*[:：]?\s*", "", r.get("source_label") or "").strip()
    name = str(r["celeb"]) if r.get("celeb") and r["celeb"] != "불명" else ""
    # 고정 검색어를 늘 먼저 — AI 가 판마다 검색어를 새로 지어 같은 영상인데 원본이 걸렸다 안 걸렸다 했다(10-21 #7)
    fixed = [name, f"{name} {label}".strip(), f"{name} 꿀템"] if name else []
    words = [w for w in r.get("product_words") or [] if w]
    prod_q = ([f"{name} {w}".strip() for w in words[:2]] if name else []) + [q for q in r.get("queries") or [] if q]
    # 제품 낱말 검색어 먼저 — 이름만 검색하면 그 채널 일반 영상이 후보 자리를 다 차지한다(10-21 정재형 실전: 원본 후보 16개가 전부 토크·룸투어)
    qs = [q for q in prod_q + fixed + ([label] if label else []) + ([r["channel_hint"]] if r.get("channel_hint") else []) if q]
    peers = [p for p in st.get("peers") or [] if RU.norm(p) not in RU.norm(label)]
    if peers:
        r["channel_hint"] = " / ".join([r.get("channel_hint") or ""] + peers)
        qs = qs[:3] + [f"{name} {p}".strip() for p in peers[:2]] + qs[3:]
    return list(dict.fromkeys(qs))[:10]


def ph_search(st, m, rp, u):
    st.setdefault("origin_tried", []).append("search")
    return {"do": [{"id": "search", "cmd": "search", "queries": _queries(st), "n": 12}], "then": "search_got"}


def _channels_of(found: list[dict], r: dict) -> list[str]:
    """원본을 뒤질 채널 — ① 연예인 **본인 채널**(사장님 10-21 "연예인 본인 채널이 1순위") ② 출처 글자·채널 단서와 맞는 채널."""
    hint = RU.norm((r.get("source_label") or "").replace("출처", "") + (r.get("channel_hint") or ""))
    celeb = RU.norm(r.get("celeb") or "")
    own, other = [], []
    for c in found:
        name, cid = RU.norm(c.get("channel") or ""), c.get("channel_id")
        if not cid or not name or cid in own or cid in other:
            continue
        if len(celeb) >= 2 and celeb in name:
            own.append(cid)
        elif name in hint or (hint[:6] and hint[:6] in name):
            other.append(cid)
    return own + other


def ph_search_got(st, m, rp, u):
    found = (m.get("search") or {}).get("found") or []
    r, B = st["read"], st["bench"]
    celeb = RU.norm(r.get("celeb") or "")
    hint = RU.norm((r.get("source_label") or "").replace("출처", "") + (r.get("channel_hint") or ""))
    own = lambda c: len(celeb) >= 2 and celeb in RU.norm(c.get("channel") or "")
    cands = [c for c in found if c["id"] != B.get("id") and (c.get("dur") or 0) > (B.get("dur") or 0) + 20]
    pw = [RU.norm(w) for w in r.get("product_words") or [] if len(RU.norm(w)) >= 2]
    def prod_hits(c):          # 제품 낱말이 든 검색어 몇 개에 걸렸나 + 제목에 제품 낱말
        qs = c.get("qs") or [c.get("q")]
        return sum(1 for q in qs if any(w in RU.norm(q or "") for w in pw)) + (2 if any(w in RU.norm(c.get("title") or "") for w in pw) else 0)
    cands.sort(key=lambda c: (not own(c), -prod_hits(c), (celeb[-2:] not in RU.norm(c.get("title") or "")) if celeb else 0,
                              not (RU.norm(c.get("channel") or "") and RU.norm(c.get("channel") or "") in hint)))
    st["cands"] = cands
    ch = _channels_of(found, r)[:3]
    if not ch:
        st["titles"] = []
        return {"goto": "subs"}
    return {"do": [{"id": "chlist", "cmd": "channel_list", "channels": ch, "n": 300}], "then": "titles"}


def ph_titles(st, m, rp, u):
    titles = (m.get("chlist") or {}).get("titles") or []
    st["titles"] = titles
    if not titles:
        return {"goto": "subs"}
    B, r = st["bench"], st["read"]
    revs = []
    for k in range(0, len(titles), TITLE_CHUNK):
        part = titles[k:k + TITLE_CHUNK]
        revs.append(_rv(f"titles_{k // TITLE_CHUNK}", ORIGIN_TITLES + f"\n\n벤치 제목: {B.get('title')}\n제품 낱말: {r.get('product_words')}\n채널 영상 목록(아이디\t제목):\n" +
                        "\n".join(f"{t['id']}\t{str(t.get('title') or '')[:80]}" for t in part), need=("ids",)))
    return {"review": revs, "then": "titles_got"}


def ph_titles_got(st, m, rp, u):
    titles = st.get("titles") or []
    known = {t["id"] for t in titles}
    ids: list[str] = []
    for k in range(0, len(titles), TITLE_CHUNK):
        a = rp.get(f"titles_{k // TITLE_CHUNK}") or {}
        ids += [i for i in a.get("ids") or [] if i in known and i not in ids][:8]
    st["picked"] = [t for t in titles if t["id"] in ids]
    return {"goto": "subs"}


def ph_subs(st, m, rp, u):
    cands, picked = st.get("cands") or [], st.get("picked") or []
    mixed, seen = [], set()
    for k in range(max(len(cands), len(picked))):     # 검색 후보와 채널 목록 후보를 번갈아(#5)
        for c in (cands[k] if k < len(cands) else None, picked[k] if k < len(picked) else None):
            if c and c["id"] not in seen:
                seen.add(c["id"]); mixed.append(c)
    st["mixed"] = mixed[:ORIGIN_TRY]
    if not st["mixed"]:
        return _origin_next(st, "검색 길 후보 0")
    r = st["read"]
    terms = [w for w in (r.get("scene_words") or []) + (r.get("product_words") or []) if w][:8]
    return {"do": [{"id": "subs", "cmd": "origin_subs", "ids": [c["id"] for c in st["mixed"]], "terms": terms}], "then": "subs_got"}


def ph_subs_got(st, m, rp, u):
    sub = m.get("subs") or {}
    got = sub.get("matched") or {}        # 지문 대조 = PC 가 rules.fingerprint 로(자막 낱말은 PC 에 남긴다)
    if sub.get("blocked") and not got:
        raise _Stop("유튜브가 잠시 요청을 막았어요", "잠시 뒤 다시 시도해 주시면 이어서 찾을게요 · 유튜브 로그인 연결도 확인해 주세요", auto=True)
    scored = []
    for c in st.get("mixed") or []:
        mt = got.get(c["id"])
        if mt:
            scored.append({**{k: c.get(k) for k in ("id", "title", "channel", "dur", "views")}, "matched": mt})
    scored.sort(key=lambda c: -len(c["matched"]))
    if not scored:
        vis = _visual_cands(st, sub.get("hits") or {})
        if vis and "vis" not in (st.get("origin_tried") or []):
            st["vis"] = vis
            return {"goto": "vis_get"}
        return _origin_next(st, "후보 자막에 벤치 말 없음")
    st["scored"] = scored[:5]
    B = st["bench"]
    return {"review": [_rv("origin_pick", ORIGIN_PICK + f"\n\n벤치: {B.get('title')} ({B.get('channel')}, {B.get('date')})\n후보:\n" +
                           json.dumps(st["scored"], ensure_ascii=False, indent=1), [_img(B["sheet"])] if B.get("sheet") else [],
                           need=("origin_id", "self_spoken"))], "then": "pick_got"}


VIS_TILES = 120      # 화면 대조 시트 칸 수(8×15)
VIS_TRY = 2          # 화면 대조할 후보 수(원본을 통째로 받는다 — 유튜브 요청·시간이 크다)


def _visual_cands(st, hits: dict) -> list[dict]:
    """말 지문 0(벤치 = 내레이션뿐) → 원본 자막에 장면 낱말이 나온 **본인 채널** 후보만, 장면 낱말 ×3 + 제품 낱말 가짓수 순(10-22 고현정 가방)."""
    r = st["read"]
    scene = {RU.norm(w) for w in r.get("scene_words") or [] if len(RU.norm(w)) >= 2}
    celeb = RU.norm(r.get("celeb") or "")
    out = []
    for c in st.get("mixed") or []:
        h = hits.get(c["id"]) or []
        if not h or not (len(celeb) >= 2 and celeb in RU.norm(c.get("channel") or "")):
            continue
        kinds = {x["term"] for x in h}
        score = 3 * len(kinds & scene) + len(kinds - scene)
        at = [x["origin_t"] for x in h if x["term"] in scene] or [x["origin_t"] for x in h]
        out.append({"id": c["id"], "title": c.get("title"), "channel": c.get("channel"), "dur": c.get("dur"), "score": score, "at": at[:3], "n": len(h)})
    out.sort(key=lambda c: (-c["score"], c["n"]))
    return out[:VIS_TRY]


def ph_vis_get(st, m, rp, u):
    st.setdefault("origin_tried", []).append("vis")
    c = st["vis"][0]
    a, b = 0.0, float(c.get("dur") or max(c["at"]) + 600)       # 통째로 — 제품 장면은 장면 낱말 시각 앞뒤에 없을 수 있다(10-22 고현정 2차: '서촌'=식당, 가방=다른 시각)
    st["origin"] = {"id": c["id"], "url": f"https://www.youtube.com/watch?v={c['id']}", "matched": [], "window": [a, b], "visual": True,
                    "info": {k: c.get(k) for k in ("id", "title", "channel")}}
    return {"do": [{"id": "origin", "cmd": "origin_get", "vid": c["id"], "a": a, "b": b, "ts": [], **({"full": True} if c.get("full") else {})}], "then": "vis_got"}


def ph_vis_got(st, m, rp, u):
    o = m.get("origin") or {}
    if o.get("error") or not o.get("files"):
        raise _Stop("원본 영상을 받지 못했어요", "잠시 뒤 다시 시도해 주시면 받기부터 이어 갈게요", auto=True, retry="vis_get")
    st["origin"].update(files=o["files"], offset=o.get("offset"), offset_measured=False)
    dur = float(_origin_file(st).get("dur") or 600)
    step = max(1, math.ceil(dur / VIS_TILES))                   # 원본 전체를 VIS_TILES 칸으로 훑는다(앞뒤 60초만 보여 주자 가방 장면이 빠져 '다르다'로 판정)
    st["vis_step"] = step
    return {"do": [{"id": "vsheet", "cmd": "sheet", "src": "src/" + _origin_file(st)["name"], "dst": f"look/origin_visual_{st['origin']['id']}.jpg",
                    "fps": round(1 / step, 4), "cols": 8, "rows": VIS_TILES // 8, "w": 200, "ss": 0, "t": dur}], "then": "vis_look"}


def ph_vis_look(st, m, rp, u):
    sh = (m.get("vsheet") or {}).get("file")
    B = st["bench"]
    if not sh:
        return {"goto": "vis_next"}
    return {"review": [_rv("origin_visual", ORIGIN_VISUAL + f"\n\n벤치: {B.get('title')}\n후보: {st['origin']['info'].get('title')} ({st['origin']['info'].get('channel')})"
                           f"\n둘째 그림 = 원본 전체를 {st['vis_step']}초 간격으로(왼쪽 위 첫 칸 = 0초, n번째 칸 = (n-1)×{st['vis_step']}초) — 옷·제품이 같은 칸을 찾아 그 초를 적어라",([_img(B["sheet"])] if B.get("sheet") else []) + [_img(sh)],
                           need=("same", "origin_t"))], "then": "vis_pick"}


def ph_vis_pick(st, m, rp, u):
    a = rp.get("origin_visual") or {}
    ts = [float(t) for t in a.get("origin_t") or [] if isinstance(t, (int, float))]
    if a.get("same") and ts:
        t0 = origin_t0(st)
        st["origin"]["matched"] = [{"bench": "(화면 대조)", "origin_t": round(t + t0, 2)} for t in ts]
        st["log"].append(f"원본 = 화면 대조로 확정({st['origin']['id']}) — 벤치가 내레이션뿐: {a.get('why')}")
        return {"goto": "product_sheet"}
    return {"goto": "vis_next"}


def ph_vis_next(st, m, rp, u):
    st["vis"] = (st.get("vis") or [])[1:]
    if st["vis"]:
        return {"goto": "vis_get"}
    st.pop("origin", None)
    return _origin_next(st, "화면 대조 후보 모두 다름")


def ph_pick_got(st, m, rp, u):
    p = _reply(rp, "origin_pick", ("origin_id", "self_spoken"))
    oid = str(p.get("origin_id") or "")
    if not oid or not p.get("self_spoken") or oid not in {c["id"] for c in st.get("scored") or []}:
        return _origin_next(st, f"지문 후보 확정 못 함({str(p.get('why') or '')[:120]})")
    ts = [float(x["origin_t"]) for x in p.get("matched") or [] if isinstance(x.get("origin_t"), (int, float))]
    if not ts:
        ts = [float(x["origin_t"]) for x in next(c for c in st["scored"] if c["id"] == oid)["matched"]]
    a, b = max(0.0, min(ts) - 90), max(ts) + 90
    st["origin"] = {"id": oid, "url": f"https://www.youtube.com/watch?v={oid}", "matched": p.get("matched") or [], "window": [a, b],
                    "info": next((c for c in st["scored"] if c["id"] == oid), {})}
    full = float((st["origin"]["info"] or {}).get("dur") or 1e9) <= FULL_MAX
    if full:
        st["origin"]["window"] = [0.0, float(st["origin"]["info"]["dur"])]
    return {"do": [{"id": "origin", "cmd": "origin_get", "vid": oid, "a": a, "b": b, "ts": ts, "full": full}], "then": "origin_got"}


FULL_MAX = 1800      # 이 길이(초) 이하 원본은 통째로 바로 — 구간 받기가 멈추는 회선에서 150초+ 기다림(10-22 실측 12분 원본 통째 47~53초)


def ph_origin_fetch(st, m, rp, u):
    """원본 받기만 다시(다시 시도) — 원본 판정까지 한 일은 그대로 둔다."""
    O = st["origin"]
    ts = [float(x["origin_t"]) for x in O.get("matched") or [] if isinstance(x.get("origin_t"), (int, float))]
    return {"do": [{"id": "origin", "cmd": "origin_get", "vid": O["id"], "a": O["window"][0], "b": O["window"][1], "ts": ts}], "then": "origin_got"}


def ph_stopped(st, m, rp, u):
    """멈춘 편 — 다시 시도(retry)할 수 있는 멈춤이면 그 단계부터, 아니면 그대로 멈춤."""
    r = (st.get("stopped") or {}).get("retry")
    why0 = str((st.get("stopped") or {}).get("why") or "")
    if not r and why0.startswith("원본 영상을 받지 못했"):
        r = "origin_fetch"                       # 10-21 이전 판이 멈춘 편(retry 칸 없음)도 받기부터 이어 가게
    if not r and why0.startswith("look 단계를"):
        r = "check_retry"
    vid = _yt_id(str(u.get("origin_url") or "") or str(u.get("revise") or ""))
    if vid and (st.get("stopped") or {}).get("origin_missing"):      # '원본 주소를 주시면 바로' — 그 주소로 원본 찾기를 끝낸다
        st.pop("stopped", None)
        return _given_origin(st, vid)
    if u.get("retry") and r:
        st.pop("stopped", None)
        if r == st.get("_asker") and st.get("_asker_in"):
            st["tries"] = {k: v for k, v in (st.get("tries") or {}).items() if k == "length"}
            return {"goto": r, "feed": st["_asker_in"]}
        st["tries"] = {k: v for k, v in (st.get("tries") or {}).items() if k == "length"}   # 다시 시도 = 고치기 횟수 새로(길이 고치기만 남긴다 — 사인을 다시 받는다)
        return {"goto": r}
    raise _Stop((st.get("stopped") or {}).get("why") or "아직 마무리되지 않은 편이에요", (st.get("stopped") or {}).get("fix") or AGAIN, retry=r)


def _yt_id(text: str) -> str:
    m = re.search(r"(?:youtu\.be/|[?&]v=|/shorts/|/live/)([0-9A-Za-z_-]{11})", text or "")
    return m.group(1) if m else ""


def _given_origin(st, vid: str) -> dict:
    """회원이 준 원본 주소 — 지문만 재고(유튜브 한 번), 맞으면 그 시각으로·안 맞으면 통째 받아 화면 대조로 제품 장면을 찾는다."""
    st.setdefault("origin_tried", []).append("given")
    st["log"].append(f"회원이 준 원본 {vid}")
    st["mixed"] = [{"id": vid, "title": "", "channel": "", "dur": None}]
    r = st.get("read") or {}
    terms = [w for w in (r.get("scene_words") or []) + (r.get("product_words") or []) if w][:8]
    return {"do": [{"id": "probe", "cmd": "origin_probe", "ids": [vid], "before": "", "terms": terms, "max_sheets": 1}], "then": "given_origin_got"}


def ph_given_origin_got(st, m, rp, u):
    p = m.get("probe") or {}
    vid = st["mixed"][0]["id"]
    mt = (p.get("matched") or {}).get(vid) or []
    if mt:
        ts = [float(x["origin_t"]) for x in mt]
        st["origin"] = {"id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "matched": mt, "window": [0.0, max(ts) + 600], "given": True,
                        "info": {"id": vid}}
        return {"do": [{"id": "origin", "cmd": "origin_get", "vid": vid, "a": 0.0, "b": max(ts) + 600, "ts": ts, "full": True}], "then": "origin_got"}
    st["vis"] = [{"id": vid, "title": "", "channel": "", "dur": None, "at": [0.0], "n": 0, "score": 0, "full": True}]
    return {"goto": "vis_get"}


def ph_origin_got(st, m, rp, u):
    o = m.get("origin") or {}
    if o.get("error") or not o.get("files"):
        raise _Stop("원본 영상을 받지 못했어요", "잠시 뒤 다시 시도해 주시면 받기부터 이어 갈게요", auto=True, retry="origin_fetch")
    st["origin"].update(files=o["files"], offset=o.get("offset"), offset_measured=o.get("measured"))
    if not o.get("measured"):
        st["log"].append("원본 시작 시각을 재지 못해 요청 구간 시작으로 씀")
    return {"goto": "product_sheet"}


def origin_t0(st) -> float:
    O = st.get("origin") or {}
    off = O.get("offset")
    return float(off if off is not None else (O.get("window") or [0])[0] or 0)


def _origin_file(st) -> dict:
    return (st["origin"]["files"] or [{}])[-1]


# ── 3 제품·쿠팡 ───────────────────────────────────────────────────────────
def ph_product_sheet(st, m, rp, u):
    a = origin_t0(st)
    ts = [float(x["origin_t"]) - a for x in st["origin"].get("matched") or [] if isinstance(x.get("origin_t"), (int, float))]
    s0 = max(0.0, (min(ts) if ts else 0) - 25)      # 벤치 말이 맞은 원본 시각 근처만(10-21: 받은 구간 전체를 주자 앞머리 식칼을 골랐다)
    st["look_s0"] = s0
    return {"do": [{"id": "psheet", "cmd": "sheet", "src": "src/" + _origin_file(st)["name"], "dst": "look/origin_sheet.jpg",
                    "fps": 1, "cols": 6, "rows": 6, "w": 320, "ss": s0, "t": 36}], "then": "product_pick"}


def ph_product_pick(st, m, rp, u):
    sh = (m.get("psheet") or {}).get("file")
    if not sh:
        raise _Stop("원본 장면을 열지 못했어요", "다시 시도해 주시면 이어 갈게요", auto=True)
    s0, R0 = st["look_s0"], st["read"]
    return {"review": [_rv("product_pick", PRODUCT_PICK + f"\n\n첫 그림 = 받은 원본 파일 {s0:.0f}초부터 1초 간격(왼쪽 위부터) — 답의 t 는 **파일 초**({s0:.0f} + 칸 번호).\n"
                           f"둘째 그림 = 벤치 쇼츠 1초 시트(그 제품이 무엇인지 보여 준다). 벤치·원본 대사의 제품 낱말: {R0.get('product_words')}",
                           [_img(sh)] + ([_img(st["bench"]["sheet"])] if st["bench"].get("sheet") else []), need=("scenes", "coupang_queries"))],
            "then": "product_cands"}


def ph_product_pick_wide(st, m, rp, u):
    sh = (m.get("psheet") or {}).get("file")
    if not sh:
        if st.get("given"):
            return {"goto": "given"}
        raise _Stop("원본 영상에 제품이 화면으로 나오지 않아요(말로만 소개)", "제품이 화면에 나오는 다른 영상 주소를 주세요", final=True)
    step, R0 = st["look_step"], st["read"]
    return {"review": [_rv("product_pick", PRODUCT_PICK + f"\n\n첫 그림 = 받은 원본 파일 **전체**를 {step}초 간격으로(왼쪽 위 첫 칸 = 0초, n번째 칸 = (n-1)×{step}초) — 답의 t 는 **파일 초**.\n"
                           f"둘째 그림 = 벤치 쇼츠 1초 시트(그 제품이 무엇인지 보여 준다). 벤치·원본 대사의 제품 낱말: {R0.get('product_words')}",
                           [_img(sh)] + ([_img(st["bench"]["sheet"])] if st["bench"].get("sheet") else []), need=("scenes", "coupang_queries"))],
            "then": "product_cands"}


def ph_product_cands(st, m, rp, u):
    r = _reply(rp, "product_pick", ("scenes", "coupang_queries"))
    scenes = [s for s in r.get("scenes") or [] if isinstance(s, dict) and isinstance(s.get("t"), (int, float))][:4]
    if len(scenes) < 1:
        if not st.get("_wide_product"):        # 말이 맞은 곳 앞뒤에 제품이 없다 — 원본 전체를 훑은 시트로 한 번 더(10-22 강주은: 가방은 10분 50초)
            st["_wide_product"] = True
            dur = float(_origin_file(st).get("dur") or 600)
            step = max(1, math.ceil(dur / VIS_TILES))
            st["look_step"] = step
            return {"do": [{"id": "psheet", "cmd": "sheet", "src": "src/" + _origin_file(st)["name"], "dst": "look/origin_wide.jpg",
                            "fps": round(1 / step, 4), "cols": 8, "rows": VIS_TILES // 8, "w": 200, "ss": 0, "t": dur}], "then": "product_pick_wide"}
        if st.get("given"):
            return {"goto": "given"}
        raise _Stop("원본 영상에 제품이 화면으로 나오지 않아요(말로만 소개)", "제품이 화면에 나오는 다른 영상 주소를 주세요", final=True)
    st["product_pick"] = r
    qs = [q for q in r.get("coupang_queries") or [] if q][:4] + [w for w in r.get("brand_words") or [] if w][:2]
    st["coupang_qs"] = qs
    return {"do": [{"id": "shots", "cmd": "frames", "src": "src/" + _origin_file(st)["name"], "items": scenes, "prefix": "look/p"},
                   {"id": "coupang", "cmd": "coupang", "queries": qs}], "then": "product_same"}


def ph_product_same(st, m, rp, u):
    _coupang_down(m)
    shots = (m.get("shots") or {}).get("files") or []
    if not shots:
        raise _Stop("제품 장면을 자르지 못했어요", "다시 시도해 주시면 이어 갈게요", auto=True)
    st["product_shots"] = shots
    cands = (m.get("coupang") or {}).get("items") or []
    st["coupang_cands"] = cands[:16]
    if not cands:
        return {"goto": "name_find"}
    return _cand_sheet_do(st, st["coupang_cands"], "same")


def _given_query(g: str) -> tuple[str, str]:
    """고객이 정한 제품 글 → (쿠팡 검색어, 상품번호). 주소면 번호만 뽑고 남은 글을 검색어로."""
    pid = (re.search(r"products/(\d{6,})", g) or re.search(r"\b(\d{8,})\b", g) or [None, ""])[1]
    q = re.sub(r"https?://\S+", " ", g)
    q = re.sub(r"\b\d{8,}\b", " ", q)
    return " ".join(q.split())[:80], pid


def ph_given(st, m, rp, u):
    q, _ = _given_query(st["given"])
    if not q:
        raise _Stop("정해 주신 제품 이름을 알 수 없어요", "쿠팡 상품 이름을 함께 적어 다시 만들어 주세요", final=True)
    st["log"].append("원본에 제품 장면 없음 → 고객이 정한 제품으로")
    return {"do": [{"id": "coupang", "cmd": "coupang", "queries": [q]}], "then": "given_same"}


def ph_given_same(st, m, rp, u):
    _coupang_down(m)
    cands = (m.get("coupang") or {}).get("items") or []
    if not cands:
        raise _Stop("정해 주신 제품을 쿠팡에서 찾지 못했어요", "쿠팡 상품 이름을 정확히 적어 다시 만들어 주세요", final=True)
    st["given_cands"] = cands[:16]
    return _cand_sheet_do(st, st["given_cands"], "given")


CAND_NOTE = ("\n\n★마지막 그림 = 쿠팡 후보 사진 시트(칸 '#번호 상품번호' = 아래 후보 목록 순서). **같은 제품은 사진으로도 같아야 한다** — 모양·색·버클·로고까지 원본 장면과 대조한다. "
             "이름만 맞으면 같은 제품이 아니다(10-22 강주은: 이름 '그린 버클 소가죽'만 보고 둥근 실버 잠금 가방을 같은 제품으로 골랐다).")


def _cand_sheet_do(st, cands: list, kind: str) -> dict:
    """후보 사진 시트(파트너스 API 이미지 주소 — 상품 페이지를 열지 않는다)를 만들고 판정 질문으로(kind = same|named|best)."""
    st["_cand_kind"] = kind
    items = [{"product_id": str(c.get("product_id") or ""), "image": c.get("image") or ""} for c in cands[:12]]
    return {"do": [{"id": "csheet", "cmd": "cand_sheet", "items": items}], "then": "cand_look"}


def ph_cand_look(st, m, rp, u):
    sh = (m.get("csheet") or {}).get("file")
    kind = st.get("_cand_kind") or "same"
    pics = [_img(x) for x in st.get("product_shots") or []] + ([_img(sh)] if sh else [])
    note = CAND_NOTE if sh else "\n\n(후보 사진을 받지 못했다 — 이름만으로는 같은 제품이라고 하지 않는다)"
    if kind == "given":
        _, pid = _given_query(st["given"])
        return {"review": [_rv("given_same", PRODUCT_GIVEN + note + f"\n\n고객이 정한 제품: {st['given']}" + (f"\n(쿠팡 상품번호 {pid} — 후보에 있으면 그것)" if pid else "") +
                               "\n\n쿠팡 후보:\n" + json.dumps((st.get("given_cands") or [])[:12], ensure_ascii=False, indent=1), pics, need=("product_id", "name", "category"))],
                "then": "product_done"}
    if kind == "same":
        cands = st.get("coupang_cands") or []
        return {"review": [_rv("product_same", PRODUCT_SAME + note + "\n\n쿠팡 후보:\n" + json.dumps(cands[:12], ensure_ascii=False, indent=1),
                               pics, need=("product_id", "name", "category"))], "then": "product_done"}
    if kind == "named":
        c2 = st.get("named_cands") or []
        return {"review": [_rv("named_same", PRODUCT_NAMED + note + "\n\n찾은 제품 이름·근거:\n" + json.dumps((st.get("name_find") or {}).get("names"), ensure_ascii=False, indent=1) +
                               "\n\n쿠팡 후보:\n" + json.dumps(c2[:12], ensure_ascii=False, indent=1), pics, need=("product_id", "name", "category"))], "then": "product_done"}
    cands = st.get("coupang_cands") or st.get("named_cands") or []
    kind_txt = (st.get("name_find") or {}).get("kind") or (st.get("product_pick") or {}).get("brand_words")
    best_note = CAND_NOTE.replace("같은 제품은 사진으로도 같아야 한다", "같은 종류·같은 쓰임인지 사진으로 본다") if sh else ""
    return {"review": [_rv("best_same", _q(st, "PRODUCT_BEST") + best_note + f"\n\n연예인이 쓴 것: {kind_txt}\n\n쿠팡 후보:\n" + json.dumps(cands[:12], ensure_ascii=False, indent=1),
                           pics, need=("product_id", "name", "category"))], "then": "product_done"}


def ph_product_done(st, m, rp, u):
    same = rp.get("product_same") or rp.get("named_same") or rp.get("best_same") or rp.get("given_same") or {}
    mode = "exact" if "product_same" in rp else ("named" if "named_same" in rp else "alt")
    given = "given_same" in rp
    if given and not same.get("product_id"):
        raise _Stop("정해 주신 제품을 쿠팡에서 찾지 못했어요", "쿠팡 상품 이름을 정확히 적어 다시 만들어 주세요", final=True)
    if not same.get("product_id"):
        if mode == "exact":
            return {"goto": "name_find"}
        if mode == "named":
            return {"goto": "best"}
        st["coupang_cands"], st["named_cands"] = [], []
        w = _best_wide(st)
        if w:
            return w
        raise _Stop(*NO_SIMILAR)
    if same.get("category") in ("의약품", "의료기기"):
        raise _Stop("의약품·의료기기는 만들 수 없는 소재예요", "다른 소재 영상을 주세요", final=True)
    pool = st.get("given_cands") if given else (st.get("named_cands") if mode == "named" else st.get("coupang_cands"))
    if pool and str(same["product_id"]) not in {str(c.get("product_id") or c.get("productId") or c.get("id") or "") for c in pool}:
        st["log"].append(f"제품 번호 {same['product_id']} 가 후보 표에 없음 — 답 그대로 씀")
    st["product"] = {**{k: same.get(k) for k in ("product_id", "name", "why", "category")}, "mode": mode, **({"given": True} if given else {}),
                     "name_hints": (st.get("name_find") or {}).get("names") or [], "brand_words": (st.get("product_pick") or {}).get("brand_words")}
    if mode == "alt" and not given:     # 같은 물건이 없어 비슷한 제품 — 회원에게 쉬운 말로 한 번 알린다(대본의 '비슷한 제품' 줄은 script_audit.alt_disclosed 가 강제)
        mw = str(same.get("member_why") or "").strip()
        st["notice"] = ALT_NOTICE + (f" — {mw}" if mw and member_ok(mw) else " — 종류와 쓰임이 같은 제품이에요")
        st.pop("_notice_shown", None)
    return {"goto": "reviews"}


def ph_reviews(st, m, rp, u):
    """고른 쿠팡 상품의 베스트 후기(도움 순) — 대본 뒷부분 셀링포인트·소구점 근거(사장님 10-22)."""
    return {"do": [{"id": "reviews", "cmd": "coupang_reviews", "product_id": str((st.get("product") or {}).get("product_id") or "")}], "then": "reviews_got"}


def ph_reviews_got(st, m, rp, u):
    r = m.get("reviews") or {}
    st["reviews"] = [{"id": x.get("id"), "text": str(x.get("text") or "")[:400]} for x in r.get("reviews") or []][:8]
    if not st["reviews"]:
        # 쿠팡 후기를 못 받으면(회원 PC 도 막힐 수 있다 — 사장님 10-22 "쿠팡 후기 아니어도 된다") 네이버 검색 글에서 셀링포인트를 찾는다
        st["log"].append("쿠팡 베스트 후기 못 받음" + (" — 쿠팡이 잠시 막음" if r.get("blocked") else "") + " → 네이버 글로")
        name = str((st.get("product") or {}).get("name") or "").strip()
        if name:
            short = " ".join(name.split()[:4])
            return {"do": [{"id": "nreviews", "cmd": "naver", "queries": [f"{short} 후기", f"{short} 장점"]}], "then": "reviews_naver"}
    return {"goto": "research"}


def ph_reviews_naver(st, m, rp, u):
    texts = ((m.get("nreviews") or {}).get("texts") or {})
    st["reviews"] = [{"id": f"n{i + 1}", "text": f"[네이버 '{q}'] " + str(t)[:1200]} for i, (q, t) in enumerate(texts.items())
                     if t and not str(t).startswith("(네이버 검색 실패")]
    if not st["reviews"]:
        st["log"].append("네이버 글도 못 받음 — 대본은 후기 없이(지어내지 않는다)")
    return {"goto": "research"}


def ph_name_find(st, m, rp, u):
    R0 = st["read"]
    celeb, words = str(R0.get("celeb") or ""), [w for w in (R0.get("product_words") or []) if w][:3]
    if not celeb or celeb == "불명" or not words:
        return {"goto": "best"}
    qs = [f"{celeb} {w}" for w in words]
    return {"do": [{"id": "naver", "cmd": "naver", "queries": qs}, {"id": "ytnames", "cmd": "search", "queries": qs, "n": 8}], "then": "name_got"}


def ph_name_got(st, m, rp, u):
    R0 = st["read"]
    texts = [f"[네이버 {q}] {t}" for q, t in ((m.get("naver") or {}).get("texts") or {}).items()]
    yt = (m.get("ytnames") or {}).get("found") or []
    texts.append("[유튜브 제목] " + " / ".join(f"{c.get('channel')}: {c.get('title')}" for c in yt)[:3000])
    return {"review": [_rv("name_find", NAME_FIND + f"\n\n연예인: {R0.get('celeb')}\n제품 낱말: {R0.get('product_words')}\n\n" + "\n\n".join(texts),
                           need=("names",))], "then": "named_cands"}


def ph_named_cands(st, m, rp, u):
    a = rp.get("name_find") or {}
    st["name_find"] = a
    named = [n["name"] for n in a.get("names") or [] if isinstance(n, dict) and n.get("name")][:3]
    if not named:
        return {"goto": "best"}
    return {"do": [{"id": "coupang2", "cmd": "coupang", "queries": named}], "then": "named_same"}


def ph_named_same(st, m, rp, u):
    _coupang_down(m, "coupang2")
    c2 = (m.get("coupang2") or {}).get("items") or []
    if not c2:
        return {"goto": "best"}
    st["named_cands"] = c2[:16]
    return _cand_sheet_do(st, st["named_cands"], "named")


def _wide_queries(st) -> list[str]:
    """비슷한 제품 넓은 검색어 — 연예인 이름 없이 제품 낱말·종류만(같은 종류·쓰임이면 된다)."""
    r = st.get("read") or {}
    kind = (st.get("name_find") or {}).get("kind") or (st.get("product_pick") or {}).get("brand_words") or ""
    qs = [str(w) for w in (r.get("product_words") or []) if w] + ([str(kind)] if isinstance(kind, str) and kind else [])
    return list(dict.fromkeys(q.strip() for q in qs if q.strip()))[:4]


def _best_wide(st) -> dict | None:
    if st.get("_wide"):
        return None
    st["_wide"] = True
    qs = _wide_queries(st)
    if not qs:
        return None
    st["log"].append(f"비슷한 제품 넓은 검색: {qs}")
    return {"do": [{"id": "coupang", "cmd": "coupang", "queries": qs, "ratings": True}], "then": "best_rated"}


def ph_best(st, m, rp, u):
    cands = st.get("coupang_cands") or st.get("named_cands") or []
    if not cands:
        w = _best_wide(st)
        if w:
            return w
        raise _Stop(*NO_SIMILAR)
    if not any(c.get("rating") for c in cands) and st.get("coupang_qs") and not st.get("_rated"):
        st["_rated"] = True          # 대체 제품 = 후기 많은 것 — 후기 수는 이때만 채운다(98 #11·#43)
        return {"do": [{"id": "coupang", "cmd": "coupang", "queries": st["coupang_qs"], "ratings": True}], "then": "best_rated"}
    return _cand_sheet_do(st, cands, "best")


def ph_best_rated(st, m, rp, u):
    _coupang_down(m)
    got = (m.get("coupang") or {}).get("items") or []
    if got:
        st["coupang_cands"] = got[:16]
    cands = st.get("coupang_cands") or st.get("named_cands") or []
    if not cands:
        w = _best_wide(st)
        if w:
            return w
        raise _Stop(*NO_SIMILAR)
    return _cand_sheet_do(st, cands, "best")


# ── 4 조사 ────────────────────────────────────────────────────────────────
def ph_research(st, m, rp, u):
    f = _origin_file(st)
    return {"do": [{"id": "words", "cmd": "origin_words", "vid": st["origin"]["id"], "src": "src/" + f["name"], "t0": origin_t0(st)}], "then": "research_got"}


def ph_research_got(st, m, rp, u, fail: str = ""):
    w = m.get("words") or st.get("_words") or {}
    st["_words"] = w
    a = origin_t0(st)
    f = _origin_file(st)
    near = [(round(t, 1), x) for t, x in (w.get("words") or []) if a <= t <= a + float(f.get("dur") or 1e9)]
    txt = " ".join(f"[{t}]{x}" for t, x in near)[:9000]
    O, PR = st["origin"], st["product"]
    ask = (RESEARCH + f"\n\n## 원본\n{O['url']} (받은 파일 0초 = 원본 {a:.2f}초 — 잰 값. spans 는 파일 초 = 원본 초 − {a:.2f}, 받은 파일 길이 {f.get('dur')}초)\n"
           f"지문 대조: {json.dumps(O.get('matched'), ensure_ascii=False)}\n자막({w.get('from') or '자동자막'}, 원본 초):\n{txt}\n\n## 제품\n"
           f"{json.dumps(PR, ensure_ascii=False)}" + (RESEARCH_GIVEN if PR.get("given") else "") + (f"\n\n## 지난 답에서 걸린 것(고쳐라)\n{fail}" if fail else ""))
    return {"review": [_rv("research", ask, [_img(x) for x in st.get("product_shots") or []][:3], need=("조사_md", "keywords", "queries", "spans"))],
            "then": "research_check", "reject": {"why": fail, "fix": "조사를 고쳐 다시"} if fail else None}


def ph_research_check(st, m, rp, u):
    r = _reply(rp, "research", ("조사_md", "keywords", "queries", "spans"))
    if r.get("stop"):
        st["log"].append("조사 멈춤: " + str(r["stop"])[:400])     # 판정 글은 기록에만 — 고객에겐 이유·해결 두 줄(사장님 10-22)
        raise _Stop("조사해 보니 이 제품은 만들 수 없는 소재예요(의약품·금지 품목 등)", "다른 소재 영상을 주세요", final=True)
    md, bad = str(r.get("조사_md") or ""), []
    for h in ("결론", "출처", "원음", "사실", "금지", "확인 못"):
        if h not in md:
            bad.append(f"조사.md 에 '{h}' 절이 없다")
    dur = float(_origin_file(st).get("dur") or 1e9)
    spans = [s for s in r.get("spans") or [] if isinstance(s, dict)]
    if not spans:
        bad.append("원음 구간(spans)이 없다")
    for s in spans:
        try:
            if not (0 <= float(s["a"]) < float(s["b"]) <= dur + 0.5):
                bad.append(f"원음 구간 {s.get('tag')} {s.get('a')}~{s.get('b')} 가 받은 파일 길이({dur:.1f}초) 밖")
        except (KeyError, TypeError, ValueError):
            bad.append(f"원음 구간 꼴이 틀렸다: {s}")
    for f in r.get("facts") or []:
        if isinstance(f, dict) and not str(f.get("src") or "").strip():
            bad.append(f"사실 {f.get('id')} 에 출처가 없다")
    forbid = ((_style(st["version"]).get("script") or {}).get("forbid") or [])
    hit = [w for w in forbid if isinstance(w, str) and w and any(w in str((f or {}).get("fact") or "") for f in r.get("facts") or [])]
    if hit:
        bad.append(f"사실에 금지 낱말: {hit}")
    if bad:
        _tries(st, "research", 3)
        return ph_research_got(st, {}, {}, u, fail="; ".join(bad))
    st["research"] = {k: r.get(k) for k in ("keywords", "queries", "exclude", "spans", "facts")}
    st["research_md"] = md
    return {"do": [{"id": "save_research", "cmd": "write_doc", "files": {"조사/조사.md": md}}], "then": "material"}


# ── 5 재료 영상 ───────────────────────────────────────────────────────────
def ph_material(st, m, rp, u):
    R = st["research"]
    return {"do": [{"id": "screen", "cmd": "screen", "queries": R.get("queries") or [], "exclude": R.get("exclude") or [],
                    "keywords": R.get("keywords") or [], "top": 8, "bench_id": st["bench"].get("id"), "origin_id": (st.get("origin") or {}).get("id")}],
            "then": "material_got"}


def ph_material_got(st, m, rp, u):
    s = m.get("screen") or {}
    rows = s.get("rows") or []
    st["screen_rows"] = rows
    if not rows:
        return {"do": [{"id": "stills", "cmd": "product_stills", "product_id": (st.get("product") or {}).get("product_id"), "n": 4}], "then": "material_dl"}
    return {"review": [_rv("screen_pick", SCREEN_PICK + "\n\n후보(시트 순서와 같다):\n" + json.dumps(rows, ensure_ascii=False, indent=1) +
                           f"\n\n제품: {st['product'].get('name')} / 연예인: {st['read'].get('celeb')}", [_img(x) for x in s.get("sheets") or []][:8],
                           need=("chosen",))], "then": "material_pick"}


def ph_material_pick(st, m, rp, u):
    r = _reply(rp, "screen_pick", ("chosen",))
    known = {x.get("id") for x in st.get("screen_rows") or []}
    celeb = str(st["read"].get("celeb") or "")
    chosen = [c for c in r.get("chosen") or [] if isinstance(c, dict) and c.get("id") in known and c["id"] not in (st["bench"].get("id"), (st.get("origin") or {}).get("id"))
              and not (celeb and celeb in str(c.get("why") or ""))]
    st["screen_pick"] = {"chosen": chosen, "rejected": r.get("rejected") or []}
    stills = {"id": "stills", "cmd": "product_stills", "product_id": (st.get("product") or {}).get("product_id"), "n": 4}
    return {"do": [{"id": "dl", "cmd": "download", "items": [{"id": c["id"], "sections": c.get("sections") or []} for c in chosen]}, stills] if chosen else [stills],
            "then": "material_dl"}


def ph_material_dl(st, m, rp, u):
    # 쿠팡 상품 사진도 재료 — 제작순서 05 '리뷰 영상이 없으면 쿠팡 상품 사진을 움직이는 컷으로'(10-21 선우용여 제품 컷 0개, 98 #22)
    st["material"] = {"files": ((m.get("dl") or {}).get("files") or []) + ((m.get("stills") or {}).get("files") or [])}
    return {"goto": "asr"}


# ── 6 받아쓰기·샷 표 ──────────────────────────────────────────────────────
def ph_asr(st, m, rp, u):
    f = _origin_file(st)
    return {"do": [{"id": "asr", "cmd": "asr_spans", "src": "src/" + f["name"], "spans": st["research"].get("spans") or []},
                   {"id": "shots", "cmd": "shot_sheets", "files": ["src/" + x["name"] for x in st["origin"]["files"]], "window": _use_window(st)}], "then": "asr_got"}


SHOT_PAD = 90.0       # 샷 표를 만드는 구간 = 쓰는 곳(원음 구간·지문·제품 장면) 앞뒤 이만큼(초)


def _use_window(st) -> list | None:
    """원본 파일에서 실제로 쓰는 곳(받은 파일 초) 앞뒤 SHOT_PAD — 통째로 받은 원본 전체를 샷으로 자르지 않게(10-22 샷 표 72초)."""
    t0 = origin_t0(st)
    ts = [float(x["origin_t"]) - t0 for x in st["origin"].get("matched") or [] if isinstance(x.get("origin_t"), (int, float))]
    for s_ in (st.get("research") or {}).get("spans") or []:
        ts += [float(s_.get("a") or 0), float(s_.get("b") or 0)]
    ts += [float(x["t"]) for x in (st.get("product_pick") or {}).get("scenes") or [] if isinstance(x.get("t"), (int, float))]
    return [max(0.0, min(ts) - SHOT_PAD), max(ts) + SHOT_PAD] if ts else None


def ph_asr_got(st, m, rp, u):
    st["asr"] = m.get("asr") or {}
    sh = m.get("shots") or {}
    st["shots"] = sh.get("shots") or {}          # {stem: [{i,a,b}]}
    R0 = st["read"]
    kind = (st.get("product") or {}).get("name") or R0.get("product_words")
    revs = []
    for stem, sheets in (sh.get("sheets") or {}).items():
        for k, rel in enumerate(sheets):
            revs.append(_rv(f"shot_{stem}_{k}", SHOT_READ.format(celeb=R0.get("celeb") or "주인공", kind=kind), [_img(rel)], need=("shots",)))
    if not revs:
        return {"goto": "script"}
    return {"review": revs, "then": "shots_got"}


def ph_shots_got(st, m, rp, u):
    _apply_shot_reads(st, rp)
    return {"goto": "script"}


def _apply_shot_reads(st, rp) -> None:
    """샷 판독 답(shot_<파일>_<k>) → 샷 표 칸(who·product·desc·cx·text, 해외원본형은 other_product 도). 연예인형·해외원본형 공용."""
    for stem, shots in (st.get("shots") or {}).items():
        got = {}
        for rid, a in rp.items():
            if rid.startswith(f"shot_{stem}_") and isinstance(a, dict):
                for x in a.get("shots") or []:
                    if isinstance(x, dict):
                        try:
                            got[int(x.get("i", -1))] = x
                        except (TypeError, ValueError):
                            pass
        for s in shots:
            g = got.get(s["i"]) or {}
            cx = g.get("cx")
            boxes = [b for b in g.get("text") or [] if isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)]
            s.update(who=g.get("who") or "?", product=bool(g.get("product")), desc=str(g.get("desc") or "")[:30],
                     cx=float(cx) if isinstance(cx, (int, float)) and 0 <= cx <= 1 else None, text=boxes)
            if "other_product" in g:
                s["other_product"] = bool(g.get("other_product"))


# ── 7 대본·재료·근거 ──────────────────────────────────────────────────────
def _rule_bench_id(st) -> str:
    """출처 규칙 ①(벤치는 재료가 아니다)에 넘길 벤치 id — 해외원본형에서 회원이 해외 원본 주소를 바로 줬으면 벤치 = 첫 원본이라 재료다(빈 값)."""
    b = str((st.get("bench") or {}).get("id") or "")
    return "" if b and b in {str(o.get("id")) for o in st.get("origins") or []} else b


def _origin_names(st) -> set:
    return {x["name"] for x in (st.get("origin") or {}).get("files") or []}


def _origin_dims(st) -> dict:
    return {x["name"]: [int(x.get("w") or 0), int(x.get("h") or 0)] for x in (st.get("origin") or {}).get("files") or [] if x.get("w")}


def _all_dims(st) -> dict:
    """원본 + 재료(영상·사진) 크기 — crop 단위 바로잡기(rules.fix_crop_units)용."""
    return {**{x["name"]: [int(x.get("w") or 0), int(x.get("h") or 0)] for x in (st.get("material") or {}).get("files") or [] if x.get("w")}, **_origin_dims(st)}


def _shots_ctx(st) -> str:
    out = [f"### {stem} (파일 {stem}.mp4)\n" + RU.shot_text(shots) for stem, shots in (st.get("shots") or {}).items()]
    return ("\n\n## 원본 샷 표(카메라가 바뀌는 곳마다 — 주인공 컷은 who main·both 샷 안에서 ss 를 고르고, 컷 길이가 그 샷 끝을 넘지 않게)\n" + "\n".join(out)) if out else ""


def ph_script(st, m, rp, u):
    mats = ["src/" + x["name"] for x in (st.get("material") or {}).get("files") or []]
    origs = ["src/" + x["name"] for x in (st.get("origin") or {}).get("files") or []]
    files = (origs + mats) if _fmt(st) == "해외원본형" else (mats + origs)     # 해외원본형은 원본이 주재료 — 원본 시트가 앞
    return {"do": [{"id": "msheets", "cmd": "mat_sheets", "files": files[:5]}], "then": "script_ask"}


def _script_ask(st, fail: str = "") -> dict:
    from tools.calcopy.hybrid import render_bench, styles as STY
    v = st["version"]
    fmt = (render_bench.__doc__ or "")
    fmt = fmt[fmt.find("대본.json:"):] if "대본.json:" in fmt else fmt
    PR = st.get("product") or {}
    ms = st.get("_msheets") or {}
    talk = RU.PRODUCT_TALK_FOREIGN if _fmt(st) == "해외원본형" else RU.PRODUCT_TALK
    ctx = (STY.brief(v) + "\n\n## 대본·재료 꼴\n" + fmt + "\n\n## 조사.md\n" + (st.get("research_md") or "") +
           "\n\n## 제품 판정\n" + talk.get("given" if PR.get("given") else (PR.get("mode") or "exact"), "") + "\n" +
           json.dumps({k: PR.get(k) for k in ("name", "product_id", "why", "mode", "name_hints")}, ensure_ascii=False) +
           "\n\n## 쿠팡 베스트 후기(r번호 — 도움 순, 셀링포인트·소구점 근거)\n" +
           (json.dumps(st.get("reviews") or [], ensure_ascii=False)[:4000] if st.get("reviews") else "(못 받음 — 후기 전언 줄을 쓰지 않는다)") +
           "\n\n## 원음 받아쓰기(구간마다 — 모델 둘이면 둘 다)\n" + json.dumps(st.get("asr") or {}, ensure_ascii=False)[:6000] +
           "\n\n## 재료 파일(시트 순서 = 앞 5개)\n" + json.dumps(ms.get("list") or [], ensure_ascii=False) +
           "\n실제 크기(crop 은 이 픽셀로 — 시트는 줄인 미리보기다): " + json.dumps(_all_dims(st), ensure_ascii=False) + _shots_ctx(st) +
           _foreign_script_ctx(st) + (f"\n\n## 대본 검사에서 걸린 것(고쳐라)\n{fail}" if fail else ""))
    return _rv(f"script_{v}", _q(st, "SCRIPT") + "\n\n" + ctx, [_img(x) for x in ms.get("sheets") or []], need=("대본", "재료"))


def ph_script_ask(st, m, rp, u):
    st["_msheets"] = m.get("msheets") or {}
    return {"review": [_script_ask(st)], "then": "script_got"}


def audit_script(st: dict, S: dict, M: dict) -> dict:
    """서버 판정 — 대본 검사(script_audit — 자막↔목소리·줄 끝 부호·영문 포함) + 제목 색 + 출처 규칙 ①②·다른 출연자 샷. 하나라도 걸리면 반려."""
    from tools.calcopy.hybrid import script_audit
    v = st["version"]
    PR = st.get("product") or {}
    if PR:     # 제품 판정을 대본에 싣는다 — script_audit.alt_disclosed 가 alt 면 '비슷한 제품' 밝히는 줄을 요구(03 · 사장님 10-25)
        S["product_mode"] = "given" if PR.get("given") else (PR.get("mode") or "exact")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "대본.json"
        p.write_text(json.dumps(S, ensure_ascii=False), encoding="utf-8")
        try:
            a = script_audit.audit(p, v)
        except Exception as e:  # noqa: BLE001 — 꼴이 틀린 대본은 검사가 죽는다 → 반려 사유로
            a = {"ok": False, "error": f"대본 꼴이 틀렸다: {type(e).__name__}: {str(e)[:200]}"}
    extra = {"title": RU.title_colors_bad(S, _style(v)), "claims": RU.script_claim_problems(S),   # 자막↔목소리 = script_audit(G-1) 안
             "alt_scene": RU.alt_scene_problems(S, M, _origin_names(st)) if (st.get("product") or {}).get("mode") == "alt" else [],
             "source_rule": RU.source_rule_static(M, _origin_names(st), _rule_bench_id(st), st.get("shots") or {})}
    on = _origin_names(st)
    if _fmt(st) != "해외원본형" and not any(str(c.get("src") or "") not in on for cs in (M.get("cuts") or {}).values() for c in (cs if isinstance(cs, list) else [cs])):
        extra["product_cut"] = ["제품 컷이 하나도 없다 — '써 봤다'·제품 설명 줄은 재료 파일(제품 영상 또는 prod_*.jpg 사진, 사진은 move: in·out·left·right)로. "
                                "원본 방송 화면만으로 우리 제품 이야기를 하지 않는다(98 #22)"]
    bad = {k: x for k, x in extra.items() if x}
    return {**a, **bad, "ok": bool(a.get("ok")) and not bad}


def _prep_material(st, S: dict, M: dict) -> dict:
    """대본 답의 재료에 서버가 채우는 칸(한 곳) — 샷 끝·주인공 칸(fill_shot_max) · 해외원본형 박힌 글자 흐림(text_blur_all) · crop 단위."""
    M = RU.fill_shot_max(M, S, _origin_dims(st), st.get("shots") or {}, _ar(st["version"]))
    if _fmt(st) == "해외원본형":              # 박힌 글자 = 지운 파일(clean)은 그대로, 나머지는 흐림 — 판단 주인 rules.text_blur_all(관제 263 08)
        nb = RU.merge_blur(M, RU.text_blur_all(st.get("shots") or {}, _origin_dims(st), set((st.get("text_fix") or {}).get("cleaned") or [])))
        if nb:
            st["log"].append(f"박힌 글자 흐림 {nb}칸(재료.blur)")
    fixed = RU.fix_crop_units(M, _all_dims(st))
    if fixed:
        st["log"].append("crop 단위 바로잡음: " + "; ".join(fixed)[:300])
    return M


def dev_inject_script(st: dict, answer: dict) -> list:
    """(개발 완주 전용 — flow_dev --from-plan) 대본 답을 **대본 검사 없이** 넣고 계획 단계부터. 서버 step 은 이 함수를 부르지 않는다.
    쓰는 곳: 돈 0 시험에서 TTS 캐시가 있는 승인본 대본으로 계획·렌더·검사를 돌릴 때. 반환 = 실행기 do(대본·재료·근거 쓰기)."""
    v = st["version"]
    S, M = answer["대본"], _prep_material(st, answer["대본"], answer["재료"])
    st["script"] = {"S": S, "M": M, "G": answer.get("근거_md") or ""}
    st["approved"], st["phase"] = True, "plan"
    st["log"].append("(개발) 대본 검사 없이 대본 넣음 — flow_dev --from-plan")
    return [{"id": "save_script", "cmd": "write_doc", "files": {f"{v}/대본.json": S, f"{v}/재료.json": M, f"{v}/근거.md": st["script"]["G"]}, "cand_dir": True, "version": v}]


def ph_script_got(st, m, rp, u):
    v = st["version"]
    r = _reply(rp, f"script_{v}", ("대본", "재료"))
    S, M = r["대본"], r["재료"]
    if not isinstance(S, dict) or not isinstance(M, dict):
        a = {"ok": False, "error": "대본·재료는 JSON 객체여야 한다"}
    else:
        ch = ((st.get("origin") or {}).get("info") or {}).get("channel")
        if _fmt(st) == "해외원본형":              # 원본 여럿 — 원본 채널 이름을 다 적는다
            ch = ", ".join(dict.fromkeys(str((o.get("info") or {}).get("channel")) for o in st.get("origins") or [] if (o.get("info") or {}).get("channel"))) or ch
        if ch:                                   # 출처 줄 = 원본 채널 이름 그대로(사장님 '원본을 출처로') — 판정 답이 아니라 서버가 정한다
            S["source_label"] = f"출처: {ch}"
        M = _prep_material(st, S, M)
        a = audit_script(st, S, M)
    if not a.get("ok"):
        _tries(st, "script", LIMITS["script"])
        why = json.dumps({k: x for k, x in a.items() if k != "ok"}, ensure_ascii=False)[:4000]
        return {"review": [_script_ask(st, why)], "then": "script_got", "reject": {"why": why[:400], "fix": "대본을 고쳐 다시"}}
    st["script"] = {"S": S, "M": M, "G": r.get("근거_md") or ""}
    return {"do": [{"id": "save_script", "cmd": "write_doc", "files": {f"{v}/대본.json": S, f"{v}/재료.json": M, f"{v}/근거.md": st["script"]["G"]},
                    "cand_dir": True, "version": v},
                   {"id": "heard", "cmd": "orig_heard", "version": v}], "then": "script_heard"}


def ph_script_heard(st, m, rp, u):
    """원음 줄마다 그 구간을 **실제로 받아써** 자막과 대조 — 집 PC 워커가 귀로 하던 확인(98 #20). 다르면 앞뒤 받아쓰기를 붙여 대본 다시."""
    bad = (m.get("heard") or {}).get("bad") or []
    if not bad:
        return {"goto": "customize"}
    _tries(st, "script", LIMITS["script"])
    why = json.dumps({"orig_heard": bad}, ensure_ascii=False)[:4000]
    return {"review": [_script_ask(st, why)], "then": "script_got", "reject": {"why": why[:400], "fix": "원음 구간을 그 말이 들리는 자리로"}}


def script_view(st) -> dict:
    S = (st.get("script") or {}).get("S") or {}
    title = " ".join("".join(c[0] for c in l) if isinstance(l, list) else str(l) for l in S.get("title_lines") or [])
    lines = [(l.get("tts") or l.get("text") or " ".join(c[0] for c in l.get("caps_rel") or []) or "").strip() for l in S.get("lines") or []]
    return {"title": title, "lines": [x for x in lines if x][:30]}


# ── 회원 맞춤 자리(표준 §10-3 — 지시서 12 가 채운다) ─────────────────────────────
def ph_customize(st, m, rp, u):
    """회원 채팅 → 팩 항목 교체 패치(styles.apply_patch) 자리. 08 은 자리만 — 지금은 그대로 사인으로(do·질문 없음 = 단계 수 그대로)."""
    return {"goto": "sign"}


# ── 사인 ──────────────────────────────────────────────────────────────────
def ph_sign(st, m, rp, u):
    if u.get("approve"):
        st["approved"] = True
        return {"goto": "plan"}
    if u.get("revise"):
        st["tries"]["script"] = 0
        return {"review": [_script_ask(st, "고객 요청: " + str(u["revise"])[:500])], "then": "script_got"}
    return {"wait": {"kind": "approve", "script": script_view(st)}, "then": "sign"}


# ── 8 계획 ────────────────────────────────────────────────────────────────
def ph_plan(st, m, rp, u):
    return {"do": [{"id": "plan", "cmd": "plan", "version": st["version"], "origin_names": sorted(_origin_names(st))}], "then": "plan_got"}


def ph_plan_got(st, m, rp, u):
    p = m.get("plan") or {}
    if p.get("error"):                            # 계획 자체가 못 돌았다(실행기 오류·돈 0 모드 TTS 캐시 없음) — 빈 시트로 검수를 묻지 않는다(조용한 통과 금지)
        st["log"].append("계획 실패: " + str(p["error"])[:300])
        raise _Stop("장면 계획을 만들지 못했어요", "다시 시도해 주시면 계획부터 이어 갈게요", retry="plan", auto=True, detail=str(p["error"])[:300])
    if p.get("conflict"):                         # 배치 충돌 = 대본이 1차 audit 밖이라 생긴 증상(표준 §11-5 ㉛) → 대본 단계로
        return _conflict_rewrite(st, p["conflict"])
    ln = p.get("length") or {}
    if ln.get("measured") and not ln.get("ok"):   # 진짜 목소리 길이가 판 범위 밖 — 렌더(5분) 전에 글로 고친다(10-22 선우용여: 렌더 뒤에야 걸려 렌더 3번)
        return _length_rewrite(st, f"{ln.get('sec')}초 (판 {ln.get('min')}~{ln.get('max')})")
    over = [p["over"]] if p.get("over") else []
    known = _origin_names(st) | {x.get("name") for x in (st.get("material") or {}).get("files") or [] if x.get("name")}
    orig_lines = {l["id"] for l in (st["script"].get("S") or {}).get("lines") or [] if l.get("kind") == "orig"}
    over += RU.material_problems(st["script"]["M"], known, orig_lines, _all_dims(st), _ar(st["version"]))        # 재료 답 꼴 — 렌더에서 터지기 전에(뿌리 10-22)
    over += RU.source_rule_static(st["script"]["M"], _origin_names(st), _rule_bench_id(st), st.get("shots") or {})
    over += p.get("jumps") or []
    st["_plan_over"] = over
    st["_plan_sheet"], st["_n_cuts"] = p.get("sheet"), p.get("cuts")
    return {"review": [_fix_review(st, "; ".join(over), p.get("sheet"), f"plan_{st['version']}")], "then": "plan_look"}


def _fix_review(st, why: str, sheet: str | None, rid: str) -> dict:
    v = st["version"]
    _, _, ww, wh = _style(v)["frame"]["window"]
    sc = st["script"]
    return _rv(rid, _q(st, "PLAN_LOOK").replace("{ar}", f"{ww}:{wh}") + (f"\n\n멈춘 이유(재료를 고쳐라): {why}" if why else "") + "\n\n대본:\n" +
               json.dumps(sc["S"], ensure_ascii=False)[:6000] + "\n\n재료:\n" + json.dumps(sc["M"], ensure_ascii=False)[:8000] + _shots_ctx(st),
               [_img(sheet)] if sheet else [], need=("ok",))


def _take_fix(st, r: dict) -> dict | None:
    M = r.get("재료")
    if not isinstance(M, dict):
        return None
    M = RU.fill_shot_max(M, st["script"]["S"], _origin_dims(st), st.get("shots") or {}, _ar(st["version"]))
    fixed = RU.fix_crop_units(M, _all_dims(st))
    if fixed:
        st["log"].append("crop 단위 바로잡음: " + "; ".join(fixed)[:300])
    bad = RU.source_rule_static(M, _origin_names(st), _rule_bench_id(st), st.get("shots") or {})
    st["script"]["M"] = M
    st["_fix_bad"] = bad
    return M


def ph_plan_look(st, m, rp, u):
    v = st["version"]
    r = _reply(rp, f"plan_{v}", ("ok",))
    over = st.get("_plan_over") or []
    if r.get("ok") and not over and not r.get("재료"):
        return {"goto": "thumb"}
    _tries(st, "plan", LIMITS["plan"])
    M = _take_fix(st, r)
    if M is None:
        probs = [str(p) for p in (r.get("problems") or []) if str(p).strip()]
        voice = [str(o) for o in over if "말속도" in str(o) or "목소리" in str(o) or "TTS" in str(o)]
        if voice:      # 엔진이 짚은 목소리 이상(줄 말속도 ±35% 밖 — 되풀이·빠뜨림)은 재료로 못 고친다 → 문장 고치기(10-26 회원 마스크편 L8)
            probs = voice
        if probs and (voice or not over):
            # 장면은 맞는데 대본·목소리 쪽 문제(예: 한 줄 말속도 이상 → 문장 고치기)를 짚었다 — 재료 답 칸이 없어 멈추던 것(10-26 회원 마스크편)
            #   → 대본 단계로 되돌린다(배치 충돌과 같은 길, 시도 수는 conflict 한도가 지킨다)
            st["log"].append("계획 검수 → 대본 다시: " + " / ".join(probs)[:300])
            _tries(st, "conflict", 2)
            st["tries"]["script"] = 0
            st["approved"] = False
            why = "장면 확인에서 대본·목소리 쪽 문제가 나왔습니다 — 아래만 고치고 내용·결은 그대로: " + " / ".join(probs)[:1200]
            return {"review": [_script_ask(st, why)], "then": "script_got"}
        raise _Stop("장면을 맞추다 막혔어요", "다시 시도해 주시면 이어 갈게요")
    return {"do": [{"id": "save_m", "cmd": "write_doc", "files": {f"{v}/재료.json": M}, "cand_dir": True, "version": v}], "then": "plan"}


# ── 9-1 썸네일 카드(맨 앞 2프레임) — 판단 주인 thumb_rule(찾는 순서·좋은 조건·3안 검사), 그리기·입히기 = render_bench → thumb.cards ──
THUMB_ASK = """완성본 맨 앞 2프레임(0.067초)에 넣을 썸네일 카드 3안을 정한다(사장님 10-24 — 본보기: 재벌 회장이 혀로 요거트 뚜껑 핥는 순간 + 입에 빨간 원 + "회장님도 뚜껑 핥는다고??").
장면은 아래 계획 시트의 컷(칸 위 글 'c번호 줄 시작~끝 초' — c번호가 part. 옛 설치본은 c번호가 없으니 왼쪽 위부터 0,1,2… 로 센다)에서만 고른다(본편에 나오는 장면만).

{good}

{order}
(회원 라인은 이미 받은 원본·재료 안에서 고른다 — 원본 연예인 영상의 결정적 순간이 1순위)

좌표 = 창 안 {ww}×{wh}. 각 안: {{"id":"A|B|C","axis":"인물순간|물건근접|정체숨김|황당사실|짤반응","mood":"funny|wow","why":"…","part":컷 번호,"t":컷 안 초,
 "circle":[[cx,cy,r]]?, "arrow":[[[x0,y0],[x1,y1]]]?, "q":[[cx,cy,px]]?, "hide":[[x,y,w,h]]?, "zoom":[x,y,w,h]?, "text":[{{"lines":["한 줄"],"xy":[cx,cy],"px":120}}]}}
JSON 하나: {{"썸네일": {{"options":[3안], "no_person_why": "인물순간 안이 없을 때만 — 왜 없는지"}}}}"""


def ph_thumb(st, m, rp, u):
    from tools.calcopy.hybrid import thumb_rule as TR
    v = st["version"]
    _, _, ww, wh = _style(v)["frame"]["window"]
    ask = THUMB_ASK.format(good=TR.GOOD, order=TR.find_order(st.get("slug")), ww=ww, wh=wh)    # 상위 편 훅 참고 한 줄(지시서 15 — slug 의 _kal/상위편_목표.json)
    if st.get("_thumb_bad"):
        ask += "\n\n지난 답 반려 이유(고쳐서 다시):\n- " + "\n- ".join(st["_thumb_bad"])
    sheet = st.get("_plan_sheet")
    return {"review": [_rv(f"thumb_{v}", ask + "\n\n대본:\n" + json.dumps((st.get("script") or {}).get("S") or {}, ensure_ascii=False)[:4000],
                           [_img(sheet)] if sheet else [], need=("썸네일",))], "then": "thumb_got"}


def ph_thumb_got(st, m, rp, u):
    from tools.calcopy.hybrid import thumb_rule as TR
    v = st["version"]
    spec = _reply(rp, f"thumb_{v}", ("썸네일",)).get("썸네일")
    bad = TR.check(spec, n_parts=st.get("_n_cuts")) if isinstance(spec, dict) else ["썸네일 답이 JSON 객체가 아니다"]
    if bad:
        n = st["tries"].get("thumb", 0) + 1
        st["tries"]["thumb"] = n
        if n <= 2:
            st["_thumb_bad"] = bad
            return {"goto": "thumb"}
        st["log"].append("썸네일 3안이 두 번 반려돼 카드 없이 렌더: " + "; ".join(bad)[:300])   # 영상은 막지 않는다(카드 = 덤)
        return {"goto": "render"}
    st.pop("_thumb_bad", None)
    return {"do": [{"id": "save_thumb", "cmd": "write_doc", "files": {f"{v}/썸네일.json": spec}, "version": v}], "then": "render"}


# ── 10 렌더 ───────────────────────────────────────────────────────────────
def ph_render(st, m, rp, u):
    return {"do": [{"id": "render", "cmd": "render", "version": st["version"], "origin_names": sorted(_origin_names(st))}], "then": "render_got"}


def ph_render_got(st, m, rp, u):
    r = m.get("render") or {}
    if r.get("conflict"):
        return _conflict_rewrite(st, r["conflict"])
    why = r.get("error") or "; ".join(r.get("jumps") or [])
    if not why and r.get("ok"):
        tl = r.get("tempo") or {}
        cap = 1.36 if str((_style(st["version"]).get("voice") or {}).get("voice_id", "")).startswith("kr-mina") else 1.26
        if tl.get("max") and float(tl["max"]) > cap:
            st["log"].append(f"배속 {tl['max']} > {cap - 0.01}")
        return {"goto": "check"}
    if r.get("error") and "원본 샷보다 길다" not in str(r["error"]) and not r.get("jumps") and st["tries"].get("render_err", 0) >= 1:
        st["log"].append("렌더 오류: " + str(r["error"])[:300])
        raise _Stop("영상을 만들다 멈췄어요", "다시 시도해 주시면 멈춘 곳부터 이어 갈게요", retry="render", auto=True)
    if r.get("error") and "원본 샷보다 길다" not in str(r["error"]) and not r.get("jumps"):
        st["tries"]["render_err"] = st["tries"].get("render_err", 0) + 1   # 처음 보는 렌더 오류도 재료로 한 번 고쳐 본다(10-22 강주은: 사진 컷 ss 없음 KeyError 로 곧장 멈춤)
        why = f"렌더 오류: {str(r['error'])[:300]} — 재료.json 컷의 빠진 칸(src·ss·crop)·형식을 바로잡아라"
    _tries(st, "render", LIMITS["render"])
    return {"review": [_fix_review(st, why, None, f"render_fix_{st['version']}")], "then": "render_fix"}


def ph_render_fix(st, m, rp, u):
    v = st["version"]
    r = _reply(rp, f"render_fix_{v}", ("ok",))
    M = _take_fix(st, r)
    if M is None:
        raise _Stop("영상을 다듬다 막혔어요", "다시 시도해 주시면 이어 갈게요")
    return {"do": [{"id": "save_m", "cmd": "write_doc", "files": {f"{v}/재료.json": M}, "cand_dir": True, "version": v}], "then": "render"}


# ── 11 검사 — 표준 §5: 1단 quality_gate.gate(전체, PC 가 잰다) → 2단 눈 E1~E8(회원 Claude) → 미통과면 고쳐 다시(2회) → 그래도면 멈춤 ──
EYE_ASK = """너는 완성본 눈 검수 담당이다(표준 §5-2 — 사장님 눈의 대리인). 1단 자동 관문은 통과했다. 기계가 못 재는 것만 아래 번호로 답한다.
자료 = 그림(1초 시트 · 벤치 나란히 시트 · 벤치 등장 대조 · 훅 3초 0.1초 띠 · 끝 2초 0.1초 띠) + 받아쓰기 대조표 + 줄↔컷 대조표(아래 글).
번호마다 v = "○"(기준 그대로) | "△"(애매 — 통과 아님) | "×"(어긋남), memo = 근거 한 줄(어느 초·어느 줄). ○ 전부여야 통과다 — 모르면 △.
{rows}
★우리 틀(결함 아님): 맨 위 제목·로고·출처 줄·우리 자막(색 강조) — 남의 글자·워터마크가 아니다.
JSON 하나: {{{keys}}}"""


def _eye_rows(upgrade: bool) -> list:
    from tools.calcopy.hybrid import quality_gate as QG          # 질문·기준 = quality_gate.EYE_Q 한 곳(우리 PC 눈 검수와 같은 질문 — 표준 §5-3)
    return list(QG.EYE_Q) + ([QG.EYE_Q9] if upgrade else [])


def ph_check(st, m, rp, u):
    return {"do": [{"id": "check", "cmd": "check", "version": st["version"], "mode": "full"}], "then": "check_got"}


def ph_check_got(st, m, rp, u):
    c = m.get("check") or {}
    if c.get("error"):
        st["auto"] = {"ok": False, "rows": [{"group": "표식", "what": "관문 실행", "ok": False, "value": str(c["error"])[:300]}]}
    else:
        st["auto"] = c.get("auto") or {"ok": False, "rows": [{"group": "표식", "what": "관문 결과 없음", "ok": False, "value": ""}]}
    st["eye_pack"] = c.get("eye_files") or []
    if not st["auto"].get("ok"):          # 1단이 ×면 눈 검수는 하지 않는다(표준 §5-2 '1단 통과 뒤') — 바로 고치기 판정으로
        st["look"] = {"ok": False, "problems": ["1단 자동 관문 미통과 — 눈 검수 생략"], "skipped": True}
        return {"goto": "check_judge"}
    rows = _eye_rows(bool(c.get("upgrade")))
    st["eye_keys"] = [k for k, _, _ in rows]
    keys = ", ".join(f'"{k}": {{"v": "○|△|×", "memo": "…"}}' for k, _, _ in rows)
    ask = EYE_ASK.format(rows="\n".join(f"{k} {q} — 기준: {c_}" for k, q, c_ in rows), keys=keys)
    texts = "".join(f"\n\n## {n}\n{str(t)[:5000]}" for n, t in (c.get("eye_texts") or {}).items())
    sc = st.get("script") or {}
    return {"review": [_rv(f"eye_{st['version']}", ask + texts + "\n\n## 대본\n" + json.dumps(sc.get("S") or {}, ensure_ascii=False)[:5000],
                           [_img(x) for x in st["eye_pack"]][:6], need=tuple(k for k, _, _ in rows))], "then": "check_look"}


def _eye_verdict(a: dict, keys: list) -> tuple[bool, list]:
    """눈 답 → (통과, 걸린 것). ○ 전부 + △ 0 이어야 통과(표준 §5-2)."""
    bad = []
    for k in keys:
        x = a.get(k)
        v = str((x or {}).get("v") if isinstance(x, dict) else x or "").strip()
        if v != "○":
            bad.append(f"{k} {v or '답 없음'}: {str((x or {}).get('memo') if isinstance(x, dict) else '')[:160]}")
    return not bad, bad


def ph_check_look(st, m, rp, u):
    v = st["version"]
    rid = f"eye_{v}"
    a = rp.get(rid)
    if not isinstance(a, dict):
        raise _Stop("확인 결과를 받지 못했어요", "다시 시도해 주시면 멈춘 곳부터 이어 갈게요", auto=True)
    keys = st.get("eye_keys") or [f"E{k}" for k in range(1, 9)]          # 물은 번호 전부(업그레이드 판은 E9 까지) — 답에 빠진 번호도 ×
    ok, bad = _eye_verdict(a, keys)
    st["eye"] = a
    st["look"] = {"ok": ok, "problems": bad}
    return {"do": [{"id": "save_eye", "cmd": "write_doc", "files": {f"{v}/눈검수.json": {"made_by": "flow 눈 2단(회원 Claude)", "ok": ok, **a}}, "version": v}],
            "then": "check_judge"}


def _check_fails(st) -> str:
    """멈춤 사유 = × 항목 번호(1단 행 이름 · 2단 E 번호)."""
    one = [str(r.get("what")) for r in (st.get("auto") or {}).get("rows") or [] if r.get("ok") is not True and not r.get("ref")]
    two = [p.split(" ")[0] for p in (st.get("look") or {}).get("problems") or [] if re.match(r"E\d", p)]
    return " / ".join(x for x in [("1단 × " + "·".join(one[:8])) if one else "", ("2단 × " + "·".join(two)) if two else ""] if x) or "알 수 없음"


def ph_check_judge(st, m, rp, u):
    v = st["version"]
    auto_ok, look = bool((st.get("auto") or {}).get("ok")), st.get("look") or {}
    if auto_ok and look.get("ok"):
        return {"goto": "deliver"}
    long = [r for r in (st.get("auto") or {}).get("rows") or [] if r.get("what") == "길이" and r.get("ok") is False]
    if long:
        return _length_rewrite(st, long[0].get("value"))
    if st["tries"].get("look", 0) >= LIMITS["look"]:
        why = _check_fails(st)
        st["log"].append("완성본 검사 멈춤: " + why)
        raise _Stop("완성본 마무리 확인에서 걸린 곳이 있어요", "다시 시도해 주시면 걸린 곳부터 고쳐서 이어 갈게요", retry="check_retry", detail=why)
    _tries(st, "look", LIMITS["look"])
    probs = json.dumps({"자동 관문 ×": [{k: r.get(k) for k in ("group", "what", "value")} for r in (st.get("auto") or {}).get("rows") or []
                                    if r.get("ok") is not True and not r.get("ref")] if not auto_ok else None,
                        "눈 검수 ×": look.get("problems")}, ensure_ascii=False)[:3000]
    return {"review": [_fix_review(st, "완성본 검사에서 걸린 것(화면·크롭·남의 글자는 재료로 고친다): " + probs + _face_hint(st), None, f"final_fix_{v}")], "then": "check_fix"}


def _length_rewrite(st, value) -> dict:
    """길이 넘침·모자람은 재료가 아니라 글로 고친다(배속 아님, 07 §4) → 대본 다시 + 회원 사인 다시. 계획(목소리 실측)·완성본 검사 두 곳이 부른다."""
    _tries(st, "length", 2)
    st["tries"]["script"] = 0
    st["approved"] = False
    return {"review": [_script_ask(st, f"완성본 길이가 판 범위를 벗어났다: {value} — 나레 글을 줄이거나(넘침) 늘려서(모자람) 범위 안으로. 내용·결은 그대로")],
            "then": "script_got"}


def _conflict_rewrite(st, c) -> dict:
    """placement conflict{axis, need, cap, cause} → 대본 다시(표준 §11-5 ㉛ — 상한을 올리지도 뼈대를 줄이지도 않는다). 사유 = 위반 audit 규칙 이름(cause).
    글자 수 위반 고치는 순서 = 부사·군더더기 제거 → 두 TTS 줄로 나누기(훅 ending 은 첫 줄) → 사인 아래 재작성(정보 낱말 보존). 회원에게는 한 줄 이유 + 사인 다시."""
    c = c if isinstance(c, dict) else {"cause": str(c)}
    cause = str(c.get("cause") or c.get("axis") or "배치 충돌")[:120]
    st["log"].append(f"배치 충돌 → 대본 다시: {json.dumps(c, ensure_ascii=False)[:300]}")
    _tries(st, "conflict", 2)
    st["tries"]["script"] = 0
    st["approved"] = False
    why = (f"배치 충돌({c.get('axis')}: 필요 {c.get('need')} > 상한 {c.get('cap')}) — 뿌리 = 대본 규칙 위반 '{cause}'. 고치는 순서: ① 부사·군더더기·중복 조사 빼기 "
           f"② 그래도 넘치면 낱말 그대로 두 TTS 줄로 나누기(훅 어미는 첫 줄에) ③ 그래도면 정보 낱말을 지키며 다시 쓰기. 내용·결은 그대로")
    return {"review": [_script_ask(st, why)], "then": "script_got", "reject": {"why": f"대본 규칙 '{cause}' 때문에 장면 배치가 맞지 않아 대본을 고칩니다", "fix": "대본을 고쳐 다시 확인받습니다"}}


def _face_hint(st) -> str:
    """'0초·첫 줄 얼굴'이 걸렸을 때 — 첫 줄 길이보다 오래 주인공이 화면에 머무는 원본 샷 목록(10-22 정재형: 짐작으로 바꾼 샷마다 주인공이 걸어 나감)."""
    rows = (st.get("auto") or {}).get("rows") or []
    bad = next((r for r in rows if "얼굴" in str(r.get("what")) and not r.get("ok")), None)
    if not bad:
        return ""
    long = [f"{stem}.mp4 #{x['i']} {x['a']:.1f}~{x['b']:.1f}초({x['b'] - x['a']:.1f}초) {x.get('desc', '')}"
            for stem, shots in (st.get("shots") or {}).items() for x in shots if x.get("who") == "main" and x["b"] - x["a"] >= 3.0][:12]
    return (f"\n\n★자동 검사 '{bad.get('what')}' 걸림: {bad.get('value')} — 첫 줄 컷 전체가 주인공 얼굴이어야 한다. 한 컷으로, 아래처럼 주인공이 오래 머무는 샷에서 고른다"
            f"(샷 안에서 ss·길이를 잡아 샷 끝을 넘지 않게):\n" + "\n".join(long)) if long else ""


def ph_check_retry(st, m, rp, u):
    """완성본 검사에서 멈춘 편을 다시 시도 — 걸린 곳부터 다시 고친다(받기·대본은 그대로)."""
    st["tries"]["look"] = 0
    v = st["version"]
    look = st.get("look") or {}
    probs = json.dumps({"자동 관문 ×": [r for r in (st.get("auto") or {}).get("rows") or [] if r.get("ok") is not True and not r.get("ref")],
                        "눈 검수 ×": look.get("problems")}, ensure_ascii=False)[:3000]
    return {"review": [_fix_review(st, "완성본 검사에서 걸린 것: " + probs + _face_hint(st), None, f"final_fix_{v}")], "then": "check_fix"}


def ph_check_fix(st, m, rp, u):
    v = st["version"]
    r = _reply(rp, f"final_fix_{v}", ("ok",))
    M = _take_fix(st, r)
    if M is None:
        raise _Stop("완성본 마무리 확인을 통과하지 못했어요", "숏템 피드백으로 알려 주시면 확인해 드릴게요 · 다른 소재로 갈까요?")
    return {"do": [{"id": "save_m", "cmd": "write_doc", "files": {f"{v}/재료.json": M}, "cand_dir": True, "version": v}], "then": "render"}


# ── 12·13 납품·정리 ───────────────────────────────────────────────────────
def ph_deliver(st, m, rp, u):
    return {"do": [{"id": "final", "cmd": "finish", "version": st["version"], "title": script_view(st)["title"]}], "then": "finished"}


def ph_finished(st, m, rp, u):
    f = m.get("final") or {}
    if not f.get("video"):
        raise _Stop("완성본 파일을 찾지 못했어요", "다시 시도해 주시면 이어 갈게요", auto=True)
    asr_single = not ((st.get("env") or {}).get("keys") or {}).get("speechmatics")
    if not ((st.get("auto") or {}).get("ok") and (st.get("look") or {}).get("ok")):     # 관문 2단을 안 거친 완성본은 내지 않는다(표준 §5 — 다른 길로 deliver 에 와도)
        raise _Stop("완성본 마무리 확인을 아직 통과하지 않았어요", "다시 시도해 주시면 확인부터 다시 할게요", retry="check", detail=_check_fails(st))
    return {"done": {"video": f["video"], "title": script_view(st)["title"], "auto_ok": bool((st.get("auto") or {}).get("ok")),
                     "look_ok": bool((st.get("look") or {}).get("ok")), "gate": (st.get("auto") or {}).get("report"), "asr_single": asr_single,
                     "note": "귀 확인 없음(스피치매틱스 키 없음 — 위스퍼와 눈으로만 대조)" if asr_single else ""}}


# ══ 형식별 질문·처리기(관제 263 지시서 08 · 표준 §7) ══════════════════════════════════════════
BRIEFS = Path(__file__).with_name("briefs")


def _brief(name: str) -> str:
    """해외원본형 노하우 글(briefs/*.md) — 우리 PC 워커와 회원 흐름이 같은 글을 읽는다(두 벌 금지)."""
    p = BRIEFS / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


TRAPS_FOREIGN = {   # 해외원본형 단계별 함정 — 연예인형 TRAPS(연예인 본인 채널·방송 원본)를 쓰지 않는다
    "origin": ["같은 촬영분만 같은 영상 — 같은 제품을 다른 사람이 쓴 영상·같은 사람의 다른 영상은 다르다(01b §5)",
               "원본 = 해외 채널마다 가장 먼저 올린 것 — 한국 재편집보다 늦게 올린 해외 계정은 퍼 간 쪽(01b §6)",
               "모음 편은 원본이 여럿 — 렌즈 장면 4장이 서로 다른 원본을 가리킬 수 있다"],
    "product": ["원본 화면 포장·로고·모양·색이 같은 것이 같은 제품 — 없으면 같은 종류 중 후기 많은 비슷한 제품(현장썰 규칙)", "의약품·의료기기는 만들지 않는다"],
    "research": ["원본 출연자 본인 말만 원음 줄로 — 남(촬영자·댓글)의 말은 원음 줄로 쓰지 않는다", "효능 단정·질병 이름·다른 회사 숫자 금지"],
    "material": ["박힌 자막·워터마크는 잘라서 피하지 않는다 — 지우거나(회원 VMake 키) 흐린다(확대 1.0)", "다른 제품(비슷한 다른 브랜드)이 나오는 구간은 쓰지 않는다(10-24 ep13)"],
    "asr": ["외국어 받아쓰기는 고유명사·약어를 틀린다 — 원문(said)은 들리는 대로, 번역 자막은 뜻대로"],
    "script": ["박자·훅·끝 줄 꼴은 판 brief 가 정한다", "빠른 영문 약어는 목소리에서 빼고 자막에만(ep13 PDRN)"],
    "plan": ["원본별 시간순·재사용 0·확대 1.0(세로 원본은 폭 전체)", "컷이 원본 샷보다 길면 렌더가 멈춘다"],
    "check": ["1초 시트 사이로 0.5초 장면 전환이 지나갈 수 있다(#1)", "남의 글자(박힌 자막) 남았나 — 흐림 칸이 그 샷을 다 덮었나"],
}

REF_READ_FOREIGN = """너는 해외원본형 소재 판독 담당이다. 아래는 회원이 준 쇼츠(소재)의 1초 장면 시트·큰 장면 한 장·제목·설명·받아쓰기다.
- ref_kind: "korean_reedit" = 한국 채널이 해외 영상을 가져와 한국어 자막·나레를 입힌 재편집 / "overseas_origin" = 해외 출연자 본인이 올린 원본(제목·말·채널이 외국어).
- is_shopping: 영상 속 사람이 실제로 쓰는·먹는 **제품**이 화면에 나오면 true(제품이 말로만·의약품·의료기기면 false).
- product_words: 제품을 가리키는 낱말(한국어·영어 둘 다 — 화면 글자·설명란·말에서). brand_hint: 화면·설명란에 보이는 브랜드·제품 이름 그대로, 없으면 ''.
- queries_en: 같은 제품을 다른 해외 사람이 처음 써 보는 쇼츠를 찾을 영어 검색어 2~4개('<브랜드> <제품> reaction'·'trying korean <제품>' 꼴).
- people: 화면의 해외 출연자 수·옷·머리 한 줄(같은 영상 판정 단서).
JSON 하나: {"ref_kind": "korean_reedit|overseas_origin", "is_shopping": true, "product_words": ["…"], "brand_hint": "…", "queries_en": ["…"], "people": "…", "why": "한 줄"}"""

PEER_PICK_FOREIGN = """너는 같은 제품 해외 반응 고르기 담당이다. 이미 정한 원본과 **같은 제품**({product})을 **다른 해외 사람**이 써 보고 반응하는 쇼츠를 고른다.
첫 그림 맨 위 줄(S1~S4) = 이미 정한 원본 장면, 아래 파란 번호 칸 = 후보 썸네일(번호 = 아래 후보 목록 n).
고를 것: 해외 출연자(한국 채널·한국어 제목 재편집 금지) · 그 제품이 또렷이 보이고 반응이 큰 것 · 박힌 자막이 적은 것 · 이미 정한 원본과 같은 촬영분이 아닌 것 · 다른 제품이면 고르지 않는다. 최대 2개, 없으면 빈 목록.
JSON 하나: {"picks": [번호, …], "why": "한 줄"}"""

PRODUCT_PICK_FOREIGN = """너는 제품 특정 담당이다. 해외 원본 영상들의 장면 시트(원본마다 한 장, 칸 = 1초 또는 적힌 간격, 왼쪽 위 첫 칸 = 0초)에서
원본 출연자가 쓰는 그 제품의 **전체 모양**이 보이는 장면을 2~4개 골라라(포장 라벨·로고가 보이는 장면이 최고, 너무 작게 부분만 자르지 않는다).
JSON 하나: {"scenes": [{"src": "원본 파일 이름", "t": 파일 초, "crop": [x, y, w, h] (원본 픽셀)}], "brand_words": ["화면·말·설명란의 브랜드·제품 이름"], "coupang_queries": ["쿠팡 검색어 2~4개(한국어)"]}"""

PRODUCT_BEST_FOREIGN = """너는 대체 제품 고르기 담당이다(같은 제품이 없으면 쿠팡에서 후기 많고 좋은 비슷한 제품 — 현장썰 규칙). 원본 출연자가 쓴 것과 **같은 종류·같은 쓰임**인 쿠팡 후보 중
후기(rating 의 괄호 숫자) 많고 별점 높은 것 하나를 골라라. 광고(is_ad)·묶음 이상한 것은 뒤로. 같은 종류가 없으면 product_id ''.
JSON 하나: {"product_id": "…", "name": "…", "why": "고른 이유 한 줄(후기 수·별점)", "member_why": "회원에게 보일 쉬운 말 한 줄 — 종류·색·모양이 어떻게 비슷한지(예 '같은 기미 앰플이고 용량·병 모양이 비슷해요')", "category": "화장품|생활용품|식품|의류|의약품|의료기기|기타"}"""

RESEARCH_FOREIGN = """너는 조사 담당이다. 이 편의 `조사.md` 한 파일 내용을 써라. 웹 검색으로 사실을 확인하고 출처 URL 을 적는다.
## 할 일
1. 원본마다 자막·받아쓰기(파일 초·말)에서 원본 출연자가 **본인 입으로 말한** 제품 반응·설명 구간을 표로(원본 id · 파일 초 · 원문 · 한국어 뜻).
2. 제품 사실: 브랜드 공식·판매처 설명 · 리뷰 2개 이상 · 원본 출연자 말 — 출처별 표. 시험 수치가 아닌 것은 '브랜드 문구'로. 최상급·범위 숫자 단정 금지.
3. 금지 품목(의약품·의료기기·기능성 효능 주장)인지 결론 1줄. 멈출 이유가 있으면 stop 에 적는다.
4. 원음으로 쓸 구간 spans: 원본 출연자 본인의 반응·말이 또렷한 자리만, **원본 파일 이름(src)과 그 파일 초**. 남의 말·작은 소리 제외. 한 구간 1~4초, 원본 통틀어 2~4개(O1·O2…).
## 조사.md 머리글(이 순서 그대로)
## 0 결론 / ## 1 출처 / ## 2 원음 / ## 3 사실(f번호 + 출처 URL 또는 '원본 id n초') / ## 4 금지 품목 / ## 5 검색어 / ## 6 확인 못 한 것
## 금지
지어내기 · 수치 어림 · 원본에 없는 말을 본인 말로 적기 · 다른 브랜드 제품을 같은 제품으로 적기 · 다른 회사 숫자 · 질병 이름.
JSON 하나: {"stop": "", "조사_md": "마크다운 전문", "keywords": ["제품명", "영문명"], "queries": ["…"], "exclude": ["모음", "TOP"],
 "spans": [{"src": "원본 파일 이름", "a": 파일 초, "b": 초, "tag": "O1"}], "facts": [{"id": "f1", "fact": "…", "src": "URL 또는 '원본 id n초'"}]}"""

SHOT_READ_FOREIGN = """너는 원본 샷 판독 담당이다. 해외 원본 영상을 카메라가 바뀌는 곳마다 나눈 샷들의 가운데 장면이다(칸마다 '#번호 시작~끝초').
샷마다: who = "main"(원본 주인공 혼자 또는 크게) · "both"(주인공과 다른 사람 함께) · "other"(주인공 없이 다른 사람만) · "none"(사람 없음),
product = 그 제품({kind})이 또렷이 보이면 true, text = 영상 위에 덧씌운 자막·제목 띠·워터마크·스티커 글자마다 [x0,y0,x1,y1](0~1, 왼쪽 위 기준, 없으면 [] — 제품 포장 글자·옷 글자는 넣지 않는다),
other_product = 그 제품이 아닌 다른 제품이 주로 보이면 true, cx = 주인공 얼굴 가운데의 가로 위치(0~1, 없으면 null), desc = 한국어 10자 안팎.
JSON 하나: {{"shots": [{{"i": 번호, "who": "main", "product": false, "other_product": false, "text": [[0.1, 0.85, 0.9, 0.95]], "cx": 0.5, "desc": "…"}}]}}"""

SCRIPT_FOREIGN = """너는 대본 작가다(오푸스). 해외원본형 — 해외 원본 영상(2~3개)을 재료로 판 규칙·결 기준 그대로 이 편의 대본·재료·근거를 써라. 대본 검사를 통과해야 한다 — 걸린 이유가 아래에 있으면 고쳐서 다시.
재료의 cand_dir 는 비워 둔다(PC 가 채운다), 컷 src 는 받은 파일 이름(원본 = '<영상 id>.mp4', 상품 사진 = prod_*.jpg).
★확대는 1.0 — 세로 원본은 폭 전체(crop [0, y, 원본 폭, 원본 폭 ÷ 창 비율]), 박힌 글자는 엔진이 지우거나 흐린다(crop 으로 피하지 않는다).
★CTA·금액·질병·효능 단정 없음. 창작 허용 = 나레의 계기·감상·전언 말투 / 근거 필수 = 제품 속성·원리·반응 내용(줄마다 근거).

""" + "{brief}"

PLAN_LOOK_FOREIGN = """너는 장면 검수 담당이다(해외원본형). 계획 시트를 보고 컷마다: 대사와 화면이 맞나 · 남의 글자(원본에 박힌 자막·워터마크 — 재료.blur 가 덮나) ·
다른 제품(비슷한 다른 브랜드)이 나오나 · 원본별 시간순·같은 장면 재사용 0 · A-B-A 끼움 · 0초·훅 = 결과(놀람 반응 얼굴 또는 제품 크게).
★확대는 1.0 — 세로 원본은 폭 전체(높이 = 폭 ÷ 창 비율 {ar}), 가로 원본은 높이 전체. 숫자 crop 으로 좁혀 확대하지 않는다. crop 은 원본 픽셀 정수[x, y, w, h].
박힌 글자는 재료.blur {원본 파일: [[x, y, w, h, 시작초, 끝초]]}(원본 픽셀·원본 초)로 흐린다. 시트 칸 = 렌더러가 실제로 자를 화면 그대로다.
고칠 것이 있으면 재료 전체를 고쳐서 돌려준다(없으면 null).
★우리 틀(결함 아님): 맨 위 제목 · 로고 · 출처 줄 · 우리 자막(색 강조) — 남의 글자·워터마크가 아니다.
JSON 하나: {"ok": true, "problems": ["…"], "재료": null}"""

TOPIC_READ_SHOP = """너는 쇼핑형 소재 판독 담당이다. 아래는 회원이 준 소재 영상(제품 썰·게시글·리뷰)의 1초 장면 시트·제목·설명·받아쓰기다.
- is_shopping: 쿠팡에서 살 수 있는 **제품** 이야기면 true(의약품·의료기기·서비스면 false).
- product_words: 제품을 가리키는 낱말. coupang_queries: 쿠팡 검색어 2~4개. story: 이 소재의 썰 요지 2줄(누가·무엇에 놀랐나 — 화면·말에 있는 것만).
JSON 하나: {"is_shopping": true, "product_words": ["…"], "coupang_queries": ["…"], "story": "…", "why": "한 줄"}"""

PRODUCT_SAME_SHOP = """너는 제품 판정 담당이다(쇼핑형). 첫 그림 = 소재 영상 1초 시트, 마지막 그림 = 쿠팡 후보 사진 시트. 소재 영상의 그 제품과 포장·모양·색이 **같은 제품** 하나를 골라라.
같은 제품이 없으면 같은 종류·같은 쓰임 중 후기 많고 별점 높은 것(mode 'alt'). 그것도 없으면 product_id ''.
JSON 하나: {"product_id": "…", "name": "…", "why": "대조 근거 한 줄", "mode": "exact|alt", "category": "화장품|생활용품|식품|의류|의약품|의료기기|기타"}"""

RESEARCH_SHOP = """너는 조사 담당이다(쇼핑형). 이 편의 `조사.md` 한 파일 내용을 써라. 웹 검색으로 사실을 확인하고 출처 URL 을 적는다.
근거 = 소재 영상 말·화면 · 쿠팡 베스트 후기(r번호) · 네이버 글(n번호, 그 상품 이야기인 부분만) · 브랜드 공식·판매처 설명.
## 조사.md 머리글(이 순서 그대로)
## 0 결론 / ## 1 출처 / ## 2 원음 / ## 3 사실(f번호 + 출처 URL) / ## 4 금지 품목 / ## 5 검색어 / ## 6 확인 못 한 것
(쇼핑형은 원음 줄이 없다 — '## 2 원음' 절은 '없음' 한 줄)
JSON 하나: {"stop": "", "조사_md": "마크다운 전문", "keywords": ["제품명"], "queries": ["재료 영상 검색어 5~8개"], "exclude": ["모음", "TOP", "가성비"],
 "spans": [], "facts": [{"id": "f1", "fact": "…", "src": "URL 또는 r번호·n번호"}]}"""

SCRIPT_SHOP = """너는 대본 작가다(오푸스). 쇼핑형 — 판 규칙·결 기준 그대로 이 편의 대본·재료·근거를 써라(원음 줄 없음 — kind tts, 판이 자막 줄(sub)을 쓰면 그대로). 대본 검사를 통과해야 한다.
근거 = 쿠팡 베스트 후기(r번호 — 셀링포인트·소구점 전언)·네이버 글(n번호)·조사 사실(f번호). 후기 개수·별점 숫자는 쓰지 않는다. CTA·금액·질병·효능 단정 없음.
재료의 cand_dir 는 비워 둔다, 컷 src 는 받은 재료 파일 이름(제품 영상·prod_*.jpg 사진 — 사진은 move: in·out·left·right). 컷마다 see — 그 줄 대사의 동작·상태가 그 컷에 보여야 한다."""

PLAN_LOOK_SHOP = """너는 장면 검수 담당이다(쇼핑형). 계획 시트를 보고 컷마다: 대사와 화면이 맞나 · 남의 글자·워터마크 · 남의 얼굴(재료 영상의 리뷰어·광고 모델) · A-B-A 끼움.
crop 은 원본 픽셀 정수[x, y, w, h] — 숫자 crop 은 엔진이 바꾸지 않는다. 박힌 글자는 재료.blur {파일: [[x, y, w, h, 시작초, 끝초]]}로 흐린다. 고칠 것이 있으면 재료 전체를 고쳐서 돌려준다(없으면 null).
★우리 틀(결함 아님): 맨 위 제목 · 로고 · 우리 자막(색 강조).
JSON 하나: {"ok": true, "problems": ["…"], "재료": null}"""

_Q = {   # 형식별 질문 — 없으면 공용(연예인형) 상수
    "해외원본형": {"PLAN_LOOK": PLAN_LOOK_FOREIGN, "PRODUCT_BEST": PRODUCT_BEST_FOREIGN, "SCRIPT": None},
    "쇼핑형": {"PLAN_LOOK": PLAN_LOOK_SHOP, "SCRIPT": SCRIPT_SHOP},
}


def _q(st: dict, key: str) -> str:
    f = _fmt(st)
    if f == "해외원본형" and key == "SCRIPT":
        return SCRIPT_FOREIGN.replace("{brief}", _brief("script_foreign.md"))
    return (_Q.get(f) or {}).get(key) or globals()[key]


def _foreign_script_ctx(st: dict) -> str:
    """해외원본형 대본 질문에 더하는 것 — 원본 목록(시간순)·박힌 글자 처리·재료 초안(materials_draft)."""
    if _fmt(st) != "해외원본형":
        return ""
    O = [f"- {o.get('id')} · {(o.get('info') or {}).get('channel')} · '{(o.get('info') or {}).get('title')}' · 날짜 {(o.get('info') or {}).get('date')} · 파일 "
         + ", ".join(f"{x['name']}({x.get('w')}x{x.get('h')}, {x.get('dur')}초)" for x in o.get("files") or []) for o in st.get("origins") or []]
    tf = st.get("text_fix") or {}
    fix = ((f"VMake 로 지움(렌더 전, 고른 컷 중 박힌 글자 있는 구간만): {tf.get('need')} — 글자 샷도 그대로 골라 써도 된다" if tf.get("mode") == "vmake" else "지울 파일 없음")
           + f" · 지우기 전·실패 구간 = 엔진이 재료.blur 로 흐림(방식 {tf.get('mode') or '-'}: {tf.get('why') or ''})")
    dr = st.get("mat_draft") or {}
    return ("\n\n## 해외 원본(시간순 — 이 순서로 쓴다)\n" + "\n".join(O) + "\n\n## 박힌 글자 처리\n" + fix +
            "\n\n## 재료 초안(materials_draft — 원본별 시간순·재사용 0·확대 1.0 구간표, 줄마다 이 안에서 고른다)\n" + json.dumps(dr, ensure_ascii=False)[:5000])


# ── 해외원본형 처리기 ─────────────────────────────────────────────────────
F_ORIGINS_MAX = 3      # 원본 2~3개(판 v2 upgrades 4 '원본 2~3개 시간순')
F_PEER_N = 12          # 같은 제품 다른 해외 반응 검색 후보 수


def f_bench_got(st, m, rp, u):
    b = m.get("bench") or {}
    if b.get("error"):
        raise _Stop("영상을 받지 못했어요", "영상 주소가 맞는지, 유튜브 로그인 연결이 되어 있는지 확인해 주세요", auto=True)
    st["bench"] = {k: b.get(k) for k in ("id", "title", "channel", "date", "dur", "desc", "sheet", "big")}
    st["bench_lines"] = b.get("lines") or []
    return {"review": [_rv("ref_read", REF_READ_FOREIGN + "\n\n" + _brief("origin_foreign.md") + "\n\n제목: " + str(b.get("title")) + "\n채널: " + str(b.get("channel")) +
                           "\n설명: " + str(b.get("desc") or "")[:1500] + "\n받아쓰기: " + " / ".join(str(l.get("text")) for l in st["bench_lines"])[:3000],
                           ([_img(b["sheet"])] if b.get("sheet") else []) + ([_img(b["big"])] if b.get("big") else []),
                           need=("ref_kind", "is_shopping", "product_words", "queries_en"))], "then": "ref_read"}


def f_ref_read(st, m, rp, u):
    from tools.calcopy import origin_find as OF
    r = _reply(rp, "ref_read", ("ref_kind", "is_shopping", "product_words", "queries_en"))
    if not r.get("is_shopping"):
        raise _Stop("제품이 화면에 나오는 영상이 아니에요", "외국인이 제품을 써 보는 쇼츠 주소를 주세요", final=True)
    B = st["bench"]
    korean = OF.is_korean(str(B.get("title") or ""), str(B.get("channel") or "")) or r.get("ref_kind") == "korean_reedit"   # 한글 = 규칙(주인 is_korean), 판독은 보탬
    st["read"] = {**r, "celeb": "", "korean": korean}
    st["origins"] = []
    if korean:
        st["log"].append("소재 = 한국 재편집 → 렌즈로 해외 원본")
        return {"do": [{"id": "of", "cmd": "origin_foreign", "mode": "lens", "bench_id": B.get("id")}], "then": "of_got"}
    st["origins"] = [{"id": B.get("id"), "info": {k: B.get(k) for k in ("id", "title", "channel", "date", "dur")}, "how": "소재 = 해외 원본"}]
    st["log"].append("소재 = 해외 원본 → 첫 원본, 같은 제품 다른 해외 반응 찾기")
    return {"goto": "of_peers"}


def f_of_peers(st, m, rp, u):
    st["_peers_done"] = True
    qs = [q for q in st["read"].get("queries_en") or [] if q][:4]
    if not qs:
        return {"goto": "of_fetch"}
    return {"do": [{"id": "of", "cmd": "origin_foreign", "mode": "peers", "queries": qs, "n": F_PEER_N,
                    "skip": [o["id"] for o in st["origins"]] + [st["bench"].get("id")]}], "then": "of_got"}


def f_of_got(st, m, rp, u):
    o = m.get("of") or {}
    mode = o.get("mode") or ("peers" if st.get("_peers_done") else "lens")
    cands = [c for c in o.get("cands") or [] if isinstance(c, dict)]
    st["of_cands"], st["of_mode"] = cands, mode
    if o.get("error") or not cands or not o.get("sheets"):
        st["log"].append(f"원본 후보 없음({mode}): {str(o.get('error') or '')[:200]}")
        if mode == "lens":
            raise _Stop("해외 원본을 못 찾았어요", "원본 영상 주소를 주시면 바로 만들 수 있어요 · 다른 소재로 갈까요?")
        return {"goto": "of_fetch"}
    rows = "\n".join(f"{c['n']}. {c.get('platform')}:{c.get('id')} · {c.get('channel')} · '{str(c.get('title') or '')[:70]}' · {c.get('date')} · 한글 {bool(c.get('korean'))}"
                     for c in cands)
    if mode == "lens":
        from tools.calcopy import origin_find as OF
        ask = OF.JUDGE_PROMPT + "\n\n" + _brief("origin_foreign.md") + "\n\n후보 목록(칸 번호 = n):\n" + rows
        return {"review": [_rv("of_judge", ask, [_img(x) for x in o["sheets"]][:4], model="sonnet", need=("same",))], "then": "of_pick"}
    prod = ", ".join([str(st["read"].get("brand_hint") or "")] + [str(w) for w in st["read"].get("product_words") or []][:3]).strip(", ")
    ask = PEER_PICK_FOREIGN.replace("{product}", prod) + "\n\n" + _brief("origin_foreign.md") + "\n\n후보 목록(칸 번호 = n):\n" + rows
    return {"review": [_rv("of_peer", ask, [_img(x) for x in o["sheets"]][:4], model="sonnet", need=("picks",))], "then": "of_pick"}


def f_of_pick(st, m, rp, u):
    from tools.calcopy import origin_find as OF
    cands = st.get("of_cands") or []
    by_n = {int(c["n"]): c for c in cands if str(c.get("n", "")).isdigit() or isinstance(c.get("n"), int)}
    if st.get("of_mode") == "lens":
        a = _reply(rp, "of_judge", ("same",))
        same = [by_n[int(n)] for n in a.get("same") or [] if str(n).isdigit() and int(n) in by_n]
        seed = {"key": f"yt:{st['bench'].get('id')}", "korean": True, "date": st["bench"].get("date")}
        vs = [seed] + [{**c, "key": f"{c.get('platform')}:{c.get('id')}"} for c in same]
        picked = [v for v in OF.pick_origins(vs) if v.get("platform") == "yt"]       # 주인 = origin_find.pick_origins(해외 채널마다 가장 먼저·한국 재편집보다 늦은 것 제외)
        skipped = [v["key"] for v in OF.pick_origins(vs) if v.get("platform") != "yt"]
        if skipped:
            st["log"].append(f"유튜브 밖 원본은 받기 길이 없어 뺌: {skipped}")
        for v in picked[:F_ORIGINS_MAX]:
            st["origins"].append({"id": v["id"], "info": {k: v.get(k) for k in ("id", "title", "channel", "date", "dur")}, "how": "렌즈 같은 촬영분"})
        st["log"].append(f"렌즈 같은 영상 {len(same)}개 → 원본 {[o['id'] for o in st['origins']]}: {str(a.get('why'))[:120]}")
        if not st["origins"]:
            raise _Stop("해외 원본을 못 찾았어요", "원본 영상 주소를 주시면 바로 만들 수 있어요 · 다른 소재로 갈까요?")
        if len(st["origins"]) < 2 and not st.get("_peers_done"):
            return {"goto": "of_peers"}
        return {"goto": "of_fetch"}
    a = _reply(rp, "of_peer", ("picks",))
    have = {o["id"] for o in st["origins"]}
    for n in a.get("picks") or []:
        c = by_n.get(int(n)) if str(n).isdigit() else None
        if not c or c.get("id") in have or c.get("korean") or c.get("platform") != "yt":
            continue
        if len(st["origins"]) >= F_ORIGINS_MAX:
            break
        st["origins"].append({"id": c["id"], "info": {k: c.get(k) for k in ("id", "title", "channel", "date", "dur")}, "how": "같은 제품 다른 해외 반응"})
        have.add(c["id"])
    st["log"].append(f"같은 제품 다른 해외 반응 → 원본 {[o['id'] for o in st['origins']]}: {str(a.get('why'))[:120]}")
    return {"goto": "of_fetch"}


def f_of_fetch(st, m, rp, u):
    """원본 받기(해외 쇼츠는 짧다 — 통째로). 순서 = 고른 순서(소재의 원본 → 렌즈 원본(올린 날짜 순, pick_origins) → 같은 제품 다른 반응) —
    판 v2 '원본 2~3개 시간순'은 원본마다 그 안에서 시간순이고, 이어 붙이는 순서는 주 원본이 먼저(10-24 ep13: MissDarcei → milky)."""
    return {"do": [{"id": f"og_{k}", "cmd": "origin_get", "vid": o["id"], "a": 0.0, "b": float((o.get("info") or {}).get("dur") or 600), "ts": [], "full": True}
                   for k, o in enumerate(st["origins"])], "then": "of_fetched"}


def f_of_fetched(st, m, rp, u):
    files, keep = [], []
    for k, o in enumerate(st["origins"]):
        g = m.get(f"og_{k}") or {}
        if g.get("error") or not g.get("files"):
            st["log"].append(f"원본 {o['id']} 받기 실패: {str(g.get('error'))[:160]}")
            continue
        o["files"] = g["files"]
        keep.append(o)
        files += g["files"]
    if not keep:
        raise _Stop("해외 원본 영상을 받지 못했어요", "잠시 뒤 다시 시도해 주시면 받기부터 이어 갈게요", retry="of_fetch", auto=True)
    st["origins"] = keep
    o0 = keep[0]
    st["origin"] = {"id": o0["id"], "url": f"https://www.youtube.com/watch?v={o0['id']}", "files": files, "offset": 0.0, "offset_measured": True,
                    "matched": [], "window": [0.0, max(float(f.get("dur") or 0) for f in files)], "info": o0.get("info") or {}}
    return {"goto": "f_product_sheet"}


def f_product_sheet(st, m, rp, u):
    do = []
    for k, f in enumerate(st["origin"]["files"]):
        dur = float(f.get("dur") or 36)
        fps = 1.0 if dur <= 36 else round(36 / dur, 4)
        do.append({"id": f"psheet_{k}", "cmd": "sheet", "src": "src/" + f["name"], "dst": f"look/origin_sheet_{k}.jpg", "fps": fps, "cols": 6, "rows": 6, "w": 240, "ss": 0, "t": dur})
    return {"do": do, "then": "f_product_pick"}


def f_product_pick(st, m, rp, u):
    shs = [(f, (m.get(f"psheet_{k}") or {}).get("file")) for k, f in enumerate(st["origin"]["files"])]
    shs = [(f, x) for f, x in shs if x]
    if not shs:
        raise _Stop("원본 장면을 열지 못했어요", "다시 시도해 주시면 이어 갈게요", auto=True)
    note = "\n".join(f"{k + 1}번째 그림 = {f['name']}(길이 {f.get('dur')}초) — 칸 간격 {1 if float(f.get('dur') or 0) <= 36 else round(float(f['dur']) / 36, 2)}초"
                     for k, (f, _) in enumerate(shs))
    R0 = st["read"]
    return {"review": [_rv("product_pick", PRODUCT_PICK_FOREIGN + f"\n\n{note}\n마지막 그림 = 소재 쇼츠 1초 시트. 제품 낱말: {R0.get('product_words')} · 브랜드 단서: {R0.get('brand_hint')}",
                           [_img(x) for _, x in shs] + ([_img(st["bench"]["sheet"])] if st["bench"].get("sheet") else []), need=("scenes", "coupang_queries"))],
            "then": "f_product_cands"}


def f_product_cands(st, m, rp, u):
    r = _reply(rp, "product_pick", ("scenes", "coupang_queries"))
    names = {f["name"] for f in st["origin"]["files"]}
    scenes = [s for s in r.get("scenes") or [] if isinstance(s, dict) and isinstance(s.get("t"), (int, float))][:4]
    if not scenes:
        raise _Stop("원본 영상에 제품이 화면으로 나오지 않아요", "제품이 화면에 나오는 다른 영상 주소를 주세요", final=True)
    st["product_pick"] = r
    qs = [q for q in r.get("coupang_queries") or [] if q][:4] + [w for w in r.get("brand_words") or [] if w][:2]
    st["coupang_qs"] = qs
    by_src: dict = {}
    for s in scenes:
        src = str(s.get("src") or "") if str(s.get("src") or "") in names else st["origin"]["files"][0]["name"]
        by_src.setdefault(src, []).append(s)
    do = [{"id": f"shots_{k}", "cmd": "frames", "src": "src/" + src, "items": items, "prefix": f"look/p{k}_"} for k, (src, items) in enumerate(by_src.items())]
    st["_shot_ids"] = [f"shots_{k}" for k in range(len(by_src))]
    return {"do": do + [{"id": "coupang", "cmd": "coupang", "queries": qs}], "then": "f_product_same"}


def f_product_same(st, m, rp, u):
    shots = [x for k in st.get("_shot_ids") or [] for x in (m.get(k) or {}).get("files") or []]
    return ph_product_same(st, {**m, "shots": {"files": shots}}, rp, u)      # 쿠팡 후보 사진 시트·같은 제품 판정은 공용(질문만 형식별)


def f_research(st, m, rp, u):
    return {"do": [{"id": f"words_{k}", "cmd": "origin_words", "vid": f["name"].rsplit(".", 1)[0], "src": "src/" + f["name"], "t0": 0.0}
                   for k, f in enumerate(st["origin"]["files"])], "then": "f_research_got"}


def f_research_got(st, m, rp, u, fail: str = ""):
    W = st.get("_fwords") or {}
    for k, f in enumerate(st["origin"]["files"]):
        if m.get(f"words_{k}"):
            W[f["name"]] = m[f"words_{k}"]
    st["_fwords"] = W
    txt = "\n".join(f"### {n} ({w.get('from') or '받아쓰기'}, 파일 초)\n" + " ".join(f"[{round(float(t), 1)}]{x}" for t, x in (w.get("words") or []))[:4000]
                    for n, w in W.items())
    O = "\n".join(f"- {o['id']} {(o.get('info') or {}).get('channel')} '{(o.get('info') or {}).get('title')}' 파일 {[x['name'] for x in o.get('files') or []]}"
                  for o in st.get("origins") or [])
    PR = st["product"]
    ask = (RESEARCH_FOREIGN + f"\n\n## 원본(파일 0초 = 원본 0초)\n{O}\n\n## 자막·받아쓰기\n{txt}\n\n## 제품\n{json.dumps(PR, ensure_ascii=False)}" +
           (f"\n\n## 지난 답에서 걸린 것(고쳐라)\n{fail}" if fail else ""))
    return {"review": [_rv("research", ask, [_img(x) for x in st.get("product_shots") or []][:3], need=("조사_md", "keywords", "queries", "spans"))],
            "then": "f_research_check", "reject": {"why": fail, "fix": "조사를 고쳐 다시"} if fail else None}


def f_research_check(st, m, rp, u):
    r = _reply(rp, "research", ("조사_md", "keywords", "queries", "spans"))
    if r.get("stop"):
        st["log"].append("조사 멈춤: " + str(r["stop"])[:400])
        raise _Stop("조사해 보니 이 제품은 만들 수 없는 소재예요(의약품·금지 품목 등)", "다른 소재 영상을 주세요", final=True)
    md, bad = str(r.get("조사_md") or ""), []
    for h in ("결론", "출처", "원음", "사실", "금지", "확인 못"):
        if h not in md:
            bad.append(f"조사.md 에 '{h}' 절이 없다")
    durs = {f["name"]: float(f.get("dur") or 1e9) for f in st["origin"]["files"]}
    spans = [s for s in r.get("spans") or [] if isinstance(s, dict)]
    if not spans:
        bad.append("원음 구간(spans)이 없다")
    for s in spans:
        src = str(s.get("src") or "")
        if src not in durs:
            bad.append(f"원음 구간 {s.get('tag')} 의 src '{src}' 가 받은 원본 파일이 아니다({list(durs)})")
            continue
        try:
            if not (0 <= float(s["a"]) < float(s["b"]) <= durs[src] + 0.5):
                bad.append(f"원음 구간 {s.get('tag')} {s.get('a')}~{s.get('b')} 가 {src} 길이({durs[src]:.1f}초) 밖")
        except (KeyError, TypeError, ValueError):
            bad.append(f"원음 구간 꼴이 틀렸다: {s}")
    for f in r.get("facts") or []:
        if isinstance(f, dict) and not str(f.get("src") or "").strip():
            bad.append(f"사실 {f.get('id')} 에 출처가 없다")
    if bad:
        _tries(st, "research", 3)
        return f_research_got(st, {}, {}, u, fail="; ".join(bad))
    st["research"] = {k: r.get(k) for k in ("keywords", "queries", "exclude", "spans", "facts")}
    st["research_md"] = md
    return {"do": [{"id": "save_research", "cmd": "write_doc", "files": {"조사/조사.md": md}}], "then": "f_material"}


def f_material(st, m, rp, u):
    """원본 샷 표(카메라 바뀌는 곳·박힌 글자 상자) + 쿠팡 상품 사진 — 해외원본형 재료는 원본이 주재료(남의 리뷰 영상 검색은 안 한다)."""
    return {"do": [{"id": "shots", "cmd": "shot_sheets", "files": ["src/" + f["name"] for f in st["origin"]["files"]], "window": None},
                   {"id": "stills", "cmd": "product_stills", "product_id": (st.get("product") or {}).get("product_id"), "n": 3}], "then": "f_material_got"}


def f_material_got(st, m, rp, u):
    st["material"] = {"files": (m.get("stills") or {}).get("files") or []}
    sh = m.get("shots") or {}
    st["shots"] = sh.get("shots") or {}
    kind = (st.get("product") or {}).get("name") or st["read"].get("product_words")
    revs = [_rv(f"shot_{stem}_{k}", SHOT_READ_FOREIGN.format(kind=kind), [_img(rel)], need=("shots",))
            for stem, sheets in (sh.get("sheets") or {}).items() for k, rel in enumerate(sheets)]
    if not revs:
        return {"goto": "f_clean"}
    return {"review": revs, "then": "f_shots_got"}


def f_shots_got(st, m, rp, u):
    _apply_shot_reads(st, rp)
    return {"goto": "f_clean"}


def f_clean(st, m, rp, u):
    """박힌 글자 — 여기서는 **준비만**(돈 0: 판 칸·키 확인, 키 없으면 일찍 멈춤). 실제 VMake 는 장면 맞추기(컷 확정) 뒤·렌더 전 f_render 가
    자막 있는 컷 구간만(사장님 10-26 — 주인 vmake_clean.used_spans·clean_used). 원본 통째로 보내지 않는다."""
    dims = _origin_dims(st)
    need = sorted(n for n in dims if any(s.get("text") for s in (st.get("shots") or {}).get(n.rsplit(".", 1)[0]) or []))
    if not need:
        st["text_fix"] = {"mode": "none", "need": [], "cleaned": [], "done": {}, "calls": 0, "sec": 0.0, "why": "박힌 글자 샷 없음"}
        return {"goto": "f_draft"}
    st["text_fix"] = {"need": need}
    return {"do": [{"id": "clean", "cmd": "clean_text", "check": True, "version": st["version"]}], "then": "f_clean_got"}


def f_clean_got(st, m, rp, u):
    c = m.get("clean") or {}
    if c.get("mode") == "need_key":
        raise _Stop(str(c.get("why")), str(c.get("fix") or ""), retry="f_clean")
    st["text_fix"] = {"mode": c.get("mode") or ("error" if c.get("error") else "blur"), "need": (st.get("text_fix") or {}).get("need") or [],
                      "cleaned": [], "done": {}, "calls": 0, "sec": 0.0, "why": str(c.get("why") or c.get("error") or "")[:200]}
    st["log"].append(f"박힌 글자: {st['text_fix']['mode']} 준비 · 글자 원본 {st['text_fix']['need']} — VMake 는 장면 맞추기 뒤 자막 있는 컷 구간만")
    return {"goto": "f_draft"}


def _cuts_key(st) -> str:
    import hashlib
    return hashlib.md5(json.dumps(((st.get("script") or {}).get("M") or {}).get("cuts") or {}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def f_plan(st, m, rp, u):
    st["_plan_key"] = _cuts_key(st)          # 계획 시간표가 어느 재료로 만들어졌나 — 렌더 고치기 뒤 VMake 구간을 새 시간표로 다시 재기 위해
    return ph_plan(st, m, rp, u)


def f_render(st, m, rp, u):
    """렌더 전 박힌 글자 지우기(사장님 10-26 '장면 편집 후 자막 있는 컷만') — 재료(컷)가 지난 지우기 뒤 바뀌었을 때만 clean_text.
    구간 계산·자르기·덮기 = vmake_clean(주인), 여기는 순서만. 지운 구간 = 재료.blur 에서 뺀다(rules.blur_minus_spans)."""
    tf = st.get("text_fix") or {}
    if tf.get("mode") != "vmake" or tf.get("key") == _cuts_key(st):
        return ph_render(st, m, rp, u)
    return {"do": [{"id": "clean", "cmd": "clean_text", "version": st["version"], "shots": st.get("shots") or {}, "done": tf.get("done") or {},
                    "replan": st.get("_plan_key") != _cuts_key(st)}], "then": "f_render_clean_got"}


def f_render_clean_got(st, m, rp, u):
    c = m.get("clean") or {}
    tf = st["text_fix"]
    if c.get("mode") == "need_key":
        raise _Stop(str(c.get("why")), str(c.get("fix") or ""), retry="render")
    if c.get("error"):
        st["log"].append("박힌 글자 지우기 실패(흐림 그대로 렌더): " + str(c["error"])[:200])
    for n, iv in (c.get("done") or {}).items():
        tf.setdefault("done", {}).setdefault(n, []).extend(iv)
        if n not in tf.setdefault("cleaned", []):
            tf["cleaned"].append(n)
    tf["calls"] = int(tf.get("calls") or 0) + int(c.get("calls") or 0)
    tf["sec"] = round(float(tf.get("sec") or 0) + float(c.get("send_sec") or 0), 3)
    tf["key"] = _cuts_key(st)
    st["log"].append(f"박힌 글자 VMake: 쓰는 구간 {c.get('used_sec')}초 중 자막 컷 {c.get('send_sec')}초 · 호출 {c.get('calls')}회 · 보낸 초 {c.get('sent')}"
                     + (f" · ⚠ {c['sent_bad']}" if c.get("sent_bad") else "") + (f" · {c.get('why')}" if c.get("why") else ""))
    if c.get("sent_bad"):
        raise _Stop("자막 지우기에 쓰지 않는 구간까지 보낸 게 보여 멈췄어요", "숏템 피드백으로 알려 주시면 확인해 드릴게요", final=True)
    M = st["script"]["M"]
    nb = RU.blur_minus_spans(M, tf.get("done") or {})
    if nb:
        st["log"].append(f"지운 구간의 흐림 {nb}칸 뺌(재료.blur)")
    v = st["version"]
    return {"do": [{"id": "save_m", "cmd": "write_doc", "files": {f"{v}/재료.json": M}, "cand_dir": True, "version": v}], "then": "render"}


def f_draft(st, m, rp, u):
    return {"do": [{"id": "draft", "cmd": "materials_draft", "version": st["version"], "files": [f["name"] for f in st["origin"]["files"]],
                    "shots": st.get("shots") or {}, "cleaned": (st.get("text_fix") or {}).get("need") or [] if (st.get("text_fix") or {}).get("mode") == "vmake" else []}], "then": "f_draft_got"}


def f_draft_got(st, m, rp, u):
    d = m.get("draft") or {}
    st["mat_draft"] = d.get("draft") or {}
    if d.get("error"):
        st["log"].append("재료 초안 실패(대본은 초안 없이): " + str(d["error"])[:200])
    return {"goto": "f_asr"}


def f_asr(st, m, rp, u):
    return {"do": [{"id": "asr", "cmd": "asr_spans", "spans": st["research"].get("spans") or []}], "then": "f_asr_got"}


def f_asr_got(st, m, rp, u):
    st["asr"] = m.get("asr") or {}
    return {"goto": "script"}


# ── 쇼핑형 처리기(원본 찾기·원음 없음 — 소재 → 쿠팡 → 근거 글 → 재료 영상 → 대본) ──────────────
def s_bench_got(st, m, rp, u):
    b = m.get("bench") or {}
    if b.get("error"):
        raise _Stop("영상을 받지 못했어요", "영상 주소가 맞는지, 유튜브 로그인 연결이 되어 있는지 확인해 주세요", auto=True)
    st["bench"] = {k: b.get(k) for k in ("id", "title", "channel", "date", "dur", "desc", "sheet", "big")}
    st["bench_lines"] = b.get("lines") or []
    return {"review": [_rv("topic_read", TOPIC_READ_SHOP + "\n\n제목: " + str(b.get("title")) + "\n채널: " + str(b.get("channel")) + "\n설명: " + str(b.get("desc") or "")[:1500] +
                           "\n받아쓰기: " + " / ".join(str(l.get("text")) for l in st["bench_lines"])[:3000], [_img(b["sheet"])] if b.get("sheet") else [],
                           need=("is_shopping", "product_words", "coupang_queries"))], "then": "topic_got"}


def s_topic_got(st, m, rp, u):
    r = _reply(rp, "topic_read", ("is_shopping", "product_words", "coupang_queries"))
    if not r.get("is_shopping"):
        raise _Stop("쿠팡 제품 이야기가 아닌 영상이에요", "제품 썰 영상 주소를 주세요", final=True)
    st["read"] = {**r, "celeb": ""}
    st["coupang_qs"] = [q for q in r.get("coupang_queries") or [] if q][:4]
    if st.get("given"):
        q, _ = _given_query(st["given"])
        st["coupang_qs"] = [q] + st["coupang_qs"][:2]
    return {"do": [{"id": "coupang", "cmd": "coupang", "queries": st["coupang_qs"], "ratings": True}], "then": "s_cands"}


def s_cands(st, m, rp, u):
    _coupang_down(m)
    cands = (m.get("coupang") or {}).get("items") or []
    if not cands:
        raise _Stop(*NO_SIMILAR)
    st["coupang_cands"] = cands[:16]
    st["product_shots"] = [st["bench"]["sheet"]] if st["bench"].get("sheet") else []
    st["_cand_kind"] = "shop"
    items = [{"product_id": str(c.get("product_id") or ""), "image": c.get("image") or ""} for c in cands[:12]]
    return {"do": [{"id": "csheet", "cmd": "cand_sheet", "items": items}], "then": "s_cand_look"}


def s_cand_look(st, m, rp, u):
    sh = (m.get("csheet") or {}).get("file")
    pics = [_img(x) for x in st.get("product_shots") or []] + ([_img(sh)] if sh else [])
    return {"review": [_rv("shop_same", PRODUCT_SAME_SHOP + "\n\n쿠팡 후보:\n" + json.dumps((st.get("coupang_cands") or [])[:12], ensure_ascii=False, indent=1),
                           pics, need=("product_id", "name", "category"))], "then": "s_product_done"}


def s_product_done(st, m, rp, u):
    a = _reply(rp, "shop_same", ("product_id", "name", "category"))
    if not a.get("product_id"):
        raise _Stop(*NO_SIMILAR)
    if a.get("category") in ("의약품", "의료기기"):
        raise _Stop("의약품·의료기기는 만들 수 없는 소재예요", "다른 소재 영상을 주세요", final=True)
    st["product"] = {**{k: a.get(k) for k in ("product_id", "name", "why", "category")}, "mode": "exact" if a.get("mode") != "alt" else "alt"}
    return {"goto": "reviews"}


def s_research(st, m, rp, u, fail: str = ""):
    PR = st["product"]
    ask = (RESEARCH_SHOP + "\n\n## 소재 영상\n제목: " + str(st["bench"].get("title")) + "\n받아쓰기: " + " / ".join(str(l.get("text")) for l in st.get("bench_lines") or [])[:3000] +
           "\n\n## 제품\n" + json.dumps(PR, ensure_ascii=False) + "\n\n## 쿠팡 베스트 후기·네이버 글\n" + json.dumps(st.get("reviews") or [], ensure_ascii=False)[:5000] +
           (f"\n\n## 지난 답에서 걸린 것(고쳐라)\n{fail}" if fail else ""))
    return {"review": [_rv("research", ask, [], need=("조사_md", "keywords", "queries"))], "then": "s_research_check",
            "reject": {"why": fail, "fix": "조사를 고쳐 다시"} if fail else None}


def s_research_check(st, m, rp, u):
    r = _reply(rp, "research", ("조사_md", "keywords", "queries"))
    if r.get("stop"):
        st["log"].append("조사 멈춤: " + str(r["stop"])[:400])
        raise _Stop("조사해 보니 이 제품은 만들 수 없는 소재예요(의약품·금지 품목 등)", "다른 소재 영상을 주세요", final=True)
    md = str(r.get("조사_md") or "")
    bad = [f"조사.md 에 '{h}' 절이 없다" for h in ("결론", "출처", "사실", "금지", "확인 못") if h not in md]
    bad += [f"사실 {f.get('id')} 에 출처가 없다" for f in r.get("facts") or [] if isinstance(f, dict) and not str(f.get("src") or "").strip()]
    if bad:
        _tries(st, "research", 3)
        return s_research(st, {}, {}, u, fail="; ".join(bad))
    st["research"] = {k: r.get(k) for k in ("keywords", "queries", "exclude", "spans", "facts")}
    st["research"]["spans"] = []
    st["research_md"] = md
    return {"do": [{"id": "save_research", "cmd": "write_doc", "files": {"조사/조사.md": md}}], "then": "material"}


def s_material_dl(st, m, rp, u):
    st["material"] = {"files": ((m.get("dl") or {}).get("files") or []) + ((m.get("stills") or {}).get("files") or [])}
    if not st["material"]["files"]:
        raise _Stop("영상 조각과 제품 사진을 하나도 받지 못했어요", "다시 시도해 주시면 이어 갈게요", auto=True)
    return {"goto": "script"}


FORMAT_PHASES = {   # 형식별 세부 단계 처리기 — 없는 세부 단계는 공용 PHASES
    "해외원본형": {"bench_got": f_bench_got, "ref_read": f_ref_read, "of_peers": f_of_peers, "of_got": f_of_got, "of_pick": f_of_pick, "of_fetch": f_of_fetch,
                "of_fetched": f_of_fetched, "f_product_sheet": f_product_sheet, "f_product_pick": f_product_pick, "f_product_cands": f_product_cands,
                "f_product_same": f_product_same, "research": f_research, "f_research_got": f_research_got, "f_research_check": f_research_check,
                "f_material": f_material, "material": f_material, "f_material_got": f_material_got, "f_shots_got": f_shots_got, "f_clean": f_clean,
                "f_clean_got": f_clean_got, "f_draft": f_draft, "f_draft_got": f_draft_got, "f_asr": f_asr, "f_asr_got": f_asr_got,
                "plan": f_plan, "render": f_render, "f_render_clean_got": f_render_clean_got},
    "쇼핑형": {"bench_got": s_bench_got, "topic_got": s_topic_got, "s_cands": s_cands, "s_cand_look": s_cand_look, "s_product_done": s_product_done,
             "research": s_research, "s_research_check": s_research_check, "material_dl": s_material_dl},
    "레시피형": {},      # 연예인형 처리기 그대로(재료 스티커 = 판)
}
PHASE_STAGE.update({
    "ref_read": "bench", "topic_got": "bench", "of_peers": "origin", "of_got": "origin", "of_pick": "origin", "of_fetch": "origin", "of_fetched": "origin",
    "f_product_sheet": "product", "f_product_pick": "product", "f_product_cands": "product", "f_product_same": "product", "s_cands": "product", "s_cand_look": "product",
    "s_product_done": "product", "f_research_got": "research", "f_research_check": "research", "s_research_check": "research", "f_material": "material",
    "f_material_got": "material", "f_shots_got": "material", "f_clean": "material", "f_clean_got": "material", "f_draft": "material", "f_draft_got": "material",
    "f_asr": "asr", "f_asr_got": "asr", "customize": "sign", "check_judge": "check", "f_render_clean_got": "render",
})


PHASES = {
    "setup": ph_setup, "setup_check": ph_setup_check, "bench": ph_bench, "bench_got": ph_bench_got, "origin_read": ph_origin_read, "src_got": ph_src_got, "probe_got": ph_probe_got, "sb_pick": ph_sb_pick,
    "peer": ph_peer, "peer_read": ph_peer_read, "search": ph_search, "search_got": ph_search_got, "titles": ph_titles,
    "titles_got": ph_titles_got, "subs": ph_subs, "subs_got": ph_subs_got, "pick_got": ph_pick_got, "origin_fetch": ph_origin_fetch, "origin_got": ph_origin_got, "stopped": ph_stopped, "given_origin_got": ph_given_origin_got,
    "vis_get": ph_vis_get, "vis_got": ph_vis_got, "vis_look": ph_vis_look, "vis_pick": ph_vis_pick, "vis_next": ph_vis_next,
    "product_sheet": ph_product_sheet, "product_pick": ph_product_pick, "product_pick_wide": ph_product_pick_wide, "product_cands": ph_product_cands, "product_same": ph_product_same,
    "product_done": ph_product_done, "cand_look": ph_cand_look, "reviews": ph_reviews, "reviews_got": ph_reviews_got, "reviews_naver": ph_reviews_naver, "name_find": ph_name_find, "name_got": ph_name_got, "named_cands": ph_named_cands,
    "named_same": ph_named_same, "best": ph_best, "best_rated": ph_best_rated, "given": ph_given, "given_same": ph_given_same, "research": ph_research, "research_got": ph_research_got,
    "research_check": ph_research_check, "material": ph_material, "material_got": ph_material_got, "material_pick": ph_material_pick,
    "material_dl": ph_material_dl, "asr": ph_asr, "asr_got": ph_asr_got, "shots_got": ph_shots_got, "script": ph_script,
    "script_ask": ph_script_ask, "script_got": ph_script_got, "script_heard": ph_script_heard, "sign": ph_sign, "plan": ph_plan, "plan_got": ph_plan_got,
    "plan_look": ph_plan_look, "thumb": ph_thumb, "thumb_got": ph_thumb_got, "render": ph_render, "render_got": ph_render_got, "render_fix": ph_render_fix, "check": ph_check,
    "check_got": ph_check_got, "check_look": ph_check_look, "check_judge": ph_check_judge, "check_fix": ph_check_fix, "customize": ph_customize, "check_retry": ph_check_retry, "deliver": ph_deliver, "finished": ph_finished,
}
for _k, _v in {"check_retry": "check", "origin_fetch": "origin", "src_got": "origin", "probe_got": "origin", "sb_pick": "origin", "vis_get": "origin", "vis_got": "origin", "vis_look": "origin", "vis_pick": "origin", "vis_next": "origin", "given_origin_got": "origin", "stopped": "setup", "research_check": "research", "script_ask": "script", "script_heard": "script", "best": "product", "best_rated": "product", "given": "product", "given_same": "product", "cand_look": "product", "reviews": "product", "reviews_got": "product", "reviews_naver": "product", "product_pick_wide": "product", "deliver": "done", "finished": "done"}.items():
    PHASE_STAGE.setdefault(_k, _v)
