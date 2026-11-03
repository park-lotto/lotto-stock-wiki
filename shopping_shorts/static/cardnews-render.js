/* 카드뉴스 렌더러(관제 223, 2026-10-17) — ★카드 그림의 주인은 이 파일 하나다(0순위-B·C).
 * 편집 미리보기·썸네일·보관함·다운로드(JPEG/ZIP)가 전부 CardNews.render 하나로 그린다.
 * 그래서 "화면에서 본 것"과 "받은 파일"이 다를 수 없다 — 다운로드는 화면과 같은 DOM을 1080 원본 크기로 찍는다.
 * 글자 넘침 판정도 여기(fit) 한 곳: 칸을 넘치면 글자를 4%씩 줄이고(최대 30%), 그래도 넘치면 overflow 로 보고한다.
 * 문구·장 구성 판단은 서버 cardnews.py — 여기는 그리기만 한다.
 */
(function () {
  "use strict";
  var W = 1080;
  var RATIO_H = { "4:5": 1350, "1:1": 1080, "9:16": 1920 };
  var FONT_DIR = "/fonts/";
  var FONTS = [
    { id: "Pretendard", name: "프리텐다드", note: "깔끔한 기본", css: "CNPretendard" },
    { id: "GmarketSans", name: "지마켓 산스", note: "굵고 또렷함", css: "CNGmarket" },
    { id: "SUIT", name: "수트", note: "단정한 정보형", css: "CNSuit" },
    { id: "Hahmlet", name: "함렛", note: "세련된 명조", css: "CNHahmlet" },
    { id: "NanumMyeongjo", name: "나눔명조 엑스트라볼드", note: "잡지 표지", css: "CNMyeongjo" },
    { id: "BlackHanSans", name: "블랙한산스", note: "강한 임팩트", css: "CNBlackHan" },
    { id: "Jalnan", name: "잘난체", note: "둥글고 귀여움", css: "CNJalnan" },
    { id: "GowunDodum", name: "고운돋움", note: "부드러운 감성", css: "CNGowun" }
  ];
  var PACKS = [
    { id: "editorial", name: "에디토리얼", note: "어두운 바탕 · 정보형", titleFont: "Pretendard" },
    { id: "magazine", name: "매거진", note: "종이 질감 · 명조", titleFont: "Hahmlet" },
    { id: "photo", name: "포토", note: "사진 꽉 채움 · 홍보형", titleFont: "GmarketSans" },
    { id: "pastel", name: "파스텔", note: "밝은 색 · 생활 팁", titleFont: "SUIT" }
  ];
  var ROLE_NAMES = { cover: "표지", number: "숫자", compare: "비교", steps: "단계", list: "목록", quote: "한마디", cta: "마무리" };
  var LAYOUTS = 3;

  function fontCss(id) {
    for (var i = 0; i < FONTS.length; i++) if (FONTS[i].id === id) return FONTS[i].css;
    return "CNPretendard";
  }

  var STYLE = [
    "@font-face{font-family:CNPretendard;src:url(" + FONT_DIR + "Pretendard-Regular.otf);font-weight:400}",
    "@font-face{font-family:CNPretendard;src:url(" + FONT_DIR + "Pretendard-SemiBold.otf);font-weight:600}",
    "@font-face{font-family:CNPretendard;src:url(" + FONT_DIR + "Pretendard-Bold.otf);font-weight:700}",
    "@font-face{font-family:CNPretendard;src:url(" + FONT_DIR + "Pretendard-ExtraBold.otf);font-weight:800}",
    "@font-face{font-family:CNGmarket;src:url(" + FONT_DIR + "GmarketSansBold.otf);font-weight:700}",
    "@font-face{font-family:CNSuit;src:url(" + FONT_DIR + "SUIT-Regular.otf);font-weight:400}",
    "@font-face{font-family:CNSuit;src:url(" + FONT_DIR + "SUIT-Bold.otf);font-weight:700}",
    "@font-face{font-family:CNHahmlet;src:url(" + FONT_DIR + "Hahmlet-Variable.ttf);font-weight:100 900}",
    "@font-face{font-family:CNMyeongjo;src:url(" + FONT_DIR + "NanumMyeongjo-ExtraBold.ttf);font-weight:800}",
    "@font-face{font-family:CNBlackHan;src:url(" + FONT_DIR + "BlackHanSans.ttf);font-weight:400}",
    "@font-face{font-family:CNJalnan;src:url(" + FONT_DIR + "Jalnan2.ttf);font-weight:400}",
    "@font-face{font-family:CNGowun;src:url(" + FONT_DIR + "GowunDodum-Regular.ttf);font-weight:400}",

    /* 공통 뼈대 — 원본 1080 폭. --u = 글자 배율(크기 S·M·L × 자동 맞춤) */
    ".cn-card{position:relative;width:1080px;height:var(--h,1350px);overflow:hidden;box-sizing:border-box;",
    "  display:flex;flex-direction:column;padding:92px 96px 84px;font-family:CNPretendard,'Malgun Gothic',sans-serif;",
    "  --u:1;--ac:#37e0bd;-webkit-font-smoothing:antialiased;text-rendering:geometricPrecision;word-break:keep-all;overflow-wrap:break-word}",
    ".cn-card *{box-sizing:border-box;margin:0;padding:0}",
    ".cn-bg{position:absolute;inset:0;z-index:0;background-size:cover;background-position:center}",
    ".cn-card>:not(.cn-bg){position:relative;z-index:1}",
    ".cn-top{display:flex;justify-content:space-between;align-items:center;height:52px;flex:none}",
    ".cn-brand{display:flex;align-items:center;gap:16px;font-size:30px;font-weight:700;letter-spacing:-.01em}",
    ".cn-brand img{height:52px;width:auto;max-width:180px;object-fit:contain}",
    ".cn-brand .cn-dot{width:16px;height:16px;border-radius:50%;background:var(--ac)}",
    ".cn-idx{font-size:27px;font-weight:600;letter-spacing:.08em;font-variant-numeric:tabular-nums}",
    ".cn-main{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;gap:calc(40px*var(--u));overflow:hidden;padding:24px 0}",
    ".cn-card.L1 .cn-main{justify-content:flex-end}",
    ".r-cover.L0 .cn-main{justify-content:flex-end;padding-bottom:40px}",
    ".cn-card.L2 .cn-main{justify-content:flex-start;padding-top:64px}",
    ".cn-foot{display:flex;justify-content:space-between;align-items:center;height:48px;flex:none;font-size:27px;font-weight:600}",
    ".cn-k{font-size:calc(31px*var(--u));font-weight:700;letter-spacing:.16em;text-transform:uppercase}",
    ".cn-t{font-size:calc(var(--ts,100px)*var(--u));line-height:1.16;font-weight:800;letter-spacing:-.035em}",
    ".cn-t.cn-big{--ts:132px;line-height:1.1}",
    ".cn-b{font-size:calc(41px*var(--u));line-height:1.6;font-weight:500;letter-spacing:-.01em;white-space:pre-line}",
    ".cn-num{font-size:calc(320px*var(--u));line-height:.92;font-weight:800;letter-spacing:-.05em;font-variant-numeric:tabular-nums}",
    ".cn-list{list-style:none;display:flex;flex-direction:column;gap:calc(22px*var(--u))}",
    ".cn-list li{display:flex;align-items:center;gap:30px;font-size:calc(50px*var(--u));font-weight:700;letter-spacing:-.02em;line-height:1.3}",
    ".cn-list .cn-mk{flex:none;width:calc(78px*var(--u));height:calc(78px*var(--u));border-radius:50%;display:grid;place-items:center;font-size:calc(31px*var(--u));font-weight:800}",
    ".cn-cmp{display:grid;grid-template-columns:1fr 1fr;gap:28px}",
    ".cn-cmp .cn-side{border-radius:32px;padding:calc(40px*var(--u)) 36px;display:flex;flex-direction:column;gap:calc(20px*var(--u))}",
    ".cn-cmp .cn-nm{font-size:calc(50px*var(--u));font-weight:800;letter-spacing:-.02em}",
    ".cn-cmp .cn-pt{font-size:calc(38px*var(--u));line-height:1.45;font-weight:600;display:flex;gap:14px;align-items:flex-start}",
    ".cn-cmp .cn-pt i{font-style:normal;font-weight:800;flex:none;width:34px}",
    ".cn-quote{font-size:calc(240px*var(--u));line-height:.6;font-weight:800;height:calc(130px*var(--u))}",
    ".cn-acts{display:flex;gap:22px;margin-top:8px}",
    ".cn-acts span{display:flex;align-items:center;gap:14px;border-radius:999px;padding:22px 36px;font-size:33px;font-weight:700}",
    ".cn-acts svg{width:36px;height:36px;fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}",
    ".cn-swipe{display:flex;align-items:center;gap:10px}",
    ".cn-swipe svg{width:38px;height:38px;fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}",
    ".cn-rule{width:110px;height:7px;border-radius:3px;background:var(--ac)}",
    ".cn-t em,.cn-b em{font-style:normal}",

    /* 1) 에디토리얼 — 깊은 검정, 강조색 글자, 숫자는 크게 */
    ".pk-editorial{background:#0b0d0c;color:#f3f4f1}",
    ".pk-editorial .cn-bg{background:radial-gradient(1100px 760px at 108% -8%,color-mix(in srgb,var(--ac) 26%,transparent),transparent 62%),radial-gradient(900px 600px at -20% 120%,color-mix(in srgb,var(--ac) 10%,transparent),transparent 60%)}",
    ".pk-editorial .cn-k{color:var(--ac)}",
    ".pk-editorial .cn-t em{color:var(--ac)}",
    ".pk-editorial .cn-b{color:#b9c0bb}",
    ".pk-editorial .cn-idx,.pk-editorial .cn-foot{color:#6c746f}",
    ".pk-editorial .cn-num{color:var(--ac)}",
    ".pk-editorial .cn-list li{border-bottom:2px solid #1f2522;padding-bottom:calc(22px*var(--u))}",
    ".pk-editorial .cn-list li:last-child{border-bottom:0}",
    ".pk-editorial .cn-list .cn-mk{border:3px solid var(--ac);color:var(--ac)}",
    ".pk-editorial .cn-cmp .cn-side{background:#141816;border:2px solid #232a26}",
    ".pk-editorial .cn-cmp .cn-side:first-child .cn-nm{color:var(--ac)}",
    ".pk-editorial .cn-cmp .cn-pt i{color:var(--ac)}",
    ".pk-editorial .cn-quote{color:var(--ac)}",
    ".pk-editorial .cn-acts span{border:2px solid #2b322e;color:#e8ebe8}",
    ".pk-editorial .cn-acts span:first-child{background:var(--ac);border-color:var(--ac);color:#0b0d0c}",

    /* 2) 매거진 — 종이색, 명조 제목, 형광펜 강조, 가는 선 */
    ".pk-magazine{background:#f2efe7;color:#171614}",
    ".pk-magazine .cn-bg{background:linear-gradient(#0000 0,#0000 100%),repeating-linear-gradient(0deg,rgba(0,0,0,.018) 0 2px,transparent 2px 6px)}",
    ".pk-magazine .cn-top{border-bottom:2px solid #171614;padding-bottom:22px;height:auto}",
    ".pk-magazine .cn-foot{border-top:2px solid #171614;padding-top:20px;height:auto;color:#6d685e}",
    ".pk-magazine .cn-idx{color:#6d685e}",
    ".pk-magazine .cn-t{font-family:var(--tf,CNHahmlet),serif;font-weight:800;letter-spacing:-.04em;line-height:1.18}",
    ".pk-magazine .cn-t em{background:linear-gradient(transparent 58%,color-mix(in srgb,var(--ac) 55%,transparent) 58%,color-mix(in srgb,var(--ac) 55%,transparent) 92%,transparent 92%)}",
    ".pk-magazine .cn-k{color:#6d685e;letter-spacing:.24em}",
    ".pk-magazine .cn-b{color:#3d3a34}",
    ".pk-magazine .cn-num{font-family:var(--tf,CNHahmlet),serif;font-weight:800;color:#171614}",
    ".pk-magazine .cn-rule{background:#171614;height:3px;width:120px}",
    ".pk-magazine .cn-list li{border-top:2px solid #cfc9bb;padding-top:calc(22px*var(--u))}",
    ".pk-magazine .cn-list .cn-mk{background:#171614;color:#f2efe7;border-radius:12px;font-family:CNHahmlet,serif}",
    ".pk-magazine .cn-cmp{gap:0}",
    ".pk-magazine .cn-cmp .cn-side{border-radius:0;padding:12px 40px}",
    ".pk-magazine .cn-cmp .cn-side+.cn-side{border-left:2px solid #171614}",
    ".pk-magazine .cn-cmp .cn-nm{font-family:CNHahmlet,serif;font-size:calc(58px*var(--u))}",
    ".pk-magazine .cn-quote{font-family:CNHahmlet,serif;color:color-mix(in srgb,var(--ac) 70%,#171614)}",
    ".pk-magazine .cn-acts span{border:2px solid #171614}",
    ".pk-magazine .cn-acts span:first-child{background:#171614;color:#f2efe7}",

    /* 3) 포토 — 사진 꽉 채움 + 아래 그늘, 강조는 색 띠 */
    ".pk-photo{background:#101214;color:#fff}",
    ".pk-photo .cn-bg{background-image:var(--img,none),radial-gradient(900px 900px at 15% 0%,color-mix(in srgb,var(--ac) 70%,#000),transparent 70%),radial-gradient(900px 900px at 100% 100%,#1c2b4a,transparent 70%),linear-gradient(160deg,#20262c,#0c0e10)}",
    ".pk-photo .cn-bg::after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.42) 0%,rgba(0,0,0,0) 22%,rgba(0,0,0,0) 38%,rgba(0,0,0,.72) 72%,rgba(0,0,0,.86) 100%)}",
    ".pk-photo .cn-main{justify-content:flex-end}",
    ".pk-photo.L1 .cn-main{justify-content:center}",
    ".pk-photo.L2 .cn-main{justify-content:flex-start}",
    ".pk-photo .cn-t{font-family:var(--tf,CNGmarket),sans-serif;font-weight:700;letter-spacing:-.03em;line-height:1.24}",
    ".pk-photo .cn-t em{background:var(--ac);color:#0b0b0b;padding:0 .14em;box-decoration-break:clone;-webkit-box-decoration-break:clone;border-radius:6px}",
    ".pk-photo .cn-k{color:#fff;opacity:.9}",
    ".pk-photo .cn-b{color:rgba(255,255,255,.86)}",
    ".pk-photo .cn-idx,.pk-photo .cn-foot{color:rgba(255,255,255,.75)}",
    ".pk-photo .cn-num{color:var(--ac);font-family:CNGmarket,sans-serif}",
    ".pk-photo .cn-list li{background:rgba(10,12,14,.58);border-radius:24px;padding:22px 28px}",
    ".pk-photo .cn-list .cn-mk{background:var(--ac);color:#0b0b0b}",
    ".pk-photo .cn-cmp .cn-side{background:rgba(10,12,14,.62);border:2px solid rgba(255,255,255,.14)}",
    ".pk-photo .cn-cmp .cn-pt i{color:var(--ac)}",
    ".pk-photo .cn-quote{color:var(--ac)}",
    ".pk-photo .cn-acts span{background:rgba(255,255,255,.14);border:2px solid rgba(255,255,255,.3)}",
    ".pk-photo .cn-acts span:first-child{background:var(--ac);color:#0b0b0b;border-color:var(--ac)}",

    /* 4) 파스텔 — 브랜드색을 옅게, 흰 판 위 둥근 칩 */
    ".pk-pastel{background:color-mix(in srgb,var(--ac) 16%,#fffdf8);color:#1c1f23}",
    ".pk-pastel .cn-bg{background:radial-gradient(700px 520px at 100% 0%,color-mix(in srgb,var(--ac) 34%,transparent),transparent 70%),radial-gradient(640px 480px at 0% 100%,rgba(255,255,255,.75),transparent 70%)}",
    ".pk-pastel .cn-t{font-family:var(--tf,CNSuit),sans-serif;font-weight:700;letter-spacing:-.035em}",
    ".pk-pastel .cn-t em{background:color-mix(in srgb,var(--ac) 42%,#fff);border-radius:14px;padding:0 .16em;box-decoration-break:clone;-webkit-box-decoration-break:clone}",
    ".pk-pastel .cn-k{align-self:flex-start;background:#fff;color:color-mix(in srgb,var(--ac) 65%,#1c1f23);border-radius:999px;padding:16px 32px;letter-spacing:.06em;font-size:calc(29px*var(--u));box-shadow:0 10px 30px rgba(0,0,0,.06)}",
    ".pk-pastel .cn-b{color:#4a4f57}",
    ".pk-pastel .cn-idx,.pk-pastel .cn-foot{color:#7a808a}",
    ".pk-pastel .cn-num{color:color-mix(in srgb,var(--ac) 75%,#1c1f23);font-family:CNSuit,sans-serif}",
    ".pk-pastel .cn-list li{background:#fff;border-radius:28px;padding:24px 30px;box-shadow:0 14px 34px rgba(30,40,60,.06)}",
    ".pk-pastel .cn-list .cn-mk{background:var(--ac);color:#fff}",
    ".pk-pastel .cn-cmp .cn-side{background:#fff;box-shadow:0 18px 40px rgba(30,40,60,.07)}",
    ".pk-pastel .cn-cmp .cn-side:first-child .cn-nm{color:color-mix(in srgb,var(--ac) 70%,#1c1f23)}",
    ".pk-pastel .cn-quote{color:var(--ac)}",
    ".pk-pastel .cn-acts span{background:#fff;box-shadow:0 10px 26px rgba(30,40,60,.08)}",
    ".pk-pastel .cn-acts span:first-child{background:#1c1f23;color:#fff}",

    /* 표지·마무리 공통 */
    ".r-cover .cn-t{--ts:132px}",
    ".r-cta .cn-t{--ts:110px}",
    ".r-quote .cn-t{--ts:82px;line-height:1.34}",
    ".cn-center .cn-main{text-align:center;align-items:center}",
    ".cn-center .cn-rule,.cn-center .cn-k{align-self:center}"
  ].join("\n");

  function injectStyle() {
    if (document.getElementById("cn-render-style")) return;
    var st = document.createElement("style");
    st.id = "cn-render-style";
    st.textContent = STYLE;
    document.head.appendChild(st);
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function hl(s) { return esc(s).replace(/\{([^}]+)\}/g, "<em>$1</em>"); }
  function plain(s) { return String(s || "").replace(/[{}]/g, ""); }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }

  var ICON = {
    save: '<svg viewBox="0 0 24 24"><path d="M6 3h12v18l-6-4-6 4z"/></svg>',
    share: '<svg viewBox="0 0 24 24"><path d="M4 12l16-8-6 16-2-6z"/></svg>',
    follow: '<svg viewBox="0 0 24 24"><circle cx="10" cy="8" r="4"/><path d="M3 21a7 7 0 0 1 14 0M19 8v6M16 11h6"/></svg>',
    arrow: '<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
  };

  function body(s) {
    var r = s.role, k = s.kicker ? '<div class="cn-k" data-ed="kicker">' + esc(s.kicker) + "</div>" : "";
    var t = '<h2 class="cn-t' + (r === "cover" ? " cn-big" : "") + '" data-ed="title">' + hl(s.title) + "</h2>";
    var b = s.body ? '<p class="cn-b" data-ed="body">' + hl(s.body) + "</p>" : "";
    if (r === "cover") return k + t + b;
    if (r === "number") return k + '<div class="cn-num" data-ed="num">' + esc(s.num || "") + "</div>" + t + b;
    if (r === "steps" || r === "list") {
      var li = (s.items || []).map(function (x, j) {
        return '<li><span class="cn-mk">' + (r === "steps" ? pad2(j + 1) : "✓") + "</span><span>" + hl(x) + "</span></li>";
      }).join("");
      return k + t + '<ul class="cn-list" data-ed="items">' + li + "</ul>" + b;
    }
    if (r === "compare") {
      var side = function (o) {
        o = o || {};
        return '<div class="cn-side"><div class="cn-nm">' + esc(o.name || "") + "</div>" + (o.points || []).map(function (p) {
          var minus = /^[-−]/.test(p);
          return '<div class="cn-pt"><i>' + (minus ? "−" : "+") + "</i><span>" + esc(p.replace(/^[+\-−]\s*/, "")) + "</span></div>";
        }).join("") + "</div>";
      };
      return k + t + '<div class="cn-cmp" data-ed="compare">' + side(s.a) + side(s.b) + "</div>" + b;
    }
    if (r === "quote") return k + '<div class="cn-quote">“</div>' + t + b;
    if (r === "cta") {
      return k + t + b + '<div class="cn-acts"><span>' + ICON.save + "저장</span><span>" + ICON.share + "공유</span><span>" +
        ICON.follow + "팔로우</span></div>";
    }
    return k + t + b;
  }

  /** 장 하나를 원본 크기(1080×H) DOM으로. ctx = {pack, brand, font, coverFont, size, ratio} */
  function render(s, i, total, ctx) {
    injectStyle();
    ctx = ctx || {};
    var pack = ctx.pack || "editorial";
    var brand = ctx.brand || {};
    var el = document.createElement("div");
    var layout = (s.layout || 0) % LAYOUTS;
    var center = (s.role === "cover" || s.role === "cta" || s.role === "quote") && layout === 1 && pack !== "photo";
    el.className = "cn-card pk-" + pack + " r-" + s.role + " L" + layout + (center ? " cn-center" : "");
    var u = { S: 0.88, M: 1, L: 1.12 }[ctx.size || "M"] || 1;
    el.style.setProperty("--u", String(u));
    el.dataset.u = String(u);
    el.style.setProperty("--ac", /^#[0-9a-fA-F]{6}$/.test(brand.color || "") ? brand.color : "#37e0bd");
    el.style.setProperty("--h", (RATIO_H[ctx.ratio] || 1350) + "px");
    var tf = fontCss(i === 0 && ctx.coverFont ? ctx.coverFont : (ctx.font || ""));
    if (ctx.font || (i === 0 && ctx.coverFont)) el.style.setProperty("--tf", tf);
    var bgUrl = s.bg && s.bg.url ? s.bg.url : "";
    if (bgUrl && pack === "photo") el.style.setProperty("--img", 'url("' + bgUrl.replace(/"/g, "") + '")');
    var name = brand.logo ? '<img src="' + esc(brand.logo) + '" alt="">' : '<span class="cn-dot"></span>' + esc(brand.name || "");
    var foot = i === 0 ? '<span>' + esc(brand.handle ? "@" + brand.handle.replace(/^@/, "") : "") + '</span><span class="cn-swipe">넘겨보기 ' + ICON.arrow + "</span>"
      : '<span>' + esc(brand.handle ? "@" + brand.handle.replace(/^@/, "") : "") + "</span><span></span>";
    el.innerHTML = '<div class="cn-bg"></div><div class="cn-top"><span class="cn-brand">' + name + '</span><span class="cn-idx">' +
      pad2(i + 1) + " / " + pad2(total) + '</span></div><div class="cn-main">' + body(s) + '</div><div class="cn-foot">' + foot + "</div>";
    // 제목 글꼴: 에디토리얼은 산세리프 기본이지만 글꼴을 고르면 그 글꼴로
    if (ctx.font || (i === 0 && ctx.coverFont)) {
      var t = el.querySelector(".cn-t");
      if (t) t.style.fontFamily = tf + ",CNPretendard,sans-serif";
      var n = el.querySelector(".cn-num");
      if (n && pack !== "editorial") n.style.fontFamily = tf + ",CNPretendard,sans-serif";
    }
    return el;
  }

  /** ★넘침 판정의 주인 — 본문(.cn-main)이 칸을 넘치면 글자를 4%씩 줄인다(최대 30%). 결과 {overflow, scale}. 문서에 붙은 노드에서만 잴 수 있다. */
  function fit(card) {
    var main = card.querySelector(".cn-main");
    var base = parseFloat(card.dataset.u || "1");
    var f = 1;
    var over = function () { return main.scrollHeight > main.clientHeight + 1 || main.scrollWidth > main.clientWidth + 1; };
    card.style.setProperty("--u", String(base));
    while (over() && f > 0.7) {
      f -= 0.04;
      card.style.setProperty("--u", String(base * f));
    }
    var bad = over();
    card.dataset.overflow = bad ? "1" : "0";
    return { overflow: bad, scale: Math.round(f * 100) / 100 };
  }

  /** 화면에 축소해 붙인다. host 안을 비우고 width 폭으로 맞춘다. 돌려주는 값 = {card, fit} */
  function mount(host, s, i, total, ctx, width) {
    var card = render(s, i, total, ctx);
    var h = RATIO_H[ctx && ctx.ratio] || 1350;
    var w = width || host.clientWidth || 300;
    var k = w / W;
    host.innerHTML = "";
    host.style.position = "relative";
    host.style.width = w + "px";
    host.style.height = Math.round(h * k) + "px";
    host.style.overflow = "hidden";
    var scaler = document.createElement("div");
    scaler.style.cssText = "position:absolute;left:0;top:0;transform-origin:0 0;transform:scale(" + k + ")";
    scaler.appendChild(card);
    host.appendChild(scaler);
    var r = fit(card);
    return { card: card, fit: r };
  }

  function fontsReady() {
    injectStyle();
    var fams = ["CNPretendard", "CNGmarket", "CNSuit", "CNHahmlet", "CNMyeongjo", "CNBlackHan", "CNJalnan", "CNGowun"];
    var loads = [];
    if (document.fonts && document.fonts.load) {
      fams.forEach(function (f) { loads.push(document.fonts.load("800 40px " + f, "가나다ABC123").catch(function () {})); });
      return Promise.all(loads).then(function () { return document.fonts.ready; });
    }
    return Promise.resolve();
  }

  /** 다운로드용 — 화면과 같은 render·fit 결과를 원본 크기로 찍는다. 화면 밖 무대에 잠깐 붙였다 뗀다. */
  function snapshot(s, i, total, ctx, type) {
    if (!window.htmlToImage) return Promise.reject(new Error("이미지 변환 도구를 못 불러왔어요"));
    var stage = document.getElementById("cn-stage");
    if (!stage) {
      stage = document.createElement("div");
      stage.id = "cn-stage";
      stage.style.cssText = "position:fixed;left:-20000px;top:0;width:1080px;pointer-events:none;opacity:1";
      document.body.appendChild(stage);
    }
    var card = render(s, i, total, ctx);
    stage.innerHTML = "";
    stage.appendChild(card);
    var r = fit(card);
    var h = RATIO_H[ctx && ctx.ratio] || 1350;
    var opt = { width: W, height: h, pixelRatio: 1, quality: 0.93, cacheBust: false,
      style: { transform: "none" } };
    var run = type === "png" ? window.htmlToImage.toBlob(card, opt) : window.htmlToImage.toJpeg(card, opt).then(function (u) {
      return fetch(u).then(function (x) { return x.blob(); });
    });
    return run.then(function (blob) { stage.innerHTML = ""; return { blob: blob, fit: r }; });
  }

  /** 모든 장 → ZIP(Blob). onProgress(i, n). 넘침 장 번호 목록도 돌려준다. */
  function exportZip(car, ctx, baseName, onProgress) {
    var slides = (car && car.slides) || [];
    var zip = new window.JSZip();
    var over = [];
    return fontsReady().then(function () {
      var p = Promise.resolve();
      slides.forEach(function (s, i) {
        p = p.then(function () {
          if (onProgress) onProgress(i, slides.length);
          return snapshot(s, i, slides.length, ctx, "jpeg").then(function (r) {
            if (r.fit.overflow) over.push(i + 1);
            zip.file((baseName || "card") + "_" + pad2(i + 1) + ".jpg", r.blob);
          });
        });
      });
      return p;
    }).then(function () {
      var cap = (car.caption || "") + (car.hashtags && car.hashtags.length ? "\n\n" + car.hashtags.map(function (h) { return "#" + h; }).join(" ") : "");
      if (cap.trim()) zip.file("caption.txt", cap);
      return zip.generateAsync({ type: "blob" });
    }).then(function (blob) { return { blob: blob, overflow: over }; });
  }

  window.CardNews = {
    W: W, RATIO_H: RATIO_H, FONTS: FONTS, PACKS: PACKS, ROLE_NAMES: ROLE_NAMES, LAYOUTS: LAYOUTS,
    render: render, fit: fit, mount: mount, snapshot: snapshot, exportZip: exportZip, fontsReady: fontsReady,
    plain: plain, esc: esc, hl: hl
  };
})();
