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


def detect_crop(src, seconds=3):
    """여러 프레임에서 배경색과 다른 픽셀의 영역을 합쳐 crop 값을 만든다. (ffmpeg cropdetect는 어두운
    얇은 자막에서 음수 폭을 내 무효 — 2026-09-13 실측) 내용이 화면 60% 이상이면 None."""
    from PIL import Image, ImageChops
    tmpdir = src + "_cd"
    os.makedirs(tmpdir, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-t", str(seconds), "-i", src, "-vf", "fps=3", os.path.join(tmpdir, "f%02d.png")])
    frames = sorted(os.listdir(tmpdir))
    if not frames:
        return None
    x0 = y0 = 10 ** 9; x1 = y1 = -1; W = H = None
    for fn in frames:
        im = Image.open(os.path.join(tmpdir, fn)).convert("RGB"); W, H = im.size
        small = im.resize((64, 36)); bgc = max(small.getcolors(64 * 36), key=lambda c: c[0])[1]
        bb = ImageChops.difference(im, Image.new("RGB", im.size, bgc)).convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()
        if bb:
            x0, y0, x1, y1 = min(x0, bb[0]), min(y0, bb[1]), max(x1, bb[2]), max(y1, bb[3])
    import shutil as _sh; _sh.rmtree(tmpdir, ignore_errors=True)
    if x1 < 0 or (x1 - x0) * (y1 - y0) > W * H * 0.6:
        return None
    w, h = x1 - x0, y1 - y0
    mx, my = int(w * 0.20) + 8, int(h * 0.30) + 8
    cx0, cy0, cx1, cy1 = max(0, x0 - mx), max(0, y0 - my), min(W, x1 + mx), min(H, y1 + my)
    cw, ch = (cx1 - cx0) // 2 * 2, (cy1 - cy0) // 2 * 2   # 짝수
    if cw < 32 or ch < 16:
        return None
    return f"crop={cw}:{ch}:{cx0}:{cy0}"


def best_poster(mp4, out):
    """미리보기 mp4에서 여러 시점을 뽑아 밝은 내용이 가장 넓은 프레임을 포스터로 쓴다(빈 화면·글자 등장 전 방지)."""
    from PIL import Image
    best, best_area = None, -1
    for t in ("0.3", "0.8", "1.3", "1.9", "2.6", "3.4"):
        cand = out + f".{t}.png"
        run(["ffmpeg", "-v", "error", "-y", "-ss", t, "-i", mp4, "-frames:v", "1", "-update", "1", cand])
        if not os.path.exists(cand):
            continue
        im = Image.open(cand).convert("L"); bb = im.point(lambda v: 255 if v > 60 else 0).getbbox()
        area = (bb[2] - bb[0]) * (bb[3] - bb[1]) if bb else 0
        if area > best_area:
            if best and os.path.exists(best): os.remove(best)
            best, best_area = cand, area
        else:
            os.remove(cand)
    if best:
        os.replace(best, out)


def is_static(mp4):
    """미리보기 첫 프레임과 끝 프레임이 거의 같으면 정지형."""
    try:
        from PIL import Image, ImageChops, ImageStat
        a = mp4 + "_a.png"; b = mp4 + "_b.png"
        run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-frames:v", "1", "-update", "1", a])
        run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.3", "-i", mp4, "-frames:v", "1", "-update", "1", b])
        if not (os.path.exists(a) and os.path.exists(b)):
            return False
        d = ImageStat.Stat(ImageChops.difference(Image.open(a).convert("L"), Image.open(b).convert("L"))).mean[0]
        os.remove(a); os.remove(b)
        return d < 1.0
    except Exception:
        return False


def make_previews(pack_dir, pack_id, f):
    src = os.path.join(pack_dir, f["file"])
    key = hashlib.md5(f["file"].encode("utf-8")).hexdigest()[:10]
    outdir = os.path.join(THUMB, pack_id)
    os.makedirs(outdir, exist_ok=True)
    ext = f["ext"]
    thumb = os.path.join(outdir, key + ".png")
    prev = os.path.join(outdir, key + ".mp4")
    big = os.path.join(outdir, key + "_big.mp4")
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
            pass   # 포스터는 아래 prev 생성 뒤 best_poster 로 뽑는다
        if not os.path.exists(prev):
            comp_v = f"[0:v]scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease,format=rgba[f];color=c=0x8c8c8c:s={SIZE}x{SIZE}[bg];[bg][f]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p"
            run(["ffmpeg", "-v", "error", "-y", "-t", "3", "-i", src, "-filter_complex", comp_v, "-r", "15", "-c:v", "libx264",
                 "-preset", "veryfast", "-crf", "28", "-an", prev])
        if not os.path.exists(thumb) and os.path.exists(prev):
            best_poster(prev, thumb)
        if not os.path.exists(big):   # 크게 보기(라이트박스)용 — 원본 비율, 최대 960
            comp_b = f"[0:v]scale=960:960:force_original_aspect_ratio=decrease,format=rgba[f];color=c=0x8c8c8c:s=960x960[bg];[bg][f]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p"
            run(["ffmpeg", "-v", "error", "-y", "-t", "6", "-i", src, "-filter_complex", comp_b, "-r", "24", "-c:v", "libx264",
                 "-preset", "veryfast", "-crf", "24", "-an", big])
    if ext in MOGRT and not (os.path.exists(thumb) and os.path.exists(prev)):
        try:
            import zipfile
            from PIL import Image, ImageChops
            with zipfile.ZipFile(src) as z:
                names = z.namelist()
                W2, H2 = SIZE * 2, SIZE + (SIZE % 2)
                if "thumb.mp4" in names:
                    if not (os.path.exists(prev) and os.path.exists(big)):
                        tmp = os.path.join(outdir, key + "_src.mp4")
                        open(tmp, "wb").write(z.read("thumb.mp4"))
                        cr = detect_crop(tmp)   # 검은 화면 속 작은 자막 → 글자 영역만
                        pre = (cr + ",") if cr else ""
                        run(["ffmpeg", "-v", "error", "-y", "-t", "4", "-i", tmp, "-vf", f"{pre}scale={W2}:{H2}:force_original_aspect_ratio=decrease,pad={W2}:{H2}:(ow-iw)/2:(oh-ih)/2:color=0x222222,format=yuv420p", "-r", "15", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-an", prev])
                        # 크게 보기는 크롭 없이 원본 전체 화면 — 옆에서 들어오는 요소가 잘리지 않게
                        run(["ffmpeg", "-v", "error", "-y", "-t", "8", "-i", tmp, "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x222222,format=yuv420p", "-r", "24", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-an", big])
                        os.remove(tmp)
                    if not os.path.exists(thumb) and os.path.exists(prev):
                        best_poster(prev, thumb)   # ★영상이 있으면 포스터는 항상 영상(크롭본)에서 — thumb.png 는 작거나 비어 있는 게 많다
                if not os.path.exists(thumb) and "thumb.png" in names:
                    im = Image.open(z.open("thumb.png")).convert("RGB")
                    # 배경색(가장 흔한 색)과 다른 픽셀의 영역만 잘라 키운다 — 검정뿐 아니라 사진 배경도 대응
                    small = im.resize((64, 36)); bgc = max(small.getcolors(64 * 36), key=lambda c: c[0])[1]
                    diff = ImageChops.difference(im, Image.new("RGB", im.size, bgc)).convert("L").point(lambda v: 255 if v > 40 else 0)
                    bb = diff.getbbox()
                    if bb and (bb[2] - bb[0]) * (bb[3] - bb[1]) < im.width * im.height * 0.6:
                        mx, my = int((bb[2] - bb[0]) * 0.20) + 8, int((bb[3] - bb[1]) * 0.30) + 8
                        im = im.crop((max(0, bb[0] - mx), max(0, bb[1] - my), min(im.width, bb[2] + mx), min(im.height, bb[3] + my)))
                    im.thumbnail((W2, H2))
                    bg = Image.new("RGB", (W2, H2), (34, 34, 34)); bg.paste(im, ((W2 - im.width) // 2, (H2 - im.height) // 2)); bg.save(thumb)
        except Exception as e:
            print("  mogrt 미리보기 실패", src, e)
    rel = lambda p: os.path.relpath(p, LIB).replace("\\", "/") if os.path.exists(p) else None
    static = is_static(prev) if os.path.exists(prev) else False
    empty = False
    try:
        if os.path.exists(thumb):
            from PIL import Image
            empty = Image.open(thumb).convert("L").point(lambda v: 255 if v > 60 else 0).getbbox() is None
    except Exception:
        pass
    return {"thumb": rel(thumb), "prev": rel(prev), "big": rel(big), "static": static, "empty": empty, "wide": ext in MOGRT,
            "src": os.path.relpath(src, LIB).replace("\\", "/")}


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
    .cell.wide{width:%dpx} .cell.wide video,.cell.wide img{width:%dpx;height:%dpx}
    .cell{cursor:zoom-in}
    #lb{position:fixed;inset:0;background:#000d;display:none;align-items:center;justify-content:center;flex-direction:column;z-index:9}
    #lb video,#lb img{max-width:92vw;max-height:80vh;background:#222} #lb .cap{color:#ddd;font-size:13px;margin-top:8px}
    #lb .x{position:absolute;top:14px;right:22px;color:#fff;font-size:28px;cursor:pointer}
    .stat{position:absolute;top:4px;right:4px;font-size:10px;padding:1px 5px;border-radius:3px;background:#a33c}
    """ % (SIZE, SIZE, SIZE, SIZE * 2, SIZE * 2, SIZE * 2, SIZE)
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
            if p.get("encrypted_zips") and not p["file_list"]:
                out.append("<div style='color:#f9b;font-size:12px;margin:4px 0'>🔒 zip에 비밀번호가 걸려 있어 아직 못 풀었습니다 — 비번은 배포 영상 안에 표시됨. 원본 영상 링크에서 확인 후 알려주시면 풀어 넣겠습니다.</div>")
            out.append("<div class='grid'>")
            for f in p["file_list"][:60]:
                pv = f["pv"]; name = os.path.basename(f["file"])
                if f["ext"] in AUD:
                    out.append(f"<div class='aud'>🔊 {html.escape(name)}<audio controls preload='none' src='{html.escape(pv['src'])}'></audio></div>")
                elif f["ext"] in VID | MOGRT and pv.get("prev"):
                    badge = "mogrt" if f["ext"] in MOGRT else ("α" if f.get("alpha") else "mp4")
                    wide = " wide" if pv.get("wide") else ""
                    stat = "<span class='stat'>미리보기 빈 화면(제작자 파일)</span>" if pv.get("empty") else ("<span class='stat'>정지형</span>" if pv.get("static") else "")
                    bigsrc = pv.get("big") or pv["prev"]
                    out.append(f"<div class='cell{wide}' data-big='{html.escape(bigsrc)}' data-kind='video' data-name='{html.escape(name)}'><video class='pv' muted loop playsinline preload='metadata' poster='{pv['thumb'] or ''}' src='{pv['prev']}' title='클릭: 크게 보기'></video><span class='b'>{badge} {f.get('w','')}×{f.get('h','')}</span>{stat}<div class='n' title='{html.escape(name)}'>{html.escape(name)}</div></div>")
                elif pv.get("thumb"):
                    out.append(f"<div class='cell' data-big='{html.escape(pv['src'])}' data-kind='img' data-name='{html.escape(name)}'><img loading='lazy' src='{pv['thumb']}'><span class='b'>{f['ext'][1:]} {f.get('w','')}×{f.get('h','')}</span><div class='n' title='{html.escape(name)}'>{html.escape(name)}</div></div>")
            if len(p["file_list"]) > 60:
                out.append(f"<div class='aud'>… 외 {len(p['file_list'])-60}개 (폴더에서 보기)</div>")
            out.append("</div></div>")
    out.append("""<div id='lb'><span class='x'>&#10005;</span><div id='lbc'></div><div class='cap' id='lbcap'></div></div>
<script>
function openLB(src,kind,name){ const c=document.getElementById('lbc'); c.innerHTML = kind==='video' ? '<video src="'+src+'" controls autoplay loop muted playsinline></video>' : '<img src="'+src+'">'; document.getElementById('lbcap').textContent=name+'  (ESC 또는 바깥 클릭으로 닫기)'; document.getElementById('lb').style.display='flex'; }
function closeLB(){ document.getElementById('lb').style.display='none'; document.getElementById('lbc').innerHTML=''; }
document.getElementById('lb').addEventListener('click', e=>{ if(e.target.id==='lb'||e.target.className==='x') closeLB(); });
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeLB(); });
document.querySelectorAll('.cell[data-big]').forEach(c=>c.addEventListener('click',()=>openLB(c.dataset.big,c.dataset.kind,c.dataset.name)));
function togglePlay(v){ if(v.paused){ v.play().catch(()=>{}); } else { v.pause(); } }
const io = new IntersectionObserver(es => { es.forEach(e => { const v=e.target; if(e.isIntersecting){ v.play().catch(()=>{}); } else { v.pause(); } }); }, {threshold: 0.2});
document.querySelectorAll('video.pv').forEach(v => io.observe(v));
</script>""")
    path = os.path.join(LIB, "index.html")
    open(path, "w", encoding="utf-8").write("\n".join(out))
    print("viewer:", path, "packs", len(packs), "previews", n_files)
    if "--open" in sys.argv:
        os.startfile(path)


if __name__ == "__main__":
    main()
