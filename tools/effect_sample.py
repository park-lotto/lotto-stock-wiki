# -*- coding: utf-8 -*-
"""화면 효과 후보를 **한 편의 영상으로 만들어 눈으로 고르게** 한다 (2026-09-24).

사장님 지시 — "전환이나 줌·확대·강조 같은 것들을 자연스럽게 하는 게 중요하니 샘플을 만들어
렌더해서 바탕화면에". 글로 설명하면 판단이 안 된다. 같은 재료에 효과만 하나씩 바꿔 이어붙여
무엇이 자연스러운지 보고 고른다.

효과는 전부 ffmpeg 필터다 — 새 기술이 아니라 지금 렌더가 쓰는 것과 같은 방식이고,
AI 생성과 달리 매번 똑같이 나온다.

    py tools/effect_sample.py <원본.mp4> -o <결과.mp4> [--seg 2.0]
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

W, H, FPS = 720, 1280, 30   # 샘플은 눈으로 고르는 용도 — 720p면 충분하고 렌더가 빠르다
FONT = Path(__file__).resolve().parents[1] / "shopping_shorts" / "assets" / "NanumGothic.ttf"

# 켄번즈는 zoompan이 프레임 번호(on)로 도는 필터다. 지금 렌더도 이 방식을 쓴다.
def _zp(z_expr, d):
    """zoompan 한 줄. 확대 전에 여유를 두고 키워야 크롭 여백이 남는다(현재 렌더와 같은 수법)."""
    return (f"scale={int(W*1.35)}:{int(H*1.35)},"
            f"zoompan=z='{z_expr}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}")


def effects(d):
    """(이름, 설명, 필터) — d = 조각 길이(초). n = 그 조각의 프레임 수."""
    n = int(d * FPS)
    return [
        ("없음", "지금 대부분의 칸 (정지)", "null"),
        ("켄번즈", "지금 훅·반전 칸에만 (1.10배 서서히)", _zp(f"min(1+{0.10/n:.6f}*on,1.10)", d)),
        ("천천히 밀기", "1.18배까지 — 켄번즈보다 눈에 보이게", _zp(f"min(1+{0.18/n:.6f}*on,1.18)", d)),
        ("천천히 빠지기", "1.22배에서 원래대로 (마무리·정리)", _zp(f"max(1.22-{0.22/n:.6f}*on,1.0)", d)),
        ("급속 줌인", "0.25초 만에 1.3배로 훅 들어가 멈춤", _zp("min(1+0.04*on,1.30)", d)),
        ("펀치 줌", "확 커졌다 바로 돌아옴 (강조 한 방)", _zp("if(lt(on,7),1+0.035*on,max(1.0,1.245-0.02*(on-7)))", d)),
        ("클로즈업→공개", "1.5배에서 쭉 빠지며 전체가 드러남", _zp(f"max(1.5-{0.5/n:.6f}*on,1.0)", d)),
        ("손떨림", "들고 찍은 느낌 (긴장·다급함)",
         f"scale={int(W*1.12)}:{int(H*1.12)},crop={W}:{H}:"
         f"'(iw-ow)/2+14*sin(3.4*t*6.283)':'(ih-oh)/2+11*sin(2.1*t*6.283+1)'"),
        ("살짝 기울임", "1.2도 — 불안·긴장 (과하면 멀미)",
         f"scale={int(W*1.12)}:{int(H*1.12)},rotate=0.021:c=none,crop={W}:{H}"),
        ("밝기 펌프", "0.3초에 확 밝아졌다 돌아옴 (발견·공개)",
         "eq=brightness='0.22*exp(-pow(t-0.3,2)/0.012)':eval=frame"),
        ("비네팅", "가장자리를 어둡게 — 가운데로 시선", "vignette=PI/4.2"),
        ("위에서 떨어짐", "화면이 위에서 내려와 튕김 (등장·가격)",
         f"scale={int(W*1.06)}:{int(H*1.06)},crop={W}:{H}:'(iw-ow)/2':"
         f"'clip((ih-oh)/2 - 420*max(0,1-t/0.42)*cos(min(t,0.42)*7.5), 0, ih-oh)'"),
        ("옆에서 들어옴", "화면이 오른쪽에서 밀려 들어옴 (전환)",
         f"scale={int(W*1.06)}:{int(H*1.06)},crop={W}:{H}:"
         f"'clip((iw-ow)/2 + 520*max(0,1-t/0.38), 0, iw-ow)':'(ih-oh)/2'"),
        # ★'가운데서 열기'는 뺐다(2026-09-24 실측): crop의 폭엔 t를 못 쓰고, drawbox의 w는
        #   t를 줘도 프레임마다 다시 안 재서 화면이 통째로 검게 나왔다. 대신 실제로 되는 슬로모션을 둔다.
        ("슬로모션", "0.7배속으로 천천히 — 중요한 순간 늘리기", "setpts=1.43*PTS"),
        ("멈춤", "1.2초 뒤 탁 멈춤 (반전 직전)",
         f"trim=0:1.2,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={max(0.1,d-1.2):.2f}"),
    ]


def build(src, out, seg, starts, still_at=None):
    src = Path(src).resolve()        # cwd를 tmp로 바꾸므로 입력은 절대경로여야 한다
    fx = effects(seg)
    parts, labels = [], []
    tmp = Path(out).parent / "_fx_parts"
    tmp.mkdir(parents=True, exist_ok=True)
    # ★폰트는 파일명으로만 부른다(2026-09-24 실측): 윈도우 절대경로의 'C:'를 ffmpeg 필터가
    #   옵션 구분자로 읽어 drawtext가 통째로 깨졌다. tmp로 복사하고 cwd를 tmp로 둔다.
    shutil.copy(FONT, tmp / "f.ttf")
    font = "f.ttf"
    stillpng = None
    if still_at is not None:
        stillpng = tmp / "still.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{still_at:.2f}", "-i", str(src),
                        "-frames:v", "1", str(stillpng)], check=True, stdin=subprocess.DEVNULL)
        # 시간 흐름이 있어야 뜻이 있는 효과는 정지 사진에선 뺀다
        fx = [e for e in fx if e[0] not in ("슬로모션", "멈춤")]
    for i, (name, desc, f) in enumerate(fx):
        st = starts[i % len(starts)]
        p = tmp / f"p{i:02d}.mp4"
        label = f"{i+1}. {name}"
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},{f},"
              f"drawtext=fontfile={font}:text='{label}':"
              f"fontsize=62:fontcolor=white:borderw=5:bordercolor=black@0.85:x=(w-tw)/2:y=h-250,"
              f"drawtext=fontfile={font}:text='{desc}':"
              f"fontsize=40:fontcolor=white:borderw=4:bordercolor=black@0.85:x=(w-tw)/2:y=h-165,"
              f"format=yuv420p")
        if stillpng is not None:
            cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", "still.png"]
        else:
            cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{st:.2f}", "-i", str(src)]
        cmd += ["-vf", vf, "-t", f"{seg:.2f}", "-r", str(FPS), "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(p)]
        r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, cwd=str(tmp))
        if r.returncode != 0 or not p.exists():
            print(f"  [실패] {label}: {r.stderr.decode('utf-8','replace')[:160]}")
            continue
        parts.append(p)
        labels.append(label)
        print(f"  [ok] {label}")
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(out)], check=True, stdin=subprocess.DEVNULL)
    return labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--seg", type=float, default=2.0)
    ap.add_argument("--starts", default="1.5,6.0,10.5,15.0,19.0")
    ap.add_argument("--still", type=float, default=None,
                    help="이 시각의 정지 사진 한 장으로 만든다 — 효과만 보이게(원본 움직임 배제)")
    a = ap.parse_args()
    starts = [float(x) for x in a.starts.split(",")]
    labels = build(a.src, a.out, a.seg, starts, still_at=a.still)
    print(f"\n{len(labels)}개 효과 · {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
