# 효과음 전수 조사 1단계: 파일 목록(경로·크기) -> files.json. 원본 읽기만.
import os, json, sys
sys.stdout.reconfigure(encoding="utf-8")
EXT={".mp3",".wav",".ogg",".m4a",".aac"}
SKIPN={".tracks","node_modules",".git","mix_jobs","meme_pack","windows","program files","program files (x86)",
 "$recycle.bin","system volume information","programdata","sfx_census"}
SKIPP=[s.lower() for s in [r"AppData\Local\Google",r"AppData\Local\Microsoft\Edge",r"AppData\Roaming\Mozilla",r"AppData\Local\Mozilla",
 r"AppData\Local\Naver",r"AppData\Local\BraveSoftware",r"AppData\Local\Temp",r"AppData\Local\Packages",r"AppData\Local\ms-playwright",
 r"AppData\Local\Microsoft\Windows",r"\Cache",r"\Code Cache",r"\GPUCache"]]
out=[]
for root in [r"C:\Users\TheRose", "D:\\"]:
    for dp,dns,fns in os.walk(root):
        low=dp.lower()
        dns[:]=[d for d in dns if d.lower() not in SKIPN and not any((os.path.join(low,d.lower())).endswith(s) or s+"\\" in os.path.join(low,d.lower())+"\\" for s in SKIPP)]
        for f in fns:
            if os.path.splitext(f)[1].lower() in EXT:
                p=os.path.join(dp,f)
                try: out.append({"path":p,"size":os.path.getsize(p)})
                except OSError: pass
json.dump(out,open(sys.argv[1],"w",encoding="utf-8"),ensure_ascii=False)
print(len(out), sum(x["size"] for x in out)//2**20,"MB")
