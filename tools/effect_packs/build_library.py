"""raw/<id>_<채널>/ 다운로드 → library/<카테고리>/<pack_id>/ 로 정리 + library.json 카탈로그.

폰트 라이브러리(static/fonts + fonts.json)와 같은 꼴: 파일 폴더 + 카탈로그 한 벌.
- zip은 전부 푼다(중첩 포함). 파일마다 종류·해상도·길이·알파 여부(ffprobe)를 잰다
- 카테고리는 catalog.json의 분류 + 제목 키워드로 정한다
- pack.json(팩 단위) + library.json(전체) 두 층. 라이선스 문구·출처 영상은 그대로 실어 둔다
"""
import json, os, re, shutil, subprocess, sys, zipfile, hashlib

RAW, LIB, CAT = sys.argv[1], sys.argv[2], sys.argv[3]
catalog = {r["id"]: r for r in json.load(open(CAT, encoding="utf-8"))}
# zip 비밀번호: 배포자가 영상 안에 표시한 것을 사장님이 알려준 값. {"채널명 일부 또는 *": ["비번", ...]}
PW_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zip_passwords.json")
PASSWORDS = json.load(open(PW_FILE, encoding="utf-8")) if os.path.exists(PW_FILE) else {}


def pw_candidates(channel):
    out = []
    for k, v in PASSWORDS.items():
        if k == "*" or (channel and k in channel):
            out += v
    return out

CATEGORIES = [  # (폴더, 한글, 제목 키워드)
    ("arrows_highlights", "화살표·강조", r"화살표|arrow|형광|highlight|marker|마커|체크|check|underline|circle|동그라미"),
    ("captions_bars_frames", "자막바·프레임", r"자막바|subtitle box|subtitles box|frame|프레임|테두리|border|lace|장식|스케치북"),
    ("stickers_emoji", "스티커·이모티콘", r"스티커|sticker|이모티콘|emoji|emoticon|말풍선|speech|bubble|notepaper|메모|paper"),
    ("variety_fx", "예능효과", r"예능|웃음|laugh|lol|ㅋㅋ|깜짝|빵터|해골|skull|물음표|question|느낌표|팡팡|뽕뽕|펑펑"),
    ("transitions", "전환", r"트랜지션|transition|화면전환|swipe|liquid|brush"),
    ("particles_fx", "파티클·반짝", r"반짝|twinkle|sparkl|particle|파티클|불효과|fire|연기|smoke|glitter|빛"),
    ("cta_ui", "구독·CTA·UI", r"구독|subscribe|like|알람|loading|로딩|buffering|rec\b|녹화|뷰파인더|progress|bar"),
    ("memes", "밈·짤", r"밈|짤|meme|troll|reaction"),
    ("sfx", "효과음", r"효과음|sound effect|sfx|sound"),
    ("bgm", "배경음악", r"브금|bgm|배경음악|music"),
    ("backgrounds", "배경", r"배경|background|paper background|종이"),
    ("luts", "LUT·색보정", r"\blut|색보정"),
    ("caption_templates", "자막 템플릿(편집프로그램용)", r"자막|caption|subtitle|title|text|타이핑|typing|모션 자막|mogrt|프리셋|preset|lower third|로워"),
    ("intro_outro", "인트로·아웃트로", r"인트로|intro|outro|최종화면|end screen"),
    ("misc", "기타", r"."),
]
DIRECT = {".mov", ".png", ".mp4", ".gif", ".webm", ".mp3", ".wav", ".ogg", ".jpg", ".jpeg", ".webp", ".cube"}
TOOL = {".mogrt": "premiere", ".prproj": "premiere", ".prfpset": "premiere", ".aep": "ae", ".ffx": "ae", ".drfx": "davinci",
        ".setting": "davinci", ".motn": "fcp", ".moti": "fcp", ".psd": "photoshop", ".ai": "illustrator", ".ttf": "font", ".otf": "font"}


def category_for(r):
    # 제목이 먼저(구체적) → 카탈로그 분류(넓음)는 폴백. 순서를 바꾸면 '프레임' 같은 넓은 말이 다 먹는다
    for text in ((r["title"] or ""), (r.get("category") or "")):
        for folder, ko, kw in CATEGORIES[:-1]:
            if re.search(kw, text, re.I):
                return folder, ko
    return "misc", "기타"


def unzip_all(root, passwords=()):
    n = 0
    for _ in range(3):  # 중첩 zip
        # 이전에 비번 걸려 .ENCRYPTED 로 남긴 것도 비번이 생겼으면 다시 시도
        for d, _, fs in os.walk(root):
            for f in fs:
                if f.lower().endswith(".zip.encrypted") and passwords:
                    os.rename(os.path.join(d, f), os.path.join(d, f[:-len(".ENCRYPTED")]))
        zips = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs if f.lower().endswith(".zip")]
        if not zips:
            break
        for z in zips:
            out = z[:-4]
            try:
                with zipfile.ZipFile(z) as zf:
                    pwd = None
                    enc = [i for i in zf.infolist() if i.flag_bits & 0x1 and not i.is_dir()]
                    if enc:
                        for cand in passwords:
                            try:
                                zf.open(enc[0], pwd=cand.encode("utf-8")).read(16); pwd = cand.encode("utf-8"); break
                            except Exception:
                                continue
                        if pwd is None:
                            raise RuntimeError("password required (no match)")
                        zf.setpassword(pwd)
                    for info in zf.infolist():
                        # 한글 파일명(cp437로 잘못 읽힘) 복구
                        name = info.filename
                        try:
                            name = name.encode("cp437").decode("cp949")
                        except Exception:
                            pass
                        if info.is_dir() or "__MACOSX" in name or name.endswith(".DS_Store"):
                            continue
                        dst = os.path.join(out, name)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        with zf.open(info) as src, open(dst, "wb") as f:
                            shutil.copyfileobj(src, f)
                        n += 1
                os.remove(z)
            except RuntimeError as e:
                if "password" in str(e):
                    enc = z + ".ENCRYPTED"   # 비번 걸린 zip: 이름만 바꿔 남기고 다시 안 건드린다
                    if not os.path.exists(enc): os.rename(z, enc)
                    print("  zip 비번", os.path.basename(z))
                else:
                    print("  zip 실패", z, e)
            except Exception as e:
                print("  zip 실패", z, e)
    return n


def probe(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,pix_fmt,width,height,duration,nb_frames", "-of", "json", path],
                           capture_output=True, text=True, timeout=30)
        s = (json.loads(r.stdout).get("streams") or [{}])[0]
        pf = s.get("pix_fmt") or ""
        alpha = ("a" in pf.replace("yuv", "").replace("gray", "")) or s.get("codec_name") in ("qtrle", "png", "apng")
        return {"codec": s.get("codec_name"), "w": s.get("width"), "h": s.get("height"),
                "dur": round(float(s["duration"]), 2) if s.get("duration") else None, "alpha": bool(alpha)}
    except Exception:
        return {}


def main():
    lib = {"version": 1, "built": "2026-09-13", "root": LIB, "categories": {f: ko for f, ko, _ in CATEGORIES}, "packs": []}
    os.makedirs(LIB, exist_ok=True)
    for name in sorted(os.listdir(RAW)):
        src = os.path.join(RAW, name)
        if not os.path.isdir(src):
            continue
        vid = name[:11]   # 유튜브 id 11자(맨 앞이 _나 -일 수 있어 split 금지)
        r = catalog.get(vid)
        if not r:
            print("카탈로그에 없음", name); continue
        files_all = [f for d, _, fs in os.walk(src) for f in fs if f != "LICENSE_NOTE.txt"]
        if not files_all:
            print("빈 폴더(다운로드 실패)", name); continue
        folder, ko = category_for(r)
        pack_id = f"{vid}_{re.sub(r'[^\w가-힣]+', '_', (r['channel'] or '')[:20]).strip('_')}"
        dst = os.path.join(LIB, folder, pack_id)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        unzipped = unzip_all(dst, pw_candidates(r.get("channel") or ""))
        inv = []
        for d, _, fs in os.walk(dst):
            for f in fs:
                if f == "LICENSE_NOTE.txt" or f.endswith(".part"):
                    continue
                p = os.path.join(d, f); ext = os.path.splitext(f)[1].lower()
                e = {"file": os.path.relpath(p, dst).replace("\\", "/"), "ext": ext, "bytes": os.path.getsize(p),
                     "direct": ext in DIRECT, "tool": TOOL.get(ext)}
                if ext in (".mov", ".mp4", ".webm", ".gif", ".png", ".webp"):
                    e.update(probe(p))
                inv.append(e)
        exts = {}
        for e in inv: exts[e["ext"]] = exts.get(e["ext"], 0) + 1
        encrypted = [e["file"] for e in inv if e["file"].endswith(".ENCRYPTED")]
        pack = {"id": pack_id, "name": r["title"], "channel": r["channel"], "source_url": r["url"], "views": r["views"],
                "category": folder, "category_ko": ko, "license": r["license"], "license_lines": r.get("lic_lines") or [],
                "download_links": r["links"], "files": len(inv), "exts": exts,
                "direct_files": sum(1 for e in inv if e["direct"]), "alpha_files": sum(1 for e in inv if e.get("alpha")),
                "tools": sorted({e["tool"] for e in inv if e["tool"]}), "bytes": sum(e["bytes"] for e in inv),
                "encrypted_zips": encrypted,
                "inventory": inv}
        json.dump(pack, open(os.path.join(dst, "pack.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        lib["packs"].append({k: v for k, v in pack.items() if k != "inventory"})
        print(f"{folder:22s} {pack_id[:32]:32s} files={len(inv):4d} alpha={pack['alpha_files']:3d} {round(pack['bytes']/1e6):5d}MB unzipped={unzipped}")
    json.dump(lib, open(os.path.join(LIB, "library.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    by = {}
    for p in lib["packs"]:
        b = by.setdefault(p["category_ko"], [0, 0, 0]); b[0] += 1; b[1] += p["files"]; b[2] += p["bytes"]
    print("\n== 카테고리별 팩/파일/용량")
    for k, (n, f, b) in sorted(by.items()): print(f"  {k}: {n}팩 {f}파일 {round(b/1e6)}MB")


if __name__ == "__main__":
    main()
