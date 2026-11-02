import os,sys,io,re,datetime
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
R=r"G:\내 드라이브\강의정리"
ds=sorted(d for d in os.listdir(R) if os.path.isdir(os.path.join(R,d)) and not d.startswith('_'))
lec=[d for d in ds if not d.endswith('_자료')]; mat=[d for d in ds if d.endswith('_자료')]
G=[("정규 강의",r"^AI스위칭쇼츠"),("부기님 왕초보 특강",r"^부기님"),("프리미엄반 특강",r"^프리미엄반"),("초청 특강",r"^초청특강"),("게릴라 특강",r"^(게릴라|프반게릴라)"),("시크릿·스타터·기타",r".")]
out=[f"# 강의정리 색인\n\n갱신 {datetime.date.today()} · 강의 {len(lec)}개 · 자료 {len(mat)}개\n\n각 강의는 노하우카드(html·md)와 원본기록으로 구성됩니다.\n"]
left=list(lec); from urllib.parse import quote
for t,p in G:
    cur=[d for d in left if re.search(p,d)]; left=[d for d in left if d not in cur]
    out.append(f"\n## {t} ({len(cur)})\n\n| 강의 | 노하우카드 | 원본기록 |\n|---|---|---|")
    for d in cur:
        fs=os.listdir(os.path.join(R,d))
        c=next((f for f in fs if f.endswith('노하우카드.html')),None); o=next((f for f in fs if f.endswith('원본기록.md')),None)
        l=lambda f,txt:f"[{txt}]({quote(d)}/{quote(f)})" if f else "없음"
        out.append(f"| {d.replace('_',' ')} | {l(c,'열기')} | {l(o,'열기')} |")
out.append(f"\n## 강의 자료 ({len(mat)})\n\n| 자료 | 정리본 |\n|---|---|")
for d in mat:
    f=next((x for x in os.listdir(os.path.join(R,d)) if x.endswith('자료정리.md')),None)
    out.append(f"| {d.replace('_',' ')} | "+(f"[열기]({quote(d)}/{quote(f)})" if f else "없음")+" |")
open(os.path.join(R,"강의정리_색인.md"),"w",encoding="utf-8").write("\n".join(out)+"\n")
print(len(lec),len(mat),[l for l in out if '없음' in l])
