"""시안 v3 HTML 만들기 — work/v3_data.json + template.html(머리) → out/인기상품랭킹_시안.html.
work 폴더에서 실행: cd tools/hot_products/work && py -I ../build_html.py"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "out", "인기상품랭킹_시안.html")

t = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
head = t[:t.index("<script>")]
head = head.replace("<title>인기상품 랭킹 — 시안</title>", "<title>인기상품 랭킹 — 시안 v3</title>")
head = head.replace(".note{", """.score{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--sub)}
.score b{font-size:18px;color:var(--mint)}
.sbar{flex:1;height:6px;background:#141e30;border-radius:4px;overflow:hidden}
.sbar i{display:block;height:100%;background:linear-gradient(90deg,#8c6ef0,#3ee0bf)}
.dem{font-size:11.5px;color:var(--sub);line-height:1.5}
.dem b{color:var(--txt)}
.site-tag{position:absolute;top:8px;right:8px;font-size:11px;font-weight:800;padding:3px 7px;border-radius:7px;background:rgba(7,11,20,.85);border:1px solid var(--line)}
.wow{color:var(--gold);letter-spacing:-1px}
.note{""")
head = head.replace("""    · [숏템파워로 찾기]를 누르면 숏템메이커에서 그 제품명으로 검색됩니다(로그인 필요). 검색어는 제품명에서 수량·용량 등을 뺀 앞부분입니다.<br>
    · 네이버·쿠팡은 서버가 모으고, 아마존·테무·알리·1688은 사장님 PC가 모아 서버로 보냅니다.<br>
    · 알리는 제휴 API 승인 뒤 정렬 종류가 늘어납니다. 1688 신상품, 아마존 급상승은 아직 수집되지 않습니다.""",
"""    · <b>종합 점수</b> = 판매 속도 35% (같은 사이트 안 백분위) + 검색 수요 25% (네이버 월 검색수, 상승 추세 가산) + 신박함 25% (AI 0~3점) + 쇼츠 기회 15% (검색은 많은데 유튜브 영상 조회가 적을수록 높음).<br>
    · 판매 속도: 테무 = 1시간 동안 늘어난 판매수 / 1688 = 월 판매량 / 아마존 = 리뷰 증가 × 30 / 네이버 = 구매순 순위. 네이버·1688은 하루 단위 갱신이라 매일 쌓이면 '순위 상승·전월 대비'로 바뀝니다.<br>
    · 광고 상품, 식품·소모품·의류 등 쇼츠로 만들 수 없는 상품은 기본으로 숨기고 '🚫 제외'에서 이유와 함께 볼 수 있습니다.<br>
    · 이번 시안 수집: 2026-10-19 20:15·21:13 (사장님 PC). 쿠팡·알리는 이번 수집에 빠졌습니다.""")
js = open(os.path.join(HERE, "view.js"), encoding="utf-8").read()
d = open("v3_data.json", encoding="utf-8").read().replace("</", "<\\/")
out = (head + "<script>\n" + js.replace("__DATA__", d) + "\n</script>\n</body>\n</html>\n").replace("__DATE__", "2026-10-19")
open(OUT, "w", encoding="utf-8").write(out)
print("저장", os.path.abspath(OUT), len(out))
