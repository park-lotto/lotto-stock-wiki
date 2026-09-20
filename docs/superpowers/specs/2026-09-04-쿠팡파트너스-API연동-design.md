# 쿠팡 파트너스 오픈API 연동 1단계 — 설계 (2026-09-04)

## 목표
회원이 8단계(SEO)에서 **상품 카드를 클릭하면** 파트너스 추적 링크가 자동으로 만들어져
설명란·인포크 문구에 들어간다. 파트너스 웹 왕복(상품 URL 복사 → 파트너스에서 링크 생성 →
붙여넣기)을 없앤다. 키는 **회원 각자의 파트너스 계정**(BYOK).

## 근거(실측 2026-09-04)
- 사장님 키로 딥링크 API 200(`link.coupang.com/a/…` 발급), 상품검색 API 200(5건, 추적태그 포함 URL).
- 담긴 인스타·틱톡 영상 4,141건 중 캡션에 쿠팡 링크 0.3% → 검색 API가 1차 발굴 수단.
  리뷰 0건 신제품은 검색에 안 뜬다 → **2단계(원본 채널 링크 발굴) 별도 스펙**.

## 범위(1단계)
1. `coupang_partners.search_products`·`to_deeplink` 껍데기를 HMAC 실호출로 채운다(호출부 무변경).
2. 회원 키 BYOK: `keyroute.SVC_COUPANG="coupang"`(SERVICES·WIRED, 개인 전용·폴백 없음).
   키등록 화면에 "쿠팡 파트너스" 카드. 값은 `AccessKey:SecretKey` 한 줄(VMake와 같은 방식).
   등록 시 딥링크 1회 호출로 살아있는 키만 저장.
3. 8단계: 회원 키가 있으면 `/api/coupang/search`가 **API 검색**을 먼저 쓴다(카드 형태 동일).
   없으면 종전(릴레이 크롤 → 수동) 그대로.
4. `/api/mix/product` 저장 시 회원 키가 있고 partner_url이 비어 있으면 **딥링크 자동 발급**.
   실패하면 원본 URL 유지 + 사유(작업은 안 막는다).
5. 남의 추적링크(`link.coupang.com/re/…?pageKey=` / `lptag=`)가 오면 상품번호만 남겨 본인 키로 재발급.
6. 관측: 호출 결과를 `api_events`(service=`coupang`)에 기록 → 관측판 등급 체계(회원 키 죽음=운영주의) 그대로.

## 범위 밖
- 상품검색 API로 릴레이 크롤 대체(키 없는 회원이 있어 릴레이는 남는다).
- 원본 채널 링크인바이오 발굴(2단계).
- 키 180일 만료 사전 경고(다음).

## 데이터·인터페이스
- `search_products(keyword, limit, access_key, secret_key)` → `{ok, items:[{product_id,name,url,image,price,rating,is_ad}], source:"api"}`
- `to_deeplink(urls, ak, sk)` → `[{original_url, shorten_url, landing_url, requires_approval:False}]`
- `probe_key(ak, sk)` → bool (딥링크 1회)
- `split_key("ak:sk")`, `canonical_product_url(url)`(추적 파라미터 제거·pageKey→상품 URL)
- product 레코드에 `partner_url`은 shorten_url, `partner_auto: True` 표시.

## 오류 처리
- API 401/403 → `api_health.record(outcome=auth_dead, customer_id)` → 관측판 "회원 N의 키가 죽음"(warn).
- 429·5xx → 카드 없이 종전 경로로 폴백, 화면에 사유.
- 키 형식 오류(콜론 없음·공백)는 등록 시점에 막는다.

## 테스트
- coupang_partners: HMAC 서명 형식, search/deeplink 응답 파싱(가짜 urlopen), canonical_product_url.
- keyroute: coupang이 SERVICES·WIRED, 개인 전용(사장님 키 폴백 없음).
- app: 키 있는 회원의 product 저장 시 딥링크 자동, 실패 시 원본 유지·200.
- byok_ui: 설정 화면에 coupang 카드(종전 "쿠팡 파트너스 없어야 한다" 검사는 폐기).
