# 옥수수커터 창고판 (관제 269, 2026-10-25) — 창고 먼저 → 선별 → 대본

사장님: "장면 모을 때 많은 영상을 처음부터 분석해야 그다음 선별", "사진·멈춤 없이 두유노홈디노 99% 퀄리티".

## 원본(두유노홈디노) 화면 공식 — 상위 6편 실측
- 모든 컷 = 바로 그 제품(출처 1편 3개 · 3~5편 2개, 출처 달라도 제품 같음)
- 핵심 동작 하나를 각도·사람만 바꿔 반복(TV 거치대 16컷 중 끌기 6컷)
- 대본 한 줄 = 그 말 그대로의 장면(1:1)
- 잇썸홈 옛 5편: 아이스큐브·옥수수커터 = 같은 종류 다른 제품 섞임, 대사↔장면 어긋남. 원인 = material_auto 가 대본 먼저→줄마다 검색,
  잇썸홈 규칙 same_product_only False + situation/before 허용(material_auto.py:66), 제품 칸에 similar 통과(:521)

## 이번 손 제작
1. ytsearch 6개 검색어 → 43편 전수 장면 시트 → 최다 제품 Chef'n Cob → 전용 검색 11편 더
2. 글자·로고 없는 고화질 3편: A=IlvcFqaYEgE(4K) · B=X1wdusSWj0s(1080) · C=c9-LzEQ5ZOs(4K, 0~8초 글자 있음 피함)
3. 핵심 동작(통에 끼워 밀면 알 우수수) 20컷 중 11컷, 대본은 장면 보고 마지막에(대본.json·재료.json)
4. preset_make 렌더: 19.63초, 멈춤(freezedetect) 0, 샷 번쩍 0, B13(±3초) 20건·A12 1건만 미달
- 완성본: 구글드라이브 `칼카피영상/잇썸홈 대기중/칼카피_잇썸홈_옥수수커터_창고판.mp4` (md5 a060a86f…)

## 집에서 이어 하기
- 재료 받기: `yt-dlp -f "bv*+ba/b" --merge-output-format mp4 -o C:/숏템_칼카피/homedesignnote/작품5_옥수수커터_창고판/A.mp4 https://youtu.be/IlvcFqaYEgE` (B·C 같은 식) 후 이 폴더 json 2개 복사
- 렌더: `PYTHONUTF8=1 py tools/calcopy/engine/preset_make.py channel/homedesignnote/preset/전체화면_가운데자막 <작업폴더> --allow-tts`
- ⏭ 사장님 판정 → 이 순서를 material_auto 에 넣기(창고: 전 후보 태깅 → product=same 만 → 최다 동작=핵심 → 출처 1~5편 → 장면 목록 주고 대본 → 1:1 배치 → 멈춤·다른제품 검사)
- ⏭ 사장님 결정 필요: B13 '같은 소스 ±3초' 규칙 — 원본 공식(한 영상 연속 컷)과 충돌. 실제 겹침만 막을지
