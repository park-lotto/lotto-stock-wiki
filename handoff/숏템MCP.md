# 숏템MCP — 고객 PC 클로드형 설치팩·프리셋 옵션 페이지

관제 카드 234(사장님 승인 카드 — 회원 데이터: 라이선스·기기 잠금·탐지 로그·채널 옵션)

## 2026-10-18 (TheRose PC) 설계 확정
- 설계 4판: `docs/superpowers/specs/2026-10-18-숏템MCP-design.md` (미결 0, A~F 확정)
- 핵심: 렌더=고객 PC(카드 079·213), 서버 제작 호출 0 / 원격 MCP 없음 / 서명 exe·공증 pkg에 실행도구 전부 + 얇은 .mcpb / 자산은 편당 필요분만 서명 URL / 견본은 preview/ 접두사·워터마크 / 기기 2대·동시 작동 금지(lease) / 이상행동 A1~A10
- 판단 주인(선점 신고 완료): claude_portal.py:assets_for · lease · anomaly_check · preview / PC쪽 engine/next_step.js:nextStep / channel_profile.merge
- 비교 조사: 볼케이노 MCP(원격·OAuth·상태기계), 쇼츠AI 스타터킷(평문 동봉·winget 설치)

## ⏭ 다음
- 사장님 승인(카드 234) 후 1단계 착수: 실측 5종(자체 ffmpeg 용량, .mcpb 한계·키 저장, 견본 품질, 탐지 오탐, 고객 PC·맥 렌더 시간)
- 코드 들어갈 때 `관제/ownership.json`에 주인 함수 시그니처 등록(지금은 코드가 없어 정규식을 못 정함)
- 착수 전 `.tracks/칼카피숏템엔진` pull(로컬이 origin보다 뒤처짐)
- 클리피 조사: 사장님께 사이트 주소/설치 파일 위치/명령어 한 줄 받으면 진행
