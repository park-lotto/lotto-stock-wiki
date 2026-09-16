---
name: reference_미리보기_pv쿠키_되돌리기
description: 숏템메이커 미리보기 인스턴스 전환/복귀 = ?pv=1 / ?pv=0 (쿠키 ssprev), 분기 자체는 preview_route.sh on|off
metadata:
  type: reference
---

같은 공개 도메인(shoppingshorts.duckdns.org)이 **쿠키에 따라 라이브(8849)와 미리보기(8850)로 갈린다.**
그래서 "라이브 확인"을 했는데 실제로는 미리보기를 보고 있을 수 있다 — 파일이 코드와 안 맞으면 이걸 먼저 의심하라.

- `?pv=1` → 쿠키 `ssprev=1` 심고 미리보기로 (480분 뒤 만료)
- `?pv=0` → **되돌리기** (쿠키 삭제 → 라이브)
- 분기 자체 끄기/켜기: `bash /home/ubuntu/lotto-stock-wiki/deploy/preview_route.sh off|on` (on이 apache conf 백업을 뜬다)

판정은 아파치 `RewriteCond %{HTTP_COOKIE} ssprev=1` 로 한다(`/etc/apache2/sites-enabled/shopping-shorts-le-ssl.conf`).
미리보기 워크트리 = `/home/ubuntu/preview` (라이브 repo와 별개, 원하는 커밋으로 detach checkout).
미리보기 띄우기/내리기는 `deploy/preview.sh start track/<트랙> | stop | status`.

★실측 함정(2026-08-27): 브라우저에서 받은 filmroll.js가 서버 디스크 파일과 크기가 달라 한참 헤맸다.
  원인은 캐시가 아니라 **미리보기로 라우팅되고 있었던 것**. `find / -name <파일>`로 두 벌(라이브·preview)을 확인하면 바로 갈린다.
  관련: [[reference_deploy_truth_branch_ssh]]
