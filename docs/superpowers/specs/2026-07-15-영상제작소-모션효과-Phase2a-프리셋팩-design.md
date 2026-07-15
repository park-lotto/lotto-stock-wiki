# 영상제작소 모션효과 — Phase 2a 프리셋 팩 설계

날짜: 2026-07-15
선행: [Phase 1 뼈대 설계](2026-07-15-영상제작소-모션효과-뼈대-design.md) (완료·배포됨)
관련 코드: [video_assemble.py](../../../shopping_shorts/video_assemble.py) · [mix_pipeline.py](../../../shopping_shorts/mix_pipeline.py) · [motion_assets.py](../../../shopping_shorts/motion_assets.py) · [produce.html](../../../shopping_shorts/static/produce.html)
메모리: [[feedback_whole_branch_review_catches_seams]] [[feedback_동시세션_커밋규칙]] [[feedback_remotion_reference_rule]]

## 목표

Phase 1이 만든 "타임드 투명 레이어" 뼈대 위에 **프리셋 팩 3~4종**을 얹어,
사용자가 꾸미기에서 **카드 하나만 누르면 모션까지 완성**되게 한다.

팩 = `{전환 + 스티커 + 텍스트 모션 + 색감}` 한 세트.
텍스트 모션은 **기존 자막·헤드카피에 입히는 효과**이지 새 텍스트 생성이 아니다(④ 참조).

## Phase 2 분해 (이 스펙의 위치)

Phase 2가 한 스펙에 담기엔 커서 둘로 쪼갠다.

| | 범위 | 상태 |
|---|---|---|
| **Phase 2a** (이 스펙) | 팩 스키마·자동배치 엔진·자산·꾸미기 UI | 지금 |
| **Phase 2b** | 상시 모션 분석기(레퍼런스 영상 → 패턴 DB → 팩 자동갱신) · Remotion `render:overlay` 실 키네틱 타이포 | 다음 |

**순서 근거**: 분석기를 먼저 만들면 패턴이 내려앉을 "팩" 그릇이 없어 결과가 갈 곳이 없고,
팩 스키마가 안 굳은 채로 분석 결과 스키마까지 흔들린다. 그릇 먼저, 자동갱신 나중.

## 확정된 결정 (브레인스토밍)

1. **팩은 완성스타일에 내장** — 별도 선택지를 만들지 않는다. `FULL_PRESETS`(18종) 각 항목이 팩을 참조해
   카드 하나 = 글씨 + 모션 딸깍. 피팅룸 철학("최적 하나 기본, 세부는 감추기") 유지. 팩만 따로 바꾸는 건 고급.
2. **자동배치 강도 자체가 팩 정체성** — 다이나믹팝=모든 경계+스티커 多 / 미니멀시크=훅·클라이맥스만.
   팩 선택 = 곡 템포 선택.
3. **키네틱 타이포는 Phase 2a에서 drawtext로** — 프리렌더 `.mov`는 텍스트를 못 담고,
   Remotion 런타임 렌더는 서버 RAM 제약(아래) 때문에 위험. 기존 자막 drawtext·effect를 재사용한다.
   진짜 Remotion 키네틱은 Phase 2b.
4. **팩 값의 근거 = 우리 레퍼런스 랭킹 DB** — 이 스펙은 스키마·엔진만 확정하고,
   실제 팩 3~4종의 값은 구현 Task 1에서 랭킹 상위 영상 분석 결과로 채운다(지어내지 않는다).

## 핵심 설계: 레이어는 저장이 아니라 렌더 시점 생성

비트 경계 시각은 **TTS 실길이가 확정되는 렌더 때** 정해진다
(`_burn_captions`가 `_probe_duration(tts_paths[i])`를 누적해 `t0` 계산 — video_assemble.py:575-583).

따라서:
- `deco.motion`에는 **`pack_id`만 저장**한다.
- 구체 레이어(asset_id·start·dur)는 `run_render`에서 **그때 계산**한다.

저장 시점에 레이어를 박으면 대본·TTS가 바뀔 때마다 전환이 어긋난다.

```
deco.motion = { "pack_id": "dynamic_pop" }        # 저장은 이것뿐
                    │
     run_render ────┼──▶ _beat_timeline(edit_plan, tts_paths)   # 경계 계산
                    │         │
                    └──▶ motion_packs.build_layers(pack, timeline)
                              │  → layers[] + color_filter + timed_texts[]
                              ▼
                    motion_assets.resolve_layers(layers)  # asset_id → _abspath (기존)
                              ▼
                    assemble(... deco=...) → _burn_captions  # 기존 합성 경로 (무변경)
```

기존 `deco.motion.layers`(수동 레이어)도 계속 지원한다: `pack_id`가 없고 `layers`만 있으면 그대로 쓴다.
둘 다 있으면 팩이 생성한 레이어 뒤에 수동 레이어를 이어붙인다.

## 컴포넌트

### ① `_beat_timeline()` 추출 (video_assemble.py) — 중복 금지가 핵심

현재 비트 경계 `t0` 누적은 `_burn_captions` 내부에 인라인돼 있다.
이를 순수 헬퍼로 뽑아 **자막과 모션이 같은 타임라인을 공유**하게 한다.

```python
def _beat_timeline(edit_plan, tts_paths) -> list[dict]:
    """[{beat_idx, t0, dur, narration, role}, ...] — 자막·모션 공통 타임라인."""
```

- `_burn_captions`는 자기 인라인 계산을 이 헬퍼 호출로 교체한다(동작 동일).
- `mix_pipeline.run_render`도 같은 헬퍼를 쓴다.
- **여기서 중복 구현하면 전환이 자막과 밀리는 버그가 반드시 난다.** 동치성 테스트로 못박는다.

### ② `motion_packs.py` (신규, 순수 Python)

```python
def load_packs(assets_dir=DEFAULT_ASSETS_DIR) -> dict   # {pack_id: pack}
def build_plan(pack, timeline) -> dict
    # → {"layers": [...],            # 전환·스티커 (motion_assets.resolve_layers 입력형)
    #    "color_filter": str|None,
    #    "caption_effect": str|None, # ④-1
    #    "headcopy_enable": str|None}# ④-2 (ffmpeg enable 식 또는 None=전체)
```

- ffmpeg·Node·DB 의존 0 → **단위 테스트가 쉽다**(이 설계의 검증 가능성이 여기 달림).
- `motion_assets.py`(자산 해석)와 역할 분리: 이쪽은 **정책 → 계획**, 저쪽은 **레이어 → 실경로**.

**배치 정책** (전환·스티커 공용)

| policy | 배치 |
|---|---|
| `every_beat` | 모든 비트 경계(첫 비트 시작 제외) |
| `hook_climax` | 첫 경계 + 마지막 경계만 |
| `none` | 없음 |

- **전환**: 경계마다 `start = t0_boundary - lead`(0 아래로 clamp), `dur = transition.dur`.
- **스티커**: 해당 비트 **시작**에 `start = t0_beat`, `dur = sticker.dur`. 위치는 manifest의 `default` 배치를 따른다.

### ③ 팩 스키마 — `assets/motion/packs.json` (git 추적)

```json
{
  "packs": [
    {
      "id": "dynamic_pop",
      "name": "다이나믹 팝",
      "intensity": "high",
      "transition": {"asset_id": "swipe_left", "dur": 0.5, "lead": 0.25, "policy": "every_beat"},
      "sticker":    {"asset_id": "sparkle", "policy": "hook_climax", "dur": 1.0},
      "caption":    {"effect": "pop"},
      "headcopy":   {"policy": "hook_only"},
      "color_filter": "eq=saturation=1.15:contrast=1.05"
    }
  ]
}
```

- `manifest.json`(자산 카탈로그)과 **별도 파일**로 둔다: 자산은 빌드 산출물, 팩은 큐레이션 — 수명주기가 다르다.
- 팩이 참조하는 `asset_id`는 manifest에 있어야 한다. 없으면 그 레이어만 skip(아래 에러 처리).

### ④ 팩이 규정하는 텍스트 모션 (drawtext 재사용)

**팩은 텍스트 내용을 만들지 않는다.** 이미 사용자가 넣은 텍스트(자막·헤드카피)에 **모션만 입힌다.**
(내용을 지어내면 대본과 겉돈다. 실제 키네틱 타이포 신규 텍스트는 Phase 2b의 Remotion 몫.)

팩이 규정하는 것은 둘뿐:

1. **자막 effect** — 기존 `caption_style.effect`(`fade|pop|slide|none`)를 팩 값으로 덮는다.
   구현 신규 없음(자막 drawtext가 이미 지원).
2. **헤드카피 노출 정책** — 현재 헤드카피는 `enable` 없이 **영상 전체 고정**이다(video_assemble.py:584-585).
   팩이 `headcopy.policy`로 이를 규정한다.

   | policy | 헤드카피 |
   |---|---|
   | `always` | 전체 표시 (= 현재 동작, 기본값) |
   | `hook_only` | 훅 비트 구간(`timeline[0]`)에만 표시 |

   `hook_only`는 헤드카피 drawtext에 `enable='between(t,0,t0_1)'`을 붙이면 된다.
   effect도 자막과 같은 구현을 재사용한다.

- `deco.motion.pack_id`가 없으면 두 값 모두 손대지 않는다 → **완전 하위호환**.
- 사용자가 고급에서 직접 고른 자막 effect가 있으면 그쪽이 우선한다(팩은 기본값 제공자).

**범위 밖(YAGNI)**: `deco.extra_texts`의 타임드 확장은 이번에 하지 않는다.
자동 배치할 텍스트 원천이 없어 지금은 쓰일 데가 없다 — 필요해지면 Phase 2b에서.

### ⑤ 색감 필터 순서 수정 (Phase 1 동작 변경 — 회귀 주의)

현재 `color_filter`는 base vf 문자열 **맨 끝**(자막·헤드카피 drawtext 뒤)에 붙어
**색보정이 자막에까지 걸린다**(video_assemble.py:620, 626-627).

팩 색감은 소스 영상에만 걸려야 하므로 **drawtext 앞**으로 옮긴다.

이건 Phase 1이 육안검증한 동작을 바꾸는 것이라 **실렌더 육안 재검증이 필수**다.
(자막 색이 팩 색감에 물들지 않는지 = 이 변경의 성공 정의)

### ⑥ 배선 (mix_pipeline.run_render)

`resolve_layers` 호출 직전(mix_pipeline.py:225-228)에 팩 확장을 끼운다.

```
pack_id = deco.motion.pack_id
if pack_id and pack_id in packs:
    timeline = _beat_timeline(plan, tts_paths)
    p = build_plan(packs[pack_id], timeline)
    deco.motion.layers       = p["layers"] + (기존 수동 layers)
    deco.motion.color_filter = deco.motion.color_filter or p["color_filter"]   # 사용자 지정 우선
    caption_style.effect     = caption_style.effect or p["caption_effect"]     # 사용자 지정 우선
    deco.motion._headcopy_enable = p["headcopy_enable"]   # _burn_captions가 헤드카피 drawtext에 부착
```

`_headcopy_enable`은 팩이 계산해 넘기는 **렌더 전용 파생값**이다(DB에 저장하지 않는다 —
저장하는 건 `pack_id`뿐이라는 핵심 설계와 일관).

### ⑦ UI (produce.html) — 신규 엔드포인트 없음

- `FULL_PRESETS[i]`에 `motion: "<pack_id>"` 필드 추가(없으면 모션 없음 = 하위호환).
- `applyFullPreset(i)`가 `STATE.deco.motion = {pack_id}` 세팅.
- 저장은 기존 `saveHeadcopy()` → `POST /api/produce/mix/settings`(body에 `deco` 이미 포함) **그대로 재사용**.
- 고급("세부 직접 다듬기") 접기 안에 팩 교체 셀렉트 + "모션 끄기".

### ⑧ 자산 (motion/ Remotion)

팩이 요구하는 전환·스티커 컴포지션을 추가하고 `render:library`의 `LIB` 배열에 등록한다.
출력은 Phase 1이 확정한 **qtrle .mov(argb)** 유지 — VP9 알파 webm 금지(디코더가 알파를 죽임).

## 에러 처리

- `pack_id`가 packs.json에 없음 → 모션 skip, 렌더 계속(로그 경고).
- 팩이 참조한 `asset_id`가 manifest/실물에 없음 → 기존 `resolve_layers`가 조용히 skip.
- `timeline`이 비었거나 비트 1개 → 전환 없음(경계 없음). 스티커는 가능.
- **폰트 미해결 조기 return 함정**: `_burn_captions`(video_assemble.py:570-572)는 폰트 실패 시 원본을 복사하고
  return하므로 **모션·색감·오버레이·BGM이 통째로 스킵**된다. 이 경로에 경고 로그를 추가한다(동작은 유지).
- ffmpeg 실패 → 기존 `run_render` try/except가 status='failed'로 잡음(무변경).

## 테스트

- **`build_plan` 단위**: policy별 레이어 수·start/dur 계산·clamp·빈 타임라인·`headcopy_enable` 식.
- **`load_packs` 단위**: 파일 부재 → `{}`, 미존재 asset_id 참조.
- **타임라인 동치성**: `_beat_timeline`이 뽑아내는 `t0`가 리팩터 전 `_burn_captions`의 자막 `t0`와
  **동일함을 증명**(전환-자막 어긋남 방지의 핵심 가드).
- **하위호환**: `pack_id` 없는 기존 deco / `start` 없는 기존 extra_texts가 그대로 동작.
- **실렌더 육안 grounding (완료 정의)**: 격리 테스트 말고 **실제 payload 경로**로
  팩 선택 → run_render → 최종 mp4에서 ① 전환이 비트 경계에 맞는지 ② 자막이 색감에 물들지 않는지 육안 확인.
  ([[feedback_whole_branch_review_catches_seams]])

## 서버 제약 (설계 근거)

라이브 서버(Lightsail 3.39.179.148) 실측: **Node v22.22.2 · google-chrome/chromium 설치됨**,
그러나 **RAM 총 1.9GB / 가용 830MB**. 헤드리스 크롬 런타임 렌더는 위험
(2026-07-12 재인코딩 concat이 서버를 죽인 전력과 같은 계열의 리스크).
→ Phase 2a는 **런타임 Node 의존 0** 유지. Remotion은 빌드타임 자산 생성기로만.

## 범위 밖

- 상시 모션 분석기(Phase 2b) — 레퍼런스 랭킹 영상 Gemini 모션분석 → 패턴 DB → 팩 자동갱신.
  선례: 대본위키 `element_category_stats` + 일일배치 클러스터링과 같은 모양이라 그 패턴을 재사용할 것.
- Remotion `render:overlay` 실구현(`motion_text.render_text_overlay` 스텁 채우기) — Phase 2b.
- 색감 프리셋 세부 튜닝 · JP/EN.

## 동시세션 주의

`produce.html`은 **"영상제작소 대본·영상믹스 통합" 트랙이 동시 편집 중**(SDD 원장 기준 Task3 프론트·4·5 미완).
영역은 다르지만(대본 모달 vs 꾸미기) 같은 파일이다.
커밋 규칙: `git add -A` 금지 · 내 hunk만 격리(`git apply --cached`) · main 고정 · 커밋 후 HEAD에 내 변경 확인.
