"""프리셋 꾸러미 — 편마다 서버가 빌려주는 '완성 프리셋' 한 벌(관제 234 5판, 2026-10-19 사장님 "등급별 프리셋 / 노하우가 자산").

우리 PC 에서 엔진 트랙을 읽어 프리셋마다 꾸러미(zip)를 만든다. 서버는 이것을 보관만 하고, 편 시작 때 라이선스·등급·작업 권한을
확인한 뒤 그 편에 한 벌 내려준다(claude_portal.preset_pack). 고객 PC 는 엔진이 도는 동안만 풀어 두고 끝나면 지운다.

  py tools/claude_portal/preset_pack.py build --engine <엔진 폴더> --preset channel/<slug>/preset/<틀> --out <폴더>
  py tools/claude_portal/preset_pack.py list  --engine <엔진 폴더> --preset …        # 담길 파일만 보기

판단 주인(한 곳): files_for() — 엔진이 프리셋 하나로 영상을 만들 때 읽는 channel/ 파일
  (topic_find.load_preset 과 같은 규칙: 프리셋 폴더 manifest·frame · rules_path(없으면 <slug>/*.rules.json) · 원자료/top50.json ·
   뜯기/<id>/뜯기.json · 이미 만든 편 <편>/대본.json(겹침 검사 재료)). 'sources/'(벤치 화면 그림)는 넣지 않는다.
결과물 검사: 꾸러미만 넣은 엔진 묶음으로 렌더가 되는가(engine_bundle 과 함께 — handoff 실측 기록).
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path


def files_for(engine: Path, preset: str) -> list[str]:
    pdir = engine / preset
    man = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
    slug = man.get("slug") or Path(preset).parts[1]
    ch = engine / "channel" / slug
    out = [f"{preset}/manifest.json", f"{preset}/frame.json"]
    rp = man.get("rules_path")
    if rp and (engine / rp).is_file():
        out.append(rp)
    else:
        out += [p.relative_to(engine).as_posix() for p in sorted(ch.glob("*.rules.json"))]
    for rel in (ch / "원자료" / "top50.json",):
        if rel.is_file():
            out.append(rel.relative_to(engine).as_posix())
    out += [p.relative_to(engine).as_posix() for p in sorted((ch / "뜯기").glob("*/뜯기.json"))]
    out += [p.relative_to(engine).as_posix() for p in sorted(ch.glob("*/대본.json"))]
    for s in man.get("sources") or []:                       # 프리셋이 가리킨 뜯기(다른 폴더에 있을 수 있다)
        t = s.get("tteutgi") if isinstance(s, dict) else None
        if t and (engine / t).is_file():
            out.append(Path(t).as_posix())
    return [x for x in dict.fromkeys(out) if (engine / x).is_file()]


def build(engine: Path, preset: str) -> tuple[bytes, dict]:
    files = files_for(engine, preset)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(engine / rel, rel)
    data = buf.getvalue()
    meta = {"preset": preset, "files": len(files), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return data, meta


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    a = dict(zip(argv[1::2], argv[2::2]))
    engine, preset = Path(a["--engine"]), a["--preset"].strip("/")
    if argv[:1] == ["list"]:
        fs = files_for(engine, preset)
        for f in fs:
            print(f)
        print(f"{len(fs)}개")
        return 0
    if argv[:1] == ["build"]:
        data, meta = build(engine, preset)
        out = Path(a["--out"])
        out.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(preset.encode()).hexdigest()[:12] + ".zip"
        (out / name).write_bytes(data)
        (out / (name + ".json")).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(meta, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
