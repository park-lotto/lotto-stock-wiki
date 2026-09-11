---
name: reference-empty-screen-may-be-zero-data
description: "화면에 아무것도 안 뜬다" 제보 = 코드 아니라 데이터 0건일 수 있다. 확인 순서와 랭킹 데이터 실제 저장 위치
metadata:
  type: reference
---

**"아무것도 안 떠" 제보를 코드 버그로 먼저 의심하지 마라.** 2026-08-30 실사고:
네이버클립 탭이 비어 보였는데 원인은 **수집 버튼이 한 번도 안 눌린 것**이었다.
서버 로그가 그대로 말해줬다 — `GET /api/reference?platform=naverclip 200`(탭은 열림)
는 있는데 `POST /api/naverclip/collect`는 내 테스트 1건(401)뿐이었다.

**확인 순서**

```
① 호출 기록부터: sudo journalctl -u shopping-shorts --since '2 hours ago' | grep <플랫폼>
   → 수집 POST가 실제로 있었나. 없으면 데이터 0건이 정상 동작이다.
② 저장 위치를 직접 본다(아래).
③ 화면 기본 탭이 '48시간 히트작'이다 — 최근 몇 달치를 담으면 대부분 필터에 걸려
   안 보인다. '역대 히트작'으로 바꿔야 다 보인다.
④ 프로세스가 옛 코드일 수 있다: auto_deploy는 **고객 접속 중이면 재시작을 미룬다**
   (MAX_DEFER_SEC=1800). 디스크 코드 ≠ 도는 코드.
   systemctl show shopping-shorts -p ActiveEnterTimestamp 로 기동시각 확인.
```

**★랭킹 수집분의 실제 저장 위치** (헤매기 쉬움):
`shopping_shorts/data/reference.db`(app.db 아님)의 **`settings` 테이블**,
key = `last_run::<platform>` 에 JSON `{items, collected_at}`.
`last_run` 테이블이 아니다 — 거긴 인스타 전용 `id=1` 한 줄뿐이고 platform 컬럼도 없다.
`platform_snapshots`에도 안 들어간다.

```
select key from settings where key like 'last_run::%'
→ instagram·youtube·pinterest·naverclip·threads·tiktok·xiaohongshu·douyin
```

관련: [[project_네이버클립_수집축]] · [[reference_deploy_truth_branch_ssh]] ·
[[reference_핸드오프_없다는말_직접확인]]
