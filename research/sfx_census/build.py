# 2단계: files.json -> 길이(ffprobe 순차)·md5·분류·출처 -> catalog.json. 원본은 읽기만.
import json, os, sys, hashlib, subprocess, re
sys.stdout.reconfigure(encoding="utf-8")
d=json.load(open("files.json",encoding="utf-8"))
cache={}
if os.path.exists("catalog.json"):
    for x in json.load(open("catalog.json",encoding="utf-8")): cache[x["path"]]=x
def dur(p):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True,encoding="utf-8",errors="replace")
    try: return round(float(r.stdout.strip()),3)
    except: return None
def md5(p):
    h=hashlib.md5()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()
CATS=[("리액션탄성",r"와우|우와|wow|헉|어머|대박|오오|오우|감탄|omg|oh my|탄성|ooh|aww|우오|이야"),
 ("웃음",r"웃음|laugh|하하|ㅋㅋ|lol|haha|키득|giggle|chuckle"),
 ("박수환호",r"박수|환호|applause|clap|cheer|crowd|yay|함성"),
 ("실패삐",r"wrong|buzz|fail|error|틀림|땡|삑|삐|오답|beep|부저|bruh|negative"),
 ("긴장드럼롤",r"드럼롤|drum ?roll|긴장|suspense|tension|heartbeat|심장|두근"),
 ("놀람효과",r"뿅|띠용|두둥|dun|boing|놀람|surprise|shock|충격|reveal|짠|tada|ta-da|등장|vine|boom|쾅|impact|hit|dramatic"),
 ("휙전환",r"whoo?sh|swoosh|swish|휙|휘|슉|전환|transition|swipe|slide|woosh|바람"),
 ("팝띵",r"pop|뽁|뽀|뿅|ding|띵|띠링|챙|bell|chime|click|딸깍|tick|틱|tap|bubble|notification|알림|sparkle|반짝|coin|ui|button|버튼|blip|bling")]
MEME={"놀람":["놀람효과","리액션탄성"],"충격_입막":["놀람효과"],"의심_황당":["실패삐","놀람효과"],"기쁨_환호":["박수환호","리액션탄성"],
 "감탄_박수":["박수환호","리액션탄성"],"웃음":["웃음"],"슬픔":[],"분노_짜증":["실패삐"],"당황_멘붕":["실패삐","놀람효과"],
 "공포_움찔":["긴장드럼롤","놀람효과"],"거절_절레":["실패삐"],"끄덕_엄지":["팝띵"]}
MEMEKW={"놀람":r"놀|헉|wow|surprise|띠용|우와",
 "충격_입막":r"충격|shock|두둥|dun|dramatic|쾅|boom|impact",
 "의심_황당":r"띠용|boing|황당|의심|\?|bruh|huh|물음",
 "기쁨_환호":r"환호|cheer|yay|기쁨|함성|tada|짠|성공|success|win",
 "감탄_박수":r"박수|clap|applause|감탄|와우|우와|오오",
 "웃음":r"웃음|laugh|하하|ㅋㅋ|haha|giggle",
 "슬픔":r"슬픔|sad|trombone|womp|우울|fail",
 "분노_짜증":r"분노|짜증|angry|화남|grr|buzz|부저",
 "당황_멘붕":r"당황|멘붕|panic|glitch|글리치|어리둥|띠용|error",
 "공포_움찔":r"공포|horror|scary|scream|비명|움찔|긴장|suspense|heartbeat|심장",
 "거절_절레":r"wrong|오답|땡|삑|no|거절|nope|x",
 "끄덕_엄지":r"ding|띵|딩동|정답|correct|ok|좋아|띠링|success|체크|check"}
def cat(name):
    s=name.lower()
    for c,rx in CATS:
        if re.search(rx,s): return c
    return "기타"
def src(p):
    s=p.lower()
    if "capcut" in s: return "캡컷 앱 캐시(캡컷 효과음 라이선스)"
    if "kakao" in s: return "카카오톡 앱 내장 알림음"
    if "movavi" in s: return "Movavi 편집기 기본 콘텐츠"
    if "appdata\local\programs" in s: return "설치 프로그램 내장 소리"
    if "mixkit" in s or re.search(r"\\d{3,4}-preview\.(mp3|wav)$",s): return "mixkit 추정(파일명 NNNN-preview)"
    if "pixabay" in s: return "pixabay"
    if "freesound" in s: return "freesound"
    if "media-use" in s or "\skills\\" in s: return "에이전트 스킬 번들(media-use)"
    if "효과음 종합" in s: return "모름(바탕화면 '효과음 종합' — 유튜버 배포팩 추정, 라이선스 미확인)"
    if "sfx_packs" in s or "이븐쇼핑_효과음" in s: return "숏템메이커 효과음팩(효과음 종합·mixkit에서 가공)"
    return "모름"
res=[]
for i,x in enumerate(d):
    p=x["path"]; c=cache.get(p)
    if c and c.get("size")==x["size"] and c.get("dur") is not None: res.append(c); continue
    try: h=md5(p)
    except OSError: continue
    du=dur(p); name=os.path.basename(p); folder=os.path.basename(os.path.dirname(p))
    key=folder+"/"+name
    r={"path":p,"name":name,"folder":folder,"size":x["size"],"dur":du,"md5":h,"category":cat(key),"source":src(p),
       "long_bgm": bool(du and du>10)}
    r["meme"]=[m for m,rx in MEMEKW.items() if re.search(rx,key.lower()) and not r["long_bgm"]]
    res.append(r)
    if i%200==0: print(i,flush=True)
json.dump(res,open("catalog.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("done",len(res))
