import json,sys,re,collections,numpy as np
sys.stdout.reconfigure(encoding="utf-8")
p=json.load(open("prep.json",encoding="utf-8")); ev=json.load(open("events.json")); ty=json.load(open("types.json",encoding="utf-8"))
NAMES=["1제목훅","2떡밥","3정체공개","4기능시연","5반전","6마무리"]
def sections(d):
    W=d["words"]; segs=d["segs"]; dur=d["dur"]
    hook_end=next((s["s"] for s in segs[1:] if s["s"]>=1.3),2.0)
    # 떡밥 끝: hook 뒤 첫 '는데' 어미 단어
    bait_end=None
    for i,w in enumerate(W):
        if w["s"]>=hook_end-0.05 and re.search(r"는데\??[.,]?$",w["w"]):
            bait_end=W[i+1]["s"] if i+1<len(W) else w["e"]; bi=i+1; break
    # 반전 시작
    turn=None
    for i,w in enumerate(W):
        if re.search(r"충격|종결급",w["w"]) or (w["w"].startswith("진짜는")):
            # 구절 시작으로 거슬러: 앞 1~3단어 중 '근데/진짜/하지만/그' 포함 처음
            j=i
            while j>0 and i-j<4 and re.match(r"(근데|진짜|하지만|그|누구도|예상|못한)",W[j-1]["w"]) and W[j]["s"]-W[j-1]["e"]<0.4: j-=1
            turn=W[j]["s"]; break
    last=segs[-1]["s"]
    reveal=None
    if bait_end is not None and bi<len(W) and re.match(r"(바로|이건)",W[bi]["w"]):
        # 정체공개 구절 끝 = 다음 세그먼트 시작
        nxt=[s["s"] for s in segs if s["s"]>W[bi]["s"]+0.3]
        reveal=(bait_end,nxt[0] if nxt else bait_end+1.5)
    b=[(0,hook_end,NAMES[0])]
    if bait_end: b.append((hook_end,bait_end,NAMES[1]))
    s4=bait_end or hook_end
    if reveal: b.append((reveal[0],reveal[1],NAMES[2])); s4=reveal[1]
    e4=turn if turn else last
    b.append((s4,e4,NAMES[3]))
    if turn: b.append((turn,last,NAMES[4]))
    b.append((last,dur,NAMES[5]))
    return b
out={}
for vid,d in p.items():
    b=sections(d); out[vid]=b
    print(vid," | ".join(f"{n}:{s:.1f}-{e:.1f}" for s,e,n in b))
json.dump(out,open("sections.json","w",encoding="utf-8"),ensure_ascii=False)
