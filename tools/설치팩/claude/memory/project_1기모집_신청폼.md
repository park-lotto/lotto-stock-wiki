---
name: project-1
description: 숏템메이커 1기 구글폼(Apps Script로 생성·갱신) + 마이페이지 결제카드. 링크·계좌·환불규정 확정
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f9103ad-e557-463a-9a3b-3411f8e30338
  modified: 2026-08-30T05:50:22.339Z
---

숏템메이커 1기 모집(2026-08-30 착수). 참가비 **77만원**, 정원 미정(선착순 마감).

**구글폼은 손으로 안 만든다 — Apps Script로 만든다.**
`out/숏템메이커_1기_신청폼_갱신.gs`의 `rebuildForm()`이 **기존 폼을 그대로 두고 문항만 갈아끼운다**(링크 유지).
문항을 바꿔야 하면 이 파일을 고쳐 다시 실행하면 된다. 새로 만들지 마라(링크가 바뀐다).

- 신청폼: `docs.google.com/forms/d/e/1FAIpQLScd2daWqtFnea1e_5y5ZKq6OkDPOeuw3qLg3tBinv6G2P4eCQ/viewform`
- 편집: 폼 ID `1j7DEOvChLxsUDl8VHnj9o18kPw1c5hDvZbZW4sWMd5Q` (★`DEOv` — 로그 스샷에서 O를 0으로 읽어 한 번 틀렸다)
- 카드결제: `stmaker.kr/surl/O/3068` — **2026-08-31(일) 11:00 KST 오픈**
- 계좌: 카카오뱅크 3333-13-9497518 (최지희)

**환불규정** = 서비스 개시(계정 발급·로그인 가능 시점) 후 환불 불가.
유효성 때문에 ①결제 전 고지+동의(전자서명 칸=성함 직접 입력) ②판매자 귀책 시 환불 조항을 **반드시 남긴다**.
둘 중 하나라도 빼면 규정 전체가 무효로 다뤄질 수 있다. 개별 예외는 사장님 재량.
저장소에 기존 환불규정 문서는 **없었다**(전수 검색 확인) — 이 초안이 첫 문서다.

**Apps Script 실행 시 함정**: 최초 실행의 OAuth 승인 팝업은 **자동 클릭으로는 안 뜬다**(크롬이 사용자 제스처로 안 봄).
실행이 로그 없이 멈춰 있으면 이것이다. 사장님이 직접 ▶실행을 눌러 "고급 → 안전하지 않음으로 이동 → 허용".

마이페이지 결제카드는 [[project_마이페이지_결제카드]] 참고. 브랜드명은 [[project_brand_name_shottemtops]].
