# 3단계: catalog.json 재분류(종류·분류·감정짤 짝·출처) + 요약.md + meme_sfx 복사(원본 유지)
import json, os, re, sys, shutil, collections
sys.stdout.reconfigure(encoding="utf-8")
d=json.load(open("catalog.json",encoding="utf-8"))
def kind(p):
    s=p.lower().replace(chr(92),"/")
    if re.search(r"voice_samples|/tts/|audioalg|site-packages|accessibilitysignal|antigravitysounds|notice_sound|fish_tts|/ai shorts/voice|/out/(?!volcano)|/data/|/tests?/",s): return "효과음 아님"
    if "kakaotalk" in s: return "앱 내장(카카오 이모티콘 소리)"
    return "효과음"
B=r"(?<![a-z])"; E=r"(?![a-z])"
CATS=[("리액션 탄성",r"와우|우와|"+B+"wow"+E+"|헉|어머|대박|오오|"+B+"omg"+E+"|탄성|감탄|"+B+"ooh"+E+"|"+B+"aww"+E),
 ("웃음",r"웃음|웃긴|laugh|하하|ㅋㅋ|haha|giggle|chuckle|키득"),
 ("박수·환호",r"박수|환호|applause|clap|cheer|crowd|"+B+"yay"+E+"|함성"),
 ("실패·삐",r"wrong|buzz|"+B+"fail|error|틀림|오류|땡|삑|삐|오답|"+B+"beep"+E+"|부저|bruh"),
 ("긴장·드럼롤",r"드럼롤|drum ?roll|긴장|suspense|tension|heartbeat|심장|두근"),
 ("놀람 효과",r"뿅|띠용|두둥|"+B+"dun"+E+"|boing|놀람|surprise|shock|충격|reveal|tada|짠|vine|"+B+"boom"+E+"|쾅|폭발|explosion|dramatic"),
 ("휙·전환",r"whoo?sh|swoosh|swish|휙|슉|전환|transition|swipe|woosh"),
 ("팝·띵",r"pop|뽁|뾱|뽀|ding|띵|띠링|챙|bell|chime|click|딸깍|"+B+"tick"+E+"|틱|"+B+"tap"+E+"|bubble|알림|sparkle|반짝|coin|버튼|blip|bling|오프너|opener")]
def cat(k):
    for c,rx in CATS:
        if re.search(rx,k): return c
    return "기타"
MEMEKW={"놀람":r"놀람|헉|"+B+"wow"+E+"|surprise|띠용|우와|뿅",
 "충격_입막":r"충격|shock|두둥|"+B+"dun"+E+"|dramatic|쾅|"+B+"boom"+E+"|impact|폭발",
 "의심_황당":r"띠용|boing|황당|의심|bruh|"+B+"huh"+E,
 "기쁨_환호":r"환호|cheer|"+B+"yay"+E+"|기쁨|함성|tada|짠|success|"+B+"win"+E,
 "감탄_박수":r"박수|clap|applause|감탄|와우|우와|오오",
 "웃음":r"웃음|laugh|하하|ㅋㅋ|haha|giggle",
 "슬픔":r"슬픔|"+B+"sad"+E+"|trombone|womp|우울",
 "분노_짜증":r"분노|짜증|angry|"+B+"grr|부저|buzzer",
 "당황_멘붕":r"당황|멘붕|panic|글리치|glitch|어리둥|황당",
 "공포_움찔":r"공포|horror|scary|scream|비명|움찔|suspense|heartbeat|심장|긴장",
 "거절_절레":r"wrong|오답|땡|틀림|"+B+"nope"+E+"|거절|error|오류",
 "끄덕_엄지":r"딩동|정답|correct|띠링|"+B+"ding"+E+"|체크|"+B+"ok"+E}
def src(p):
    s=p.lower()
    if "capcut" in s: return "캡컷(앱 캐시/프로젝트, 캡컷 라이선스)"
    if "kakaotalk" in s: return "카카오톡 앱 내장"
    if "movavi" in s: return "Movavi 편집기 기본 콘텐츠"
    if r"appdata\local\programs" in s: return "설치 프로그램 내장"
    if "sfx_norm" in s and "volcano" in s: return "볼케이노 채널 자산(.volcano-asset-receipts)"
    if "media-use" in s: return "에이전트 스킬 번들(media-use)"
    if "makelens" in s: return "MakeLens 앱 번들"
    if "mixkit" in s or re.search(r"(^|[^0-9])[0-9]{3,4}-preview\.(mp3|wav)$",os.path.basename(s)): return "mixkit 추정(NNNN-preview 파일명)"
    if "pixabay" in s: return "pixabay"
    if "sfx_packs" in s or "이븐쇼핑_효과음" in s: return "숏템메이커 효과음팩(효과음 종합·mixkit 가공)"
    if "효과음 종합" in s: return "모름(바탕화면 '효과음 종합', 튜브렌즈 배포팩 추정)"
    if "효과음 120가지" in s: return "모름(효과음 120가지 배포팩)"
    return "모름"
for x in d:
    k=(x["folder"]+"/"+x["name"]).lower()
    x["kind"]=kind(x["path"]); x["source"]=src(x["path"])
    sfx = x["kind"]=="효과음" and x["dur"] is not None
    x["category"]=cat(k) if sfx else "-"
    x["long_bgm"]=bool(x["dur"] and x["dur"]>10)
    x["meme"]=[m for m,rx in MEMEKW.items() if re.search(rx,k)] if (sfx and not x["long_bgm"]) else []
# 중복 묶기
g=collections.defaultdict(list)
for x in d: g[x["md5"]].append(x)
for x in d: x["dup_count"]=len(g[x["md5"]]); x["dup_group"]=x["md5"][:10] if len(g[x["md5"]])>1 else ""
json.dump(d,open("catalog.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
# 고유 효과음(10초 이하, 대표=첫 경로)
uniq={}
for x in d:
    if x["kind"]=="효과음" and x["dur"] is not None and not x["long_bgm"] and x["md5"] not in uniq: uniq[x["md5"]]=x
U=list(uniq.values())
L=[]; A=L.append
tot=sum(x["size"] for x in d)
A("# PC 효과음 전수 조사 (2026-10-06)\n")
A(f"- 검사 범위: C:/Users/TheRose 전체(제외: .tracks·node_modules·.git·mix_jobs·meme_pack·브라우저 캐시·Temp·Packages). **D: 드라이브는 연결 안 됨(드라이브 비어 있음) → 미검사**")
A(f"- 찾은 소리 파일 {len(d)}개 / {tot/2**20:.0f}MB. 종류: "+", ".join(f"{k} {v}" for k,v in collections.Counter(x['kind'] for x in d).items()))
A(f"- 효과음 중 10초 초과(배경음) {sum(1 for x in d if x['kind']=='효과음' and x['long_bgm'])}개 · 길이 못 읽음 {sum(1 for x in d if x['dur'] is None)}개")
A(f"- 같은 소리(md5) 중복: 묶음 {sum(1 for v in g.values() if len(v)>1)}개, 중복 사본 {sum(len(v)-1 for v in g.values())}개")
A(f"- **고유 효과음(10초 이하, 중복 제거) {len(U)}개 / {sum(x['size'] for x in U)/2**20:.1f}MB**\n")
A("## 분류별 개수(고유 효과음 기준)\n")
cc=collections.Counter(x["category"] for x in U)
for c,_ in CATS+[("기타","")]:
    xs=sorted([x for x in U if x["category"]==c],key=lambda x:-x["dup_count"])
    A(f"### {c} — {cc[c]}개")
    for x in xs[:5]: A(f"- `{x['path']}` ({x['dur']}초, {x['source']})")
    A("")
A("## 감정짤 짝 후보 (이 짤 감정엔 이 소리)\n")
A("| 감정짤 | 후보 수 | 대표 후보 |"); A("|---|---|---|")
mm={m:[x for x in U if m in x["meme"]] for m in MEMEKW}
for m,xs in mm.items(): A(f"| {m} | {len(xs)} | "+" · ".join(f"{x['folder']}/{x['name']}" for x in xs[:4])+" |")
A("\n## 출처별(고유 효과음)\n")
for k,v in collections.Counter(x["source"] for x in U).most_common(): A(f"- {k}: {v}")
A("\n## 기존 숏템메이커 효과음팩\n- `shopping_shorts/assets/sfx_packs/팩01~21` (7칸: 오프너·뽁·둥·띠링·휙·틱·딸깍2, wav). 구성표 `packs.json`. 만든 도구 `tools/sfx_bench/packs.py`.")
A("- 원재료: 바탕화면 `효과음 종합`(두둥.mp3·챙.mp3·뽁소리 등) + mixkit 추정 `NNNN-preview.mp3` + 합성(둥합성_*Hz) + 음높이 변형. 중간 산출물 `바탕화면/이븐쇼핑_효과음_벤치마크/3_효과음팩`. 팩21=사장님 고른 팩.")
A("- 핸드오프 기록상 `효과음 종합` 라이선스는 **미확인**(handoff/효과음배치.md).")
open("요약.md","w",encoding="utf-8").write("\n".join(L))
# 복사
base="meme_sfx"
if os.path.isdir(base): shutil.rmtree(base)
n=0
for m,xs in mm.items():
    os.makedirs(os.path.join(base,m),exist_ok=True)
    for x in xs:
        dst=os.path.join(base,m,x["folder"][:20]+"__"+x["name"])
        shutil.copy2(x["path"],dst); n+=1
print("uniq",len(U),cc,{m:len(v) for m,v in mm.items()},"copied",n)
