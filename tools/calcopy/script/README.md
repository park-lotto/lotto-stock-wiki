# 대본 칼카피 엔진 (`tools/calcopy/script`)

채널 하나의 쇼츠 **대본(말)** 을 전부 받아 줄 단위로 뜯고, 첫 줄 유형별로 묶어 그대로 베껴 쓸 수 있는 칼카피 카드를 만든다.
화면·편집 칼카피는 `tools/calcopy/engine`(뜯기)이 맡는다. 이 엔진은 말만 본다.

| 단계 | 하는 일 | 버텍스 |
|---|---|---|
| `list` | 채널 쇼츠 목록(yt-dlp --flat-playlist) → `out/script_calcopy/<slug>/list.tsv` | 0 |
| `pull` | 음성만 받기(m4a, 쿠키·로그인 없음). `audio/`는 커밋 안 함 | 0 |
| `transcribe` | faster-whisper 받아쓰기(이 PC CPU) → `transcripts.json` | 0 |
| `tag` | 줄별 상세 태깅 — beat·연결어·어미·장치·권위 종류·꾸밈말·와우 종류·줄 틀 + 편별 화자·인물 역할·스토리 전개·CTA | 묶음(기본 8편/회) |
| `cluster` | 첫 줄 유형 × 전개 방식(정체 위치·권위·와우 수·닫는 법)으로 묶기 → `types.json` | 0 |
| `card` | 유형별 칼카피 카드 → `cards/<유형>.json·md`. 숫자는 전부 태그를 센 값 | 0 |
| `report` | 보고 HTML → `report.html` | 0 |

- 모든 단계는 **재개 가능**하다(끝난 편은 건너뛴다).
- 태깅 품질 검사: 줄을 이어 붙인 글이 받아쓰기 원문을 85% 이상 덮어야 카드에 들어간다(`coverage`). 모델이 줄을 빼거나 요약한 편은 빠진다.
- transcribe 는 faster-whisper 가 깔린 파이썬으로 돌린다(예: `바탕화면/쇼츠AI_스타터킷/.venv/Scripts/python.exe`).

```
py tools/calcopy/script/script_calcopy.py list --url https://www.youtube.com/@두유노홈디노/shorts --slug homedesignnote
py tools/calcopy/script/script_calcopy.py pull --slug homedesignnote
<whisper python> tools/calcopy/script/script_calcopy.py transcribe --slug homedesignnote
py tools/calcopy/script/script_calcopy.py tag --slug homedesignnote --batch 8
py tools/calcopy/script/script_calcopy.py cluster --slug homedesignnote
py tools/calcopy/script/script_calcopy.py card --slug homedesignnote
py tools/calcopy/script/script_calcopy.py report --slug homedesignnote
```
