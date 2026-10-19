# 아마존 상품 리서치 강의 조사 (2026-10-19)

검색어 14개를 돌렸고(yt-dlp ytsearch + WebSearch), 자막 12개를 받아 읽었다. 자막 위치: `amz_subs\`. (5개는 429로 자막 실패: Hv4iPJZoENs, S5Xh39hMdg0, clyDp6UEyZs, tmqmX9agHew, 0BnPdsCcQV0. 제목만 확인했고 내용은 읽지 않았다.)
표기: [확인] = 자막에서 인용 확인 / [추정] = 내 판단.

## 1. 공통 기준 (강사들이 쓰는 값)

| 기준 | 강사들 값 | 무료 공개 데이터로 구현? |
|---|---|---|
| 월 판매량 | 최소 100~300개, 상한 300~380 (신규 셀러). 300+ (JS 공식). 180~380, 250~300 | 부분 가능. BSR로 추정(오차 큼), 또는 "X+ bought in past month" 배지(50+ 단위 구간값). Keepa 무료 확장은 "순위 하락 횟수/월"을 보여줌 |
| 월 매출 | $6,000~18,000 / $10,000~88,000 / $1,500~5,000 / 최소 $5,000 | 가격 x 추정 판매량으로 계산 가능(추정) |
| 가격대 | $15~85, $18+, $30~80, $20~40(영국 £), $14.99~39.99, 이커머스 일반 $20~200 | 가능 (베스트셀러 페이지에 가격 있음) |
| 리뷰 수 상한(경쟁도) | <50(Black Box 초보), <100(JS), <300(Crescent), <400(Travis), 500(Passive Path), 1,000(Travis 완화) | 가능 (페이지에 리뷰 수 있음) |
| 평점 | 4.2 이상(Travis) 또는 일부러 낮은 평점(<=3, 개선 여지) | 가능 |
| 판매/리뷰 비율 | 판매량 30 이상 : 리뷰 1 (Paul Savage) = 리뷰 증가 속도가 느린 상품 | 부분 가능. 판매량 추정과 리뷰 수가 있으면 계산됨 |
| 순위 급상승 | Movers & Shakers = 24시간 순위 상승 상위, "트렌드 신호"이며 단독 근거로 쓰지 말고 검증 | 가능하나 수집이 까다로움(아래 b) |
| 신상품/신출시 | New Releases에서 매출 좋은 신규 (Travis) | 가능 (공개 페이지) |
| 제외 조건 | 계절상품, 선물세트, 액체, 대형/중량(수수료), 게이트 카테고리 | 카테고리·제목 키워드로 일부 가능 |
| 판매 실재 확인 | Keepa 순위 그래프 하락 횟수 = 판매 횟수 근사 | 무료 Keepa 확장/페이지 일부 가능 [추정: 대량 자동 수집은 유료 API] |

## 2. (a) 무료 공개 페이지만으로 판매 속도 재기

- BSR -> 판매량 환산: 강사들이 쓰는 방법. Todd Wells는 Jungle Scout 무료 추정기에 순위+카테고리를 넣음("BSR 16 Pet Supplies = 월 16,680개", 그는 "JS는 높게 나오는 편"이라 말함) [확인]. MWQH는 Greg Mercer 환산표를 인용: "BSR 728 = 하루 약 10개" [확인]. 환산표는 카테고리마다 달라 [추정] 상대 비교용으로만 쓰는 게 안전.
- BSR 변화(스냅샷 누적): 우리가 매시간/매일 BSR을 저장하면 직접 만들 수 있다 [추정]. 베스트셀러 페이지가 하루 단위로 순위를 주므로 이전 값과 비교하면 Movers 효과를 자체 구현 가능.
- Keepa 방식: 순위가 "떨어졌다 올랐다" 하는 횟수(drops)가 곧 판매 횟수. 예: 90일 평균 월 42회 vs 월 5회 [확인, Tit66RxdCy0 "Duke Does Amazon"]. 순위 값 자체보다 이 횟수가 중요하다고 강조. 자동화는 Keepa 유료 API 필요 [추정].
- 리뷰 증가 속도: 판매 대비 리뷰 비율(1:30 이상, 약 3~4%) [확인, Paul Savage]. 우리가 리뷰 수를 일별 저장해 증가분/일을 구하면 판매 속도 대용 지표가 된다 [추정].
- "X+ bought in past month" 배지: PMG 2023 분석에 따르면 월 50개 초과 판매 상품에만 뜨고, 대상 상품 중에서도 일부에만 표시됨. 캐나다 셀러 포럼에서 "50+/100+ bought in past month" 구간 표기 확인. 1K+ 이상 구간과 산정 방식은 확인 못 함 [WebSearch 2건, 2023 자료라 현재와 다를 수 있음]. 구간값(하한)이라 정밀도는 낮지만 무료 공개이고 실제 구매 신호라 가장 직접적. 우리 서버/브라우저에서 해당 문구가 실제로 뜨는지는 아직 직접 확인 안 함.

## 3. (b) Movers & Shakers 데이터 받기

- 공식 API는 없다(검색에서 못 찾음) [확인 못함]. 모두 HTML 스크래핑.
- 상품이 2개만 잡히는 원인 [추정이나 검색 결과가 일치]: 페이지가 지연 로딩(lazy load)이라 스크롤해야 나머지가 뜬다. 단순 HTTP 요청은 약 30개, 헤드리스는 스크롤 + 대기가 필요하다는 튜토리얼이 있다. 스크롤을 여러 번 하고 2~5초 기다리면 개선될 가능성이 크다.
- 한 차트당 최대 100개(Apify 액터 설명). 카테고리 단위로 모아야 한다. 갱신은 시간 단위라 하루 몇 번 수집이 의미 있음. 급하게 연속 요청하면 15회 안팎에서 차단된다는 보고.
- 대안: Apify의 Amazon Movers & Shakers 스크래퍼(유료), 또는 자체 스냅샷 방식(위 a의 BSR 변화).
- Chris Green(YnyBMGEv4Dw): M&S 장난감 카테고리를 하루 몇 번 보고 새로 올라온 항목을 찾고, Keepa 무료 확장으로 가격 이력을 확인 [확인].

## 4. 영상별 항목

1. COMPLETE Amazon Product Research Tutorial 2026 | Crescent Kao | 6,116회 | https://www.youtube.com/watch?v=6Ve3dV8-jF0 | Helium 10 Black Box, Xray | 인용: "set the max review count to 300"; "I prefer higher priced products, ideally around $30 to $80"; "monthly revenue ... between $6,000 and $18,000"; "monthly sales ... 300 units minimum"; 낮은 BSR + 나쁜 리뷰 조합 탐색.
2. Amazon FBA COMPLETE Product Research Tutorial 2026 | Travis Marziani | 33,324회 | https://www.youtube.com/watch?v=pBhY-fP2oiE | Helium 10 Black Box, Cerebro, Amazon New Releases/Movers | 인용: "less than 400 reviews"; "search volume of at least 200"; "price ... between $15 and $85"; "review count we'll go up to 1,000, rating 4.2"; Movers & Shakers = "biggest gainers in sales rank over the past 24 hours ... a sign a trend is on the rise", 단독 근거로 쓰지 말라고 함.
3. How To Do Amazon FBA Product Research Using Helium 10 FULL TUTORIAL 2026 | Darren - FBA Elite | 15,266회 | https://www.youtube.com/watch?v=kp0QZsz-RtQ | Helium 10 Black Box | 인용: 가격 최소 £20(미국은 $25 이상), 최대 £40; "between 100 ... up to around 300 units per month" (3개월 재고와 PPC 부담 때문); 소형/표준 사이즈 위주, 1.9kg 이하(영국 기준).
4. Product Research Filters That Find Me $5000-$10,000 Per Month Products | Paul J. Savage | 2,932회 | https://www.youtube.com/watch?v=K_tRE0buY1g | Helium 10 Black Box | 인용: 리뷰 약 11~190; "minimum of like 30 sales to every review"; 월 판매 "180 to maybe 380"; 매출 대신 판매량 필터 사용; 정렬은 리뷰 낮은 순.
5. Jungle Scout Product Database tutorial | Jungle Scout | 179,392회 | https://www.youtube.com/watch?v=ISUn4_cpMW0 | Jungle Scout Product Database | 인용: "price no lower than 18"; "at least 300 sales per month ... about 10 sales per day"; "maximum of 50 to 100 reviews".
6. Helium 10 Amazon FBA Product Research (low competition) | The Passive Path | 41,091회 | https://www.youtube.com/watch?v=9ZFZmgBMeaE | Helium 10 Black Box 키워드 방식, Xray | 인용: 검색량 "at least 10,000"; 월 매출 "at least 10,000" (10~50k); 리뷰 "max 500"; 계절 상품 제외; Xray에서 스폰서 4개 제외하고 자연 노출 1위부터 리뷰 대비 매출 비교.
7. How To Pick Top Selling Products For Amazon FBA | MyWifeQuitHerJob | 76,562회 | https://www.youtube.com/watch?v=R4W5arb9QHs | Amazon BSR(무료), Jungle Scout | 인용: 이상적 가격 $20~200; "BSR 728 ~ about 10 sales per day"; JS 예시 "at least five thousand dollars a month with less than a hundred reviews"; eBay 판매완료 목록도 활용.
8. How to Find Amazon Sales per Month for Wholesale Products | Amazon Seller School (Todd Wells) | 135,540회 | https://www.youtube.com/watch?v=GxoLYEi1bPg | Jungle Scout 무료 판매 추정기(순위+카테고리 입력), ReviewMeta | 무료 BSR 환산 과정 시연.
9. Free Amazon Product Research WITHOUT Any Paid Tools! | Sumner Hobart | 16,314회 | https://www.youtube.com/watch?v=cDosRI877fQ | 무료: Helium 10 무료 확장 + 구글시트 | 시트 컬럼: ASIN, 리뷰 수, 평점, 가격, BSR, 월 판매 추정. 임계값은 없고 양식 위주.
10. KEEPA SERIES: How to Tell if Something is Selling & How Often | Duke Does Amazon | 1,082회 | https://www.youtube.com/watch?v=Tit66RxdCy0 | Keepa | 인용: 순위 하락 횟수 = 판매 횟수, 90일 평균 "42 times per month" vs "five times per month".
11. Finding products to resell on Amazon using Movers & Shakers & Keepa | Chris Green | 2,330회 | https://www.youtube.com/watch?v=YnyBMGEv4Dw | Amazon Movers & Shakers (장난감), Keepa 무료 확장 | M&S는 24시간 순위 상승, 시간 단위 갱신, 하루 한두 번 확인해 신규 진입 포착; 제3자 판매자의 가격 부풀림(재고 없음 신호) 구별.
12. (한국어) 헬리움10 Black Box 상품 찾기 | 아마존 셀러 채널(제작자 "보표") | 16,647회 | https://www.youtube.com/watch?v=bLnJxzeGAlE | Helium 10 Black Box | 자막이 영어 번역본이라 표현은 번역투. 인용: "monthly sales $1,500~$5,000"; "$14.99 to $39.99"; "max number of reviews to 50"; "maximum review score to 3" (낮은 평점 = 개선 여지). 제목·채널명은 터미널 인코딩으로 깨져 일부는 내 추정 표기. 게이트 카테고리 회피 권고.

한국어 영상 추가 후보(자막 못 받음, 제목만 확인): clyDp6UEyZs(아마존에서 잘 팔리는 상품 소싱), tmqmX9agHew(아마존 데이터로 상품 소싱), y4gedKMJ8K4(아마존 바로가기 5화 60,609회).

## 5. 참고
- 영어 강사 대부분이 신규 셀러 기준(경쟁이 약한 틈새)이라 "월 300개 이하·리뷰 100~400 이하" 쪽이다. 쇼핑쇼츠용 "신박한 인기 상품"에는 반대로 판매 속도 상승(Movers)과 신규 출시, 높은 판매량 하한이 더 맞을 수 있다 [추정].
- 판매량 숫자는 모두 도구 추정치이고 강사들도 "스냅샷이며 높게 나오는 편"이라고 한다 [확인].
