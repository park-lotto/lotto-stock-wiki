# NEXT_SESSION — 쇼핑쇼츠 믹스 자막 이어하기

**날짜**: 2026-07-12 (사무실 PC) → 집에서 이어서
**대상 파일**: `shopping_shorts/video_assemble.py`

## 지금까지 완료 (전부 main 푸시됨)

| 커밋 | 내용 |
|------|------|
| 45da313e | 자막 페이싱: setpts 배속압축 폐지, 나레이션 길이만큼 1배속 재생 |
| 02fd75c1 | **새 대본 자막 굽기**: 하단 바 + drawtext(렌더러가 오디오만 교체하던 문제 해결) |
| 2d908760 | NanumGothic 폰트 repo 번들(서버 pull만으로 자막 렌더, apt 불필요) |
| 5eaaaa9a | 장면 반복 해결(연속재생) + 자막 문장단위 분할 |

## ⚡ 바로 할 일: 자막을 "짧은 구절 단위"로 분할 (사용자 요청)

현재 `_caption_segments`는 문장(.?!) 단위 2줄 덩어리 → 너무 큼.
사용자는 **어절 단위 짧은 구절**(오이 사자마자 / 냉장고에 / 넣으셨나요?)로 원함.
"너무 규칙적으로 자르면 이상하니까" → 어절 길이가 제각각이라 자연히 불규칙해짐.

### ✅ 검증 완료된 알고리즘 (이대로 `_caption_segments` 교체)

```python
_CAP_TARGET = 7  # 한 구절 목표 글자수(공백 제외)

def _caption_segments(narration):
    """어절(띄어쓰기) 기준으로 짧게 묶는다. 누적 글자수가 _CAP_TARGET을 넘으면
    끊어 새 구절 시작. 어절 길이가 제각각이라 자연히 불규칙하게 끊긴다."""
    narr = (narration or "").strip()
    if not narr:
        return []
    out, cur = [], ""
    for w in narr.split():
        if not cur:
            cur = w
        elif len((cur + w).replace(" ", "")) <= _CAP_TARGET:
            cur = cur + " " + w
        else:
            out.append(cur); cur = w
    if cur:
        out.append(cur)
    return out or [narr]
```

사용자 예시 텍스트로 돌려본 결과가 사용자가 손으로 나눈 예시와 거의 동일했음(검증됨).

### 구현 시 같이 볼 것
- `_caption_vf`: 이제 각 구절이 짧은 **1줄**이므로 2줄 wrap 로직 불필요.
  글자수 비례 시간배분은 유지. 아주 짧은 구절(2~3자)이 너무 빨리 지나가면
  최소 표시시간(~0.5s) 하한 고려(단, 합이 dur 넘지 않게 정규화).
- 폰트 크기 키워도 됨(짧은 1줄이라 여유). 현재 `_CAP_FONTSIZE=46`.
- 미사용된 `_CAP_WRAP`(=13)는 아주 긴 단일 어절 방어용으로 남기거나 정리.

## 남은 과제 (우선순위 순)
1. **위 자막 구절 분할** (바로 위, 알고리즘 준비됨)
2. **실음성** — 서버에 ElevenLabs 키 없어 무음(-91dB). Gemini TTS 연결 검토.
3. **원본 중앙자막 덮기** — 일부 소스는 원본 자막이 화면 중앙이라 하단 바로 안 가려짐.

## 검증 방법 (집에서)
- 소스 예시: `C:\Users\TheRose\Downloads\source_8d49da15-*.mp4`(가지, 20s),
  `source_2_8d49da15-*.mp4`(20s). 캐시 EDL: 스크래치패드 `synctest/edl.json`(있으면).
- 로컬 렌더 후 프레임 뽑아 눈으로 확인(자막 속도·구절 끊김·장면 반복).
- `python -m pytest shopping_shorts/tests/ -q` (현재 194 통과).

## 주의
- 브랜치 **main** 고정. `git add -A` 금지(raw/ 크롤데이터 섞임) — shopping_shorts 파일만.
- 커밋 전 `git branch --show-current`=main 확인.
