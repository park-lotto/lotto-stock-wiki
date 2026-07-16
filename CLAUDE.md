# 로또의 주식 — 나만의 지식 위키

---

## 🚀 세션 시작 시 필수 읽기

새 세션이 시작되면 아래 파일을 **순서대로** 반드시 읽어라.

```
0. handoff/{내 트랙}.md                        → ⚡ 최우선. 내 트랙 미완료 작업 파악
   (트랙을 못 정했으면 NEXT_SESSION.md = 트랙 목록 → 사용자에게 어느 트랙인지 확인)
1. wiki/BRAIN_INDEX.md                        → 6레이어 분석 프레임워크
2. channel/yt/yt_전략_채널방향.md              → 채널/서비스 전략 (STOCK BRAIN)
3. channel/strategy/strategy_remotion_가이드.md → 영상 작성 핵심 가이드
4. py tools/log_view.py --days 7              → 최근 작업 이력(전 트랙 합본)
   (wiki/log.md는 2026-07-15부로 동결된 아카이브 — 옛 기록 찾을 때만)
5. wiki/rules/analysis_rules.md               → 분석 행동 규칙
```

---

## ⚠️ 동시세션 = 트랙마다 **자기 폴더**에서 일한다 (2026-07-16~)

**이 폴더(`로또의 주식`)에서 코드 작업하지 마라.** 여기서 일하면 파일이 디스크에 하나뿐이라
먼저 커밋하는 세션이 **남의 미완성 코드를 물리적으로 자기 커밋에 담아** 라이브로 내보낸다(흡수).
규칙으로 못 막는다 — 2026-07-15에 "`git add -A` 금지"를 박은 날 저녁에 흡수가 3번 났다.

```
py tools/track.py start <트랙명>     # 내 폴더 .tracks/<트랙명> + track/<트랙명> 브랜치 생성
트랙.bat                            # ★열린 트랙 목록에서 번호로 골라 Claude Code 열기
트랙.bat <트랙명>                    #   바로 그 트랙으로 (경로 칠 필요 없음)
py tools/track.py finish <트랙명>    # 게이트 통과해야만 main 병합 → 라이브 (폴더는 남는다)
py tools/track.py list              # 열린 트랙 + 얼마나 밀렸는지
py tools/track.py close <트랙명>     # 트랙을 아주 접는다 — 폴더·브랜치 삭제
```

**`finish`는 폴더를 안 지운다.** 태스크가 끝난 거지 트랙이 끝난 게 아니다 — 병합 후 트랙 폴더는
자동으로 최신 main에 맞춰지고 **바로 다음 작업을 얹으면 된다**. 설계가 "태스크 단위로 자주 병합"을
요구하는데 매번 883MB 체크아웃을 다시 만들 순 없다. 트랙을 진짜 접을 때만 `close`
(아직 main에 안 들어간 커밋이 있으면 막는다).

**경로를 손으로 치지 마라.** 프로젝트 루트의 `트랙.bat`을 더블클릭하면 열린 트랙이 번호로
뜨고, 고르면 그 폴더에서 Claude Code가 뜬다. 규칙은 지키기 쉬워야 지켜진다.

**내 트랙 폴더 = `로또의 주식\.tracks\<트랙명>`** (프로젝트 안에 있다).
점(`.`)으로 시작하는 이유: 이 폴더는 **옵시디언 볼트**고 `.md`가 11,120개다. 점 폴더는
옵시디언이 인덱싱에서 자동 제외하므로 트랙마다 볼트에 중복 노트 1만여 개가 생기는 걸 막는다.
`.gitignore`(`/.tracks/`)와 짝이라 main이 트랙 폴더를 untracked로도 안 본다.

- **내 폴더 안에선 `git add -A`도 안전하다** — 남의 파일이 애초에 없다. 커밋은 `track/<트랙명>`으로만 간다.
- **`finish`가 게이트를 돌린다**: 문법 → `import shopping_shorts.app` → pytest.
  **"전부 green"이 아니라 "병합 전보다 실패가 늘지 않았나"**로 본다(기준선 10건은 이미 깨져 있다).
  실패하면 병합을 버리고 **라이브는 무사**하다. 트랙 폴더도 그대로 남는다.
- **병합은 전용 임시 폴더에서** 한다 → 이 폴더는 안 건드린다. 다른 세션이 여기서 일하고 있어도 상관없다.
- **동시에 `finish`해도 안전**: git이 두 번째 push를 거절하면 최신 main 위에서 자동 재시도한다.
  "나 커밋하니까 기다려" 같은 신호등은 필요 없다.
- ⚠️ **오래 끌지 마라.** 태스크 단위로 병합한다. `list`가 5커밋 이상 밀리면 경고한다.

### 🤖 Claude가 지켜야 할 것 (사용자에게 창 바꾸라고 시키지 마라)

사용자가 **"<트랙명> 작업 이어서"** / **"<트랙명> 하자"** 라고 하면, 창이 main 폴더로 열려 있어도
**Claude가 알아서 그 트랙 폴더에서 작업한다.** 창을 새로 열라고 요구하지 마라 — 안 지켜지는 규칙은 없는 규칙이다.

```
□ 1. 트랙 폴더 확인: .tracks/<트랙명> 이 있나?
      없으면 → py tools/track.py start <트랙명>  (사용자 확인 후)
□ 2. 편집은 전부 .tracks/<트랙명>/... 절대경로로.
      ★main 폴더의 코드 파일은 단 하나도 건드리지 마라. 그게 흡수의 재료다.
□ 3. git은 전부 -C 로: git -C .tracks/<트랙명> add -A / commit / status
□ 4. 커밋 전 반드시: git -C .tracks/<트랙명> status --porcelain 로 내 트랙 파일만 있는지 눈으로 확인
□ 5. 작업이 끝났으면(진행 중이면 하지 마라): py tools/track.py finish <트랙명>
      → 폴더는 남고 최신 main에 맞춰진다. 바로 다음 작업 가능.
```

**세션 하나가 트랙 여러 개를 다뤄도 된다** — 폴더만 정확히 가르면 흡수는 안 난다.
흡수를 막는 건 "어느 창에서 여느냐"가 아니라 **"파일이 어느 폴더에 있느냐"**다.

> 트랙 폴더에서 직접 Claude Code를 열어도 된다(상대경로가 자연히 그 트랙을 가리켜 실수 여지가 준다).
> 규칙·스킬·훅 다 그대로 돌고, **`finish`도 트랙 폴더 안에서 그냥 된다**(2026-07-16 수정 —
> 예전엔 BASE가 트랙 폴더가 돼 깨져서 "main 폴더에서 실행"이라는 우회를 적어둬야 했다).

### 어느 폴더에서 일하나 — 작업 종류로 갈린다

| 작업 | 폴더 | 왜 |
|---|---|---|
| **코드** (shopping_shorts·dashboard·tools·scripts) | **`.tracks/<트랙명>`** | 흡수가 여기서 난다 |
| **위키·인제스트** (raw 읽고 wiki 쓰기, 옵시디언) | **main 폴더 그대로** | 아래 |

**위키 작업을 트랙 폴더에서 하지 마라.** git이 추적 안 하는 것은 트랙 폴더로 안 따라온다:
- `raw/` — 크롤봇이 **main 폴더에만** 쓴다. 트랙 폴더의 `raw/`는 커밋된 것까지만이라 **뒤처진다**
  (실측 2026-07-16: 트랙 13,504 vs main 14,572 = **1,068개 차이**). 옛 데이터로 분석하면 틀린 답이 나온다.
- `shopping_shorts/data/` — DB. gitignore라 **빈 DB로 시작**한다. 로컬 확인이 필요하면 복사해 오거나 서버에서 봐라.
- `.obsidian` — 볼트 설정. **볼트는 main 폴더뿐**이라 트랙 폴더의 `.md`는 옵시디언에 안 보인다.
- `.superpowers/` — **SDD 원장·브리프·리뷰**. gitignore라 트랙 폴더에 없다 → main 폴더에서 읽어라.
- `.env`(API 키) — gitignore지만 **`start`가 자동으로 복사한다**(2026-07-16 추가).
  안 하면 `key_vault`가 모듈 위치 기준으로 `.env`를 찾다 키 0개가 돼 **트랙에서 AI 작업이 통째로 막힌다**
  (실측: main 45개 / 트랙 0개 → Gemini 영상분석이 "키풀이 비었다"로 죽었다).
  ⚠️ `start` 전에 만든 트랙 폴더엔 없을 수 있다 — `copy .env .tracks\<트랙명>\`

**따라오는 것**(git 추적): `CLAUDE.md` · `.claude/settings.json`(훅) · `.agents/skills` · `tools/` · `wiki/` · `handoff/` · 코드 전부.
→ 트랙 폴더에서 Claude Code를 열어도 **규칙·스킬·훅이 그대로 도는 똑같은 세션**이다.
→ 대시보드 stop 훅도 트랙 폴더를 '스탁브레인'으로 인식한다(실측). **프로젝트 밖에 두면 인식 실패**라 안에 둔 것이다.

> 아직 이 폴더에서 일하는 중이라면(전환 전 세션): 내 파일만 커밋 → `start`로 폴더 만들고 옮겨라.
> 규칙: `handoff/README.md` / 설계: `docs/superpowers/specs/2026-07-15-트랙폴더-병합게이트-design.md`
> (선행 설계 `2026-07-15-동시세션-충돌차단-트랙격리-design.md`의 **페이즈2(락·신호등)는 폐기됨** — 따라가지 마라)

**git pull 후 CLAUDE.md가 변경됐으면 즉시 다시 읽어라.**

읽기 완료 후 출력:
```
📋 세션 시작 요약
- 내 트랙: {트랙명}
- 최근 작업: {log_view 최근 내용}
- 미결 작업: {handoff/{내 트랙}.md 의 ⏭ 항목 그대로 / 없으면 "없음"}
```

log.md에 `투경 해제 예측 검증` / `종가배팅 시스템` 키워드 있으면 **요약 전에 먼저 표로 보고**.

> 상세 규칙 파일: `wiki/rules/` — analysis_rules / ingest_rules / naming_rules / topick_rules / skill_routing / page_templates / **투경_관리규칙**

> **투경 관리**: `wiki/rules/투경_관리규칙.md` — 관리 종목·신규 추가 절차·텔레 메시지 구조
> 관리 종목 파일: `pipeline/투경_관리.json` (12종목) | 신규 종목은 사용자 확인 후 추가

---

## 🚢 대시보드 배포 규칙 (필수 — 안 지키면 "왜 안 고쳐지나" 재발)

라이브 대시보드 = **stockbrain1.duckdns.org** (서버 `ubuntu@3.39.179.148`, systemd `stockbrain`).

1. **브랜치는 무조건 `main`.** 서버는 `main`만 추적한다. `feat/*` 등 다른 브랜치에 커밋하면 **서버에 영영 안 감**. 커밋 전 `git branch --show-current`로 main 확인.
2. **서버 파일 직접수정(핫패치) 금지.** git에 안 남아 다음 pull에 덮인다. 무조건 로컬 → 커밋 → `git push origin main`.
3. **배포는 자동.** 서버 크론(`deploy/auto_deploy.sh`, 3분)이 새 커밋 감지 시 pull+조건부재시작. 즉 **push까지만 하면 3분 내 자동반영.** 급하면 서버에서 `git pull --ff-only origin main && sudo systemctl restart stockbrain`.
4. **세션 끝 = 반드시 커밋+푸시.** "커밋할까요?"로 방치 금지. 남기면 다른 세션·PC와 꼬인다.
5. **동시에 여러 세션/PC가 같은 워킹트리 편집 금지** (커밋 섞임·작업 유실).
6. **배포 = `finish`.** 내 트랙 폴더에서 커밋만 하면 라이브로 안 간다(서버는 main만 추적).
   ```
   ① (트랙 폴더에서) git add -A → git commit -m "..."   # 내 폴더라 -A 안전
   ② py tools/track.py finish <트랙명>                   # 게이트 통과해야만 main → 3분 뒤 라이브
   ```
   게이트가 막으면 **라이브는 무사**하고 트랙 폴더도 그대로다. 고치고 다시 `finish`.
   충돌이 나면 트랙 폴더에서 `git fetch origin && git merge origin/main`으로 풀고 다시 `finish`.
   <details><summary>아직 main 폴더에서 일하는 전환 전 세션이라면 (옛 방식)</summary>

   ```
   ① git add <내 파일만>              # git add -A 금지 (남의 작업이 실린다)
   ② git commit -m "..."              # 내 작업 먼저 커밋 (원자적 보존)
   ③ git pull --rebase origin main    # 남의 최신 커밋 위에 재배치
   ④ (push는 post-commit 훅이 자동)
   ```
   ⚠️ pull을 커밋보다 먼저 하지 마라 — uncommitted 상태의 raw `git pull`은 충돌로 막힌다.
   </details>
7. CRLF/데이터 노이즈는 `.gitattributes`(eol=lf)로 봉인됨. `raw/`는 git추적 유지(PC간 공유).
8. **같은 서버(`ubuntu@3.39.179.148`), 같은 repo(`/home/ubuntu/lotto-stock-wiki`)에 서비스 2개.**
   `dashboard/`·`scripts/` 변경 → systemd `stockbrain`(:8090, stockbrain1.duckdns.org) 재시작.
   `shopping_shorts/` 변경 → systemd `shopping-shorts`(:8849, shoppingshorts.duckdns.org) 재시작.
   둘 다 같은 `deploy/auto_deploy.sh` 크론(3분)이 처리 — 그래서 아래 9번 사고가 **두 서비스 배포를 동시에** 막는다.
9. **서버 워킹트리는 SSH로 절대 `git add`/`commit` 하지 않는다(핫패치 금지의 연장).** 서버는 `git pull --ff-only`
   전용 — 서버에 uncommitted/staged 변경이 하나라도 남으면 `auto_deploy.sh`가 pull 실패로 **조용히 스킵**되고,
   이후 다른 세션이 아무리 정상적으로 push해도 서버엔 영영 안 감(2026-07-14 실사고: `shopping_shorts/` 여러 파일이
   서버에 staged 상태로 방치돼 배포가 통째로 멈춰있었음, 로컬 4세션 작업 자체는 문제 없었음).
   - **세션 시작 시 1번만 확인**(의심되거나 "배포했는데 안 바뀜" 제보 시 필수):
     ```
     ssh -i C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem ubuntu@3.39.179.148 \
       "cd /home/ubuntu/lotto-stock-wiki && git status --short && tail -5 /tmp/auto_deploy.log"
     ```
   - `git status --short`에 뭔가 걸리면(특히 "M "/"A " staged) 로그에 `pull실패(작업트리충돌?)`가 있는지 확인.
   - **발견해도 함부로 `git stash`/`reset`으로 지우지 마라** — 누구 작업인지 모르면 사용자에게 먼저 보고하고
     처리 방법(그대로 두기 vs stash) 확인받는다. 판단은 사용자 몫.

> 상세·SSH키 위치·트러블슈팅: memory `reference_deploy_truth_branch_ssh`

---

## ⚡ 토큰 절약 규칙

| 툴 | 금지 | 대신 |
|----|------|------|
| `WebSearch` | 결과 전문 유지 | 제목 + 1줄 요약만 |
| `WebFetch` / 크롤링 | 페이지 전체 인용 | 필요 수치·날짜만 추출 |
| `Bash` 출력 50줄 초과 | 전체 출력 유지 | "총 X줄, 핵심: ..." 1줄 요약 |
| `Read` 긴 파일 | 전체 재인용 | 파일 경로 + 줄 번호만 참조 |
| `Write`/`Edit` 완료 후 | 파일 내용 재확인 | 완료 확인 없이 다음 작업 |

- 사용자 메시지 길게 재인용 금지 / 작업 완료 요약 3줄 이내 / 이전 턴 내용 반복 금지
- "컨텍스트"/"토큰"/"압축" 언급 시 → `context-engineering:context-compression` 즉시 실행

---

## ⚡ Superpowers 자동 트리거

| 트리거 조건 | 실행 스킬 |
|------------|---------|
| "만들자" / "설계하자" / "기획하자" / 새 시스템·기능 | `superpowers:brainstorming` |
| brainstorming 완료 후 구현 단계 진입 | `superpowers:writing-plans` |
| writing-plans 완료 후 코드 작성 | `superpowers:executing-plans` |
| 에러·버그·오작동 | `superpowers:systematic-debugging` |
| "다 됐어" / "완료" / 커밋 전 확인 | `superpowers:verification-before-completion` |
| 씬 여러 개 동시 / 파이프라인 병렬 | `superpowers:dispatching-parallel-agents` |
| 커스텀 슬래시 명령어 만들기 | `superpowers:writing-skills` |

> **1%라도 겹치면 무조건 실행. 스킬 라우팅 전체: `wiki/rules/skill_routing.md`**

**fablize (2026-07-02, 글로벌 always-on 설치됨)** — 위 트리거들과 별개로 매 세션 자동 작동하는
검증 절차 레이어. "완료" 주장 전 실행증거 요구(멀티스토리 작업), 디버깅 시 재현→가설→인과사슬
강제, HTML/차트 등 렌더 산출물은 실제 구동 확인 없이 완료 처리 금지. `verification-before-completion`과
겹치는 영역은 fablize가 상시 보강. 설정: `C:\Users\TheRose\.claude\CLAUDE.md`(FABLIZE 블록).

---

## 🎯 스킬 활용 원칙

1. **스킬 먼저** — 작업 시작 전 Skill 목록 스캔. 맞는 게 있으면 즉시 호출.
2. **2개 이상 조합** — 최고 결과물을 위해 스킬을 체이닝한다.
3. **스킬 없이 혼자 하는 건 차선** — 스킬이 있는데 안 쓰는 건 품질 저하.

**유튜브 영상 70/20/10 원칙** (모든 영상 씬 작성 시 필수):

| 비율 | 유형 | 핵심 |
|------|------|------|
| **70%** | 순수 정보 | 내 시스템·서비스 **일절 언급 금지** |
| **20%** | 간접 노출 | "나는 이렇게 한다" 방법론만 |
| **10%** | 직접 CTA | S8(마지막 씬)에서만 **딱 한 번** |

---

## 운영자 프로필

- **역할**: 휴대폰 수출 사업자 + 주식 트레이더, 주식 유튜브 채널 운영자
- **채널명**: 로또의 주식인사이트
- **미션**: 정보의 홍수에서 인사이트만 복리로 쌓는다. AI를 제2의 두뇌(Stock Brain)로.
- **핵심 콘텐츠**: 수급빈집추적, 대장주 포착, 단기 스윙 매매법

---

## 위키 구조

```
로또의 주식/
├── CLAUDE.md              ← 핵심 운영 규칙 (이 파일)
├── wiki/rules/            ← 상세 규칙 (analysis/ingest/naming/topick/skill_routing)
├── raw/                   ← 크롤링 원본 (Claude는 읽기만)
│   └── L1~L6/ market/ news/ telegram/ report/ supply/ export/ blog/ yt/
├── wiki/                  ← 주식 분석 지식 (Claude가 작성·관리)
│   ├── BRAIN_INDEX.md / index.md / log.md
│   └── L1~L6/ L5_섹터/{섹터}/stock/
├── channel/               ← 채널/서비스 전략
├── .agents/skills/        ← 커스텀 스킬 (morning-note, morning-brief, yt-*)
└── out/                   ← 생성된 결과물 (HTML·MP4·스크립트)

C:\Users\TheRose\crawling_bot_data\   ← ⚡ 크롤링봇 수신 폴더 (프로젝트 외부)
    └── 텔레그램봇·뉴스봇·리포트봇이 자동 저장하는 위치
        ingest 시 이 폴더도 항상 확인할 것
```

---

## 4가지 운영 방법

### 1. Ingest (`/ingest today` / `/ingest raw/{파일}`)

라우팅: 섹터(L5) = 1줄 요약 / 종목(L6) = 상세 누적

```
□ 폴더명으로 유형 판별 → 종목명·코드 추출 → 섹터 매핑
□ L5/L6 동시 업데이트 (stock 없으면 신규 생성)
□ 신호 강도 재평가 (같은 방향 3개↑ → 탑픽 콜아웃 / 충돌 → ⚠️)
□ log.md 기록
```

**⚠️ Ingest 시 절대 금지**: 브리핑·HTML·스크립트 생성 — 사용자 명시 요청 시에만.
> 상세: `wiki/rules/ingest_rules.md` / 매핑·네이밍: `wiki/rules/naming_rules.md`

### 2. 결과물 (Output) — 사용자 명시 요청 시에만

`오늘 리포트 만들어줘` / `브리핑 만들어줘` → wiki 참조 → `out/` 저장 → log.md 기록

### 3. 질문 (Query)

wiki 기반으로 답변. 위키에 없으면 "위키에 없음 — 자료 추가 필요" 명시.

### 📊 시장·종목·섹터 분석 자동 파이프라인 (필수)

아래 신호어가 포함된 질문은 **반드시 3단계 순서 실행**:

**신호어**: 어때 / 전망 / 분석 / 왜 / 지금 / 오늘 / 내일 / 반도체·조선·로봇·방산·바이오·전력·2차전지·자동차·통신 / 종목명 / 시장 / 코스피 / 나스닥

```
STEP 1 — 원자 DB 맥락 확보 (최신 데이터 한계 인지)
  python -m pipeline.atoms.query "{핵심 키워드}" --n 5
  → 날짜 확인: DB 최신 날짜가 오늘 기준 2일+ 이전이면 "DB 데이터 {날짜} 기준" 명시

STEP 2 — WebSearch 현재 사실 확인 (실시간 상황)
  → 뉴스·공시·미국 증시 반응 등 현재 사실

STEP 3 — 결합 답변
  → 원자 DB: 맥락·히스토리·리포트 분석
  → WebSearch: 현재 사실·최신 이벤트
  → 두 개 합쳐서 판단. 충돌 시 WebSearch 우선
```

⚠️ **원자 DB만 보고 답하지 마라** — 시간 지연 데이터로 틀린 분석 나옴 (2026-06-07 경험)
⚠️ **WebSearch만 보고 답하지 마라** — 맥락 없는 피상적 분석됨

### 4. 건강검진 (`위키 건강검진 해줘`)

최근 7일 ingest 커버리지 / 공백·오래된 페이지 / 고아 페이지 / 유망 영상 주제 3개 / log.md 기록

---

## Claude 행동 원칙

0. **답변 순서**: 위키 먼저 → WebSearch 교차검증 → 합쳐서 답 (`wiki/rules/analysis_rules.md` §0)
1. **종목 페이지 즉시 생성**: stock/ 페이지 없으면 바로 생성
2. **히스토리 누적**: stock/ 페이지는 새로 만들지 않고 기존에 쌓는다
3. **충돌 감지**: 상충 정보 발견 시 ⚠️ 플래그, 덮어쓰지 않는다
4. **Gemini 검증 필수**: 파트너십·납품 주장은 WebSearch로 검증 (`analysis_rules.md` §4)
5. **TYPE 분류**: 섹터 분석 전 TYPE A/B/C 판단 (`analysis_rules.md` §1)
6. **탑픽 기준**: `wiki/rules/topick_rules.md` 참조
7. **모델 분기** (필수):
   - Haiku 위임: log.md 기록 / index.md 업데이트 / 파일 탐색 / 단순 라우팅
   - Sonnet 전용: 분석·대본·HTML·WebSearch·신호 해석·판단·창작
8. **MCP 최우선**: 웹크롤링→Fetch MCP / 브라우저→Playwright MCP / 저장→SQLite MCP
9. **인덱스·로그 최신화**: 파일 생성·수정 시 index.md 업데이트 + log.md 기록
10. **교차참조**: 새 페이지 작성 시 관련 sector/ stock/ 페이지와 연결
11. **출처 명시**: 모든 wiki 내용에 원본 raw 파일명 기재

**저장 트리거** (`저장해` / `마무리` / `세션 끝` / `마감해줘` / `집에서 이어해`):

```
□ 1. handoff/{내 트랙}.md 갱신 (내 트랙 파일만!)
      - 날짜·PC명·세션 요약
      - 완료 항목 / 미완료 항목 (구체적으로)
      - 관련 파일 경로
      ⚠️ NEXT_SESSION.md는 목록일 뿐 — 거기 쓰면 타세션과 덮어쓴다
□ 2. wiki/log.d/{내 트랙}.md 에 1~3줄 추가 (log.md는 동결 아카이브)
□ 3. memory/ 업데이트 (중요 결정·피드백만)
□ 4. (내 트랙 폴더에서) git add -A → git commit -m "..."     # 내 폴더라 -A 안전
□ 5. 작업이 끝났으면 py tools/track.py finish {내 트랙}      # 게이트 통과 시 main → 3분 뒤 라이브
      ⚠️ 아직 진행 중이면 finish 하지 마라 — 커밋만 해두면 트랙 브랜치에 남는다(유실 없음)
      ⚠️ main 폴더에서 일하는 전환 전 세션이라면: git add {내 파일만}(‑A 금지) → commit → pull --rebase
□ 6. 확인 후 출력:
      ✅ 마감 완료 / 오늘 한 것 / 다음 할 것 / 커밋(+병합 여부)
```

⚠️ **커밋 없이 끝내면 다른 PC에서 못 이어간다.** 트랙 브랜치 커밋은 origin에 백업되니
`finish` 안 해도 유실은 없다 — 단 **`finish` 전엔 라이브에 안 간다**(서버는 main만 추적).

---

## 결과물 자동 열기

사용자 명시 요청 결과물 → 응답 끝에 PowerShell로 자동 실행.

| 확장자 | 실행 명령 |
|------|---------|
| `.html` | `Start-Process "<절대경로>"` |
| `.md` | `code "<절대경로>"` |

대상: `out/` 신규 생성·주요 수정 파일 / 제외: ingest 갱신 파일 / log.md / index.md
