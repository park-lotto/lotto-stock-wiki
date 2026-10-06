"""배경음 목록 파일 만들기(관제 146). 사용: py tools/bgm_lib/build.py <원본폴더(full.mp3·full2.mp3·b2/)> shopping_shorts/assets/bgm_lib
모음 영상은 구간(SEG), 단곡 영상은 유튜브 id(YT)로 받는다. 전부 -14 LUFS·최대 60초·끝 1.5초 페이드."""
import subprocess, sys, os
T = sys.argv[1]; O = sys.argv[2]; CAP = 60.0
# (id, 원본파일, 시작, 끝|None)
SEG = [("qiuqiu","full.mp3",0,31),("christian","full.mp3",68,94),("machi_no_dorufin","full.mp3",94,112),
 ("buttercup","full.mp3",112,139),("free_bird","full.mp3",139,176),("everything","full.mp3",176,241),
 ("astronomia","full.mp3",272,299),("dance_with_me","full.mp3",299,348),
 ("passo_bem_solto","full2.mp3",1.8,117.6),("before_spring_ends","full2.mp3",121.8,296.9),
 ("pretty_little_baby","full2.mp3",298.4,436.6),("beggin","full2.mp3",439.5,648.7),
 ("unstoppable","full2.mp3",651.8,866.4),("blue","full2.mp3",867.7,1079.3),("yoru_no_odoriko","full2.mp3",1082.5,1382.5)]
YT = [("EYGGd2NKwtI","mori_no_restaurant"),("orOgilmiL_4","no_batidao"),("Ip6cw8gfHHI","here_with_me"),
 ("e3Rnsz7XWkk","chubina"),("HLiYPbpvPVE","honwaka_puppu"),("-G62ksjwWbM","sweets"),("u5CVsCnxyXg","no_surprises"),
 ("Atx1ktB2dgs","otsukare_summer"),("1qtIoroF_Y4","lets_go"),("OMOGaugKpzs","every_breath_you_take"),("CvLHKUtcFg4","epic_inspiration")]
TRIM = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
def dur(p): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]).decode().strip())
def enc(src, out, pre_args, pre_af):
    tmp = out + ".tmp.wav"
    subprocess.run(["ffmpeg","-nostdin","-y","-loglevel","error",*pre_args,"-i",src,"-af",pre_af+"loudnorm=I=-14:TP=-1.5:LRA=11","-t",str(CAP),"-ar","44100","-ac","2",tmp],check=True)
    d = dur(tmp); fo = max(0.0, d-1.5)
    subprocess.run(["ffmpeg","-nostdin","-y","-loglevel","error","-i",tmp,"-af",f"afade=t=in:d=0.2,afade=t=out:st={fo:.2f}:d=1.5","-b:a","128k",out],check=True)
    os.remove(tmp); print(os.path.basename(out), round(dur(out),1), flush=True)
for i,f,a,b in SEG:
    enc(os.path.join(T,f), os.path.join(O,i+".mp3"), ["-ss",str(a+0.3),"-t",str(min(CAP+5,b-a-0.6))], "")
for v,i in YT:
    w = os.path.join(T,"b2",i+".wav")
    if not os.path.exists(w):
        subprocess.run(["yt-dlp","-q","-x","--audio-format","wav","-o",os.path.join(T,"b2",i+".%(ext)s"),"--","https://www.youtube.com/watch?v="+v],check=True,stdin=subprocess.DEVNULL)
    enc(w, os.path.join(O,i+".mp3"), [], TRIM)
