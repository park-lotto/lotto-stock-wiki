# 배경음 내려받기 (Kevin MacLeod · incompetech.com · CC BY 4.0) → media/bgm/
# 사용: python -X utf8 get_bgm.py    
import os, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(HERE, "media", "bgm"); os.makedirs(OUT, exist_ok=True)
SONGS = ["Bass Walker", "Thinking Music", "Local Forecast", "Pamgaea"]
for name in SONGS:
    path = os.path.join(OUT, name.replace(" ", "_") + ".mp3")
    if os.path.exists(path) and os.path.getsize(path) > 500_000: print("있음", name); continue
    url = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/" + urllib.parse.quote(name) + ".mp3"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=120).read()
    if len(data) < 500_000: raise SystemExit(f"받기 실패: {name} ({url})")
    open(path, "wb").write(data); print(f"받음 {name} {len(data) / 1e6:.1f}MB")
print("설명란 크레딧: Music: " + ", ".join(f'"{s}"' for s in SONGS) +
      " Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/")
