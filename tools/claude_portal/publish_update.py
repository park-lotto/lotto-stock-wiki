"""켤 때 자동 업데이트 묶음 올리기(관제 234 5판) — 설치팩 빌드 폴더(<out>/win-x64/Shortem)의 server/·engine/ 을 zip 으로 묶어
서버 저장소(claude_portal.store_dir)에 내용주소로 넣고 updates/latest.json 을 쓴다. 고객 PC 는 켤 때 /api/claude/update 로 받는다.

  py tools/claude_portal/publish_update.py --stage <빌드 폴더>/win-x64/Shortem --version 1.0.1 [--notes "…"]
  py tools/claude_portal/publish_update.py --install <dist>/shortem-win-x64-1.0.0.zip --plat win-x64 --version 1.0.0
    = exe 없이 까는 묶음(실행 도구까지 든 설치 폴더 통째, build_win 이 만든다) → install/latest-<plat>.json
  (서버에서 돌리거나, CLAUDE_STORE_DIR 를 서버 저장소와 같은 곳으로 두고 돌린다)

단계 배포(관제 304) — 판단은 claude_portal.rollout_* 한 곳, 여기는 명령만:
  py tools/claude_portal/publish_update.py --stage <빌드> --version 1.0.2 --rollout-cid 123 --db <DB>   1명 시작(전체 판은 그대로)
  py tools/claude_portal/publish_update.py --rollout-status --db <DB>                                   단계·판별 실패율
  py tools/claude_portal/publish_update.py --rollout-advance 10 --db <DB>                               10%
  py tools/claude_portal/publish_update.py --rollout-advance 100 --approved-by 사장님 --db <DB>          전체(사람 승인 필수)
  py tools/claude_portal/publish_update.py --rollout-finish --db <DB>                                   100% 뒤 전체 판으로 굳히기
  py tools/claude_portal/publish_update.py --rollout-rollback "사유" --db <DB>                           손으로 되돌리기

판단 주인: 무엇을 묶나 = UPDATE_DIRS(server·engine) + carries_models 한 곳. 실행 도구(tools/)·받아쓰기 모델(models/whisper)은 설치팩을 다시 받는다.
판독 모델: 옛 연결기가 engine/ 을 통째로 바꾸므로, 옛 판 회원은 engine/models 로 실린 판을 한 번 받아야 하고 새 프로그램이 그것을 설치 폴더 models/ 로
  옮긴다(updater.adoptModels). MODELS_LAST 가 그 마지막 판이다 — 정하기 전까지는 모든 판에 싣는다.
결과물 검사: shortem_client/test/update.test.js — 받은 묶음을 풀어 바꾼 뒤 서버가 새 판으로 뜨는가.
판 번호 규칙(사장님 11-03 "큰변화.기능추가.작은수정"): X.Y.Z — X 큰 변화(설치 다시·옛 판과 안 맞음) / Y 기능 추가(Z 는 0 으로) / Z 작은 수정·수리.
  1.0.62 까지는 순번으로 올렸다(마지막 숫자만). 비교는 숫자 세 칸(claude_portal._semver)이라 1.0.62 → 1.1.0 도 새 판으로 받는다.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path

UPDATE_DIRS = ("server", "engine")
SKIP = re.compile(r"(^|/)(__pycache__|\.git)(/|$)|\.pyc$")
ENGINE_MODELS = "engine/models/"
VISION_MODELS = ("ppocrv5_server_det.onnx", "face_detection_yunet_2023mar.onnx", "face_recognition_sface_2021dec.onnx", "nanodet.onnx")
# 판독 모델을 싣는 마지막 판. None = 아직 안 정함(전부 싣는다). 서버가 옛 판 회원에게 이 판을 먼저 주게 된 뒤에 번호를 적는다 —
#   옛 회원이 이 판을 건너뛰고 그 다음 판을 받으면 모델이 지워진다(연결기 applyPending)
MODELS_LAST: str | None = None


def carries_models(version: str) -> bool:
    return MODELS_LAST is None or tuple(map(int, version.split("."))) <= tuple(map(int, MODELS_LAST.split(".")))


def vision_model_source(name: str) -> Path:
    """개발 PC 의 판독 모델 원본 자리."""
    home = Path.home() / ".shortem" / "models"
    return home / "dl" / name if name == "nanodet.onnx" else home / name


def _models_to_add(stage: Path) -> dict:
    """engine/models 로 실을 파일 → 묶음 이름. 무대 engine/models 에 이미 있는 것은 그 자리로 실린다."""
    out = {}
    real = (stage / "engine/tools/calcopy/hybrid/render_bench.py").is_file()    # 시험용 작은 무대는 있는 것만
    for name in VISION_MODELS:
        if (stage / ENGINE_MODELS / name).is_file():
            continue
        src = stage / "models" / name
        if real and not src.is_file():
            src = vision_model_source(name)                                     # 빠른배포 무대엔 models/ 가 없다
        if src.is_file():
            out[src] = ENGINE_MODELS + name
        elif real:
            raise SystemExit(f"[publish_update] 판독 모델 없음: {src} — 이 판은 모델을 실어야 한다")
    return out


def make_zip(stage: Path, version: str) -> bytes:
    buf = io.BytesIO()
    carry = carries_models(version)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in UPDATE_DIRS:
            root = stage / d
            if not root.is_dir():
                raise SystemExit(f"[publish_update] {root} 없음")
            for p in sorted(root.rglob("*")):
                rel = p.relative_to(stage).as_posix()
                if p.is_file() and not SKIP.search(rel) and (carry or not rel.startswith(ENGINE_MODELS)):
                    z.write(p, rel)
        if carry:
            for src, name in _models_to_add(stage).items():
                z.write(src, name)
        z.writestr("app_version.json", json.dumps({"version": version}))
    return buf.getvalue()


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage")
    ap.add_argument("--install", help="설치 묶음 zip(build_win 이 만든 것) — 주면 업데이트 대신 설치 묶음을 올린다")
    ap.add_argument("--plat", default="win-x64")
    ap.add_argument("--version")
    ap.add_argument("--notes", default="")
    ap.add_argument("--db", help="단계 배포 명령이 읽는 서버 DB(reference.db)")
    ap.add_argument("--rollout-cid", type=int, help="--stage 와 함께: 전체 판 대신 이 회원 1명에게만 준다")
    ap.add_argument("--rollout-status", action="store_true")
    ap.add_argument("--rollout-advance", type=int, choices=(10, 100))
    ap.add_argument("--approved-by", default="", help="--rollout-advance 100 에 필수: 승인한 사람")
    ap.add_argument("--rollout-finish", action="store_true")
    ap.add_argument("--rollout-rollback", metavar="사유")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from shopping_shorts import claude_portal as cp
    control = a.rollout_status or a.rollout_advance or a.rollout_finish or a.rollout_rollback
    store = None
    if control or a.rollout_cid is not None:
        if not a.db:
            raise SystemExit("--db 필요(서버 reference.db)")
        from shopping_shorts.store import Store
        store = Store(a.db)
    try:
        if control:
            return _rollout_command(cp, a, store)
        if not a.version or not re.fullmatch(r"\d+\.\d+\.\d+", a.version):
            raise SystemExit("버전은 1.2.3 꼴")
        return _publish(cp, a)
    except cp.PortalError as e:
        raise SystemExit(f"[publish_update] 거절: {e.msg}")


def _rollout_command(cp, a, store) -> int:
    if a.rollout_status:
        d = cp.update_table()
        print(json.dumps({"version": d.get("version"), "rollout": d.get("rollout"), "recalled": d.get("recalled"),
                          "health": cp.rollout_health(store, d)}, ensure_ascii=False))
    elif a.rollout_advance:
        print(json.dumps(cp.rollout_advance(a.rollout_advance, store, a.approved_by), ensure_ascii=False))
    elif a.rollout_finish:
        print(json.dumps({"version": cp.rollout_finish()["version"]}, ensure_ascii=False))
    else:
        print(json.dumps({"version": cp.rollout_rollback(a.rollout_rollback, by="사람", store=store)["version"]}, ensure_ascii=False))
    return 0


def _publish(cp, a) -> int:
    if a.install:
        if a.plat not in cp.INSTALL_PLATS:
            raise SystemExit(f"plat 은 {cp.INSTALL_PLATS} 중 하나")
        sha, size = cp.put_blob(Path(a.install))
        cp.install_path(a.plat).parent.mkdir(parents=True, exist_ok=True)
        cp.install_path(a.plat).write_text(json.dumps({"version": a.version, "sha256": sha, "size": size}), encoding="utf-8")
        print(json.dumps({"install": a.plat, "version": a.version, "sha256": sha, "mb": round(size / 1e6, 1)}, ensure_ascii=False))
        return 0
    if not a.stage:
        raise SystemExit("--stage 또는 --install")
    data = make_zip(Path(a.stage), a.version)
    tmp = cp.store_dir() / "updates" / f"shortem-app-{a.version}.zip"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(data)
    sha, size = cp.put_blob(tmp)
    tmp.unlink()
    if a.rollout_cid is not None:
        cp.rollout_start(a.version, sha, size, [a.rollout_cid], a.notes)
    else:
        cp.update_register(a.version, sha, size, a.notes)
    print(json.dumps({"version": a.version, "sha256": sha, "mb": round(size / 1e6, 1), "rollout_cid": a.rollout_cid}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
