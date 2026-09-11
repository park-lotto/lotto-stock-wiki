---
name: feedback_sector_label_integrity
description: 섹터 신호는 라벨만 보지 말고 속(실제 종목)이 일치하는지 검증해야 한다
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c471b6f9-0e43-4ca2-8e64-a79a91d391d2
---

주도섹터 산출 시 여러 데이터(미장·소르티노·빈집)가 같은 섹터 라벨을 달아도 **실체가 다를 수 있다.**

**Why**: 2026-06-26 "통신"이 A 교집합에 진입했으나 — 미장 통신=코닝·코히런트(AI 광통신부품), 소르티노 통신=RISE 네트워크인프라 ETF, 빈집 통신=KTcs·KT서브마린(통신SI·해저케이블). 같은 '통신' 라벨이지만 미장/소르티노는 광통신, 빈집은 KT 소형주로 불일치. `_match_sector` 키워드 매핑이 광통신과 통신서비스를 뭉뚱그린 탓. 빈집 종목(KTcs 등)을 사라는 신호로 읽으면 빗나감. (반면 반도체는 SK하이닉스·삼성전자가 3데이터 다 일치=깨끗).

**How to apply**: 섹터 신호 보고할 때 "라벨이 같다"로 끝내지 말고 각 데이터의 실제 종목/ETF를 까서 일치하는지 확인. 불일치면 명시(예: "통신 강세=광통신이지 KT 아님"). 고칠 것=광통신/네트워크인프라를 통신서비스와 분리. [[project_ttalkkak_dashboard]] [[project_leading_sector_system]]
