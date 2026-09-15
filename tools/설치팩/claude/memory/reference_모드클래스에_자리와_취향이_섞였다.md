---
name: reference_모드클래스에_자리와_취향이_섞였다
description: scene_lab의 body.tight에 '글자 접기(취향)'와 '배치·높이·overflow(자리)'가 섞여 있어 [넓게]를 누르면 틀이 무너졌다 — 자리 규칙은 모드 밖으로
metadata:
  type: reference
---

**2026-08-30.** 3단계에서 미리보기가 훅 옆이 아니라 칸들 아래로 떨어지고, 자막 조각이
쏟아지고, 필름이 안 펼쳐지던 세 증상의 뿌리는 하나였다 — `sceneLab:tight='0'`(넓게).

`scene_lab.html`의 `body.tight` 규칙 60여 개에 성격이 다른 둘이 섞여 있었다:
- **취향**: `.tbsay` 한 줄·`.tbsegs` 숨김·`.seg .meta` 숨김·안내문 접기 → 모드로 갈리는 게 맞다
- **자리**: `#topband` 배치·`--pv-w:330px`·밴드 높이·`#topright{overflow:hidden}`·
  `#topzone{overflow-x:auto}`·`#rollbay` flex·`body:not(.tight) #rollbay:empty{min-height:0}`
  → **모드와 무관해야 하는데 같이 묶여 있었다**

그래서 [넓게]가 취향뿐 아니라 **틀까지** 껐다. 다른 단계는 이런 모드 클래스가 없어 멀쩡했다.

**★내가 만든 2차 사고**: 한 번에 전수로 안 걷고 세 번 나눠 배포했다(F25 배치만 →
F26 폭·높이·overflow → F27 필름 자리). **반쪽 상태가 매번 라이브에 올라가** 사장님이
"이상해졌어"를 겪었다. 배치를 옮기면 **그 배치를 버티는 규칙까지 같은 커밋에서** 옮겨라.

**교훈**
- 모드 클래스를 손댈 땐 `body.MODE`와 `body:not(.MODE)` **양쪽을 한 번에 grep**해 전수로 갈라라.
- 한 화면의 '자리'는 한 곳에서만 정한다(0순위-B). 모드는 보이는 글자만 바꾼다.

관련: [[reference_revert가_남긴_localStorage]] · [[reference_main_overflow가_sticky를_죽인다]]
