# -*- coding: utf-8 -*-
"""brainbulb_orange 밈 — 밈 팩 영상(사장님 11-06 "동물말고 밈폴더에 있는거 모두", 초록 배경 밈은 금지).

밈 팩 = 숏템메이커 서버 research/meme_pack 에서 받은 영상 밈(<키>.mp4) + _meta/highlights.json(설명·쓸 구간·usable).
위치: 환경변수 BRAINBULB_MEME_PACK > 바탕화면/볼케이노/밈팩. ★팩은 git 에 없다(남의 영상 짤 — 저작권 미확인, 원본 brainbulb 와 같은 원칙).

고르는 규칙은 다듬기(볼케이노/다듬기_오렌지_페이퍼로지_동물밈.py animal_memes·pick)와 같다:
  (11-06부터) 팩 전부 · usable 만 · 초록 배경(is_chroma) 제외 · 감정 낱말이 설명에 든 것 · 한 편 안에서 안 겹치게 · 편마다 다르게(작업폴더 이름 씨앗)
  ⚠️ 다듬기 스크립트는 볼케이노 완성본용으로 따로 남아 있다(레포 밖). 우리 엔진으로 넘어오면 그쪽은 은퇴한다.
"""
import hashlib
import json
import os
import subprocess

from shopping_shorts.channelkit import render

PACK_DIR = os.environ.get("BRAINBULB_MEME_PACK") or os.path.join(os.path.expanduser("~"), "Desktop", "볼케이노", "밈팩")

EMOTION_WORDS = {"경악/충격": ["놀란", "놀라", "충격", "경악", "눈을 크게"], "의심/떨떠름": ["의심", "곁눈", "떨떠름", "째려", "노려", "못마땅", "흘겨"],
                 "비웃음/조롱": ["비웃", "조롱", "메롱", "능글", "킥킥", "깐족"], "당황": ["당황", "황당", "어리둥절", "어색"],
                 "만족/엄지척": ["만족", "엄지", "흐뭇", "미소", "뿌듯"], "무표정/멍": ["멍하", "무표정", "멍한"],
                 "분노": ["분노", "화난", "화를", "으르렁", "성난"], "슬픔/울음": ["슬픈", "슬퍼", "울고", "눈물", "울먹"],
                 "피곤/지침": ["피곤", "지친", "하품", "졸린", "축 처"]}
# 대본 밈 칸 감정(spec.EMOTIONS) → 숏템메이커 밈 감정(서버 scene_assets.tone 12가지, 밈팩 _meta/emotions.json).
#   사장님 11-06 "숏템메이커에 감정분류가 되어있을텐데" — 설명 낱말 맞추기(후보 66%가 어느 감정에도 안 걸렸다) 대신 이 표로 고른다.
#   앞쪽 감정이 먼저(첫 감정에 후보가 있으면 그것만), 없으면 뒤 감정, 그래도 없으면 설명 낱말, 그래도 없으면 아무 밈.
TONE_FOR = {
    "경악/충격": ["충격_입막", "놀람"],
    "당황": ["당황_멘붕"],
    "만족/엄지척": ["끄덕_엄지", "감탄_박수"],
    "무표정/멍": ["의심_황당", "당황_멘붕"],
    "분노": ["분노_짜증"],
    "비웃음/조롱": ["웃음"],
    "슬픔/울음": ["슬픔"],
    "의심/떨떠름": ["의심_황당", "거절_절레"],
    "피곤/지침": ["거절_절레", "슬픔"],
    "기타": [],
}


def tones(pack_dir=None):
    """밈 키 → 숏템메이커 감정. 표가 없으면 {}(설명 낱말로 고르는 옛 방식으로 돈다)."""
    p = os.path.join(pack_dir or PACK_DIR, "_meta", "emotions.json")
    if not os.path.exists(p):
        return {}
    return json.load(open(p, encoding="utf-8")).get("tone", {})


MOODS = ["놀", "웃", "장난", "메롱", "능글", "의기양양", "씩", "곁눈", "한심", "황당", "멍하", "째려", "노려", "당황", "충격"]


# 설명에 '캐릭터·만화' 낱말이 없어 DRAWN 으로 못 거르는 그림 짤(11-04 락스 편: fm_thisisfine = 불타는 방 만화 강아지)
# 사장님 11-06: 글자(자막·욕설) 박힌 밈·배우 장면은 전수 검사하지 않고, 완성본에서 걸리면 하나씩 여기에 넣는다
EXCLUDE_KEYS = {"gdb_1aubp94slkac2s27", "tnr_5991920615405934389",
                "b8nPTAXxWOc",   # 11-06 태권도 시험판 7번 컷: 원본 자막에 욕설
                "tnr_24236787",  # 11-06 사장님 제외: 기초연금 5번 컷(예능 자막·연예인)
                "gdb_uv4qowxegi7qk1kd"}   # 11-06 사장님 제외: 태권도 7번 컷(영화 배우·방송 로고)   # (fm_thisisfine 그림 짤은 11-06 '팩 전부'로 다시 허용)   # + 영어 자막 박힌 영상(11-04 의대 편 «You stared me!»)

# 초록 배경(크로마키) 밈 — 사장님 11-06 "할때마다 검사하지말고 지금 검사에 걸린건 아예 안쓰도록".
#   팩 1,228개를 is_chroma 기준으로 한 번 재서 걸린 19개 + 화면을 못 읽는 깨진 파일 10개. 만들 때는 재지 않고 이 목록만 뺀다.
#   팩에 밈을 새로 넣었으면 다시 잰다: py -m shopping_shorts.channel_presets.brainbulb_orange.memes --scan (새 목록을 찍어 준다)
CHROMA_KEYS = frozenset({
    "0rIVToIx9c8", "36kI8XZlxUI", "4D0o8exrcAk", "8DXsEQKR4pk", "DxYgkPGiBhM", "Hra7rZxuqFQ", "ISs1T4lQspg", "K4zQFw1hIe0",
    "Uv27Jag_k1w", "WsLn9U4VF1w", "fm_carlton", "fm_crycat", "fm_freshprince", "fm_frysquint", "fm_homerhedge", "fm_joeyshock",
    "fm_ohmygodwow", "gfr_CjqN", "pp_16761834542196815081",
})
BROKEN_KEYS = frozenset({
    "gdb_j0u1yrjah5a2a96e", "gdb_mz567cufi33ij9bg", "gfr_25ci", "gph_J3T9b6JFfxFT2", "gph_N7vysOmYh5sru",
    "pp_17124539", "pp_18862714", "pp_24418434", "tnr_11454518", "tnr_12632100731716971368",
})


def candidates(pack_dir=None):
    """→ [(키, 메타, 표정점수)] 동물 영상 밈만, 표정 분명한 것 먼저."""
    pack_dir = pack_dir or PACK_DIR
    meta = os.path.join(pack_dir, "_meta", "highlights.json")
    if not os.path.exists(meta):
        return []
    out = []
    for k, v in json.load(open(meta, encoding="utf-8")).items():
        w = v.get("what", "")
        # 사장님 11-06 "동물말고 밈폴더에 있는거 모두 사용해도 되는 것으로" — 동물·사람·그림·페페(pp_) 구분 없이 팩 전부.
        #   남는 거름 = usable·파일 있음·EXCLUDE_KEYS. 크로마키는 고를 때 영상 전체를 재서 뺀다(pick·is_chroma)
        if k in EXCLUDE_KEYS or k in CHROMA_KEYS or k in BROKEN_KEYS or not v.get("usable") or not os.path.exists(os.path.join(pack_dir, k + ".mp4")):
            continue
        out.append((k, v, sum(m in w for m in MOODS)))
    out.sort(key=lambda x: (-x[2], x[0]))
    return out


# 크로마키(초록 배경) 밈 금지 — 사장님 11-06 "크로마키가 들어간 밈은 사용하지 않는다 / 크로마키=초록배경"
#   기준은 팩 1,228개를 전부 재고 걸린 것·경계 31개를 눈으로 대조해 정했다(11-06):
#   ① 형광 초록(G>170·R,B<110) 이 한 장면이라도 화면의 4% 넘음 → 초록 화면·초록 사각형(가운데 박힌 것 포함)
#   ② 연두·청록까지 넓힌 초록이 화면 가장자리의 30% 넘음 → 초록 배경
#   페페(초록 개구리) 피부는 ① 보다 어둡고 가장자리에 안 닿아 안 걸린다(옛 기준은 페페를 초록 배경으로 잡았다). 걸림 19개
CHROMA_STRICT_MAX = 0.04
CHROMA_EDGE_MAX = 0.30
_N = 32
_RING = [(x, y) for y in range(_N) for x in range(_N) if x in (0, 1, _N - 2, _N - 1) or y in (0, 1, _N - 2, _N - 1)]


def _strict(r, g, b):
    return g > 170 and r < 110 and b < 110 and g - max(r, b) > 100


def _loose(r, g, b):
    return g > 150 and g - b > 80 and g - r > 40


def is_chroma(mp4):
    """영상 전체(초당 4장)를 재서 초록 배경이면 True. 화면을 못 얻으면 True(안 쓴다 — 후보는 많다)."""
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"fps=4,scale={_N}:{_N}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
        px = r.stdout
    except Exception:  # noqa: BLE001 — 못 재면 쓰지 않는다 — 로그
        print(f"[memes] 초록 배경 검사 실패(안 씀): {mp4}")
        return True
    fs = _N * _N * 3
    frames = [px[i:i + fs] for i in range(0, len(px) - fs + 1, fs)]
    if not frames:
        return True
    for f in frames:
        if sum(1 for i in range(0, fs, 3) if _strict(f[i], f[i + 1], f[i + 2])) / (_N * _N) > CHROMA_STRICT_MAX:
            return True
        if sum(1 for x, y in _RING if _loose(*f[(y * _N + x) * 3:(y * _N + x) * 3 + 3])) / len(_RING) > CHROMA_EDGE_MAX:
            return True
    return False


def pick(emotions, seed, pack_dir=None):
    """밈 칸마다(감정 순서대로) → [{"src": mp4, "start": 초, "key", "what"}]. 팩이 없으면 [].
    감정에 맞는 게 없으면 표정 분명한 아무 밈. 한 편 안에서 겹치지 않는다."""
    pack_dir = pack_dir or PACK_DIR
    cands = candidates(pack_dir)
    if not cands:
        return []
    key = lambda c: hashlib.md5((seed + c[0]).encode()).hexdigest()
    tone = tones(pack_dir)
    used, out = set(), []
    for emo in emotions:
        words = EMOTION_WORDS.get(emo or "", [])
        pool = []
        for t in TONE_FOR.get(emo or "", []):          # 숏템메이커 감정 표 먼저
            pool = [c for c in cands if c[0] not in used and tone.get(c[0]) == t]
            if pool:
                break
        if not pool:
            pool = [c for c in cands if c[0] not in used and any(w in c[1].get("what", "") for w in words)]
        if not pool:
            pool = [c for c in cands if c[0] not in used and c[2] > 0] or [c for c in cands if c[0] not in used] or cands
        c = sorted(pool, key=key)[0]                  # 초록 배경·깨진 파일은 candidates 가 이미 뺐다(CHROMA_KEYS·BROKEN_KEYS)
        used.add(c[0])
        src = os.path.join(pack_dir, c[0] + ".mp4")
        out.append({"src": src, "start": render.meme_start(src, c[1].get("start")),   # 렌더와 같은 시작점(주인 한 곳)
                    "key": c[0], "what": c[1].get("what", "")})
    return out


def scan(pack_dir=None):
    """팩 전체를 is_chroma 로 재서 (초록 배경 키, 못 읽는 키) — 팩을 바꿨을 때 CHROMA_KEYS·BROKEN_KEYS 를 새로 적으려고."""
    pack_dir = pack_dir or PACK_DIR
    meta = json.load(open(os.path.join(pack_dir, "_meta", "highlights.json"), encoding="utf-8"))
    chroma, broken = [], []
    for k, v in sorted(meta.items()):
        p = os.path.join(pack_dir, k + ".mp4")
        if k in EXCLUDE_KEYS or not v.get("usable") or not os.path.exists(p):
            continue
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-frames:v", "1", "-f", "null", "-"], capture_output=True, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            broken.append(k)
        elif is_chroma(p):
            chroma.append(k)
    return chroma, broken


if __name__ == "__main__":
    import sys
    if "--scan" in sys.argv:
        c, b = scan()
        print("CHROMA_KEYS", len(c), c)
        print("BROKEN_KEYS", len(b), b)
