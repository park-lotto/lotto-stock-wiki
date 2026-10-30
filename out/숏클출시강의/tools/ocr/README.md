# 한글 OCR (채널 이름 찾기용) — 10-30

- 엔진: rapidocr_onnxruntime 1.2.3(설치돼 있음) + 한국어 인식 모델(monkt/paddleocr-onnx korean)
  - 모델 받기(13MB, git 에 안 넣음):
    `curl -L -o k_rec.onnx https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/korean/rec.onnx`
    `curl -L -o k_dict.txt https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/korean/dict.txt`
  - 이 폴더에 두면 `ocr_ko.make()` 가 쓴다. cv2.imread 는 한글 경로를 못 읽는다 → PIL 로 열어 넘긴다.
- `sweep.py <영상> <out.json>` : 조각 영상 1초 간격 전수(어디에 무슨 글자가 나오나)
- `ocr_vid.py <영상> <fps> <out.json> [t0 t1]` : 소재 영상 촘촘히 → `../ocr_blur.py` 에 넘김
- 작은 글자(회색 워터마크·lily 칩)는 자주 놓친다 → 결과물 클립은 `../blur_names.py` 의 자리표(가족별 비율 상자)로, 흐린 뒤 반드시 확대 캡처로 눈 확인.
