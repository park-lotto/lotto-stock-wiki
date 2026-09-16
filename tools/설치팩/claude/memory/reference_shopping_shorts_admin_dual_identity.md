---
name: reference_shopping_shorts_admin_dual_identity
description: 숏템메이커 사장님 로그인 이중신원 — 관리자비번=cid0(데이터 있음)/구글=cid2(빈계정). 기기간 안맞으면 admin로 통일
metadata: 
  node_type: memory
  type: reference
  originSessionId: 2f2de74e-9381-490d-83bf-4c43ed5192e4
  modified: 2026-07-26T07:39:05.155Z
---

숏템메이커(shopping_shorts)에서 **PC·모바일 작업/AI PICK이 서로 안 맞으면** 십중팔구 **로그인 신원 불일치**다. 사장님은 계정이 둘로 갈린다(서버 DB 실측 2026-07-26):

- **관리자 아이디/비번 로그인** (`DASH_USER`/`DASH_PASS`, app.py:4686) → **customer_id 0** (LEGACY). **script_wiki(도서관) 31건·produce_works·담김 데이터가 전부 여기 있다.**
- **구글 로그인** (`parklotto12@gmail.com`) → **customer_id 2** — 사실상 빈 계정(도서관 0건).

증상: 한 기기는 admin(cid0), 다른 기기는 구글(cid2)로 들어가면 ①내작업 목록이 서로 안 겹치고 ②AI PICK "이대로 만들기 시작"이 폴백("대본 아직 분석 못했어요")으로 떨어진다. AI PICK 소스(`_load_work_sources`)가 **그 계정의 script_wiki 저장분만** 보기 때문(app.py:5870). cid2엔 도서관이 없어 `build_aipick`이 `pick_id=null` 반환.

**해결: 모든 기기를 admin 로그인으로 통일** (구글 버튼 X, 로그인화면에서 관리자 아이디/비번). 데이터가 cid0에 있으니 이관 불필요·유실 없음. 구글로 통일하려면 cid0→cid2 데이터 이관이 선행돼야 한다.

⚠️ 2026-07-26 내가 처음에 "구글로 통일"을 권했다가 이 회귀를 만들었다 — **데이터가 어느 cid에 있는지 먼저 확인**하고 그 계정으로 통일하라. 관련: 헤더 '내 작업목록' 모달·대본없음 폴백 '📝대본뽑기' 버튼 복구도 이때 라이브. [[feedback_verify_before_claim_and_act]]
