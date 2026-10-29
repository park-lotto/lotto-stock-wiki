"""데일리 1편 구성안 HTML 생성(장면마다 바탕화면 숏클_장면샘플 영상을 그 자리에서 재생)."""
import os, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))


def v(name):
    return "file:///C:/Users/TheRose/Desktop/" + urllib.parse.quote("숏클_장면샘플/" + name)


from plan_rows_v3 import rows, tests  # 라이브 반응 반영판
shorts = [
    ("①", "클로드에 이 한 줄 넣었더니", "해외+화장품", "번호·칩 소개"),
    ("②", "연예인 후기 쇼츠, 한 줄이면 됩니다", "연예인+후기", "격자 쏟아짐"),
    ("③", "이 썰 쇼츠, 사람이 안 썼습니다", "썰비하인드", "번호·칩 소개"),
    ("④", "자는 동안 쇼츠 3편이 왔습니다", "해외핫영상+나레원음", "폰 알림 도착"),
]
presets = [
    ("해외+화장품", "해외원본 · 나레+원음", 10), ("연예인+후기", "연예인쇼핑형 · 후기형", 40),
    ("썰비하인드", "쇼핑형 · 썰쇼핑형", 30), ("해외핫영상+나레원음", "해외원본 · 나레+원음", 30),
    ("해외핫영상+자막·배경음", "해외원본 · 자막+배경음", 6), ("연예인 레시피", "연예인레시피형", 7),
    ("원곡 인물", "인물형", 10), ("여행 숙소", "여행쇼츠형", 2),
]


def vid(n):
    if not n:
        return '<div class="nov">새로 만듦<br>(베이지 카드)</div>'
    return f'<video src="{v(n)}" autoplay muted loop playsinline controls preload="auto"></video>'


trs = "".join(
    f'<tr><td class="st">{st}<div class="t">{t}</div></td><td>{vid(f)}<div class="sc">{sc}</div></td>'
    f'<td class="nar">{nar}</td><td class="dev">{dev}</td></tr>'
    for st, t, sc, f, nar, dev in rows)
tt = "".join(
    f'<div class="test"><div class="n">{a}</div><div class="cmd">› {b}</div><div class="pt">{c}</div>{vid(e)}'
    f'<div class="meta"><b>{d}</b> · {f}</div></div>' for a, b, c, d, e, f in tests)
sh = "".join(f'<tr><td>{a}</td><td class="hook">“{b}”</td><td>{c}</td><td>{d}</td></tr>' for a, b, c, d in shorts)
pr = "".join(f'<tr><td><b>{a}</b></td><td>{b}</td><td class="num">{c}편</td></tr>' for a, b, c in presets)

CSS = """
:root{--bg:#EFE9DF;--card:#F8F4ED;--ink:#1C1B19;--sub:#6B6660;--or:#E07A2B;--teal:#12957F;--line:#DDD4C7}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Pretendard,"Malgun Gothic",sans-serif;line-height:1.55;word-break:keep-all}
.wrap{max-width:1180px;margin:0 auto;padding:40px 20px 80px}
h1{font-family:"Gowun Batang",Batang,serif;font-size:42px;margin:0 0 6px;letter-spacing:-.02em}
h2{font-family:"Gowun Batang",Batang,serif;font-size:28px;margin:48px 0 14px}
.lead{color:var(--sub);font-size:17px}.pill{display:inline-block;background:var(--or);color:#fff;border-radius:99px;padding:2px 12px;font-weight:700;font-size:14px}
.sum{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin-top:22px}
.box{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px}.box b{color:var(--or)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line)}
td,th{padding:14px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left;font-size:16px}
th{background:#E6DED1;font-size:14px;color:var(--sub)}
td.st{font-weight:800;width:130px}.t{font-weight:400;color:var(--sub);font-size:13px}td.nar{font-size:17px}
td.dev{color:var(--teal);font-weight:700;width:150px;font-size:14px}
video{width:240px;max-width:100%;max-height:300px;border-radius:10px;background:#000;display:block}
.nov{width:240px;height:135px;border:2px dashed var(--line);border-radius:10px;display:flex;align-items:center;justify-content:center;text-align:center;color:var(--sub);font-size:14px}
.sc{font-size:13px;color:var(--sub);margin-top:6px}
.tests{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.test{background:#1F1E1C;color:#F3ECE0;border-radius:16px;padding:16px}
.test .n{font-family:serif;font-size:34px;color:var(--or)}.cmd{font-family:Consolas,monospace;font-size:15px;margin:4px 0 8px}
.pt{font-weight:800;font-size:17px;margin-bottom:10px}.test video{width:100%;max-height:360px;object-fit:contain}
.meta{font-size:13px;color:#B8B1A6;margin-top:8px}.meta b{color:#5FD3BC}
.hook{font-family:"Gowun Batang",serif;font-size:19px}.num{text-align:right;font-weight:800;color:var(--or)}
ol li{margin:6px 0;font-size:17px}
.bar{display:flex;height:24px;border-radius:99px;overflow:hidden;margin:22px 0 4px}
.bar div{display:flex;align-items:center;justify-content:center;font-size:12px;color:#fff;font-weight:700;white-space:nowrap}
@media (max-width:700px){td.dev,th.dev{display:none}h1{font-size:30px}}
"""

html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>숏클 데일리 1편 구성안</title><style>{CSS}</style></head><body><div class="wrap">
<span class="pill">사장님 승인 대기</span>
<h1>숏클 데일리 1편 구성안</h1>
<div class="lead">롱폼 약 18분 40초 + 쇼츠 4편, 같은 날 함께 기획 · 2026-10-29 · 샘플 영상은 바탕화면 숏클_장면샘플 폴더(그 자리에서 재생)</div>
<div class="sum">
<div class="box"><b>관통 키워드 = "진짜 딸깍"</b> (+ "한 줄")<br>오프닝 "진짜 클로드의 딸깍을 보여 드립니다" → 한계 "한 줄로 부탁하면 안 된다" → 본론 "프리셋+한 줄" ×8 → 끝 "오늘 한 줄 넣어 보세요"</div>
<div class="box"><b>이야기 구조</b><br>주인공 = 시청자(40·50·60대) · 적 = 시간 · 실패한 시도 = AI에게 말로 부탁 · 조력자 = 숏클 엔진 · <b>시험 8번</b> = 프리셋 8개 · 결말 = 자는 동안 쌓인 결과물</div>
<div class="box"><b>핵심(사장님)</b><br>라이브에서 사람들이 좋아한 것 = 진솔함 + 기존 클로드형이 못 하는 것들(근거: 라이브_반응분석.md — 채팅 157개 × 발언 대조). 진짜 Claude 가 만드는 과정 + 결과물 등장. 결과 등장 방식은 매번 다르게. 목소리 = 필재 1.25배속.</div>
</div>
<div class="bar"><div style="flex:40;background:#6B6660">훅</div><div style="flex:325;background:#9A8F80">공감·문제·해결책·한계·바람·방향·배제 5분25초</div><div style="flex:585;background:var(--or)">6 내 아이템 9분45초</div><div style="flex:70;background:#B5651D">비전</div><div style="flex:100;background:var(--teal)">질문·CTA</div></div>
<h2>롱폼 장면표 — 설득 7단계</h2>
<table><tr><th>단계</th><th>장면(샘플)</th><th>필재 나레이션 요지</th><th class="dev">설득 장치</th></tr>{trs}</table>
<h2>6단계 — 라이브에서 반응이 컸던 메리트 순서 + 프리셋 시험 8번(메리트마다 증거로 붙임)</h2>
<div class="lead" style="margin-bottom:12px">매번 <b>진짜 Claude Code 터미널에 한 줄</b> → 결과 3편 등장. 한 번마다 새 능력 하나. 결과 등장 방식 4가지를 돌려 써 같은 방식이 연달아 나오지 않게. (영상은 등장 방식 샘플 — 실제 편에서는 그 프리셋의 결과물로 다시 렌더)</div>
<div class="tests">{tt}</div>
<h2>쇼츠 4편 — 자르지 않고 세로로 따로</h2>
<table><tr><th></th><th>0~3초 훅</th><th>프리셋</th><th>결과 등장</th></tr>{sh}</table>
<div class="lead" style="margin-top:8px">35~45초 · 끝은 결론 한 줄 + 로고 3초 · "본영상 보세요"는 넣지 않음(벤치마킹 72편 중 1편) → 같은 키워드 제목 · 고정 댓글 링크 · 같은 날 업로드</div>
<h2>쓸 수 있는 프리셋 (구글 드라이브 칼카피영상 실측)</h2>
<table><tr><th>한 줄 명령</th><th>형식</th><th>완성본</th></tr>{pr}</table>
<div class="lead" style="margin-top:8px">이번 편은 8개 전부 사용. 다음 편부터는 같은 8개를 다른 결과물·다른 등장 순서로 돌린다(매일 스타일 교체). 폴더↔프리셋 짝은 폴더 이름과 프리셋.json 형식으로 맞춘 것.</div>
<h2>사장님 확인할 것</h2><ol><li>관통 키워드 "한 줄" · 이야기 구조(시험 8번) 이대로?</li><li>프리셋 8개와 순서(쉬운 → 어려운) 이대로?</li><li>터미널 = 진짜 Claude Code 화면 녹화로?</li><li>18분 40초판으로? (앞 6분 · 6단계 9분 45초 · 질문·CTA 1분 40초 — 필재 실측 뒤 조정) / 힉스필드·구글 플로우 이름을 그대로 말할지</li></ol>
</div></body></html>"""

out = os.path.join(HERE, "데일리_1편_구성안.html")
open(out, "w", encoding="utf-8").write(html)
open(r"C:\Users\TheRose\Desktop\숏클_데일리1편_구성안.html", "w", encoding="utf-8").write(html)
print(out)
