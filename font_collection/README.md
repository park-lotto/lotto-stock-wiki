# 무료 한글 폰트 수집 원본

이 폴더는 폰트 라이브러리 구현과 분리된 **수집 전용 산출물**이다.

- `manifests/noonnu.json`: 눈누 무료 폰트 전체 색인과 각 상세 페이지의 라이선스 표
- `manifests/google_fonts_korean.json`: Google Fonts의 Korean subset 전체 목록
- `manifests/github_upstreams.json`: 개인 디자이너·공식 제작사의 원본 GitHub 저장소
- `manifests/official_archives.json`: 제작사/개인 디자이너 공식 ZIP 배포본
- `manifests/github_discovery.json`: GitHub 한글/OFL 폰트 검색 후보와 원본성 검토 상태
- `files/google-fonts/`: 공식 `google/fonts` 저장소에서 받은 OFL 원본 파일
- `files/github/`: 제작자 원본 GitHub 저장소에서 받은 설치형 폰트 파일
- `files/official-archives/`: 공식 페이지·GitHub Release에서 받은 ZIP의 폰트 파일
- `licenses/`: 각 패밀리의 원문 라이선스와 공식 메타데이터
- `logs/`: 실패 URL과 재시도 대상
- `audit/`: 실파일 내부 이름·한글 글리프·손상·중복 검사 결과
- `collection_report.json`: 수집 건수와 용량 요약

눈누 항목은 `영상`, `임베딩`, `OFL/재배포`가 모두 명시적으로 허용된 경우에만
`download_allowed`로 분류한다. 조건부 허용, 재배포 금지, 판정 불명 항목은
파일을 복제하지 않고 메타데이터와 공식 다운로드 페이지 링크만 보관한다.

재실행:

```powershell
py tools/collect_font_sources.py --source all --download
```

이 수집 결과를 제품 라이브러리에 넣기 전에는 원 제작사의 최신 라이선스를 한 번 더
확인해야 한다. 눈누 역시 각 폰트의 저작권과 라이선스 문의 주체가 원 저작권자라고
명시한다.

## 2026-09-11 수집 스냅샷

- 눈누 상세 페이지: 1,172/1,172 수집
- 보수적 자동 다운로드 허용: 395패밀리, 웹폰트 참조 625개
- Google Fonts Korean subset: 38패밀리, 파일 참조 64개
- 원 제작 GitHub: 15곳(개인 디자이너 포함)
- 공식 ZIP: 페이퍼로지, LINE Seed KR, Gmarket Sans, 물마루 2종, D2Coding
- GitHub 추가 검색 후보: 121곳, 그중 원 제작 후보 88곳
- 실파일 감사: 892개 전부 정상, 한글 지원 834개, 비한글 장식/영문 58개
- 물리 용량: 1,493,785,744바이트
- 동일 해시 중복: 12그룹(출처 보존을 위해 삭제하지 않음)

실제 바이너리는 Git 용량 폭증을 막기 위해 `files/`가 ignore되어 있다. 같은 PC의 다른
세션에서는 이 트랙의 `font_collection/files/`를 직접 읽으면 된다. 영구 저장소로 옮길 때는
`audit/files.json`의 `has_korean=true`, `valid=true` 항목만 우선 사용한다.
