---
name: yt-editor
description: 녹음 파일(MP3/WAV) → Whisper 자막 → Remotion 렌더 → 완성 MP4. 명령어 하나로 편집 자동화.
metadata:
  tags: youtube, editor, remotion, whisper, 편집, 자막, 영상
---

## When to use

사용자가 다음 중 하나를 요청할 때:
- `/edit [녹음파일경로]`
- "편집해줘", "영상 만들어줘", "자막 달아줘"
- "녹음 끝났어, 영상 만들어줘"

---

## 전체 흐름

```
녹음 파일 (MP3/WAV)
    ↓ Step 1: Whisper 자막 생성
SRT 자막 파일
    ↓ Step 2: 파일 배치
remotion-stock/public/ 에 오디오+SRT 복사
    ↓ Step 3: Remotion 렌더
완성 MP4 → out/video/YYYYMMDD_video.mp4
```

---

## Step 1: Whisper 자막 생성

```powershell
# SRT 자막 생성 (한국어, medium 모델)
python -m whisper "{녹음파일}" `
  --language Korean `
  --model medium `
  --output_format srt `
  --output_dir "out/captions"
```

- 출력: `out/captions/YYYYMMDD_recording.srt`
- 모델 기본값: `medium` (속도/정확도 균형)
- 사용자가 `large` 요청 시 `--model large` 로 변경

---

## Step 2: 파일 배치

```powershell
# Remotion public 폴더로 복사
Copy-Item "{녹음파일}" "remotion-stock/public/audio.mp3"
Copy-Item "out/captions/{파일명}.srt" "remotion-stock/public/captions.srt"
```

---

## Step 3: Remotion 렌더

`remotion-stock/src/LongformComposition.tsx` 를 사용한다.
이 컴포지션은 오디오 길이에 맞게 자동으로 영상 길이가 조정된다.

```bash
cd remotion-stock
npx remotion render LongformComposition ../out/video/YYYYMMDD_video.mp4
```

렌더 전 오디오 길이 확인:
```powershell
ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{녹음파일}"
```

---

## Step 4: LongformComposition에 오디오+자막이 없을 경우

`remotion-stock/src/LongformComposition.tsx` 를 읽어 현재 구조 파악 후:
1. `<Audio>` 컴포넌트 추가 (오디오 트랙)
2. `<Subtitles>` 또는 자막 오버레이 컴포넌트 추가 (SRT 기반)
3. `calculateMetadata` 로 오디오 길이에 맞게 durationInFrames 자동 계산

remotion-best-practices 스킬의 `rules/audio.md`, `rules/subtitles.md`, `rules/get-audio-duration.md` 를 참조한다.

---

## 출력

- 영상: `out/video/YYYYMMDD_video.mp4`
- 자막: `out/captions/YYYYMMDD_captions.srt`

---

## 완료 후

`wiki/log.md` 에 기록:
`[YYYY-MM-DD] 영상 렌더 완료 — {녹음파일} → out/video/YYYYMMDD_video.mp4`
