"""
삼프로TV 영상 → 구어체 스토리보드
진행자 발언을 그대로 살려서 씬별로 정리
"""
import re, sys, os
sys.stdout.reconfigure(encoding='utf-8')

VTT = r'C:\Users\TheRose\AppData\Local\Temp\3pro_sb\v.ko.vtt'
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'wiki', 'insights', '3pro', 'SB_마켓인사이드_반도체독주조심.md'
)

# ── VTT 파싱 ──────────────────────────────────────────────
with open(VTT, encoding='utf-8') as f:
    content = f.read()

segs, cur_t, cur_txt = [], '', []
for line in content.split('\n'):
    line = line.strip()
    if '-->' in line:
        if cur_txt and cur_t:
            segs.append((cur_t, ' '.join(cur_txt).strip()))
        cur_t = line.split('-->')[0].strip()[:8]
        cur_txt = []
    elif line and not line.isdigit() and not line.startswith('WEBVTT'):
        c = re.sub(r'<[^>]+>', '', line).strip()
        if c:
            cur_txt.append(c)

# 중복 제거
uniq, prev = [], ''
for t, txt in segs:
    if txt != prev:
        uniq.append((t, txt))
        prev = txt

def kor(s):
    return len(re.findall(r'[가-힣]', s))

def t2s(t):
    try:
        h, m, s = t.split(':')
        return int(h)*3600 + int(m)*60 + int(s)
    except:
        return 0

def decode(txt):
    return (txt.replace('&gt;', '>')
               .replace('&lt;', '<')
               .replace('&amp;', '&')
               .replace('&quot;', '"'))

# 한국어 필터
filt, prev = [], ''
for t, txt in uniq:
    if kor(txt) < 4 or len(txt) < 5:
        continue
    if txt[:8] == prev[:8]:
        continue
    filt.append((t, txt))
    prev = txt

# ── 화자 분리 + 발언 이어붙이기 ───────────────────────────
# >> 표시가 화자 B 전환
merged = []
buf_t, buf_spk, buf_lines = '', 'A', []

def flush():
    if buf_lines:
        merged.append((buf_t, buf_spk, ' '.join(buf_lines)))

for t, raw in filt:
    txt = decode(raw)
    is_b = txt.startswith('>>')
    txt_clean = txt[2:].strip() if is_b else txt
    cur_spk = 'B' if is_b else 'A'

    # 같은 화자 & 8초 이내면 이어붙이기
    if cur_spk == buf_spk and buf_lines and t2s(t) - t2s(buf_t) < 10:
        buf_lines.append(txt_clean)
    else:
        flush()
        buf_t, buf_spk, buf_lines = t, cur_spk, [txt_clean]

flush()

# ── 마크다운 출력 ─────────────────────────────────────────
os.makedirs(os.path.dirname(OUT), exist_ok=True)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('# [마켓 인사이드] 반도체 독주가 계속될수록 더 조심해야 하는 이유\n\n')
    f.write('> 삼프로TV | 43:27 | <https://www.youtube.com/watch?v=9lZVpFREQvU>\n\n')
    f.write('| 기호 | 추정 화자 |\n|------|----------|\n')
    f.write('| **A** | 진행자 (홍진채 라쿤자산운용 대표) |\n')
    f.write('| **B** | 게스트 |\n\n')
    f.write('---\n')

    scene_bucket = -1
    for t, spk, txt in merged:
        sec = t2s(t)
        bucket = sec // 300   # 5분 단위 씬

        if bucket != scene_bucket:
            scene_bucket = bucket
            mm = (sec // 60)
            ss = sec % 60
            m_label = f'{mm:02d}:{ss:02d}'
            f.write(f'\n\n## SCENE [{m_label}]\n\n')

        prefix = '**A**' if spk == 'A' else '> **B**'
        f.write(f'{prefix} `{t}` {txt}\n\n')

print(f'저장 완료: {OUT}')
print(f'총 발언 블록: {len(merged)}개')
