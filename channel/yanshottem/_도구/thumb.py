"""thumb.py OUT FINAL T_BASE SRC SS x,y,w,h — 영상 그 순간 화면(제목 띠·출처)을 바탕으로, 창(0,420,1080,1080)만 원본 깨끗한 프레임으로 갈아 끼운 썸네일."""
import io, subprocess, sys
from PIL import Image

out, final, tb, src, ss, crop = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], float(sys.argv[5]), [int(v) for v in sys.argv[6].split(",")]


def grab(v, t, vf=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", v, "-frames:v", "1"] + (["-vf", vf] if vf else []) + ["-f", "image2pipe", "-vcodec", "png", "-"]
    return Image.open(io.BytesIO(subprocess.run(cmd, capture_output=True, check=True).stdout)).convert("RGB")


base = grab(final, tb)
assert base.size == (1080, 1920), base.size
x, y, w, h = crop
win = grab(src, ss, f"crop={w}:{h}:{x}:{y},scale=1080:1080:flags=lanczos")
base.paste(win, (0, 420))
base.save(out, quality=95)
print(out)
