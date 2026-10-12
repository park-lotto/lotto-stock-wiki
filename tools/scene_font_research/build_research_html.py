# -*- coding: utf-8 -*-
"""장면폰트 조사 HTML 생성기 — 사장님이 글꼴·색톤·꾸밈을 고르는 페이지를 만든다.

입력(전부 실측):
  out/장면꾸미기_작업대/스타일수집/final_styles.json   훅·본문 실측 102채널
  tools/scene_font_research/noonnu_pages/*.html        눈누 글꼴 페이지 원문(라이선스·파일 URL의 근거)
출력:
  out/장면폰트_조사.html

다시 돌리기:  py tools/scene_font_research/build_research_html.py
눈누 페이지가 없으면 받아 온다(--fetch). 경로를 손으로 짓지 않는다 — 페이지에서 뽑는다(handoff/폰트추가.md 함정 3).
"""
import sys, re, json, html, colorsys, collections, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAGES = pathlib.Path(__file__).resolve().parent / 'noonnu_pages'
STYLES = ROOT / 'out' / '장면꾸미기_작업대' / '스타일수집' / 'final_styles.json'
OUT = ROOT / 'out' / '장면폰트_조사.html'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36'

# (눈누 페이지 번호, 화면 이름, 고를 파일명에 들어갈 조각, 성격)
CANDIDATES = [
    (330, '양진체', 'yangjin', '각진 임팩트 · 쇼츠 단골'),
    (364, '쿠키런 Black', 'Black', '통통 굵은 · 게임 느낌'),
    (676, '원스토어 모바일POP', 'POP', '팝 · 마트 전단 느낌'),
    (223, '에스코어드림 9', '9Black', '초굵은 고딕 · 뉴스 속보'),
    (1456, '페이퍼로지 9', '9Black', '초굵은 모던 고딕'),
    (1369, '프리젠테이션 9', '9Black', '좁고 굵은 · 글자 많이 들어감'),
    (427, '메이플스토리 Bold', 'Bold', '둥글 귀여움 · 친근'),
    (82, '즐거운이야기', 'Enjoy', '예능 자막 느낌'),
    (463, '이사만루 Bold', 'Bold', '스포츠 중계 · 단단함'),
    (1146, 'KBO 다이아고딕 Bold', 'bold', '스포츠 · 각진 고딕'),
    (669, '카페24 써라운드', 'Ssurround', '둥근 굵은 · 부드러운 강조'),
    (1381, 'HS산토끼 2.0', 'SanTokki', '손맛 굵은 붓 · 개성'),
    (461, '빙그레 싸만코 Bold', 'Bold', '말랑 둥근 · 간식 느낌'),
    (1042, '태나다', 'Tenada', '세로로 긴 · 포스터'),
    (731, '창원단감아삭 Bold', 'Asac', '아삭한 각 · 또렷'),
    (321, '을지로체', 'EULJIRO', '간판 붓글씨 · 레트로'),
    (499, '을지로10년후', '10years', '낡은 간판 · 빈티지'),
    (805, '강원교육튼튼', 'Power', '튼튼 굵은 · 어린이 교재'),
    (1710, '학교안심 포스터', 'Poster', '포스터 제목 · 굵고 곧음'),
    (458, '티머니 둥근바람 EB', 'ExtraBold', '둥근 고딕 · 깔끔 강조'),
    (876, '영도체 Heavy', 'Hv', '바다 도시 · 묵직한 곡선'),
    (1186, '파셜산스', 'Partial', '잘린 획 · 실험적 · 패션'),
    (1405, '망고보드 또박 B', 'Ddobak-B', '또박또박 · 정보 전달'),
]

# 색톤: 실측 조합(어두운 바탕+흰 1줄+강조 2줄)이 뼈대. 강조색을 더 곱게 다듬은 것과 새 조합을 섞었다.
PALETTES = [
    ('p01', '이븐 청록', '#1B1B1F', '#FFFFFF', '#19F5E6', '실측 2위 조합(15채널)을 살짝 맑게'),
    ('p02', '경고 노랑', '#141414', '#FFFFFF', '#FFE500', '실측 1위 조합(17채널)'),
    ('p03', '네온 라임', '#0E1410', '#FFFFFF', '#B6FF3C', '실측 초록 계열(8채널)을 형광으로'),
    ('p04', '핫핑크', '#17101A', '#FFFFFF', '#FF5FA8', '실측 핑크 계열(8채널)'),
    ('p05', '세일 레드', '#151010', '#FFFFFF', '#FF3B3B', '실측 빨강 계열(6채널)'),
    ('p06', '귤 오렌지', '#17120C', '#FFFFFF', '#FF9A1F', '실측 주황 계열(4채널)'),
    ('p07', '일렉트릭 블루', '#0B1020', '#FFFFFF', '#3DA5FF', '실측 파랑 계열(3채널)을 밝게'),
    ('p08', '노랑+청록 더블', '#121212', '#FFE500', '#19F5E6', '1줄도 색 — 실측엔 9채널이 1줄 노랑'),
    ('p09', '라벤더 밤', '#15122B', '#F3EEFF', '#B69CFF', '새 조합 · 뷰티·감성 상품용'),
    ('p10', '민트 크림', '#0F1F1C', '#F4FFF9', '#6FFFD2', '새 조합 · 살림·청소 상품용'),
    ('p11', '피치 코랄', '#22120F', '#FFF4EC', '#FF8F6B', '새 조합 · 식품·간식 상품용'),
    ('p12', '골드 프리미엄', '#14110A', '#FFF8E1', '#F4C542', '새 조합 · 고급·가전 상품용'),
    ('p13', '흰 바탕 빨강', '#FFFFFF', '#111111', '#FF2D2D', '실측 흰 바탕(5채널) · 뉴스 속보'),
    ('p14', '흰 바탕 로열블루', '#FFFFFF', '#111111', '#1F4BFF', '흰 바탕 변형 · 신뢰감'),
    ('p15', '노랑 바탕 검정', '#FFE500', '#111111', '#E60023', '새 조합 · 전단지·특가'),
    ('p16', '딥 블루 바탕', '#0D2A6B', '#FFFFFF', '#FFE45B', '실측 파랑 바탕(4채널)'),
]

# 꾸밈(글자 처리). 최종 영상은 편집기 화면을 그대로 찍는 구조라(precision20-ui.js:268 주석) CSS로 되는 건 영상에도 나온다.
TREATMENTS = [
    ('t_plain', '기본 외곽선', '검은 외곽선 + 아래 그림자. 지금 편집기 방식'),
    ('t_box', '형광 박스', '2줄 뒤에 강조색 박스, 글자는 어둡게. 실측 대조표에 여러 채널'),
    ('t_under', '형광펜 밑줄', '2줄 아래 절반만 강조색 칠'),
    ('t_glow', '네온 글로우', '강조색 빛 번짐'),
    ('t_grad', '그라데이션 글자', '2줄이 강조색→흰색으로 흐름'),
    ('t_3d', '입체 그림자', '오른쪽 아래로 두꺼운 단색 그림자'),
    ('t_tilt', '기울임 속도감', '살짝 기울여 움직이는 느낌'),
    ('t_thick', '두꺼운 흰 테두리', '스티커처럼 흰 테두리를 두껍게'),
]


def fetch_pages():
    PAGES.mkdir(parents=True, exist_ok=True)
    for pid, *_ in CANDIDATES:
        p = PAGES / f'{pid}.html'
        if p.exists() and p.stat().st_size > 1000:
            continue
        req = urllib.request.Request(f'https://noonnu.cc/font_page/{pid}', headers={'User-Agent': UA})
        p.write_bytes(urllib.request.urlopen(req, timeout=30).read())
        print('받음', pid)


def parse_page(pid, pick):
    s = (PAGES / f'{pid}.html').read_text(encoding='utf-8', errors='ignore')
    urls = sorted(set(re.findall(r"https://[^\"')\s]+\.(?:woff2|woff|ttf|otf)", s)))
    hit = [u for u in urls if pick.lower() in u.rsplit('/', 1)[1].lower()]
    if not hit:
        raise SystemExit(f'{pid}: 파일명에 "{pick}" 들어간 URL이 없다 — {urls}')
    txt = html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)))
    video = bool(re.search(r'영상[^※]{0,80}?사용 가능', txt)) or '영상 제작 및 자막' in txt or '일반 동영상' in txt or '영상: 썸네일' in txt
    m = re.search(r'임베딩 웹사이트 및 프로그램 서버 내 폰트 탑재, E-book 제작 (사용 가능|사용 금지|조건부 허용)', txt)
    embed = m.group(1) if m else ('사용 가능(본문)' if ('임베드' in txt or '임베딩' in txt) else '표 없음')
    return hit[0], video, embed


def hue_name(c):
    r, g, b = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < .25:
        return '흰색·회색' if v > .6 else '검정·어두움'
    h *= 360
    for lim, n in [(15, '빨강'), (45, '주황'), (70, '노랑'), (160, '초록'), (200, '청록'), (260, '파랑'), (330, '보라·핑크'), (361, '빨강')]:
        if h < lim:
            return n


def research_stats():
    d = json.loads(STYLES.read_text(encoding='utf-8'))
    acc, bg, ratios, nlines = collections.Counter(), collections.Counter(), [], collections.Counter()
    for t in d:
        L = (t.get('hook') or {}).get('lines') or []
        nlines[len(L)] += 1
        if len(L) < 2:
            continue
        acc[hue_name(L[1]['color'])] += 1
        bg[hue_name(t['hook'].get('title_bg') or '#000000')] += 1
        ratios.append(L[1]['h'] / L[0]['h'])
    ratios.sort()
    return {'channels': len(d), 'two': sum(v for k, v in nlines.items() if k >= 2), 'nlines': dict(nlines),
            'accent': acc.most_common(), 'bg': bg.most_common(),
            'ratio_med': round(ratios[len(ratios) // 2], 2), 'ratio_q1': round(ratios[len(ratios) // 4], 2),
            'ratio_q3': round(ratios[3 * len(ratios) // 4], 2)}


def main():
    if '--fetch' in sys.argv or not PAGES.exists():
        fetch_pages()
    fonts = []
    for pid, name, pick, mood in CANDIDATES:
        url, video, embed = parse_page(pid, pick)
        fonts.append({'id': f'f{pid}', 'name': name, 'mood': mood, 'url': url, 'video': video, 'embed': embed,
                      'page': f'https://noonnu.cc/font_page/{pid}'})
    bad = [f['name'] for f in fonts if not f['video']]
    if bad:
        raise SystemExit(f'영상 사용 가능을 확인 못 한 글꼴: {bad}')
    data = {'fonts': fonts, 'stats': research_stats(),
            'palettes': [dict(zip(('id', 'name', 'bg', 'c1', 'c2', 'note'), p)) for p in PALETTES],
            'treatments': [dict(zip(('id', 'name', 'note'), t)) for t in TREATMENTS]}
    tpl = (pathlib.Path(__file__).resolve().parent / 'research_template.html').read_text(encoding='utf-8')
    OUT.write_text(tpl.replace('/*__DATA__*/', 'const DATA=' + json.dumps(data, ensure_ascii=False) + ';'), encoding='utf-8')
    print('글꼴', len(fonts), '색톤', len(PALETTES), '꾸밈', len(TREATMENTS), '→', OUT)
    print('통계', json.dumps(data['stats'], ensure_ascii=False))


if __name__ == '__main__':
    main()
