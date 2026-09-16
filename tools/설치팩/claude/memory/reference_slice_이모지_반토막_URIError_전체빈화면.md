---
name: reference-slice-urierror
description: "즐겨찾기·랭킹 '전부 지워졌다' 제보의 뿌리 — 카드 1장의 slice(0,60)가 이모지를 반으로 잘라 encodeURIComponent가 URIError → render 통째 중단. 데이터는 무사. 또 Bash heredoc 안 \\n은 실제 개행으로 들어간다"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 50bfe5b4-1d96-41a5-904f-3ce0cb3dbe70
  modified: 2026-09-04T05:16:13.235Z
---

2026-09-04 라이브 사고. 사장님 캡처 "영상 즐겨찾기가 모두 지워졌다", 곧이어 "모든 사람 다 그래".

- **데이터는 살아 있었다.** `/api/mix/basket` 응답 532KB. 화면만 못 그렸다.
- **뿌리**: 같은 날 병합된 '🛒 쿠팡에 있나?' 버튼(collection.html·index.html)이 제목을
  `.slice(0,60)`으로 자르는데, JS slice는 UTF-16 단위라 이모지(서로게이트 쌍)를 반으로 자른다.
  반토막 문자열을 `encodeURIComponent`에 넣으면 **URIError: URI malformed** → 카드 map 안에서
  던지니 카드 1장이 아니라 **전체 render가 죽어 빈 화면**. 캡션에 이모지 있는 회원은 전원.
- **판별 순서**: "다 지워졌다" 제보 → ①API 응답 크기 ②콘솔 EXCEPTION. 1분이면 갈린다.
  (관련: [[reference_render_crash_looks_like_buffering]] · [[reference_안뜬다는_데이터0건일수있다]])
- **처방**: `cpKw()` = `Array.from(s).slice(0,60).join('')`(코드포인트 단위) + try/catch. 화면 문자열을
  URL/인코딩에 넣을 땐 항상 이 모양. 게이트(pytest)는 HTML/JS를 못 본다 → node로 helper 실행 검증.

**How to apply:**
- 카드 목록 map 안에서 던질 수 있는 호출(encodeURIComponent·JSON.parse·toFixed)은 카드 하나가 아니라 목록 전체를 죽인다. 카드 단위 try/catch나 안전 helper.
- ★Bash 툴 heredoc 안의 `'\\n'`은 **실제 개행으로 파일에 들어간다**(같은 날 2번 당함, 커밋까지 됐다).
  백슬래시가 필요하면 Python에서 `chr(92)+'n'`으로 만들어라. 쓴 뒤 node/파서로 반드시 실행 확인.
- 급할 때 게이트 순번이 밀리면(다른 세션 finish 대기) HTML만 바뀐 건 사장님 지시로 트랙 HEAD를 `git push origin HEAD:main` 직접 올릴 수 있다(먼저 origin/main 머지).
