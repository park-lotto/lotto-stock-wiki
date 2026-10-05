(function (root) {
  'use strict';
  // 자막 등장 효과 계약(관제 127 자막팩) — 편집기(precision20-ui.js runCaptionEnter)·렌더러·서버 검증(scene_style.py)이 모두 이 한 곳을 읽는다.
  //   키 = 저장값(bodyCaptionMotion). label 화면 이름 · ms 한 단위 길이 · easing · frames(Web Animations 키프레임).
  //   unit: 없음 = 자막 통째로 / 'word' 어절마다 / 'char' 글자마다. stagger = 단위 사이 간격(ms), spread = 마지막 단위가 늦게 시작하는 상한(ms, 긴 자막도 이 안에 끝).
  //   spreadX: 글자마다 가운데에서 (번호-가운데)×값(em)만큼 벌어진 자리에서 모인다 — 키프레임마다 spreadK 배(없으면 0). origin: true = 자막 가운데 기준 / 문자열 = 단위마다의 기준점. boxAt: 글자 단위일 때 단어 강조 상자를 첫 글자 시작 뒤 ms×boxAt 에 켠다.
  //   ★새 효과는 transform 대신 translate·scale 을 쓴다 — 자막 칸의 가로 줄임(scaleX)·단어 '툭 커짐'(scale)을 덮지 않게.
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
  "boxAt": 0.35
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
  "boxAt": 0.1
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
  "boxAt": 0.4
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
  ]
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
  ]
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
  "boxAt": 1
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
  "boxAt": 0.05
 }
}/*JSON*/;
})(window);
