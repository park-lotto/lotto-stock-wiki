"""Vertex 안내 영상 v4 — **4단계(가입 → 클라우드 셸 열기 → 명령 붙여넣기 → 나온 한 줄 붙여넣고 연결)** 장면 재료(관제 119).
  py tools/vertex_guide/prep_v4.py <옛 영상 v3.mp4> <스크립트 출력 ansi> <출력폴더>
  node tools/vertex_guide/remotion/render.mjs <출력폴더> <out.mp4>

재료는 셋이다 — 전부 **실물**에서 온다:
  ① 1단계(가입·결제·2단계 인증)와 💳 결제 안내 = 옛 영상(실제 구글 콘솔 캡처, 개인정보 가림 끝난 것)의 화면 부분을 잘라 쓴다.
     옛 캡처 원본(.playwright-mcp/vertex_cap)은 이 PC에 없다(prep_v3.py 머리말과 같은 사정). 강조 상자는 이미 그려져 있어 hl 은 비운다.
  ② 2·3·4단계 마이페이지 칸 = 진짜 앱(격리 DB·로그인 끔)의 settings.html#keys 「🚀 구글 버텍스 API」 칸을 찍는다.
  ③ 검은 창 = vertex_setup.sh 를 가짜 gcloud(셸 함수)로 실제로 돌린 출력(ANSI) 그대로를 터미널 모양으로 그린다.
     계정·프로젝트·키는 예시값이고 키 글자는 •••로 가린다. 구글 화면 테두리는 흉내 내지 않는다(검은 창 글자만).
장면 순서·자막은 아래 SCENES 한 곳. Guide.tsx 는 그리기만 한다.
"""
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OLD, ANSI, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
BG = (0x0B, 0x14, 0x18)
INTRO, PER = 3.2, 6.0           # 옛 영상(Guide.tsx v3) 시간 상수

# 옛 영상의 장면 번호(0부터, v3 순서) → 그 화면 부분을 잘라 쓴다
OLD_PICK = {0: "freetrial", 1: "payment", 2: "mfa", 3: "twosv", 19: "billing_upgrade", 20: "billing_close"}


def crop_old(idx, name):
    """옛 영상 idx 장면의 5초 지점 프레임에서 배경색이 아닌 화면 상자만 잘라낸다(머리글·자막 띠 제외)."""
    t = INTRO + idx * PER + 5.0
    tmp = OUT / f"_old_{idx}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(OLD), "-frames:v", "1", str(tmp)], check=True)
    im = Image.open(tmp).convert("RGB")
    w, h = im.size
    top, bot = 125, h - 195                      # Guide.tsx HEAD_H 120 · CAP_H 190 안쪽만 본다
    px = im.load()
    xs, ys = [], []
    for y in range(top, bot, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if abs(r - BG[0]) + abs(g - BG[1]) + abs(b - BG[2]) > 60:
                xs.append(x); ys.append(y)
    box = (max(0, min(xs) - 2), max(top, min(ys) - 2), min(w, max(xs) + 3), min(bot, max(ys) + 3))
    c = im.crop(box)
    fn = f"v4_{name}.png"
    c.save(OUT / fn)
    tmp.unlink()
    return fn, c.size


def capture_app():
    """진짜 앱의 마이페이지 버텍스 칸 — 빈 칸 / 예시 한 줄을 붙여넣은 칸. 강조 좌표(화면 px × 배율)를 돌려준다."""
    work = OUT / "_work"
    shutil.rmtree(work, ignore_errors=True); work.mkdir()
    from shopping_shorts import app as module
    import uvicorn
    from playwright.sync_api import sync_playwright
    module.DB_PATH = str(work / "qa.db"); module._AUTH_ON = False
    module.keycrypt.enabled = lambda: True          # 칸 보이기만(저장은 안 한다)
    port = 8796
    server = uvicorn.Server(uvicorn.Config(module.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)
    K = 1.5
    one_line = ('{"type":"service_account","project_id":"shorts-261005-1208","private_key_id":"••••••••",'
                '"private_key":"-----BEGIN PRIVATE KEY-----\\n••••••••\\n-----END PRIVATE KEY-----\\n",'
                '"client_email":"shortsmaker@shorts-261005-1208.iam.gserviceaccount.com"}')
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1100, "height": 1000}, device_scale_factor=K)
        pg.goto(f"http://127.0.0.1:{port}/settings.html#keys", wait_until="networkidle"); pg.wait_for_timeout(1500)
        card = pg.locator("#vertexCard")
        if not card.is_visible():
            raise SystemExit("버텍스 칸이 안 보인다(keycrypt 비활성?)")
        card.scroll_into_view_if_needed(); pg.wait_for_timeout(300)

        def rects(*ids):
            r = pg.evaluate("""(ids)=>{const c=document.getElementById('vertexCard').getBoundingClientRect();
              return ids.map(id=>{const b=document.getElementById(id).getBoundingClientRect();
              return [b.x-c.x,b.y-c.y,b.width,b.height]})}""", list(ids))
            return [[round(v * K) for v in q] for q in r]
        card.screenshot(path=str(OUT / "v4_card_empty.png"))
        res["empty"] = ("v4_card_empty.png", Image.open(OUT / "v4_card_empty.png").size,
                        {"shell": rects("vertexShellBtn"), "cmd": rects("vertexCmdBtn", "vertexCmd")})
        pg.fill("#vertexJson", one_line); pg.wait_for_timeout(300)
        card.screenshot(path=str(OUT / "v4_card_pasted.png"))
        res["pasted"] = ("v4_card_pasted.png", Image.open(OUT / "v4_card_pasted.png").size,
                         {"paste": rects("vertexJson", "vertexBtn")})
        b.close()
    server.should_exit = True
    return res


_ANSI = re.compile(r"\x1b\[([0-9;]*)m")
_COLOR = {"1;36": "#5fd7ff", "1;32": "#5fff87", "1;31": "#ff5f5f", "1;33": "#ffd75f", "1": "#ffffff"}


def ansi_html(text):
    """ANSI 색 → span. 키 글자(\\u2022 이스케이프)는 화면에서 •••로 보이게만 바꾼다."""
    text = text.replace("\\u2022" * 8, "••••••••")
    out, cur = [], None
    pos = 0
    for m in _ANSI.finditer(text):
        out.append(html.escape(text[pos:m.start()])); pos = m.end()
        code = m.group(1)
        if cur:
            out.append("</span>"); cur = None
        if code and code != "0" and code in _COLOR:
            out.append(f'<span style="color:{_COLOR[code]};font-weight:700">'); cur = code
    out.append(html.escape(text[pos:]))
    if cur:
        out.append("</span>")
    return "".join(out)


def render_terminal(lines_ansi, fname, mark=None):
    """검은 창 그림. mark = 강조할 줄의 글자 일부 — 그 줄들의 좌표를 돌려준다."""
    from playwright.sync_api import sync_playwright
    K = 1.5
    body = "".join(f'<div class="l">{ansi_html(l) or "&nbsp;"}</div>' for l in lines_ansi)
    page = f"""<!doctype html><meta charset="utf-8"><style>
      body{{margin:0;background:#1e1e1e}}
      .bar{{background:#2d2d2d;color:#bbb;font:600 15px 'Malgun Gothic',sans-serif;padding:9px 16px;border-bottom:1px solid #111}}
      .t{{padding:14px 18px 18px;color:#e6e6e6;font:15px/1.55 Consolas,'D2Coding','Malgun Gothic',monospace;width:820px;
          white-space:pre-wrap;word-break:break-all}}
    </style><div id="root" style="width:860px"><div class="bar">검은 창 (클라우드 셸 터미널)</div><div class="t">{body}</div></div>"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1100, "height": 800}, device_scale_factor=K)
        pg.set_content(page); pg.wait_for_timeout(200)
        pg.locator("#root").screenshot(path=str(OUT / fname))
        hl = []
        if mark:
            hl = pg.evaluate("""(marks)=>{const r=document.getElementById('root').getBoundingClientRect();
              const out=[];for(const m of marks){const ls=[...document.querySelectorAll('.l')].filter(e=>e.textContent.includes(m));
              if(!ls.length)continue;const a=ls[0].getBoundingClientRect(),z=ls[ls.length-1].getBoundingClientRect();
              out.push([a.x-r.x,a.y-r.y,Math.max(a.width,z.width),z.bottom-a.top])}return out}""", mark)
            hl = [[round(v * K) for v in q] for q in hl]
        b.close()
    return fname, Image.open(OUT / fname).size, hl


def main():
    old = {name: crop_old(i, name) for i, name in OLD_PICK.items()}
    app = capture_app()
    raw = ANSI.read_text(encoding="utf-8").splitlines()
    prompt = "\x1b[1;32myou@cloudshell\x1b[0m:\x1b[1;36m~\x1b[0m$ curl -fsSL https://shoppingshorts.duckdns.org/landing/vertex_setup.sh | bash"
    cut = next(i for i, l in enumerate(raw) if "5/5" in l)
    upto3 = next(i for i, l in enumerate(raw) if "API 켜짐" in l) + 1      # 첫 장면은 3/5 까지만 — 줄이 많으면 글자가 깨알이 된다
    term_a = render_terminal([prompt] + raw[:upto3], "v4_term_run.png", mark=["curl -fsSL"])
    term_b = render_terminal(raw[cut:], "v4_term_done.png", mark=['{"type"'])

    def sc(src, step, title, cap, hl=()):
        fn, (w, h) = src[0], src[1]
        return {"file": fn, "w": w, "h": h, "step": step, "title": title, "cap": cap, "hl": [list(x) for x in hl]}
    e_fn, e_sz, e_hl = app["empty"]
    p_fn, p_sz, p_hl = app["pasted"]
    scenes = [
        sc(old["freetrial"], "1", "구글 클라우드 무료 체험 가입",
           ["cloud.google.com 에서 「무료로 시작하기」", "국가 대한민국 · 약관 2개 체크 → 「계속」 (이미 가입했으면 2단계로)"]),
        sc(old["payment"], "1", "결제 정보 입력",
           ["계좌 유형은 「개인」으로 바꾸세요", "이름·주소·카드 등록 — 직접 유료 전환 전엔 청구되지 않아요"]),
        sc(old["mfa"], "1", "이 화면이 뜨면 — 2단계 인증",
           ["구글 클라우드는 2단계 인증을 켜야 들어갈 수 있어요", "「MFA 사용 설정」을 누르세요 (이미 켜 두셨으면 안 떠요)"]),
        sc(old["twosv"], "1", "2단계 인증 켜기",
           ["「2단계 인증 사용 설정」 → 휴대폰으로 확인", "켠 뒤 몇 분 지나면 구글 클라우드가 열려요"]),
        sc((e_fn, e_sz), "2", "클라우드 셸 열기",
           ["마이페이지 › 🔑 내 키 등록 › 🚀 구글 버텍스 API 에서 「클라우드 셸 열기」", "화면 아래 검은 창이 뜰 때까지 기다리세요 (처음엔 1~2분)"], e_hl["shell"]),
        sc((e_fn, e_sz), "3", "명령 복사",
           ["「명령 복사」를 누르세요", "검은 창을 한 번 클릭 → Ctrl+V 로 붙여넣고 엔터"], e_hl["cmd"]),
        sc(term_a, "3", "붙여넣고 엔터 — 알아서 설정돼요",
           ["「승인(Authorize)」 창이 뜨면 「승인」을 누르세요", "API·서비스 계정·역할·키를 알아서 만들어요 (2~3분)"], term_a[2]),
        sc(term_b, "4", "나온 한 줄 복사",
           ["초록 줄 아래 { 부터 } 까지 마우스로 끌어서 복사", "이 글은 비밀번호와 같아요 — 다른 곳에 올리지 마세요"], term_b[2]),
        sc((p_fn, p_sz), "4", "붙여넣고 「확인하고 연결」",
           ["마이페이지 칸에 붙여넣고 「확인하고 연결」", "「확인 완료」가 뜨면 끝 — 대본 쓰기·장면 매칭이 버텍스로 돌아가요"], p_hl["paste"]),
        sc(old["billing_upgrade"], "주의", "카드가 결제되지 않게",
           ["맨 위 파란 「업그레이드」는 누르지 마세요", "「무료 체험판 계정」이면 카드는 청구되지 않아요 — 90일 끝나면 스스로 멈춰요"]),
        sc(old["billing_close"], "주의", "이미 업그레이드했다면",
           ["결제 › 계정 관리 › 「결제 계정 폐쇄」", "그때까지 쓴 만큼만 청구되고 멈춰요 — 예산 알림만으로는 안 막혀요"]),
    ]
    (OUT / "scenes.json").write_text(json.dumps(scenes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(scenes)} scenes → {OUT}")
    for s in scenes:
        print(" ", s["step"], s["title"], s["w"], "x", s["h"], "hl", len(s["hl"]))


if __name__ == "__main__":
    main()
