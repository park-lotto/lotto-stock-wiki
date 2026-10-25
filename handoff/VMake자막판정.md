# VMake자막판정 — 핸드오프 (관제 271)

**소유 트랙**: VMake자막판정 — 이 파일은 이 트랙 세션만 수정한다.

## 2026-10-26 (CH PC, 기미크림 창 배경 작업자)

사장님 지시(10-26, 서버 설치까지 승인 "ok go"): 웹 라인 VMake 에 **자막 있는 컷만** — 고객이 장면을 안 고르면 자동 판정.
관제 270(track/VMake웹자막컷, 보낼 컷 주인 vmake_send_cuts·관문 _vmake_gate) 위에 쌓았다.

### 주인·검사 (0순위-C)
- 판정 주인: `shopping_shorts/channelkit/vision/burned_text.py:foreign_text`(+ text_feats·cut_hit·video_cut_feats)
  = 칼카피 관문 ④(`tools/calcopy/hybrid/render_bench.py` text_feats·foreign_text·TEXT_*)를 **그대로 옮김**. 칼카피 표본 762컷 대조: 옮긴 판정 tp121·fp13 = render_bench 와 동일(P 0.903·R 0.917).
- 보낼 컷 주인: `mix_pipeline.vmake_send_cuts(cuts, sel, text)` — 고객 선택이 이긴다 / 안 골랐으면 글자 없음(False) 컷만 뺀다 / 못 잰 컷(None)은 보낸다 / 전부 False·판정기 없음 = 확정 컷 전부 + ops_alert(`vmake_text_judge`).
- 재기: `mix_pipeline.vmake_cut_text(조립본, 컷 지도, work)` — job 폴더 `vmake_cut_text.json` 캐시. 결과 요약은 `vmake_sent.json` 장부 줄의 `text`(judge·cuts·sent·skipped·unsure).
- 검사: `shopping_shorts/tests/test_vmake_text_judge.py` — 옛 코드(6a9ea6b70)에서 빨강 확인(6초 전체 전송) → 새 코드 2초. 합성 자막 영상 실판정 [True, False].
- `channelkit/__init__.py`·`vision/{__init__,facelib_cv,ocrdet}.py`·LICENSE 는 칼카피숏템엔진 트랙과 **바이트 동일** 사본(md5 대조) — 칼카피 병합 때 충돌 없음.

### 서버
- `pip install --user --break-system-packages "opencv-python-headless<5" onnxruntime` → cv2 4.14.0 · onnxruntime 1.31.0 · numpy 2.4.6 그대로(auto_deploy 는 pip 안 한다 — requirements.txt 에 적어 둠, 새 서버면 손으로).
- 모델 `~/.shortem/models/ppocrv5_server_det.onnx`(88MB, git 밖) scp — sha256 f4c03784… 로컬과 일치.
- 실측(job 39279d1d1438 청소본 16컷): 서버 41초 · 최대 RSS 1.1GB · 판정 = 로컬과 동일(글자 4컷: HANDY SPACE 로고·.com 워터마크, 지운 컷 전부 없음).

### ⏭ 남은 것
- 칼카피숏템엔진 트랙: `render_bench.py` 의 text_feats·foreign_text·TEXT_*·_in_ring·_glyph_diff 를 `from shopping_shorts.channelkit.vision.burned_text import …` 로 바꾸기(두 벌 해소). blur_cover 는 `text_feats(..., blur=lambda box: blur_cover(regs, crop, win, box, t))` 로 넘긴다. 표본 시험 test_cut_content_labels 그대로 통과 확인.
- 속도: 컷당 서버 ~2.6초(PP-OCR server det). 길면 렌더가 그만큼 늘어난다 — 필요하면 mobile det 또는 컷 병렬.
- 워터마크만 있는 컷("Gadget ivo" 얇은 글)은 '없음'으로 나온다(칼카피 자와 같음) — 고객이 직접 고르면 보낸다.
