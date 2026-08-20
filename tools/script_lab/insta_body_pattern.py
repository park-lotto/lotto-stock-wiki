# -*- coding: utf-8 -*-
"""인스타 대본 — 훅 문형 축 × 본문 역할 프로필 실측 (2026-08-20, 인스타문형학습 트랙)

왜 이 파일이 있나
  인스타 spine 37행 중 31행이 beat_roles·templates가 빈 '죽은 재고'다. 개수가 아니라
  근거로 채우려면 실제 대본이 어떤 순서로 흐르는지를 실측해야 한다.

왜 판정 단위가 '채널'이 아니라 '훅 문형(축)'인가 — 실측 근거
  · 채널 안에서 훅 첫 2어절 일치율은 7~42%뿐이다(chae2home 42편에서 23%).
  · 반대로 같은 훅이 채널을 넘나든다: "여러분 다이소 가면 이거 무조건" 26편/12채널.
  → 채널로 가르면 대부분 '패턴 없음'으로 떨어지고, 문형으로 모으면 축이 잡힌다.
  사장님 확정(2026-08-20): "훅 문형 방향이 맞고, 본문 패턴도 패턴화 가능하다."

축 정규식은 짐작이 아니라 **미분류 훅을 눈으로 읽어가며** 3회 반복해 넓혔다.
역할 정규식도 대본 전문 6편을 읽고 뽑았다.

사용: python3 insta_body_pattern.py [reference.db 경로]
"""
import sqlite3, json, re, sys, collections

DB = sys.argv[1] if len(sys.argv) > 1 else 'reference.db'
BIN_NAMES = ['도입', '전개', '중반', '후반', '마무리']

# ── 훅 문형 축 — 위에서부터 먼저 맞는 것을 쓴다(구체적인 것이 위) ──────────
#
# ★가짜 축 3개를 검정으로 걸러냈다(접두어 검정: 접두어를 지우고 재판정)
#     대상호출("여러분") 32편 → 32편 전부 여전히 미분류
#     감탄개시("와")     32편 → 29편 여전히 미분류
#     본인경험("저 이거") 16편 → 14편 여전히 미분류
#   셋 다 내용 축이 아니라 **훅 수식어**다. 축으로 두면 진짜 축을 가린다.
#   수식어 출현율은 따로 쓸모가 있다: 여러분 23% · 와/우와 13% · 저 이거 8%
#
# ★'권위출처'(의사·기장·디자이너)는 훅 축에서 내렸다.
#   11편 중 3편이 실제로는 금지경고 문장이었고("흰쌀밥 절대 먹이지 마세요"),
#   유튜브 spine 55·56이 이미 authority를 **본문 칸**으로 둔다.
#   같은 판단을 훅과 본문 두 군데에 두면 반드시 어긋난다(CLAUDE.md 0순위-B).
#
# ★판정에 첫 2컷을 쓴다 — 첫 컷만 쓰면 커버리지가 72%→56%로 떨어진다(실측).
AXES = [
    ('다이소지목',  r'다이소.{0,10}(가면|에서|가서|털어)'),
    ('전세공포',    r'(원상\s*복구|전세|월세집|집주인|보증금|나가실\s*때)'),
    ('정체의문',    r'(라고\?|이라고\?|없앤다고|만든\s*거라고|되네\?|진짜\?)'),
    ('잘못인지',    r'(잘못\s*(먹|쓰|알|하)|아직도\s|지금까지)'),
    ('가족감동',    r'(펑펑|우셨|울었|눈물|감동)'),
    ('사회증거',    r'(어디서\s*(샀|사냐|산)|물어봐|다\s*이거\s*쓴|쓴다면서|난리|유행이)'),
    ('리스트형',    r'(\d+\s*(개|가지)|다섯|일곱|열\s*개|세\s*가지|알려드릴|모아왔|꿀템)'),
    ('지목호명',    r'(하시는\s*분|계시면|계신\s*분|둔\s*엄마|쓰시는\s*분|포기했던\s*분|사는\s*분|궁금하신\s*분)'),
    ('공감질문',    r'(죠\?|많죠|기억나세요|아니냐며|하시죠|안\s*지워지|무섭잖아요|많이들)'),
    ('금지경고',    r'(마세요|마시고|하지\s*마|주지\s*마|안\s*돼요|당장\s*보세요|큰일)'),
    ('무지후회',    r'(몰라서|모르면|나만\s*몰랐|진작|할\s*뻔|바꿀\s*뻔|왜\s*이제\s*알)'),
    ('지인증언',    r'(시어머니|시부모|어머님|시누이|처남댁|친구네|친구\s*집|친구가|동창|와이프|남편|언니네|언니를|엄마한테|엄마가|아빠한테|딸이|아들이|애\s*친구|선생님한테|조카가|부모님이)'),
    ('충격선언',    r'(충격|소리\s*질렀|난리|헛웃음|웃음부터|기절|깜짝\s*놀랐|역대급|발견했|대박|소름)'),
    ('해외발견',    r'(일본|중국|미국|독일|교도소|라쿠텐|해외|유럽|네덜란드|파리|프랑스)'),
    ('가격경악',    r'(만원|원도|원대|천원|원밖에|가성비|공짜|무료)'),
    ('무조건지시',  r'무조건\s*(이렇게|이거|사|담)'),
]

# ── 본문 역할 — 컷 텍스트 하나를 한 역할로 태깅(첫 매치) ────────────────
ROLES = [
    ('cta',   r'(남겨주세요|남겨\s*주세요|댓글|저장해|프로필|링크|디엠)'),
    ('가격',   r'(\d[\d,]*\s*원|만원대|천원|가성비|품절)'),
    ('불신',   r'(안\s*믿|거짓말|무슨\s*소리|설마)'),
    ('반응',   r'(왜\s*이제|섭섭|극찬|어디서\s*샀|알려주냐|물어봐|대박|난리)'),
    ('지적',   r'(뭐라|화를|혼났|보시더니|빤히|유심히|왜\s*이렇게)'),
    ('상황',   r'(갔다가|만났는데|오셨는데|들렸는데|받았는데|나갔는데|다녀왔|놀러)'),
    ('후회',   r'(진작|예전엔|그동안|그전엔|괜히|고생|폭탄|버렸|할\s*뻔)'),
    ('문제',   r'(스트레스|고민|짜증|불편|힘들|귀찮|냄새|곰팡이|눅눅|물때|잘\s*안)'),
    ('실증',   r'(직접|보여드|꺼내서|발라|붙이|뿌려|넣고|해봤|써보|눌러|담가|올리)'),
    ('사용법', r'(쓱|그냥|하기만|넣기만|한\s*번만|끝이|하면\s*돼|만\s*하면)'),
    ('효과',   r'(살아나|맑아|연해|사라|없어지|깨끗|줄어|안\s*느껴|훨씬|확실히|좋아졌|바뀌)'),
    ('정체',   r'(이거|이게|이건).{0,20}(예요|이에요|인데|래요|거든요|제품)'),
]

def axis_of(head):
    for name, rx in AXES:
        if re.search(rx, head):
            return name
    return '(미분류)'

def role_of(t):
    for name, rx in ROLES:
        if re.search(rx, t):
            return name
    return None

def load(db):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    sc2u = {}
    for r in c.execute('select shortcode,username from channel_archive'):
        sc2u.setdefault(r['shortcode'], r['username'])
    for r in c.execute('select shortcode,username from reel_history'):
        sc2u.setdefault(r['shortcode'], r['username'])
    docs = []
    for r in c.execute('select shortcode,script_json from script_extracts'):
        try: d = json.loads(r['script_json'])
        except Exception: continue
        segs = [s for s in (d.get('segments') or []) if (s.get('text') or '').strip()]
        if len(segs) < 5: continue
        ft = d.get('full_text') or ''
        # 한국어 대본만 — 샤오홍슈 중국어 편은 문형이 다르다(별도 축으로 다뤄야 한다)
        if not re.search(r'[가-힣]', ft): continue
        head = ' '.join(s['text'] for s in segs[:2])
        docs.append(dict(sc=r['shortcode'], u=sc2u.get(r['shortcode'], '?'),
                         head=head, segs=segs, ft=ft, axis=axis_of(head)))
    return docs

def med(a): return sorted(a)[len(a)//2]

def main():
    docs = load(DB)
    print(f'분석 대상 {len(docs)}편 (한국어·컷 5개 이상)\n')
    print('=' * 74); print('[A] 훅 문형 축 분포'); print('=' * 74)
    cnt = collections.Counter(d['axis'] for d in docs)
    for a, n in cnt.most_common():
        ch = len({d['u'] for d in docs if d['axis'] == a})
        print(f'  {a:<10}{n:>5}편 ({n*100//len(docs):>2}%) {ch:>3}채널')
    cov = 100 - cnt['(미분류)'] * 100 // len(docs)
    print(f'  → 축 커버리지 {cov}%')

    for ax, _ in AXES:
        mine = [d for d in docs if d['axis'] == ax]
        if len(mine) < 12: continue
        print(); print('=' * 74)
        print(f'[B] {ax} — {len(mine)}편 / {len({d["u"] for d in mine})}채널')
        print('=' * 74)
        bins = [collections.Counter() for _ in range(5)]
        for d in mine:
            n = len(d['segs'])
            for i, s in enumerate(d['segs']):
                r = role_of(s['text'])
                if r: bins[min(4, i * 5 // n)][r] += 1
        for i, b in enumerate(bins):
            tot = sum(b.values()) or 1
            print(f'   {BIN_NAMES[i]}: ' + ', '.join(f'{k} {v*100//tot}%' for k, v in b.most_common(4)))
        dens = [len(d['ft']) / max(1, max((s.get('end') or 0) for s in d['segs'])) * 30 for d in mine]
        durs = [max((s.get('end') or 0) for s in d['segs']) for d in mine]
        cta = sum(1 for d in mine if re.search(ROLES[0][1], d['ft'][-70:]))
        print(f'   밀도 {med(dens):.0f}자/30s · 길이 {med(durs):.0f}초 · '
              f'컷 {med([len(d["segs"]) for d in mine])} · CTA {cta*100//len(mine)}%')
        ng = collections.Counter(); wh = collections.defaultdict(set)
        for d in mine:
            w = d['head'].split()
            for i in range(max(1, len(w) - 3)):
                g = ' '.join(w[i:i+4]); ng[g] += 1; wh[g].add(d['u'])
        fixed = [(g, n) for g, n in ng.most_common(60) if n >= 3 and len(wh[g]) >= 2][:6]
        if fixed:
            print('   고정 어구: ' + ' | '.join(f'{g}({n}편/{len(wh[g])}채널)' for g, n in fixed))
        print('   훅 예시: ' + ' / '.join(d['segs'][0]['text'][:34] for d in mine[:3]))

if __name__ == '__main__':
    main()
