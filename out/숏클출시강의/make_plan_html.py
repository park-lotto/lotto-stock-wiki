"""데일리 1편 구성안 HTML 생성(장면마다 바탕화면 숏클_장면샘플 영상을 그 자리에서 재생)."""
import os, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))


def v(name):
    return "file:///C:/Users/TheRose/Desktop/" + urllib.parse.quote("숏클_장면샘플/" + name)


rows = [
    ("오프닝", "0:00–0:30", "결말 먼저", "J1_결과쏟아짐_세로_HeadshotPro.mp4", "이 쇼츠들, 전부 클로드에 말 한 줄로 만들었습니다. 오늘은 프리셋 8개로 한 줄을 8번 넣어 보겠습니다. 끝까지 보시면 어떤 쇼츠든 한 줄로 나오는 이유를 아시게 됩니다.", "썸네일 약속 30초 안 회수 · 끝까지 볼 이유"),
    ("1 문제 인식", "0:30–1:20", "손그림", "A_손그림_질문.mp4", "휴대폰에 저장해 둔 쇼츠, 몇 개나 되세요. 카톡 '나에게 보내기'까지요. 그중 올린 건 몇 개입니까. 의지가 약해서가 아닙니다.", "눈에 그려지는 손해"),
    ("", "", "네온 범퍼", "B_네온범퍼_포인트.mp4", "한 편에 원본 찾기, 자르기, 대본, 목소리, 자막, 썸네일. 5~6시간이 걸리니까요.", ""),
    ("2 일반 해결책", "1:20–2:00", "베이지 질문 카드 3장", "", "다들 이렇게 해결합니다. 직접 편집, 템플릿 프로그램, 요즘은 AI에게 부탁. 셋 다 맞는 방법이고, 각각 이렇게 하시면 됩니다(방법 하나씩 진짜로 알려줌).", "먼저 인정 · 가치 선지급"),
    ("3 한계", "2:00–2:40", "까만 창 기다림", "E_까만창_기다림.mp4", "그런데 AI에게 '쇼츠 만들어 줘' 한 줄로 부탁해 보면, 까만 창에서 글자만 보며 기다리다 끝납니다. 원본은 못 찾고, 됐는지도 모릅니다.", "'한 줄' 두 번째 등장"),
    ("4 해결 방향", "2:40–2:55", "베이지 카드", "", "필요한 건 더 좋은 질문이 아닙니다. 처음부터 끝까지 일하는 엔진입니다.", "범주를 먼저"),
    ("5 대안 배제", "2:55–3:30", "말로 부탁 vs 엔진", "D_말로부탁vs엔진.mp4", "말로 부탁하면 핑퐁만 길어집니다. 엔진은 원본 찾기부터 검증까지 6단계를 약 7분에, 사람 손 없이 끝냅니다.", "이름 없이 구조로"),
    ("6-① 엔진 원리", "3:30–5:00", "말로 vs 엔진 → 348 채널", "H_숫자격자_348채널.mp4", "왜 원본이어야 하는지, 엔진이 6단계를 어떻게 도는지. 지금까지 원본 채널 348곳, 판정한 영상 208편.", "6단계 시작 — 원리 먼저"),
    ("6-② 시험 8번", "5:00–11:40", "Claude 터미널 한 줄 → 결과 등장 ×8", "", "이번엔 ○○ 프리셋으로 한 줄. (아래 8번 — 한 번에 50초, 매번 새 능력 하나)", "본체 · 쉬운 것→어려운 것"),
    ("6-③ 보면서 고르기", "11:40–12:30", "웹 진행판", "F_웹진행판.mp4", "100% 맡겨도 되고, 단계마다 후보를 보고 고를 수도 있습니다. 무엇을 왜 했는지 한 줄씩 남습니다.", "통제감(60대 불안 해소)"),
    ("6-④ 증거", "12:30–13:20", "채널 리포트", "G_채널리포트.mp4", "구독자 9명 새 채널에서 일주일 19,164회. 어떤 영상이 평소보다 7배 터졌는지 숫자로 봅니다.", "실측 숫자"),
    ("6-⑤ 자는 동안", "13:20–14:00", "폰 알림 도착", "I2_결과등장_폰도착.mp4", "PC만 켜 두면 밤새 돌고, 아침에 폰으로 도착합니다.", "결말 회수"),
    ("7 질문·CTA", "14:00–15:30", "말풍선 질문 4개 → 베이지 카드 + 로고", "", "'클로드 어렵잖아요?' '저작권은요?' '나이가 많은데요?'에 하나씩 답하고 → 프리셋 하나 고르고, 한 줄만 넣어 보세요. 신청서는 고정 댓글에.", "반론 차단 · 쉬운 다음 행동"),
]
tests = [
    ("1", "해외+화장품 프리셋으로 만들어줘", "해외 원본을 찾아 온다", "카드 3장 솟음", "I1_결과등장_카드3장.mp4", "코팩 · 연어크림 · 선크림"),
    ("2", "해외핫영상+자막·배경음 프리셋으로 만들어줘", "말 없이 자막과 배경음만으로", "번호·칩 소개", "J2_결과소개_세로_Flatlay.mp4", "하키퍽 · 파울볼 아빠 · LED 수도꼭지"),
    ("3", "해외핫영상+나레원음 프리셋으로 만들어줘", "원음을 살리고 나레를 섞는다", "격자 쏟아짐", "J1_결과쏟아짐_세로_HeadshotPro.mp4", "아이언맨 헬멧 · 미니카 · 가짜 잠자리"),
    ("4", "썰비하인드 프리셋으로 만들어줘", "숨은 이야기 대본을 쓴다", "폰 알림 도착", "I2_결과등장_폰도착.mp4", "아웃백 비밀 · 바나나우유 · 코스트코 가격코드"),
    ("5", "연예인+후기 프리셋으로 만들어줘", "연예인 원음 + 같은 제품까지 찾아 붙인다", "카드 3장 솟음 + 진행판", "I1_결과등장_카드3장.mp4", "함익병 도브 · 강민경 틴트 · 김가연 BB"),
    ("6", "연예인 레시피 프리셋으로 만들어줘", "레시피 원음 + 재료까지", "번호·칩 소개", "J2_결과소개_세로_Flatlay.mp4", "성시경 신라면 · 김가연 오징어무 · 강주은 티본"),
    ("7", "원곡 인물 프리셋으로 만들어줘", "나레 없이 음악으로 끌고 간다", "격자 쏟아짐", "J1_결과쏟아짐_세로_HeadshotPro.mp4", "베이스점프 · 독수리 착지 · 사과깎이"),
    ("8", "여행 숙소 프리셋으로 만들어줘", "숙소 주소 하나로 숙소 쇼츠까지", "폰 알림 도착", "I2_결과등장_폰도착.mp4", "가평 숨은계곡 펜션 2판"),
]
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
<div class="lead">롱폼 약 15분 30초 + 쇼츠 4편, 같은 날 함께 기획 · 2026-10-29 · 샘플 영상은 바탕화면 숏클_장면샘플 폴더(그 자리에서 재생)</div>
<div class="sum">
<div class="box"><b>관통 키워드 = "한 줄"</b><br>오프닝 "한 줄로 나왔습니다" → 한계 "한 줄로 부탁하면 안 된다" → 본론 "프리셋+한 줄" ×8 → 끝 "오늘 한 줄 넣어 보세요"</div>
<div class="box"><b>이야기 구조</b><br>주인공 = 시청자(40·50·60대) · 적 = 시간 · 실패한 시도 = AI에게 말로 부탁 · 조력자 = 숏클 엔진 · <b>시험 8번</b> = 프리셋 8개 · 결말 = 자는 동안 쌓인 결과물</div>
<div class="box"><b>핵심(사장님)</b><br>진짜 Claude 가 만드는 과정 + 결과물 등장. 결과 등장 방식은 매번 다르게. 목소리 = 필재 1.25배속.</div>
</div>
<div class="bar"><div style="flex:30;background:#6B6660">오프닝</div><div style="flex:180;background:#9A8F80">1~5단계 3분</div><div style="flex:630;background:var(--or)">6 내 아이템 10분30초 (68%)</div><div style="flex:90;background:var(--teal)">질문·CTA</div></div>
<h2>롱폼 장면표 — 설득 7단계</h2>
<table><tr><th>단계</th><th>장면(샘플)</th><th>필재 나레이션 요지</th><th class="dev">설득 장치</th></tr>{trs}</table>
<h2>6단계 — 시험 8번 (쉬운 것 → 어려운 것, 한 번 50초)</h2>
<div class="lead" style="margin-bottom:12px">매번 <b>진짜 Claude Code 터미널에 한 줄</b> → 결과 3편 등장. 한 번마다 새 능력 하나. 결과 등장 방식 4가지를 돌려 써 같은 방식이 연달아 나오지 않게. (영상은 등장 방식 샘플 — 실제 편에서는 그 프리셋의 결과물로 다시 렌더)</div>
<div class="tests">{tt}</div>
<h2>쇼츠 4편 — 자르지 않고 세로로 따로</h2>
<table><tr><th></th><th>0~3초 훅</th><th>프리셋</th><th>결과 등장</th></tr>{sh}</table>
<div class="lead" style="margin-top:8px">35~45초 · 끝은 결론 한 줄 + 로고 3초 · "본영상 보세요"는 넣지 않음(벤치마킹 72편 중 1편) → 같은 키워드 제목 · 고정 댓글 링크 · 같은 날 업로드</div>
<h2>쓸 수 있는 프리셋 (구글 드라이브 칼카피영상 실측)</h2>
<table><tr><th>한 줄 명령</th><th>형식</th><th>완성본</th></tr>{pr}</table>
<div class="lead" style="margin-top:8px">이번 편은 8개 전부 사용. 다음 편부터는 같은 8개를 다른 결과물·다른 등장 순서로 돌린다(매일 스타일 교체). 폴더↔프리셋 짝은 폴더 이름과 프리셋.json 형식으로 맞춘 것.</div>
<h2>사장님 확인할 것</h2><ol><li>관통 키워드 "한 줄" · 이야기 구조(시험 8번) 이대로?</li><li>프리셋 8개와 순서(쉬운 → 어려운) 이대로?</li><li>터미널 = 진짜 Claude Code 화면 녹화로?</li><li>15분 30초판으로 바로 제작? (1~5단계 3분 · 6단계 10분 30초 · 질문·CTA 1분 30초 — 필재 실측 뒤 조정)</li></ol>
</div></body></html>"""

out = os.path.join(HERE, "데일리_1편_구성안.html")
open(out, "w", encoding="utf-8").write(html)
open(r"C:\Users\TheRose\Desktop\숏클_데일리1편_구성안.html", "w", encoding="utf-8").write(html)
print(out)
