---
name: reference-buffer-youtube-type-field
description: Buffer 유튜브 예약 실패 뿌리 — YoutubePostMetadataInput에 type 칸이 없다. SNS별 metadata는 스키마 introspection으로 확인하라
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4132c8ff-2b02-4536-8e2a-3f391b6f0c7e
  modified: 2026-09-02T02:30:51.683Z
---

Buffer 예약발행에서 **유튜브만 100% 실패**했다. 뿌리는 `shopping_shorts/buffer_api.py`가
`{"youtube": {"type": "short", ...}}`를 보낸 것 — **YoutubePostMetadataInput에는 type이 없다**.
GraphQL 검증 단계에서 죽어 라이브 로그 6회(2026-09-01~09-02) 전부 같은 문구였다:
`Field "type" is not defined by type "YoutubePostMetadataInput"`.

`type`은 **인스타에만 있는 축**인데 인스타 코드를 보고 유튜브에도 따라 적어서 난 사고다.

**실측(introspection) — SNS마다 칸이 전혀 다르다**
- YoutubePostMetadataInput(8): categoryId · title · privacy · embeddable · isAiGenerated ·
  license · madeForKids · notifySubscribers  → **title 없으면 거절**(실질 필수)
- InstagramPostMetadataInput: type(필수) · shouldShareToFeed(필수) · firstComment · link 등
- **TiktokPostMetadataInput은 존재하지 않는다** → 틱톡엔 metadata를 안 붙이는 게 정답
- 인스타 **개인 프로필** 계정은 Buffer가 아예 거절한다("personal profile channels require
  notification scheduling") — 코드 문제가 아니라 계정 종류 문제다. 프로페셔널로 전환해야 한다.

**How to apply**
- SNS metadata를 손댈 땐 짐작하지 말고 introspection으로 칸을 뽑아라:
  `query($n:String!){ __type(name:$n){ inputFields{ name type{ kind name ofType{name enumValues{name}} } } } }`
- 게시하지 않고 모양만 검증하는 법: **존재하지 않는 channelId**로 createPost를 보낸다.
  모양이 틀리면 스키마 오류, 맞으면 "Channel not found"까지 간다(실제 게시 없음).
- 한 SNS의 metadata를 다른 SNS에 복사하지 마라 — 공통 칸이 거의 없다. [[reference_prompt_says_but_nobody_checks]]
