# 무료 한글 폰트 수집 핸드오프

## 2026-09-11 완료 범위

- 라이브러리/UI 코드는 건드리지 않고 `font_collection/` 수집 산출물만 생성했다.
- 눈누 사이트맵 1,172개 상세 페이지를 전수 수집했다.
- 눈누 라이선스 표의 영상·임베딩·재배포가 모두 명시 허용된 395패밀리에서 웹폰트 625개를 받았다.
- Google Fonts 공식 저장소의 Korean subset 38패밀리를 수집했다.
- 개인 디자이너 및 제작사 공식 GitHub 15곳을 수집했다: Pretendard, SUIT, Wanted Sans,
  Interop, Galmuri, Mulmaru, MaruMinya Hangul, DenkiChip Hangul, MapleSaemmul,
  JAMO Orbit/Moirai/Grandiflora, LXGW WenKai KR, BitBit, D2Coding.
- 페이퍼로지, LINE Seed KR, Gmarket Sans, 물마루/모노, D2Coding은 공식 ZIP도 별도 수집했다.
- GitHub 검색 후보 121곳 중 미러/파생 의심을 제외한 원 제작 후보 88곳을 후속 검토 목록으로 남겼다.
- 실제 폰트 892개를 fontTools+Brotli로 전수 검사: 정상 892, 한글 지원 834, 비한글 58.
- 동일 SHA-256 중복 12그룹은 출처 비교를 위해 유지했다.

## 핵심 경로

- `font_collection/manifests/noonnu.json`
- `font_collection/manifests/google_fonts_korean.json`
- `font_collection/manifests/github_upstreams.json`
- `font_collection/manifests/official_archives.json`
- `font_collection/manifests/github_discovery.json`
- `font_collection/audit/files.json`
- `font_collection/audit/report.json`
- `font_collection/files/` (1.49GB, Git ignore, 같은 PC에서만 공유)

## 라이브러리 세션에서 지킬 것

1. `audit/files.json`에서 `valid=true`와 `has_korean=true`를 기본 필터로 쓴다.
2. 눈누 `file_policy=metadata_only` 항목은 파일을 라이브러리에 복제하지 않는다.
3. 조건부 허용은 자동 선택에서 제외하고 원 제작사 재확인 큐로 보낸다.
4. 내부 family/full name을 UI 표시명과 분리한다.
5. 중복 해시는 파일 하나만 저장하되 출처·라이선스 레코드는 모두 유지한다.

## 남은 일

- `github_discovery.json`의 원 제작 후보 88곳을 사람 눈으로 샘플 검수하고 추가 채택한다.
- 비한글 58개는 영문 포인트/아이콘 전용 그룹으로 쓸지 결정한다.
- 라이브러리 세션에서 시각 샘플 렌더와 훅용 점수(굵기·폭·가독성·개성)를 만든다.
