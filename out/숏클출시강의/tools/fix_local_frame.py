"""조각 tsx 의 sq(a, b, <장면>) 안에서 인라인 useCurrentFrame() 을 쓰면 '전체 영상 프레임'을 읽어
장면 안 시각(로컬)과 어긋난다(애니메이션이 일찍 끝나거나 조건부 호출로 훅 오류). 이걸 sq(a, b, (lf) => <장면>) 으로 바꾸고
안의 useCurrentFrame() 을 lf 로 바꾼다. sq 정의도 함수형 장면을 받게 고친다. 사용: py fix_local_frame.py <src 폴더> [파일...]
점검만: --check (고칠 곳 개수만 출력)"""
import re, sys, pathlib
SQ_OLD = 'const sq = (a: number, b: number, el: React.ReactNode) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{el}</Sequence>;'
SQ_NEW = ('const LF: React.FC<{ r: (f: number) => React.ReactNode }> = ({ r }) => <>{r(useCurrentFrame())}</>;\n'
          'const sq = (a: number, b: number, el: React.ReactNode | ((f: number) => React.ReactNode)) => <Sequence from={S(a)} durationInFrames={Math.max(1, S(b) - S(a))}>{typeof el === "function" ? <LF r={el} /> : el}</Sequence>;')
def match_paren(s, i):
    d = 0; q = None
    for j in range(i, len(s)):
        c = s[j]
        if q:
            if c == q and s[j-1] != chr(92): q = None
            continue
        if c in '"`': q = c; continue
        if c == '(': d += 1
        elif c == ')':
            d -= 1
            if d == 0: return j
    raise ValueError('unbalanced')
def fix(text):
    m = text.find('const Main')
    head, body = text[:m], text[m:]
    out, i, n = [], 0, 0
    while True:
        k = body.find('sq(', i)
        if k < 0: out.append(body[i:]); break
        if k > 0 and (body[k-1].isalnum() or body[k-1] == '_'): out.append(body[i:k+3]); i = k+3; continue
        e = match_paren(body, k+2)
        call = body[k:e+1]
        if 'useCurrentFrame()' in call:
            # 세 번째 인자 시작 = 최상위 쉼표 두 개 뒤
            d = 0; commas = []
            for j, c in enumerate(call):
                if c in '([{': d += 1
                elif c in ')]}': d -= 1
                elif c == ',' and d == 1: commas.append(j)
            p = commas[1] + 1
            call = call[:p] + ' (lf: number) =>' + call[p:].replace('useCurrentFrame()', 'lf')
            n += 1
        out.append(body[i:k]); out.append(call); i = e+1
    return head + ''.join(out), n
if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    src = pathlib.Path(args[0]); files = args[1:] or sorted(p.name for p in src.glob('p*.tsx'))
    for name in files:
        p = src / name; t = p.read_text(encoding='utf-8')
        new, n = fix(t)
        if n and SQ_OLD in new: new = new.replace(SQ_OLD, SQ_NEW)
        left = new[new.find('const Main'):].count('useCurrentFrame()') - (1 if 'const f = useCurrentFrame()' in new[new.find('const Main'):] else 0)
        print(f'{name}: 고침 {n}곳, 남은 인라인 {left}')
        if '--check' not in sys.argv and n: p.write_text(new, encoding='utf-8')
