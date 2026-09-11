---
name: project
description: 쇼츠 하드섭 자막제거 도구(판매용). VSR fork+LaMa 고정영역으로 품질 검증 완료
metadata: 
  node_type: memory
  type: project
  originSessionId: 650df538-b0a0-4ec1-9502-1a210e401852
  modified: 2026-07-24T07:48:46.747Z
---

실사 쇼츠 하드섭 제거 도구. **상업/판매** 목적이라 ProPainter(비영리) 제외, STTN+LaMa(Apache)만.

**베이스**: YaoFANGUK/video-subtitle-remover(VSR) fork. 위치 `C:\Users\TheRose\Desktop\자막제거`. **소스 백업 repo(비공개)=github.com/park-lotto/subtitle-remover** (소스만: src/backend_custom·cloud_deploy·PROJECT.md, 무거운 번들·venv·모델은 .gitignore 제외) (스탁브레인 repo와 별개 폴더).
**환경(재설치 불필요)**: Python 3.12 venv + torch 2.7.0+cu126, RTX 3060 12GB. prebuilt 1.1.1의 `vsr-cuda126\resources\backend`가 모델 포함 실행소스. 로컬 wheel은 `vsr-cuda126\opt\packages`(torch 등 97개, 재다운 불필요).

**핵심 발견**: STTN 빠른모드(검출생략)는 **자막이 내내 고정된 자동자막 쇼츠엔 잔상**이 남는다(앞뒤프레임 배경복원인데 깨끗한 참조프레임이 없어서). **LaMa 고정영역**이 프레임별 생성이라 깨끗. 실측(16초/1080×1920): STTN 149s(잔상) vs LaMa 357s(깨끗). 2영역(하단자막+우상단[광고]) 동시제거 완성본 검증 완료.

**직접 커스터마이즈**: `backend/run_cli.py`(다중영역+`--fixed` 검출우회 드라이버), `config.py` MODE=LAMA, `lama_inpaint.py` **한글경로 버그 패치**(torch.jit.load가 비ASCII 경로 fopen 실패 → BytesIO로 읽어 로드). paddle→onnx 자동검출은 paddle 3.0 포맷 때문에 깨져서 현재 고정영역으로 우회.

**★한글경로 근본해결**: torch.jit·paddle inference C++ 로더가 한글경로 못 연다. 파일패치 말고 **ASCII 정션** `New-Item -ItemType Junction C:\vsr -Target 자막제거폴더` 만들고 **항상 C:\vsr\...로 실행** → __file__ 파생경로 전부 ASCII화.

**★자동검출 작동**: config `ONNX_PROVIDERS=[]` 강제 → paddle 네이티브 검출(구형 pdmodel 로드). 좌표 없이 랜덤위치 자막 자동검출(프레임당 0.9s, paddle CPU판이라 병목). paddle→onnx 변환은 paddle3.0 포맷 못읽어 깨짐 → 네이티브가 정답.

**배치도구 완성(A단계)**: `backend/batch_remove.py` 폴더/파일들→자동검출→LaMa→_clean.mp4. 데모2파일 품질 판매수준 검증. 속도 714s/16초(검출 CPU 병목).

**엔진 비교 결론(파일B=단색벽+고정자막 최악케이스)**: LaMa 460s=옅은얼룩(최선) / STTN+검출 291s=검은잔상박스(더나쁨, 고정자막이라 참조프레임에도 자막) / ProPainter=최고지만 비영리. **상업가능 중엔 LaMa가 최선.** 근본해결은 생성형 영상모델 **Wan2.1 VACE(Apache2.0)**뿐인데 무겁고느림(3060부담, 별도 대작업=B단계 후보). 단 랜덤 퍼온영상 대부분은 배경복잡/움직여 LaMa로 깨끗, 단색+고정자막만 예외.

**최적화 반영**: config `DETECTION_STRIDE=5`(검출 N프레임마다, 714→460s), `SUBTITLE_AREA_DEVIATION_PIXEL=50`(마스크팽창). 엔진=LaMa 확정.

**바탕화면 산출물**: `자막제거_여기에_영상_끌어다놓기.bat`(드래그앤드롭 런처, C:\vsr 경유). 좌우비교영상=ffmpeg hstack(7.6s).

**★핵심 제품딜레마(발견)**: 완전자동 전체검출은 자막뿐 아니라 **장면 속 제품글자(드릴로고·배터리 "18 LITHIUM" 라벨)까지 뭉갠다**. 판매용 부적합. 해결=①영역지정(고객이 자막박스, Vmake방식, 안전) ②자막스타일필터(흰/노랑+검은테두리+가로넓음만) ③고정위치만. 클라우드 이전에 이 설계 먼저 정해야 함. ProPainter 로컬은 12GB로 풀해상도 불가(OOM), 8배수해상도 필요, 축소하면 화질열화(줄무늬)—풀실력은 24GB+ 클라우드+비영리라 판매X.

**사업방향 확정**: 독립제품(레드오션 Vmake·HitPaw) 아니라 **기존 쇼핑쇼츠(숏템탑스)에 자막제거 기능으로 얹어 판매**. 서비스=클라우드 서버리스(RunPod, 요청당 워커1개=동시처리) 필수(로컬GPU1장 불가). 개당원가 ~150원 vs Vmake 500원=마진60%+. 법적리스크(퍼온영상 가공) 유의.

**클라우드 배포패키지 작성완료**: `Desktop\자막제거\cloud_deploy\`(Dockerfile CUDA12.1 + handler.py 서버리스 + client_test.py + prep_backend.ps1 + README). ⚠️로컬빌드·테스트 못함(Docker/리눅스GPU 없음)—첫 실빌드때 의존성 미세조정 필요. 사장님 액션=RunPod가입+충전→빌드푸시→엔드포인트(4090)→client_test로 개당원가 실측.

**★다음 세션 시작점 = `Desktop\자막제거\HANDOFF_OPUS.md`** (2026-07-23 작성, repo에도 커밋). 완료: 스타일필터·스티키 깜빡임제거·recall튜닝·실영상3종 검증. 남은 로컬리밋: ①위치+지속성 판별(최대 레버) ②대량 로버스트 검증(reference.db→yt-dlp 20~30개) ③[광고] 저대비 잔여 ④마스크 feather. 미확인: 깜빡임 수정본 사장님 재생확인, recall 후 전체렌더 1회. ⚠️Bash cd는 C:\vsr 정션을 한글로 풀어 paddle이 죽음→PowerShell로 실행.

**★클라우드 실험(2026-07-23, RunPod 4090 Pod) 교훈**: 화질=로컬과 100% 동일(같은코드·1080x1920)→클라우드는 화질용 아님, 속도·동시처리용. **즉석 Pod GPU세팅 실패**: SSH가 긴명령에 계속 끊김(exit255), paddle-GPU가 CUDA+multiprocessing(spawn)에서 hang, 결국 paddle CPU회귀+torch도 CPU로 떨어져 GPU 0% 내내→921초(로컬949초와 동일)=속도이점0. **속도벤치는 반드시 cloud_deploy Docker이미지로** 해야함(즉석세팅 취약). 주의: batch_remove의 `multiprocessing.set_start_method("spawn")`+GPU paddle 교착 의심→Docker때 조사. 비용 $0.58. SSH접속 `-o ServerAliveInterval` 필수, 긴실행은 nohup 분리+run.log 폴링. API키 대화노출→재발급 권장.

**★Wan2.1 fal VACE 성공 레시피(2026-07-23 해결)**: 자막 깨끗제거 성공. 앞선 실패 6번 근본원인 2개—**(1)파라미터명 오류**: `mask`로 보내서 fal이 조용히 무시(마스크 아예 미적용)→어떤 폴러리티든 자막유지. 정답은 **`mask_video_url`**(마스크는 IMG아니라 **영상**, 81프레임). `mask_image_url`은 salient tracking용 별개. **(2)VACE는 마스크영역의 원본 구조를 그대로 재현**(structure-guided)→고대비 자막텍스트를 폴러리티 무관하게 픽셀단위 복원(생성모델이 크리스프 한글=재생성 아니라 보존의 증거). **해결=입력영상의 자막영역을 배경색으로 미리 블랭크**(빨간벽 BGR≈(50,42,199)로 사각형 칠) → mask_video_url 흰=재생성 → Wan이 블랭크영역을 배경으로 채움. 레시피: ①원본 자막박스 배경색 블랭크(cv2.rectangle 프레임별) ②마스크영상 흰=블랭크영역/검=유지 ③args=video_url+mask_video_url+prompt+match_input_num_frames:true+aspect_ratio:9:16+resolution:720p+num_inference_steps30. 결과 720x1280 자막·[광고] 완전제거, 빨간벽 깨끗. 비교=`Desktop\Wan2.1_원본vs제거_빨간벽.mp4`·3자비교 `Desktop\자막제거_원본_LaMa_Wan.mp4`. **★요금(실측, $0.01는 오류)=초당 720p $0.08 / 580p $0.06 / 480p $0.04(16fps 환산). 청크수 아니라 총길이×요율.** num_frames 81~241(한번에 최대~8초@30fps). **30초숏 720p=$2.40≈3,360원(Vmake 500원의 6.7배), 60초=$4.80≈6,720원.** 스크립트=scratchpad\wan_run.py.

**★그러나 전략적 결론=제품엔 Wan 부적합**: Wan은 자막검출을 대체못함(블랭크하려면 어차피 Paddle검출=LaMa와 동일 전처리 필요)—즉 **파이프라인=검출→블랭크→Wan** vs 현행 **검출→LaMa**. Wan은 인페인팅 단계만 교체. 게다가 재생성이 **자막없는 다른 영역까지 뭉갬**(run6 금속빔 스머지 관측)+클립당 과금+~3~8초 청크 이음매. 반면 로컬 LaMa v2는 이 빨간벽 최악케이스도 이미 깨끗. **결론: 화질우위 미검증(오히려 정상영역 열화 리스크), 원가·복잡도↑. 제품은 LaMa 유지 권장. Wan은 LaMa로도 안되는 특정 복잡배경 정밀보정용 옵션으로만.** RunPod A100 종료(잔액$9.28). fal잔액≈결제$10-6콜. fal키 재발급 필요.

**★글자획 마스크(2026-07-23, 자국 근본해결)**: 자국 원인=사각형 마스크가 자막 겹친 물체(봉·장갑)까지 지워 LaMa가 어두운 얼룩 생성. 해결=`_refine_to_stroke`(lama_inpaint.py): 사각형 안에서 밝은획(≥180)+검은테두리 인접 픽셀만 마스킹→물체 보존, 못 찾으면 사각형 폴백. **★LaMa 마스크 3대 함정(실측)**: ①글자 실루엣 모양 마스크를 주면 LaMa가 "글자모양 물체"를 검게 되그림→팽창으로 뭉툭한 띠로 만들어야(검증 최적=글자획 세로스팬×0.45≈d29) ②적응팽창 기준 text_h는 밝은획 스팬(실측68)이지 글자높이(140) 아님—0.18 썼다가 dil13→검은얼룩 회귀 ③테스트에서 `import config`≠`backend.config`(별개 모듈!)—런타임 토글 전부 무효되는 오염, 반드시 `from backend import config`. **크롭 인페인트**(`LAMA_CROP`, `_mask_boxes` 연결요소+병합+margin96): LaMa를 마스크 주변만→모델 22배(0.10s vs 2.24s), e2e 174.6→97.0s(1.8배, 잔여병목=CPU 검출). **페더 합성**: 마스크 밖 원본픽셀 100% 보존(전프레임 신경망 통과로 인한 물러짐 제거=실질 선명도↑). 검증=빨간벽 1080p(봉·장갑 보존)+드라마 640p(얼굴 옆 자막, 얼굴 무손상).

**★두더지잡기 진단·종결 로드맵(2026-07-24 확정)**: 실영상 10개 검증에서 생김새 기반 판정의 한계 노출—①팽창량이 글자획 세로스팬 기준=드릴 과적합(비자막 경계 잡혀 스팬 튐)→검출박스 높이 기준으로 수정 ②판때기형(반투명 배경박스) 자막은 글자획만 지우면 회색판 잔존→`_has_plate`(박스 안팎 밝기 중앙값 차>12, 단 dev만큼 erode한 진짜 박스로 재야 분리: 폰93 vs 드릴1) 판때기=박스째/아니면 글자획만(커밋 3e01263). **드릴 고품질의 정체=단색벽+판때기없음=쉬운 조건이었지 기술 아님—기준 삼지 말 것.** 남은 오탐=폰 화면 속 UI 글자. **종결 로드맵: ①생김새→행동 기반 판정(고정위치+지속=자막의 정의라 유형 불변)이 일반해 ③원클릭 확인 UX(Vmake식, 추측 제거) + 고정 테스트셋 30개 실패율 측정으로 끝을 선언. ②Wan은 화질천장의 끝이나 30초 3,360원=프리미엄 보류.** 실측 속도: 로컬 평균 40x realtime(30초숏=20분)→클라우드 필수 재확인. 샘플=`Desktop\vsr_samples\`, 원본·산출=`C:\vsr_refs\sample10\`.

**A단계(개인도구) 완료.** 다음: **행동(위치·지속성) 판정 구현**(find_subtitle_frame_no가 프레임별 박스 dict 생성—후처리 삽입점), 테스트셋 30 실패율, RunPod Docker 배포·벤치(Docker Desktop 설치 대기, 잔액 $9), 쇼핑쇼츠 웹연동. 상세=`Desktop\자막제거\PROJECT.md`·`cloud_deploy\README_DEPLOY.md`. [[feedback_ttalkkak_senior_northstar]] [[project_brand_name_shottemtops]] [[reference_freeze_whackamole_root]]
