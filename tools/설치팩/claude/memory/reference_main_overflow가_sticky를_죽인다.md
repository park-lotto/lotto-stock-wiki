---
name: main_overflow가_sticky를_죽인다
description: 숏템메이커 페이지들의 .main{overflow:auto}가 position:sticky를 조용히 무력화한다 — 미리보기가 안 따라오면 이것부터 의심하라
metadata:
  type: reference
---

2026-08-27, 제작소(produce.html) 썸네일 미리보기를 스크롤에 따라오게(사장님 "엘리베이터같이")
만들다 발견. **`.previewSlot`(sticky)이 이 페이지에서 처음부터 죽어 있었다.**

## 원리
```
position:sticky는 **가장 가까운 스크롤 조상**을 기준으로 붙는다.
.main{overflow:auto}가 있으면 그 자리를 .main이 차지한다.
그런데 .main은 높이 제한이 없어 **실제로는 스크롤되지 않는다**
  (실측: main.scrollHeight == main.clientHeight == 2756).
→ 기준은 잡혔는데 그 기준이 안 움직이니 sticky가 아무 일도 안 한다.
   에러도 경고도 없다. 그냥 조용히 안 붙는다.
```

produce.html의 `.previewSlot` **3곳이 전부 무력**이었다: 0단계 꾸미기 미러 ·
4단계 믹스 미리보기 · 7단계 썸네일. 주석엔 "sticky·상단고정 규약을 공유한다"고
적혀 있었지만 아무도 실제로 확인한 적이 없다([[reference_prompt_says_but_nobody_checks]]).

## 고치는 법
```css
/* 전 */ .main{flex:1;padding:24px 32px;overflow:auto}
/* 후 */ .main{flex:1;min-width:0;padding:24px 32px}
```
`min-width:0`은 admin.html이 이미 쓰는 패턴 — flex 자식이 내용 최소폭 때문에 사이드바를
밀지 않게 막는다(overflow 대신 가로 넘침을 방어). 실측: 가로 스크롤 안 생김.

## ⚠️ 같은 함정이 남아 있는 페이지
`collection · discover · find · index · library · outreach · scene_library · produce_intro`
전부 `.main{flex:1;...;overflow:auto}`다. **거기에 sticky를 붙이면 같은 함정을 밟는다.**
(produce.html만 고쳤다 — 내 트랙 범위 밖은 건드리지 않았다)

## 진단 순서 (sticky가 안 먹을 때)
```
1. getComputedStyle(el).position === 'sticky' 인가  ← 여기까진 대개 정상이라 속는다
2. 조상 중 overflow가 visible이 아닌 곳을 전부 찾는다
3. ★그 조상의 scrollHeight == clientHeight 인가 → 같으면 그건 스크롤 컨테이너가 아니다.
   이 한 줄이 진짜 원인을 가리킨다.
4. 부모 높이 == sticky 요소 높이면 붙을 여지가 없다(align-self:flex-start 필요)
```

## 내가 두 번 틀린 측정 (같은 실수 반복 금지)
- **`window.scrollTo`로 쟀는데 실제 스크롤 컨테이너가 다를 수 있다.** window로 재서
  "특정 위치에선 붙는다"는 **가짜 성공**을 봤다. 스크롤 컨테이너를 먼저 확정하고 재라.
- sticky는 **제 부모 안에서만** 산다. 부모(flex 줄)가 끝나면 따라 올라간다 →
  "위쪽까지 따라오게" 하려면 그 요소를 **같은 부모 안으로 옮겨야** 한다.

관련: [[feedback_mockup_is_source_of_truth]] · [[reference_아이콘은_확대해_눈으로_봐라]]
