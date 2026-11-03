# SHOTLIST — 새 주인공(버텍스 선화 → trace 획) 컷별 그림 목록 (2026-10-29 밤, 아트 디렉터 Fable · 설계만)

사장님 확정 주인공: 남 = `g_m_hope.png`·`g_m_tired.png`(30대 직장인, 흰 셔츠·검정 넥타이) / 여 = `g_f_hope.png`·`g_f_tired.png`(30대, 단발·흰 블라우스).
방식 = 원작 `presets/ink_explainer`(혼자스): 버텍스 흑백 선화 → `tools/trace.py` 펜 획 → 획 순서대로 그려지는 애니 → **(사장님 추가) 선이 다 그려진 뒤 같은 그림의 컬러판이 번지듯 들어온다.**
읽은 것: 14장면 `scene.js`(인물 호출 줄 전부), `ART_GATE_1.md`, 나레이션 `tts_in/s01…s26.txt` 원문, `_lib_p/hq.js`(Layer.line/fill/fills 재생), `_qtools/qkit.js:37 hero()`, `_tools_p6p10/helpers.js:36 heroX()`, 원작 `template/index.html` 75~105행(strokes 그리기), `gen_hero.py`, 주인공 4장 + `c_m_hope.png`(컬러 시험 1장) 직접 봄.

---

## 0. 결론 숫자

- **선화 15장**(이미 있는 4장 + 새로 11장) → 14장면 29컷을 전부 덮는다. 같은 그림을 컷 평균 2회 재사용.
- **컬러판 15장**(선화 1장당 1장, 흑백 원본을 기준그림으로 생성) → 파일은 30개지만 **인물 설계는 15장**.
- 남 7장 / 여 8장. 공감·고통 장면(P1~P5·Q1~Q3·P6)은 남녀를 번갈아 넣는다 — P1 여, P2 남, P3 여, P4 남, P5 남, Q1 여, Q2 남, Q3 여, Q4 남, P6 여, P9 남, P10 여. 한 장면 안에서는 한 사람(장면 중간에 사람이 바뀌면 다른 사람 얘기로 읽힌다).
- 직급 로봇(`rank.*`)·소품(`prop.*`)·손(`hand.*`)은 지금 `_assets` 부품 그대로. **사람만 바꾼다.**
- P7(대리→부장)·P8(해외→한국)은 지금도 사람이 없고 나레이션상 필요 없다(P7 "저도 똑같은 고민" = 말하는 이 = 사장님, 주인공 아님). 선택으로 P7 컷2 단상 왼쪽에 `#7 M_point_hope` 1장을 세워 "회원이 로봇 셋을 본다" 구도를 만들 수 있다(새 그림 0장).

---

## 1. 그림 목록 (선화 15장) — gen_hero.py 에 넣을 영어 문장 그대로

쓰기: `cd INK_hq\_hero_draft && py gen_hero.py <이름> "<설명>" <기준그림.png>` (기준그림을 주면 같은 인물 유지 — 확인됨).
기준그림: 남 = `g_m_hope.png`, 여 = `g_f_hope.png`(둘 다 폰을 들고 있으므로 폰 없는 포즈는 설명에 **"not holding a phone"** 을 반드시 넣는다).
구도 표기: 상반신 = 허리 위(지금 bust.* 와 같은 범위) / 얼굴 CU = 어깨 위.

| # | 이름(파일) | 남/여 | 표정·포즈·손에 든 것 | 구도 | 기준그림 | gen_hero.py 설명(영어, 그대로) | 쓰는 컷 |
|---|---|---|---|---|---|---|---|
| 1 | `g_m_hope` (있음) | 남 | 기대 미소, 두 손으로 폰 들고 내려다봄 | 상반신 | — | (이미 있음) | P2 컷1 보조 없음 → **재사용 없음(기준그림 전용)**. 필요하면 Q2 컷1 대체 |
| 2 | `g_m_tired` (있음) | 남 | 지침, 손을 이마에, 눈 내리깔음 | 상반신 | — | (이미 있음) | P2 컷2, P5 컷2 |
| 3 | `g_f_hope` (있음) | 여 | 기대 미소, 두 손으로 폰 들고 내려다봄 | 상반신 | — | (이미 있음) | P1 컷B, P10 컷3 전반 대체 가능 |
| 4 | `g_f_tired` (있음) | 여 | 지침, 턱을 손에 괴고 시선 아래 | 상반신 | — | (이미 있음) | P3 컷1·컷2, Q1 컷1·컷2 후반, P10 컷1(회색) |
| 5 | `g_f_night_phone` | 여 | 눈 크게 뜨고 입 살짝 벌린 설렘, 폰을 얼굴 가까이 들고 봄(밤, 폰 불빛) | 얼굴 CU(가슴 위) | g_f_hope | `Close-up from the chest up, the woman holding a smartphone close to her face with both hands, eyes wide open and sparkling, mouth slightly open in excitement, looking down at the screen, hair slightly messy as if lying in bed at night.` | P1 컷A |
| 6 | `g_f_laptop_hope` | 여 | 기대 미소, 노트북 앞, 오른손 검지로 트랙패드/화면을 누르려 함 | 상반신(노트북 뚜껑 뒤 포함) | g_f_hope | `The woman sitting at an open laptop seen from the front, not holding a phone, right index finger reaching forward to click, gentle hopeful smile, eyes on the laptop screen, laptop lid drawn in front of her chest.` | P1 컷C, P6 컷2 |
| 7 | `g_m_point_hope` | 남 | 기대 미소, 오른팔을 화면 오른쪽으로 뻗어 가리킴, 왼손 내림 | 상반신 | g_m_hope | `The man standing, not holding a phone, right arm extended to the right side pointing with index finger at something off-frame, left arm relaxed, confident hopeful smile, eyes looking toward the pointing direction.` | P2 컷1, Q4 0~8.8, P9 컷3 0~12.4, (선택) P7 컷2 |
| 8 | `g_f_point_hope` | 여 | 위와 같음(여) | 상반신 | g_f_hope | `The woman standing, not holding a phone, right arm extended to the right side pointing with index finger at something off-frame, left arm relaxed, confident hopeful smile, eyes looking toward the pointing direction.` | Q1 3.6~9.5, Q3 0~7.0, P6 컷3, P10 컷3 |
| 9 | `g_f_frustr_head` | 여 | 좌절, 두 손으로 머리를 감싸고 눈 질끈, 입 꾹 | 상반신 | g_f_hope | `The woman, not holding a phone, both hands gripping her head above the ears, elbows out, eyes squeezed shut, mouth pressed tight in frustration, shoulders raised.` | P3 컷3, Q3 7.0~ |
| 10 | `g_m_laptop_tired` | 남 | 지침, 노트북 앞, 어깨 처짐, 눈 반쯤 감고 화면 봄, 두 손 키보드 | 상반신(노트북 포함) | g_m_hope | `The man sitting at an open laptop seen from the front, not holding a phone, both hands on the keyboard, shoulders slumped, half-closed tired eyes staring at the screen, mouth flat, laptop lid drawn in front of his chest.` | P4 컷1, P5 컷3, Q2 컷2 |
| 11 | `g_m_frustr_head` | 남 | 좌절, 두 손으로 머리 감싸기(#9 남자판) | 상반신 | g_m_hope | `The man, not holding a phone, both hands gripping his head above the ears, elbows out, eyes squeezed shut, mouth pressed tight in frustration, shoulders raised, tie slightly loosened.` | P4 컷3 |
| 12 | `g_m_laptop_hope` | 남 | 기대, 노트북 앞 타이핑, 살짝 미소, 화면 봄 | 상반신(노트북 포함) | g_m_hope | `The man sitting at an open laptop seen from the front, not holding a phone, both hands typing on the keyboard, slight hopeful smile, eyes on the screen, upright posture, laptop lid drawn in front of his chest.` | Q2 컷1 |
| 13 | `g_m_excited` | 남 | 설렘·확신, 양 주먹을 가슴 높이로 쥐고 활짝 웃음, 눈 반짝 | 상반신 | g_m_hope | `The man, not holding a phone, both fists raised to chest height in a small cheer, big open smile with teeth, bright sparkling eyes, eyebrows up, energetic posture.` | Q4 8.8~, P9 12.4~(안도=같은 그림) |
| 14 | `g_f_dream` | 여 | 꿈꾸듯 기대, 턱에 손, 시선 오른쪽 위(하늘), 입꼬리 올림 | 얼굴 CU | g_f_hope | `Close-up of the woman's face and shoulders, not holding a phone, chin resting lightly on her right hand, eyes looking up and to the right dreamily, soft hopeful smile, relaxed eyebrows.` | P6 컷1(sc 큰 클로즈업) |
| 15 | `g_f_excited` | 여 | 설렘·확신, 양손 펴서 가슴 앞, 활짝 웃음(#13 여자판) | 상반신 | g_f_hope | `The woman, not holding a phone, both hands open and raised to chest height with excitement, big open smile with teeth, bright sparkling eyes, eyebrows up, energetic posture.` | P6 컷2 6.6~, P10 컷1 5.0~(컬러 전환), P10 컷3 13.2~ |

생성 뒤 검사(Opus): 15장을 `py render_draft.py` 식 한 장 시트로 모아 **얼굴이 같은 사람인지**(머리 모양·넥타이·블라우스)·폰이 안 든 포즈에 폰이 남았는지·배경 회색 번짐을 본다. 틀린 것만 같은 명령으로 다시 뽑는다(seed 없음 → 한 번 더가 곧 재시도).

---

## 2. 컷별 shot list (장면 · 컷 · 초 · 그림 · 표정 전환 · 흑백→컬러 시점)

초 = 장면 절대시각. 자리(x,y)·sc 는 지금 scene.js 의 인물 값을 그대로 쓴다(통합 방법 §4 — 새 그림의 눈 사이를 그 (x,y)에 맞춘다). 펜 = 획 그리기 시작~끝. 컬러 = 컬러판 페이드인 시작(규칙: **펜 끝 + 0.3초부터 0.6초 동안**, 예외만 적음).

| 장면(나레) | 컷·초 | 그림 | 나레이션 대목 | 펜 | 컬러 | 비고 |
|---|---|---|---|---|---|---|
| P1 (s01) 12s | A 0~3.8 (960,395) sc1.75 | #5 g_f_night_phone | "밤에 쇼츠로 돈 번다는 영상을 봤어요, 가슴이 뛰어서" | 0.35~1.7 | 2.0 | 침대 무대 그대로. 기존 `tired` 지시는 틀렸다 — 나레이션은 설렘이다(ART_GATE ② P1 과 같은 판단) |
| | B 3.8~7.0 (1180,430) sc1.7 | #3 g_f_hope | "눌러 봤더니" 직전, 폰 보며 기대 | 3.85~5.0 | 5.3 | 폰은 그림 속 폰 하나만(큰 폰·가리키는 손 금지, ART_GATE P1 과 같음) |
| | C 7.0~12 (1490,355) sc1.6 | #6 g_f_laptop_hope | "눌러 봤더니, 그 뒤에 할 게 더 많았죠" | 7.05~8.2 | 8.5 | 결제 화면·결론 글씨는 지금 그대로 |
| P2 (s03) 10s | A 0~4.0 (520,322) sc1.6 | #7 g_m_point_hope | "힘들게 만들어서 올렸는데, 어떻던가요" → 999 벽을 가리킴 | 0.3~1.5 | 1.8 | |
| | B 4.0~10 (470,330) sc1.6 | #2 g_m_tired | "새로고침 몇 번이나… 그 밤이 얼마나 길었는지" | 4.3~5.5 | 5.8 | |
| P3 (s04) 9s | 1 0~3.0 (1480,600) sc2.0 | #4 g_f_tired | "달력이 넘어가죠, 한 달 두 달" | 0~1.1 | 1.4 | 시선이 아래-왼쪽(달력 쪽)이라 그대로 맞는다 |
| | 2 3.0~6.0 (1600,369) sc1.7 | #4 g_f_tired (mir:true) | "수익은 그대로예요" 통장 0원 | 3.05~4.0 | 4.3 | 같은 그림 좌우반전 — 포즈 변화 없이 자리만 옮겨도 되지만, 비용 0 이라 그대로 둠 |
| | 3 6.0~9.0 (560,420) sc1.7 | #9 g_f_frustr_head | "언제까지 수익 없이… 그만두고 싶은데 아까워서" | 6.05~7.1 | 7.4 | 결론 글씨 165px 그대로 |
| P4 (s05) 9s | 1 0~3.0 (1560,330) sc1.9 | #10 g_m_laptop_tired | "강의도 들어 보셨을 거예요" 강의 쌓임 | 0~1.2 | 1.5 | ART_GATE 지시(tired)와 일치 |
| | 3 6.0~9.0 (520,420) sc1.7 | #11 g_m_frustr_head | "남은 건 캡컷 실력뿐" | 6.05~7.0 | 7.3 | |
| P5 (s06) 10s | 2 3.5~7.0 (470,340) sc1.6 | #2 g_m_tired | "틱톡 갔다가 인스타 갔다가 구글 렌즈" | 3.55~4.6 | 4.9 | 컷1 은 사람 없음(창문이 시간 경과) 그대로 |
| | 3 7.0~10 (520,290) sc1.55 | #10 g_m_laptop_tired | "겨우 찾았는데 남의 자막이 덮여 있잖아요" | 7.05~8.0 | 8.3 | |
| Q1 (s07+s08) 16s | 1 0~3.6 (470,470) sc1.95 | #4 g_f_tired | "이 네 가지 중 하나예요… 내가 어디 서 있는지" | 0~1.2 | 1.5 | |
| | 1 3.6~5.8 같은 자리 | #8 g_f_point_hope | "첫째, 강의 듣고 직접 만드는 길" 표지판 가리킴 | 정지(이미 그려진 상태로 교체) | 3.6 즉시(컬러 상태로 등장) | 표정 교체 = 그림 교체(0.12 out / 0.15 in, qkit 과 같은 시간) |
| | 2 5.8~9.5 (330,480) sc1.9 | #8 g_f_point_hope | "캡컷으로 한 장면 한 장면… 실력은 늘어요" | 정지 | 5.8 즉시 | |
| | 2 9.5~16 같은 자리 | #4 g_f_tired | "보통은 대여섯 시간, 그 한 편에 지칩니다" | 정지 교체 | 9.5 즉시 | |
| Q2 (s09) 12s | 1 0~6.9 (960,470) sc1.6 | #12 g_m_laptop_hope | "둘째, 반자동… 시간은 확실히 줄죠" | 0~1.3 | 1.6 | 타원 책상 삭제·prop.laptop 은 ART_GATE 지시대로. 새 그림에 노트북이 들어 있으니 `prop.laptop` 은 **빼도 된다**(이중 노트북 금지) |
| | 2 6.9~12 같은 자리 | #10 g_m_laptop_tired | "영상 찾기랑 편집은 여전히 내 손… 반은 노가다" | 정지 교체 | 6.9 즉시 | |
| Q3 (s11) 14s | 0~7.0 (340,519) sc1.7 | #8 g_f_point_hope | "넷째, 클로드죠… 그림은 근사합니다" | 0~1.2 | 1.5 | |
| | 7.0~14 같은 자리 | #9 g_f_frustr_head | "다시 만들어 줘 할 때마다 크레딧이 나가요" | 정지 교체 | 7.0 즉시 | |
| Q4 (s14) 12s | 0~8.8 (300,410) sc2.0 | #7 g_m_point_hope | "필요한 건 두 가지… 시스템 / 노하우" | 0~1.3 | 1.6 | |
| | 8.8~12 같은 자리 | #13 g_m_excited | "이 두 개가 필요했던 겁니다" | 정지 교체 | 8.8 즉시 | |
| P6 (s13) 12s | 1 0~3.6 (700,500) sc3.0→**k 큰 CU** | #14 g_f_dream | "우리가 정말 원하는 건… 말씨름하고 싶은 게 아니잖아요" | 0.05~1.0 | 1.3 | 얼굴 CU 는 그림 자체가 CU 라 sc 는 §4 공식으로 머리 높이 ≈ 700px 에 맞춘다 |
| | 2 3.2~9.55 (400,470) sc1.42 | #6 g_f_laptop_hope → 6.6 #15 g_f_excited | "저 채널 스타일 나도 해 보고 싶다 / 원본만 찾으면 나도 터지는 영상" | 정지 | 3.2 즉시 / 6.6 즉시 | 구름 두 소망 그대로 |
| | 3 9.4~12 (520,400) sc1.6 | #8 g_f_point_hope → 10.4 #15 g_f_excited | "이 두 가지예요… 안 해 보신 분 없으실 겁니다" | 정지 | 즉시 | 결론 190px 그대로 |
| P7 (s15) 18s | (선택) 컷2 6.45~11.7 단상 왼쪽 (200,430) sc1.3 | #7 g_m_point_hope | "대리급… 클로드는 부장급" 로봇 셋을 봄 | 정지 | 즉시 | 사람 없이도 통과 가능. 넣으면 로봇과 겹치지 않게 x ≤ 330 |
| P8 (s16) 14s | 없음 | — | 지구본·폰·시계가 주인공 | | | |
| P9 (s24) 14s | 3 9.9~12.4 (420,430) sc1.6 | #7 g_m_point_hope | "회원님은 이 세팅을 건드릴 필요도 없어요" | 정지 | 즉시 | |
| | 3 12.4~14 같은 자리 | #13 g_m_excited | "설치팩 깔고, 그냥 엔진 돌리시면 됩니다"(안도) | 정지 교체 | 즉시 | |
| P10 (s26) 16s | 1 0~5.0 (520,470) sc1.6 **회색** | #4 g_f_tired | "흑백 티비가 컬러 티비로" — 흑백 시대 | 0.15~1.3 | **없음(회색 유지)** | 선·컬러판 모두 `grayscale(1)`. 컬러판은 1.6 부터 들어오되 회색 상태 |
| | 1 5.0~6.5 같은 자리 | #15 g_f_excited **컬러** | 컬러 TV 전환과 동시 | 정지 교체 | **5.0 에 0.25초 페이드로 컬러**(TV 와 같은 시각) | 이 컷이 영상 전체의 "색이 들어오는" 비유 자체 — 다른 컷보다 전환을 또렷하게(0.25초) |
| | 3 11.2~13.2 (420,440) sc1.6 | #8 g_f_point_hope | "이천이십육년, 정말 대단한 한 해" | 정지 | 즉시 | |
| | 3 13.2~16 같은 자리 | #15 g_f_excited | "그 한가운데에 여러분이 서 계신 거예요" | 정지 교체 | 즉시 | |

표정 ↔ 나레이션 자가검사(ART_GATE ④-7)용 표는 위 표의 (초, 그림, 대목) 열 그대로 보고에 붙이면 된다.

---

## 3. 색 설계 (사장님 "컬러도 입히고")

### 팔레트 — 종이색 `#FBF8F1`(hq.js PAPER) 위에 채도 낮은 4색 + 주황 강조 1
| 역할 | 색 | 어디 |
|---|---|---|
| 살구(피부) | `#F2C9B8` | 얼굴·손 (기존 SKIN #F2B8B0 보다 한 단 연하게 — 종이결 위에서 번진 느낌) |
| 회갈(머리) | `#6E6761` | 남 머리·여 단발 (기존 HAIR #8E877C 보다 어둡게 — 넥타이 검정과 머리가 구분되게) |
| 청회(옷 그림자) | `#C9D4DE` | 흰 셔츠·블라우스의 주름 그림자만. 옷 본체는 **종이색 그대로 비움**(흰 옷 = 칠하지 않는다) |
| 모래(소품·책상) | `#E9DCC6` | 노트북 몸·침대·책 더미 등 인물 그림 안의 소품 |
| 주황(강조) | `#F6A93B` | 기존 ORG 그대로 — 결론 밑줄·화살표·P10 컬러 TV 띠. **인물에는 쓰지 않는다**(강조색이 흩어진다) |
| 잉크 | `#1F1D1A` | 획(기존 INK). 회색 모드 `#8C8A86` |

컬러판 불투명도 0.9, `mix-blend-mode: multiply`(종이결·획이 비친다). 컬러판은 선 **아래**(`Layer.fg`)에 둔다.

### 컬러판 만드는 법(흑백 원본을 기준그림으로)
```
py gen_hero.py c_<이름> "Keep every black line of the reference exactly as it is, same pose, same framing, same size. Add only soft flat watercolor-style coloring with no gradients: skin #F2C9B8, hair #6E6761, white shirt stays white with faint blue-grey #C9D4DE fold shadows only, tie black, laptop or furniture sand #E9DCC6. Pure white background, no new lines, no outlines thicker, no text." g_<이름>.png
```
⚠️ `gen_hero.py` 의 `STYLE` 머리말에 **"NO color, NO grey fill"** 이 박혀 있다 → 컬러판 생성 때는 이 머리말을 빼야 한다. `gen(name, desc, ref, color=True)` 인자 하나 추가해 `color` 면 STYLE 대신 `"Clean Korean webtoon line-art illustration with soft flat coloring, pure white background, single character, no text. "` 을 쓴다(사장님 시험 `c_m_hope.png` 가 나온 걸 보면 이미 우회했을 수 있다 — 코드가 어떻게 바뀌었는지 Opus 가 먼저 본다).

### 컬러판 검사(생성 모델이 선을 옮길 수 있다 — 반드시 잰다)
1. 정합: `ink_bw = (gray(g_x) < 140)`, `ink_c = (gray(c_x) < 140)` → IoU ≥ 0.80 이면 통과. 미달이면 `cv2.findTransformECC`(affine) 로 c_x 를 g_x 에 맞추고 다시 잰다. 그래도 미달 → 다시 생성.
2. 컬러판의 검은 선은 지운다(획 레이어와 이중선 방지): `ink_c` 픽셀을 `cv2.inpaint(…, 3, INPAINT_TELEA)` 로 주변색으로 메움 → `c_<이름>_flat.png`. 화면에 올리는 건 이 flat 판이다.
3. 바탕: 215 이상 → 흰색, 그 다음 흰색(≥ 250) → 알파 0 으로 빼서 PNG 로 저장(종이결이 비치게).
4. 눈으로: 15장 전/후(흑백 위에 flat 판 multiply) 시트 한 장 1000px 로 본다.

---

## 4. 장면 통합 방법 — Opus 가 그대로 따라 할 순서

### 4-1. 획 추출 (`trace.py`)
원작 `C:\Users\TheRose\숏템자료\모션그래픽엔진\presets\ink_explainer\tools\trace.py` 를 `_hero_draft\trace_hero.py` 로 복사해 네 군데만 바꾼다(원작 알고리즘은 그대로: skeletonize → 끝점부터 walk → approxPolyDP 0.8 → 왼쪽 위에서 가까운 획 순서로 이어 붙임).
```
S = 1024                         # 원작 700 → 그림이 1024 라 그대로(축소하면 가는 선이 끊긴다)
names = sys.argv[1:]             # 고정 6개 이름 → 인자로 받음(g_*.png 15개)
g[g >= 215] = 255                # resize 직후: 바탕 정리(원작 assets_pipeline "215 이상 → 흰색")
ink = g < 160                    # 원작 140 → 160(웹툰 선이 가늘어 회색 가장자리까지 잡아야 끊기지 않는다; 10장 중 끊김 많으면 170)
if len(s) < 10: continue         # 원작 6 → 10(점 찌꺼기 제거)
out → "hero_strokes.js", window.HERO_STROKES = { name: {S:1024, paths:[...]} }
```
실행: `cd INK_hq\_hero_draft && py trace_hero.py g_f_night_phone g_f_laptop_hope …`(15개). 출력 한 줄당 `이름 획수 점수`. **획수 150~500 이 정상**(원작 6장이 그 범위). 800 넘으면 머리카락 해칭이 전부 획이 된 것 → 그 그림만 `ink = g < 120` 으로.
획 순서 손질(사람이 그리는 순서): trace 는 왼쪽 위부터 가까운 순이라 머리 → 얼굴 → 몸 순이 대체로 나온다. 결과 미리보기(`_v_*.png` 식 시트)에서 **몸을 먼저 긋고 얼굴로 돌아오는 그림**만 아래 4-3 의 `order:"y"`(획 시작점 y 로 안정 정렬)로 바꾼다.

### 4-2. 자리·크기 — 지금 자산 좌표계에 꽂는 법
지금 인물은 `(x,y) = 두 눈 사이`, `sc 1.7` 이면 머리 높이 160×1.7 ≈ 270px, 상반신 밑 y+330×1.7(ART_GATE R3 주 그림 높이 ≥ 650).
새 그림마다 **눈 사이 픽셀 (ex,ey)** 와 **머리 높이 hpx**(정수리~턱, 1024 기준)를 `hero_anchor.json` 에 적는다(15장 각각 — 그림을 1000px 로 보고 읽는다; 상반신 그림은 대략 ex≈512, ey≈230~300, hpx≈260~300).
배율 `k = sc × 160 / hpx` → 머리 높이가 지금 자산과 같아진다. 1024 그림 전체는 k×1024 ≈ 0.95~1.1 배(sc 1.7)라 상반신이 지금과 같은 범위에 들어온다.
배치: `<g transform="translate(x − ex·k, y − ey·k) scale(k)">`. 얼굴 CU(#5·#14)는 hpx 가 500~600 이라 같은 공식으로 자동으로 작아진다 — P6 컷1 은 sc 3.0 을 그대로 넣으면 머리 ≈ 480px 로 CU 가 된다.
`mir:true`(P3 컷2)는 `scale(−k, k)` + translate 보정.

### 4-3. 그리기 — hq.js 를 고치지 않고 `Layer.line()`/`S.fills` 만 쓴다(판단의 주인 = 새 파일 하나)
새 파일 `_hero_draft\hero_put.js`(template 이 `hq.js`·`assets.js` 다음에 싣는다) 에 **함수 하나** `INKHERO.put(L, name, o)` 를 두고, 지금 세 벌인 인물 호출(`K.hero` P1~P5 / `QK.hero` qkit.js:37 / `heroX` helpers.js:36)을 전부 이걸 부르게 바꾼다(0순위-B: 사람 그리는 판단은 한 곳).
```js
// o = {x, y, sc, s, dur:1.2, mir:false, gray:false, color:"auto"|초|false, stat:false, win:[a,b]}
INKHERO.put = function (L, name, o) {
  const ST = HERO_STROKES[name], A = HERO_ANCHOR[name], k = (o.sc || 1.7) * 160 / A.hpx;
  const tx = o.x - A.ex * k, ty = o.y - A.ey * k;
  const map = (px, py) => [tx + (o.mir ? -1 : 1) * px * k, ty + py * k];       // 획 좌표 → 장면 좌표
  const root = o.win ? L.sub().xf(t => ({ o: (t >= o.win[0] && t < o.win[1]) ? 1 : 0 })) : L.sub();
  // 1) 컬러판: 선 아래(fg), S.fills 로 페이드(hq.js 175행이 opacity 를 돌린다)
  const img = mk("image", { href: `../_hero_draft/c_${name}_flat.png`, x: 0, y: 0, width: 1024, height: 1024,
    transform: `translate(${tx} ${ty}) scale(${o.mir ? -k : k} ${k})`, opacity: 0, style: "mix-blend-mode:multiply" }, root.fg);
  // 2) 획: 길이 비례로 시간을 나눠 line() 에 넘긴다 → 펜이 따라간다(it.pen=true), ease 는 hq 의 eo 그대로
  const paths = ST.paths.map(d => d.replace(/(-?\d+) (-?\d+)/g, (_, X, Y) => map(+X, +Y).map(v => v.toFixed(1)).join(" ")));
  const lens = paths.map(d => { const p = mk("path", { d }); return p.getTotalLength(); }), tot = lens.reduce((a, b) => a + b, 0);
  const s0 = o.s || 0, dur = o.dur || 1.2; let cum = 0, end = s0;
  paths.forEach((d, i) => { const si = s0 + dur * cum / tot, di = Math.max(0.03, dur * lens[i] / tot);
    root.line(d, o.stat ? -99 : si, di, { w: 5, pen: !o.stat }); cum += lens[i]; end = si + di; });
  // 3) 색 들어오는 시점: 기본 = 펜 끝 + 0.3, 0.6초(hq.fill 이 0.3/0.45 인 것과 같은 결)
  const cs = o.color === false ? null : (typeof o.color === "number" ? o.color : (o.stat ? -99 : end + 0.3));
  if (cs !== null) S.fills.push({ el: img, s: cs, dur: o.stat ? 0.01 : 0.6, op: 0.9 });
  if (o.gray) root.g.style.filter = "grayscale(1)";          // P10 컷1: 5.0 에 xf 로 filter 를 지운다
  return { root, end, T: map };
};
```
- 획 굵기 5(자산 W2 와 같은 급; 원작은 2.6/k ≈ 2.5 였지만 1920 화면에서 가늘다). 펜 아이콘은 hq.js 가 `it.pen` 으로 따라간다(173행).
- 그리기 시간 `dur`: 상반신 **1.2초**, 얼굴 CU **1.0초**, Q·P6 이후 "정지 교체"는 `stat:true`(즉시, 컬러 즉시). 원작은 `min(2.4, max(0.95, 길이×0.8))` 이었지만 우리 컷은 3초대라 1.2 고정이 맞다(ART_GATE R1: 펜은 주인공에만).
- 표정 교체(컷 안 at): 두 번 `put` — 앞 그림 `win:[a, at]`, 뒤 그림 `win:[at, b], stat:true`. 겹침 0(ART_GATE C1 과 같다). 페이드 0.12/0.15 가 필요하면 win 대신 qkit 의 xf 식을 그대로 쓴다.
- 종이결 `paper` 필터·회색 모드(`L.gray`)는 root 가 상속한다(hq.js Layer 생성자).
- 컬러판 파일은 `_flat.png`(§3 검사 2·3 을 거친 것)만 쓴다. 원본 `c_*.png` 를 바로 올리면 선이 두 겹이 된다.

### 4-4. 원작 index.html 이 strokes.js 를 그리는 방식(참고 — 4-3 이 같은 원리를 hq.js 어휘로 옮긴 것)
`template/index.html` 82~105행: `STROKES[name]` 의 d 마다 `<path>`, `stroke-dasharray = stroke-dashoffset = 길이+1` 로 숨김 → 누적 길이 `cum` 으로 "지금 몇 번째 획, 그 안 어디까지" 를 구해 dashoffset 을 줄인다 → 펜은 `getPointAtLength(into)` 자리 → **마지막 18%(p 0.82~1) 에 원본 PNG 를 opacity 로 겹쳐 검은 칠을 채운다**. 우리는 그 "원본 겹치기" 자리에 **컬러판**을 넣는 것이고(선 완성 뒤 0.3초), hq.js 는 path 마다 `pathLength:1` 로 이미 같은 dash 방식을 쓰므로 획을 `line()` 에 하나씩 넘기면 된다.

### 4-5. 검사(Opus 가 보고 전에)
1. 15장 획 미리보기 시트(획만, 1000px) — 끊김·찌꺼기·몸부터 그리는 순서.
2. 장면마다 `ART_GATE_1 ④` 8항목 그대로 + **컬러 전환 프레임**: 컬러 시작 −0.1/+0.3/+0.7 초 세 프레임을 뽑아 (선 완성 뒤에 색이 들어오나 / 이중선 없나 / 종이결 비치나) 본다.
3. 피부색 동일(④-5): 15장 flat 판의 얼굴 영역 평균색이 `#F2C9B8` ±12.
4. P10 컷1: 5.0 전 프레임 회색(채도 0) · 5.3 프레임 컬러.

---

## 5. 뒤돌아본 것(정직하게)
- 눈 사이 픽셀 (ex,ey)·머리 높이 hpx 는 **아직 안 쟀다** — 생성 뒤 Opus 가 그림마다 잰다(공식만 적었다).
- 컬러판이 선을 옮길 위험은 §3 검사로 거른다. 통과율은 모른다(시험 1장 `c_m_hope.png` 는 눈으로 선이 맞아 보였지만 IoU 는 안 쟀다).
- 그림 #1(g_m_hope)은 기준그림 전용이라 화면엔 안 나온다. 아깝지만 Q2 컷1(#12)을 #1 로 대체하면 노트북 없이 폰을 보는 게 돼 나레이션("프롬프트로 대본 맡기고")과 어긋나 두지 않았다.
