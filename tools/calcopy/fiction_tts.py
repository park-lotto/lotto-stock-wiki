# -*- coding: utf-8 -*-
"""픽션 썰 결과(json) → 역할별 목소리로 녹음한 mp3 + 대본 txt. 결과를 손대지 않고 그대로 읽는다.
사용: PYTHONUTF8=1 py tools/calcopy/fiction_tts.py <결과.json> <출력 폴더> [접두어]
목소리: 나레 박창수 · 윗선 용식이(화남) · 실무자 김건. 속도 1.15. 키 = ~/.volcano/keys/typecast
"""
import json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from shopping_shorts.channelkit import providers

VOICES = {"NARR": "tc_6059dad0b83880769a50502f", "CHAR": "tc_5feb2085cca1a479e73bac37", "PUNCH": "tc_61c2f7741330d213c238cba6"}
ROLE = {"나레": "NARR", "윗선": "CHAR", "실무자": "PUNCH"}
EMO = {"윗선": ("angry", 1.3)}


def main():
    src, out_dir = sys.argv[1], sys.argv[2]
    prefix = sys.argv[3] if len(sys.argv) > 3 else ""
    os.makedirs(out_dir, exist_ok=True)
    synth = providers.typecast_synth(VOICES, tempo=1.15)
    rows = [r for r in json.load(open(src, encoding="utf-8")) if r.get("fit") and r.get("script")]
    for k, r in enumerate(rows, 1):
        sc = r["script"]
        seq = [("나레", sc.get("title") or "")] + [(L.get("speaker") or "나레", L["text"]) for L in sc.get("lines") or [] if (L.get("text") or "").strip()]
        tmp = os.path.join(out_dir, "_tmp%d" % k); os.makedirs(tmp, exist_ok=True)
        parts = []
        for i, (sp, t) in enumerate(seq):
            f = os.path.join(tmp, "%02d.mp3" % i)
            emo = EMO.get(sp, (None, None))
            synth(t, f, role=ROLE.get(sp, "NARR"), emotion=emo[0], intensity=emo[1])
            parts.append(f)
        lst = os.path.join(tmp, "list.txt")
        open(lst, "w", encoding="utf-8").write("".join("file '%s'\n" % p.replace("\\", "/") for p in parts))
        name = "%s%d_%s.mp3" % (prefix, k, r["product"].replace(" ", ""))
        dst = os.path.join(out_dir, name)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "libmp3lame", "-q:a", "3", dst], check=True)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", dst], capture_output=True, text=True).stdout.strip()
        open(dst.replace(".mp3", ".txt"), "w", encoding="utf-8").write("\n".join("[%s] %s" % (sp, t) for sp, t in seq))
        shutil.rmtree(tmp, ignore_errors=True)
        print(name, "%.1f초" % float(dur), "줄", len(seq))


if __name__ == "__main__":
    main()
