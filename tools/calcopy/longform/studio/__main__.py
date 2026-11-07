# 사용: python -X utf8 -m studio schedule | bake [구간수] | still <초...> | finish
import sys
from .sound import make_soundtrack
from .timing import make_schedule
from .output import *


def main():
    a = sys.argv[1:] or ["schedule"]
    if a[0] == "schedule":
        make_soundtrack(make_schedule())
    elif a[0] == "bake":
        bake_all(int(a[1]) if len(a) > 1 else 6)
    elif a[0] == "part":
        bake_range(out=a[3], frames=(int(a[1]), int(a[2])))
    elif a[0] == "still":
        for ts in a[1:]:
            t = float(ts); p = os.path.join(BUILD, f"still_{t:.1f}")
            bake_range(t, t + 1 / FPS, p + ".mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", p + ".mp4", "-frames:v", "1", p + ".png"], check=True); os.remove(p + ".mp4")
    elif a[0] == "finish":
        finish_file()


main()
