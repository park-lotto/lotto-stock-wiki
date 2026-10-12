# -*- coding: utf-8 -*-
"""영어모드 라이브 끝까지 시험(관제 029) — 서버 안에서 관리자 세션으로 실제 API를 차례로 부른다.

2단계 변환(/api/script/translate) → 3단계 시작(/api/produce/mix/start, 영어 given_script) → 미리보기 →
일레븐 성우 적용(/api/mix/voice; 타입캐스트는 422여야 함) → 렌더(/api/mix/render) → 캡컷(/api/mix/capcut) → 내보내기 ZIP.
결과 job_id 를 찍고, 비트별 영어 문장·자막 줄·음성 길이를 요약한다. 그 뒤 대조 도구 3종을 그 job 에 돌린다.

서버에서:  cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \
           /home/ubuntu/venv/bin/python tools/lang_mode_e2e.py <원본 job_id>
비밀값은 절대 출력하지 않는다(쿠키는 app._sign_session 으로 만들어 세션 안에서만 쓴다).
"""
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shopping_shorts import app as A          # noqa: E402  (env 로드 뒤 import)
from shopping_shorts import config            # noqa: E402
from shopping_shorts.store import Store       # noqa: E402

BASE = "http://127.0.0.1:8849"


def _poll(S, job_id, want, field="status", bad=("failed",), timeout=1500, every=10):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        d = S.get(BASE + "/api/mix/status/" + job_id).json()
        v = d.get(field)
        if v != last:
            print("  [%4.0fs] %s=%s %s" % (time.time() - t0, field, v, (d.get("error") or d.get("preview_error") or "")[:120]), flush=True)
            last = v
        if v in want:
            return d
        if v in bad:
            raise SystemExit("❌ %s=%s: %s" % (field, v, (d.get("error") or d.get("preview_error") or "")[:300]))
        time.sleep(every)
    raise SystemExit("❌ 시간 초과(%ds) — %s=%s" % (timeout, field, last))


def _pid(group):
    """/api/voice-presets 그룹 → preset_id (variants는 {이름: {preset_id, voice_id,…}} dict, default_variant 우선)."""
    v = group.get("variants") or {}
    pick = v.get(group.get("default_variant") or "") or (list(v.values())[0] if v else {})
    return pick.get("preset_id") or group.get("preset_id")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "a012b53091f7"
    st = Store(config.DB_PATH)
    job = st.get_mix_job(src)
    if not job:
        raise SystemExit("원본 job 없음: " + src)
    urls, ko = job["urls"], job.get("given_script") or ""
    lines = [x.strip() for x in ko.splitlines() if x.strip()]
    print("원본", src, "소스", len(urls), "줄", len(lines))
    S = requests.Session()
    S.cookies.set("dash_auth", A._sign_session(0, int(time.time()) + 7200))

    # ① 2단계 변환
    r = S.post(BASE + "/api/script/translate", json={"lines": lines, "product": ""}, timeout=180)
    d = r.json(); assert r.ok and d.get("ok"), ("translate", r.status_code, d)
    en = d["lines"]; assert len(en) == len(lines)
    print("① 변환 OK — 줄", len(en)); [print("   KO:", k, "\n   EN:", e) for k, e in zip(lines[:3], en[:3])]

    # ② 3단계 시작(영어 given_script)
    r = S.post(BASE + "/api/produce/mix/start", json={"urls": urls, "script": "\n".join(en), "target_seconds": job.get("target_seconds") or 25,
                                                         "subtitle_removal": False, "scene_first": True}, timeout=60)
    d = r.json(); assert r.ok and d.get("ok"), ("start", r.status_code, d)
    jid = d["job_id"]; print("② job", jid)
    _poll(S, jid, ("ready_for_review", "done"))

    # ③ 성우: 타입캐스트는 422, 일레븐은 통과
    g = S.get(BASE + "/api/voice-presets?lang=KR").json().get("groups") or []
    tc = next((x for x in g if x.get("engine") == "typecast"), None)
    el = next((x for x in g if x.get("engine") != "typecast"), None)
    assert el, "일레븐 프리셋 없음"
    if tc:
        pid = _pid(tc)
        r = S.post(BASE + "/api/mix/voice", json={"job_id": jid, "preset_id": pid}, timeout=60)
        print("③-a 타입캐스트 시도 →", r.status_code, (r.json().get("error") or "")[:80])
        assert r.status_code == 422, "영어모드에서 타입캐스트가 막히지 않았다"
    pid = _pid(el)
    r = S.post(BASE + "/api/mix/voice", json={"job_id": jid, "preset_id": pid, "speed": 1.0}, timeout=60)
    d = r.json(); assert r.ok and d.get("ok"), ("voice", r.status_code, d)
    print("③-b 일레븐", el.get("name"), pid, "→ 음성 생성 중")
    _poll(S, jid, ("ready_for_review",))

    # ④ 미리보기(편집 화면 대 완성본 대조 도구가 preview_status=ready 를 본다)
    r = S.post(BASE + "/api/produce/mix/preview", json={"job_id": jid}, timeout=60)
    print("④ preview", r.status_code, (r.json().get("error") or "")[:80])
    _poll(S, jid, ("ready",), field="preview_status", bad=("failed", "error"))

    # ⑤ 렌더
    r = S.post(BASE + "/api/mix/render", json={"job_id": jid, "thumb_intro": False}, timeout=60)
    d = r.json(); assert r.ok and d.get("ok"), ("render", r.status_code, d)
    print("⑤ render 예약 →", d.get("status"))
    _poll(S, jid, ("done",), timeout=2400)

    # ⑥ 캡컷 + 내보내기
    r = S.get(BASE + "/api/mix/capcut/" + jid, params={"base": r"C:\Users\test\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"}, timeout=300)
    cc = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    print("⑥-a capcut", r.status_code, "ok=", cc.get("ok"), "파일", len(cc.get("files") or cc.get("assets") or []), (cc.get("error") or "")[:80])
    r = S.get(BASE + "/api/mix/export/" + jid, timeout=600)
    print("⑥-b export ZIP", r.status_code, "%.1fMB" % (len(r.content) / 1e6))

    # 요약
    j = st.get_mix_job(jid); beats = (j.get("edit_plan") or {}).get("beats") or []
    print("== 결과 job", jid, "상태", j.get("status"), "video", j.get("video_path"))
    for b in beats:
        print("  %2s %-70s | 자막 %s | tts %s" % (b.get("beat_idx"), (b.get("narration") or "")[:70],
                                              b.get("caption_lines"), Path(b.get("tts_path") or "").name))
    print("JOB_ID=" + jid)


if __name__ == "__main__":
    main()
