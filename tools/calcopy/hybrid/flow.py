# -*- coding: utf-8 -*-
"""회원 라인 **서버 지시서**(볼케이노형, 관제 234·097 — 사장님 10-21 "볼케이노처럼 / 칼카피 노하우를 녹여서 지금처럼 영상이 나오게").

노하우(단계 순서·판정 질문·반려 규칙·함정)는 이 파일 한 곳. 회원 PC 는 손(runner_ops 가 do 를 실행)과 눈(회원 Claude 가 review 에 답)만.
서버(shopping_shorts/claude_flow.py)가 이 모듈을 불러 매 호출마다:

    resp = step(state, measure, replies, user)      # state = 지난 응답의 상태(서버 서명 payload 안), measure = do 결과, replies = review 답
    resp = {"status": execute|review|wait_user|reject|stop|done, "message": "OO 완료 → 다음 OO", "stage": {no,total,text},
            "do": [{id, cmd, …}], "review": [{id, model, ask, show[…], need[…]}], "traps": [...], "reject": {why, fix},
            "wait": {kind, script}, "video": "<PC 파일>", "state": {...}}

판단 주인(새로 적지 않고 부른다): 판 = styles · 대본 검사 = script_audit · 출처 규칙·자막↔목소리·제목 색·샷 끝 = rules ·
자동 검사 6항목 = bench_check(PC 가 재고 여기서 판정). 단계는 channel/칼카피_제작순서 00~13 과 같은 순서(바꾸면 문서와 같은 커밋).
"""
from __future__ import annotations

import json
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

PHASE_STAGE = {   # 세부 단계 → 회원에게 보이는 단계
    "setup": "setup", "setup_check": "setup", "bench": "bench", "bench_got": "bench", "origin_read": "origin", "peer": "origin", "peer_read": "origin",
    "search": "origin", "search_got": "origin", "titles": "origin", "titles_got": "origin", "subs": "origin", "subs_got": "origin",
    "pick_got": "origin", "origin_got": "origin", "product_sheet": "product", "product_pick": "product", "product_cands": "product",
    "product_same": "product", "name_find": "product", "name_got": "product", "named_cands": "product", "named_same": "product",
    "best_same": "product", "product_done": "product", "research": "research", "research_got": "research", "material": "material",
    "material_got": "material", "material_pick": "material", "material_dl": "material", "asr": "asr", "asr_got": "asr", "shots_got": "asr",
    "script": "script", "script_got": "script", "script_saved": "script", "sign": "sign", "plan": "plan", "plan_got": "plan",
    "plan_look": "plan", "plan_saved": "plan", "render": "render", "render_got": "render", "render_fix": "render", "render_saved": "render",
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
    "plan": ["'face' 크롭은 높이 전체라 원본 아래 박힌 자막이 들어온다 → 숫자 crop 으로 자막 밖(#13·#14)", "컷이 원본 샷보다 길면 렌더가 멈춘다"],
    "check": ["1초 시트 사이로 0.5초 장면 전환이 지나갈 수 있다(#1)", "0초 = 연예인 얼굴 크게"],
}

# ── 판정 질문(회원 Claude) — customer.py(10-21) 지시문을 옮겨 왔다 ─────────────────
ORIGIN_READ = """너는 쇼츠 원본 추적 담당이다. 아래는 남의 채널이 만든 연예인 쇼핑 쇼츠(벤치)의 1초 간격 장면 시트와 제목·설명·받아쓰기다.
이 쇼츠가 따온 **연예인 본인 원본 영상**(본인 유튜브·방송)을 찾기 위한 단서를 읽어라.
- 화면 위·아래의 '출처: ○○' 글자 = 원본 채널. 방송 로고·프로그램 이름도 본다. 이름표·자막으로 말하는 사람을 확인(얼굴로 짐작한 이름은 '불명').
- 설명란 '영상 속 제품'은 그 채널의 파트너스 상품일 뿐 근거가 아니다.
- 연예인이 쓰는 물건(쇼핑 소재)이 아니면 is_shopping=false. 의약품·의료기기면 is_shopping=false.
JSON 하나: {"celeb": "이름 또는 불명", "source_label": "화면 출처 글자 그대로 또는 ''", "channel_hint": "원본 채널 이름·핸들 추정 또는 ''",
 "product_words": ["제품을 가리키는 낱말"], "queries": ["유튜브 검색어 3~5개 — '<연예인> <제품 낱말>' 꼴"], "is_shopping": true}"""

PEER_READ = """너는 출처 글자 읽기 담당이다. 같은 연예인·제품을 다룬 **다른 채널 쇼츠**들의 장면 모음이다(쇼츠마다 한 줄, 왼쪽에 번호).
화면 위·아래의 '출처: ○○' 글자, 방송 로고·프로그램 이름을 그대로 읽어라. 안 보이면 빈 값. 지어내지 마라.
JSON 하나: {"labels": [{"n": 번호, "source": "출처 글자 그대로 또는 ''", "program": "방송·채널 이름 또는 ''"}]}"""

ORIGIN_TITLES = """너는 원본 후보 고르기 담당이다. 연예인 본인 채널의 영상 목록(제목)에서, 벤치 쇼츠가 따온 원본일 만한 영상을 최대 8개 골라라 —
제목에 그 제품·쓰임(주방·청소·살림템·추천템 등)·계절이 맞는 것. 벤치보다 먼저 올라온 것.
JSON 하나: {"ids": ["유튜브 id", …]}"""

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

PRODUCT_BEST = """너는 대체 제품 고르기 담당이다(같은 제품이 없으면 쿠팡에서 후기 많고 제일 좋은 제품). 연예인이 쓴 것과 **같은 종류·같은 쓰임**인 쿠팡 후보 중
후기(rating 의 괄호 숫자) 많고 별점 높은 것 하나를 골라라. 광고(is_ad)·묶음 이상한 것은 뒤로. 같은 종류가 없으면 product_id ''.
JSON 하나: {"product_id": "…", "name": "…", "why": "고른 이유 한 줄(후기 수·별점)", "category": "화장품|생활용품|식품|의류|의약품|의료기기|기타"}"""

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
각 후보의 360p 토막 시트(키워드 구간)와 메타가 있다. 쓸 게 없으면 chosen 빈 목록.
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
- ★권위 1줄 필수(브랜드 유래·연도·나라·판매 기록 — 조사.md 사실 번호, 전언 '~하더라고요/~대요') · 비유 1줄('~같아요') · 끝 줄 = 사회 반응(그 제품의 품절·기사·입소문 — '난리·필수템·말 다 했죠·품절' 중 하나).
- CTA 없음 · 금액 없음 · 질병·효능 단정 없음 · 다른 회사 숫자 없음. 창작 허용 = 화자의 계기·감상·비유 / 근거 필수 = 제품 속성·원리·수치·인기(줄마다 facts).
## 읽는 글(tts)
- 렌더러가 읽는 칸은 tts 하나. 줄 끝 문장부호 필수. 숫자·영문·기호는 읽는 대로('100%'→'백 퍼센트', '2024년'→'이천이십사 년'), 자막(caps)은 원문.
- ★자막(caps 를 이은 글)은 읽는 말과 같게 — 다르게 해도 되는 건 숫자·영문 읽기와 발음 고침뿐.
- 미나 목소리가 자주 틀리게 들리는 말 → 대신 쓸 말(자막도 같이 바꾼다): '따라 사 봤는데요'→'하나 사서 따라 해 봤어요' · '대체'→'도대체' · '꾸덕'→'묵직해서' ·
  '울퉁불퉁'→'제각각이라' · 이름 뒤 '이'(김영옥이)→'선생님이/씨가' · 첫 낱말이 브랜드면 앞에 한 낱말('요즘 설화수…').
- 조사·어미를 빼지 않는다(명사 3개 이상 조사 없이 연속 금지). 판 길이를 넘치면 글을 줄인다(배속 아님).
## 재료(컷)
- 컷마다 see(무엇이 보이나) — 그 줄 대사의 동작·상태가 그 컷에 보여야 한다. 같은 소스 ±3초 재사용 금지 · A-B-A 끼움 금지 · 컷 ≥1.2초 · 끝 컷 ≥1.5초.
- ★연예인 장면(face 가 사람)은 원본 파일에서만. 제품 컷도 원본 안 제품 장면이 먼저. 남의 얼굴·손·워터마크·박힌 자막·다른 브랜드는 crop 밖.
- 0초 첫 컷 = 연예인 얼굴 크게(제품 컷으로 시작 금지). 주인공 컷은 원본 샷 표의 who main·both 샷 안에서, 컷 길이가 그 샷 끝을 넘지 않게.
## 근거.md
'| 줄 | 말 | 근거 |' — 줄마다 한 줄(원본 초 · 사실 번호 · URL). 근거 줄 수 = 대본 줄 수. 쿠팡 상품번호도 적는다.
JSON 하나: {"대본": {…}, "재료": {"cuts": {…}}, "근거_md": "…"}"""

PLAN_LOOK = """너는 장면 검수 담당이다. 계획 시트를 보고 컷마다: 대사와 화면이 맞나 · 남의 신체 근접 · 남의 글자·원본 자막 띠 · 0초·훅 = 연예인 얼굴 · A-B-A 끼움.
★주인공은 칸 가운데. 원본 샷 표의 '글자'(박힌 글자 상자 — 0~1 **비율**)를 보고 칸이 그 글자를 피하게 숫자 crop 을 정한다. ★crop 은 **원본 픽셀 정수**[x, y, w, h](비율 × 원본 가로·세로) — 숫자 crop 은 엔진이 바꾸지 않는다(정한 그대로 렌더).
★연예인이 나오는 영상은 찾은 원본에서만 — 다른 채널 연예인 영상 절대 금지. 사람 얼굴 컷(face)은 원본 파일만, 제품 컷도 원본 안 제품 장면이 먼저. 시트 칸 = 렌더러가 실제로 자를 화면 그대로다.
★crop 'face' 는 원본 **높이 전체**를 쓴다 — 원본에 편집 자막·제목 띠가 박혀 있으면 'face' 대신 숫자 crop [x, y, w, h](원본 픽셀, 창 비율 {ar})로
자막·띠 밖을 잘라라(예: 1920×1080 원본, 자막 y≈930 → [455, 0, 870, 870]). 고칠 것이 있으면 재료 전체를 고쳐서 돌려준다(없으면 null).
★우리 틀(결함 아님): 맨 위 제목 2줄 · 화면 왼쪽 위 '얜샷템' 로고 · 화면 아래 '출처: …' 줄 · 우리 자막(가운데 아래, 색 강조) — 이것들은 남의 글자·워터마크가 아니다.
JSON 하나: {"ok": true, "problems": ["…"], "재료": null}"""

FINAL_LOOK = """너는 완성본 검수 담당이다. 1초 시트를 보고: 틀·제목·자막 자리·출처 줄, 줄마다 화면이 대사와 맞나, 남의 얼굴·손·글자(원본 편집 자막·워터마크) 없나,
0초 = 연예인 얼굴 크게. 남의 채널 연예인 장면·장면 전환 효과(별·와이프)가 섞였나. 받아쓰기와 대본 글자도 대조한다(받아쓰기 한 모델만 틀린 건 결함이 아닐 수 있다).
★우리 틀(결함 아님): 맨 위 제목 2줄 · 화면 왼쪽 위 '얜샷템' 로고 · 화면 아래 '출처: …' 줄 · 우리 자막(가운데 아래, 색 강조) — 이것들은 남의 글자·워터마크가 아니다.
JSON 하나: {"ok": true, "problems": ["…"]}"""


# ── 응답 꼴 ────────────────────────────────────────────────────────────────
def _stage(phase: str) -> dict:
    k = PHASE_STAGE.get(phase, "setup")
    return {"no": STAGE_NO[k], "total": len(STAGES), "text": STAGE_TEXT[k], "key": k}


def _msg(st: dict, phase: str) -> str:
    k = PHASE_STAGE.get(phase, "setup")
    prev = st.get("_shown_stage")
    st["_shown_stage"] = k
    now = STAGE_TEXT[k] + (" 중" if k not in ("done", "sign") else "")
    if prev and prev != k:
        return f"{STAGE_TEXT[prev]} 완료 → {now}"
    return now


def _rv(rid: str, ask: str, show: list | None = None, model: str = "opus", need: tuple = ()) -> dict:
    return {"id": rid, "model": model, "ask": ask, "show": show or [], "need": list(need)}


def _img(rel: str) -> dict:
    return {"file": rel}


def _txt(s: str) -> dict:
    return {"text": s}


class _Stop(Exception):
    """멈춤. retry = 다시 시도하면 이어 갈 세부 단계(받기 실패처럼 잠깐의 문제 — 앞 단계 유튜브 요청을 다시 쓰지 않게)."""
    def __init__(self, why: str, fix: str = "", retry: str | None = None):
        super().__init__(why)
        self.why, self.fix, self.retry = why, fix, retry


def start(ref: str, version: str, sid: str) -> dict:
    return {"sid": sid, "ref": ref, "version": version, "phase": "setup", "tries": {}, "log": []}


def step(state: dict, measure: dict | None = None, replies: dict | None = None, user: dict | None = None) -> dict:
    """한 번 호출 = 지난 do·review 결과를 먹고 다음 할 일을 낸다. 같은 호출 안에서 바로 이어 갈 수 있는 단계(goto)는 계속 넘어간다."""
    st = state
    m, rp, user = dict(measure or {}), dict(replies or {}), dict(user or {})
    for _ in range(40):
        ph = st.get("phase") or "setup"
        h = PHASES.get(ph)
        if h is None:
            return _out(st, "stop", ph, why="알 수 없는 단계입니다", fix="")
        try:
            r = h(st, m, rp, user)
        except _Stop as e:
            st["phase"] = "stopped"
            st["stopped"] = {"why": e.why, "fix": e.fix, **({"retry": e.retry} if e.retry else {})}
            return _out(st, "stop", ph, why=e.why, fix=e.fix, retry_ok=True if e.retry else None)
        m, rp, user = {}, {}, {}           # 한 번 먹은 입력은 다음 단계로 넘기지 않는다
        if "goto" in r:
            st["phase"] = r["goto"]
            continue
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
    return _out(st, "stop", st.get("phase"), why="단계가 돌기만 합니다", fix="")


def _out(st: dict, status: str, phase: str, **kw) -> dict:
    stage = _stage(phase)
    res = {"status": status, "stage": stage, "message": _msg(st, phase), "traps": TRAPS.get(stage["key"], []), "state": st}
    for k, v in kw.items():
        if v is not None:
            res[k] = v
    if status == "stop":
        res["message"] = f"멈춤: {kw.get('why')}"
    return res


def _tries(st: dict, key: str, limit: int) -> int:
    n = st["tries"].get(key, 0) + 1
    st["tries"][key] = n
    if n > limit:
        raise _Stop(f"{key} 단계를 {limit}번 고쳐도 통과하지 못했습니다", "같은 영상으로 다시 만들거나 다른 영상을 주세요")
    return n


def _reply(rp: dict, rid: str, need: tuple = ()) -> dict:
    a = rp.get(rid)
    if not isinstance(a, dict):
        raise _Stop(f"판정 답이 없습니다({rid})", "다시 이어서 부르세요")
    miss = [k for k in need if k not in a]
    if miss:
        raise _Stop(f"판정 답에 칸이 없습니다({rid}: {miss})", "다시 이어서 부르세요")
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
        raise _Stop("회원 PC 준비 확인이 실패했습니다", str(env["error"])[:200])
    voice = (_style(st["version"]).get("voice") or {}).get("voice_id", "")
    need = "elevenlabs" if voice.startswith("kr-mina") else "typecast"
    if not (env.get("keys") or {}).get(need) and not env.get("dev"):
        raise _Stop("목소리 키가 없습니다", f"설정 화면 '소리' 칸에 {'일레븐랩스' if need == 'elevenlabs' else '타입캐스트'} 키를 넣어 주세요")
    if float(env.get("disk_gb") or 99) < 1.5:
        raise _Stop("PC 저장 공간이 모자랍니다(1편에 1.5GB)", "C 드라이브 공간을 비워 주세요")
    st["env"] = {k: env.get(k) for k in ("keys", "dev", "cache", "asr")}
    return {"goto": "bench"}


# ── 1 소재(벤치) ──────────────────────────────────────────────────────────
def ph_bench(st, m, rp, u):
    return {"do": [{"id": "bench", "cmd": "bench", "url": st["ref"]}], "then": "bench_got"}


def ph_bench_got(st, m, rp, u):
    b = m.get("bench") or {}
    if b.get("error"):
        raise _Stop("영상을 받지 못했습니다", "영상 주소가 맞는지, 또는 유튜브 로그인 연결을 확인해 주세요")
    st["bench"] = {k: b.get(k) for k in ("id", "title", "channel", "date", "dur", "desc", "sheet")}
    st["bench_lines"] = b.get("lines") or []
    return {"review": [_rv("origin_read", ORIGIN_READ + "\n\n제목: " + str(b.get("title")) + "\n채널: " + str(b.get("channel")) +
                           "\n설명: " + str(b.get("desc") or "")[:1500] + "\n받아쓰기: " + " / ".join(str(l.get("text")) for l in st["bench_lines"])[:3000],
                           [_img(b["sheet"])] if b.get("sheet") else [], need=("celeb", "queries", "is_shopping"))], "then": "origin_read"}


# ── 2 원본 찾기 ───────────────────────────────────────────────────────────
def ph_origin_read(st, m, rp, u):
    r = _reply(rp, "origin_read", ("celeb", "queries", "is_shopping"))
    if not r.get("is_shopping"):
        raise _Stop("연예인이 쓰는 물건이 나오는 영상이 아닙니다", "연예인 쇼핑 쇼츠 주소를 주세요")
    st["read"] = r
    celeb = str(r.get("celeb") or "")
    if not celeb or celeb == "불명":
        return {"goto": "search"}
    if re.sub(r"^\s*출처\s*[:：]?\s*", "", r.get("source_label") or "").strip():
        return {"goto": "search"}            # 화면 출처 글자를 이미 읽었다 — 남의 쇼츠 출처 읽기(유튜브 약 11건)는 출처가 안 보일 때만(계정 한도 아끼기)
    words = [w for w in r.get("product_words") or [] if w][:2] or [""]
    return {"do": [{"id": "peer", "cmd": "peer_sheet", "queries": [f"{celeb} {w}".strip() for w in words], "bench_id": (st.get("bench") or {}).get("id")}],
            "then": "peer"}


def ph_peer(st, m, rp, u):
    p = m.get("peer") or {}
    if not p.get("sheet"):
        return {"goto": "search"}
    return {"review": [_rv("peer_read", PEER_READ + f"\n\n연예인: {st['read'].get('celeb')}", [_img(p["sheet"])], model="sonnet", need=("labels",))],
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
                        "\n".join(f"{t['id']}\t{str(t.get('title') or '')[:80]}" for t in part), model="sonnet", need=("ids",)))
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
        raise _Stop("원본 영상 후보를 찾지 못했습니다", "연예인 본인 원본 영상(유튜브) 주소를 알려 주세요")
    return {"do": [{"id": "subs", "cmd": "origin_subs", "ids": [c["id"] for c in st["mixed"]]}], "then": "subs_got"}


def ph_subs_got(st, m, rp, u):
    sub = m.get("subs") or {}
    got = sub.get("matched") or {}        # 지문 대조 = PC 가 rules.fingerprint 로(자막 낱말은 PC 에 남긴다)
    if sub.get("blocked") and not got:
        raise _Stop("유튜브가 지금 이 PC 요청을 막았습니다(봇 확인)", "유튜브 로그인 연결을 확인하거나 잠시 뒤 다시 이어서 부르세요")
    scored = []
    for c in st.get("mixed") or []:
        mt = got.get(c["id"])
        if mt:
            scored.append({**{k: c.get(k) for k in ("id", "title", "channel", "dur", "views")}, "matched": mt})
    scored.sort(key=lambda c: -len(c["matched"]))
    if not scored:
        raise _Stop("원본 영상을 찾지 못했습니다", "연예인 본인 원본 영상(유튜브) 주소를 알려 주세요")
    st["scored"] = scored[:5]
    B = st["bench"]
    return {"review": [_rv("origin_pick", ORIGIN_PICK + f"\n\n벤치: {B.get('title')} ({B.get('channel')}, {B.get('date')})\n후보:\n" +
                           json.dumps(st["scored"], ensure_ascii=False, indent=1), [_img(B["sheet"])] if B.get("sheet") else [],
                           need=("origin_id", "self_spoken"))], "then": "pick_got"}


def ph_pick_got(st, m, rp, u):
    p = _reply(rp, "origin_pick", ("origin_id", "self_spoken"))
    oid = str(p.get("origin_id") or "")
    if not oid or not p.get("self_spoken") or oid not in {c["id"] for c in st.get("scored") or []}:
        raise _Stop("연예인 본인이 말한 원본을 확정하지 못했습니다", "연예인 본인 원본 영상(유튜브) 주소를 알려 주세요")
    ts = [float(x["origin_t"]) for x in p.get("matched") or [] if isinstance(x.get("origin_t"), (int, float))]
    if not ts:
        ts = [float(x["origin_t"]) for x in next(c for c in st["scored"] if c["id"] == oid)["matched"]]
    a, b = max(0.0, min(ts) - 90), max(ts) + 90
    st["origin"] = {"id": oid, "url": f"https://www.youtube.com/watch?v={oid}", "matched": p.get("matched") or [], "window": [a, b],
                    "info": next((c for c in st["scored"] if c["id"] == oid), {})}
    return {"do": [{"id": "origin", "cmd": "origin_get", "vid": oid, "a": a, "b": b, "ts": ts}], "then": "origin_got"}


def ph_origin_fetch(st, m, rp, u):
    """원본 받기만 다시(다시 시도) — 원본 판정까지 한 일은 그대로 둔다."""
    O = st["origin"]
    ts = [float(x["origin_t"]) for x in O.get("matched") or [] if isinstance(x.get("origin_t"), (int, float))]
    return {"do": [{"id": "origin", "cmd": "origin_get", "vid": O["id"], "a": O["window"][0], "b": O["window"][1], "ts": ts}], "then": "origin_got"}


def ph_stopped(st, m, rp, u):
    """멈춘 편 — 다시 시도(retry)할 수 있는 멈춤이면 그 단계부터, 아니면 그대로 멈춤."""
    r = (st.get("stopped") or {}).get("retry")
    if not r and str((st.get("stopped") or {}).get("why") or "").startswith("원본 영상을 받지 못했습니다"):
        r = "origin_fetch"                       # 10-21 이전 판이 멈춘 편(retry 칸 없음)도 받기부터 이어 가게
    if u.get("retry") and r:
        st.pop("stopped", None)
        return {"goto": r}
    raise _Stop((st.get("stopped") or {}).get("why") or "멈춘 편입니다", (st.get("stopped") or {}).get("fix") or "", retry=r)


def ph_origin_got(st, m, rp, u):
    o = m.get("origin") or {}
    if o.get("error") or not o.get("files"):
        raise _Stop("원본 영상을 받지 못했습니다", "잠시 뒤 다시 시도(retry)하면 받기부터 이어 갑니다", retry="origin_fetch")
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
        raise _Stop("원본 장면을 볼 수 없습니다", "다시 이어서 부르세요")
    s0, R0 = st["look_s0"], st["read"]
    return {"review": [_rv("product_pick", PRODUCT_PICK + f"\n\n첫 그림 = 받은 원본 파일 {s0:.0f}초부터 1초 간격(왼쪽 위부터) — 답의 t 는 **파일 초**({s0:.0f} + 칸 번호).\n"
                           f"둘째 그림 = 벤치 쇼츠 1초 시트(그 제품이 무엇인지 보여 준다). 벤치·원본 대사의 제품 낱말: {R0.get('product_words')}",
                           [_img(sh)] + ([_img(st["bench"]["sheet"])] if st["bench"].get("sheet") else []), need=("scenes", "coupang_queries"))],
            "then": "product_cands"}


def ph_product_cands(st, m, rp, u):
    r = _reply(rp, "product_pick", ("scenes", "coupang_queries"))
    scenes = [s for s in r.get("scenes") or [] if isinstance(s, dict) and isinstance(s.get("t"), (int, float))][:4]
    if len(scenes) < 1:
        raise _Stop("제품이 보이는 장면을 찾지 못했습니다", "")
    st["product_pick"] = r
    qs = [q for q in r.get("coupang_queries") or [] if q][:4] + [w for w in r.get("brand_words") or [] if w][:2]
    st["coupang_qs"] = qs
    return {"do": [{"id": "shots", "cmd": "frames", "src": "src/" + _origin_file(st)["name"], "items": scenes, "prefix": "look/p"},
                   {"id": "coupang", "cmd": "coupang", "queries": qs}], "then": "product_same"}


def ph_product_same(st, m, rp, u):
    shots = (m.get("shots") or {}).get("files") or []
    if not shots:
        raise _Stop("제품 장면을 자르지 못했습니다", "")
    st["product_shots"] = shots
    cands = (m.get("coupang") or {}).get("items") or []
    st["coupang_cands"] = cands[:16]
    if not cands:
        return {"goto": "name_find"}
    return {"review": [_rv("product_same", PRODUCT_SAME + "\n\n쿠팡 후보:\n" + json.dumps(cands[:16], ensure_ascii=False, indent=1),
                           [_img(x) for x in shots], need=("product_id", "name", "category"))], "then": "product_done"}


def ph_product_done(st, m, rp, u):
    same = rp.get("product_same") or rp.get("named_same") or rp.get("best_same") or {}
    mode = "exact" if "product_same" in rp else ("named" if "named_same" in rp else "alt")
    if not same.get("product_id"):
        if mode == "exact":
            return {"goto": "name_find"}
        if mode == "named":
            return {"goto": "best"}
        raise _Stop("쿠팡에서 같은 종류 제품을 찾지 못했습니다", "")
    if same.get("category") in ("의약품", "의료기기"):
        raise _Stop("의약품·의료기기는 만들 수 없는 소재입니다", "다른 소재 영상을 주세요")
    pool = st.get("named_cands") if mode == "named" else st.get("coupang_cands")
    if pool and str(same["product_id"]) not in {str(c.get("product_id") or c.get("productId") or c.get("id") or "") for c in pool}:
        st["log"].append(f"제품 번호 {same['product_id']} 가 후보 표에 없음 — 답 그대로 씀")
    st["product"] = {**{k: same.get(k) for k in ("product_id", "name", "why", "category")}, "mode": mode,
                     "name_hints": (st.get("name_find") or {}).get("names") or [], "brand_words": (st.get("product_pick") or {}).get("brand_words")}
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
    c2 = (m.get("coupang2") or {}).get("items") or []
    if not c2:
        return {"goto": "best"}
    st["named_cands"] = c2[:16]
    return {"review": [_rv("named_same", PRODUCT_NAMED + "\n\n찾은 제품 이름·근거:\n" + json.dumps((st.get("name_find") or {}).get("names"), ensure_ascii=False, indent=1) +
                           "\n\n쿠팡 후보:\n" + json.dumps(c2[:16], ensure_ascii=False, indent=1), [_img(x) for x in st.get("product_shots") or []],
                           need=("product_id", "name", "category"))], "then": "product_done"}


def ph_best(st, m, rp, u):
    cands = st.get("coupang_cands") or st.get("named_cands") or []
    if not cands:
        raise _Stop("쿠팡에서 같은 종류 제품을 찾지 못했습니다", "")
    kind = (st.get("name_find") or {}).get("kind") or (st.get("product_pick") or {}).get("brand_words")
    return {"review": [_rv("best_same", PRODUCT_BEST + f"\n\n연예인이 쓴 것: {kind}\n\n쿠팡 후보:\n" + json.dumps(cands, ensure_ascii=False, indent=1),
                           [_img(x) for x in st.get("product_shots") or []], need=("product_id", "name", "category"))], "then": "product_done"}


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
           f"{json.dumps(PR, ensure_ascii=False)}" + (f"\n\n## 지난 답에서 걸린 것(고쳐라)\n{fail}" if fail else ""))
    return {"review": [_rv("research", ask, [_img(x) for x in st.get("product_shots") or []][:3], need=("조사_md", "keywords", "queries", "spans"))],
            "then": "research_check", "reject": {"why": fail, "fix": "조사를 고쳐 다시"} if fail else None}


def ph_research_check(st, m, rp, u):
    r = _reply(rp, "research", ("조사_md", "keywords", "queries", "spans"))
    if r.get("stop"):
        raise _Stop(str(r["stop"])[:200], "다른 소재 영상을 주세요")
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
                    "keywords": R.get("keywords") or [], "top": 8, "bench_id": st["bench"].get("id"), "origin_id": st["origin"]["id"]}],
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
    chosen = [c for c in r.get("chosen") or [] if isinstance(c, dict) and c.get("id") in known and c["id"] not in (st["bench"].get("id"), st["origin"]["id"])
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
                   {"id": "shots", "cmd": "shot_sheets", "files": ["src/" + x["name"] for x in st["origin"]["files"]]}], "then": "asr_got"}


def ph_asr_got(st, m, rp, u):
    st["asr"] = m.get("asr") or {}
    sh = m.get("shots") or {}
    st["shots"] = sh.get("shots") or {}          # {stem: [{i,a,b}]}
    R0 = st["read"]
    kind = (st.get("product") or {}).get("name") or R0.get("product_words")
    revs = []
    for stem, sheets in (sh.get("sheets") or {}).items():
        for k, rel in enumerate(sheets):
            revs.append(_rv(f"shot_{stem}_{k}", SHOT_READ.format(celeb=R0.get("celeb") or "주인공", kind=kind), [_img(rel)], model="sonnet", need=("shots",)))
    if not revs:
        return {"goto": "script"}
    return {"review": revs, "then": "shots_got"}


def ph_shots_got(st, m, rp, u):
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
    return {"goto": "script"}


# ── 7 대본·재료·근거 ──────────────────────────────────────────────────────
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
    files = ["src/" + x["name"] for x in (st.get("material") or {}).get("files") or []] + ["src/" + x["name"] for x in st["origin"]["files"]]
    return {"do": [{"id": "msheets", "cmd": "mat_sheets", "files": files[:5]}], "then": "script_ask"}


def _script_ask(st, fail: str = "") -> dict:
    from tools.calcopy.hybrid import render_bench, styles as STY
    v = st["version"]
    fmt = (render_bench.__doc__ or "")
    fmt = fmt[fmt.find("대본.json:"):] if "대본.json:" in fmt else fmt
    PR = st.get("product") or {}
    ms = st.get("_msheets") or {}
    ctx = (STY.brief(v) + "\n\n## 대본·재료 꼴\n" + fmt + "\n\n## 조사.md\n" + (st.get("research_md") or "") +
           "\n\n## 제품 판정\n" + RU.PRODUCT_TALK.get(PR.get("mode") or "exact", "") + "\n" +
           json.dumps({k: PR.get(k) for k in ("name", "product_id", "why", "mode", "name_hints")}, ensure_ascii=False) +
           "\n\n## 원음 받아쓰기(구간마다 — 모델 둘이면 둘 다)\n" + json.dumps(st.get("asr") or {}, ensure_ascii=False)[:6000] +
           "\n\n## 재료 파일(시트 순서 = 앞 5개)\n" + json.dumps(ms.get("list") or [], ensure_ascii=False) + _shots_ctx(st) +
           (f"\n\n## 대본 검사에서 걸린 것(고쳐라)\n{fail}" if fail else ""))
    return _rv(f"script_{v}", SCRIPT + "\n\n" + ctx, [_img(x) for x in ms.get("sheets") or []], need=("대본", "재료"))


def ph_script_ask(st, m, rp, u):
    st["_msheets"] = m.get("msheets") or {}
    return {"review": [_script_ask(st)], "then": "script_got"}


def audit_script(st: dict, S: dict, M: dict) -> dict:
    """서버 판정 — 대본 검사(script_audit) + 제목 색 + 자막↔목소리 + 출처 규칙 ①②·다른 출연자 샷. 하나라도 걸리면 반려."""
    from tools.calcopy.hybrid import script_audit
    v = st["version"]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "대본.json"
        p.write_text(json.dumps(S, ensure_ascii=False), encoding="utf-8")
        try:
            a = script_audit.audit(p, v)
        except Exception as e:  # noqa: BLE001 — 꼴이 틀린 대본은 검사가 죽는다 → 반려 사유로
            a = {"ok": False, "error": f"대본 꼴이 틀렸다: {type(e).__name__}: {str(e)[:200]}"}
    extra = {"title": RU.title_colors_bad(S, _style(v)), "caps_vs_tts": RU.caps_vs_tts(S),
             "source_rule": RU.source_rule_static(M, _origin_names(st), str(st["bench"].get("id") or ""), st.get("shots") or {})}
    on = _origin_names(st)
    if not any(str(c.get("src") or "") not in on for cs in (M.get("cuts") or {}).values() for c in (cs if isinstance(cs, list) else [cs])):
        extra["product_cut"] = ["제품 컷이 하나도 없다 — '써 봤다'·제품 설명 줄은 재료 파일(제품 영상 또는 prod_*.jpg 사진, 사진은 move: in·out·left·right)로. "
                                "원본 방송 화면만으로 우리 제품 이야기를 하지 않는다(98 #22)"]
    bad = {k: x for k, x in extra.items() if x}
    return {**a, **bad, "ok": bool(a.get("ok")) and not bad}


def ph_script_got(st, m, rp, u):
    v = st["version"]
    r = _reply(rp, f"script_{v}", ("대본", "재료"))
    S, M = r["대본"], r["재료"]
    if not isinstance(S, dict) or not isinstance(M, dict):
        a = {"ok": False, "error": "대본·재료는 JSON 객체여야 한다"}
    else:
        ch = ((st.get("origin") or {}).get("info") or {}).get("channel")
        if ch:                                   # 출처 줄 = 원본 채널 이름 그대로(사장님 '원본을 출처로') — 판정 답이 아니라 서버가 정한다
            S["source_label"] = f"출처: {ch}"
        M = RU.fill_shot_max(M, S, _origin_dims(st), st.get("shots") or {}, _ar(v))
        fixed = RU.fix_crop_units(M, _all_dims(st))
        if fixed:
            st["log"].append("crop 단위 바로잡음: " + "; ".join(fixed)[:300])
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
        return {"goto": "sign"}
    _tries(st, "script", LIMITS["script"])
    why = json.dumps({"orig_heard": bad}, ensure_ascii=False)[:4000]
    return {"review": [_script_ask(st, why)], "then": "script_got", "reject": {"why": why[:400], "fix": "원음 구간을 그 말이 들리는 자리로"}}


def script_view(st) -> dict:
    S = (st.get("script") or {}).get("S") or {}
    title = " ".join("".join(c[0] for c in l) if isinstance(l, list) else str(l) for l in S.get("title_lines") or [])
    lines = [(l.get("tts") or l.get("text") or " ".join(c[0] for c in l.get("caps_rel") or []) or "").strip() for l in S.get("lines") or []]
    return {"title": title, "lines": [x for x in lines if x][:30]}


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
    over = [p["over"]] if p.get("over") else []
    over += RU.source_rule_static(st["script"]["M"], _origin_names(st), str(st["bench"].get("id") or ""), st.get("shots") or {})
    over += p.get("jumps") or []
    st["_plan_over"] = over
    return {"review": [_fix_review(st, "; ".join(over), p.get("sheet"), f"plan_{st['version']}")], "then": "plan_look"}


def _fix_review(st, why: str, sheet: str | None, rid: str) -> dict:
    v = st["version"]
    _, _, ww, wh = _style(v)["frame"]["window"]
    sc = st["script"]
    return _rv(rid, PLAN_LOOK.replace("{ar}", f"{ww}:{wh}") + (f"\n\n멈춘 이유(재료를 고쳐라): {why}" if why else "") + "\n\n대본:\n" +
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
    bad = RU.source_rule_static(M, _origin_names(st), str(st["bench"].get("id") or ""), st.get("shots") or {})
    st["script"]["M"] = M
    st["_fix_bad"] = bad
    return M


def ph_plan_look(st, m, rp, u):
    v = st["version"]
    r = _reply(rp, f"plan_{v}", ("ok",))
    over = st.get("_plan_over") or []
    if r.get("ok") and not over and not r.get("재료"):
        return {"goto": "render"}
    _tries(st, "plan", LIMITS["plan"])
    M = _take_fix(st, r)
    if M is None:
        raise _Stop("장면 검수가 통과하지 않았는데 재료를 고치지 못했습니다", "다시 이어서 부르세요")
    return {"do": [{"id": "save_m", "cmd": "write_doc", "files": {f"{v}/재료.json": M}, "cand_dir": True, "version": v}], "then": "plan"}


# ── 10 렌더 ───────────────────────────────────────────────────────────────
def ph_render(st, m, rp, u):
    return {"do": [{"id": "render", "cmd": "render", "version": st["version"], "origin_names": sorted(_origin_names(st))}], "then": "render_got"}


def ph_render_got(st, m, rp, u):
    r = m.get("render") or {}
    why = r.get("error") or "; ".join(r.get("jumps") or [])
    if not why and r.get("ok"):
        tl = r.get("tempo") or {}
        cap = 1.36 if str((_style(st["version"]).get("voice") or {}).get("voice_id", "")).startswith("kr-mina") else 1.26
        if tl.get("max") and float(tl["max"]) > cap:
            st["log"].append(f"배속 {tl['max']} > {cap - 0.01}")
        return {"goto": "check"}
    if r.get("error") and "원본 샷보다 길다" not in str(r["error"]) and not r.get("jumps"):
        raise _Stop("영상을 만들다 멈췄습니다", str(r["error"])[:200])
    _tries(st, "render", LIMITS["render"])
    return {"review": [_fix_review(st, why, None, f"render_fix_{st['version']}")], "then": "render_fix"}


def ph_render_fix(st, m, rp, u):
    v = st["version"]
    r = _reply(rp, f"render_fix_{v}", ("ok",))
    M = _take_fix(st, r)
    if M is None:
        raise _Stop("렌더 뒤 재료를 고치지 못했습니다", "다시 이어서 부르세요")
    return {"do": [{"id": "save_m", "cmd": "write_doc", "files": {f"{v}/재료.json": M}, "cand_dir": True, "version": v}], "then": "render"}


# ── 11 검사 ───────────────────────────────────────────────────────────────
def ph_check(st, m, rp, u):
    return {"do": [{"id": "check", "cmd": "check", "version": st["version"], "asr_cross": True}], "then": "check_got"}


def ph_check_got(st, m, rp, u):
    c = m.get("check") or {}
    st["auto"] = c.get("auto") or {}
    sc = st["script"]
    heard = c.get("heard") or {}
    return {"review": [_rv(f"final_{st['version']}", FINAL_LOOK + f"\n\n자동 검사: {json.dumps(st['auto'], ensure_ascii=False)[:2500]}\n받아쓰기: " +
                           json.dumps(heard, ensure_ascii=False)[:3000] + "\n대본:\n" + json.dumps(sc["S"], ensure_ascii=False)[:5000],
                           [_img(c["sheet"])] if c.get("sheet") else [], need=("ok",))], "then": "check_look"}


def ph_check_look(st, m, rp, u):
    v = st["version"]
    look = _reply(rp, f"final_{v}", ("ok",))
    st["look"] = look
    auto_ok = bool(st.get("auto", {}).get("ok"))
    if look.get("ok") and auto_ok:
        return {"goto": "deliver"}
    long = [r for r in (st.get("auto") or {}).get("rows") or [] if r.get("what") == "길이" and not r.get("ok")]
    if long:                                    # 길이 넘침·모자람은 재료가 아니라 글로 고친다(배속 아님, 07 §4) → 대본 다시 + 회원 사인 다시
        _tries(st, "length", 2)
        st["tries"]["script"] = 0
        st["approved"] = False
        return {"review": [_script_ask(st, f"완성본 길이가 판 범위를 벗어났다: {long[0].get('value')} — 나레 글을 줄이거나(넘침) 늘려서(모자람) 범위 안으로. 내용·결은 그대로")],
                "then": "script_got"}
    _tries(st, "look", LIMITS["look"])
    probs = json.dumps({"자동검사": {k: x for k, x in (st.get("auto") or {}).items() if k != "ok"} if not auto_ok else None,
                        "눈 검수": look.get("problems")}, ensure_ascii=False)[:3000]
    return {"review": [_fix_review(st, "완성본 검사에서 걸린 것(화면·크롭·남의 글자는 재료로 고친다): " + probs, None, f"final_fix_{v}")], "then": "check_fix"}


def ph_check_fix(st, m, rp, u):
    v = st["version"]
    r = _reply(rp, f"final_fix_{v}", ("ok",))
    M = _take_fix(st, r)
    if M is None:
        raise _Stop("완성본 검사를 통과하지 못했고 재료로 고칠 수 없습니다", "숏템 피드백으로 알려 주세요")
    return {"do": [{"id": "save_m", "cmd": "write_doc", "files": {f"{v}/재료.json": M}, "cand_dir": True, "version": v}], "then": "render"}


# ── 12·13 납품·정리 ───────────────────────────────────────────────────────
def ph_deliver(st, m, rp, u):
    return {"do": [{"id": "final", "cmd": "finish", "version": st["version"], "title": script_view(st)["title"]}], "then": "finished"}


def ph_finished(st, m, rp, u):
    f = m.get("final") or {}
    if not f.get("video"):
        raise _Stop("완성본 파일을 찾지 못했습니다", "다시 이어서 부르세요")
    asr_single = not ((st.get("env") or {}).get("keys") or {}).get("speechmatics")
    return {"done": {"video": f["video"], "title": script_view(st)["title"], "auto_ok": bool((st.get("auto") or {}).get("ok")),
                     "look_ok": bool((st.get("look") or {}).get("ok")), "asr_single": asr_single,
                     "note": "귀 확인 없음(스피치매틱스 키 없음 — 위스퍼와 눈으로만 대조)" if asr_single else ""}}


PHASES = {
    "setup": ph_setup, "setup_check": ph_setup_check, "bench": ph_bench, "bench_got": ph_bench_got, "origin_read": ph_origin_read,
    "peer": ph_peer, "peer_read": ph_peer_read, "search": ph_search, "search_got": ph_search_got, "titles": ph_titles,
    "titles_got": ph_titles_got, "subs": ph_subs, "subs_got": ph_subs_got, "pick_got": ph_pick_got, "origin_fetch": ph_origin_fetch, "origin_got": ph_origin_got, "stopped": ph_stopped,
    "product_sheet": ph_product_sheet, "product_pick": ph_product_pick, "product_cands": ph_product_cands, "product_same": ph_product_same,
    "product_done": ph_product_done, "name_find": ph_name_find, "name_got": ph_name_got, "named_cands": ph_named_cands,
    "named_same": ph_named_same, "best": ph_best, "research": ph_research, "research_got": ph_research_got,
    "research_check": ph_research_check, "material": ph_material, "material_got": ph_material_got, "material_pick": ph_material_pick,
    "material_dl": ph_material_dl, "asr": ph_asr, "asr_got": ph_asr_got, "shots_got": ph_shots_got, "script": ph_script,
    "script_ask": ph_script_ask, "script_got": ph_script_got, "script_heard": ph_script_heard, "sign": ph_sign, "plan": ph_plan, "plan_got": ph_plan_got,
    "plan_look": ph_plan_look, "render": ph_render, "render_got": ph_render_got, "render_fix": ph_render_fix, "check": ph_check,
    "check_got": ph_check_got, "check_look": ph_check_look, "check_fix": ph_check_fix, "deliver": ph_deliver, "finished": ph_finished,
}
for _k, _v in {"origin_fetch": "origin", "stopped": "setup", "research_check": "research", "script_ask": "script", "script_heard": "script", "best": "product", "deliver": "done", "finished": "done"}.items():
    PHASE_STAGE.setdefault(_k, _v)
