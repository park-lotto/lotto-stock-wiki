"""글자 인식(OCR)으로 채널 이름을 찾아 그 자리만 살짝 흐린다 — 움직이는 화면(리포트·검색 화면)용.

쓰기: py ocr_blur.py <public 폴더> <파일(public 기준)> <ocr.json | -> [fps]
  ocr.json = ocr_vid.py 결과 [t, 글, 점수, [x0,y0,x1,y1]] (없으면 '-' : 그림 파일은 여기서 바로 읽는다)
채널 이름 고르는 규칙(NAME):
  ① 우리 결과물 채널 띠·워터마크·유튜브 채널 글자(오인식 변형 포함)
  ② 유튜브 검색 결과: '조회수/…전' 줄 바로 아래 같은 칸 첫 줄 = 채널 이름 줄(아바타까지 덮게 왼쪽 50px)
출처 줄('출처')은 건드리지 않는다(사장님 10-30 "출처는 지우지 말고").
결과 상자는 blur_names.py 의 boxes 형식으로 넘겨 원본(_pre_blur)에서 다시 만든다.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = re.compile(r"(리포|리폭|리풋|리끗|리폰|리봇|리폿|홈샷|홀샷|lily|lyly|liby|lly|샷템|샷팀|상템|shortem|에이아이온|AI:ON|Al:ON|^@)", re.I)
VIEWS = re.compile(r"[·•]\s*\d+\s*(주|일|개월|년|시간|분)\s*전")  # 목록형 '3.6만 • 2개월 전'(쇼츠 칸의 '조회수 n회'는 아님)


def pick(rows):
    """한 프레임의 [글, 상자] → 흐릴 상자들."""
    out = []
    for txt, b in rows:
        if "출처" in txt or "출치" in txt:
            continue
        if NAME.search(txt.replace(" ", "")):
            out.append([b[0] - 6, b[1] - 4, b[2] + 6, b[3] + 4])
    for txt, b in rows:  # 유튜브 목록: 조회수 줄 아래 채널 줄
        if not VIEWS.search(txt) or "조회수" in txt or len(txt) > 25:
            continue
        h = b[3] - b[1]
        cand = [(c, d) for c, d in rows if d[1] > b[3] and d[1] - b[3] < 4 * h + 30 and abs(d[0] - b[0]) < 90 and "출처" not in c]
        if cand:
            c, d = min(cand, key=lambda q: q[1][1])
            if not VIEWS.search(c):
                out.append([d[0] - 50, d[1] - 6, d[2] + 8, d[3] + 6])
    return out


def merge(timed, step):
    """같은 자리 상자가 이어지면 한 구간으로 묶는다."""
    segs = []
    for t, b in sorted(timed, key=lambda q: q[0]):
        for s in segs:
            if abs(s[2] - b[0]) < 14 and abs(s[3] - b[1]) < 14 and abs(s[4] - b[2]) < 14 and abs(s[5] - b[3]) < 14 and t - s[1] <= step * 1.6:
                s[1] = t; s[2] = min(s[2], b[0]); s[3] = min(s[3], b[1]); s[4] = max(s[4], b[2]); s[5] = max(s[5], b[3]); break
        else:
            segs.append([t, t] + list(b))
    return [[round(max(0, s[0] - step * 0.6), 2), round(s[1] + step * 0.6, 2)] + s[2:] for s in segs]


def main():
    pub, rel, oj = sys.argv[1], sys.argv[2], sys.argv[3]
    fps = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    if oj == "-":
        sys.path.insert(0, os.environ["OCR_DIR"]); import ocr_ko, numpy as np
        from PIL import Image
        src = os.path.join(pub, "_pre_blur", rel) if os.path.exists(os.path.join(pub, "_pre_blur", rel)) else os.path.join(pub, rel)
        im = np.asarray(Image.open(src).convert("RGB"))[:, :, ::-1].copy()
        r, _ = ocr_ko.make()(im)
        data = [[0, t, float(s), [int(min(q[0] for q in b)), int(min(q[1] for q in b)), int(max(q[0] for q in b)), int(max(q[1] for q in b))]] for b, t, s in (r or [])]
    else:
        data = json.load(open(oj, encoding="utf-8"))
    by = {}
    for t, txt, s, b in data:
        if s >= 0.45: by.setdefault(t, []).append((txt, b))
    timed = [(t, b) for t, rows in by.items() for b in pick(rows)]
    img = rel.lower().endswith((".jpg", ".png"))
    if img:
        boxes = [[None, None] + [max(0, v) for v in b] for t, b in timed]
    else:
        boxes = [[s[0], s[1]] + [max(0, v) for v in s[2:]] for s in merge(timed, 1 / fps)]
    cfg = os.path.join(os.path.dirname(oj) if oj != "-" else os.environ["OCR_DIR"], "ocrblur_" + rel.replace("/", "_") + ".json")
    json.dump({"boxes": {rel: boxes}}, open(cfg, "w", encoding="utf-8"))
    print(rel, "흐릴 곳", len(boxes))
    subprocess.run([sys.executable, os.path.join(HERE, "blur_names.py"), pub, cfg], check=True)


main()
