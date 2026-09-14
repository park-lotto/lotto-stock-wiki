"""받은 zip(`<id>.bin`)을 풀어 내용을 세고, 암호가 걸린 것은 표시만 한다.

★암호 걸린 zip은 건너뛴다 — 조PD 팩은 비번을 영상 끝에서 알려준다(사장님이 알려주셔야 함).
  09-13에도 8팩이 `.ENCRYPTED`로 남았다. 여기선 `_LOCKED.txt`를 남겨 눈에 보이게 한다.
★확장자별 개수를 찍는다 — 뭘 받았는지 사람이 바로 알아야 한다.
"""
import collections
import os
import sys
import zipfile


def main():
    root = sys.argv[1]
    pwd = None
    if "--pwd" in sys.argv:
        pwd = sys.argv[sys.argv.index("--pwd") + 1].encode()

    for d in sorted(os.listdir(root)):
        pack = os.path.join(root, d)
        if not os.path.isdir(pack):
            continue
        blobs = [f for f in os.listdir(pack) if f.endswith(".bin")]
        if not blobs:
            continue
        for b in blobs:
            src = os.path.join(pack, b)
            out = os.path.join(pack, "unpacked")
            if os.path.isdir(out) and os.listdir(out):
                kinds = collections.Counter()
                for r, _, fs in os.walk(out):
                    for f in fs:
                        kinds[os.path.splitext(f)[1].lower()] += 1
                print(f"{d:28} 이미풀림  {dict(kinds)}")
                continue
            try:
                z = zipfile.ZipFile(src)
            except zipfile.BadZipFile:
                print(f"{d:28} ZIP아님(수동확인)")
                continue
            enc = [i for i in z.infolist() if i.flag_bits & 0x1]
            if enc and not pwd:
                with open(os.path.join(pack, "_LOCKED.txt"), "w", encoding="utf-8") as fh:
                    fh.write(f"암호 걸린 항목 {len(enc)}/{len(z.infolist())}개 — "
                             f"비번은 원본 영상 끝부분에 표시된다.\n")
                names = [i.filename.split("/")[-1] for i in z.infolist() if not i.is_dir()]
                print(f"{d:28} 🔒암호 {len(enc)}개  예: {names[:3]}")
                continue
            os.makedirs(out, exist_ok=True)
            try:
                z.extractall(out, pwd=pwd)
            except RuntimeError as e:
                print(f"{d:28} 해제실패({str(e)[:40]})")
                continue
            kinds = collections.Counter()
            for r, _, fs in os.walk(out):
                for f in fs:
                    kinds[os.path.splitext(f)[1].lower()] += 1
            print(f"{d:28} 풀었다  {dict(kinds)}")


if __name__ == "__main__":
    main()
