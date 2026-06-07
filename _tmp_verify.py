import sys
sys.stdout.reconfigure(encoding='utf-8')
from pipeline.atoms.db import query_atoms, get_atom_count

print(f'총 원자 수: {get_atom_count()}')

print('\n== 최신 원자 10개 ==')
atoms = query_atoms(days=60, limit=10)
for a in atoms:
    print(f"  [{a['date']}][{a['signal']}] {a['source_name']} | {a['asset']} | {a['content'][:70]}...")

print('\n== 섹터별 bullish 원자 ==')
for sector in ['반도체', '조선', '방산', '로봇']:
    atoms = query_atoms(sector=sector, signal='bullish', days=60, limit=2)
    if atoms:
        print(f"\n  [{sector}]")
        for a in atoms:
            print(f"    {a['asset']}: {a['content'][:60]}...")
