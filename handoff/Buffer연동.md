# Buffer(SNS 예약발행) 연동 — 조사 결과

## 2026-08-29 조사 (공식 문서 실측) — **고객별 연결은 지금 불가**

사장님: "BUFFER 이거 자동등록 프로그램이라고 하는데 붙일건데 어떻게 해야하나"
사장님 선택: **고객마다 자기 Buffer 연결(OAuth)** → ⚠️ **그 방식은 현재 Buffer가 지원 안 함**

### Buffer API 현재 상태 (2026-08)
| 항목 | 사실 |
|---|---|
| 요금제 | **모든 요금제에 API 포함**. 무료=키 1개·월 3,000요청 / Essentials=3개·7,500 / Team=5개·15,000 |
| 키 생성 | **조직 소유자만** 가능 |
| 지원 채널 11개 | 인스타·쓰레드·틱톡·유튜브·페이스북·X·링크드인·핀터레스트·구글비즈니스·마스토돈·블루스카이 |
| **파일 업로드** | ⚠️ **업로드 엔드포인트가 없다.** 우리가 **공개 URL**로 호스팅하고 주소만 넘긴다.<br>조건: 인증 없이 접근 · HTTPS · 게시 시점까지 유지(만료 서명URL 금지) |
| **제3자 OAuth** | ⚠️ **아직 안 열림.** 새 GraphQL API는 **개인 키 전용 베타**(신청·승인 후 내 채널만).<br>옛 REST API의 OAuth는 **신규 앱 등록이 닫혔다.** |

★헬프센터에 "다른 사람이 연결하게 하려면 OAuth를 쓰라"고 적혀 있지만, 그건 **아직 열리지 않은
  기능을 가리키는 안내**다. 개발자 문서·제3자 정리글 모두 "2026년 신규 개발자에게 제3자 발행 불가"로 일치.

### 그래서 가능한 것
- ✅ **사장님 계정 하나로**: 사장님 Buffer에 사장님 채널 연결 + 개인 키로 예약. 배선 작다.
- ❌ **고객마다 자기 Buffer**: Buffer가 제3자 OAuth를 열어야 한다. 로드맵에 일정 없음.

### 붙이려면 우리가 할 일 (사장님 계정 방식 기준)
1. **완성 영상의 공개 URL** — 지금 완성본은 유료게이트 뒤에 있다. 게시 예정 영상만
   인증 없이 열리는 주소로 내주는 길이 필요(랜덤 긴 주소 + 게시 후 만료 등).
   ⚠️ 관련 함정: 단축링크를 프로세스 메모리에 두면 재배포 때 전멸한다
   (memory `reference_share_link_memory_dies_on_restart`) → DB에 둘 것.
2. **API 키 보관** — 기존 `key_vault` 방식 그대로.
3. **예약 전송** — 8단계 SEO의 제목·설명·해시태그를 Buffer 초안으로 넘기고 시간 지정.

### ⏭ 다음 (사장님 결정 대기)
- (A) 사장님 계정 하나로 진행할지
- (B) 고객 판매가 목적이면 **제3자 발행을 정식 지원하는 다른 API**를 조사할지 — 별건

### 출처
- support.buffer.com/en-us/articles/using-buffers-api-GtIYIQilz5 (요금제·채널·키)
- developers.buffer.com/guides/hosting-media.html (공개 URL 방식, 업로드 엔드포인트 없음)
- postproxy.dev / zernio.com 정리글 (제3자 OAuth 미개방)

## 2026-09-02 — 유튜브 예약이 통째로 거절되던 것 (해결, 게이트 대기)

**증상**: 버퍼 예약발행에서 유튜브만 안 됨. 인스타·틱톡은 됨.

**뿌리(라이브 로그 실측, 9/1~9/2 6회 전부 동일)**
```
Field "type" is not defined by type "YoutubePostMetadataInput"
```
`_post_metadata`가 유튜브에 `{"type":"short","privacy":...}`를 보냈는데
**type이라는 칸이 유튜브 스키마엔 없다**(인스타에만 있는 축이었다).
GraphQL 검증 단계에서 죽어 유튜브는 100% 실패.

**introspection 실측 — YoutubePostMetadataInput 8필드**
categoryId · title · embeddable · isAiGenerated · license · madeForKids ·
notifySubscribers · privacy

**고친 것** (`shopping_shorts/buffer_api.py`)
- 유튜브: type 제거 → `title`(본문 첫 줄, 100자·<> 정리) + `categoryId="22"` + `privacy`
- 틱톡: `TiktokPostMetadataInput` **자체가 없음**을 확인 → metadata 안 붙이는 현행이 정답
- 인스타: type/shouldShareToFeed 맞음. 단 **개인 프로필 계정이면 Buffer가 거절**
  ("personal profile channels require notification scheduling") → `_humanize`로
  한국어 안내 변환(프로페셔널 계정 전환 안내)

**검증**: 없는 channelId로 3개 SNS 모두 createPost를 실제 Buffer에 보내
스키마 검증을 통과해 "Channel not found"까지 도달함을 확인(게시는 안 됨).

⏭ 다음
- track finish 게이트 통과 확인 → 라이브에서 유튜브 실제 예약 1건 성공 확인
- 인스타는 계정을 프로페셔널로 전환한 뒤 재시도

### 2026-09-02 12:59 — 라이브 반영 + 3채널 실예약 검증 완료

사장님이 Buffer에 3채널을 등록한 뒤 실제 예약을 시험했다.
- 유튜브 `Micro-Universe1` / 인스타 `syospa123` / 틱톡 `parkpotto12`

**검증 방법**(게시하지 않는다): 실제 완성본 `353493f20d31/final.mp4`로 공개링크를 발급해
**25일 뒤로 customScheduled** 예약 → post id 확인 → **deletePost로 즉시 삭제**.
shareNow는 쓰지 않았다(되돌릴 수 없다).

| 시점 | 코드 | 유튜브 | 인스타 | 틱톡 |
|---|---|---|---|---|
| 12:07 | 라이브(옛 코드) | ❌ `Field "type" is not defined` | ✅ | ✅ |
| 12:07 | 고친 코드 끼워넣기 | ✅ | ✅ | ✅ |
| 12:59 | **라이브(반영 후)** | ✅ | ✅ | ✅ |

서버는 12:59:11에 auto_deploy가 재시작해 새 코드로 돌고 있다.

⚠️ 인스타 "개인 프로필" 거절(9/1 로그)은 **다른 고객 계정** 이야기다 — 사장님 계정은
프로페셔널이라 정상 통과했다. 그 고객에겐 `_humanize`가 한국어 안내를 준다.

⏭ 남은 것
- HTTP 경로(`POST /api/buffer/schedule`)까지의 실사용 확인은 **고객 실사용 로그로** 본다
  (관리자 비번으로 대신 로그인하지 않았다). 인스타·틱톡은 이미 그 경로로 200 성공 기록이 있다.
- 별건: `pipeline/atoms/key_vault.py`의 `rotated()`와 PID 커서 씨딩이 main에서 사라졌다
  (9/1 커밋 3ae3b2b6c가 넣은 것이 이후 병합에서 되돌려짐). 키 회전이 죽어 429 재발 위험.
  되돌린 이유를 몰라 손대지 않았다 — 사장님 판단 필요.
