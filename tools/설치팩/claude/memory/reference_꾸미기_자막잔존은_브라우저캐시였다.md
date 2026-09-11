---
name: 꾸미기-자막잔존은-브라우저캐시였다
description: "자막제거 했는데 꾸미기에 자막 그대로" 제보의 또 다른 뿌리 — 서버는 청소본에서 뜨고 있었고, 화면에 나간 건 청소 전에 받아 브라우저에 남은 옛 그림. 주소가 같으면 다시 안 받는다
metadata:
  type: reference
---

2026-09-09 박세현님 job `57722281732e`(work=dbb99123b5ca). 6단계 장면꾸미기 배경에
원본 자막("하루 자고 간다고 하길래")과 `[광고]`가 그대로 보였다.

**서버는 정상이었다.** `_beatframe_file`은 `_clean` 태그로 청소본에서 뜨고 있었고
그 파일(`5_c1_s8@3.34_clean.jpg`)엔 자막이 없다(실물 확인). 화면에 나간 건
**청소(00:42) 전 23:38에 뽑혀 브라우저에 남아 있던 `_src` 그림**이다.
주소 `/api/produce/mix/beatframe/{job}/{i}?cut={c}`가 청소 전후로 **똑같아서**
이미 그린 `<img>`가 다시 받을 이유가 없었다.

★교훈: 서버 캐시 파일명에는 소스·시각을 넣어 갈라 뒀는데 **주소는 안 갈랐다**.
파일명을 가르면 주소도 갈라야 한다 — 짝이다.
([[reference_iframe_캐시버스터가_옛코드를_물린다]]와 같은 모양)

★"자막제거 안 됐다" 제보 판정 순서:
1. `beatframes/` 파일 태그를 봐라 — `_src`면 서버 문제, `_clean`이면 **브라우저 캐시**다.
2. 그 `_clean` 파일을 실제로 열어봐라(자막이 있으면 청소 자체가 실패).
3. 서버 함수 직접 호출: `A._clean_frame_src(job, work, i, cut=c)` → `(map, cvp, ratio, tag, fresh)`.

수정(main `25b04e3d5`): `_frame_cache_key`(청소 출처·mtime 해시)를
`beats_preview`가 `fkey`로 내려주고 `_beatFrameUrl`이 `?v=`로 붙인다.
라이브 실측: fkey=`336992057fef`, `5?cut=1&v=…` → 60,613B(=`_clean`), `_src`(68,374B) 아님.

곁: work_id ≠ job_id. `produce_works`(reference.db)에서 work→job을 먼저 찾아라.
서버엔 `sqlite3` CLI가 없다 → python3으로 열어라.

관련: [[reference_자동저장이_오려낸조각을_지운다]] [[reference_청소본_시간축은_청소시점_편성]]
