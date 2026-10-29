import subprocess, json
import re
L=[re.sub(r"^/c/","C:/",l.strip()) for l in open("list.txt",encoding="utf8") if l.strip()]
# card index -> source idx (list order 1..9 => card 0..8)
# spotlight: (card, a, d, S) per version
spots={'w':[(5,7.1,2.2,5.6),(4,7.6,2.8,8.0),(0,22.0,1.7,10.9),(3,21.7,2.3,12.8)],
       't':[(5,7.1,2.2,3.4),(4,7.6,2.8,5.8),(0,22.0,1.7,8.8)]}
st={'w':lambda i:2.0+i*0.3,'t':lambda i:0.5+i*0.22}
def run(a): subprocess.run(a,check=True)
for v in "wt":
    off={c:3.0 for c in range(9)}
    for c,a,d,S in spots[v]: off[c]=a-(S-st[v](c)); assert off[c]>=0,(v,c)
    for c in []:
        run(["ffmpeg","-v","error","-y","-ss",f"{off[c]:.3f}","-t","18","-i",L[c],"-an","-vf","scale=540:960,tpad=stop_mode=clone:stop_duration=20","-t","18","-r","30","-c:v","libx264","-crf","18","-pix_fmt","yuv420p",f"public/v{v}{c+1}.mp4"])
    dur=18 if v=='w' else 12
    inp=[];fl=[]
    g=[]
    for c,a,d,S in spots[v]:
        o=subprocess.run(["ffmpeg","-nostats","-hide_banner","-ss",str(a),"-t",str(d),"-i",L[c],"-vn","-af","ebur128","-f","null","-"],capture_output=True,text=True).stderr
        li=float(o.rsplit("I:",1)[1].split("LUFS")[0]); g.append(round(-15-li,2))
    print(v,g)
    for k,(c,a,d,S) in enumerate(spots[v]):
        inp+=["-ss",f"{a}","-t",f"{d}","-i",L[c]]
        fl.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={g[k]}dB,aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:d=0.15,afade=t=out:st={d-0.15}:d=0.15,adelay={int(S*1000)}|{int(S*1000)}[a{k}]")
    n=len(spots[v])
    fl.append("".join(f"[a{k}]" for k in range(n))+f"amix=inputs={n}:normalize=0:duration=longest,apad=whole_dur={dur},atrim=0:{dur},alimiter=limit=0.89[o]")
    run(["ffmpeg","-v","error","-y",*inp,"-filter_complex",";".join(fl),"-map","[o]","-ar","48000",f"aud/mix_{v}.wav"])
json.dump({v:spots[v] for v in spots},open("spots.json","w"))
