# -*- coding: utf-8 -*-
"""원본 소스(CHA 모션 키트 등) 찾기·메타 읽기 — 판단 주인 scan_sources (관제 244).

원본은 저장소 밖 폴더(MOGRAPH_REF_DIR)에만 둔다 — CHA 자료는 "개인 학습·콘텐츠 제작"만 허용이라
회원에게 재배포할 수 없다(라이선스 ref_only). 저장소에는 장부 레코드(메타)만 들어간다.
폴더가 없으면 빈 목록 — 장부는 그대로 읽히고 작업대 미리보기만 "원본 없음"으로 뜬다."""
import json
import os
import re
from pathlib import Path

_DEFAULT_REF_DIR = Path(r"C:\Users\TheRose\숏템자료\모션그래픽엔진\CHA")


def ref_dir():
    return Path(os.environ.get("MOGRAPH_REF_DIR") or _DEFAULT_REF_DIR)


# 팩 이름 → (조각 폴더가 있는 곳, brand 폴더) — ref_dir 기준 상대 경로
PACKS = {
    "cha-remix": ("remix-7-source", "remix-7-source/brand"),
    "cha-generative": ("generative-5-source", "generative-5-source/brand"),
    "cha-immersive": ("immersive-61-source/scripts/motion-kit/pieces", "immersive-61-source/scripts/motion-kit/brand"),
}

LICENSE_REF_ONLY = {"origin": "CHA(커리어해커 알렉스)", "status": "ref_only",
                    "note": "개인 학습·콘텐츠 제작만 허용 — 회원 재배포 금지, 기법을 참고해 우리 것으로 다시 짠다"}


def pack_dirs(pack):
    pieces, brand = PACKS[pack]
    return ref_dir() / pieces, ref_dir() / brand


def piece_dir(pack, slug):
    """조각 폴더(index.html·meta.json·prompt.md). 없으면 None."""
    if pack not in PACKS or not slug or "/" in slug or "\\" in slug or ".." in slug:
        return None
    d = pack_dirs(pack)[0] / slug
    return d if (d / "index.html").exists() else None


def brand_dir(pack):
    if pack not in PACKS:
        return None
    d = pack_dirs(pack)[1]
    return d if d.exists() else None


def scan_sources():
    """ref_dir 의 모든 팩을 훑어 부품 레코드 후보(list[dict])를 만든다. meta.json 값만 옮긴다(지어내지 않는다)."""
    out = []
    for pack in PACKS:
        pieces, _ = pack_dirs(pack)
        if not pieces.is_dir():
            continue
        for d in sorted(pieces.iterdir()):
            meta_p = d / "meta.json"
            if not (d / "index.html").exists() or not meta_p.exists():
                continue
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
            except Exception as e:      # noqa: BLE001 — 깨진 meta 는 건너뛰되 조용히 넘기지 않는다
                print("[mograph.sources] meta 읽기 실패 %s: %r" % (meta_p, e))
                continue
            size = meta.get("size") or [1080, 830]
            dur = float(meta.get("duration") or 0)
            out.append({
                "slug": meta.get("slug") or d.name,
                "kind": "scene",
                "label": meta.get("title_ko") or d.name,
                "group": meta.get("category") or "",
                "src": {"url": "https://careerhackeralex.com/sharings/cha-motion-kit", "pack": pack, "folder": d.name},
                "license": dict(LICENSE_REF_ONLY),
                "impl": {"runtime": "gsap+hyperframes", "pack": pack, "folder": d.name},
                "geometry": {"w": int(size[0]), "h": int(size[1])},
                "duration_ms": int(round(dur * 1000)),
                "ratio": "9:16" if size[1] > size[0] else "16:10",
                "ratio_variants": [],
                "vars": list(meta.get("vars") or []),
                "key_at": list(meta.get("key_at") or []),
                "uses": list(meta.get("uses") or []),
                "what": meta.get("what") or "",
                "how_to_use": meta.get("how_to_use") or "",
                "techniques": list(meta.get("techniques") or []),
            })
    return out


# ── JasonZhu 라이브러리(motion 분야 263편, 2026-10-20 내려받음) — 영상 권리는 제작자, ref_only ──
_DEFAULT_JZ_DIR = Path(r"C:\Users\TheRose\숏템자료\모션그래픽엔진\jasonzhu")
_JZ_ID = re.compile(r"^[0-9]{10,25}$")
_JZ_CACHE = {"mtime": None, "rows": []}


def jasonzhu_dir():
    return Path(os.environ.get("MOGRAPH_JZ_DIR") or _DEFAULT_JZ_DIR)


def jasonzhu_index():
    """motion/_index.json(조회순, 제작자·도구·prompt 메타) 그대로. 없으면 빈 목록. 파일 mtime 으로 캐시."""
    p = jasonzhu_dir() / "motion" / "_index.json"
    if not p.exists():
        return []
    mt = p.stat().st_mtime
    if _JZ_CACHE["mtime"] != mt:
        try:
            rows = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:      # noqa: BLE001
            print("[mograph.sources] jasonzhu _index.json 읽기 실패: %r" % e)
            rows = []
        _JZ_CACHE.update(mtime=mt, rows=[r for r in rows if _JZ_ID.match(str(r.get("id") or ""))])
    return _JZ_CACHE["rows"]


def jasonzhu_meta(ref_id):
    for r in jasonzhu_index():
        if str(r.get("id")) == ref_id:
            return r
    return None


def jasonzhu_video(ref_id):
    """받아진 mp4 경로(motion/<id>.mp4, 없으면 상위 작품 폴더 v/<id>.mp4). 없으면 None."""
    if not _JZ_ID.match(ref_id or ""):
        return None
    for p in (jasonzhu_dir() / "motion" / (ref_id + ".mp4"), jasonzhu_dir() / "v" / (ref_id + ".mp4")):
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def jasonzhu_prompt(ref_id):
    """프롬프트 본문(motion/<id>.prompt.txt). 없으면 None — 그때 역설계 대상이다."""
    if not _JZ_ID.match(ref_id or ""):
        return None
    p = jasonzhu_dir() / "motion" / (ref_id + ".prompt.txt")
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
