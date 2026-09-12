# 장면꾸미기 추가 폰트 출처

2026-09-10에 아래 한글 폰트를 Google Fonts 공식 저장소에서 내려받았다. 모두 각 폴더의 `OFL.txt`가 명시하는 SIL Open Font License 1.1이며, 라이선스 원문은 `licenses/`에 함께 보관한다.

| 로컬 파일 | 공식 원본 |
|---|---|
| `BagelFatOne-Regular.ttf` | `google/fonts/ofl/bagelfatone` |
| `Dongle-Bold.ttf` | `google/fonts/ofl/dongle` |
| `GothicA1-Black.ttf` | `google/fonts/ofl/gothica1` |
| `Hahmlet-Variable.ttf` | `google/fonts/ofl/hahmlet` |
| `Orbit-Regular.ttf` | `google/fonts/ofl/orbit` |
| `SongMyung-Regular.ttf` | `google/fonts/ofl/songmyung` |
| `YeonSung-Regular.ttf` | `google/fonts/ofl/yeonsung` |
| `GowunDodum-Regular.ttf` | `google/fonts/ofl/gowundodum` |
| `NanumGothicCoding-Bold.ttf` | `google/fonts/ofl/nanumgothiccoding` |
| `NanumMyeongjo-ExtraBold.ttf` | `google/fonts/ofl/nanummyeongjo` |
| `GrandifloraOne-Regular.ttf` | `google/fonts/ofl/grandifloraone` |
| `MoiraiOne-Regular.ttf` | `google/fonts/ofl/moiraione` |

원본 저장소: <https://github.com/google/fonts>

## 2026-09-10 제목용 보강

| 로컬 파일 | 공식 원본 / 용도 |
|---|---|
| `Jalnan2.ttf` | GC컴퍼니 공식 잘난체 2 · 둥글고 강한 예능형 제목 |
| `JalnanGothic.ttf` | GC컴퍼니 공식 잘난체 고딕 · 네모를 채우는 굵은 제목 |
| `GasoekOne-Regular.ttf` | Google Fonts `ofl/gasoekone` · 초굵은 한글 임팩트 제목 |
| `Stylish-Regular.ttf` | Google Fonts `ofl/stylish` · 손맛이 있는 정보형 제목 |

잘난체 사용 가이드는 `licenses/Jalnan-license-guide.pdf`, OFL 원문은 각각
`licenses/GasoekOne-OFL.txt`, `licenses/Stylish-OFL.txt`에 보관한다.

무결성 및 한글 글리프 검사는 `py tools/verify_scene_fonts.py`로 실행한다.

## 2026-09-12 · 볼케이노 팩 활용

- 로컬 `.volcano/jobs/20260911_뇌전구/fonts`에서 원본 그대로 복사: `SBAggroB.ttf`, `yg-jalnan.ttf`.
- 팩 동봉 고지는 `licenses/Volcano-pack-LICENSE.txt`에 보존했다. 이를 OFL 또는 무제한 재배포 허가로 해석하지 않는다.
- 어그로체 공식 안내: https://sandbox.co.kr/assets/images/pc/aggro/SB_Aggro_Font_license.pdf (웹사이트/영상/서버 임베딩 허용, OFL 아님).
- 잘난체 공식 안내: https://image.goodchoice.kr/images/jalnan_font/jalnan-font-202004ver.pdf (파일 자체 유료 판매·임의 개작 재배포 금지).
- 이번 사용은 편집기 웹폰트 임베딩이다. 별도 폰트 판매/다운로드 팩 기능은 추가하지 않았다.
- S-CoreDream 6/7은 팩에 있지만 동봉 고지만으로 배포 조건을 확정하지 않아 이번 등록에서 제외했다. 공식 라이선스 원문 확보 후 별도 적용한다.
