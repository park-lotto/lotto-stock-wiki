import json, sys
from pathlib import Path
D = Path(sys.argv[1]); OE = D.parent / "칼카피_OE11"
U = {"stwt": "https://www.youtube.com/shorts/stwtJyFQyKg", "cna": "https://www.youtube.com/watch?v=junnnF3cRuQ",
     "uiah": "https://www.youtube.com/watch?v=uiaHf2j2b5g", "ve6": "https://www.youtube.com/watch?v=-vE6Nl0cILw",
     "mrwho": "https://www.youtube.com/watch?v=n3F996g8wjg", "hc": "https://www.huaweicentral.com/honor-robot-phone-pre-order-begins/"}
facts = {
    "f1": {"text": "stwtJyFQyKg(Gyan Therapy, 1,763,764회, 2026-08-25) 댓글 1위(좋아요 1,770) 'At first, I thought it was another AI generated video 😂' · 'Mujhe phle AI LGA 😅'(7) — PlayMCP 댓글 20개 실측 10-16", "url": U["stwt"]},
    "f2": {"text": "같은 쇼츠 화면: 뒷면 카메라 덩어리가 위로 솟아 짐벌처럼 섬(5.8~7.2초, 12.5~14.8초) — 0.75초 간격 시트 눈 확인", "url": U["stwt"], "kind": "화면 관찰"},
    "f3": {"text": "CNA 'Gimmick or game changer? Chinese smart device maker Honor launches robot phone'(2026-08-13): 'Chinese smart device maker Honor… launched what it calls the world's first robot phone'(0~15초) · 'You see the retractable gimbal here. It can track my movements wherever I go.'(45.3~51.5초, 제미나이 받아쓰기)", "url": U["cna"]},
    "f4": {"text": "stwt 받아쓰기: 15.6~17.5초 'Play music and dance.'(영어 음성 명령) → 17.5~27.5초 폰에서 노래(가사만, 사람 말 없음) + 카메라 머리가 좌우로 움직임(18.5~25.2초 시트)", "url": U["stwt"], "kind": "받아쓰기+화면"},
    "f5": {"text": "CNA 'But reactions to this new concept were mixed.'(95.0~96.8초) + 거리 인터뷰(103.0~113.8초, 화면 영어 자막) 'I wouldn't consider it as I think it might be quite fragile. If you knock or drop it and the gimbal stops working, the repair cost would be high.' · 댓글 'If it drop while camera dancing 😮'(stwt, 31) · 'Afraid if after you accidentally drop it…'(CNA, 2)", "url": U["cna"]},
    "f6": {"text": "Huawei Central(2026-07-18) 사전예약 혜택: 'a free 1-year gimbal replacement guarantee' · 'Users can replace the movable robotic camera arm up to three times in a year for free.' (중국 사전예약 기준 — 해외 판매 조건은 확인 안 됨)", "url": U["hc"]},
    "f7": {"text": "브이로그 반응 댓글: CNA 'This is a niche device that can appeal to vloggers and content creators…'(11) · Mrwhosetheboss(n3F996g8wjg, 5,119,492회) 'If it’s really that convenient, it would be incredibly useful for vlog users.'(13) · 'for a content creator this is probably highly rated'(552)", "url": U["cna"] + " · " + U["mrwho"]},
}
lines = [
    ("훅(AI 의심→진짜)", "이게 AI 영상이 아니라고요? 카메라가 튀어나오는, 진짜 폰이에요.", ["f1", "f2"]),
    ("정체(로봇 폰·짐벌)", "아너가 만든, 로봇 폰인데, 뒷면 카메라가, 짐벌처럼 솟아올라요.", ["f3", "f2"]),
    ("기능 1(따라오기)", "내가 움직이면, 카메라가 고개 돌려서, 계속 따라온대요.", ["f3"]),
    ("기능 2(춤)", "말로 음악 틀고, 춤추라고 하면, 진짜 춤까지 춰요.", ["f4"]),
    ("논란(내구성)", "근데 반응은 엇갈렸어요, 고장 나면 수리비가, 걱정이라는 사람도 있었거든요.", ["f5"]),
    ("반전(무상 교체)", "그래서 중국에선, 사전 예약하면, 1년 동안 짐벌을, 세 번까지 공짜로 바꿔 준대요.", ["f6"]),
    ("마무리(누구한테)", "브이로그 찍는 사람한텐 딱이라는 댓글도 있네요.", ["f7"]),
]
S = {
    "topic": "AI 영상인 줄 알았던 아너(HONOR) 로봇 폰 — 카메라가 짐벌처럼 솟아 춤까지 추는데, 내구성 걱정 → 짐벌 무상 교체(중국 사전예약)",
    "titles": {"hook": "AI인 줄 알았던\n춤추는 로봇 폰"},
    "facts": facts,
    "caption_events": [
        {"kind": "emph", "text": "처음엔 AI인 줄 ㅋㅋ", "rgb": [80, 200, 255], "t0": 3.64, "dur": 3.0, "est": True,
         "basis": "f1 stwt 댓글 1위 'At first, I thought it was another AI generated video 😂'(1,770) 번역 — 이 구간 원음은 새소리(받아쓰기 3회 사람 말 없음), 화면은 카메라 솟는 장면"},
        {"kind": "emph", "text": "춤추다 떨어지면…?", "rgb": [80, 200, 255], "t0": 15.3, "dur": 4.5, "est": True,
         "basis": "f5 stwt 댓글 'If it drop while camera dancing 😮'(31) 번역 — 원음은 폰에서 나오는 노래(사람 말 없음), 다음 줄 내구성 논란으로 넘기는 다리"},
        {"kind": "blank", "t0": 30.6, "dur": 1.0, "est": True, "basis": "끝 1초 BGM 만(OE11 꼴)"},
    ],
    "final": {
        "lines": [{"fn": f, "text": t, "facts": fx, "sources": sorted({facts[k]["url"] for k in fx})} for f, t, fx in lines],
        "model": "오푸스 손 작성(제미나이 안 씀) — OE11 꼴(훅 질문→정체→기능 2→논란→반전→마무리, 해요체 7줄). 평가는 전부 댓글·인터뷰 전언체('~대요','~사람도 있었거든요','~댓글도 있네요')",
        "check": {"chars_no_space": [len(t.replace(" ", "").replace(",", "")) for _, t, _ in lines],
                  "total_chars": sum(len(t.replace(" ", "").replace(",", "")) for _, t, _ in lines),
                  "superlatives": [], "range_numbers": [],
                  "numbers": ["1년", "세 번 — f6 원문 'up to three times in a year'"]},
        "caption_split_note": "TTS 는 쉼표를 뺀 원문으로 1회 합성(OE11 과 같음). 자막 조각 ≤13자 — 쉼표로 조각 경계(narr_video chunk_sentence 쉼표 규칙, 화면엔 쉼표 안 나옴)",
    },
    "gate": {
        "scores": {"우리(로봇 폰)": {"아는 대상": 6, "몰랐던": 8, "재미": 8, "이야기": 7, "얻는 것": 6, "보여줄 수 있나": 8}},
        "score_note": "오푸스 판정(10-16). 아는 대상 6 = 스마트폰은 누구나 알지만 아너 브랜드는 국내 인지 낮음. 몰랐던 8 = 폰 카메라가 짐벌로 솟는 모양은 처음 봄. 이야기 7 = AI 의심→진짜→춤→고장 걱정→무상 교체. 얻는 것 6 = 고장 걱정에 대한 회사 답(1년 3회 교체)·누구에게 맞나. 보여줄 수 있나 8 = 실착 쇼츠(1080×1920)·뉴스 인터뷰 실영상, 단 따라오기 장면은 공식 영상의 고개 돌리는 짐벌(사람을 따라가는 실영상은 못 구함)",
        "angle": "'AI 영상인 줄 알았던 춤추는 폰 — 근데 떨어뜨리면? → 회사가 짐벌을 공짜로 바꿔 준다'",
        "twist": "6번 줄 '중국에선 사전 예약하면 1년 동안 짐벌을 세 번까지 공짜로 바꿔 준대요' — 5번 줄 내구성 논란에 대한 답",
        "twist_orig": "OE11 원본은 반전 없음(기능 나열). OE11 칼카피는 6번 줄 '오토바이용 아님' 반전 — 같은 자리",
    },
}
(D / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")

F = json.loads((OE / "frame_OE11.json").read_text(encoding="utf-8"))
for l in F["layers"]:
    if l.get("role") == "title":
        l["text"] = S["titles"]["hook"]
F["source"] = "frame_OE11.json 복사(제목 글만 바꿈) — 핫템 채널 틀"
(D / "frame_로봇폰.json").write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")

C = "C:/숏템_칼카피/hottemreport/칼카피_HONOR/cand"
shots = [
    {"i": 0, "src": "v_junnnF3cRuQ.mp4", "url": U["cna"], "ss": 34.3, "kind": "남의영상재편집", "full": True, "src_crop": [900, 0, 682, 860], "mute": True, "res": "1920x1080", "Y": 168,
     "ours": "흰 벽 앞 받침대에 꽂힌 로봇 폰 — 짐벌 카메라가 위로 솟고 화면에 로봇 눈(CNA 34.2~36.6 한 장면)",
     "why": "'이게 AI 영상이 아니라고요?' — 첫 1.6초에 '폰 위 로봇 머리' 그림",
     "why_audio": "CNA 기자·폰 대화(29.8~40.3) → mute", "crop_note": "아래 CNA 로고·뉴스띠(y≥885) 잘라 냄"},
    {"i": 1, "src": "v_stwtJyFQyKg.mp4", "url": U["stwt"], "ss": 3.6, "kind": "남의영상재편집", "full": True, "src_crop": [0, 120, 1080, 1361], "res": "1080x1920", "Y": 120,
     "gap_src": [5.6, 8.6], "audio_src": "v_stwtJyFQyKg.mp4", "audio_ss": 3.6,
     "ours": "공원에서 손에 든 폰(옆모습 5.0) → 뒷면 카메라가 위로 솟아 짐벌로 섬(5.8~7.2)",
     "why": "'카메라가 튀어나오는, 진짜 폰이에요.' 뒤 원음 3.0초 — 솟는 순간을 원음으로(OE11 원본 5.0~7.0 리액션 자리)",
     "audio_check": "stwt 5.6~8.6 사람 말 없음 — 받아쓰기 3회(전체·0~9초·0.5초 창 분류) 모두 새소리·기차 경적만, 첫 사람 말은 9.1초 'Hello, dance karte phone dekha hai kabhi?'",
     "overlays": [{"kind": "emoji", "emoji": "😲", "size": 170, "at": [210, 1180], "t": [2.3, 3.6], "why": "카메라 솟는 소스 5.9~7.2"}]},
    {"i": 2, "src": "v_stwtJyFQyKg.mp4", "url": U["stwt"], "ss": 12.4, "kind": "남의영상재편집", "full": True, "src_crop": [0, 120, 1080, 1361], "mute": True, "res": "1080x1920", "Y": 118,
     "ours": "폰 뒷면(12.5) → 앞으로 돌리자 짐벌 카메라가 솟아 있음(13.2~15.5)",
     "why": "'아너가 만든, 로봇 폰인데, 뒷면 카메라가, 짐벌처럼 솟아올라요.'",
     "why_audio": "12.0~15.0 말 없음(숨소리) · 15.6~ 영어 명령이 끝 0.3초 걸침 → mute"},
    {"i": 3, "src": "v_cNwj827V7WA.mp4", "url": "https://www.youtube.com/watch?v=cNwj827V7WA", "ss": 22.4, "kind": "남의영상재편집(공식)", "full": True, "src_crop": [790, 250, 659, 830], "mute": True, "res": "1920x1080", "Y": 193,
     "ours": "흰 배경 위 짐벌 카메라 머리가 좌우·위아래로 고개를 돌림(22.4~25.0 한 장면, 25.0부터 위쪽에 영어 글자 — y≥250 크롭으로 잘라 냄)",
     "why": "'내가 움직이면, 카메라가 고개 돌려서, 계속 따라온대요.' — 고개 돌리는 움직임(말 근거는 CNA 기자 'It can track my movements')",
     "why_audio": "공식 영상 음악 → mute", "crop_note": "위 'Do I seem different to you?' 글자(y≈160) 잘라 냄 · 확대 1.64배",
     "why_change": "1안 CNA 45.6(기자+폰)은 크롭 폭 674에 얼굴·폰이 같이 안 들어가 버림(시트 확인)"},
    {"i": 4, "src": "v_stwtJyFQyKg.mp4", "url": U["stwt"], "ss": 15.99, "kind": "남의영상재편집", "full": True, "src_crop": [0, 120, 1080, 1361], "res": "1080x1920", "Y": 105,
     "gap_src": [18.5, 23.0], "audio_src": "v_stwtJyFQyKg.mp4", "audio_ss": 15.99,
     "ours": "짐벌 카메라 + 화면 로봇 얼굴(15.5~17.8) → 음악 틀자 화면에 음표·카메라 머리가 좌우로 흔들림(18.5~23.0)",
     "why": "'말로 음악 틀고, 춤추라고 하면, 진짜 춤까지 춰요.' 뒤 원음 4.5초 — 폰이 노래 틀고 춤추는 소리(OE11 원본 12.5~15.0 자리)",
     "audio_check": "stwt 18.5~23.0 사람 말 없음 — 받아쓰기 3회 모두 노래(폰 재생, 중국어 가사 '從此海闊天空…')만. ★조율자 받아쓰기(18~25 힌디어 말)와 다름 — 0.5초 창 분류에서 17.5~27.5 전부 'sing', 사람 말은 9.1~12.0·15.6~17.5·28.0~29.3 셋뿐. 앞 15.99~17.5 영어 명령 'Play music and dance.'는 나레 아래(덕킹 10dB)로 덮임",
     "overlays": [{"kind": "emoji", "emoji": "🕺", "size": 170, "at": [210, 1180], "t": [3.0, 4.5], "why": "카메라 머리 흔들림 소스 18.9~20.4"}]},
    {"i": 5, "src": "v_junnnF3cRuQ.mp4", "url": U["cna"], "ss": 104.3, "kind": "남의영상재편집", "full": True, "src_crop": [800, 0, 682, 860], "mute": True, "res": "1920x1080", "Y": 114,
     "ours": "광저우 거리 인터뷰 — 청년이 '부서지기 쉬울 것 같아 안 산다, 짐벌 고장 나면 수리비가 비쌀 것'이라 말하는 장면(104.0~114.5 한 장면)",
     "why": "'근데 반응은 엇갈렸어요, 고장 나면 수리비가, 걱정이라는 사람도 있었거든요.' — 그 말을 한 사람 얼굴",
     "why_audio": "중국어 말 → mute(나레가 내용 전함)", "crop_note": "아래 영어 자막·CNA 로고(y≥885) 잘라 냄"},
    {"i": 6, "src": "v_-vE6Nl0cILw.mp4", "url": U["ve6"], "ss": 66.0, "kind": "남의영상재편집", "full": True, "src_crop": [440, 100, 778, 980], "mute": True, "res": "1920x1080", "Y": 134,
     "ours": "런던 거리 리뷰어가 짐벌 솟은 로봇 폰을 얼굴 옆에 들고 있음(65~78 한 장면)",
     "why": "'그래서 중국에선, 사전 예약하면, 1년 동안 짐벌을, 세 번까지 공짜로 바꿔 준대요.' — 솟은 짐벌이 계속 보임",
     "why_audio": "리뷰어 말 → mute", "crop_note": "왼쪽 위 'Shot on Oppo Find X9 Ultra' 글자(y<90) 잘라 냄"},
    {"i": 7, "src": "v_uiaHf2j2b5g.mp4", "url": U["uiah"], "ss": 57.4, "kind": "남의영상재편집(공식)", "full": True, "src_crop": [480, 0, 857, 1080], "mute": True, "res": "1920x1080", "Y": 90,
     "gap_src": "end 1.0",
     "ours": "방에서 로봇 폰으로 셀카 브이로그 찍는 여성(57.5~59.2) → 짐벌 카메라 클로즈업(59.5~60.9)",
     "why": "'브이로그 찍는 사람한텐 딱이라는 댓글도 있네요.' — 끝 1초는 BGM 만",
     "why_audio": "공식 광고 음악 → mute", "bright_note": "평균 밝기 Y80~107(다른 컷 105~168보다 어두운 편, 검정 아님)"},
]
M = {
    "_note": "HONOR 로봇 폰 칼카피 재료 계획(TTS·렌더 전 선검수). 시각은 OE11 말속도 7.965자/초(공백 뺀 글자)로 추정 — TTS 뒤 gap_src[0] − 그 문장 말 길이로 ss·audio_ss 를 다시 맞춘다. 원음 구간은 사람 말 없는 곳만(조율자 10-16).",
    "cand_dir": C,
    "replaced": "없음(새 소재 — 같은 제품 실영상)",
    "narration": "타입캐스트 필재(남성, copy_render.NARR 기본) · OE11 과 같은 템포 1.24(OE11 실측 7.965자/초) · 해요체 7줄 · 184자(공백·쉼표 뺌)",
    "shots": shots,
    "gaps": {"plan": "문장 2('카메라가 튀어나오는, 진짜 폰이에요.') 뒤 3.0초 · 문장 5('…진짜 춤까지 춰요.') 뒤 4.5초 · 끝 1.0초",
             "hottem_audio_gaps": "1:3.0,4:4.5,end:1.0"},
    "sfx": [
        {"file": "C:/숏템_칼카피/packs/sfx/sfx_pick/sfx_29.mp3", "t": 3.93, "db": -6, "why": "OE11 과 같은 팝 — 😲 등장(컷1 시작 1.63 + 2.3)"},
        {"file": "C:/숏템_칼카피/packs/sfx/sfx_pick/sfx_29.mp3", "t": 15.79, "db": -6, "why": "🕺 등장(컷4 시작 12.79 + 3.0)"},
        {"file": "C:/숏템_칼카피/packs/sfx/sfx_pick/sfx_10.mp3", "t": 23.82, "db": -4, "why": "반전 줄 시작(컷6)"},
    ],
    "source_audio": {"keep": True, "volume": 1.0, "duck_db": 10.0, "why": "OE11 과 같음 — 원음 구간 크기는 TTS 뒤 hottem_audio measure 로 재서 gap_gain 정함(지금 미정)"},
    "caption_effects": {"now": "OE11 과 같은 틀: 흰 글자 PretendardXBold 84 + 검정 외곽선 8px · 교체형(replace) · 한 줄 ≤13자",
                        "planned": "gap 두 곳 하늘색 강조 자막(caption_events emph) — narr_video 64827c81e 연결됨(OE11 통과)"},
    "timing_est": {"shots": [[0.0, 1.63], [1.63, 6.64], [6.64, 9.91], [9.91, 12.79], [12.79, 19.8], [19.8, 23.82], [23.82, 27.96], [27.96, 31.6]],
                   "gaps": [[3.64, 6.64], [15.3, 19.8], [30.6, 31.6]],
                   "how": "공백 뺀 글자 ÷ 7.965(OE11 TTS 23.226초/185자) — 렌더 전 추정. 글자 = 쉼표·공백 뺀 184자"},
}
(D / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", S["final"]["check"]["total_chars"])
