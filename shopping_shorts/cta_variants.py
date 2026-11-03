"""플랫폼별 CTA 판(2026-10-18 고객 제보 F1) — 렌더 한 번에 마지막 CTA만 다른 영상을 함께 뽑는다.

고객: "영상 하나 만들면 뒤에 CTA만 각 플랫폼에 맞게 3~4가지 버전으로 한번에 뽑을 수 없을까요?
       인스타는 댓글, 유튜브 수창은 제품스티커, 비수창은 롱폼 연결, 클립·틱톡은 프로필 — 매번 캡컷에 TTS까지 번거롭다."
사장님: "렌더 한 번에 어차피 1회 차감."

★판단의 주인은 이 파일 하나다(0순위-C):
  - 판 설정(어느 플랫폼·문구·목소리 방식) = load_config / save_config (설정 표 cta_variants::<job>)
  - 판 대본 = variant_plan — 본편 대본 사본에서 CTA 칸(edit_plan._is_cta) 문장만 바꾼다
  - 판 렌더 = render_variants — 본편 run_render 가 조립을 끝낸 **뒤** 같은 재료로 assemble 을 판마다 한 번 더 부른다
  - 판 상태 = <작업폴더>/cta_variants.json (DB 스키마를 안 건드린다)
★과금 코드는 여기 없다 — 판은 본편 렌더 1회 차감에 포함된다(사장님 확정).
★본편 final.mp4·DB 편성은 건드리지 않는다. 판 실패는 본편을 살린다(경보만).
"""
import copy
import json
import sys
import time
import traceback
from pathlib import Path

# 플랫폼 4종 — 기본 문구는 고객이 고쳐 쓴다(화면이 이 목록을 그대로 그린다)
PLATFORMS = [
    {"key": "insta",   "label": "인스타",        "text": "궁금하면 댓글 남겨주세요, 바로 링크 보내드릴게요."},
    {"key": "yt_shop", "label": "유튜브 수익창출", "text": "영상 속 제품 스티커를 눌러보세요."},
    {"key": "yt_long", "label": "유튜브 비수창",   "text": "아래 ▶관련 영상을 눌러 구매링크를 확인하세요."},
    {"key": "profile", "label": "틱톡·클립",       "text": "프로필 링크에서 확인하세요."},
]
_KEYS = {p["key"] for p in PLATFORMS}
_OLD_DEFAULTS = {"아래 관련 영상을 눌러 구매링크를 확인하세요."}
TTS_MODES = ("cta", "full")      # cta = CTA 칸만 새로 굽기(빠름) / full = 판마다 전체 목소리 다시(느림·이음매 자연)
MAX_TEXT = 80


def _key(job_id):
    return f"cta_variants::{job_id}"


def _cust_key(cid):
    return f"cta_variants_default::{int(cid or 0)}"


def normalize(raw):
    """화면이 보낸 값 → 저장할 모양. 모르는 플랫폼·빈 문구는 버린다."""
    raw = raw if isinstance(raw, dict) else {}
    mode = raw.get("tts_mode") if raw.get("tts_mode") in TTS_MODES else "cta"
    items = []
    by = {str(x.get("key")): x for x in (raw.get("items") or []) if isinstance(x, dict)}
    for p in PLATFORMS:
        x = by.get(p["key"]) or {}
        text = " ".join(str(x.get("text") or p["text"]).split())[:MAX_TEXT]
        if text in _OLD_DEFAULTS:      # 고치지 않은 옛 기본 문구는 새 기본으로(화살표 추가, 10-19)
            text = p["text"]
        items.append({"key": p["key"], "label": p["label"], "on": bool(x.get("on")), "text": text})
    return {"tts_mode": mode, "items": items}


def load_config(store, job_id, customer_id=0):
    """이 작업의 판 설정. 없으면 이 회원이 지난번에 쓴 문구(없으면 기본) — 전부 꺼진 채로."""
    for k in (_key(job_id), _cust_key(customer_id)):
        try:
            v = store.get_setting(k, "") or ""
            if v:
                cfg = normalize(json.loads(v))
                if k != _key(job_id):
                    for it in cfg["items"]:
                        it["on"] = False
                return cfg
        except Exception:      # noqa: BLE001 — 깨진 저장값은 기본으로
            traceback.print_exc(file=sys.stderr)
    return normalize({})


def save_config(store, job_id, customer_id, raw):
    cfg = normalize(raw)
    s = json.dumps(cfg, ensure_ascii=False)
    store.set_setting(_key(job_id), s)
    store.set_setting(_cust_key(customer_id), s)   # 다음 영상 기본 문구
    return cfg


def chosen(cfg):
    return [it for it in (cfg or {}).get("items") or [] if it.get("on") and it.get("text")]


def cta_beat_indexes(plan):
    """CTA 칸 위치(대본 순서). 판단은 edit_plan._is_cta 한 곳."""
    from shopping_shorts.edit_plan import _is_cta
    return [i for i, b in enumerate((plan or {}).get("beats") or []) if _is_cta(b)]


def marked_plan(plan, job):
    """칸에 CTA 표시가 하나도 없는 작업(계획 때 자동 추정이 못 잡은 것)은 **사본**에 같은 판정(apply_cta_mark)을
    다시 얹는다 — app 의 CTA 자르기와 같은 방식. DB 의 계획은 안 바꾼다(2026-10-19 Park님 383ac5b29649)."""
    beats = (plan or {}).get("beats") or []
    if not beats or any("cta_mark" in b for b in beats):
        return plan
    from shopping_shorts.edit_plan import apply_cta_mark
    vp = copy.deepcopy(plan)
    apply_cta_mark(vp["beats"], (job or {}).get("given_script"), (job or {}).get("script_structure"))
    return vp


def variant_plan(plan, text):
    """본편 대본 사본에서 CTA 칸 문장만 바꾼다. CTA 칸이 여럿이면 첫 칸에 새 문장, 나머지 칸은 뺀다.
    바뀐 칸은 음성·자막 줄·시간을 비워 합성이 새로 채우게 한다(app 문장 고치기와 같은 초기화)."""
    vp = copy.deepcopy(plan)
    idx = cta_beat_indexes(vp)
    if not idx:
        return None
    beats = vp["beats"]
    b = beats[idx[0]]
    b["narration"] = text
    b["narration_manual"] = True
    for k in ("tts_path", "tts_speed_base_path", "cap_durs", "caption_lines", "cap_src"):
        b.pop(k, None)
    b["cap_lead"] = 0.0
    b["caption_lines_human"] = False
    for i in reversed(idx[1:]):
        del beats[i]
    return vp


def status_path(work):
    return Path(work) / "cta_variants.json"


def out_path(work, key):
    return Path(work) / f"final_cta_{key}.mp4"


def read_status(work):
    try:
        return json.loads(status_path(work).read_text(encoding="utf-8"))
    except Exception:      # noqa: BLE001
        return {}


def _write_status(work, st):
    p = status_path(work)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def render_variants(*, cfg, plan, work, render_one, synth):
    """판마다: 대본 사본 → 음성(synth) → 조립(render_one). 상태 파일을 판마다 갱신한다.

    synth(vplan, tts_dir, full) — 음성을 채운다(본편과 같은 _synthesize_beats).
    render_one(vplan, out) — 본편과 같은 assemble(+인트로)로 out 에 굽는다.
    반환 상태 dict. 하나가 실패해도 나머지는 계속한다."""
    items = chosen(cfg)
    st = {"stamp": time.time(), "tts_mode": cfg.get("tts_mode", "cta"),
          "items": {it["key"]: {"label": it["label"], "text": it["text"], "status": "waiting"} for it in items}}
    if not items:
        _write_status(work, st)
        return st
    full = cfg.get("tts_mode") == "full"
    for it in items:
        rec = st["items"][it["key"]]
        rec["status"] = "rendering"
        _write_status(work, st)
        t0 = time.time()
        try:
            vp = variant_plan(plan, it["text"])
            if vp is None:
                raise RuntimeError("이 대본엔 CTA 칸이 없어요")
            tts_dir = (Path(work) / f"tts_cta_{it['key']}") if full else (Path(work) / "tts")
            synth(vp, tts_dir, full)
            out = out_path(work, it["key"])
            render_one(vp, out)
            if not out.exists() or out.stat().st_size < 1000:
                raise RuntimeError("판 영상이 만들어지지 않았어요")
            rec.update(status="done", file=out.name, sec=round(time.time() - t0, 1))
        except Exception as e:      # noqa: BLE001 — 판 하나 실패가 나머지·본편을 죽이지 않는다
            traceback.print_exc(file=sys.stderr)
            rec.update(status="failed", error=str(e)[:200], sec=round(time.time() - t0, 1))
        print(f"[cta_variants] {it['key']} {rec['status']} {rec.get('sec')}s", file=sys.stderr, flush=True)
        _write_status(work, st)
    return st
