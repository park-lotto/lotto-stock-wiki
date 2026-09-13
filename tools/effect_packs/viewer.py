"""library/ → library/index.html 뷰어 (폰트 라이브러리처럼 카테고리별로 훑어보기).

- 이미지(png/jpg/webp): 썸네일 PNG
- 영상(mov/mp4/webm): 회색 바탕에 알파를 합성한 3초짜리 mp4 미리보기(마우스 올리면 재생) + 첫 프레임 썸네일
- 음원(mp3/wav): <audio> 로 바로 재생
썸네일은 library/_thumbs/<팩id>/ 에 캐시한다(있으면 다시 안 만든다).
쓰는 법: py tools/effect_packs/viewer.py <library 폴더> [--open]
"""
import html, json, os, subprocess, sys, hashlib, concurrent.futures as cf

LIB = os.path.abspath(sys.argv[1])
THUMB = os.path.join(LIB, "_thumbs")
IMG = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VID = {".mov", ".mp4", ".webm"}
AUD = {".mp3", ".wav", ".ogg"}
MOGRT = {".mogrt"}   # 프리미어 모션그래픽 템플릿 = zip(thumb.png·thumb.mp4 내장) → 그걸로 미리보기
SIZE = 240


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).returncode == 0


def make_previews(pack_dir, pack_id, f):
    src = os.path.join(pack_dir, f["file"])
    key = hashlib.md5(f["file"].encode("utf-8")).hexdigest()[:10]
    outdir = os.path.join(THUMB, pack_id)
    os.makedirs(outdir, exist_ok=True)
    ext = f["ext"]
    thumb = os.path.join(outdir, key + ".png")
    prev = os.path.join(outdir, key + ".mp4")
    # 알파는 회색 바탕에 합성해서 보이게(검정 바탕이면 검은 글자 소스가 안 보인다)
    comp = f"[0:v]scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease,format=rgba[f];color=c=0x8c8c8c:s={SIZE}x{SIZE}:d=1[bg];[bg][f]overlay=(W-w)/2:(H-h)/2:shortest=1,format=rgb24"
    if ext in IMG and not os.path.exists(thumb):
        # ★정지 이미지는 PIL로 합성한다 — ffmpeg overlay+shortest=1은 단일 프레임 입력에서
        #   배경만 있는 첫 프레임을 내보내 회색 빈 썸네일이 됐다(실측 355장 중 71장)
        try:
            from PIL import Image
            im = Image.open(src).convert("RGBA")
            im.thumbnail((SIZE, SIZE))
            bg = Image.new("RGBA", (SIZE, SIZE), (140, 140, 140, 255))
            bg.alpha_composite(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2))
            bg.convert("RGB").save(thumb)
        except Exception as e:
            print("  이미지 썸네일 실패", src, e)
    if ext in VID:
        if not os.path.exists(thumb):
            # 포스터는 길이의 40% 지점 — 알파 애니메이션은 첫 0.5초가 빈 화면인 게 많다(실측 71장 회색)
            ss = max(0.3, float(f.get("dur") or 1.0) * 0.4)
            # ★-frames:v 3 + -update 1 = 마지막(3번째) 프레임을 남긴다. overlay는 영상 프레임이
            #   배경(color)보다 늦게 도착하면 첫 출력이 배경만이라, 1프레임만 뽑으면 회색 빈 칸이 된다
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.2f}", "-i", src, "-filter_complex", comp, "-frames:v", "3", "-update", "1", thumb])
        if not os.path.exists(prev):
            comp_v = f"[0:v]scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease,format=rgba[f];color=c=0x8c8c8c:s={SIZE}x{SIZE}[bg];[bg][f]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p"
            run(["ffmpeg", "-v", "error", "-y", "-t", "3", "-i", src, "-filter_complex", comp_v, "-r", "15", "-c:v", "libx264",
                 "-preset", "veryfast", "-crf", "28", "-an", prev])
    if ext in MOGRT and not (os.path.exists(thumb) and os.path.exists(prev)):
        try:
            import zipfile, tempfile
            with zipfile.ZipFile(src) as z:
                names = z.namelist()
                if "thumb.png" in names and not os.path.exists(thumb):
                    from PIL import Image
                    im = Image.open(z.open("thumb.png")).convert("RGBA"); im.thumbnail((SIZE, SIZE))
                    bg = Image.new("RGBA", (SIZE, SIZE), (140, 140, 140, 255)); bg.alpha_composite(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2)); bg.convert("RGB").save(thumb)
                if "thumb.mp4" in names and not os.path.exists(prev):
                    tmp = os.path.join(outdir, key + "_src.mp4")
                    open(tmp, "wb").write(z.read("thumb.mp4"))
                    run(["ffmpeg", "-v", "error", "-y", "-t", "3", "-i", tmp, "-vf", f"scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease,pad={SIZE}:{SIZE}:(ow-iw)/2:(oh-ih)/2:color=0x8c8c8c,format=yuv420p", "-r", "15", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-an", prev])
                    os.remove(tmp)
        except Exception as e:
            print("  mogrt 미리보기 실패", src, e)
    rel = lambda p: os.path.relpath(p, LIB).replace("\\", "/") if os.path.exists(p) else None
    return {"thumb": rel(thumb), "prev": rel(prev), "src": os.path.relpath(src, LIB).replace("\\", "/")}


def main():
    lib = json.load(open(os.path.join(LIB, "library.json"), encoding="utf-8"))
    cats = lib["categories"]
    packs = []
    jobs = []
    for p in lib["packs"]:
        pd = os.path.join(LIB, p["category"], p["id"])
        pj = json.load(open(os.path.join(pd, "pack.json"), encoding="utf-8"))
        files = [f for f in pj["inventory"] if f["ext"] in IMG | VID | AUD | MOGRT]
        # 그린스크린 mp4는 알파 mov와 짝이라 미리보기에선 mov를 우선(중복 줄이기)
        files.sort(key=lambda f: (0 if f["ext"] in (".mov", ".mogrt") else 1 if f["ext"] in IMG else 2, f["file"]))
        p2 = dict(p, file_list=files, dir=pd)
        packs.append(p2)
        for f in files:
            jobs.append((pd, p["id"], f))
    print("preview jobs", len(jobs), flush=True)
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda j: make_previews(*j), jobs))
    r_i = 0
    for p in packs:
        for f in p["file_list"]:
            f["pv"] = res[r_i]; r_i += 1

    by = {}
    for p in packs:
        by.setdefault(p["category"], []).append(p)
    n_files = sum(len(p["file_list"]) for p in packs)
    css = """
    body{font-family:Pretendard,'Malgun Gothic',sans-serif;background:#111;color:#eee;margin:0;padding:16px}
    h1{font-size:22px;margin:0 0 6px} .sub{color:#999;font-size:13px;margin-bottom:14px}
    nav a{display:inline-block;margin:0 8px 8px 0;padding:6px 10px;background:#222;border-radius:6px;color:#ddd;text-decoration:none;font-size:13px}
    h2{font-size:18px;margin:26px 0 10px;border-bottom:1px solid #333;padding-bottom:6px}
    .pack{background:#1a1a1a;border-radius:10px;padding:12px;margin-bottom:14px}
    .pack .t{font-weight:700;font-size:15px}
    .pack .cover{float:right;width:160px;height:90px;object-fit:cover;border-radius:6px;margin:0 0 6px 10px;background:#333} .pack .m{color:#9ab;font-size:12px;margin:4px 0 8px}
    .lic{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;margin-right:6px}
    .lic.ok{background:#1e4d2b} .lic.attr{background:#4d3f1e} .lic.no{background:#4d1e1e} .lic.unk{background:#333}
    .grid{display:flex;flex-wrap:wrap;gap:8px}
    .cell{width:%dpx;background:#222;border-radius:6px;overflow:hidden;position:relative}
    .cell img,.cell video{width:%dpx;height:%dpx;display:block;object-fit:contain;background:#8c8c8c}
    .cell .n{font-size:10px;color:#aaa;padding:3px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .cell .b{position:absolute;top:4px;left:4px;font-size:10px;padding:1px 5px;border-radius:3px;background:#000a}
    .aud{width:%dpx;padding:6px;font-size:11px} .aud audio{width:100%%;height:28px}
    details summary{cursor:pointer;color:#8cf;font-size:12px}
    """ % (SIZE, SIZE, SIZE, SIZE * 2)
    out = [f"<!doctype html><meta charset='utf-8'><title>효과팩 라이브러리</title><style>{css}</style>",
           f"<h1>효과팩 라이브러리 (2026-09-13)</h1><div class='sub'>{len(packs)}팩 · 미리보기 {n_files}개 · 영상은 마우스를 올리면 재생 · 출처·라이선스는 팩마다 표시</div><nav>"]
    for c, L in by.items():
        out.append(f"<a href='#{c}'>{html.escape(cats.get(c, c))} ({len(L)})</a>")
    out.append("</nav>")
    for c, L in by.items():
        out.append(f"<h2 id='{c}'>{html.escape(cats.get(c, c))} <span style='color:#777;font-size:13px'>{c}</span></h2>")
        for p in sorted(L, key=lambda x: -(x["views"] or 0)):
            lic = p["license"]
            cls = "ok" if "표기불요" in lic else "attr" if "출처표기" in lic else "no" if "비상업" in lic else "unk"
            enc = f" · 🔒 비번 zip {len(p['encrypted_zips'])}개" if p.get("encrypted_zips") else ""
            vid = p["source_url"].split("v=")[-1]
            cover = f"<a href='{p['source_url']}' target='_blank'><img class='cover' src='https://i.ytimg.com/vi/{vid}/mqdefault.jpg' loading='lazy'></a>"
            out.append(f"<div class='pack'>{cover}<div class='t'>{html.escape(p['name'])}</div>"
                       f"<div class='m'><span class='lic {cls}'>{html.escape(lic)}</span>{html.escape(p['channel'] or '')} · 조회 {p['views']:,} · "
                       f"파일 {p['files']} (알파 {p['alpha_files']}) · {round(p['bytes']/1e6)}MB{enc} · <a href='{p['source_url']}' target='_blank' style='color:#8cf'>원본 영상</a> · "
                       f"<a href='file:///{html.escape(p['dir'].replace(chr(92), '/'))}' style='color:#8cf'>폴더</a></div>")
            if p["license_lines"]:
                out.append("<details><summary>라이선스 문구(설명란 원문)</summary><pre style='font-size:11px;color:#bbb;white-space:pre-wrap'>" + html.escape("\n".join(p["license_lines"])) + "</pre></details>")
            out.append("<div class='grid'>")
            for f in p["file_list"][:60]:
                pv = f["pv"]; name = os.path.basename(f["file"])
                if f["ext"] in AUD:
                    out.append(f"<div class='aud'>🔊 {html.escape(name)}<audio controls preload='none' src='{html.escape(pv['src'])}'></audio></div>")
                elif f["ext"] in VID | MOGRT and pv.get("prev"):
                    badge = "mogrt" if f["ext"] in MOGRT else ("α" if f.get("alpha") else "mp4")
                    out.append(f"<div class='cell'><video muted loop preload='none' poster='{pv['thumb'] or ''}' src='{pv['prev']}' onmouseover='this.play()' onmouseout='this.pause()'></video><span class='b'>{badge} {f.get('w','')}×{f.get('h','')}</span><div class='n' title='{html.escape(name)}'>{html.escape(name)}</div></div>")
                elif pv.get("thumb"):
                    out.append(f"<div class='cell'><img loading='lazy' src='{pv['thumb']}'><span class='b'>{f['ext'][1:]} {f.get('w','')}×{f.get('h','')}</span><div class='n' title='{html.escape(name)}'>{html.escape(name)}</div></div>")
            if len(p["file_list"]) > 60:
                out.append(f"<div class='aud'>… 외 {len(p['file_list'])-60}개 (폴더에서 보기)</div>")
            out.append("</div></div>")
    path = os.path.join(LIB, "index.html")
    open(path, "w", encoding="utf-8").write("\n".join(out))
    print("viewer:", path, "packs", len(packs), "previews", n_files)
    if "--open" in sys.argv:
        os.startfile(path)


if __name__ == "__main__":
    main()
