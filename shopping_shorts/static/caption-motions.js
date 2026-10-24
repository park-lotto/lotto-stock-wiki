(function (root) {
  'use strict';
  // 자막 등장 효과 계약(관제 127 자막팩) — 편집기(precision20-ui.js runCaptionEnter)·렌더러·서버 검증(scene_style.py)이 모두 이 한 곳을 읽는다.
  //   키 = 저장값(bodyCaptionMotion). label 화면 이름 · ms 한 단위 길이 · easing · frames(Web Animations 키프레임).
  //   unit: 없음 = 자막 통째로 / 'word' 어절마다 / 'char' 글자마다. stagger = 단위 사이 간격(ms), spread = 마지막 단위가 늦게 시작하는 상한(ms, 긴 자막도 이 안에 끝).
  //   spreadX: 글자마다 가운데에서 (번호-가운데)×값(em)만큼 벌어진 자리에서 모인다 — 키프레임마다 spreadK 배(없으면 0). origin: true = 자막 가운데 기준 / 문자열 = 단위마다의 기준점. boxAt: 글자 단위일 때 단어 강조 상자를 첫 글자 시작 뒤 ms×boxAt 에 켠다.
  //   ★새 효과는 transform 대신 translate·scale 을 쓴다 — 자막 칸의 가로 줄임(scaleX)·단어 '툭 커짐'(scale)을 덮지 않게.
  //   pack: true = 자막팩 관리자 스위치(caption_pack_enabled) 뒤 — 꺼진 계정 편집기에선 버튼이 안 보인다(저장값·렌더는 그대로 받는다).
  //   ★마지막 키프레임은 '효과 없는 자막'과 같은 그림이어야 한다(tools/caption_pack/check_motions.py ③⑥ 이 잰다).
  //   ★서버는 아래 JSON 표식 두 개 사이를 그대로 json 으로 읽는다 — 그 안에는 JSON 만 쓴다(주석·작은따옴표·끝 쉼표 금지).
  root.CAPTION_MOTIONS = /*JSON*/{
 "rise": {
  "label": "스윽 올라오기",
  "ms": 380,
  "easing": "cubic-bezier(.16,1,.3,1)",
  "frames": [
   {
    "opacity": 0,
    "transform": "translateY(70px)"
   },
   {
    "opacity": 1,
    "transform": "translateY(0)"
   }
  ]
 },
 "grow": {
  "label": "천천히 확대",
  "origin": true,
  "ms": 650,
  "easing": "cubic-bezier(.25,.8,.35,1)",
  "frames": [
   {
    "opacity": 0.2,
    "transform": "scale(.45)"
   },
   {
    "opacity": 1,
    "transform": "scale(1)"
   }
  ]
 },
 "pop": {
  "label": "톡 튀어나오기",
  "origin": true,
  "ms": 480,
  "easing": "linear",
  "frames": [
   {
    "opacity": 0,
    "transform": "scale(0)"
   },
   {
    "opacity": 1,
    "transform": "scale(1.3)",
    "offset": 0.45
   },
   {
    "transform": "scale(.92)",
    "offset": 0.7
   },
   {
    "transform": "scale(1.04)",
    "offset": 0.87
   },
   {
    "transform": "scale(1)"
   }
  ]
 },
 "slide": {
  "label": "옆에서 밀려오기",
  "ms": 450,
  "easing": "cubic-bezier(.2,.9,.3,1)",
  "frames": [
   {
    "opacity": 0,
    "transform": "translateX(-320px)"
   },
   {
    "opacity": 1,
    "transform": "translateX(18px)",
    "offset": 0.72
   },
   {
    "transform": "translateX(0)"
   }
  ]
 },
 "drop": {
  "label": "위에서 떨어지기",
  "ms": 560,
  "easing": "linear",
  "frames": [
   {
    "opacity": 0,
    "transform": "translateY(-160px)"
   },
   {
    "opacity": 1,
    "transform": "translateY(0)",
    "offset": 0.55
   },
   {
    "transform": "translateY(-26px)",
    "offset": 0.72
   },
   {
    "transform": "translateY(0)",
    "offset": 0.86
   },
   {
    "transform": "translateY(-6px)",
    "offset": 0.93
   },
   {
    "transform": "translateY(0)"
   }
  ]
 },
 "fade": {
  "label": "서서히 나타나기",
  "ms": 700,
  "easing": "ease-out",
  "frames": [
   {
    "opacity": 0,
    "filter": "blur(10px)"
   },
   {
    "opacity": 1,
    "filter": "blur(0)"
   }
  ]
 },
 "wide": {
  "label": "옆으로 펼치기",
  "origin": true,
  "ms": 420,
  "easing": "cubic-bezier(.2,.9,.3,1)",
  "frames": [
   {
    "opacity": 0,
    "transform": "scaleX(0)"
   },
   {
    "opacity": 1,
    "transform": "scaleX(1.12)",
    "offset": 0.7
   },
   {
    "transform": "scaleX(1)"
   }
  ]
 },
 "blurUp": {
  "label": "글자 블러 올라오기",
  "unit": "char",
  "stagger": 45,
  "spread": 700,
  "ms": 520,
  "easing": "cubic-bezier(.2,.8,.3,1)",
  "frames": [
   {
    "opacity": 0,
    "translate": "0 .85em",
    "filter": "blur(.33em)"
   },
   {
    "opacity": 1,
    "translate": "0 0",
    "filter": "blur(0)"
   }
  ],
  "boxAt": 0.35,
  "pack": true
 },
 "popBounce": {
  "label": "글자 팝 튕김",
  "unit": "char",
  "stagger": 60,
  "spread": 800,
  "ms": 800,
  "easing": "linear",
  "frames": [
   {
    "opacity": 0,
    "scale": "0",
    "offset": 0.0
   },
   {
    "opacity": 1,
    "scale": "0.509",
    "offset": 0.062
   },
   {
    "opacity": 1,
    "scale": "0.924",
    "offset": 0.125
   },
   {
    "opacity": 1,
    "scale": "1.125",
    "offset": 0.188
   },
   {
    "opacity": 1,
    "scale": "1.154",
    "offset": 0.25
   },
   {
    "opacity": 1,
    "scale": "1.1",
    "offset": 0.312
   },
   {
    "opacity": 1,
    "scale": "1.036",
    "offset": 0.375
   },
   {
    "opacity": 1,
    "scale": "0.995",
    "offset": 0.438
   },
   {
    "opacity": 1,
    "scale": "0.98",
    "offset": 0.5
   },
   {
    "opacity": 1,
    "scale": "0.983",
    "offset": 0.562
   },
   {
    "opacity": 1,
    "scale": "0.991",
    "offset": 0.625
   },
   {
    "opacity": 1,
    "scale": "0.998",
    "offset": 0.688
   },
   {
    "opacity": 1,
    "scale": "1.002",
    "offset": 0.75
   },
   {
    "opacity": 1,
    "scale": "1.003",
    "offset": 0.812
   },
   {
    "opacity": 1,
    "scale": "1.002",
    "offset": 0.875
   },
   {
    "opacity": 1,
    "scale": "1.001",
    "offset": 0.938
   },
   {
    "opacity": 1,
    "scale": "1",
    "offset": 1.0
   }
  ],
  "boxAt": 0.1,
  "pack": true
 },
 "trackIn": {
  "label": "자간 모이며 등장",
  "unit": "char",
  "spreadX": 0.55,
  "ms": 1000,
  "easing": "cubic-bezier(.25,.6,.3,1)",
  "frames": [
   {
    "opacity": 0,
    "filter": "blur(.35em)",
    "spreadK": 1
   },
   {
    "opacity": 1,
    "filter": "blur(.05em)",
    "offset": 0.5,
    "spreadK": 0.3
   },
   {
    "opacity": 1,
    "filter": "blur(0)"
   }
  ],
  "boxAt": 0.4,
  "pack": true
 },
 "riseClip": {
  "label": "아래에서 솟아오르기",
  "unit": "word",
  "stagger": 70,
  "spread": 500,
  "ms": 480,
  "easing": "cubic-bezier(.2,.9,.3,1)",
  "frames": [
   {
    "translate": "0 100%",
    "clipPath": "inset(-50% -50% 110% -50%)"
   },
   {
    "translate": "0 0",
    "clipPath": "inset(-50% -50% 0% -50%)",
    "offset": 0.99
   },
   {
    "translate": "0 0",
    "clipPath": "inset(-50% -50% -50% -50%)"
   }
  ],
  "pack": true
 },
 "slam": {
  "label": "쾅 박히기",
  "origin": true,
  "ms": 460,
  "easing": "linear",
  "frames": [
   {
    "opacity": 0,
    "translate": "0 0",
    "scale": "4",
    "easing": "cubic-bezier(.55,0,1,.45)"
   },
   {
    "opacity": 1,
    "translate": "0 0",
    "scale": "1",
    "offset": 0.3
   },
   {
    "opacity": 1,
    "translate": ".06em -.04em",
    "scale": "1",
    "offset": 0.45
   },
   {
    "opacity": 1,
    "translate": "-.05em .03em",
    "scale": "1",
    "offset": 0.6
   },
   {
    "opacity": 1,
    "translate": ".03em -.02em",
    "scale": "1",
    "offset": 0.78
   },
   {
    "opacity": 1,
    "translate": "0 0",
    "scale": "1"
   }
  ],
  "pack": true
 },
 "typing": {
  "label": "타닥타닥 타이핑",
  "unit": "char",
  "stagger": 85,
  "spread": 1100,
  "ms": 40,
  "easing": "steps(1,end)",
  "frames": [
   {
    "opacity": 0
   },
   {
    "opacity": 1
   }
  ],
  "boxAt": 1,
  "pack": true
 },
 "jelly": {
  "label": "젤리 꿀렁",
  "unit": "char",
  "stagger": 70,
  "spread": 800,
  "ms": 1000,
  "easing": "linear",
  "origin": "50% 90%",
  "frames": [
   {
    "opacity": 0,
    "translate": "0 -0.0em",
    "scale": "1.5 0.5",
    "offset": 0.0
   },
   {
    "opacity": 1,
    "translate": "0 -0.378em",
    "scale": "1.235 0.765",
    "offset": 0.05
   },
   {
    "opacity": 1,
    "translate": "0 -0.346em",
    "scale": "0.901 1.099",
    "offset": 0.1
   },
   {
    "opacity": 1,
    "translate": "0 -0.088em",
    "scale": "0.758 1.242",
    "offset": 0.15
   },
   {
    "opacity": 1,
    "translate": "0 -0.13em",
    "scale": "0.836 1.164",
    "offset": 0.2
   },
   {
    "opacity": 1,
    "translate": "0 -0.172em",
    "scale": "1.0 1.0",
    "offset": 0.25
   },
   {
    "opacity": 1,
    "translate": "0 -0.079em",
    "scale": "1.105 0.895",
    "offset": 0.3
   },
   {
    "opacity": 1,
    "translate": "0 -0.032em",
    "scale": "1.098 0.902",
    "offset": 0.35
   },
   {
    "opacity": 1,
    "translate": "0 -0.077em",
    "scale": "1.026 0.974",
    "offset": 0.4
   },
   {
    "opacity": 1,
    "translate": "0 -0.051em",
    "scale": "0.961 1.039",
    "offset": 0.45
   },
   {
    "opacity": 1,
    "translate": "0 -0.0em",
    "scale": "0.947 1.053",
    "offset": 0.5
   },
   {
    "opacity": 1,
    "translate": "0 -0.031em",
    "scale": "0.975 1.025",
    "offset": 0.55
   },
   {
    "opacity": 1,
    "translate": "0 -0.028em",
    "scale": "1.01 0.99",
    "offset": 0.6
   },
   {
    "opacity": 1,
    "translate": "0 -0.007em",
    "scale": "1.026 0.974",
    "offset": 0.65
   },
   {
    "opacity": 1,
    "translate": "0 -0.011em",
    "scale": "1.017 0.983",
    "offset": 0.7
   },
   {
    "opacity": 1,
    "translate": "0 -0.014em",
    "scale": "1.0 1.0",
    "offset": 0.75
   },
   {
    "opacity": 1,
    "translate": "0 -0.006em",
    "scale": "0.989 1.011",
    "offset": 0.8
   },
   {
    "opacity": 1,
    "translate": "0 -0.003em",
    "scale": "0.99 1.01",
    "offset": 0.85
   },
   {
    "opacity": 1,
    "translate": "0 -0.006em",
    "scale": "0.997 1.003",
    "offset": 0.9
   },
   {
    "opacity": 1,
    "translate": "0 -0.004em",
    "scale": "1.004 0.996",
    "offset": 0.95
   },
   {
    "opacity": 1,
    "translate": "0 0",
    "scale": "1 1",
    "offset": 1.0
   }
  ],
  "boxAt": 0.05,
  "pack": true
 },
 "overPop": {
  "label": "톡 넘쳤다 안착",
  "origin": true,
  "ms": 433,
  "easing": "linear",
  "frames": [
   {
    "opacity": 1,
    "scale": "0",
    "offset": 0.0
   },
   {
    "opacity": 1,
    "scale": "0.22",
    "offset": 0.077
   },
   {
    "opacity": 1,
    "scale": "0.42",
    "offset": 0.154
   },
   {
    "opacity": 1,
    "scale": "0.59",
    "offset": 0.231
   },
   {
    "opacity": 1,
    "scale": "0.75",
    "offset": 0.308
   },
   {
    "opacity": 1,
    "scale": "0.88",
    "offset": 0.385
   },
   {
    "opacity": 1,
    "scale": "0.97",
    "offset": 0.462
   },
   {
    "opacity": 1,
    "scale": "1.05",
    "offset": 0.538
   },
   {
    "opacity": 1,
    "scale": "1.09",
    "offset": 0.615
   },
   {
    "opacity": 1,
    "scale": "1.09",
    "offset": 0.692
   },
   {
    "opacity": 1,
    "scale": "1.05",
    "offset": 0.769
   },
   {
    "opacity": 1,
    "scale": "1.02",
    "offset": 0.846
   },
   {
    "opacity": 1,
    "scale": "1.007",
    "offset": 0.923
   },
   {
    "opacity": 1,
    "scale": "1",
    "offset": 1.0
   }
  ],
  "pack": true,
  "bench": "키치잇 Cs-Ka_S8nDM 0~0.433초 '1년 내내' 잉크 폭 30fps 13프레임(22%→109%→100%) — 스타일분석 §1"
 },
 "itlHookPop": {
  "label": "훅 팝+빨강 잔상(잇템로그)",
  "pack": true,
  "why": "잇템로그 ro1l 1.267~1.70초 실측(줄판독): 작게→110% 넘침 5프레임 → 가로 빨강 잔상 글리치, 총 370~433ms",
  "origin": true,
  "ms": 430,
  "easing": "linear",
  "frames": [
   {
    "opacity": 1,
    "scale": "0.55",
    "offset": 0.0
   },
   {
    "opacity": 1,
    "scale": "1.1",
    "offset": 0.38
   },
   {
    "opacity": 1,
    "scale": "1",
    "offset": 0.5
   },
   {
    "opacity": 1,
    "scale": "1",
    "offset": 1.0
   }
  ],
  "glitch": {
   "colors": [
    [
     "#FF1A1A",
     -1
    ],
    [
     "#B00000",
     1
    ]
   ],
   "amp": 0.06,
   "alpha": 0.7,
   "keys": [
    [
     0,
     0
    ],
    [
     0.6,
     0
    ],
    [
     0.68,
     1
    ],
    [
     0.85,
     0.5
    ],
    [
     1,
     0
    ]
   ]
  }
 },
 "overPopBig": {
  "label": "크게 넘쳤다 안착",
  "origin": true,
  "ms": 380,
  "easing": "linear",
  "frames": [
   {
    "opacity": 1,
    "scale": "0.3",
    "offset": 0.0
   },
   {
    "opacity": 1,
    "scale": "0.75",
    "offset": 0.1
   },
   {
    "opacity": 1,
    "scale": "1.35",
    "offset": 0.4
   },
   {
    "opacity": 1,
    "scale": "1.15",
    "offset": 0.6
   },
   {
    "opacity": 1,
    "scale": "1",
    "offset": 1.0
   }
  ],
  "pack": true,
  "bench": "꿀템노트 BpU 5.83~6.20초 '앉아보면' 0.3→1.35→1.0"
 },
 "flashIn": {
  "label": "반투명 툭",
  "ms": 66,
  "easing": "linear",
  "frames": [
   {
    "opacity": 0.45
   },
   {
    "opacity": 1
   }
  ],
  "pack": true,
  "bench": "꿀템노트 나레 BpU 1.70→1.73 · 2.60→2.63(30fps 1~2프레임)"
 },
 "typeFlash": {
  "label": "말 맞춰 타이핑(분홍 번쩍)",
  "unit": "char",
  "sync": "speech",
  "stagger": 100,
  "spread": 1600,
  "ms": 1,
  "easing": "steps(1,start)",
  "frames": [
   {
    "opacity": 0
   },
   {
    "opacity": 1
   }
  ],
  "flash": {
   "color": "#FD6B7B",
   "ms": 33
  },
  "pack": true,
  "bench": "키치잇 BRa 8.0~8.9초 0.1초마다 한 글자 · 새 글자 첫 프레임 분홍"
 },
 "typeGlow": {
  "label": "말 맞춰 타이핑(초록 번짐)",
  "unit": "char",
  "sync": "speech",
  "stagger": 80,
  "spread": 1400,
  "ms": 33,
  "easing": "steps(1,start)",
  "frames": [
   {
    "opacity": 0
   },
   {
    "opacity": 1
   }
  ],
  "glow": {
   "color": "#2B5C2B",
   "blur": [
    0.12,
    0.28
   ],
   "keys": [
    [
     0,
     0
    ],
    [
     0.35,
     1
    ],
    [
     0.8,
     1
    ]
   ]
  },
  "pack": true,
  "bench": "스타픽룸 VbpdN 6.7~10.3초 12.5자/초 · 외곽선 밖 초록 번짐(끝 세기 0.35 = 팩 나레 글자 그림자)"
 },
 "typeCursor": {
  "label": "말 맞춰 타이핑(_ 커서)",
  "unit": "char",
  "sync": "speech",
  "stagger": 85,
  "spread": 1400,
  "ms": 100,
  "easing": "ease-out",
  "frames": [
   {
    "opacity": 0.6,
    "filter": "blur(0.08em)",
    "scale": "1.15"
   },
   {
    "opacity": 1,
    "filter": "blur(0em)",
    "scale": "1"
   }
  ],
  "follow": {
   "char": "_",
   "color": "#FFFFFF",
   "at": "after",
   "gap": 0.15,
   "size": 1,
   "blink": 400,
   "until": "scene"
  },
  "pack": true,
  "bench": "스타픽룸 ASqF 3.6~6.0초 새 글자 흐림→또렷 · 끝에 '_' 400ms 깜빡"
 },
 "typeHeart": {
  "label": "말 맞춰 타이핑(분홍 하트)",
  "unit": "char",
  "sync": "speech",
  "stagger": 100,
  "spread": 1400,
  "ms": 150,
  "easing": "cubic-bezier(.2,.9,.3,1)",
  "frames": [
   {
    "opacity": 0,
    "scale": "0.55",
    "color": "#F40059",
    "offset": 0
   },
   {
    "opacity": 1,
    "scale": "0.55",
    "color": "#F40059",
    "offset": 0.01
   },
   {
    "opacity": 1,
    "scale": "1"
   }
  ],
  "follow": {
   "char": "♥",
   "color": "#F40059",
   "outline": "#FFFFFF",
   "at": "below",
   "gap": 0.95,
   "size": 0.55,
   "until": "typed",
   "hold": 200
  },
  "pack": true,
  "bench": "스타픽룸 dKcz 5.9~6.6초 새 글자 분홍 작게→흰 원크기 · 그 글자 밑 분홍 하트"
 },
 "rgbGlitch": {
  "label": "RGB 글리치",
  "ms": 430,
  "easing": "linear",
  "frames": [
   {
    "opacity": 1
   },
   {
    "opacity": 1
   }
  ],
  "glitch": {
   "colors": [
    [
     "#FF2D55",
     -1
    ],
    [
     "#FFE600",
     -0.5
    ],
    [
     "#00E676",
     0.5
    ],
    [
     "#00B0FF",
     1
    ]
   ],
   "amp": 0.2,
   "alpha": 1,
   "keys": [
    [
     0,
     0
    ],
    [
     0.23,
     0
    ],
    [
     0.35,
     0.5
    ],
    [
     0.53,
     1
    ],
    [
     0.65,
     1
    ],
    [
     0.77,
     0.4
    ],
    [
     0.93,
     0.1
    ],
    [
     1,
     0
    ]
   ]
  },
  "pack": true,
  "bench": "스타픽룸 VbpdN 1.37~1.80초 '땅콩버터에...' 30fps 프레임 실측 — 0.43초 · 빨강·하늘 번짐 ±7px(글자 62px의 0.11em) · 정지 그림엔 번짐 없음"
 },
 "wipeRTL": {
  "label": "오른쪽에서 닦아 나오기",
  "ms": 400,
  "msPerChar": 47,
  "msMin": 250,
  "msMax": 700,
  "easing": "linear",
  "wipe": "rtl",
  "frames": [
   {
    "opacity": 1
   },
   {
    "opacity": 1
   }
  ],
  "pack": true,
  "bench": "스타픽룸 VbpdN 17.37~17.70 '가르쳐 드려요?'(8자 0.33초) · EZQl 3.37~4.00 '보쌈 식당인데요 완전'(12자 0.63초) = 글자(공백 뺀)당 약 47ms · 오른쪽 끝 고정, 왼쪽으로 드러남"
 },
 "rainbowCycle": {
  "label": "글자마다 무지개 돌림",
  "unit": "char",
  "stagger": 0,
  "ms": 1,
  "easing": "linear",
  "frames": [
   {
    "opacity": 1
   },
   {
    "opacity": 1
   }
  ],
  "cycle": {
   "colors": [
    "#0795FC",
    "#FAED07",
    "#FFFFFF",
    "#FB5806"
   ],
   "ms": 250,
   "phase0": 3
  },
  "pack": true,
  "bench": "스타픽룸 j5D 0.2~1.0초 '최화정이 만들자마자' 30fps — 파랑 #0795FC→노랑 #FAED07→흰→주황 #FB5806, 250ms마다 한 칸, 글자마다 한 칸씩 어긋남",
  "boxAt": 0
 },
 "shake": {
  "label": "덜덜 흔들림",
  "ms": 360,
  "easing": "linear",
  "frames": [
   {"opacity": 1, "translate": "0em 0em", "offset": 0.0},
   {"opacity": 1, "translate": "0.2em 0em", "offset": 0.1},
   {"opacity": 1, "translate": "-0.2em 0em", "offset": 0.25},
   {"opacity": 1, "translate": "0.14em 0em", "offset": 0.4},
   {"opacity": 1, "translate": "-0.14em 0em", "offset": 0.55},
   {"opacity": 1, "translate": "0.08em 0em", "offset": 0.7},
   {"opacity": 1, "translate": "-0.04em 0em", "offset": 0.85},
   {"opacity": 1, "translate": "0em 0em", "offset": 1.0}
  ],
  "pack": true,
  "bench": "등장 흔들림(관제 235 요청서 5) — 좌우로 줄어드는 떨림, 끝은 제자리. 크기는 spec.amp(0.2em 기준 배수)로. 벤치 실측 수치는 요청서에 없음(스타픽룸 '다른 등장' 줄에 이름만)"
 },
 "glPop": {
  "label": "굿레터 빠른 톡",
  "origin": true,
  "ms": 175,
  "easing": "linear",
  "frames": [
   {
    "opacity": 1,
    "scale": "0.28",
    "offset": 0.0
   },
   {
    "opacity": 1,
    "scale": "0.55",
    "offset": 0.2
   },
   {
    "opacity": 1,
    "scale": "0.80",
    "offset": 0.4
   },
   {
    "opacity": 1,
    "scale": "1.08",
    "offset": 0.6
   },
   {
    "opacity": 1,
    "scale": "1.12",
    "offset": 0.68
   },
   {
    "opacity": 1,
    "scale": "1.04",
    "offset": 0.85
   },
   {
    "opacity": 1,
    "scale": "1",
    "offset": 1.0
   }
  ],
  "pack": true,
  "bench": "굿레터 60fps 실측: 753r 27→110%(0.117초)→100%(0.183초) · vcb 26%→110%@0.100→100%@0.167 · sMx9 2.98~3.13 — 가운데 기준, 불투명 시작, 모든 말 조각에 붙음"
 }
}/*JSON*/;
  // 자막 스타일(관제 127 → 144) — 자막 모양 한 벌. 움직임은 아래 등장 효과팩(CAPTION_MOTION_PACKS)이 맡는다(10-06 사장님 '폰트나 설정 그대로 두고 효과만').
  //   ★자막팩 = 자막 한 벌 완성형(10-05 사장님 "움직임뿐 아니라 색상·폰트크기·강조단어·밑줄·동그라미까지 한 번에"). 자막에만 건다(제목·채널명은 그대로).
  //   font 자막 글꼴(편집기에 실린 글꼴 이름) · size 자막 기본 크기(%) · look 자막 상자(CAPTION_LOOKS 번호 또는 'none')
  //   text.color 글자색 · text.style 글자 꾸밈(테두리·그림자, em 단위 — 미리보기·렌더 크기가 달라도 같은 비율)
  //   wordFx: 팩을 누를 때 같이 켜 주는 단어 강조(방식·색·커짐). 저장은 wordFx 따로 — 고객이 나중에 바꿀 수 있다.
  //   emph: 영상 위 강조 자막(장면효과팩 '어둡게 강조' 장면의 가운데 큰 글자) 모양 — font·size(자막 대비 %)·color·style. 등장은 효과팩의 emph 칸.
  //         언제·어디(어둡게·가운데 자리)는 장면효과팩(관제 124), 모양은 여기(10-05 사장님 "영상 중간에 들어가는 자막들도 효과 좋은 걸로").
  //   ★우선순위: 고객이 직접 바꾼 값(상자 모양·크기·색) > 팩 > 템플릿 기본. 판단은 precision20-ui.js captionPackStyle 한 곳.
  //   ★서버는 PACKS 표식 두 개 사이를 json 으로 읽는다(scene_style.caption_pack_keys) — 그 안에는 JSON 만.
  root.CAPTION_PACKS = /*PACKS*/{
 "tension": {
  "label": "예능 텐션",
  "desc": "굵은 흰 글씨 + 노란 상자 · 통통 튀는 등장",
  "font": "SBAggroB",
  "size": 112,
  "look": "none",
  "text": {
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.07em #000",
    "paintOrder": "stroke fill",
    "textShadow": "0 0.05em 0.1em rgba(0,0,0,.7)"
   }
  },
  "wordFx": {
   "style": "box",
   "color": "#FFE600",
   "grow": "pop"
  },
  "emph": {
   "font": "SBAggroB",
   "size": 135,
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.06em #000",
    "paintOrder": "stroke fill",
    "textShadow": "0 0.06em 0.18em rgba(0,0,0,.85)"
   }
  }
 },
 "clean": {
  "label": "깔끔 정보",
  "desc": "흰 띠 위 검은 글씨 + 분홍 밑줄",
  "font": "GmarketSansBold",
  "size": 100,
  "look": 0,
  "text": {
   "color": "#111111"
  },
  "wordFx": {
   "style": "underline",
   "color": "#FF2D6F",
   "grow": ""
  },
  "emph": {
   "font": "GmarketSansBold",
   "size": 150,
   "color": "#FFFFFF",
   "style": {
    "textShadow": "0 0.05em 0.25em rgba(0,0,0,.9),0 0 0.6em rgba(0,0,0,.5)"
   }
  }
 },
 "premium": {
  "label": "고급 리뷰",
  "desc": "명조 금색 글씨 + 네이비 금테 · 차분한 등장",
  "font": "NanumMyeongjoEB",
  "size": 100,
  "look": 7,
  "text": {
   "color": "#F6E7B8"
  },
  "wordFx": {
   "style": "glow",
   "color": "#D9B45A",
   "grow": ""
  },
  "emph": {
   "font": "NanumMyeongjoEB",
   "size": 150,
   "color": "#F6E7B8",
   "style": {
    "textShadow": "0 0 0.25em rgba(217,180,90,.65),0 0.05em 0.2em rgba(0,0,0,.9)"
   }
  }
 },
 "story": {
  "label": "썰 이야기",
  "desc": "주아체 흰 글씨 + 노란 동그라미 · 타닥타닥",
  "font": "BMJUA",
  "size": 108,
  "look": "none",
  "text": {
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.07em #000",
    "paintOrder": "stroke fill",
    "textShadow": "0 0.05em 0.1em rgba(0,0,0,.7)"
   }
  },
  "wordFx": {
   "style": "circle",
   "color": "#FFE600",
   "grow": ""
  },
  "emph": {
   "font": "BMJUA",
   "size": 135,
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.06em #000",
    "paintOrder": "stroke fill",
    "textShadow": "0 0.06em 0.18em rgba(0,0,0,.85)"
   }
  }
 },
 "deal": {
  "label": "핫딜 가격",
  "desc": "검은고딕 + 노란 형광펜 · 쾅 박히는 가격",
  "font": "BlackHanSans",
  "size": 110,
  "look": "none",
  "text": {
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.07em #000",
    "paintOrder": "stroke fill",
    "textShadow": "0 0.05em 0.1em rgba(0,0,0,.7)"
   }
  },
  "wordFx": {
   "style": "highlight",
   "color": "#FFE600",
   "grow": "hold"
  },
  "emph": {
   "font": "BlackHanSans",
   "size": 140,
   "color": "#FFE600",
   "style": {
    "WebkitTextStroke": "0.06em #000",
    "paintOrder": "stroke fill",
    "textShadow": "0 0.06em 0.18em rgba(0,0,0,.85)"
   }
  }
 },
 "soft": {
  "label": "감성 손글씨",
  "desc": "손글씨 + 종이 카드 + 주황 동그라미",
  "font": "GaeguBold",
  "size": 108,
  "look": 4,
  "text": {
   "color": "#3A2A1A"
  },
  "wordFx": {
   "style": "circle",
   "color": "#FF8A1F",
   "grow": ""
  },
  "emph": {
   "font": "GaeguBold",
   "size": 150,
   "color": "#FFFFFF",
   "style": {
    "textShadow": "0 0.05em 0.25em rgba(0,0,0,.9),0 0 0.6em rgba(0,0,0,.5)"
   }
  }
 },
 "kitchit": {
  "label": "키치잇 연예인템",
  "desc": "흰 둥근 굵은 글 + 검정·흰 두 겹 테 · 핵심 단어 5색 돌림 · 줄 첫 덩어리만 톡",
  "font": "Jalnan2",
  "size": 78,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.2em #151618",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   },
   "ring": {
    "color": "#FFFFFF",
    "width": 0.03
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#FEDD00",
    "#00FD0B",
    "#65FEFB",
    "#FD6B7B",
    "#BDB4FC"
   ]
  },
  "emph": {
   "font": "Jalnan2",
   "size": 120,
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.2em #151618",
    "paintOrder": "stroke fill"
   }
  },
  "motion": {
   "first": "overPop",
   "body": "overPop",
   "cont": "",
   "price": "overPop",
   "problem": "overPop",
   "reveal": "overPop",
   "end": "overPop",
   "emph": "overPop"
  },
  "variants": {
   "cut": {"enter": "", "why": "줄 첫 덩어리인데 벤치가 컷으로 넣은 곳(배치 규칙 placement.place, 관제 097)"},
   "pop": {"enter": "overPop", "why": "같은 줄 안 덩어리인데 벤치가 팝으로 넣은 곳(배치 규칙)"},
   "typing": {
    "enter": "typeFlash",
    "place": {
     "y": 67.71,
     "bench": "BRa 8.5초 원음 타이핑 줄 가운데 y≈1300"
    },
    "size": 100
   }
  },
  "stickers": {
   "heart": {
    "follow": {
     "char": "♥",
     "color": "#E8195E",
     "at": "below",
     "gap": 0.95,
     "size": 0.8,
     "until": "typed",
     "hold": 300
    }
   }
  },
  "bench": "channel/kitchit/자막팩_보강안.json · 스타일분석.md §1",
  "place": {
   "y": 70.36,
   "bench": "y1351/1920 — 스타일분석 §1 8편 같음"
  }
 },
 "kkultemnote": {
  "label": "꿀템노트 수다",
  "desc": "원음 꾸불림 손글씨 · 나레 굵은 고딕 + 노랑 강조 · 말한 사람마다 글꼴이 바뀐다",
  "font": "Kkubulim",
  "size": 79,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.05em #000",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#FDF60E"
   ]
  },
  "emph": {
   "font": "Kkubulim",
   "size": 120,
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.12em #000",
    "paintOrder": "stroke fill",
    "textShadow": "0 0 0.12em rgba(255,255,255,.9)"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": "overPopBig"
  },
  "speakers": {
   "narr": {
    "font": "Scene1369",
    "size": 83,
    "text": {
     "color": "#FFFFFF",
     "style": {
      "WebkitTextStroke": "0.08em #000",
      "paintOrder": "stroke fill",
      "textShadow": "0 0 0.06em rgba(0,0,0,.6)"
     }
    },
    "enter": "flashIn"
   },
   "orig": {
    "enter": ""
   }
  },
  "variants": {
   "cut": {"enter": "", "why": "나레 덩어리를 벤치가 컷으로 넣은 곳(배치 규칙 placement.place, 관제 097)"},
   "orig_pop": {
    "size": 115,
    "text": {
     "color": "#FFFFFF",
     "style": {
      "WebkitTextStroke": "0.16em #6E6E6E",
      "paintOrder": "stroke fill"
     }
    },
    "enter": "overPopBig"
   },
   "orig_red": {
    "size": 107,
    "text": {
     "color": "#F51814",
     "style": {
      "WebkitTextStroke": "0.1em #000",
      "paintOrder": "stroke fill",
      "letterSpacing": "0.18em"
     }
    },
    "enter": ""
   }
  },
  "bench": "channel/kkultemnote/자막팩_보강안.json",
  "place": {
   "y": 66.98,
   "bench": "y1245~1328 가운데 1286/1920 — 8편 중 7편"
  }
 },
 "starpick": {
  "label": "스타픽룸 타이핑",
  "desc": "흰 G마켓 굵은 글 + 두꺼운 검정 테 · 나레만 타닥 타이핑(초록 번짐) · 원음은 즉시 · 재료 낱말은 사물 색",
  "font": "GmarketSansBold",
  "size": 72,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.22em #000",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#FEFD02"
   ]
  },
  "emph": {
   "font": "GmarketSansBold",
   "size": 130,
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.22em #000",
    "paintOrder": "stroke fill"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": "pop"
  },
  "speakers": {
   "narr": {
    "text": {
     "style": {
      "textShadow": "0 0 0.12em rgba(43,92,43,.35),0 0 0.28em rgba(43,92,43,.35)"
     }
    },
    "enter": "typeGlow"
   },
   "orig": {
    "enter": ""
   }
  },
  "variants": {
   "cut": {"enter": "", "why": "나레 덩어리를 벤치가 한 번에 넣은 곳(배치 규칙 placement.place, 관제 097)"},
   "pop": {"enter": "pop", "why": "원음 덩어리를 벤치가 작게→크게로 넣은 곳(배치 규칙)"},
   "cursor": {
    "enter": "typeCursor",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   },
   "heart": {
    "enter": "typeHeart",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   },
   "glitch": {
    "enter": "rgbGlitch",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   },
   "wipe": {
    "enter": "wipeRTL",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   },
   "rainbow": {
    "enter": "rainbowCycle",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   }
  },
  "bench": "channel/starpickroom/자막팩_보강안.json",
  "place": {
   "y": 59.38,
   "bench": "y1105~1175 가운데 1140/1920 — 8편 같음, 나레·원음 같은 자리"
  }
 },
 "recipe": {
  "label": "연예인레시피 타이핑",
  "desc": "흰 잘난고딕 + 진갈색 테 · 나레만 타닥 타이핑 · 원음은 즉시 · 재료 낱말은 사물 색 — 스타픽룸 타이핑의 변형(자리·글꼴·테만 다름)",
  "font": "JalnanGothic",
  "size": 72,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.15em #2B1708",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#FEFD02"
   ]
  },
  "emph": {
   "font": "JalnanGothic",
   "size": 130,
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.15em #2B1708",
    "paintOrder": "stroke fill"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": "pop"
  },
  "speakers": {
   "narr": {
    "text": {
     "style": {
      "textShadow": "0 0 0.12em rgba(43,92,43,.35),0 0 0.28em rgba(43,92,43,.35)"
     }
    },
    "enter": "typeGlow"
   },
   "orig": {
    "enter": ""
   }
  },
  "variants": {
   "cut": {
    "enter": "",
    "why": "나레 덩어리를 벤치가 한 번에 넣은 곳(배치 규칙 placement.place, 관제 097)"
   },
   "pop": {
    "enter": "pop",
    "why": "원음 덩어리를 벤치가 작게→크게로 넣은 곳(배치 규칙)"
   },
   "cursor": {
    "enter": "typeCursor",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   },
   "heart": {
    "enter": "typeHeart",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   },
   "glitch": {
    "enter": "rgbGlitch",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   },
   "wipe": {
    "enter": "wipeRTL",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   },
   "rainbow": {
    "enter": "rainbowCycle",
    "text": {
     "style": {
      "textShadow": "none"
     }
    }
   }
  },
  "bench": "starpick 변형 — tools/calcopy/hybrid/styles/연예인레시피판.json (벤치 값 → 우리 값 note)",
  "place": {
   "y": 75.0,
   "bench": "starpick y59.38(창 안 1140) → 창 아래 검정 띠 1440/1920 (연예인레시피판 창 y400~1340)"
  },
  "why": {
   "font": "GmarketSansBold → JalnanGothic(같은 둥근 굵은 고딕 결, 다른 글꼴)",
   "stroke": "0.22em #000 → 0.15em #2B1708(얇은 진갈색)",
   "place": "창 안 y1140 → 창 아래 y1440"
  }
 },
 "goodletter": {
  "label": "굿레터 레시피 팝",
  "desc": "흰 둥근 굵은 글 + 검정 테 · 말 조각마다 빠른 톡(0.17초) · 강조 줄은 줄 전체 호박색(옛 틀은 주황·노랑·민트) · 스티커 없음",
  "font": "BinggraeBold",
  "size": 76,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FDFDFD",
   "style": {
    "WebkitTextStroke": "0.17em #000000",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#FCB53F"
   ]
  },
  "emph": {
   "font": "BinggraeBold",
   "size": 150,
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.17em #000000",
    "paintOrder": "stroke fill"
   }
  },
  "motion": {
   "first": "glPop",
   "body": "glPop",
   "cont": "glPop",
   "price": "glPop",
   "problem": "glPop",
   "reveal": "glPop",
   "end": "glPop",
   "emph": ""
  },
  "variants": {
   "hi": {
    "text": {
     "color": "#FCB53F"
    },
    "why": "새 틀 강조 줄 = 줄 전체 호박색(sMx9 #FCB53F·vcb #F6B644·753r #F2BD50) — 배치 = 판 설정 placement(말 줄 23~34%·끝 줄·훅 첫 색)"
   },
   "orange": {
    "text": {
     "color": "#FD7901"
    },
    "why": "옛 틀 주황 = 재료 낱말·수치·반문 펀치"
   },
   "yellow": {
    "text": {
     "color": "#FDD946"
    },
    "why": "옛 틀 노랑 = 감탄·맛 반응"
   },
   "mint": {
    "text": {
     "color": "#57E4D0"
    },
    "why": "옛 틀 민트 = 요령·답·제품명"
   },
   "big": {
    "enter": "",
    "size": 175,
    "why": "수량 큰글 — 흰 큰 글 + 숫자 노랑(mark #FDE675), 컷과 즉시(sMx9 13.41)"
   },
   "label": {
    "enter": "",
    "text": {
     "color": "#F9E04B"
    },
    "size": 62,
    "place": {
     "y": 65.0,
     "bench": "제품 이름 자막 y1212~1285(옛 틀 kfmZ·E6SX·m4m5) — 말 자막보다 위"
    },
    "why": "끝 제품 이름 자막: 노랑 작은 굵은 글, 컷과 즉시, 끝까지 유지 + 효과음 한 발(impact-bass/pop) 뒤 무음"
   }
  },
  "stickers": {},
  "bench": "channel/goodletter/자막팩_보강안.json · 스타일분석.md §3",
  "place": {
   "y": 68.75,
   "bench": "새 틀 자막 잉크 가운데 y≈1320/1920(sMx9 1288~1353) · 옛 틀은 y≈1396(72.7%) — 판 설정 frame 이 틀마다 덮는다"
  }
 },
 "ititemlog": {
  "label": "잇템로그 화자색",
  "desc": "굵은 고딕 + 두꺼운 검정 테 · 화자마다 색(나레 노랑·원음 흰) · 전부 즉시 · 편 첫 나레 줄만 빨강, 그 끝 덩어리 팝+빨강 잔상",
  "font": "GmarketSansBold",
  "size": 84,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FDFCFD",
   "style": {
    "WebkitTextStroke": "0.24em #000000",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#F07A09"
   ]
  },
  "emph": {
   "font": "GmarketSansBold",
   "size": 84,
   "color": "#F07A09",
   "style": {
    "WebkitTextStroke": "0.24em #000000",
    "paintOrder": "stroke fill"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "speakers": {
   "narr": {
    "text": {
     "color": "#F7EB0E"
    },
    "enter": ""
   },
   "orig": {
    "enter": ""
   }
  },
  "variants": {
   "hook": {
    "text": {
     "color": "#E30004"
    },
    "enter": "",
    "why": "훅 나레 빨강(ro1l #E30004 · aUic #DA0009) — 편 첫 나레 줄 덩어리 전부(판 설정 placement.rules.hook)"
   },
   "hook_pop": {
    "text": {
     "color": "#E30004"
    },
    "enter": "itlHookPop",
    "why": "훅 줄 끝 덩어리 팝+빨강 잔상(ro1l 1.27초 · aUic 0.70초)"
   }
  },
  "stickers": {},
  "bench": "channel/ititemlog/스타일분석.md §2 · 줄판독/",
  "place": {
   "y": 67.34,
   "bench": "채움 잉크 y≈1249~1338(가운데 1293/1920) — 2편 같음, 나레·원음 같은 자리"
  }
 },
 "banggu": {
  "label": "방구석 게시글",
  "desc": "검정 굵은 고딕 · 외곽·상자 없음 · 줄 간격 78 · 전부 즉시",
  "font": "CcPretendard-Bold",
  "size": 60.5,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#000000",
   "style": {
    "textShadow": "none",
    "lineHeight": "1.377"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "emph": {
   "font": "CcPretendard-Bold",
   "size": 150,
   "color": "#000000",
   "style": {
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/banggu/줄판독(6편 121줄)·스타일분석.md §1 · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 27.48,
   "bench": "첫 줄 잉크 y504~551(가운데 527/1920) — 2줄째 582~630, 쌓기 자리는 판 caption.stack(y·pitch)이 덮는다"
  }
 },
 "yummyknow": {
  "label": "맛있는친구들 게시글",
  "desc": "배민 도현 검정 · 외곽 없음 · 줄 간격 89 · 전부 즉시",
  "font": "BMDOHYEON",
  "size": 74.4,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#000000",
   "style": {
    "textShadow": "none",
    "lineHeight": "1.313"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "emph": {
   "font": "BMDOHYEON",
   "size": 150,
   "color": "#000000",
   "style": {
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/yummyknow/줄판독(6편 195줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 31.86,
   "bench": "첫 줄 잉크 y578~631(가운데 605/1920) — 2줄째 668~721"
  }
 },
 "humorshowshow": {
  "label": "재밌쇼 게시글",
  "desc": "검정 굵은 고딕 · 외곽 없음 · 줄 간격 76 · 전부 즉시",
  "font": "NotoSansKRBold",
  "size": 60.8,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#000000",
   "style": {
    "textShadow": "none",
    "lineHeight": "1.338"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#9E3023"
   ]
  },
  "emph": {
   "font": "NotoSansKRBold",
   "size": 150,
   "color": "#000000",
   "style": {
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/humorshowshow/줄판독(6편 190줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 27.2,
   "bench": "첫 줄 잉크 y500~552(가운데 526/1920) — 2줄째 576~629"
  }
 },
 "hottemreport": {
  "label": "핫템리포트 흰 굵은 고딕",
  "desc": "흰 굵은 고딕 + 두꺼운 검정 테(13px) · 전부 즉시",
  "font": "PretendardXBold",
  "size": 105.7,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.246em #000000",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "emph": {
   "font": "PretendardXBold",
   "size": 150,
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.246em #000000",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/hottemreport/줄판독(6편 123줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 73.19,
   "bench": "나레 잉크 y1360~1448(가운데 1404/1920)"
  }
 },
 "sinbak": {
  "label": "신박발견 손글씨",
  "desc": "둥근 손글씨풍 검정 + 흰 2px 테 · 넓은 띄어쓰기 · 전부 즉시",
  "font": "BMJUA",
  "size": 72,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#000000",
   "style": {
    "WebkitTextStroke": "0.0556em #FFFFFF",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none",
    "wordSpacing": "0.45em"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#038EFA",
    "#EEC816",
    "#F80A50"
   ]
  },
  "emph": {
   "font": "BMJUA",
   "size": 150,
   "color": "#000000",
   "style": {
    "WebkitTextStroke": "0.0556em #FFFFFF",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/sinbak/줄판독(6편 95줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 69.6,
   "bench": "잉크 y1299~1364(가운데 1331/1920)"
  }
 },
 "uljimatrot": {
  "label": "울지마트로트 흰 고딕",
  "desc": "흰 G마켓 굵은 글 + 검정 테(10px) · 줄 간격 105 · 전부 즉시",
  "font": "GmarketSansBold",
  "size": 89.9,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.2225em #000000",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none",
    "lineHeight": "1.168"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "emph": {
   "font": "GmarketSansBold",
   "size": 150,
   "color": "#FFFFFF",
   "style": {
    "WebkitTextStroke": "0.2225em #000000",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/uljimatrot/줄판독(10편 144줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 63.42,
   "bench": "잉크 y1162~1252(가운데 1207/1920)"
  }
 },
 "mantem": {
  "label": "만템 화자색",
  "desc": "원음 흰 G마켓 + 검정 테 5px · 나레 노랑 카페24 아네모네 기울임(위 줄 자리) · 전부 즉시",
  "font": "GmarketSansBold",
  "size": 64.9,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FDFCFD",
   "style": {
    "WebkitTextStroke": "0.1541em #000000",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#F891B8",
    "#A8FFE6",
    "#B0FFC3",
    "#F9F98F"
   ]
  },
  "emph": {
   "font": "GmarketSansBold",
   "size": 150,
   "color": "#FDFCFD",
   "style": {
    "WebkitTextStroke": "0.1541em #000000",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "speakers": {
   "narr": {
    "font": "Cafe24Ohsquare",
    "size": 74.3,
    "text": {
     "color": "#F5FF16",
     "style": {
      "WebkitTextStroke": "0.1346em #000000",
      "fontStyle": "italic"
     }
    },
    "place": {
     "y": 64.9,
     "bench": "나레 잉크 y1195~1290(편마다 1223~1255)"
    },
    "enter": ""
   },
   "orig": {
    "enter": ""
   }
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/mantem/줄판독(6편 원음 93·나레 24줄)·스타일분석.md §1 · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 71.0,
   "bench": "원음 잉크 y1321~1390(가운데 1355/1920)"
  }
 },
 "itemhome": {
  "label": "아이템홈 어그로",
  "desc": "흰 어그로체 + 검정 테 4px · 전부 즉시",
  "font": "SBAggroB",
  "size": 79.4,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FCFAFA",
   "style": {
    "WebkitTextStroke": "0.1008em #000000",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#F4F91E",
    "#F9B4C0",
    "#EA2634"
   ]
  },
  "emph": {
   "font": "SBAggroB",
   "size": 150,
   "color": "#FCFAFA",
   "style": {
    "WebkitTextStroke": "0.1008em #000000",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/itemhome/줄판독(6편 214줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 66.3,
   "bench": "잉크 y1228~1303(가운데 1265/1920)"
  }
 },
 "annapick": {
  "label": "안나픽 흰 고딕",
  "desc": "흰 G마켓 굵은 글 + 검정 테 5px · 기본 즉시, 일부 줄 서서히(fade)",
  "font": "GmarketSansBold",
  "size": 75.6,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FFFFFD",
   "style": {
    "WebkitTextStroke": "0.1323em #000000",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#F1FF11",
    "#F5FF50",
    "#A7F907"
   ]
  },
  "emph": {
   "font": "GmarketSansBold",
   "size": 150,
   "color": "#FFFFFD",
   "style": {
    "WebkitTextStroke": "0.1323em #000000",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {
   "fade": {
    "enter": "fade",
    "why": "벤치 등장 fade 13.7%(18줄) — 판 배치 규칙이 고른 줄만"
   }
  },
  "stickers": {},
  "bench": "channel/annapick/줄판독(6편 원음 104·나레 19줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 63.2,
   "bench": "원음 잉크 가운데 y1207/1920(줄판독 중앙 — 편마다 1110~1210)"
  }
 },
 "sseolpulda_a": {
  "label": "썰풀다 자막만형",
  "desc": "검정 스포카 굵은 글(흰 바탕 아래) · 외곽 없음 · 전부 즉시",
  "font": "CcSpoqaHanSansNeo-Bold",
  "size": 64.4,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#000000",
   "style": {
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "emph": {
   "font": "CcSpoqaHanSansNeo-Bold",
   "size": 150,
   "color": "#000000",
   "style": {
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/sseolpulda/줄판독(자막만 3편 18줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 78.17,
   "bench": "자막만형 잉크 y1468~1528(가운데 1498/1920, ZdeZ)"
  }
 },
 "sseolpulda_b": {
  "label": "썰풀다 나레형",
  "desc": "흰 G마켓 굵은 글 + 검정 테 7px · 전부 즉시",
  "font": "GmarketSansBold",
  "size": 80.8,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FFFDFD",
   "style": {
    "WebkitTextStroke": "0.1733em #000000",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#F278C9"
   ]
  },
  "emph": {
   "font": "GmarketSansBold",
   "size": 150,
   "color": "#FFFDFD",
   "style": {
    "WebkitTextStroke": "0.1733em #000000",
    "paintOrder": "stroke fill",
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/sseolpulda/줄판독(나레 3편 48줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 66.77,
   "bench": "나레형 잉크 y1229~1317(가운데 1273/1920, mYxu)"
  }
 },
 "hotpeople": {
  "label": "뜨거운사람들 주아",
  "desc": "배민 주아 검정 · 외곽 없음 · 2줄 행 간격 80 · 덩어리 세로 가운데 · 전부 즉시",
  "font": "BMJUA",
  "size": 74.7,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#000000",
   "style": {
    "textShadow": "none",
    "lineHeight": "1.158"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#E71D21",
    "#F4FE01"
   ]
  },
  "emph": {
   "font": "BMJUA",
   "size": 150,
   "color": "#000000",
   "style": {
    "textShadow": "none"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "variants": {},
  "stickers": {},
  "bench": "channel/hotpeople/줄판독(6편 156줄) · 렌더 실측 맞춤(tools/caption_pack/check_kal_new_packs.py — 벤치 프레임 같은 글로 렌더해 kal_analyze frame_metrics 잉크 상자 대조)",
  "place": {
   "y": 70.7,
   "bench": "덩어리 가운데 y≈1350(1줄 1318~1376 · 2줄 1287~1425)"
  }
 },
 "ititemlog_v2": {
  "label": "잇템로그 화자색(업그레이드)",
  "desc": "굵은 고딕 + 두꺼운 검정 테 · 화자마다 색(나레 노랑·원음 흰) · 전부 즉시 · 편 첫 나레 줄만 빨강, 그 끝 덩어리 팝+빨강 잔상 · 강조 색 후보 5개(훅 빨강 줄에도 강조가 남게)",
  "font": "GmarketSansBold",
  "size": 84,
  "flat": true,
  "look": "none",
  "text": {
   "color": "#FDFCFD",
   "style": {
    "WebkitTextStroke": "0.24em #000000",
    "paintOrder": "stroke fill",
    "strokeLinejoin": "round",
    "textShadow": "none"
   }
  },
  "wordFx": {
   "style": "mark",
   "color": "",
   "grow": ""
  },
  "mark": {
   "colors": [
    "#F07A09",
    "#E78DC3",
    "#E23F9A",
    "#FFFFFF",
    "#F7EB0E"
   ]
  },
  "emph": {
   "font": "GmarketSansBold",
   "size": 84,
   "color": "#F07A09",
   "style": {
    "WebkitTextStroke": "0.24em #000000",
    "paintOrder": "stroke fill"
   }
  },
  "motion": {
   "first": "",
   "body": "",
   "cont": "",
   "price": "",
   "problem": "",
   "reveal": "",
   "end": "",
   "emph": ""
  },
  "speakers": {
   "narr": {
    "text": {
     "color": "#F7EB0E"
    },
    "enter": ""
   },
   "orig": {
    "enter": ""
   }
  },
  "variants": {
   "hook": {
    "text": {
     "color": "#E30004"
    },
    "enter": "",
    "why": "훅 나레 빨강(ro1l #E30004 · aUic #DA0009) — 편 첫 나레 줄 덩어리 전부(판 설정 placement.rules.hook)"
   },
   "hook_pop": {
    "text": {
     "color": "#E30004"
    },
    "enter": "itlHookPop",
    "why": "훅 줄 끝 덩어리 팝+빨강 잔상(ro1l 1.27초 · aUic 0.70초)"
   }
  },
  "stickers": {},
  "bench": "ititemlog 팩 + 강조 색 후보(표준 §11-4 ㉚): 벤치 팔레트 강조 #F07A09·#E78DC3·#E23F9A + 흰·노랑 — placement.pick_emph_color(㉒ ΔE·대비 3·LCh 30°) 통과: 나레 노랑·원음 흰 줄 = #F07A09, 훅 빨강 줄 = #E78DC3(#F07A09 는 색상각 20.6° 탈락)",
  "place": {
   "y": 67.34,
   "bench": "채움 잉크 y≈1249~1338(가운데 1293/1920) — 2편 같음, 나레·원음 같은 자리"
  }
 }
}/*PACKS*/;
  // 효과마다 붙는 조건(관제 235) — 벤치에서 언제·어느 줄에 붙었나. 판 등록 작업자가 편마다 배치를 계산하는 근거. 코드는 읽지 않는다.
  root.CAPTION_EFFECT_RULES = /*RULES*/{
 "_note": "효과마다 붙는 조건. 벤치에서 꾸밈 없는 자막은 꾸미지 않는다 — 조건에 안 맞는 줄은 팩 기본(맨 글자)로 둔다. 편·초는 벤치 원본(C:/숏템_칼카피/<채널>/src) 기준.",
 "rgbGlitch": {
  "채널": "스타픽룸",
  "본 곳": "VbpdN 1.37초 '땅콩버터에...' (보강안 기록, 직접 못 본 것: dKcz 0.2 · 21Vo 7.2 · EZQl 2.5)",
  "박자": "훅(앞 원음 구간) 안에서 제품 이름이 처음 나오는 줄 — 그 줄 앞 줄('요즘에 그거에 꽂혔어요 또!')은 맨 글자",
  "조건": "편당 1~2회, 훅 구간(앞 3.5~8초)의 원음 줄에만. 나레·가운데·끝 줄엔 안 붙임"
 },
 "wipeRTL": {
  "채널": "스타픽룸",
  "본 곳": "VbpdN 17.37초 '가르쳐 드려요?' · EZQl 3.37초 '보쌈 식당인데요 완전'",
  "박자": "화면이 바뀐 직후 첫 줄(앞 줄 컷 다음 프레임부터)",
  "조건": "편당 1~2회, 8자 이상 원음 줄, 같은 줄을 둘로 나눈 둘째 조각엔 안 붙임"
 },
 "rainbowCycle": {
  "채널": "스타픽룸",
  "본 곳": "j5D 0.2~1.0초 나레 '최화정이 만들자마자'(편 첫 나레 줄)",
  "박자": "편에서 처음 나오는 나레 줄",
  "조건": "편당 1회 · 8~10자 나레 줄 · 한 줄 통째(낱말만 칠하지 않음) · 나머지 나레는 타이핑"
 },
 "place": {
  "채널": "키치잇 · 꿀템노트 · 스타픽룸",
  "본 곳": "키치잇 BRa 8.0~8.9초 원음 타이핑 줄 y1300(기본 1351)",
  "조건": "팩 기본 자리가 같은 줄이면 쓰지 않는다. 줄 변형이 자리를 가질 때만(variants.*.place) — caption_marks.place{x,y}% 는 벤치에서 자리가 달라진 줄에만"
 },
 "hearts": {
  "채널": "꿀템노트",
  "본 곳": "KCx 0.0~1.5초 '너무 예쁘다!'(선물 상자를 연 출연자 얼굴)",
  "박자": "편 첫 장면 · 감탄 한마디 줄 · 컷 직후부터 1.0초",
  "조건": "편당 1회, 얼굴이 보이는 장면(x50% y41% 얼굴 자리 — 장면마다 얼굴 자리를 받는다)"
 },
 "sound_word": {
  "채널": "꿀템노트",
  "본 곳": "cLk 5.4~6.6초 '쿰'·'직'(상자 뚜껑을 여는 소리 장면, 자막 '대용량인데 가격도 저렴해요' 위)",
  "박자": "제품에서 소리가 나는 동작 구간 한 장면",
  "조건": "편당 0~1회, 글자 한 쌍(왼쪽·오른쪽). 소리 낱말은 하이브리드가 장면 보고 지음"
 },
 "small_text": {
  "채널": "꿀템노트",
  "본 곳": "m0E 4.3~4.7초 'WOW'('지갑 열게 한 이유가 있다는데?' 줄 위, 가방 속 공개 순간) · 11.5초 ✦(장점 설명 줄 아래)",
  "박자": "제품 속·공개 순간 0.4~0.5초",
  "조건": "편당 0~2회, 설명 줄 위 따로 얹음 — 줄 안 글자는 안 바꿈"
 },
 "comic_burst": {
  "채널": "스타픽룸",
  "본 곳": "j5D 6.9~7.3초(a) · 9.3~9.5초(b) 둘 다 나레 '알고 보니 요즘'",
  "박자": "2초 넘게 머무는 나레 줄의 시작과 끝",
  "조건": "편당 0~2회, 한 줄에서 처음(a: 초록·주황 느낌표+별)·끝(b: 빨강 느낌표+번개)에 하나씩"
 },
 "aside_line": {
  "채널": "꿀템노트",
  "본 곳": "_dz 9.0~10.5초 '(난리가 났음)' — 원음 '변신하는 식탁을 막 보여주면서' 위 · 653b 14.5~16.5",
  "박자": "원음 줄이 길게(1.5초+) 머물 때 그 상황을 설명하는 한마디",
  "조건": "편당 0~2회, 원음 줄에만, 괄호로 시작"
 },
 "append_text": {
  "채널": "꿀템노트",
  "본 곳": "BpU 0.10→0.60초 '되게 가벼워' 뒤에 '맞아!' · 12.1 '아아아아악~'",
  "박자": "원음 앞 조각이 끝나기 전 같은 줄에 덧붙는 한마디(앞 조각은 제자리)",
  "조건": "편당 0~2회, 원음 줄 안에서 앞 조각이 0.5초 이상 선 뒤"
 }
}/*RULES*/;
  // ── 범용 등장 한 벌(관제 235, 칼카피 요청서 §4-2 1·2·4·5) ──────────────────────────────────────────────────────────
  //   spec = {kind?, ms?, keyframes?:[{t(초), scale(%), alpha(%), dy(px)}], cps?, cursor?:{char, blink_ms}, glow?:{decay_ms, color?},
  //           amp?(흔들림 배수), exit?:{kind:'cut'|'fade'|'slide', ms?, dx?(px, slide)}}
  //   kind: 'keyframes'(keyframes 가 있으면 생략 가능) | 이 파일의 등장 키(pop·typeGlow …) | 설명서 이름(kinds 표).
  //   줄 건 곳(위가 이긴다): 장면 자료 scene.enter > 팩 variants/speakers enter(객체) > 팩 enter(객체) > 스냅샷 captionEnter. 문자열 enter 는 종전대로 키.
  //   ★한계값 표(limits)는 서버(scene_style.clean_caption_enter)와 이 파일의 captionEnterMotion 이 같이 읽는다 — 서버는 ENTERSPEC 표식 사이를 json 으로 읽는다.
  root.CAPTION_ENTER_SPEC = /*ENTERSPEC*/{
 "limits": {"ms": [1, 5000], "t": [0, 5], "scale": [0, 400], "alpha": [0, 100], "dy": [-600, 600], "max_keyframes": 40,
            "cps": [1, 60], "blink_ms": [50, 2000], "decay_ms": [50, 2000], "exit_ms": [1, 2000], "exit_dx": [-1080, 1080], "amp": [0, 3]},
 "kinds": {"pop": "pop", "fade": "fade", "rise": "rise", "typing": "typing", "typewriter": "typing", "none": "", "shake": "shake",
           "glitch": "rgbGlitch", "wipe": "wipeRTL", "rainbow": "rainbowCycle", "slide": "slide"},
 "exits": ["cut", "fade", "slide"],
 "follow": {"char": "_", "color": "#FFFFFF", "at": "after", "gap": 0.15, "size": 1, "blink": 400, "until": "scene"},
 "glow": {"color": "#2B5C2B", "blur": [0.12, 0.28], "keys": [[0, 0], [0.35, 1]]}
}/*ENTERSPEC*/;
  root.captionEnterMotion = function (spec, motions) {
    if (!spec || typeof spec !== 'object') return null;
    const S = root.CAPTION_ENTER_SPEC, num = (v, d) => Number.isFinite(+v) && v !== null && v !== '' ? +v : d;
    const kind = spec.kind || (Array.isArray(spec.keyframes) && spec.keyframes.length ? 'keyframes' : '');
    let m;
    if (kind === 'keyframes') {
      const kf = (spec.keyframes || []).map(k => ({ t: Math.max(0, num(k.t, 0)), s: num(k.scale, 100), a: num(k.alpha, 100), d: num(k.dy, 0) })).sort((a, b) => a.t - b.t);
      if (!kf.length) return null;
      const lastT = kf[kf.length - 1].t, ms = Math.max(1, num(spec.ms, Math.round(lastT * 1000))), rest = k => k.s === 100 && k.a === 100 && k.d === 0;
      const vals = k => ({ opacity: k.a / 100, scale: String(k.s / 100), translate: `0px ${k.d}px` });
      const frames = kf.map(k => ({ offset: Math.min(1, k.t * 1000 / ms), ...vals(k) }));
      if (frames[0].offset > 0) frames.unshift({ ...frames[0], offset: 0 });                       // 첫 키프레임 앞은 그 값을 붙든다
      const lastF = frames[frames.length - 1];
      if (lastF.offset < 1 || !rest(kf[kf.length - 1])) frames.push({ offset: 1, ...vals({ s: 100, a: 100, d: 0 }) }); // 끝은 늘 '효과 없는 자막' 그림
      m = { label: '키프레임', origin: true, ms, easing: 'linear', frames };
    } else {
      const key = Object.prototype.hasOwnProperty.call(S.kinds, kind) ? S.kinds[kind] : kind;
      if (key === '') m = { label: '없음', ms: 1, easing: 'linear', frames: [{ opacity: 1 }, { opacity: 1 }] };
      else if (motions && motions[key]) m = JSON.parse(JSON.stringify(motions[key]));
      else return null;
      if (Number.isFinite(+spec.ms) && spec.ms > 0) { m.ms = +spec.ms; delete m.msPerChar; }
    }
    if (kind === 'shake' || m.frames.some(f => /em 0em$/.test(f.translate || ''))) {
      const amp = num(spec.amp, 1);
      if (amp !== 1) m.frames = m.frames.map(f => f.translate ? { ...f, translate: f.translate.replace(/(-?[\d.]+)em (-?[\d.]+)em/, (_, x, y) => `${(x * amp).toFixed(3)}em ${(y * amp).toFixed(3)}em`) } : f);
    }
    if (num(spec.cps, 0) > 0) m.cps = +spec.cps;
    if (spec.cursor && typeof spec.cursor === 'object' && m.unit === 'char') m.follow = { ...(m.follow || S.follow), char: spec.cursor.char || (m.follow || S.follow).char, blink: num(spec.cursor.blink_ms, (m.follow || S.follow).blink) };
    if (spec.glow && typeof spec.glow === 'object' && m.unit === 'char') m.glow = { ...S.glow, ...(m.glow || {}), ...(spec.glow.color ? { color: spec.glow.color } : {}), decay_ms: num(spec.glow.decay_ms, 0) };
    if (spec.exit && typeof spec.exit === 'object' && S.exits.includes(spec.exit.kind) && spec.exit.kind !== 'cut') m.exit = { kind: spec.exit.kind, ms: num(spec.exit.ms, 150), dx: num(spec.exit.dx, -400) };
    return m;
  };
  root.CAPTION_SLOTS = {"first": "첫 장면", "body": "일반 줄", "price": "가격·숫자", "end": "마지막 장면", "problem": "문제 제기", "reveal": "제품 공개", "emph": "영상 위 강조"};
  // 단어 강조 방식(관제 102 → 127) — 지금 말하는 단어를 어떻게 짚나. 편집기 WORD_FX_STYLES·서버 검증(scene_style.caption_word_fx_keys)이 여기를 읽는다.
  //   draw: 그 단어가 켜진 뒤 이 초 동안 그려진다(밑줄·형광펜·동그라미). 모양은 precision20-ui.css .wfx-<키>.
  //   ★서버는 WORDFX 표식 두 개 사이를 json 으로 읽는다 — 그 안에는 JSON 만.
  root.CAPTION_WORD_FX = /*WORDFX*/{
 "box": {
  "label": "박스"
 },
 "color": {
  "label": "색 바뀜"
 },
 "underline": {
  "label": "밑줄 긋기",
  "draw": 0.22,
  "pack": true
 },
 "highlight": {
  "label": "형광펜",
  "draw": 0.28,
  "pack": true
 },
 "circle": {
  "label": "동그라미",
  "draw": 0.35,
  "pack": true
 },
 "glow": {
  "label": "번쩍 글로우",
  "pack": true
 },
 "mark": {
  "label": "핵심 단어 색칠",
  "fixed": true,
  "pack": true,
  "hide": true
 }
}/*WORDFX*/;
  root.CAPTION_EMPH_DEFAULT = {"size": 150, "color": "#FFFFFF", "style": {"textShadow": "0 0.05em 0.25em rgba(0,0,0,.9),0 0 0.6em rgba(0,0,0,.5)"}, "motion": "pop"};
  // 등장 효과팩 20종(관제 144) — 움직임만. 칸별 효과(일반 줄 body 는 3개를 번갈아). 번호 = 배열 순서 + 1.
  //   만든 곳: tools/caption_pack/make_motion_packs.py(씨앗 고정 · 두 팩 최소 4칸 다름) — 손으로 고치지 말고 그 도구로.
  //   배정: 회원마다 자동(scene_style.caption_motion_pack_for, 회원 번호 나머지) · 영상마다 자동/끔/번호(snapshot.motionPack).
  //   ★서버는 MPACKS 표식 두 개 사이를 json 으로 읽는다 — 그 안에는 JSON 만.
  root.CAPTION_MOTION_PACKS = /*MPACKS*/[{"first": "popBounce", "body": ["blurUp", "slide", "jelly"], "price": "drop", "problem": "typing", "reveal": "grow", "end": "riseClip", "emph": "grow", "fx": {"hook": ["in"], "problem": ["inout"], "reveal": ["pull"], "peak": ["dim", "pull"], "cta": ["pull"]}}, {"first": "drop", "body": ["jelly", "grow", "rise"], "price": "slam", "problem": "drop", "reveal": "pop", "end": "slam", "emph": "slam", "fx": {"hook": ["inout"], "problem": ["in", "shock"], "reveal": ["inout"], "peak": ["dim"], "cta": ["in"]}}, {"first": "drop", "body": ["slide", "typing", "fade"], "price": "popBounce", "problem": "typing", "reveal": "popBounce", "end": "slam", "emph": "trackIn", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["inout"], "peak": ["dim"], "cta": ["inout"]}}, {"first": "popBounce", "body": ["popBounce", "riseClip", "grow"], "price": "jelly", "problem": "slide", "reveal": "popBounce", "end": "slam", "emph": "blurUp", "fx": {"hook": ["pull"], "problem": ["shock"], "reveal": ["inout"], "peak": ["dim", "in"], "cta": ["pull"]}}, {"first": "slam", "body": ["fade", "blurUp", "popBounce"], "price": "popBounce", "problem": "drop", "reveal": "riseClip", "end": "blurUp", "emph": "trackIn", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["pull"], "peak": ["dim", "in"], "cta": ["inout"]}}, {"first": "riseClip", "body": ["pop", "riseClip", "rise"], "price": "drop", "problem": "slide", "reveal": "popBounce", "end": "rise", "emph": "blurUp", "fx": {"hook": ["pull"], "problem": ["in", "shock"], "reveal": ["pull"], "peak": ["dim", "pull"], "cta": ["pull"]}}, {"first": "riseClip", "body": ["riseClip", "blurUp", "jelly"], "price": "slam", "problem": "slide", "reveal": "riseClip", "end": "riseClip", "emph": "slam", "fx": {"hook": ["pull"], "problem": ["shock"], "reveal": ["pull"], "peak": ["dim", "pull"], "cta": ["in"]}}, {"first": "popBounce", "body": ["grow", "pop", "blurUp"], "price": "drop", "problem": "fade", "reveal": "grow", "end": "slam", "emph": "popBounce", "fx": {"hook": ["inout"], "problem": ["shock"], "reveal": ["pull"], "peak": ["dim"], "cta": ["inout"]}}, {"first": "trackIn", "body": ["typing", "popBounce", "grow"], "price": "jelly", "problem": "wide", "reveal": "popBounce", "end": "riseClip", "emph": "slam", "fx": {"hook": ["in"], "problem": ["shock"], "reveal": ["inout"], "peak": ["dim"], "cta": ["in"]}}, {"first": "popBounce", "body": ["rise", "jelly", "blurUp"], "price": "pop", "problem": "typing", "reveal": "riseClip", "end": "trackIn", "emph": "trackIn", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["in"], "peak": ["dim"], "cta": ["in"]}}, {"first": "wide", "body": ["blurUp", "grow", "jelly"], "price": "pop", "problem": "wide", "reveal": "grow", "end": "slam", "emph": "riseClip", "fx": {"hook": ["inout"], "problem": ["inout"], "reveal": ["inout"], "peak": ["shock", "pull"], "cta": ["inout"]}}, {"first": "drop", "body": ["popBounce", "rise", "fade"], "price": "slam", "problem": "slide", "reveal": "popBounce", "end": "trackIn", "emph": "slam", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["inout"], "peak": ["shock", "pull"], "cta": ["pull"]}}, {"first": "popBounce", "body": ["grow", "blurUp", "fade"], "price": "jelly", "problem": "fade", "reveal": "riseClip", "end": "riseClip", "emph": "grow", "fx": {"hook": ["in"], "problem": ["shock"], "reveal": ["inout"], "peak": ["dim", "pull"], "cta": ["inout"]}}, {"first": "riseClip", "body": ["typing", "blurUp", "jelly"], "price": "pop", "problem": "fade", "reveal": "grow", "end": "blurUp", "emph": "riseClip", "fx": {"hook": ["pull"], "problem": ["inout"], "reveal": ["in"], "peak": ["shock", "pull"], "cta": ["pull"]}}, {"first": "slam", "body": ["typing", "popBounce", "grow"], "price": "slam", "problem": "slide", "reveal": "popBounce", "end": "blurUp", "emph": "trackIn", "fx": {"hook": ["in"], "problem": ["inout"], "reveal": ["in"], "peak": ["dim", "in"], "cta": ["in"]}}, {"first": "wide", "body": ["typing", "fade", "pop"], "price": "slam", "problem": "typing", "reveal": "slam", "end": "slam", "emph": "riseClip", "fx": {"hook": ["pull"], "problem": ["inout"], "reveal": ["pull"], "peak": ["shock", "pull"], "cta": ["inout"]}}, {"first": "slam", "body": ["jelly", "fade", "rise"], "price": "popBounce", "problem": "fade", "reveal": "grow", "end": "rise", "emph": "grow", "fx": {"hook": ["in"], "problem": ["inout"], "reveal": ["pull"], "peak": ["dim"], "cta": ["inout"]}}, {"first": "drop", "body": ["blurUp", "popBounce", "fade"], "price": "popBounce", "problem": "drop", "reveal": "grow", "end": "trackIn", "emph": "riseClip", "fx": {"hook": ["in"], "problem": ["shock"], "reveal": ["pull"], "peak": ["dim"], "cta": ["pull"]}}, {"first": "riseClip", "body": ["fade", "blurUp", "pop"], "price": "jelly", "problem": "slide", "reveal": "pop", "end": "rise", "emph": "grow", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["pull"], "peak": ["dim", "pull"], "cta": ["in"]}}, {"first": "wide", "body": ["popBounce", "slide", "grow"], "price": "drop", "problem": "typing", "reveal": "pop", "end": "popBounce", "emph": "trackIn", "fx": {"hook": ["pull"], "problem": ["inout"], "reveal": ["inout"], "peak": ["dim"], "cta": ["in"]}}]/*MPACKS*/;
})(window);
