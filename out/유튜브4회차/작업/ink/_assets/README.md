# 숏클 손그림 자산 라이브러리 (`_assets/assets.js`) — 사용법

아트 디렉터가 그린 원화 43개(35 + ART_GATE_1 소품 8). **장면(P1~P10)은 이 자산을 조립만 한다**(ART_REVIEW.md ⑥, R7 엔진 하나).
검수 시트: `sheet.png`(1600px, 전 자산) · `big_face_hope_front.png` / `big_face_tired_front.png`(960px). 다시 만들기: `py render_sheet.py [자산명…]`.

## 목록 (43)
| 묶음 | 이름 | 개수 |
|---|---|---|
| 주인공 얼굴 | `face.<표정>.<각도>` — 표정 `hope 기대 / tired 지침 / frustr 좌절 / surprise 놀람 / relief 안도 / excited 설렘` × 각도 `front 정면 / tq ¾(화면 왼쪽을 봄) / side 옆(왼쪽)` | 18 |
| 상반신 포즈 | `bust.phone 폰 보기 / bust.laptop 노트북 앞 / bust.point 가리키기 / bust.head 머리 감싸기` (얼굴 포함, 표정·각도는 옵션) | 4 |
| 손 | `hand.press 누르기 / hand.drag 끌기 / hand.thumb 엄지 / hand.point 가리키기(오른쪽)` | 4 |
| 소품 | `prop.phone / prop.laptop / prop.clock 벽시계 / prop.calendar / prop.bankbook 통장 / prop.coin` | 6 |
| 소품 추가(ART_GATE_1, 10-29 저녁) | `prop.car_sedan 아반떼(은회색 세단) / prop.car_sport 포르쉐(빨강 쿠페·속도선) / prop.tv_crt 흑백 브라운관 TV / prop.tv_color 컬러 TV(같은 몸, 컬러 띠) / prop.flipphone 2G 폴더폰(연 상태) / prop.app_edit 편집앱 아이콘(캡컷 자리: 검정 둥근 사각+흰 가위+필름) / prop.monitor 데스크톱 모니터 / prop.globe 지구본` — 원점 바닥 중심·접지 그림자. 폭: 세단 450·쿠페 700(속도선 포함)·TV 400·폴더폰 160·아이콘 232·모니터 480·지구본 320 | 8 |
| 직급(AI 워커 로봇) | `rank.staff 사원(대리)=하이쿠 / rank.manager 과장=소넷 / rank.director 부장(사장)=오푸스·페이블` | 3 |

직급은 라이브 원문(56:30) 그대로 3단계다: "오푸스·페이블 = 부장·사장급 / 소넷 = 과장급 / 하이쿠 = 대리·사원급 … 일하는 노하우가 다르다".
키 220 → 290 → 370, 머리(돔 → 상자 → 넓은 상자), 눈(점 → 둥근 → 뿔테 안경), 장식(명찰 → 넥타이+서류 → 넥타이+수염+배지+안테나 2+팔짱)으로 서열이 한눈에 보인다. 이름표 글자는 장면에서 `text()` 로 붙인다(`INKASSETS.RANK_LABEL`).

## 좌표·기준점·크기
- 얼굴/상반신: **(0,0) = 두 눈 사이**. 머리 폭 ≈ 140, 머리 높이 ≈ 160(y −80~+82), 어깨 y≈140, 상반신 밑 y=330. `box` 필드가 자산의 로컬 범위.
  - R3 "주 그림 높이 ≥ 650px" 를 맞추려면 `bust.*` 는 `sc ≈ 1.7`(얼굴만이면 `sc ≈ 4`).
- 손: (0,0) = 손목 중심, 손가락은 위(+y 아래). `hand.point` 만 오른쪽을 가리킨다. 높이 ≈ 120.
- 소품·직급: **(0,0) = 바닥 중심**(접지점). `ground:true` 면 밑에 접지 그림자 타원(#1F1D1A 10%, 폭×0.9, 높이 24)이 자동으로 깔린다(R8②). 벽시계만 ground 없음(벽에 걸린 것).
- 선 2단(R8①): 외곽 `W1=7`, 디테일 `W2=4`, 잔선 `W3=3`. `sc` 를 주면 선 굵기도 같이 곱해진다.
- 색: `INKASSETS.COLORS` — 피부 #F2B8B0 · 머리 #8E877C · 셔츠 #8EC3E6 · 잉크 #1F1D1A · 주황 #F6A93B (hq.js 와 같은 값).

## API
```js
INKASSETS.list()                              // 자산 이름 43개
INKASSETS.get("face.tired.front", {look:[0,1]})  // {name, box, anchor, ground, items:[{k:"line",d,w,c,z}|{k:"fill",d,c,op,z}]}
INKASSETS.hero({pose:"laptop", expr:"frustr", view:"tq", look:[1,0], tilt:5})  // 상반신 + 표정 + 각도 조립
INKASSETS.toSVG("rank.director", {sc:1.5, paper:true})   // 정적 SVG 문자열(종이결 필터 포함 가능)
INKASSETS.draw(L, "prop.phone", {x:520, y:900, sc:1.4, s:2.0, per:0.12})       // hq.js Layer 에 펜 순서대로 얹기 → {end, n}
```
- `items` 는 **펜이 긋는 순서**로 정렬돼 있다(큰 윤곽 → 피부 채색 → 귀·머리카락 → 코 → 안경 → 눈썹 → 눈 → 입 → 덤). `draw()` 는 외곽선(W1)만 펜을 따라가게(`pen:true`), 디테일은 `pen:false` 로 빨리 긋는다(R1: 펜은 주인공·핵심 소품·손글씨에만).
- `z`: 같은 자산 안의 앞뒤(상반신 몸 −1 / 머리 0 / 앞팔·폰 1~2). `toSVG`·`draw` 가 z 순으로 그린다.
- **표정 바꾸기**: 장면에서 표정 전환(R2 컷당 1회)은 `face` 를 두 번 만들어 `vis(a,b,"fade")` 로 갈아 끼운다. 머리 윤곽·안경은 두 벌이 같으니, 비용을 아끼려면 `get("face.hope.front").items` 에서 눈썹 이후(인덱스는 자산마다 다르므로 `items.findIndex(i => i.w === 5)` 부터)만 두 번째 레이어에 올린다. 표정 묶음(눈썹+눈꺼풀+입+덤)이 **한 번에** 바뀌는 것이 R2 의 뜻이다 — 입만 바꾸지 마라.
- `look:[x,y]` (−1~1) 로 눈동자 방향. 포즈가 기본 look 을 준다(폰 보기=아래, 가리키기=오른쪽).
- `tilt`(도) 로 머리 기울임. 포즈 기본값: phone 6 / head 5 / point −4.

## hq.js 에 붙이기 (Sonnet 작업)
```html
<script src="../_lib_p/hq.js"></script><script src="../_assets/assets.js"></script>
```
```js
const c1 = S.layer().vis(-1, 6.6, "slide");
INKASSETS.draw(c1, INKASSETS.hero({pose:"phone", expr:"tired", view:"front"}), {x:960, y:430, sc:1.7, s:0.6});
INKASSETS.draw(c1, "rank.manager", {x:760, y:1000, sc:1.6, s:0.6});
```
`draw` 는 Layer 의 `line(d,s,dur,{w,c,pen})` · `fill(d,col,s,op,dur)` 만 쓴다. `person()`·`robot()`·`_lib/hero.js` 는 더 쓰지 않는다.

## 검수(스스로 돌린 것)
1차 시트 → 얼굴이 길쭉한 달걀이고 턱주름 선이 머리 밖에 떠 있었음·기대 입이 두 줄로 어색·손 4종이 벙어리장갑·노트북 뚜껑이 납작함 → 고쳐서 2차 시트(현재 `sheet.png`). 3차: ¾ 얼굴 팔자주름이 입과 겹쳐 오른쪽으로 옮김.
