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
 }
}/*PACKS*/;
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
 }
}/*WORDFX*/;
  root.CAPTION_EMPH_DEFAULT = {"size": 150, "color": "#FFFFFF", "style": {"textShadow": "0 0.05em 0.25em rgba(0,0,0,.9),0 0 0.6em rgba(0,0,0,.5)"}, "motion": "pop"};
  // 등장 효과팩 20종(관제 144) — 움직임만. 칸별 효과(일반 줄 body 는 3개를 번갈아). 번호 = 배열 순서 + 1.
  //   만든 곳: tools/caption_pack/make_motion_packs.py(씨앗 고정 · 두 팩 최소 4칸 다름) — 손으로 고치지 말고 그 도구로.
  //   배정: 회원마다 자동(scene_style.caption_motion_pack_for, 회원 번호 나머지) · 영상마다 자동/끔/번호(snapshot.motionPack).
  //   ★서버는 MPACKS 표식 두 개 사이를 json 으로 읽는다 — 그 안에는 JSON 만.
  root.CAPTION_MOTION_PACKS = /*MPACKS*/[{"first": "popBounce", "body": ["blurUp", "slide", "jelly"], "price": "drop", "problem": "typing", "reveal": "grow", "end": "riseClip", "emph": "grow", "fx": {"hook": ["in"], "problem": ["inout"], "reveal": ["pull"], "peak": ["dim", "pull"], "cta": ["pull"]}}, {"first": "drop", "body": ["jelly", "grow", "rise"], "price": "slam", "problem": "drop", "reveal": "pop", "end": "slam", "emph": "slam", "fx": {"hook": ["inout"], "problem": ["in", "shock"], "reveal": ["inout"], "peak": ["dim"], "cta": ["in"]}}, {"first": "drop", "body": ["slide", "typing", "fade"], "price": "popBounce", "problem": "typing", "reveal": "popBounce", "end": "slam", "emph": "trackIn", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["inout"], "peak": ["dim"], "cta": ["inout"]}}, {"first": "popBounce", "body": ["popBounce", "riseClip", "grow"], "price": "jelly", "problem": "slide", "reveal": "popBounce", "end": "slam", "emph": "blurUp", "fx": {"hook": ["pull"], "problem": ["shock"], "reveal": ["inout"], "peak": ["dim", "in"], "cta": ["pull"]}}, {"first": "slam", "body": ["fade", "blurUp", "popBounce"], "price": "popBounce", "problem": "drop", "reveal": "riseClip", "end": "blurUp", "emph": "trackIn", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["pull"], "peak": ["dim", "in"], "cta": ["inout"]}}, {"first": "riseClip", "body": ["pop", "riseClip", "rise"], "price": "drop", "problem": "slide", "reveal": "popBounce", "end": "rise", "emph": "blurUp", "fx": {"hook": ["pull"], "problem": ["in", "shock"], "reveal": ["pull"], "peak": ["dim", "pull"], "cta": ["pull"]}}, {"first": "riseClip", "body": ["riseClip", "blurUp", "jelly"], "price": "slam", "problem": "slide", "reveal": "riseClip", "end": "riseClip", "emph": "slam", "fx": {"hook": ["pull"], "problem": ["shock"], "reveal": ["pull"], "peak": ["dim", "pull"], "cta": ["in"]}}, {"first": "popBounce", "body": ["grow", "pop", "blurUp"], "price": "drop", "problem": "fade", "reveal": "grow", "end": "slam", "emph": "popBounce", "fx": {"hook": ["inout"], "problem": ["shock"], "reveal": ["pull"], "peak": ["dim"], "cta": ["inout"]}}, {"first": "trackIn", "body": ["typing", "popBounce", "grow"], "price": "jelly", "problem": "wide", "reveal": "popBounce", "end": "riseClip", "emph": "slam", "fx": {"hook": ["in"], "problem": ["shock"], "reveal": ["inout"], "peak": ["dim"], "cta": ["in"]}}, {"first": "popBounce", "body": ["rise", "jelly", "blurUp"], "price": "pop", "problem": "typing", "reveal": "riseClip", "end": "trackIn", "emph": "trackIn", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["in"], "peak": ["dim"], "cta": ["in"]}}, {"first": "wide", "body": ["blurUp", "grow", "jelly"], "price": "pop", "problem": "wide", "reveal": "grow", "end": "slam", "emph": "riseClip", "fx": {"hook": ["inout"], "problem": ["inout"], "reveal": ["inout"], "peak": ["shock", "pull"], "cta": ["inout"]}}, {"first": "drop", "body": ["popBounce", "rise", "fade"], "price": "slam", "problem": "slide", "reveal": "popBounce", "end": "trackIn", "emph": "slam", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["inout"], "peak": ["shock", "pull"], "cta": ["pull"]}}, {"first": "popBounce", "body": ["grow", "blurUp", "fade"], "price": "jelly", "problem": "fade", "reveal": "riseClip", "end": "riseClip", "emph": "grow", "fx": {"hook": ["in"], "problem": ["shock"], "reveal": ["inout"], "peak": ["dim", "pull"], "cta": ["inout"]}}, {"first": "riseClip", "body": ["typing", "blurUp", "jelly"], "price": "pop", "problem": "fade", "reveal": "grow", "end": "blurUp", "emph": "riseClip", "fx": {"hook": ["pull"], "problem": ["inout"], "reveal": ["in"], "peak": ["shock", "pull"], "cta": ["pull"]}}, {"first": "slam", "body": ["typing", "popBounce", "grow"], "price": "slam", "problem": "slide", "reveal": "popBounce", "end": "blurUp", "emph": "trackIn", "fx": {"hook": ["in"], "problem": ["inout"], "reveal": ["in"], "peak": ["dim", "in"], "cta": ["in"]}}, {"first": "wide", "body": ["typing", "fade", "pop"], "price": "slam", "problem": "typing", "reveal": "slam", "end": "slam", "emph": "riseClip", "fx": {"hook": ["pull"], "problem": ["inout"], "reveal": ["pull"], "peak": ["shock", "pull"], "cta": ["inout"]}}, {"first": "slam", "body": ["jelly", "fade", "rise"], "price": "popBounce", "problem": "fade", "reveal": "grow", "end": "rise", "emph": "grow", "fx": {"hook": ["in"], "problem": ["inout"], "reveal": ["pull"], "peak": ["dim"], "cta": ["inout"]}}, {"first": "drop", "body": ["blurUp", "popBounce", "fade"], "price": "popBounce", "problem": "drop", "reveal": "grow", "end": "trackIn", "emph": "riseClip", "fx": {"hook": ["in"], "problem": ["shock"], "reveal": ["pull"], "peak": ["dim"], "cta": ["pull"]}}, {"first": "riseClip", "body": ["fade", "blurUp", "pop"], "price": "jelly", "problem": "slide", "reveal": "pop", "end": "rise", "emph": "grow", "fx": {"hook": ["in"], "problem": ["in", "shock"], "reveal": ["pull"], "peak": ["dim", "pull"], "cta": ["in"]}}, {"first": "wide", "body": ["popBounce", "slide", "grow"], "price": "drop", "problem": "typing", "reveal": "pop", "end": "popBounce", "emph": "trackIn", "fx": {"hook": ["pull"], "problem": ["inout"], "reveal": ["inout"], "peak": ["dim"], "cta": ["in"]}}]/*MPACKS*/;
})(window);
