"""롱폼 전체에서 같은 손그림 포즈(hero/*)·소품 그림이 두 번 이상 나오나 센다(사장님 규칙: 포즈 반복 0).
사용: py check_pose_repeat.py <가편집 src 폴더>  → 반복이 있으면 rc=1"""
import re, sys, pathlib, collections
src = pathlib.Path(sys.argv[1]); uses = collections.defaultdict(list)
for p in sorted(src.glob('p*.tsx')) + [src / 'opening.tsx']:
    if not p.exists(): continue
    t = p.read_text(encoding='utf-8')
    for m in re.finditer(r'<Ink n="([a-z_]+)"', t): uses['hero/' + m.group(1)].append(p.stem)
    for m in re.finditer(r'staticFile\("(hero/[gc]_[a-z_]+|p6/p_[a-z]+)\.png"\)', t):
        k = re.sub(r'hero/[gc]_', 'hero/', m.group(1)); uses[k].append(p.stem)
rep = {k: v for k, v in uses.items() if len(v) > 1}
for k, v in sorted(uses.items()): print(('★반복 ' if k in rep else '      ') + f'{k}: {", ".join(v)}')
print(f'그림 {len(uses)}종, 반복 {len(rep)}종'); sys.exit(1 if rep else 0)
