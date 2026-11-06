# -*- coding: utf-8 -*-
"""brainbulb_orange 밈 — 페페 그림 대신 **동물 영상 밈**(사장님 10-16 다듬기 방식을 처음부터, 관제 322).

밈 팩 = 숏템메이커 서버 research/meme_pack 에서 받은 영상 밈(<키>.mp4) + _meta/highlights.json(설명·쓸 구간·usable).
위치: 환경변수 BRAINBULB_MEME_PACK > 바탕화면/볼케이노/밈팩. ★팩은 git 에 없다(남의 영상 짤 — 저작권 미확인, 원본 brainbulb 와 같은 원칙).

고르는 규칙은 다듬기(볼케이노/다듬기_오렌지_페이퍼로지_동물밈.py animal_memes·pick)와 같다:
  사람 없이 동물만 · 페페(pp_) 제외 · usable 만 · 감정 낱말이 설명에 든 것 · 한 편 안에서 안 겹치게 · 편마다 다르게(작업폴더 이름 씨앗)
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
ANIMALS = ["고양이", "강아지", "개가", "개 ", "원숭이", "침팬지", "고릴라", "햄스터", "앵무", "오리", "물개", "너구리",
           "수달", "펭귄", "곰", "라쿤", "염소", "토끼", "다람쥐", "여우", "판다", "라마", "알파카", "부엉", "올빼미"]
MOODS = ["놀", "웃", "장난", "메롱", "능글", "의기양양", "씩", "곁눈", "한심", "황당", "멍하", "째려", "노려", "당황", "충격"]
PEOPLE = ["사람", "남자", "여자", "아이", "아기", "소녀", "소년", "배우", "가수"]
DRAWN = ["캐릭터", "만화", "일러스트", "애니", "그림", "이모티콘", "인형"]   # 진짜 동물만(11-04 시험판: «분홍색 토끼 캐릭터» 그림 짤이 뽑혔다)      # 실존 인물 짤 막기(10-28 '토끼' 낱말로 아이돌 영상이 뽑혔다)


# 설명에 '캐릭터·만화' 낱말이 없어 DRAWN 으로 못 거르는 그림 짤(11-04 락스 편: fm_thisisfine = 불타는 방 만화 강아지)
EXCLUDE_KEYS = {"fm_thisisfine", "gdb_1aubp94slkac2s27", "tnr_5991920615405934389"}   # + 영어 자막 박힌 영상(11-04 의대 편 «You stared me!»)


def candidates(pack_dir=None):
    """→ [(키, 메타, 표정점수)] 동물 영상 밈만, 표정 분명한 것 먼저."""
    pack_dir = pack_dir or PACK_DIR
    meta = os.path.join(pack_dir, "_meta", "highlights.json")
    if not os.path.exists(meta):
        return []
    out = []
    for k, v in json.load(open(meta, encoding="utf-8")).items():
        w = v.get("what", "")
        if k.startswith("pp_") or k in EXCLUDE_KEYS or not v.get("usable") or not os.path.exists(os.path.join(pack_dir, k + ".mp4")):
            continue
        if any(a in w for a in ANIMALS) and not any(p in w for p in PEOPLE) and not any(x in w for x in DRAWN):
            out.append((k, v, sum(m in w for m in MOODS)))
    out.sort(key=lambda x: (-x[2], x[0]))
    return out


GREEN_MAX = 0.20     # 화면의 20% 넘게 크로마키 초록이면 빼다(11-04 시험판: 우는 고양이 fm_crycat 이 초록 배경째 나옴)


def green_ratio(mp4, at=0.5):
    """영상 한 장면(at 초)의 크로마키 초록 비율 0~1 — 32×32로 줄여 G가 R·B보다 60 넘게 밝은 화소를 센다. 화면을 못 얻으면 None(고르는 쪽이 건너뜀)."""
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.2f}", "-i", mp4, "-frames:v", "1", "-vf", "scale=32:32",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=30, stdin=subprocess.DEVNULL)
        px = r.stdout
    except Exception:  # noqa: BLE001 — 재기 실패는 None(세 지점 중 잰 것만으로 판단, 다 못 재면 그 밈은 건너뜀) — 대신 로그
        print(f"[memes] 초록 검사 실패(못 잼 — 이 지점은 빼고 판단): {mp4}")
        return None
    n = len(px) // 3
    if not n:
        return None          # 화면을 못 얻음(시작점이 파일 밖 등) — '초록 아님'으로 치지 않는다(11-06 태권도 편 사고)
    g = sum(1 for i in range(n) if px[3 * i + 1] > 120 and px[3 * i + 1] > px[3 * i] + 60 and px[3 * i + 1] > px[3 * i + 2] + 60)
    return g / n


def pick(emotions, seed, pack_dir=None):
    """밈 칸마다(감정 순서대로) → [{"src": mp4, "start": 초, "key", "what"}]. 팩이 없으면 [].
    감정에 맞는 게 없으면 표정 분명한 아무 동물 밈. 한 편 안에서 겹치지 않는다."""
    pack_dir = pack_dir or PACK_DIR
    cands = candidates(pack_dir)
    if not cands:
        return []
    key = lambda c: hashlib.md5((seed + c[0]).encode()).hexdigest()
    used, out = set(), []
    for emo in emotions:
        words = EMOTION_WORDS.get(emo or "", [])
        pool = [c for c in cands if c[0] not in used and any(w in c[1].get("what", "") for w in words)]
        if not pool:
            pool = [c for c in cands if c[0] not in used and c[2] > 0] or [c for c in cands if c[0] not in used] or cands
        c = None
        for cand in sorted(pool, key=key):            # 초록 배경(크로마키) 영상은 건너뛴다
            used.add(cand[0])
            src = os.path.join(pack_dir, cand[0] + ".mp4")
            ss = render.meme_start(src, cand[1].get("start"))     # 렌더와 같은 시작점(주인 한 곳)에서 잰다
            gs = [green_ratio(src, ss + a) for a in (0.2, 0.8, 1.4)]
            gs = [g for g in gs if g is not None]
            if gs and max(gs) <= GREEN_MAX:
                c = (cand, ss)
                break
        if c is None:
            continue
        (c, ss) = c
        out.append({"src": os.path.join(pack_dir, c[0] + ".mp4"), "start": ss,
                    "key": c[0], "what": c[1].get("what", "")})
    return out
