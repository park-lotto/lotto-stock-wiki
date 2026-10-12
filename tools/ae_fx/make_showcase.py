"""에펙 견본 영상을 카테고리별로 한 화면에 보여주는 페이지를 만든다 (관제 112).

D:\\ae_fx_work 의 <번호>.mp4 를 D:\\숏템\\30_재료\\에펙효과견본\\ 으로 복사하고 index.html 을 쓴다.
없는 영상은 목록에서 빼고 끝에 알린다(빈 칸을 만들지 않는다).
사용: py tools/ae_fx/make_showcase.py
"""
import html
import shutil
import sys
from pathlib import Path

WORK = Path(r"D:\ae_fx_work")
DEST = Path(r"D:\숏템\30_재료\에펙효과견본")

# 적용 방식: 얹기 = 에펙에서 투명 영상으로 뽑아 그대로 얹는다 / 글자 = 고객 글자가 바뀌므로 편집기 코드로 옮긴다
#           영상 = 고객 영상 자체를 바꾸므로 서버 영상 처리로 옮긴다
CATS = [
    ("A", "자막 등장", "글자가 화면에 나타나는 방식", [
        ("A1", "글자 블러 올라오기", "글자"), ("A2", "글자 팝 튕김", "글자"), ("A3", "자간 모이며 등장", "글자"),
        ("A4", "선 뒤에서 올라오기", "글자"), ("A5", "쾅 박히기", "글자"), ("A6", "한글 타이핑", "글자"),
        ("A7", "젤리 꿀렁", "글자")]),
    ("B", "단어 강조", "말하는 단어·핵심 단어를 짚는 방식", [
        ("B1", "형광펜 긋기", "글자"), ("B2", "단어 번쩍 글로우", "글자"), ("B3", "밑줄 그려지기", "글자"),
        ("B4", "강조 상자 덮기", "글자"), ("B5", "펜 동그라미·별표", "글자"), ("B6", "덜덜 떨림", "글자")]),
    ("G", "글자 꾸밈", "글자 자체의 재질·움직임", [
        ("G1", "네온사인", "글자"), ("G2", "물결 무지개", "글자"), ("G3", "글리치 글자", "글자"),
        ("G4", "가격 숫자 롤링", "글자"), ("G5", "입체 글자 튀어나오기", "글자")]),
    ("C", "화면 전환", "컷과 컷 사이", [
        ("C1", "휩 팬 (휙 넘김)", "영상"), ("C2", "줌 블러 전환", "영상"), ("C3", "글리치 전환", "영상")]),
    ("D", "빛·질감", "화면 전체의 분위기", [
        ("D1", "빛 번짐 (라이트 릭)", "얹기"), ("D2", "영화 색감 (대비·그레인·비네트)", "영상"),
        ("D3", "블룸 (뽀얀 빛)", "영상")]),
    ("E", "장식·도형", "화면 위에 얹는 그림", [
        ("E1", "손그림 동그라미", "얹기"), ("E2", "화살표 그려지기", "얹기"), ("E3", "터지는 선·반짝이", "얹기")]),
    ("F", "카메라 움직임", "영상 칸의 확대·흔들림", [
        ("F1", "펀치 줌 (뚝 끊는 확대)", "영상"), ("F2", "쾅 흔들림", "영상"), ("F3", "천천히 밀고 들어가기", "영상")]),
]
HOW = {"얹기": "에펙 결과물 그대로 얹기", "글자": "편집기 코드로 옮김", "영상": "서버 영상 처리로 옮김"}

PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>에펙 고급효과 견본</title>
<style>
:root{{--bg:#101114;--card:#1a1c21;--line:#2b2e36;--ink:#f2f3f5;--sub:#9aa0ab;--a:#ffd84a;--b:#7ad1ff;--c:#ff8fb1}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 "Pretendard","Malgun Gothic",sans-serif}}
header{{padding:28px 24px 8px;max-width:1500px;margin:0 auto}}h1{{margin:0 0 6px;font-size:26px}}
header p{{margin:0;color:var(--sub)}}.legend{{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px;font-size:14px;color:var(--sub)}}
.tag{{display:inline-block;padding:2px 9px;border-radius:99px;font-size:12px;font-weight:700;color:#111}}
.t-얹기{{background:var(--a)}}.t-글자{{background:var(--b)}}.t-영상{{background:var(--c)}}
section{{max-width:1500px;margin:0 auto;padding:22px 24px 6px}}h2{{margin:0;font-size:20px}}h2 small{{color:var(--sub);font-weight:400;font-size:14px;margin-left:8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;margin-top:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
.card video{{display:block;width:100%;aspect-ratio:9/16;background:#000;cursor:pointer}}
.card div{{padding:9px 11px 11px}}.card b{{display:block;font-size:14px}}.card span.id{{color:var(--sub);font-size:12px;margin-right:6px}}
footer{{max-width:1500px;margin:0 auto;padding:20px 24px 40px;color:var(--sub);font-size:13px}}
</style></head><body>
<header><h1>에펙 고급효과 견본 — {count}개</h1>
<p>전부 애프터이펙트에서 스크립트로 만들어 뽑은 영상입니다. 영상을 누르면 크게 봅니다.</p>
<div class="legend">{legend}</div></header>
{sections}
<footer>배경 영상은 내부 시험용 재료입니다. 만든 날 {date} · 관제 112</footer>
<script>
document.querySelectorAll('video').forEach(v=>v.addEventListener('click',()=>{{if(document.fullscreenElement)document.exitFullscreen();else v.requestFullscreen()}}));
</script></body></html>"""


def main():
    import datetime
    DEST.mkdir(parents=True, exist_ok=True)
    sections, missing, count = [], [], 0
    for key, name, desc, items in CATS:
        cards = []
        for vid, title, how in items:
            src = WORK / f"{vid}.mp4"
            if not src.exists() or src.stat().st_size < 10000:
                missing.append(vid)
                continue
            shutil.copy2(src, DEST / f"{vid}.mp4")
            count += 1
            cards.append(
                f'<div class="card"><video src="{vid}.mp4" autoplay loop muted playsinline></video>'
                f'<div><b><span class="id">{vid}</span>{html.escape(title)}</b>'
                f'<span class="tag t-{how}">{html.escape(HOW[how])}</span></div></div>')
        if cards:
            sections.append(f'<section><h2>{key}. {html.escape(name)}<small>{html.escape(desc)} · {len(cards)}개</small></h2>'
                            f'<div class="grid">{"".join(cards)}</div></section>')
    legend = "".join(f'<span><span class="tag t-{k}">{html.escape(v)}</span></span>' for k, v in HOW.items())
    (DEST / "index.html").write_text(
        PAGE.format(count=count, legend=legend, sections="\n".join(sections), date=datetime.date.today().isoformat()),
        encoding="utf-8")
    print(f"영상 {count}개 → {DEST / 'index.html'}")
    if missing:
        print("없는 영상: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
