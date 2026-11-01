# -*- coding: utf-8 -*-
"""인물형 롱폼 누끼 — 서버 일감 `prepare_cutouts` 를 실행기 공용 모듈 nukki.py 로 오린다 (2026-10-17 · 신고 #121).

■ 실행기 경계: 무엇을 오릴지(원본 경로·원본 지문·결과 이름)는 서버가 준다. 엔진 고르기(본인 Cloudflare 0순위 · 아니면 Replicate)·
    동시 수·요청 간격·거부 감지는 nukki.py 한 자리(너이봤 팩과 같은 모듈)다 — 여기에는 일감 검사·결과 파일 쓰기·모으기만 있다.
■ 다시 내도 돈·한도를 다시 쓰지 않는다: 결과 이름에 원본 지문 앞부분이 들어 있어(서버가 짓는다) 같은 이름의 결과 파일이 있으면
    보내지 않고 그 파일을 쓴다(지문은 그 파일을 한 번 읽어 잰다 · 6-00).
■ 거부·실패 한 번이면 남은 사진은 보내지 않는다(nukki.cut_files) — 결과는 status blocked 로 서버에 보인다. 자동 재시도 없음.
"""

import hashlib
import os
import re
import threading

VERSION = 1
#: 일감 id·이름은 파일 이름이 된다 — 경로 문자를 막는다(서버 longform/agy_images.ID_RE 와 같은 자).
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}")
_SHA = re.compile(r"[0-9a-f]{64}")


class LongformCutoutError(ValueError):
    """일감이 규격에 안 맞음 — 아무것도 보내지 않았다."""


def _bad(msg):
    raise LongformCutoutError("롱폼 누끼 일감이 올바르지 않습니다: " + msg + " (아무 사진도 보내지 않았습니다)")


def check_item(item):
    if not isinstance(item, dict) or item.get("version") != VERSION:
        _bad(f"version 은 {VERSION} 이어야 합니다.")
    if not isinstance(item.get("contract_key"), str) or not _SHA.fullmatch(item["contract_key"]):
        _bad("contract_key 가 sha256 글자(64자)가 아닙니다.")
    out_dir = item.get("out_dir")
    if not isinstance(out_dir, str) or not os.path.isabs(out_dir):
        _bad("out_dir 는 절대경로여야 합니다.")
    jobs = item.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        _bad("jobs 는 비어 있지 않은 목록이어야 합니다.")
    ids, names = set(), set()                      # casefold 한 집합으로 한 번 훑기(대소문자 무시 파일 시스템 · 6-00)
    for n, job in enumerate(jobs):
        where = f"jobs[{n}]"
        if not isinstance(job, dict):
            _bad(f"{where} 가 묶음이 아닙니다.")
        jid, name, src = job.get("id"), job.get("name"), job.get("src")
        if not isinstance(jid, str) or not _ID.fullmatch(jid) or not isinstance(name, str) or not _ID.fullmatch(name):
            _bad(f"{where} 의 id·name 은 영문·숫자·_.- 로 된 이름이어야 합니다.")
        if jid.casefold() in ids or name.casefold() in names:
            _bad(f"{where} 의 id·name 이 다른 일감과 겹칩니다({jid} · {name}).")
        ids.add(jid.casefold())
        names.add(name.casefold())
        if not isinstance(src, str) or not os.path.isabs(src) or not os.path.isfile(src):
            _bad(f"{where}.src 원본 사진이 없습니다(절대경로 파일이어야 합니다): {src!r}")
        if not isinstance(job.get("src_sha256"), str) or not _SHA.fullmatch(job["src_sha256"]):
            _bad(f"{where}.src_sha256 이 sha256 글자가 아닙니다.")
    return jobs


def prepare_cutouts(item):
    """서버 일감 → {version, contract_key, status, engine, cutouts, errors, refused}."""
    import nukki                                                    # noqa: PLC0415 — 실행기 공용 누끼 한 자리
    jobs = check_item(item)
    out_dir = item["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    out = {"version": VERSION, "contract_key": item["contract_key"], "status": "complete",
           "engine": None, "cutouts": {}, "errors": {}, "refused": None}
    lock = threading.Lock()
    todo = []
    for job in jobs:
        final = os.path.join(out_dir, job["name"] + ".png")
        if os.path.isfile(final) and os.path.getsize(final) > 0:
            with open(final, "rb") as fh:
                data = fh.read()
            out["cutouts"][job["id"]] = {"path": final, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                                         "cache_hit": True}
        else:
            todo.append(job)
    by_id = {job["id"]: job for job in todo}

    def write(jid, data, transparent, size):
        if not transparent:
            # 렌더(longform_render.cutout_layers)가 받지 않는 결과 — 쓰지 않고 그 사진만 실패로 적는다(다시 보내지 않는다).
            with lock:
                out["errors"][jid] = {"code": "cutout_alpha_missing",
                                      "message": "오린 결과에 투명한 곳이 없습니다 — 사람이 또렷이 보이는 다른 사진으로 바꾸세요."}
            return
        final = os.path.join(out_dir, by_id[jid]["name"] + ".png")
        with open(final + ".part", "wb") as fh:
            fh.write(data)
        try:
            # 윈도우 백신·색인기가 막 쓴 파일을 잠깐 쥐면 os.replace 가 WinError 5 로 실행 전체를 멈춘다(신고 #131 과 같은 부류) —
            # longform_* 이름 바꾸기 한 자리(longform_state.replace · 상한 있는 지연)로 하고, 끝까지 잠기면 이 사진 하나의 실패로 남긴다.
            from longform_state import replace as replace_file      # noqa: PLC0415 — 결과가 나온 뒤에만 무거운 모듈을 읽는다
            replace_file(final + ".part", final)
        except PermissionError as error:
            with lock:
                out["errors"][jid] = {"code": "cutout_locked", "message":
                                      f"다른 프로그램(백신·검색 색인 등)이 오린 사진 파일을 쥐고 있어 이름을 바꾸지 못했습니다"
                                      f"({os.path.basename(final)} · {error}). 그 프로그램을 닫고 다시 내면 이 사진만 다시 오립니다."}
            return
        with lock:
            out["cutouts"][jid] = {"path": final, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                                   "width": size[0], "height": size[1], "cache_hit": False}

    if todo:
        got = nukki.cut_files([(job["id"], job["src"]) for job in todo], write)
        out["engine"] = got["engine"]
        out["refused"] = got["refused"]
        for jid, err in got["errors"].items():
            out["errors"].setdefault(jid, err)
    for jid in out["errors"]:
        out["cutouts"].pop(jid, None)
    if out["errors"] or out["refused"]:
        out["status"] = "blocked"
    return out
