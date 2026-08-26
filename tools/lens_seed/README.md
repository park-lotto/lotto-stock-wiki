# 렌즈 씨앗 → 해외 원본 발굴 재현 도구 (2026-08-21)

오용형 대본용 **해외 원본 시연 영상**을 찾는 3단계. 자세한 배경은 handoff/오용형발굴.md 2026-08-21 항목.

## 쓰는 법 (전부 서버에서 실행)

```
scp -i <키> tools/lens_seed/*.py ubuntu@43.200.48.69:/tmp/
ssh -i <키> ubuntu@43.200.48.69 "cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env; set +a; PYTHONPATH=/home/ubuntu/lotto-stock-wiki python3 /tmp/run_lens.py"
```

⚠️ **PYTHONPATH를 반드시 명시하라.** cd만 해서는 ModuleNotFoundError가 난다.

| 파일 | 하는 일 |
|---|---|
| run_lens.py | 씨앗 이미지 → imgbb 업로드 → 렌즈 검색 → /tmp/lens_out.json |
| do_grab.py | mix_basket_add + _enrich_grab + _enqueue_prewarm (담기) |
| do_script.py | get_extract → _slots_for_spine(스파인56) → spine_fill.fill (대본 조립) |

## ★씨앗 만드는 법 — 여기서 성패가 갈린다

한국 썰쇼핑 영상은 **위 40%가 가짜 앱UI+한글 자막, 아래 60%가 원본**이다.
썸네일을 그대로 넣으면 **한국 카피본만 온다**(실측: 북엔드 25건 중 19건 한국, 1위가 씨앗 자신).

```
yt-dlp -f "bv*[height<=720]+ba/b[height<=720]/b" -o "VID.%(ext)s" "https://www.youtube.com/watch?v=VID"
ffmpeg -v error -i VID.webm -ss 12 -frames:v 1 -vf "crop=iw:ih*0.42:0:ih*0.40" -q:v 2 seed.jpg -y
```

- ⚠️ `-ss`는 반드시 **-i 뒤**(출력 seek). 입력 앞에 두면 webm에서 같은 프레임만 나온다 → md5sum으로 확인
- ⚠️ **제품이 화면 대부분을 차지하는 컷**을 골라라. 실패 실측 2건:
  - 실리콘뚜껑 → 전자레인지가 커서 9건 전부 전자레인지 결과
  - 매직랩 → 아이 옷에 붙이는 장면이라 가방·모자·속옷이 섞임

## ★담을 때 — 같은 제품이어야 한다

`merge_sul` 주석 경고: **같은 소재의 영상만 합쳐라.**
서로 다른 제품을 담으면 자격 검사가 막는다(실측):

```
못 한 이유: 이 영상은 '원래 용도를 뒤집는' 오용형이 아닙니다(제품 소개·사용법 안내)
```

오용형이 요구하는 건 "결이 비슷한 제품들"이 아니라 **한 제품의 여러 용도**다.

## 예산

렌즈 1클릭 = SerpApi 최대 3회(ko/en/zh 로케일 각 1회). 잔량 확인:
`L.account_searches_left(force=True)`
