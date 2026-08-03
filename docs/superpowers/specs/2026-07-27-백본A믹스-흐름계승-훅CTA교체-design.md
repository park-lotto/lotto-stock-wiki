# 백본-A 믹스: 흐름 계승 + Replace/Insert + 훅/CTA 장면교체 — 설계 (레버2)

- 날짜: 2026-07-27
- 트랙: 대본프롬프트단순화
- 선행: 2026-07-26-대본프롬프트-단순화(레버1, 배포됨 dcdea5045)

## 배경 / 문제

레버1(프롬프트 단순화)로 "제약 과적재"는 제거·배포됨. 하지만 사장님 통찰:
**"대본을 쓰면서 장면을 동시에 맞추려니 이상하다"** = 레버2.

조사 결과(실측):
- 스마트믹스(백본) **항상 켜져 있음** — 그런데도 이상함.
- 원인: 백본이 **"장면 순서(order_block)"만** 주고, **A 대본의 스토리 흐름은 안 넘김**
  (`backbone.py:272 backbone_flow` = seg_id·action·scene_desc·seconds만, **대사 없음**).
  → 내레이터가 A 순서는 따라도 **딴 이야기를 자유창작** → 겉돎.
- 전용 2단계 생성기 `generate_backbone_script`는 만들어졌으나 **미배선**.

## 결정: A안 (흐름 계승 — 최소 변경, 기존 rich 경로 유지)

완전 2단계(B안) 대신, **지금 라이브 rich 경로(_scene_first_candidates)에 "A 흐름"을 강하게
주입**해 자유창작을 A 흐름 변형으로 바꾼다. 스키마·다운스트림·A/B/C 3후보 무변경.
B안(2단계)은 A안이 부족할 때 escalate(A안의 흐름추출을 재사용).

## 요구사항 (사장님 확정)

1. **흐름 계승**: A 백본의 **장면 순서 + 대본 스토리 흐름**을 함께 따라간다.
2. **창의적 변형**: 흐름을 따르되 **베끼지 않는다** — 우리 말로 새로(패러프레이즈).
3. **장면 안 뒤죽박죽**: A 순서를 지켜 컷이 엉키지 않는다.
4. **Replace/Insert를 LLM에 명시 지시**(현재는 후처리만):
   - Replace: A의 컷보다 B/C에 같은 의미의 더 직관적·자극적 컷이 있으면 교체 + 그 동작을 대사에 반영.
   - Insert: A에 없는 새 정보·리액션(주변인 반응·인증 등)이 B/C에 있으면 삽입 + 접착어로 연결.
   - 기존 후처리(`pick_clips_for_action`·`ensure_sources_used`·`dedup_and_balance`)는 안전망 유지.
5. **은행 parts_block ON (창의적 우수 라인)**: 승인 훅·부사·어미·CTA 라인을 **참고·변형** 재료로.
   ★"거의 그대로"가 아니라 "이 표현 감각을 참고해 우리 소재·A흐름에 맞게 변형".
   - OFF 유지: `avoid_block`(드리프트 주범)·`winners_block`(타제품 오염)·`spine_charter`(A흐름이 대신).
6. **훅 장면 = 비-A 소스 최고장면 (아주 중요)**: 첫 컷 시각은 A 것 대신 **나머지 소스(B/C)에서
   가장 강렬한 장면**. 영상 차별화. 대사 훅은 그 장면에 얹는다.
7. **CTA 장면 = 중간 소스 클립으로 교체**: 원본 엔딩엔 원작자 수정(자체 CTA·워터마크)이 많음
   → 마지막 CTA 컷은 **중간 위치 소스 클립 중 하나**로.

### 세 재료가 안 싸우는 구조
| 재료 | 역할 |
|---|---|
| A 백본 흐름(순서+대사 gist) | 스토리 전개·순서 (창의 변형, 베끼기 X) |
| 은행 parts_block | 창의적 훅·표현 양념 (참고·변형) |
| 제품·특장점 | 중심 앵커 (벗어나지 마라) |
| Replace/Insert (B/C 컷) | 시각·정보 강화 + 영상 차별화 |

## 구현 지점 (확정·구현 완료)

- (1) **A 흐름+대사 gist**: `backbone.backbone_flow`에 `text` 필드 추가(원본 자막/대사, 60자).
- (2) **order_block = A 흐름 계승 + Replace/Insert 지시**: `edit_plan._backbone_order_block`
  헤더 "백본 흐름", 각 줄에 `(원본대사: …)`, "창의적 변형·순서계승·베끼기 금지" + Replace/Insert 지시문.
- (3) **은행 parts 재주입**: `edit_plan._scene_first_candidates` 프롬프트 끝에 `bank_context`를
  "참고·변형 양념" 프레이밍으로 재부착 + `mix_pipeline`(628) `assemble_bank_context`→`parts_block`만,
  `avoid_hooks=None`(novelty OFF).
- (4) **훅/CTA 장면교체**: `backbone.swap_hook_cta_for_differentiation`(+`_middle_source_clip`) 신규,
  `edit_plan.build_scene_first_plan` ping_pong 후처리 **마지막**에 배선(dedup_clips_global 뒤).
  훅=비-A `_visual_segs_of` 최고, CTA=`_middle_source_clip`(첫·끝 제외). narration 불변(화면만).

## 검증 결과 (구현 후)
- 문법·import OK / order_block·swap·통합 프롬프트 렌더 육안 확인 OK(프롬프트 2,353자).
- pytest 서브셋: **신규 실패 0**, 352 passed. 남은 4건은 베이스라인(mix_pipeline ffmpeg/mock, stash 확인).
- 갱신 테스트: bank 재주입(test_mix_bank_wiring)·avoid OFF(test_novelty_memory)·헤더 개명(backbone_base).

## 범위 밖 (YAGNI / "복잡한거 말고")
- 완전 2단계(B안), 전용 `generate_backbone_script` 배선, 스키마 변경, mix_type 라벨 UI,
  A/B/C 3후보 구조 변경 — 하지 않음.

## 검증
- 문법·import + 관련 pytest(scene_first·backbone·mix·bank, "실패 안 늘었나").
- 실제 렌더로 프롬프트 육안 확인(A 흐름·Replace/Insert·훅/CTA 규칙·은행 parts 반영).
- 게이트 통과 시 배포 → 라이브 A/B/C로 사장님 육안 검증.
