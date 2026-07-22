"""전역 발음교정 사전(2026-07-22, 트랙 보이스).

어색한 구절→재표기를 서버 DB(settings kv, JSON)에 한 벌로 저장하고, 공유 합성
경로가 렌더 직전 profile.pronunciation.dict 위에 병합한다. 연음 재표기는 텍스트의
성질이라 보이스와 무관 → 전역 하나로 모든 렌더·모든 보이스에 적용(설계 §2-A).

git 파일이 아니라 DB에 두는 이유: 사장님은 라이브 서버(소리 나는 곳)에서 교정하는데
서버가 git-tracked 파일에 쓰면 git status가 더러워져 auto_deploy pull이 막힌다(사고 #9).
DB(gitignore data/)는 배포 pull에 안 지워져 서버 편집이 안전하다(기존 프로파일과 동일).
"""
import copy
import json

_KEY = "global_pron_dict"


def load(store):
    """전역 발음사전 {phrase: respelling}. 없거나 JSON 손상 시 {}(graceful)."""
    raw = store.get_setting(_KEY, None)
    if not raw:
        return {}
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(store, entries):
    """전역 발음사전 저장(전체 교체). entries: {phrase: respelling}."""
    store.set_setting(_KEY, json.dumps(entries or {}, ensure_ascii=False))


def overlay(profile, global_dict):
    """전역 사전을 profile.pronunciation.dict 아래에 병합한 새 profile 반환(원본 불변).

    per-preset 명시 항목이 전역보다 우선한다(더 구체적). 전역이 빈 dict면 원본 그대로
    반환(no-op). 방어적: 어떤 예외에도 원본 profile을 반환한다 — 교정은 부가기능이라
    죽이면 안 된다(기존 _synthesize_beats probe 폴백과 같은 원칙)."""
    if not global_dict:
        return profile
    try:
        out = copy.deepcopy(profile) if profile else {}
        pron = out.get("pronunciation")
        if not isinstance(pron, dict):
            pron = {"on": True, "dict": {}}
            out["pronunciation"] = pron
        merged = dict(global_dict)                 # 전역 먼저
        merged.update(pron.get("dict") or {})      # per-preset이 덮어씀(우선)
        pron["dict"] = merged
        pron.setdefault("on", True)
        return out
    except Exception:
        return profile
