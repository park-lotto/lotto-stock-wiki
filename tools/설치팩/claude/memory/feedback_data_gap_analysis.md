---
name: feedback-data-gap-analysis
description: 위키에 없는 데이터는 연결 못 한다. 공백 = 틀린 분석. 데이터 채우기가 분석 품질을 결정한다.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e4f94263-e481-4365-85ad-fb4315c820f8
---

위키(stock 파일)에 없는 종목·섹터는 이슈 연결이 불가능하다. 없으면 그냥 지나친다.

**Why:** 두 가지 실패 사례:
1. 현대오토에버·LG CNS·LG전자·현대모비스 파일이 없어서 젠슨황 방한 수혜주를 못 잡음
2. 삼화콘덴서 파일에 "어닝쇼크" 데이터만 있고 "삼성전기 급등 후 밸류에이션 갭 플레이" 패턴이 없어서 "후발주 아님"이라고 틀린 분석

**How to apply:**
- 분석 전 해당 섹터 stock 파일 존재 여부 확인
- 없는 파일 = 분석 불가 표시 + 사용자에게 데이터 채우기 필요성 언급
- 있어도 핵심 패턴(주가 급등 사례, 뉴스 반응 패턴)이 없으면 틀릴 수 있음 명시
- 어닝 데이터만 있고 주가 패턴이 없는 종목은 "데이터 불완전" 경고

[[feedback_issue_first]] [[project_wiki_data_methodology]]
