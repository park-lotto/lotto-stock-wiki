# 썸네일 자막 제거본 선택 근본 수정

## 증상

- 박선정 고객(174)의 `1회용행주` 작업 `1a91a10941ec`은 `clean_status=ready`였지만 썸네일에는 자막이 남고 완성본에는 자막이 제거됐다.
- 서버 실측 당시 `clean_video_path`는 비어 있었고 현재 편성 청소본 `final_clean_42a1639f2994af8b.mp4`는 정상 존재했다.
- 저장된 썸네일 `video_sig`는 청소본이 아니라 `preview.mp4`의 mtime/size와 일치했다.
- 동일 구조(`subtitle_removal=1`, `clean_status=ready`, `clean_video_path` 없음)가 서버 DB에 22건 있어 반복 가능한 구조적 문제였다.

## 원인과 수정

- 완성본 1편 청소 구조는 `clean_video_path`를 채우지 않고 `final_clean_{plan_sig}.mp4`를 정본으로 남기지만, 썸네일 API는 구형 `clean_video_path`만 검사했다.
- `app._thumb_clean_background()`에서 현재 편성 서명의 `final_clean` → 구형 `clean_video_path` → 최근 `final_clean` 순으로 청소본 하나를 선택한다.
- 썸네일 API의 배경 선택과 자가치유 판단이 이 공용 선택 결과를 사용한다.
- 청소본이 뒤늦게 생기면 배경 파일 서명이 달라져 기존 preview 기반 프레임을 자동 재추출한다.

## 검증

- `test_app_thumb.py`: 30 passed
- 썸네일·자막 제거 관련 전체: 279 passed, 1 skipped
- 현재 편성 청소본 선택, 최근 청소본 폴백, 청소 전 preview 캐시가 새로고침 뒤 청소본 캐시로 교체되는 회귀 테스트를 추가했다.

## 다음 할 일

- 배포 뒤 고객 작업 `1a91a10941ec`의 썸네일 API를 호출해 기존 프레임을 재생성하고 실제 이미지 및 DB `video_sig`를 확인한다.
- 같은 구조의 기존 작업도 청소본 파일이 남아 있는 범위에서 일괄 재생성한다.
