import sys,subprocess,pathlib
from playwright.sync_api import sync_playwright
speed=float(sys.argv[1]); out=sys.argv[2]; FPS=30
p=pathlib.Path("replay.html").resolve().as_uri()
ff=subprocess.Popen(["ffmpeg","-v","error","-y","-f","image2pipe","-framerate",str(FPS),"-c:v","mjpeg","-i","-","-c:v","libx264","-crf","16","-preset","medium","-pix_fmt","yuv420p","-movflags","+faststart",out],stdin=subprocess.PIPE)
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page(viewport={"width":1920,"height":1080})
    pg.goto(p); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(800)
    print("fonts",pg.evaluate("[document.fonts.check('20px \"IBM Plex Sans KR\"'),document.fonts.check('20px \"JetBrains Mono\"')]"))
    i=0; tail=None
    while True:
        done=pg.evaluate(f"window.RENDER({i/FPS},{speed})")
        ff.stdin.write(pg.screenshot(type="jpeg",quality=95)); i+=1
        if done and tail is None: tail=i+FPS*3
        if tail and i>=tail: break
    b.close()
ff.stdin.close(); ff.wait(); print("frames",i)
