"""티키타카 샘플 — 같은 대본(요거트 필터, 라이브 작가 '물건 발견형')을 세 판으로.
N=나레이터(여) R=리액션(남, 시청자 속마음) S=언니(인물 대사). 나레이션 문장은 원문 그대로."""
import wave, os, subprocess, json, time, hashlib
from google import genai
from google.genai import types
env=dict(l.strip().split("=",1) for l in open(r"C:/Users/TheRose/Desktop/로또의 주식/shopping_shorts/.env",encoding="utf-8") if "=" in l and not l.startswith("#"))
keys=[env[k].strip('"') for k in ("GEMINI_API_KEY","GEMINI_API_KEY_2","GEMINI_API_KEY_3","GEMINI_API_KEY_4") if env.get(k)]
OUT=r"C:/Users/TheRose/Desktop/로또의 주식/out/티키타카_샘플"
VOICE={"N":("Kore","썰 푸는 친한 언니처럼 자연스럽고 빠르게 말해:"),
       "R":("Puck","옆에서 듣던 친구가 툭 끼어드는 것처럼 짧고 자연스럽게, 과장하지 말고:"),
       "S":("Leda","무심하게 별거 아니라는 듯 말해:")}
L=["아니 언니 집에 갔더니 카페에서 파는 꾸덕한 요거트를 매일 먹고 있더라고요.",
   "어떻게 만들었냐고 슬쩍 물어봤더니 요즘 인기 많은 요거트 필터를 샀다는 거예요.",
   "면포로 짜는 건 줄 알고 귀찮아서 안 먹는다니까 그냥 붓고 넣어두면 끝이라고 하더라고요.",
   "알고 보니 요거트만 부어두면 알아서 유청을 싹 빼주는 신기한 물건이었어요.",
   "전에는 면포에 짜고 무거운 그릇 올려두느라 냉장고 자리도 좁고 번거로웠거든요.",
   "게다가 이제는 통에 붓고 뚜껑 덮어 냉장고에 넣어두면 알아서 꾸덕하게 완성되더라고요.",
   "전에는 다 만든 요거트가 용기 벽에 덕지덕지 붙어서 긁어내다 버리는 게 반이었거든요.",
   "이제는 뒤집기만 하면 찌꺼기 없이 덩어리째 훌훌 깔끔하게 떨어지더라고요.",
   "요즘은 아침마다 홈카페 차려서 요거트 볼 만들어 먹는 재미에 빠졌어요.",
   "댓글에 '요거트' 남겨주시면 정보 보내드릴게요."]
N=lambda i:("N",L[i])
V1=[N(i) for i in range(10)]
V2=[N(0),("R","매일?"),N(1),N(2),("R","붓기만 하면 끝이라고?"),N(3),N(4),N(5),N(6),("R","그럼 그건 어떡해?"),N(7),("R","오!"),N(8),N(9)]
V3=[N(0),("R","매일?"),N(1),("N","면포로 짜는 건 줄 알고 귀찮아서 안 먹는다니까"),("S","그냥 붓고 넣어 두면 끝이야."),
    ("R","붓기만 하면 끝이라고?"),N(3),N(4),N(5),N(6),("R","그럼 그건 어떡해?"),N(7),("R","오!"),N(8),N(9)]
os.makedirs("tk",exist_ok=True)
def tts(who,text):
    h=hashlib.md5(f"{who}{text}".encode()).hexdigest()[:10]; raw=f"tk/{h}.wav"; cut=f"tk/{h}_c.wav"
    if not os.path.exists(cut):
        voice,style=VOICE[who]
        for a in (range(8) if not os.path.exists(raw) else []):
            try:
                c=genai.Client(api_key=keys[a%len(keys)],http_options=types.HttpOptions(timeout=90000))
                r=c.models.generate_content(model="gemini-2.5-flash-preview-tts",contents=f"{style} {text}",
                  config=types.GenerateContentConfig(response_modalities=["AUDIO"],speech_config=types.SpeechConfig(
                  voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
                d=r.candidates[0].content.parts[0].inline_data.data; break
            except Exception as e: print("retry",who,str(e)[:80]); time.sleep(5)
        if not os.path.exists(raw):
          w=wave.open(raw,"wb");w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(d);w.close()
        tempo="atempo=1.15," if who=="N" else ""      # 라이브 기본 1.25배에 가깝게(제미니 원속이 이미 빠른 편)
        subprocess.run(["ffmpeg","-y","-v","error","-i",raw,"-af",
          f"{tempo}silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100",
          "-ac","1",cut],check=True)
    return cut
GAP={("N","N"):0.28,("N","R"):0.10,("R","N"):0.14,("N","S"):0.12,("S","R"):0.10,("S","N"):0.15}
def build(seq,name):
    parts=[];tl=[];t=0.0;prev=None
    for who,text in seq:
        f=tts(who,text)
        if prev: g=GAP.get((prev,who),0.2); parts.append(("sil",g)); t+=g
        d=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f],capture_output=True,text=True).stdout)
        tl.append({"who":who,"text":text,"t":round(t,2),"dur":round(d,2)}); parts.append(("f",f)); t+=d; prev=who
    lst=f"tk/{name}.txt"
    with open(lst,"w",encoding="utf-8") as fh:
        for k,v in parts:
            if k=="f": fh.write(f"file '{os.path.abspath(v)}'\n")
            else:
                s=f"tk/sil_{int(v*1000)}.wav"
                if not os.path.exists(s): subprocess.run(["ffmpeg","-y","-v","error","-f","lavfi","-i","anullsrc=r=44100:cl=mono","-t",str(v),s],check=True)
                fh.write(f"file '{os.path.abspath(s)}'\n")
    subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",lst,"-c:a","libmp3lame","-b:a","160k",f"{OUT}/{name}.mp3"],check=True)
    return {"name":name,"total":round(t,2),"lines":tl}
res=[build(V1,"1_나레이션만"),build(V2,"2_리액션꽂기"),build(V3,"3_리액션+언니대사")]
json.dump(res,open(f"{OUT}/timeline.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
for r in res: print(r["name"],r["total"],"초", sum(1 for l in r["lines"] if l["who"]!="N"),"개 끼어듦")
