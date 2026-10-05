# -*- coding: utf-8 -*-
"""'채널별 터진 영상' 탭 라이브 검사(관제 137) — 관리자로 랭킹 화면을 열어 그 탭을 **눌러 보고** 센다.

    py tools/channel_hits/check_live.py [스크린샷.png]      # 통과 rc=0

보는 것(고객이 받는 화면·응답 그대로):
  ① 유튜브에서 '역대 히트작' 자리의 이름이 '채널별 터진 영상'인가
  ② 누르면 카드가 나오고 카드마다 '평소의 N배' 뱃지가 달리는가
  ③ 서버 응답: 카테고리가 썰쇼핑(제품정체형)·홈템 둘뿐인가 / 채널당 3편 이하인가 / 전부 평소의 5배·1만 이상인가
  ④ 유형 버튼이 전체·썰쇼핑·홈템만 남고, 썰쇼핑↔홈템을 누르면 카드가 갈리는가
  ⑤ 유형 버튼 순서(다른 탭): 전체 · 썰쇼핑 · 홈템 · 장비 …
"""
import json
import sys

sys.path.insert(0, ".")
from tools import live_admin as la  # noqa: E402

_INFO = """() => ({
  arch: (document.querySelector('#spanTabs .tab[data-span="-1"]')||{}).textContent || '',
  ctypes: [...document.querySelectorAll('#ctypes .ctype')].map(x => x.textContent.trim()),
  cards: document.querySelectorAll('#cards .card').length,
  hitBadges: [...document.querySelectorAll('#cards .ibadge .lbl')].filter(x => x.textContent.includes('평소의')).length,
  thumbs: [...document.querySelectorAll('#cards .card img')].slice(0, 12).filter(i => i.naturalWidth > 0).length,
  status: (document.getElementById('status')||{}).textContent || ''})"""
_API = """async () => { const it = ((await (await fetch('/api/reference?platform=youtube&archive=1')).json()).items)||[];
  const per = {}; it.forEach(i => per[i.username] = (per[i.username]||0)+1);
  const cats = {}; it.forEach(i => cats[i.category] = (cats[i.category]||0)+1);
  return {n: it.length, channels: Object.keys(per).length, maxPer: Math.max(0, ...Object.values(per)), cats,
          bad: it.filter(i => !(i.hit_ratio >= 5 && i.views >= 10000)).length}; }"""


def main(shot=None):
    fails = []
    with la.admin_page("") as pg:
        if pg.evaluate("PLATFORM") != "youtube":
            pg.evaluate("switchPlatform('youtube', document.querySelector('#platformTabs .ctype'))")
            pg.wait_for_timeout(1500)
        first = pg.evaluate(_INFO)
        api = pg.evaluate(_API)
        pg.click('#spanTabs .tab[data-span="-1"]')
        pg.wait_for_timeout(4000)
        sul = pg.evaluate(_INFO)
        if shot:
            pg.screenshot(path=shot)
        pg.evaluate("setCtype('홈템')")
        pg.wait_for_timeout(1500)
        home = pg.evaluate(_INFO)
        errs = list(pg.errors)
    print("① 탭 이름:", first["arch"])
    print("⑤ 유형 버튼(24시간 탭):", " · ".join(first["ctypes"]))
    print("③ 서버 응답:", json.dumps(api, ensure_ascii=False))
    print("② 누른 뒤(썰쇼핑): 카드 %d · 평소의 N배 뱃지 %d · 썸네일 로드 %d/12 · %s" % (sul["cards"], sul["hitBadges"], sul["thumbs"], sul["status"]))
    print("④ 유형 버튼(이 탭):", " · ".join(sul["ctypes"]), "| 홈템 누름: 카드 %d" % home["cards"])
    if "채널별 터진 영상" not in first["arch"]:
        fails.append("탭 이름이 아니다")
    if not api["n"] or api["maxPer"] > 3 or api["bad"] or set(api["cats"]) - {"제품정체형", "홈템"}:
        fails.append("서버 응답이 기준 밖")
    if not sul["cards"] or sul["hitBadges"] != sul["cards"]:
        fails.append("카드·뱃지가 안 맞는다")
    if not home["cards"] or len(sul["ctypes"]) != 3:
        fails.append("썰쇼핑·홈템 구분이 안 된다")
    order = [next((i for i, t in enumerate(first["ctypes"]) if k in t), -1) for k in ("전체", "썰쇼핑", "홈", "장비")]
    if -1 in order or order != sorted(order):
        fails.append("유형 버튼 순서가 다르다")
    if errs:
        fails.append("페이지 오류 %s" % errs[:2])
    print("결과:", "통과" if not fails else "실패 — " + " / ".join(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
