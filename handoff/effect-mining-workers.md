# effect-mining-workers

## 목적

쇼츠 효과 자료를 한 번 긁고 끝내지 않고 별도 클라우드 워커가 계속 `discover → acquire → measure → promote`하는 기반을 만든다. 운영 서버의 기존 렌더 큐와 무거운 수집 작업을 분리한다.

## 구현 내용

- `shopping_shorts/effect_mining/db.py`
  - 소스·영상·작업·신호·후보·실행 이력 SQLite 스키마
  - 플랫폼 영상 ID 중복 제거
  - active dedupe key, 원자적 lease, heartbeat, 만료 회수
  - 지수 백오프 재시도와 dead-letter
- `connectors.py`
  - 커넥터 레지스트리와 URL ID 정규화
  - 기존 `youtube_search.search`를 쓰는 YouTube 키워드 커넥터
- `pipeline.py`
  - 수집 단계 연결
  - 기존 `media_download.download_any`를 통한 원본 확보
  - 분석기 버전별 중복 방지
- `analyzers.py`
  - 기존 `scene_cut`의 컷·프레임 모션 신호 재사용
  - 장면전환과 모션 피크 후보 생성
- `runner.py`, `cli.py`
  - scheduler/worker 1회 실행과 상시 루프
  - `init`, `add-source`, `schedule`, `work`, `status` 명령
- `deploy/effect-mining-*.service.example`
  - 별도 머신에서 scheduler 1개와 worker N개를 띄우는 systemd 예시

## 운영 명령

```bash
python3 -m shopping_shorts.effect_mining.cli init
python3 -m shopping_shorts.effect_mining.cli add-source youtube keyword "쇼핑 꿀템" --interval-sec 3600
python3 -m shopping_shorts.effect_mining.cli schedule --once
python3 -m shopping_shorts.effect_mining.cli work --once
python3 -m shopping_shorts.effect_mining.cli status
```

상시 실행 시 `/etc/shopping-shorts.env`에 기존 YouTube/다운로드 자격과 아래 경로를 둔다.

```text
EFFECT_MINING_DB=/var/lib/shopping-shorts-effect-mining/mining.db
EFFECT_MINING_MEDIA_ROOT=/var/lib/shopping-shorts-effect-mining/media
```

## 검증

- DB/queue/pipeline/CLI 전용 테스트 19개와 기존 `test_scene_cut.py` 11개, 총 30개 통과.
- 가짜 커넥터·다운로더·분석기로 전체 4단계 lineage 저장 확인.
- FFmpeg로 만든 4초 샘플 MP4에서 2초 컷 경계와 모션 피크를 실측했고, 0 에너지 상대 피크 오탐 회귀 테스트를 추가했다.
- 이미 수집·분석을 마친 영상은 다음 발견 주기에 메타데이터만 갱신하고 downstream 큐를 다시 만들지 않는 비용 회귀 테스트를 추가했다.
- `python -m compileall -q shopping_shorts/effect_mining` 통과.
- 실제 네트워크 수집은 API 키·쿠키·프록시가 있는 별도 워커 배치 후 스모크 테스트가 필요하다.

## 다음 트랙

1. `effect-mining-source-fleet`: 쇼핑 80% + 글로벌 트렌드 20%가 되도록 YouTube 채널/키워드, Instagram, TikTok 커넥터와 source seed 정책 추가.
2. `effect-mining-signal-v2`: OCR 자막 위치·스타일, 오디오 트랜지언트, 줌/흔들림/색 변화 신호 추가.
3. `effect-mining-patterns`: 여러 영상의 후보를 군집화하고 빈도·신선도·재현 가능성으로 검수함 승격.
4. `effect-library-admin`: 관리자 전용 검수·승인·병합·릴리스 화면.
5. `effect-recipe-builder`: 승인 패턴을 Remotion/FFmpeg 자체 레시피와 정식 에셋 팩으로 재구축.

## 주의

- 수집 원본은 연구 근거다. 고객 배포물에는 자체 레시피 또는 권리가 확인된 에셋만 넣는다.
- 현재 프로덕션 커넥터는 YouTube 키워드만 연결되어 있다. Instagram/TikTok 이름으로 source를 등록하면 worker가 unsupported 오류를 기록하고 재시도한 뒤 dead로 보낸다.
- SQLite 단일 writer 처리량을 넘기 전까지는 외부 큐를 추가하지 않는다. 병목이 실측되면 `MiningDB` 인터페이스 뒤를 PostgreSQL/Redis로 교체한다.
