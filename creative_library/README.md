# 공용 크리에이티브 카탈로그 — 최초 읽기 전용 코어

현재 구현은 기존 여섯 도메인의 **조회·실사** 기능이다. 승인, 파일 복사, DB 갱신,
팩 배포, 자동 추천 적용, 렌더, 장면꾸미기 연결은 실행하지 않는다.

```powershell
py -m creative_library --repo 'C:\path\to\track' summary
py -m creative_library --repo 'C:\path\to\track' --db 'C:\path\to\root\shopping_shorts\data\reference.db' search '한글'
py -m creative_library --repo 'C:\path\to\track' --db 'C:\path\to\root\shopping_shorts\data\reference.db' --tenant 7 list --domain scene
py -m creative_library --repo 'C:\path\to\track' get 'legacy/font/TmonMonsori.ttf'
py -m creative_library --repo 'C:\path\to\track' legacy fonts.json HCTmon
```

모든 경로는 절대경로로 지정한다. DB가 없으면 만들지 않으며, 미지정하면 생략했다고
보고한다. DB 미디어 파일을 해시 검사하려면 `--media-root`를 명시해야 한다.
DB는 SQLite `mode=ro`와 `query_only`로 열고 한 읽기 트랜잭션에서 조회한다.

## 권한 경계

이 CLI는 파일시스템·DB 접근 권한이 이미 있는 **로컬 운영자 도구**다.
`--tenant`와 `--admin`은 실사 범위를 지정하는 옵션이며 로그인·인증 수단이 아니다.
HTTP 서비스에 연결할 때는 검증된 서버 세션에서 `AccessContext`를 만들어야 한다.
클라이언트가 보낸 고객 ID·관리자 플래그로 그대로 구성하면 안 된다.

기본 조회는 회사 공용 항목만 보여준다. `scene_assets.customer_id=0`도 개인 자료다.
보이스는 기존 규약대로 `owner_customer_id=0`이 공용이지만, `origin=library`인 0번
보이스는 사장님 제공자 계정 전용으로 0번 고객/관리자만 조회한다. 개인 보이스는 소유
고객만 조회한다. JSON 큐레이션 보이스는 기존 정본이고 DB의 동일 큐레이션 행은 캐시다.
`origin=tuned` 임시 작업대 기록은 소유자/관리자 실사에만 보이며 `legacy_picker_hidden`을
표시한다. 파일에서 사라진 DB 큐레이션 기록은 정본 불일치 제약으로 표시한다.
권한 밖 행은 JSON 파싱과 요약 집계 전에 제외한다. 누락된 소유권 필드는 공개로 추정하지 않는다.

## 보존하는 것과 확인하지 않은 것

- 원래 ID 별칭, 파라미터, 소유권, 승인 상태를 보존한다.
- 파일 SHA-256과 소스 파라미터로 버전을 만들고, 팩 의존성도 정확한 버전으로 고정한다.
- 기존 승인 표시는 정식 출시 승인으로 바꾸지 않는다. 권리 증거·렌더 호환·검수는
  미확인으로 남기므로 현재 legacy 항목은 모두 `usable=false`다.
- 이 읽기 전용 단계는 개별 제약의 충족 여부를 판정하지 않는다. `constraints`가 하나라도
  남아 있으면 `constraints_unverified`로 사용을 차단한다. 이후 도메인별 권리·정책
  resolver에서 조건별 근거와 판정을 구현하기 전에는 설명만으로 조건을 해제하지 않는다.
- 파일 존재·해시 확인은 디코딩·한글 글리프·알파·청각·시각 검수를 뜻하지 않는다.
- 파일 기반 원장은 실행 중 변경되지 않아야 완전한 파일 스냅샷을 얻을 수 있다.
  항목 해시와 카탈로그 fingerprint는 실제 읽은 상태를 나타낸다.
- `deco_frame`은 앱을 import하지 않고 PRESETS와 제한된 순수 빌더를 원본 AST에서 읽는다.
  새로운 실행 표현식이 생기면 어댑터 오류로 보고하며 임의로 따라 실행하지 않는다.
- 폰트 수집 트랙 전체, JS 전용 썸네일 프리셋, DB pattern_item, 브랜드, 자막 실측,
  effect_mining 후보는 아직 이 여섯 어댑터의 수집 범위에 포함하지 않는다.

`list`, `search`, `get`, `legacy`, `summary`는 JSON을 출력한다. 성공은 0,
미존재/권한 밖 항목 조회는 1, 소스 오류·잘못된 설정은 2로 끝난다.
어댑터 오류가 있으면 다른 도메인 결과는 보존하되 오류 상태와 종료코드로 불완전함을 알린다.

검증: `py -m pytest -q tests/creative_library`
