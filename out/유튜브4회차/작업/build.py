"""유튜브 4회차 가편집 — 대본 B · 손그림 + 실제 완성 영상.
단계: voice(타입캐스트 박창수) → seg(장면별 영상) → final(합본+자막). 이미 만든 것은 건너뛴다(고친 장면만 지우고 다시).
사용: py build.py [voice|seg|final|all] [장면id...]
"""
import json, math, os, random, re, shutil, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W = Path(__file__).resolve().parent
REPO = Path(__import__("os").environ.get("LOTTO_REPO") or (Path.home() / "Desktop" / "로또의 주식"))   # 음성 합성(providers) 쓸 때만 필요
FD = W / "fonts"
PEN = str(FD / "NanumPenScript.ttf")
GAEGU = str(FD / "Gaegu-Bold.ttf")
JA = r"C:\Windows\Fonts\YuGothB.ttc"   # 윈도우 기본 일본어 글꼴
SUBF = str(W / "fonts" / "Pretendard-Black.otf")
DESK = W / "src"
VW, VH, FPS = 1920, 1080, 30
PAPER = (247, 243, 234)
INK = (34, 34, 38)
RED = (226, 64, 58)
YEL = (255, 214, 40)
ORANGE = (217, 119, 87)
BLUE = (58, 108, 216)
VOICE = "tc_68257f68bc6e3c161ab5078d"   # 필재 (사장님 11-04 — 2편과 같은 성우, 발음 뭉개짐 기록 때문에 1.1배)

# 실제 완성 영상 — 채널명 띠는 위를 잘라 숨긴다(crop = 위에서 자를 비율). 연예인·방송 화면 든 편은 뺐다.
SRC = {
    "choco":  ("숏클설치본시험_썰템쇼_초코무스.mp4", 0.125),
    "ottogi": ("숏클시험_6차_오뚜기.mp4", 0.125),
    "chal":   ("숏클시험_7차_찰떡.mp4", 0.125),
    "sun":    ("숏클시험_꿀템샷_선크림.mp4", 0.0),
    "lego":   ("썰템홈샷_25_lego.mp4", 0.085),
    "spat":   ("잇템로그_14_makeup_spatula.mp4", 0.0),
    "tint":   ("잇템로그_15_black_peel_off_lip_tattoo.mp4", 0.0),
    "tattoo": ("잇템로그_16_tattoo_cover_foundation.mp4", 0.0),
    "gdp":    ("지식롱폼_GDP착시_숏클_완성본.mp4", 0.0),
}

SCENES = [
 {"id": "sh01", "vis": {}, "text": "방금 보신 거, 사람이 친 건 딱 한 줄입니다. 원본 찾기부터 대본, 장면, 자막까지, 전부 클로드가 했습니다. 잘된 채널을 뜯어보고, 그 채널처럼 만듭니다. 그러니 채널을 하나만 할 이유가 없죠. 나도 될까? 키보드로 한 줄 칠 수 있으면 됩니다. 어떻게 하는지, 본편에서 끝까지 보여 드립니다."},  # 세로 쇼츠 나레이션(11-04)
 {"id": "sh04", "vis": {}, "text": "방금 보신 거, 사람이 친 건 딱 한 줄입니다. 지금 숏클 안에는 형식 여섯 가지, 채널 스타일 스물네 가지가 들어 있습니다. 그리고 매주 두 개씩, 새 스타일이 늘어납니다. 그러니 채널을 하나만 할 이유가 없죠. 열 개, 스무 개도 됩니다. 한 줄이면 되니까요. 어떻게 늘려 가는지, 본편에서 끝까지 보여 드립니다."},  # 세로 쇼츠 나레이션(11-04)
 {"id": "sh03", "vis": {}, "text": "방금 보신 거, 사람이 친 건 딱 한 줄입니다. 잘된 채널을 벤치마킹하라, 많이 들어 보셨죠? 그런데 벤치마킹은 베끼기가 아닙니다. 가져오는 건 후킹과 이야기 흐름입니다. 클로드는 채널 하나를 통째로 뜯어봅니다. 후킹, 순서, 장면 박자, 자막, 목소리, 배경음까지. 사람 손으로는 못 하는 일이죠. 어떻게 뜯어보는지, 본편에서 끝까지 보여 드립니다."},  # 세로 쇼츠 나레이션(11-04)
 {"id": "sh02", "vis": {}, "text": "방금 보신 거, 사람이 친 건 딱 한 줄입니다. 저희 회원 중에 쉰 살이 넘은 분이 계십니다. 컴퓨터는 이메일 보내는 게 전부였던 분이에요. 쇼츠 부업을 해 보겠다고 비싼 강의를 두 개나 들으셨는데, 둘 다 손편집 강의였습니다. 몇 달이 지나도, 올린 영상은 거의 없었죠. 게을러서였을까요? 아닙니다. 방법이 틀렸던 겁니다. 이제는 키보드로 한 줄이면 됩니다. 어떻게 하는지, 본편에서 끝까지 보여 드립니다."},  # 세로 쇼츠 나레이션(11-04)
 {"id": "s00", "vis": {"tiles": ["spat", "choco", "sun"], "ss": [4, 2, 3]},
  "text": "방금 보신 거, 사람이 친 건 딱 한 줄입니다. 지금 유튜브에선 조용히 판이 바뀌고 있습니다. 클로드의 시대가 왔습니다. 클로드? 그게 뭔데? 하실 겁니다. 그런데 이걸 먼저 알아챈 사람들은, 벌써 움직이고 있습니다. 오늘 끝까지 보시면 세 가지를 보시게 됩니다. 컴퓨터로 이메일만 보내던 쉰 살 회원이 어떻게 달라졌는지. 사람은 절대 못 하는 일을 클로드가 어떻게 해내는지. 그리고 채널을 하나가 아니라 수십 개 돌리는 방법까지. 이 영상을 처음 보셨다면, 정말 운이 좋으신 겁니다."},
 {"id": "s01", "vis": {"sketch": "member"},
  "text": "저희 회원 중에 쉰 살이 넘은 분이 계십니다. 컴퓨터는 이메일 보내는 정도가 전부였던 분이에요. 이분이 쇼츠로 부업을 해 보겠다고, 비싼 강의를 두 개나 들으셨습니다. 그런데 두 강의 모두, 결국 편집 앱으로 손편집하는 강의였습니다. 장면 자르고, 자막 하나하나 얹고, 목소리 맞추고. 몇 달이 지나도, 올린 영상은 거의 없었습니다. 어떠세요, 여러분 얘기 같지 않으신가요? 이분이 게을러서였을까요? 아닙니다. 솔직해집시다. 이제 그런 시대가 아니잖아요."},
 {"id": "s02", "vis": {"sketch": "bench"},
  "text": "솔직하게 말씀드리면, 그 강의들이 말하는 방향은 맞습니다. 잘된 채널을 벤치마킹하라. 여러분도 이 말, 한 번쯤은 들어 보셨을 겁니다. 그런데 많은 분들이 여기서 오해하십니다. 벤치마킹은 남의 영상을 그대로 베끼는 게 아닙니다. 원본은 같은 걸 써도 되고, 비슷한 주제의 다른 원본을 가져와도 됩니다. 가져오는 건 영상이 아니라, 그 채널이 후킹을 어떻게 잡고, 이야기를 어떻게 끌고 가는지입니다. 방법은 이렇습니다. 터진 채널 하나를 고릅니다. 첫 삼 초에 어떻게 후킹하는지, 이야기가 어떤 순서로 흘러가는지, 장면을 어떻게 바꾸는지, 자막을 어디에 올리는지 뜯어봅니다. 그리고 그 방식은 따라 하고, 영상과 말은 내 것으로 채웁니다. 이게 정석입니다."},
 {"id": "s03", "vis": {"sketch": "limit"},
  "text": "문제는 여기서부터입니다. 뼈대를 알아낸 다음, 그걸 손으로 따라 만들라고 합니다. 여러분도 그러셨죠? 강의는 끝까지 들었는데, 막상 혼자 하려니 첫 장면부터 막히고. 한 채널도 버거운데, 채널을 두 개, 세 개 하려면요? 손편집이 그대로 두 배, 세 배가 됩니다. 그래서 강의를 몇 개를 들어도, 결국 편집 화면 앞에서 멈추는 겁니다."},
 {"id": "s04", "vis": {"sketch": "ddalkkak"},
  "text": "얼마나 답답하셨을까요. 이제는 클로드 하나면 됩니다. 복잡한 프로그램, 여러 개 켜 놓을 필요 없습니다. 뼈대를 뜯어보는 것도, 그걸 내 스타일로 바꿔 만드는 것도, 클로드가 합니다. 이게 대딸깍 시대입니다."},
 {"id": "s05", "vis": {"sketch": "myhand"},
  "text": "다른 길도 있죠. 아마 다 한 번씩 생각해 보셨을 겁니다. 강의를 더 듣는다. 결국 손편집을 더 잘하게 될 뿐입니다. 편집 앱을 더 좋은 걸로 바꾼다. 빨라지긴 하지만, 누르는 건 여전히 내 손입니다. 편집자에게 맡긴다. 채널이 늘수록 비용도 같이 늘어납니다. 셋 다 내 손에서 벗어나지 못합니다. 그래서 저희 방에서는 이런 말이 나옵니다. 아직도 편집 앱 붙잡고 손으로 자르고 있으면, 바보 소리 듣는다고요."},
 {"id": "s06", "vis": {"sketch": "history"},
  "text": "저도 처음엔 여러분과 똑같이 막혔습니다. 그래서 직접 만들었습니다. 숏클은 하루아침에 나온 프로그램이 아닙니다. 제가 이미 이 시장에 시간과 에너지를 갈아 넣어서 만든 프로그램입니다. 숏템메이커부터 지금까지, 고친 기록만 삼천구백 건이 넘습니다. 그 시행착오를 회원분들이 다시 겪지 않게, 전부 이 안에 넣었습니다."},
 {"id": "s07", "vis": {"tiles": ["ottogi", "tint", "sun", "lego"], "ss": [3, 3, 8, 4], "label": "styles"},
  "text": "지금 보시는 영상들, 전부 클로드가 만든 영상입니다. 스타일이 다 다르죠. 하고 싶은 채널 스타일을 고르고, 이 스타일로 만들어 달라고 하면, 원본은 클로드가 직접 찾아오고, 후킹과 이야기 흐름은 그 채널 방식대로 쇼츠가 나옵니다."},
 {"id": "s08", "vis": {"tiles": ["chal", "tattoo"], "ss": [6, 6], "label": "clothes"},
  "text": "여기서 정확히 말씀드리겠습니다. 클로드는 채널을 그대로 베끼지 않습니다. 잘된 채널의 영상들을 하나하나 분석합니다. 첫 삼 초에 어떻게 후킹하는지, 이야기를 어떤 순서로 끌고 가는지, 장면이 몇 초마다 바뀌는지, 자막은 어디에 어떤 글꼴과 색으로 올리는지, 목소리 톤과 배경음까지. 그 채널을 터지게 만든 규칙을 전부 뽑아냅니다. 그리고 그 규칙을 바탕으로 채널명, 글꼴, 색, 목소리, 음악을 바꿔서, 결국 나만의 채널 스타일로 만들어 냅니다. 솔직히 이건 사람이 할 수 있는 일이 아닙니다. 우리는 영상 하나 만들기도 벅찬데, 채널 하나를 이렇게 통째로 분석한다고요? 거의 불가능에 가깝습니다. 그걸 클로드가 해냅니다. 이게 클로드를 제대로 쓰는 방법입니다."},
 {"id": "s09", "vis": {"tiles": ["choco", "spat", "lego", "sun", "tint"], "ss": [10, 12, 12, 14, 10], "label": "multi"},
  "text": "여러분, 그동안 나도 이런 채널 한번 해 보고 싶다, 생각해 보신 적 있지 않으신가요? 남의 채널 보면서, 저건 어떻게 만들었지, 부러우셨던 적 있으시죠? 이제는 채널을 하나만 할 이유가 없습니다. 클로드의 벤치마킹 기술이면, 채널 열 개, 스무 개, 수십 개도 운영할 수 있습니다. 지금 숏클 안에는 이미 형식 여섯 가지, 채널 스타일 스물네 개가 들어 있습니다. 그리고 여기서 끝이 아닙니다. 매주 두 개씩, 새 스타일이 계속 늘어납니다. 그런데요, 솔직히 말씀드리면 진짜는 이게 아닙니다. 남이 골라 둔 스타일을 쓰는 것과, 내가 찜한 채널이라면 어떤 채널이든 직접 뜯어서 내 스타일로 만드는 것. 이 둘은 완전히 다른 얘기입니다. 이 얘기는 조금 뒤에 다시 꺼내 보겠습니다."},
 {"id": "s10", "vis": {"sketch": "global"},
  "text": "해외 채널 보면서, 저건 나랑 상관없는 얘기다, 생각하셨죠? 그런데 솔직히, 한국 시장은 좁습니다. 진짜 큰 시장은 바로 옆 일본부터, 미국, 러시아, 동남아까지 펼쳐져 있습니다. 쇼핑쇼츠로 돈을 벌 수 있는 시장이, 한국과는 비교도 안 되게 큽니다. 그 시장에 들어가는 첫걸음이, 바로 클로드를 배우는 겁니다."},
 {"id": "s11", "vis": {"sketch": "now"},
  "text": "아까 그 회원분, 이제는 편집 앱 대신 클로드 창부터 여십니다. 컴퓨터로 이메일만 보내던 분도 됩니다. 그게 대딸깍 시대입니다."},
 {"id": "s11b", "vis": {"sketch": "canido"},
  "text": "혹시 지금 이런 생각 드시나요? 좋은 건 알겠는데, 나도 될까? 컴퓨터도 잘 모르는데? 딱 하나만 할 줄 알면 됩니다. AI한테, 이런 영상 만들어 줘, 하고 키보드로 한 줄 칠 수 있으면 됩니다. 영상 맨 처음에 보셨던 것처럼요. 외국인 한국 화장품 영상 만들어 줘. 그 한 줄이 전부였습니다. 자판을 칠 줄 아시면, 시작할 수 있습니다."},
 {"id": "s12", "vis": {"full": "gdp", "ss": 95, "label": "cta"},
  "text": "정리하겠습니다. 벤치마킹은 맞습니다. 다만 이제 손으로 하는 시대가 아닙니다. 클로드 하나면, 잘된 채널의 규칙을 분석해서 나만의 채널로 만들 수 있습니다. 쇼츠도, 지금 보시는 이런 롱폼도요. 아까 조금 뒤에 말씀드린다고 했던 거, 기억나시죠? 내가 원하는 채널이라면 어떤 채널이든 벤치마킹할 수 있는 엔진 분석 도구. 그걸로 나만의 채널을 끊임없이 늘려 가는 능력. 그 능력을 만드는 곳이, 바로 고급 과정입니다. 그리고 저희는 혼자 하지 않습니다. 크루로 움직입니다. 한 사람 한 사람이 모여 군단이 되고, 정보를 함께 나누면서 같이 커 갑니다. 숏템메이커로 시작해서, 숏클이 나온 지 아직 얼마 안 됐습니다. 지금 배우시면, 크루의 롤모델이 될 수 있고, 누군가에게 배움을 전해 줄 기회도 생깁니다. 제가 지금 여러분과 이 기회를 나누는 것처럼요. 이 영상을 처음 보셨다면, 행운이라고 말씀드렸죠. 신청은 고정 댓글에 있습니다."},
]


def run(cmd):
    if cmd and cmd[0] == "ffmpeg":       # 가상 메모리 부족(11-04 malloc 실패) — 출력 스레드 제한
        cmd = cmd[:-1] + ["-threads", "4", cmd[-1]]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        sys.stderr.write(r.stderr.decode("utf-8", "replace")[-2000:])
        raise SystemExit(f"실패: {cmd[:6]}")
    return r


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())


# ───────── 음성 ─────────
def voice(ids):
    sys.path.insert(0, str(REPO))
    from shopping_shorts.channelkit import providers
    kf = Path.home() / ".shortem" / "keys" / "typecast"
    synth = providers.typecast_synth(VOICE, tempo=1.1, key_file=str(kf) if kf.is_file() else None)
    (W / "voice").mkdir(exist_ok=True)
    for s in SCENES:
        if ids and s["id"] not in ids:
            continue
        out = W / "voice" / f"{s['id']}.mp3"
        if out.exists() and out.stat().st_size > 1000:
            continue
        synth(s["text"], str(out))
        print("음성", s["id"], round(dur(out), 2), "초", flush=True)


# ───────── 손그림 ─────────
R = random.Random(7)


def paper():
    im = Image.new("RGB", (VW, VH), PAPER)
    n = Image.effect_noise((VW // 4, VH // 4), 14).resize((VW, VH)).filter(ImageFilter.GaussianBlur(1))
    return Image.blend(im, Image.merge("RGB", (n, n, n)).point(lambda v: 247 - (128 - v) // 6 if True else v), 0.25)


def jl(d, a, b, c=INK, w=6):
    for k in range(2):
        pts = []
        n = max(2, int(math.dist(a, b) / 40))
        for i in range(n + 1):
            t = i / n
            pts.append((a[0] + (b[0] - a[0]) * t + R.uniform(-2.2, 2.2), a[1] + (b[1] - a[1]) * t + R.uniform(-2.2, 2.2)))
        d.line(pts, fill=c, width=w if k == 0 else max(2, w // 2), joint="curve")


def jrect(d, x0, y0, x1, y1, c=INK, w=6):
    jl(d, (x0, y0), (x1, y0), c, w); jl(d, (x1, y0), (x1, y1), c, w); jl(d, (x1, y1), (x0, y1), c, w); jl(d, (x0, y1), (x0, y0), c, w)


def jcirc(d, cx, cy, r, c=INK, w=6, a0=0, a1=360):
    for k in range(2):
        pts = [(cx + (r + R.uniform(-3, 3)) * math.cos(math.radians(a)), cy + (r + R.uniform(-3, 3)) * math.sin(math.radians(a))) for a in range(a0, a1 + 1, 6)]
        d.line(pts, fill=c, width=w if k == 0 else max(2, w // 2), joint="curve")


def arrow(d, a, b, c=INK, w=6):
    jl(d, a, b, c, w)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for s in (2.6, -2.6):
        jl(d, b, (b[0] + 34 * math.cos(ang + s), b[1] + 34 * math.sin(ang + s)), c, w)


def tx(d, xy, s, size=64, c=INK, font=PEN, anchor="la"):
    d.text(xy, s, font=ImageFont.truetype(font, size), fill=c, anchor=anchor)


def hl(d, box):
    d.rectangle(box, fill=YEL + (150,))


def person(d, cx, cy, s=1.0, c=INK):
    jcirc(d, cx, cy - 120 * s, 46 * s, c)
    jl(d, (cx - 80 * s, cy + 110 * s), (cx - 60 * s, cy - 40 * s), c); jl(d, (cx - 60 * s, cy - 40 * s), (cx + 60 * s, cy - 40 * s), c); jl(d, (cx + 60 * s, cy - 40 * s), (cx + 80 * s, cy + 110 * s), c)


def monitor(d, x0, y0, x1, y1):
    jrect(d, x0, y0, x1, y1); jl(d, ((x0 + x1) / 2, y1), ((x0 + x1) / 2, y1 + 50)); jl(d, ((x0 + x1) / 2 - 70, y1 + 50), ((x0 + x1) / 2 + 70, y1 + 50))


def claude_char(d, cx, cy, P=18):
    G = ["   ############  ", "   ##E######E##  ", " ################", "   ############  ", "    # #    # #   "]
    ox, oy = cx - len(G[0]) * P // 2, cy - len(G) * P
    for r_, row in enumerate(G):
        for c_, ch in enumerate(row):
            if ch != " ":
                d.rectangle((ox + c_ * P, oy + r_ * 2 * P, ox + c_ * P + P - 1, oy + r_ * 2 * P + 2 * P - 1), fill=(20, 20, 20) if ch == "E" else ORANGE)


def stamp(d, cx, cy, s, c=RED):
    jcirc(d, cx, cy, 165, c, 8)
    tx(d, (cx, cy), s, 64, c, GAEGU, "mm")


# 그림 = 요소 목록(차례로 그려진다). 각 요소는 draw(d) 함수.
def SK(name):
    E = []
    add = E.append
    if name == "member":
        add(lambda d: person(d, 330, 560, 1.4))
        add(lambda d: tx(d, (330, 760), "50대 회원", 64, INK, PEN, "mm"))
        add(lambda d: tx(d, (330, 830), "컴퓨터 = 이메일만", 52, BLUE, PEN, "mm"))
        for i, y in enumerate((220, 470)):
            add(lambda d, y=y, i=i: (jrect(d, 640, y, 980, y + 200), [jl(d, (670, y + 50 + k * 40), (950, y + 50 + k * 40), (150, 150, 150), 3) for k in range(2)],
                                    tx(d, (700, y + 150), f"강의 {i + 1}   ₩", 56, INK, PEN, "lm"), d.rectangle((830, y + 128, 950, y + 172), fill=INK)))
        add(lambda d: tx(d, (810, 730), "수백만 원 x 2", 70, RED, GAEGU, "mm"))
        add(lambda d: monitor(d, 1130, 220, 1700, 560))
        add(lambda d: [jl(d, (1170, 300 + k * 50), (1170 + R.randint(200, 480), 300 + k * 50), (160, 160, 160), 10) for k in range(5)])
        add(lambda d: tx(d, (1415, 690), "결국 손편집 강의", 64, INK, PEN, "mm"))
        add(lambda d: (jrect(d, 1250, 760, 1580, 960), [jl(d, (1250 + k * 66, 800), (1250 + k * 66, 960), INK, 3) for k in range(1, 5)], jl(d, (1250, 800), (1580, 800), INK, 4)))
        add(lambda d: tx(d, (1415, 1010), "몇 달 뒤... 올린 영상 거의 0", 50, RED, PEN, "mm"))
    elif name == "bench":
        add(lambda d: (jrect(d, 140, 330, 520, 750), tx(d, (330, 400), "터진 채널", 66, INK, PEN, "mm"), tx(d, (330, 520), "조회 300만", 60, RED, GAEGU, "mm"), tx(d, (330, 620), "조회 120만", 60, RED, GAEGU, "mm")))
        add(lambda d: (jcirc(d, 690, 520, 90), jl(d, (754, 584), (840, 670), INK, 12)))
        add(lambda d: arrow(d, (860, 540), (980, 540)))
        boxes = [("첫 3초", 1010, 180), ("대본 흐름", 1420, 180), ("장면 순서", 1010, 560), ("자막 위치", 1420, 560)]
        for t_, x, y in boxes:
            add(lambda d, t_=t_, x=x, y=y: (jrect(d, x, y, x + 370, y + 320), tx(d, (x + 185, y + 160), t_, 72, INK, PEN, "mm")))
        add(lambda d: tx(d, (1400, 950), "뼈대는 따라, 내용은 내 것", 70, BLUE, GAEGU, "mm"))
    elif name == "limit":
        for i in range(3):
            x = 220 + i * 560
            add(lambda d, x=x, i=i: (jrect(d, x, 140, x + 360, 300), tx(d, (x + 180, 220), f"채널 {i + 1}", 68, INK, PEN, "mm")))
            add(lambda d, x=x, i=i: [jrect(d, x + (k % 4) * 90, 360 + (k // 4) * 90, x + (k % 4) * 90 + 70, 360 + (k // 4) * 90 + 70, (120, 120, 120), 4) for k in range(8 * (1))])
            add(lambda d, x=x: tx(d, (x + 180, 600), "손편집 8칸", 54, INK, PEN, "mm"))
        add(lambda d: tx(d, (960, 760), "x2    x3", 120, RED, GAEGU, "mm"))
        add(lambda d: tx(d, (960, 930), "결국 편집 화면 앞에서 멈춘다", 64, INK, PEN, "mm"))
    elif name == "ddalkkak":
        for k, (x, y) in enumerate(((150, 160), (330, 300), (190, 470), (420, 600))):
            add(lambda d, x=x, y=y: (jrect(d, x, y, x + 380, y + 240, (130, 130, 130), 5), jl(d, (x, y + 40), (x + 380, y + 40), (130, 130, 130), 4)))
        add(lambda d: (jl(d, (130, 140), (840, 880), RED, 12), jl(d, (840, 140), (130, 880), RED, 12)))
        add(lambda d: arrow(d, (900, 520), (1060, 520), INK, 8))
        add(lambda d: (jrect(d, 1100, 220, 1790, 760), jl(d, (1100, 280), (1790, 280)), claude_char(d, 1445, 520, 22)))
        add(lambda d: tx(d, (1445, 860), "클로드 하나, 딸깍!", 96, ORANGE, GAEGU, "mm"))
    elif name == "myhand":
        rows = [("강의 더 듣기", "손편집 실력만 늘어남"), ("편집 앱 바꾸기", "누르는 건 내 손"), ("편집자 맡기기", "채널 늘면 비용도 늘어남")]
        for i, (a, b) in enumerate(rows):
            y = 200 + i * 220
            add(lambda d, a=a, b=b, y=y: (tx(d, (160, y), a, 78, INK, PEN), tx(d, (720, y + 10), b, 64, (90, 90, 90), PEN)))
            add(lambda d, y=y: jl(d, (150, y + 48), (1200, y + 48), RED, 5))
        add(lambda d: stamp(d, 1530, 420, "결국 내 손"))
        add(lambda d: tx(d, (960, 920), "저희 방에선... 바보 소리 듣습니다", 76, RED, GAEGU, "mm"))
    elif name == "history":
        add(lambda d: jl(d, (180, 560), (1740, 560), INK, 8))
        for x, t_ in ((300, "숏템메이커"), (760, "숏템 v2"), (1220, "숏클"), (1640, "오늘")):
            add(lambda d, x=x, t_=t_: (jcirc(d, x, 560, 26, ORANGE, 10), tx(d, (x, 470), t_, 70, INK, PEN, "mm")))
        add(lambda d: tx(d, (960, 760), "고친 기록 3,926건+", 110, RED, GAEGU, "mm"))
        add(lambda d: tx(d, (960, 900), "돈과 시간을 갈아 넣었다", 70, INK, PEN, "mm"))
    elif name == "global":
        def globe(d):
            jcirc(d, 620, 520, 300)
            for rx in (120,):
                for k in range(2):
                    pts = [(620 + (rx + R.uniform(-2, 2)) * math.cos(math.radians(a)), 520 + (300 + R.uniform(-2, 2)) * math.sin(math.radians(a))) for a in range(0, 361, 6)]
                    d.line(pts, fill=INK, width=5 if k == 0 else 3)
            jl(d, (320, 520), (920, 520), INK, 5)
            for dy in (-160, 160):
                hw = math.sqrt(300 ** 2 - dy ** 2)
                jl(d, (620 - hw, 520 + dy), (620 + hw, 520 + dy), INK, 4)
        add(globe)
        for k, (t_, y) in enumerate((("한국 채널", 300), ("English channel", 470), ("日本チャンネル", 640))):
            add(lambda d, t_=t_, y=y, k=k: (jrect(d, 1100, y - 60, 1700, y + 60), tx(d, (1400, y), t_, 62, INK, (JA if k == 2 else GAEGU if k else PEN), "mm")))
        add(lambda d: tx(d, (1400, 860), "대본, 목소리 = 클로드", 70, BLUE, PEN, "mm"))
    elif name == "now":
        add(lambda d: person(d, 380, 600, 1.4))
        add(lambda d: arrow(d, (620, 520), (820, 520)))
        add(lambda d: (jrect(d, 880, 260, 1720, 780), jl(d, (880, 320), (1720, 320)), claude_char(d, 1300, 520, 18)))
        add(lambda d: (jrect(d, 940, 660, 1660, 740, BLUE, 5), tx(d, (970, 700), "\"이 스타일로 만들어줘\"", 54, INK, PEN, "lm")))
        add(lambda d: tx(d, (960, 930), "편집 앱 대신 클로드 창부터", 80, ORANGE, GAEGU, "mm"))
    return E


def draw_layer(fn):
    lay = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    fn(ImageDraw.Draw(lay, "RGBA"))
    return lay


def sketch_segment(sid, name, D, out):
    fdir = W / "frames" / sid
    if fdir.exists():
        shutil.rmtree(fdir)
    fdir.mkdir(parents=True)
    base = paper().convert("RGBA")
    els = [draw_layer(f) for f in SK(name)]
    slot = D * 0.8 / max(1, len(els))
    steps = 5
    lines, n = [], 0
    cur = base
    for i, lay in enumerate(els):
        bb = lay.getbbox() or (0, 0, 1, 1)
        for k in range(1, steps + 1):
            x = bb[0] + (bb[2] - bb[0]) * k // steps
            m = Image.new("L", (VW, VH), 0)
            ImageDraw.Draw(m).rectangle((0, 0, x, VH), fill=255)
            part = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
            part.paste(lay, (0, 0), Image.composite(lay.getchannel("A"), Image.new("L", (VW, VH), 0), m))
            fr = Image.alpha_composite(cur, part)
            p = fdir / f"{n:04d}.jpg"; fr.convert("RGB").save(p, quality=90); n += 1
            hold = 0.09 if k < steps else max(0.09, slot - 0.09 * (steps - 1))
            lines.append(f"file '{p.as_posix()}'\nduration {hold:.3f}")
        cur = Image.alpha_composite(cur, lay)
    p = fdir / f"{n:04d}.jpg"; cur.convert("RGB").save(p, quality=90)
    rest = D - sum(float(l.split()[-1]) for l in lines)
    lines.append(f"file '{p.as_posix()}'\nduration {max(0.1, rest):.3f}")
    lines.append(f"file '{p.as_posix()}'")
    lst = fdir / "list.txt"; lst.write_text("\n".join(lines), encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", f"fps={FPS},format=yuv420p",
         "-t", f"{D:.3f}", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-an", str(out)])


# ───────── 실제 영상 장면 ─────────
def label_png(kind):
    im = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    if kind == "styles":
        tx(d, (960, 40), "전부 클로드가 만든 영상, 스타일이 다 다르다", 70, INK, GAEGU, "ma")
    elif kind == "clothes":
        tx(d, (960, 40), "뼈대는 그대로, 옷은 내 것으로", 78, INK, GAEGU, "ma")
        for i, t_ in enumerate(("채널명", "글꼴", "색", "목소리", "음악")):
            y = 260 + i * 130
            d.rounded_rectangle((60, y - 50, 420, y + 50), 14, fill=(255, 255, 255, 235))
            (jl(d, (100, y), (125, y + 25), RED, 7), jl(d, (125, y + 25), (165, y - 25), RED, 7), tx(d, (190, y), t_, 70, RED, PEN, "lm"))
    elif kind == "multi":
        tx(d, (960, 30), "하나의 뼈대로 채널 여러 개   /   형식 6, 스타일 24", 66, INK, GAEGU, "ma")
    elif kind == "cta":
        d.rounded_rectangle((1240, 40, 1880, 190), 24, fill=(255, 255, 255, 240))
        tx(d, (1560, 115), "신청은 고정 댓글에", 80, RED, GAEGU, "mm")
    p = W / f"label_{kind}.png"; im.save(p); return p


def src(key):
    name, crop = SRC[key]
    p = W / "src" / f"{key}.mp4"
    if not p.exists():
        p.parent.mkdir(exist_ok=True); shutil.copy(DESK / name, p)
    return p, crop


def tiles_segment(v, D, out):
    keys = v.get("tiles") or [v["full"]]
    n = len(keys)
    bg = W / "paper.png"
    if not bg.exists():
        paper().save(bg)
    inp = ["-loop", "1", "-t", f"{D:.3f}", "-i", str(bg)]
    filt = []
    if v.get("full"):
        p, _ = src(v["full"])
        inp += ["-ss", str(v.get("ss", 0)), "-t", f"{D:.3f}", "-i", str(p)]
        filt.append(f"[1:v]scale={VW}:{VH},setsar=1[t0]")
        chain = "[0:v][t0]overlay=0:0"
    else:
        th = 900 if n <= 3 else (820 if n == 4 else 700)
        gap = 40
        tw = min(int(th * 9 / 16), (VW - 120 - (n - 1) * gap) // n) // 2 * 2
        th = min(th, int(tw * 16 / 9)) // 2 * 2
        total = n * tw + (n - 1) * gap
        x0 = (VW - total) // 2
        y = 150 if v.get("label") else (VH - th) // 2
        chain = "[0:v]"
        for i, k in enumerate(keys):
            p, crop = src(k)
            ss = (v.get("ss") or [0] * n)[i]
            inp += ["-stream_loop", "-1", "-ss", str(ss), "-i", str(p)]
            filt.append(f"[{i + 1}:v]crop=iw:ih*(1-{crop}):0:ih*{crop},scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},setsar=1[t{i}]")
            chain += f"[t{i}]overlay={x0 + i * (tw + gap)}:{y}:shortest=0"
            chain += f"[c{i}];[c{i}]" if i < n - 1 else ""
    if v.get("label"):
        lp = label_png(v["label"])
        inp += ["-i", str(lp)]
        chain += f"[l0];[l0][{len(keys) + 1}:v]overlay=0:0"
    fc = ";".join(filt) + ";" + chain + f",fps={FPS},format=yuv420p[v]"
    run(["ffmpeg", "-y", "-v", "error", *inp, "-filter_complex", fc, "-map", "[v]", "-t", f"{D:.3f}",
         "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-an", str(out)])


def seg(ids):
    (W / "seg").mkdir(exist_ok=True)
    for s in SCENES:
        if ids and s["id"] not in ids:
            continue
        a = W / "voice" / f"{s['id']}.mp3"
        D = dur(a) + 0.6
        out = W / "seg" / f"{s['id']}.mp4"
        if out.exists() and not ids:
            continue
        v = s["vis"]
        if "sketch" in v:
            sketch_segment(s["id"], v["sketch"], D, out)
        else:
            tiles_segment(v, D, out)
        run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-i", str(a), "-af", "apad=pad_dur=0.6", "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{D:.3f}", str(out.with_suffix(".av.mp4"))])
        print("장면", s["id"], round(D, 2), "초", flush=True)


# ───────── 합본 + 자막 ─────────
def ass_time(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def final():
    t, ev = 0.0, []
    lst = W / "concat.txt"
    lst.write_text("\n".join(f"file '{(W / 'seg' / (s['id'] + '.av.mp4')).as_posix()}'" for s in SCENES), encoding="utf-8")
    for s in SCENES:
        D = dur(W / "seg" / f"{s['id']}.av.mp4")
        A = dur(W / "voice" / f"{s['id']}.mp3")
        sents = [x.strip() for x in re.split(r"(?<=[.?!])\s+", s["text"]) if x.strip()]
        tot = sum(len(x) for x in sents)
        c = t + 0.1
        for x in sents:
            d_ = A * len(x) / tot
            ev.append((c, c + d_ - 0.05, x)); c += d_
        t += D
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VW}
PlayResY: {VH}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: S,Pretendard Black,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,5,0,2,120,120,46,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = "\n".join(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},S,,0,0,0,,{x}" for a, b, x in ev)
    (W / "subs.ass").write_text(head + body + "\n", encoding="utf-8")
    fontsdir = (W / "fonts").as_posix().replace(":", "\\:")
    out = W / "yt4_draft_v1.mp4"
    os.chdir(W)
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "concat.txt",
         "-vf", f"subtitles=subs.ass:fontsdir='{fontsdir}'", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
         "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", str(out)])
    print("완성", out, round(dur(out), 2), "초")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    ids = sys.argv[2:]
    if what in ("voice", "all"):
        voice(ids)
    if what in ("seg", "all"):
        seg(ids)
    if what in ("final", "all"):
        final()
