# -*- coding: utf-8 -*-
"""현장썰 하이브리드 — 원본 영상 속 제품과 '같은 제품'을 찾는다(사장님 10-18 "최선은 같은 제품을 찾는 거야").

구글 렌즈(PC, 무료·로그인 불필요 — SerpApi 는 유료라 안 씀)에 원본 장면 여러 장을 차례로 올려
  ① 렌즈가 보여 주는 제품 이름·쇼핑 결과(어느 가게든)를 모으고
  ② 여러 장에서 겹쳐 나온 것(hits)을 위로 — 한 장만 보면 배경 소품을 잡는다
  ③ 그 안의 coupang.com 상품을 따로 뽑는다.
쿠팡 상품이 없으면 ①의 정식 이름(브랜드·모델)으로 쿠팡검색.py 를 다시 돌린다.
★사진은 제품 **전체 모양**이 보이게 자른다(사장님 10-18 "너무 작게 부분을 잡는 거 아닌가, 여러 개 전체 모양 나오게").
쿠팡 모바일 렌즈는 PC 브라우저에서 m.coupang.com 이 Access Denied(10-18 실측)라 이 길로 간다.

실행: py channel/hottemreport/현장썰하이브리드/렌즈쿠팡.py <이름> <사진1> [<사진2> …]
결과: 같은 폴더 렌즈_<이름>.json (+ 마지막 화면 렌즈_<이름>.png)
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from tools.calcopy.lens import lens_page, lens_rows  # noqa: E402  — 렌즈 주인 = tools/calcopy/lens.py(원본찾기와 같이 쓴다, 10-21)


def main(name: str, imgs: list[str]):
    per = {}
    with lens_page() as pg:
        for img in imgs:
            img = str(Path(img).resolve())
            try:
                per[img] = lens_rows(pg, img)
            except Exception as e:  # noqa: BLE001 — 한 장 실패가 나머지를 막지 않게(실패는 결과에 남긴다)
                per[img] = []
                print("실패", Path(img).name, type(e).__name__, str(e)[:80])
            print(f"  {Path(img).name}: {len(per[img])}개")
        pg.screenshot(path=str(HERE / f"렌즈_{name}.png"))
    agg = {}
    for img, rows in per.items():
        for r in rows:
            k = re.sub(r"[?#].*$", "", r["href"]) if "coupang.com/vp/products" in r["href"] else r["href"]
            a = agg.setdefault(k, {**r, "href": k, "hits": 0})
            a["hits"] += 1
    rows = sorted(agg.values(), key=lambda r: -r["hits"])
    cp = [r for r in rows if "coupang.com/vp/products" in r["href"]]
    (HERE / f"렌즈_{name}.json").write_text(json.dumps({"imgs": imgs, "coupang": cp, "all": rows, "per": per}, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(f"사진 {len(imgs)}장 · 결과 {len(rows)}개 · 쿠팡 상품 {len(cp)}개")
    for r in cp[:10]:
        print(f"  [쿠팡 {r['hits']}장] {r['text'][:70]}  {r['href']}")
    for r in rows[:20]:
        print(f"  {r['hits']}장 {r['shop'][:24].ljust(24)} {r['text'][:70]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
