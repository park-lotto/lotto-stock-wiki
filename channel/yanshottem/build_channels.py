# -*- coding: utf-8 -*-
"""소재채널.json 만들기 (한 번 돌리면 된다). 근거 = itemhome/동종채널 자료 + 칼카피_조사 §4 + 강한채널_결과.
연예인템 비율 = b2sorted 의 자동점수(앞쪽 열) 또는 문서 표의 N/40. 조회 중앙 = chlists2/chl3/chl4 의 최근 40편 값에서 직접 다시 잰다."""
import json, re, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy import celeb_topics as ct

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "channel/itemhome/동종채널"
OUT = Path(__file__).with_name("소재채널.json")

lists = {}
for f in ("chlists2", "강한채널_chl3", "강한채널_chl4"):
    for k, v in json.load(open(D / f"{f}.json", encoding="utf-8")).items():
        lists.setdefault(k, v)

# 문서 §4 표 + 강한채널 표에서 (이름, id, 구독, 비율, 표기)
DOC = {
 "UCKFmJFCmSRgTpPHp9OR2ylw": ("안나픽", 41900, 0.98, "화면"), "UC9c_LyrFLDRsg3hQuIUoL2A": ("셀럽의 인생템", 22100, 0.95, "없음"),
 "UCNVXvKAeo3mM3toKsg-Mqog": ("만템", 5840, 0.78, "화면"), "UCh2XU0o0Yw5TUY2R5CsmGrA": ("셀럽도감", 5990, 0.58, "화면"),
 "UClcybvgYb7X7dRKtg7LRiTQ": ("쇼핑이멀전시", 32900, 0.78, "없음"), "UC9z5bQhQz6wIoUF-gXjbQcQ": ("셀럽장바구니", 2730, 0.68, "화면"),
 "UCMvUJmiUAPWfYfRVn3yX49g": ("꿀템원츄", 16400, 0.70, "없음"), "UClHe-IBvI7BF8PIbiTN7R3g": ("줍줍템즈", 12800, 0.50, "없음"),
 "UCB-6j0fUzSn2aYgtYobsK0A": ("셀바스", 1700, 0.83, "화면"), "UCUkSuomkN5lvSvK9I32lqvA": ("셀템모아", 2110, 0.83, "없음"),
 "UCKZYBi2X3WQ3XCW2Eah-MsA": ("월간추천템", 2290, 0.80, "없음"), "UCOyqDQ0TlMcNCXtO-F0O2cQ": ("햇님의 취향가게", 3040, 0.60, "없음"),
 "UC1d1uKVAcNqjiFL6GSW0EsQ": ("줍줍걸", 1510, 0.93, "없음"),
 "UCLonE7p-TmUpzbcLpAMyS5g": ("트렌또", 1690, 0.48, "화면"), "UCRrWxSEJzitWDTEF_aADh9A": ("쎌렉템", 16100, 0.79, "화면"),
 "UCcLYXGJ5fJ7Sgm3A60ubTOg": ("비밀꿀템탐험대", 12600, 0.80, "화면"), "UCqFTdAP2rY2Fn8iF8P2biog": ("맛있는쀼끼", 11200, 0.75, "미확인"),
 "UC3Eu-_fIreXjCQFXNw2OwlQ": ("셀럽픽템", 65700, 0.60, "미확인"), "UCEA4A1PEdCrLSe0-Bfy1pdw": ("뷰티하루", 3730, 0.65, "미확인"),
 "UCSJH3yRBxjVz4qh4ufcyCbg": ("굿레터", 16100, 0.65, "미확인"), "UCkIZOE5YJpBtxzp9VyNCLmQ": ("원픽꿀템", 8520, 0.83, "미확인"),
 "UCrT1-sFkSwPVcJsi2V7NGww": ("꿀쇼핑", 2260, 0.88, "미확인"),
}
STRONG = {"UCKFmJFCmSRgTpPHp9OR2ylw", "UCLonE7p-TmUpzbcLpAMyS5g", "UCRrWxSEJzitWDTEF_aADh9A", "UC9c_LyrFLDRsg3hQuIUoL2A",
          "UCcLYXGJ5fJ7Sgm3A60ubTOg", "UCNVXvKAeo3mM3toKsg-Mqog", "UCqFTdAP2rY2Fn8iF8P2biog", "UC3Eu-_fIreXjCQFXNw2OwlQ",
          "UCEA4A1PEdCrLSe0-Bfy1pdw", "UCh2XU0o0Yw5TUY2R5CsmGrA", "UCSJH3yRBxjVz4qh4ufcyCbg", "UCkIZOE5YJpBtxzp9VyNCLmQ", "UCrT1-sFkSwPVcJsi2V7NGww"}
EXCLUDE = {"UC7RASIHu7B9QtjD81yWOYMQ",  # 아이템홈 = 형식 견본(소재원 아님)
           "UC_qaaZIOOxLo61RtJOzDGQg", "UCPCO6WpeSqp2mcManUNT70g"}  # 빙글빙글하이(지디 근황)·알면 뭐하니(BTS 예능 짤) = 제품 없는 팬 클립
b2 = {}
for line in open(D / "b2sorted.txt", encoding="utf-8"):
    p = line.split(None, 4)
    if len(p) >= 4 and p[1].startswith("UC"):
        b2[p[1]] = float(p[2])

ids = list(dict.fromkeys(list(DOC) + list(b2)))
rows = []
for cid in ids:
    if cid in EXCLUDE:
        continue
    vs = [int(x[1]) for x in lists.get(cid, []) if str(x[1]).isdigit()]
    med = int(statistics.median(vs)) if vs else 0
    name, subs, ratio, src = DOC.get(cid, (None, None, b2.get(cid), "미확인"))
    if cid in DOC and cid in b2:
        ratio = DOC[cid][2]
    grade = "A" if cid in STRONG else ("B" if med >= 10000 else "C")
    rows.append({"id": cid, "이름": name, "구독": subs, "연예인템비율": ratio, "조회중앙": med, "출처표기": src,
                 "강함": grade, "근거": "문서표" if cid in DOC else "b2sorted 자동점수(제목 40편, 미검수)"})
# 이름 채우기(RSS)
for r in rows:
    if not r["이름"]:
        try:
            r["이름"] = ct.parse_feed(ct.fetch_feed(r["id"]), now=None)["name"]
        except Exception as e:
            r["이름"] = "?"
        time.sleep(0.5)
rows.sort(key=lambda r: -r["조회중앙"])
json.dump({"만든날": time.strftime("%Y-%m-%d"), "채널": rows}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(rows), "채널 →", OUT)
