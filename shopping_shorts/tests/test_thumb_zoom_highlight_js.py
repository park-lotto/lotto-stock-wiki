"""🔍썸네일 배경 확대 · 🔎돋보기 — **실제 코드를 돌려서** 값 해석과 그리기를 확인한다.

왜 문자열 검색이 아니라 실행인가: 이 기능의 버그는 "그 줄이 있느냐"가 아니라
**어떤 좌표로 그리느냐**에서 난다(빈 구석이 생긴다·원이 안 맞는다). 문자열 검사는
그걸 못 잡는다 — 그래서 produce.html에서 함수를 떼어 node로 진짜 호출한다.

여기서 못박는 계약(0순위-B — 서버 video_assemble과 **같은 뜻**이어야 한다):
  zoom  1~3                    scene_zoom_of와 같은 범위
  pan   |pan| <= (zoom-1)/2    확대한 만큼만 민다 = 화면에 빈 구석이 안 생긴다
  hl.r  0.06~0.9 (폭 대비)     scene_hl_of와 같은 범위
  hl.zoom 1.1~4
"""
from pathlib import Path

from shopping_shorts.tests.js_harness import run_js, requires_node

pytestmark = requires_node

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")

# produce.html에서 확대·돋보기 핵심부만 떼어낸다. 브라우저 전역(document 등)은 하네스가 흉내낸다.
_START = "const THUMB_VIEW_DEF"
_END = "function drawThumb(ctx, img, layers, W, H, view)"


def _core():
    assert _START in HTML, "THUMB_VIEW_DEF가 없다 — 확대·돋보기가 통째로 빠졌나?"
    assert _END in HTML, "drawThumb 시그니처가 바뀌었다 — 이 테스트의 잘라내는 지점을 고쳐라"
    return HTML.split(_START, 1)[1].split(_END, 1)[0]


_HARNESS = """
const THUMB_W=1080, THUMB_H=1920;
// 브라우저 전역 흉내 — 조작 함수(thumbViewSet 등)가 참조만 하고 실제로는 안 쓴다.
var document={getElementById:function(){return null;}};
var THUMB_STATE={view:null};
function renderThumbCanvas(){}
const THUMB_VIEW_DEF""" + """%s

// 캔버스 대역 — 무엇을 어떤 좌표로 그렸는지 기록만 한다.
function stubCtx(){
  const calls=[]; const c={calls};
  ['clearRect','drawImage','save','restore','beginPath','closePath','arc','moveTo','lineTo',
   'fill','fillRect','stroke','clip','translate','scale'].forEach(function(k){
     c[k]=function(){calls.push([k].concat([].slice.call(arguments)));};
  });
  return c;
}
const IMG={__img:true}, W=1080, H=1920;
const out={};
"""


def _run(body):
    return run_js(_HARNESS % _core() + body)


def test_defaults_are_a_no_op():
    """기본값은 '확대 없음·돋보기 꺼짐' — 안 건드리면 종전과 완전히 같아야 한다(회귀 0)."""
    r = _run("""
      const v=thumbView({});
      const c=stubCtx(); _drawThumbBg(c,IMG,v,W,H);
      const d=c.calls.find(x=>x[0]==='drawImage');
      const h=stubCtx(); _drawThumbHL(h,IMG,v,W,H);
      console.log(JSON.stringify({zoom:v.zoom,pan:[v.pan_x,v.pan_y],on:v.hl.on,
                                  draw:d.slice(2),hlCalls:h.calls.length}));
    """)
    import json
    d = json.loads(r)
    assert d["zoom"] == 1 and d["pan"] == [0, 0]
    assert d["on"] is False
    # 확대가 없으면 예전 그대로 "화면 꽉 채워 한 번"
    assert d["draw"] == [0, 0, 1080, 1920]
    # 돋보기가 꺼져 있으면 **아무것도 그리지 않는다**
    assert d["hlCalls"] == 0


def test_zoom_and_pan_are_clamped_like_the_server():
    """서버 scene_zoom_of와 같은 범위로 가둔다 — 두 뜻이 갈리면 미리보기와 결과가 달라진다."""
    import json
    d = json.loads(_run("""
      console.log(JSON.stringify({
        hi: thumbView({zoom:99}).zoom,
        lo: thumbView({zoom:0.1}).zoom,
        pan: [thumbView({zoom:2,pan_x:9,pan_y:-9}).pan_x, thumbView({zoom:2,pan_x:9}).pan_y],
        flat: thumbView({zoom:1,pan_x:9}).pan_x,
      }));
    """))
    assert d["hi"] == 3 and d["lo"] == 1
    assert d["pan"][0] == 0.5          # (2-1)/2
    assert d["flat"] == 0              # 확대가 없으면 밀 것도 없다


def test_pan_limit_leaves_no_empty_corner():
    """★핵심 계약 — pan을 한계까지 밀면 그림 끝이 화면 끝에 **정확히** 닿는다.

    어긋나면 썸네일 구석에 빈(검은) 자리가 생긴다. 눈으로만 보면 놓치는 종류라 수치로 못박는다.
    """
    import json
    d = json.loads(_run("""
      function at(px,py){
        const c=stubCtx(); _drawThumbBg(c,IMG,thumbView({zoom:2,pan_x:px,pan_y:py}),W,H);
        const g=c.calls.find(x=>x[0]==='drawImage');
        return {x:g[2],y:g[3],w:g[4],h:g[5]};
      }
      console.log(JSON.stringify({mid:at(0,0), pos:at(0.5,0.5), neg:at(-0.5,-0.5)}));
    """))
    assert d["mid"] == {"x": -540, "y": -960, "w": 2160, "h": 3840}   # 중앙
    assert d["pos"] == {"x": 0, "y": 0, "w": 2160, "h": 3840}         # 왼·위 끝에 딱
    # 오른쪽·아래 끝에 딱 — x + w == W, y + h == H
    assert d["neg"]["x"] + d["neg"]["w"] == 1080
    assert d["neg"]["y"] + d["neg"]["h"] == 1920


def test_highlight_ranges_match_the_server():
    """돋보기 값 범위도 서버 scene_hl_of와 같아야 한다."""
    import json
    d = json.loads(_run("""
      console.log(JSON.stringify({
        rHi: thumbView({hl:{on:true,r:99}}).hl.r,
        rLo: thumbView({hl:{on:true,r:0.001}}).hl.r,
        zHi: thumbView({hl:{on:true,zoom:99}}).hl.zoom,
        zLo: thumbView({hl:{on:true,zoom:0}}).hl.zoom,
        bad: [thumbView({hl:{on:true,mode:'xxx',shape:'yyy'}}).hl.mode,
              thumbView({hl:{on:true,mode:'xxx',shape:'yyy'}}).hl.shape],
        good:[thumbView({hl:{on:true,mode:'spot',shape:'round'}}).hl.mode,
              thumbView({hl:{on:true,mode:'spot',shape:'round'}}).hl.shape],
      }));
    """))
    assert (d["rHi"], d["rLo"]) == (0.9, 0.06)
    assert (d["zHi"], d["zLo"]) == (4, 1.1)
    assert d["bad"] == ["zoom", "circle"]        # 모르는 값은 기본으로 떨어뜨린다
    assert d["good"] == ["spot", "round"]


def test_zero_is_a_real_value_not_a_missing_one():
    """★0은 '안 넣은 값'이 아니다 — `+v || 기본값` 관용구의 함정을 못박는다.

    실측(2026-09-13): 처음 구현이 `+h.zoom || 2`여서 배율 0을 넣으면 하한 1.1이 아니라
    **기본값 2**가 나왔다. cx=0(왼쪽 끝)·pan=0도 같은 함정이라 전부 같이 잰다.
    """
    import json
    d = json.loads(_run("""
      console.log(JSON.stringify({
        hlZoom0: thumbView({hl:{on:true,zoom:0}}).hl.zoom,     // 하한 1.1로 잘려야 한다
        cx0:     thumbView({hl:{on:true,cx:0}}).hl.cx,         // 0 = 왼쪽 끝, 살아야 한다
        cy0:     thumbView({hl:{on:true,cy:0}}).hl.cy,
        r0:      thumbView({hl:{on:true,r:0}}).hl.r,           // 하한 0.06
        zoom0:   thumbView({zoom:0}).zoom,                     // 하한 1
        // 숫자가 아예 아니면 그때는 기본값으로 떨어져야 한다
        junk:    thumbView({hl:{on:true,zoom:'abc'}}).hl.zoom,
        nul:     thumbView({hl:{on:true,cx:null}}).hl.cx,
      }));
    """))
    assert d["hlZoom0"] == 1.1, "0이 기본값 2로 튀었다 — `|| 기본값` 함정"
    assert d["cx0"] == 0 and d["cy0"] == 0, "0(왼쪽·위 끝)이 기본 중앙으로 튀었다"
    assert d["r0"] == 0.06
    assert d["zoom0"] == 1
    assert d["junk"] == 2 and d["nul"] == 0.5      # 진짜 없는 값만 기본값으로


def test_two_highlight_modes_draw_different_things():
    """🔍원 안 확대는 잘라내 확대하고, 💡원 밖 어둡게는 덮기만 한다(확대 금지)."""
    import json
    d = json.loads(_run("""
      function mode(m){
        const c=stubCtx(); _drawThumbHL(c,IMG,thumbView({hl:{on:true,mode:m}}),W,H);
        const names=c.calls.map(x=>x[0]);
        return {clip:names.includes('clip'), scale:names.includes('scale'),
                stroke:names.includes('stroke'),
                cover:c.calls.some(x=>x[0]==='fillRect'&&x[3]===W&&x[4]===H)};
      }
      console.log(JSON.stringify({zoom:mode('zoom'), spot:mode('spot')}));
    """))
    # 원 안 확대: 원으로 잘라(clip) 그 안을 키운다(scale)
    assert d["zoom"]["clip"] and d["zoom"]["scale"]
    # 원 밖 어둡게: 화면을 덮되 **확대는 하지 않는다**
    assert d["spot"]["cover"] and not d["spot"]["scale"]
    # 테두리는 두 모드 공통 — 원이 어디인지 보여야 한다
    assert d["zoom"]["stroke"] and d["spot"]["stroke"]


def test_shape_path_stays_inside_the_radius():
    """⭕원·▢둥근네모 모두 반지름을 벗어나지 않는다 — 하나의 거리식에서 나오므로 모양이 안 터진다."""
    import json
    d = json.loads(_run("""
      const a=stubCtx(); _thumbHlPath(a,0,0,100,'circle');
      const b=stubCtx(); _thumbHlPath(b,0,0,100,'round');
      const pts=b.calls.filter(x=>x[0]==='moveTo'||x[0]==='lineTo').map(x=>[x[1],x[2]]);
      const maxAbs=Math.max.apply(null,pts.map(p=>Math.max(Math.abs(p[0]),Math.abs(p[1]))));
      console.log(JSON.stringify({
        circleArcs:a.calls.filter(x=>x[0]==='arc').length,
        roundArcs:b.calls.filter(x=>x[0]==='arc').length,
        roundPts:pts.length, maxAbs:maxAbs}));
    """))
    assert d["circleArcs"] == 1          # 원은 arc 한 번이면 정확하다
    assert d["roundArcs"] == 0 and d["roundPts"] > 50   # 둥근네모는 선분으로 잇는다
    assert d["maxAbs"] <= 100.0001       # 반지름 밖으로 안 나간다


def test_thumbnail_png_upload_carries_the_view():
    """저장 meta에 view가 실려야 한다 — 안 실으면 '미리보기만 바뀌고 다시 열면 사라진다'."""
    body = HTML.split("async function generateThumb()", 1)[1].split("renderThumbGallery()", 1)[0]
    assert "view: THUMB_STATE.view" in body, "생성 요청에 view가 빠졌다"
