# -*- coding: utf-8 -*-
"""대본 설명서(script_frame) — 채널 원본 받아쓰기 50편 + 대조군에서 "이 채널이 어떻게 설명하나"를 숫자·목록으로 뽑는다 (관제 097, 2026-10-16).

설계: docs/superpowers/specs/2026-10-16-대본엔진-대본설명서-design.md
판단 주인
  build(asr_dir, meta, bench, contrast_dirs, ...) -> script_frame.json   설명서 만들기(1~5칸 + S1/S2/S3) — 이 함수 하나
  judge_like(script, frame) -> {score, pass, parts}                       판별기(화법·S1·S2 범위) — 이 함수 하나
  features(text) / label_rules(text)                                       두 함수가 같이 쓰는 측정기(원본·대조·새 대본에 같은 자)
제미나이(무료 창구 gemini_free.ask)는 label_llm() 에서만 부른다: 원본 편당 1회(문장 역할·사슬 노드·소구 축·컷 종류), 캐시 파일.
대조군·새 대본은 LLM 없이 label_rules 로만 잰다(같은 자로 재야 diff 가 측정기 차이가 아니다).

    PYTHONUTF8=1 py tools/calcopy/engine/script_frame.py label  --chan C:/숏템_칼카피/homedesignnote
    PYTHONUTF8=1 py tools/calcopy/engine/script_frame.py build  --chan C:/숏템_칼카피/homedesignnote --out channel/homedesignnote/대본설명서
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics as st
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── 어휘(설명서·검사가 같이 쓰는 목록) ─────────────────────────────────────
ROLES = ["훅", "계기", "의심·기존인식", "문제·불편", "정체", "원리·속성", "장점·결과", "사회적증거", "감상", "행동유도"]
NODES = ["상황", "불편", "속성", "결과", "증거", "감상", "권유"]          # S2 논리 사슬 노드
HOOKS = ["고백·체험단정", "지인사건", "경고·명령", "미친제품·발견", "질문", "감탄", "대상비교·도발", "숫자·역사"]
EVIDENCE = ["사회적반응", "수치", "권위·출처", "전후비교", "체험담", "없음"]
SHOT_KINDS = ["제품전체", "사용동작", "설치·조립과정", "디테일클로즈업", "공간전경", "비포·문제상황", "사람반응·얼굴", "텍스트·가격화면", "짤·밈", "기타"]

# S1 사실 종류(축) — 규칙 측정기. 키워드는 원본·대조 받아쓰기에서 실제로 나온 말(2026-10-16 50편+대조 1,868편 읽고 고름)
AXES = {
    "설치·사용난이도": ["설치", "끼우기만", "끼워만", "붙이기만", "붙여만", "얹어만", "걸쳐만", "무타공", "타공", "공사 없이", "공사없이", "시공 없이",
                  "쉬워", "쉽게", "간단", "초보", "똥손", "따라할", "따라 할", "연결만", "꽂기만", "올려두기만", "넣어주기만", "누르면", "버튼",
                  "없이", "어디서든", "쓰기 쉬", "쓰기도"],
    "공간·분위기": ["공간", "분위기", "호텔", "카페", "갤러리", "쇼룸", "인테리어", "고급", "넓어", "깔끔", "감성", "포인트", "예쁘", "예뻐",
                "근사", "럭셔리", "모던", "미니멀", "힐링", "레트로", "전통", "기품", "차분"],
    "사회적반응": ["보는 사람마다", "어디서 샀", "물어보", "난리", "품절", "입소문", "유행", "대세", "화제", "불티", "1위", "인기", "열광", "소리 질렀",
              "사이에서"],
    "가격·대안비교": ["가격", "저렴", "만원", "원 ", "비싸", "비싼", "공사비", "돈 ", "돈주고", "돈 주고", "가성비", "최저가", "생활비", "아낄", "공사 하지",
                "공사 안", "대신", "보다", "보통", "살 일", "필요 없", "일반 "],
    "소재·질감": ["원목", "나무", "소재", "실리콘", "스틸", "스테인", "질감", "결이", "나뭇결", "패브릭", "페브릭", "알루미늄", "철제", "쇠로", "가죽", "돌"],
    "수치·스펙": [],     # 숫자+단위는 정규식(_NUM_UNIT)으로 센다
    "원리·개발비하인드": ["개발자", "개발했", "개발한", "천재", "설계", "원리", "기술", "연구", "스타트업", "회사", "방식", "구조", "모방", "적용",
                   "발명", "만든 거", "만들었"],
    "문제·불편": ["불편", "짜증", "스트레스", "힘들", "고민", "막히", "막혀", "더러", "좁", "그림의 떡", "못하게", "안되", "안 되", "단점", "금방", "귀찮",
              "도망", "망칠"],
    "가족·관계": ["와이프", "아내", "남편", "엄마", "부모님", "친구", "장모님", "애기", "애들", "아이", "손님", "할머니", "사장님", "직원", "언니"],
    "제약·주거조건": ["전셋집", "집주인", "임대", "자취", "이동식", "들고 갈", "월세", "원룸", "좁은집", "좁은 집", "신혼"],
    "수납·정리": ["수납", "정리", "보관", "선정리", "선 정리", "숨길", "칸칸", "서랍", "걸 수", "걸수"],
    "내구·안전": ["튼튼", "내구성", "버티", "매달려도", "안전", "안심", "부러", "깨지", "오래 쓸"],
}
_NUM_UNIT = re.compile(r"\d+(?:\.\d+)?\s*(?:cm|mm|m|kg|g|인치|%|배|분|초|시간|개|장|년|도|단|kw|W|만원|원|천원|ml|L|스케일|단계|가지)")

# S2 노드 규칙(문장 조각 → 노드). 순서대로 첫 매치 — 낱말·순서는 제미나이 beat 노드(원본 33편 201조각)와 일치율이 가장 높은 것(0.627, 2026-10-16)
_NODE_RULES = [
    ("권유", r"(댓글|링크|찾아봤|찾아왔|알아왔|구매처|사오세요|쓰세요|해보세요|고민해 보세요|하지 마세요|하지마세요|남겨주세요|참고해|무조건)"),
    ("증거", r"(보는 사람마다|어디서 샀|물어보고|난리|품절|입소문|불티|1위|1등|열광|인기|화제|사이에서|유행|대세|유명하|지정|팔리|작품인줄|\d+\s*(%|배|년))"),
    ("불편", r"(불편|짜증|스트레스|힘들|고민|막히|막혀|더러|좁아|좁다|그림의 떡|못하게|단점|귀찮|도망|망칠|공사비|시들|부러져|걱정|거부감|하루 다 가|혼났)"),
    ("상황", r"(친구|와이프|아내|엄마|부모님|장모님|요즘|얼마 전|얼마전|놀러|발견|알려줬|사왔|선물|보여주|알아보다|보고|출시|했는데|하는데|큰일|놀랐|충격|처음)"),
    ("결과", r"(수 있|되고|되니까|일이 없|없겠|되겠|바뀌|달라지|변했|변신|넓어|깔끔해|호텔|카페 같|갤러리|쇼룸|완성|유지|아낄|오래 쓸|새것|새 것|정리됐|정리해두면|편하더라|편해요|딱 좋|딱이)"),
    ("감상", r"(너무 좋|대만족|만족|힐링|반했|미쳤|대박|예쁘더라|좋아요|좋던데|예뻐요|고급스럽더|좋더라)"),
]

# 화법: 문장 끝 어미(긴 것부터). 원문에서 실제로 나온 꼴만 — build 가 채널별 빈도·목록을 뽑는다
ENDINGS = ["다고 하더라고요", "다고 하더라구요", "더라고요", "더라구요", "거든요", "잖아요", "대요", "는데요", "은데요", "데요", "래요", "네요", "군요",
           "세요", "습니다", "니다", "까요", "나요", "죠", "어요", "아요", "에요", "예요", "여요", "해요", "요",
           "다는데", "던데", "는데", "은데", "인데", "다고", "라고", "음", "함", "임", "됨", "짐", "림", "거", "네", "지", "냐", "다"]
POLITE = re.compile(r"(요|니다|죠|세요)[.!?~]*$")
HEARSAY = re.compile(r"(대요|래요|다는데|라는데|다던데|다더라|다고 하더라|라고 하더라|다고 합니다|라고 합니다|다고 하네|데요)")
PERSON1 = re.compile(r"(^|\s)(저|제가|제|저희|저도|저는|저같은|우리 ?집|와이프|아내|남편|엄마|부모님|친구|장모님)(\s|가|는|도|한테|랑|네|집|$)")
CONNECT = re.compile(r"(는데|은데|인데|던데|니까|어서|아서|라서|해서|지만|면서|고서)")


# ── 문장·조각 나누기 ──────────────────────────────────────────────────────
_FINAL_SPLIT = re.compile(r"(?:(?<![필중])요|니다|(?<=[가-힣])죠|(?<![다마처])음|(?<=[가-힣])[함됨짐림]|(?<=[가-힣])임|(?<=[했됐었았])다|거(?=\s+(?:근데|그래서|더|진짜|심지어|이게|이건|그리고|하지만|그런데)))[~;]*\s+")


def sentences(text: str) -> list[str]:
    """문장 = 부호(. ! ?) 경계 + 부호 없는 끝맺음(…요/니다/죠/음/함/임 + 공백). 부호 유무와 상관없이 같은 자로 자른다
    (원본 asr 은 부호가 있고 대조 뜯기·DB 글은 없다 — 부호에만 기대면 측정기 차이가 채널 차이로 보인다)."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    out = []
    for p in re.split(r"(?<=[.!?])\s+", t):
        last = 0
        for m in _FINAL_SPLIT.finditer(p + " "):
            seg = (p + " ")[last:m.end()].strip()
            if seg:
                out.append(seg)
            last = m.end()
        rest = (p + " ")[last:].strip()
        if rest:
            out.append(rest)
    return [x for x in out if len(re.sub(r"\W", "", x)) >= 2]


def clauses(sent: str) -> list[str]:
    """조각 = 연결어미(는데·니까·어서·지만·면서) 뒤에서 자른다 — S2 노드는 조각 단위로 붙인다."""
    out, buf = [], ""
    for w in sent.split(" "):
        buf = (buf + " " + w).strip()
        if re.search(r"(는데|은데|인데|던데|니까|어서|아서|라서|지만|면서),?$", w) and len(buf) >= 6:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def ending_of(sent: str) -> str:
    s = re.sub(r"[\s.!?~,;:'\"]+$", "", sent)
    s = s.replace("구요", "고요")
    for e in ENDINGS:
        if s.endswith(e.replace("구요", "고요")):
            return e.replace("구요", "고요")
    return "기타"


def axes_of(text: str) -> list[str]:
    out = []
    for ax, kws in AXES.items():
        if ax == "수치·스펙":
            if _NUM_UNIT.search(text):
                out.append(ax)
        elif any(k in text for k in kws):
            out.append(ax)
    return out


def node_of(clause: str) -> str:
    for name, pat in _NODE_RULES:
        if re.search(pat, clause):
            return name
    return "속성"


def label_rules(text: str) -> list[dict]:
    """(측정기) 대본 → 조각마다 {sent, text, node, axes}. 원본·대조·새 대본에 똑같이 쓴다."""
    out = []
    for si, s in enumerate(sentences(text)):
        for c in clauses(s):
            out.append({"sent": si, "text": c, "node": node_of(c), "axes": axes_of(c)})
    return out


def chain_shape(nodes: list[str], k: int = 4) -> str:
    """사슬 꼴 = 노드 순서에서 연속 중복을 접고 처음 k 마디. 예: 상황>속성>결과>증거"""
    seq = []
    for n in nodes:
        if not seq or seq[-1] != n:
            seq.append(n)
    return ">".join(seq[:k])


def features(text: str) -> dict:
    """(측정기) 화법·S1·S2 수치 — judge_like 와 build 가 같은 함수로 잰다."""
    ss = sentences(text)
    n = max(1, len(ss))
    lab = label_rules(text)
    ends = [ending_of(s) for s in ss]
    lens = [len(re.sub(r"\s", "", s)) for s in ss]
    ax = Counter(a for c in lab for a in set(c["axes"]))
    ax_sent = {a: sum(1 for i in range(len(ss)) if any(a in c["axes"] for c in lab if c["sent"] == i)) / n for a in AXES}
    return {
        "n_sent": len(ss),
        "chars": sum(lens),
        "sent_len_mean": round(st.mean(lens), 1) if lens else 0.0,
        "polite_ratio": round(sum(1 for s in ss if POLITE.search(re.sub(r"[\s.!?~]+$", "", s) + "")) / n, 3),
        "hearsay_ratio": round(sum(1 for s in ss if HEARSAY.search(s)) / n, 3),
        "person1_ratio": round(sum(1 for s in ss if PERSON1.search(s)) / n, 3),
        "connect_per_sent": round(sum(len(CONNECT.findall(s)) for s in ss) / n, 3),
        "question_ratio": round(sum(1 for s in ss if s.rstrip().endswith("?")) / n, 3),
        "exclaim_ratio": round(sum(1 for s in ss if s.rstrip().endswith("!") or re.match(r"^(와|아니|아이고|헐|오)\b", s)) / n, 3),
        "endings": ends,
        "axes": dict(ax),
        "axes_sent": ax_sent,
        "nodes": [c["node"] for c in lab],
        "chain": chain_shape([c["node"] for c in lab]),
    }


# ── 입력 읽기 ─────────────────────────────────────────────────────────────
def asr_words(path: Path) -> list[dict]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for r in d.get("results") or []:
        alt = (r.get("alternatives") or [{}])[0]
        out.append({"w": alt.get("content", ""), "t0": r.get("start_time", 0.0), "t1": r.get("end_time", 0.0), "punct": r.get("type") == "punctuation"})
    return out


def asr_text(words: list[dict]) -> str:
    s = ""
    for w in words:
        s += w["w"] if w["punct"] else " " + w["w"]
    return s.strip()


def contrast_texts(contrast_dirs: list) -> list[dict]:
    """대조군: ① 채널 뜯기 폴더(engine_뜯기3/*/뜯기.json audio.transcript.segments) ② 발굴 DB 덤프 json([{url,user,text,…}])."""
    out = []
    for c in contrast_dirs or []:
        p = Path(c)
        if p.is_file() and p.suffix == ".json":
            for x in json.loads(p.read_text(encoding="utf-8")):
                if x.get("chan"):            # 채널 이름이 붙은 목록([{id,chan,text}]) = 채널 대조(묶음 = 채널)
                    out.append({"src": "list", "id": x.get("id"), "chan": x["chan"], "text": x.get("text", "")})
                else:                        # 발굴 DB 덤프([{url,user,text}]) = 한 묶음 '발굴DB'
                    out.append({"src": "db", "id": x.get("url"), "chan": x.get("user") or "?", "text": x.get("text", ""), "views": x.get("views")})
            continue
        ddirs = sorted(p.glob("*/뜯기.json"))
        for f in ddirs:
            d = json.loads(f.read_text(encoding="utf-8"))
            segs = (((d.get("audio") or {}).get("transcript") or {}).get("segments")) or []
            t = " ".join(s["text"] for s in segs if s.get("kind", "narration") == "narration").strip()
            if len(t) > 30:
                out.append({"src": "dir", "id": f.parent.name, "chan": p.parent.name, "text": t})
        if not ddirs:                       # Speechmatics 받아쓰기 폴더(asr/*.json)
            for f in sorted(p.glob("*.json")):
                try:
                    t = asr_text(asr_words(f))
                except (KeyError, ValueError, TypeError):
                    continue
                if len(t) > 30:
                    out.append({"src": "asr", "id": f.stem, "chan": p.parent.name, "text": t})
    return out


# ── 제미나이 라벨(원본 편당 1회, 캐시) ─────────────────────────────────────
LABEL_PROMPT = """너는 한국어 쇼핑 숏폼 대본 분석가다. 아래 [대본]은 유튜브 숏폼의 나레이션 받아쓰기, [그림]은 이 영상의 컷마다 가운데 프레임을 번호 순서로 붙인 시트다.
JSON 하나로만 답하라. 키:
- item: 소개하는 물건 이름(한국어 짧게)
- category: 가전|가구|수납|청소|욕실|주방|조명·장식|시공자재|취미·완구|디지털|생활소품 중 하나
- match_kw: 같은 물건을 다른 영상에서 찾을 한국어 검색어 2~4개(일반명사, 예: "빨래 개는 기계")
- price_band: 저가|중가|고가|언급없음 (대본에서 가격 말이 있으면 그 느낌으로)
- install: 설치없음|끼우기·붙이기|간단조립|시공필요
- hook_type: 첫 문장 유형 — {hooks} 중 하나
- beats: 대본을 의미 조각으로 순서대로 나눈 목록. 각 원소 {{"text": 대본 원문 그대로 이어지는 조각(빠짐·바꿈 없이), "role": {roles} 중 하나, "node": {nodes} 중 하나, "axes": 이 조각이 말하는 사실 종류 목록({axes} 중), "evidence": {evid} 중 하나}}
  role 뜻: 훅=첫 주의끌기 / 계기=누가·어디서 알게 됐나 / 의심·기존인식=처음엔 안 믿음·원래 생각 / 문제·불편=기존 방식의 불편 / 정체=이게 뭔지 한 줄 / 원리·속성=작동·구조·소재·기능 / 장점·결과=쓰면 생기는 변화 / 사회적증거=남들 반응·인기 / 감상=말하는 사람의 만족 / 행동유도=댓글·링크·사라
  node 뜻(논리 사슬): 상황=맥락·계기 / 불편=문제 / 속성=제품의 성질 / 결과=쓰는 사람에게 생기는 변화 / 증거=남들 반응·수치·권위 / 감상=개인 만족 / 권유=행동 요구
- shots: 그림 시트의 번호마다 {{"i": 번호, "kind": {shots} 중 하나}}

[대본]
{text}
"""


def contact_sheet(mp4: Path, times: list[float], out: Path, tile_w: int = 180) -> Path:
    """컷 가운데 프레임을 번호 붙여 한 장으로(4열). ffmpeg 한 번씩 → PIL 타일."""
    from PIL import Image, ImageDraw
    tiles = []
    tmp = out.parent / (out.stem + "_f")
    tmp.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(times):
        f = tmp / f"{i:02d}.jpg"
        if not f.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={tile_w}:-2", str(f)],
                           stdin=subprocess.DEVNULL, check=False)
        if f.exists():
            im = Image.open(f).convert("RGB")
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 34, 22], fill=(255, 255, 0))
            d.text((4, 4), str(i), fill=(0, 0, 0))
            tiles.append(im)
    if not tiles:
        raise RuntimeError(f"프레임 0장: {mp4}")
    cols = 4
    w, h = tiles[0].size
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * w, rows * h), (40, 40, 40))
    for i, im in enumerate(tiles):
        sheet.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sheet.save(out, quality=72)
    return out


def shot_spans(bench_pv: dict) -> list[list[float]]:
    cuts = ((bench_pv.get("cuts") or {}).get("cuts")) or []
    dur = (bench_pv.get("probe") or {}).get("duration") or (cuts[-1] + 1 if cuts else 0)
    edges = [0.0] + [c for c in cuts if 0 < c < dur] + [dur]
    return [[round(edges[i], 3), round(edges[i + 1], 3)] for i in range(len(edges) - 1) if edges[i + 1] - edges[i] > 0.05]


def label_llm(chan_dir: Path, vid: str, bench_pv: dict, cache_dir: Path, ask=None) -> tuple[dict | None, str | None]:
    """원본 1편 라벨 — 캐시가 있으면 그대로. ask = gemini_free.ask(시험에선 가짜)."""
    cache = cache_dir / f"{vid}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8")), None
    words = asr_words(chan_dir / "asr" / f"{vid}.json")
    text = asr_text(words)
    if len(text) < 10:
        return None, "asr 비어 있음"
    spans = shot_spans(bench_pv)
    sheet = contact_sheet(chan_dir / "mp4" / f"{vid}.mp4", [(a + b) / 2 for a, b in spans], cache_dir / "sheets" / f"{vid}.jpg")
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask as _ask
        ask = _ask
    prompt = LABEL_PROMPT.format(hooks="|".join(HOOKS), roles="|".join(ROLES), nodes="|".join(NODES), axes="|".join(AXES),
                                 evid="|".join(EVIDENCE), shots="|".join(SHOT_KINDS), text=text)
    d, err = ask([sheet.read_bytes()], prompt, tag=f"script_frame:{vid}")
    if not d:
        return None, err
    d["_spans"] = spans
    d["_text"] = text
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d, None


# ── 계산 도우미 ───────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", s or "")


def _q(vals: list[float], p: float) -> float:
    v = sorted(vals)
    if not v:
        return 0.0
    k = (len(v) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    return round(v[f] + (v[c] - v[f]) * (k - f), 3)


def _dist(vals: list[float]) -> dict:
    return {"p10": _q(vals, .1), "median": _q(vals, .5), "p90": _q(vals, .9), "n": len(vals)}


def _collapse(seq: list[str]) -> list[str]:
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def _lev(a: list, b: list) -> int:
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (x != y))
    return d[len(b)]


def _cos(a: dict, b: dict) -> float:
    ks = set(a) | set(b)
    na = math.sqrt(sum(a.get(k, 0) ** 2 for k in ks))
    nb = math.sqrt(sum(b.get(k, 0) ** 2 for k in ks))
    return round(sum(a.get(k, 0) * b.get(k, 0) for k in ks) / (na * nb), 4) if na and nb else 0.0


def _shingles(t: str, n: int = 5) -> set:
    s = _norm(t)
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def copy_overlap(a: str, b: str) -> float:
    """두 대본의 글자 5-gram 겹침(작은 쪽 기준) — 대조군에서 이 채널을 베낀 글을 걸러낸다."""
    x, y = _shingles(a), _shingles(b)
    return round(len(x & y) / max(1, min(len(x), len(y))), 3) if x and y else 0.0


def align_beats(beats: list[dict], words: list[dict]) -> list[list[float]]:
    """beat 글 ↔ 받아쓰기 낱말 시각. 글자(공백·부호 뺀) 누적 위치로 맞춘다 — 못 찾으면 바로 앞 끝에서 이어 붙인다."""
    chars, owner = "", []
    for wi, w in enumerate(words):
        if w["punct"]:
            continue
        n = _norm(w["w"])
        chars += n
        owner += [wi] * len(n)
    total = max(1, len(chars))
    spans, cur = [], 0
    for b in beats:
        L = max(1, len(_norm(b.get("text", ""))))
        key = _norm(b.get("text", ""))[:8]
        pos = chars.find(key, cur) if key else -1
        if pos < 0 or pos - cur > 40:
            pos = cur
        end = min(total, pos + L) - 1
        if not owner:
            spans.append([0.0, 0.0])
            continue
        w0, w1 = owner[min(pos, len(owner) - 1)], owner[max(0, min(end, len(owner) - 1))]
        spans.append([round(words[w0]["t0"], 2), round(words[w1]["t1"], 2)])
        cur = end + 1
    return spans


# ── 원본 읽기(asr 폴더 또는 뜯기 폴더) ─────────────────────────────────────
def _own_docs(asr_dir, meta) -> list[dict]:
    p = Path(asr_dir)
    views, titles, order = {}, {}, None
    if meta:
        m = json.loads(Path(meta).read_text(encoding="utf-8")) if isinstance(meta, (str, Path)) else meta
        order = [x["id"] for x in m]
        views = {x["id"]: x.get("views") for x in m}
        titles = {x["id"]: x.get("title", "") for x in m}
    if list(p.glob("*/뜯기.json")):
        return [{"id": c["id"], "text": c["text"], "words": None, "views": None, "title": ""} for c in contrast_texts([p])]
    docs = []
    for vid in order or sorted(f.stem for f in p.glob("*.json")):
        f = p / f"{vid}.json"
        if not f.exists():
            continue
        w = asr_words(f)
        t = asr_text(w)
        if len(_norm(t)) < 10:
            continue
        docs.append({"id": vid, "text": t, "words": w, "views": views.get(vid), "title": titles.get(vid, "")})
    return docs


def _llm_labels(labels_dir, ids) -> dict:
    out = {}
    if not labels_dir:
        return out
    for vid in ids:
        f = Path(labels_dir) / f"{vid}.json"
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(d.get("beats"), list) and d["beats"]:
                out[vid] = d
    return out


# ── 판별기 자 ─────────────────────────────────────────────────────────────
JUDGE_FEATS = ["polite_ratio", "voice_ratio", "sent_len_mean", "connect_per_sent", "ending_char", "ending_cos", "foreign_ending", "axis_cos",
               "node_cos"]
JUDGE_WEIGHTS = {"polite_ratio": 2, "voice_ratio": 1, "sent_len_mean": 1, "connect_per_sent": 1, "ending_char": 2, "ending_cos": 1,
                 "foreign_ending": 1, "axis_cos": 2, "node_cos": 2}
# 필수(점수로 메우지 못함) = 화법 칸의 정의 그대로(설계서 4칸 "어미는 목록 안"): 존댓말 비율 + 특유 어미 비율 + 남의 어미(대조만 쓰는 어미) 비율. 데이터로 고르지 않는다
JUDGE_HARD = ["polite_ratio", "ending_char", "foreign_ending"]
CHAR_LIFT = 1.2          # 특유 어미 = 원본 비율 ≥1% 이고 대조보다 1.2배 이상 잦은 어미


def _ending_vec(ends: list[str]) -> dict:
    c = Counter(ends)
    n = max(1, len(ends))
    return {k: v / n for k, v in c.items()}


def _node_vec(nodes: list[str]) -> dict:
    """S2 사슬 꼴 수치 — 노드 비율 + 이웃 노드 쌍(접은 순서) 비율. 시작·끝 노드는 따로 표시."""
    nd = _collapse(nodes)
    v = Counter({f"n:{x}": 1 for x in nodes})
    v.update(f"b:{a}>{b}" for a, b in zip(nd, nd[1:]))
    if nd:
        v[f"s:{nd[0]}"] += 2
        v[f"e:{nd[-1]}"] += 2
    tot = sum(v.values()) or 1
    return {k: c / tot for k, c in v.items()}


def _judge_vec(text: str, core: dict) -> dict:
    """대본 1편 → 판별기 수치(설명서의 목록·중심에 대해). build·judge_like 공용."""
    f = features(text)
    ends = f["endings"] or ["기타"]
    foreign = set(core["foreign_endings"])
    return {
        "polite_ratio": f["polite_ratio"],
        "voice_ratio": round(min(1.0, f["person1_ratio"] + f["hearsay_ratio"]), 3),
        "sent_len_mean": f["sent_len_mean"],
        "connect_per_sent": f["connect_per_sent"],
        "ending_char": round(sum(1 for e in ends if e in set(core["ending_char_set"])) / len(ends), 3),
        "ending_cos": _cos(_ending_vec(ends), core["ending_centroid"]),
        "foreign_ending": round(sum(1 for e in ends if e in foreign) / len(ends), 3),
        "axis_cos": _cos(dict(f["axes_sent"]), core["axis_centroid"]),
        "node_cos": _cos(_node_vec(f["nodes"]), core["node_centroid"]),
        "_chain3": chain_shape(f["nodes"], 3),
    }


def _score(vec: dict, ranges: dict, weights: dict | None = None) -> tuple[float, dict]:
    w = weights or JUDGE_WEIGHTS
    parts, tot, got = {}, 0, 0.0
    for k in JUDGE_FEATS:
        lo, hi = ranges[k]
        ok = lo <= vec[k] <= hi
        parts[k] = {"v": vec[k], "range": [lo, hi], "ok": ok, "w": w[k]}
        tot += w[k]
        got += w[k] * ok
    return round(got / tot, 3), parts


def _as_text(script) -> str:
    if isinstance(script, dict):
        script = script.get("lines") or (script.get("final") or {}).get("lines") or script.get("text") or ""
    if isinstance(script, list):
        script = " ".join((x.get("text", "") if isinstance(x, dict) else str(x)).strip() for x in script)
    return str(script)


def judge_like(script, frame: dict) -> dict:
    """(판단 주인) 새 대본이 이 채널처럼 설명하나 — 화법·S1(소구 축 분포)·S2(사슬 꼴)를 설명서 범위로 잰다.
    script = 글 / {lines:[{text}]} / [{text}] / [글]. 반환 {score, pass, hard_fail, parts, threshold}."""
    J = frame["judge"]
    vec = _judge_vec(_as_text(script), J["core"])
    score, parts = _score(vec, J["ranges"], J.get("weights"))
    hard = [k for k in J.get("hard", []) if not parts[k]["ok"]]
    return {"score": score, "pass": bool(score >= J["threshold"] and not hard), "hard_fail": hard, "threshold": J["threshold"],
            "parts": parts, "chain3": vec["_chain3"], "channel": frame.get("channel")}


# ── S3 예문 검색·S1 사실 고르기(설명서를 쓰는 쪽 = script_engine.draft 가 부른다) ──
def nearest_examples(product: dict, frame: dict, k: int = 3, exclude: tuple = ()) -> list[dict]:
    """S3: 상품 {name, kw, category, price_band, install} 과 가까운 원본 k편 — 품목·설치형·가격대·검색어 겹침 점수, 같으면 조회수."""
    idx = [x for x in frame["S3_search"]["index"] if x["id"] not in set(exclude)]
    name = (product.get("name") or "") + " " + " ".join(product.get("kw") or [])

    def sc(x):
        s = 3 * (x.get("category") == product.get("category")) + 2 * (x.get("install") == product.get("install")) \
            + 1 * (x.get("price_band") == product.get("price_band"))
        s += sum(1 for w in (x.get("match_kw") or []) for t in w.split() if len(t) >= 2 and t in name)
        return (s, x.get("views") or 0)
    return sorted(idx, key=sc, reverse=True)[:k]


def select_facts(facts: list[str], frame: dict, k: int = 4) -> list[dict]:
    """S1: 상품 사실 목록 → 이 채널이 집는 축(lift) 점수 순 k개. 빼는 축(drop)만 걸린 사실은 뒤로."""
    pick = {x["axis"]: x["lift"] for x in frame["S1_selection"]["pick"]}
    drop = {x["axis"] for x in frame["S1_selection"]["drop"]}
    out = []
    for i, t in enumerate(facts):
        ax = axes_of(t)
        s = sum(pick.get(a, 0) for a in ax) - sum(1.0 for a in ax if a in drop and a not in pick)
        out.append({"i": i, "text": t, "axes": ax, "score": round(s, 2)})
    return sorted(out, key=lambda x: (-x["score"], x["i"]))[:k]


def brief(product: dict, frame: dict, facts: list[str], k_examples: int = 3, exclude: tuple = (), n_facts: int = 4) -> dict:
    """설명서 → 생성기에 줄 재료 묶음(LLM 없음). 생성(script_engine.draft)은 이것을 받아 문장을 통째로 쓴다(빈칸 끼우기 금지).
    공식(칸 순서·길이 비율) · 훅 유형 · S1 고른 사실(+뺄 축) · S2 사슬 꼴 · 어미 목록·말버릇 · S3 가까운 예문 · 칸별 장면 종류."""
    sk, hk, sp, s2 = frame["1_skeleton"], frame["2_hook"], frame["4_speech"], frame["S2_chains"]
    return {
        "channel": frame.get("channel"),
        "formulas": [{k: f[k] for k in ("id", "slots", "share", "len_ratio", "beats_per_slot", "fine_examples")} for f in sk["formulas"][:3]],
        "hook_types": hk["top3"], "hook_examples": [e["text"] for e in hk["examples"][:3]],
        "facts_picked": select_facts(facts, frame, n_facts), "axes_pick": [x["axis"] for x in frame["S1_selection"]["pick"]],
        "axes_drop": [x["axis"] for x in frame["S1_selection"]["drop"]],
        "chains": [x["shape"] for x in s2["shapes"][:3]],
        "endings": sp["ending_list"][:10], "signature_phrases": [x["phrase"] for x in sp["signature_phrases"][:12]],
        "connectives": [x["c"] for x in sp.get("connectives", [])[:6]], "connect_per_sent": sp["stats"]["connect_per_sent"]["median"],
        "foreign_endings": sp.get("foreign_endings", []),
        "length": {"chars_median": sk["chars"]["median"], "sent_len_median": sp["stats"]["sent_len_mean"]["median"],
                   "n_sent_median": sp["stats"]["n_sent"]["median"]},
        "examples": [{"id": x["id"], "item": x.get("item"), "text": x.get("text", "")} for x in nearest_examples(product, frame, k_examples, exclude)],
        "shot_contract": {r: v["shot_kinds"] for r, v in (frame.get("5_shot_contract") or {}).get("by_role", {}).items()},
    }


def copy_spans(text: str, examples: list[str], n: int = 7) -> list[str]:
    """베낌 검사: 새 대본과 예문이 공백 뺀 n자 이상 그대로 겹치는 조각."""
    a = _norm(text)
    hits = set()
    for ex in examples:
        b = _norm(ex)
        grams = {b[i:i + n] for i in range(max(0, len(b) - n + 1))}
        for i in range(max(0, len(a) - n + 1)):
            if a[i:i + n] in grams:
                hits.add(a[i:i + n])
    return sorted(hits)


# ── build: 설명서 만들기(주인 함수) ───────────────────────────────────────
NODE2ROLE = {"상황": "계기", "불편": "문제·불편", "속성": "원리·속성", "결과": "장점·결과", "증거": "사회적증거", "감상": "감상", "권유": "행동유도"}
MACRO = {"훅": "훅", "계기": "도입", "의심·기존인식": "도입", "문제·불편": "도입", "정체": "설명", "원리·속성": "설명",
         "장점·결과": "효과", "감상": "효과", "사회적증거": "증거", "행동유도": "행동유도"}
COPY_MAX = 0.35          # 대조 글이 원본 하나와 5-gram 35% 이상 겹치면 '베낀 글'(대조에서 뺀다)
PICK_LIFT, DROP_LIFT = 1.25, 0.8


def hook_rule(sent: str) -> str:
    s = sent.strip()
    if s.endswith("?"):
        return "질문"
    if re.match(r"^(와|아니|아이고|헐|오 )", s):
        return "감탄"
    if re.search(r"(망할|큰일|이겼|따라잡)", s):
        return "대상비교·도발"
    if re.search(r"(마세요|하세요|쓰세요|해보세요|사오세요|사세요)", s):
        return "경고·명령"
    if re.search(r"(와이프|아내|남편|엄마|친구|장모님|부모님)", s):
        return "지인사건"
    if re.search(r"^(저|제가|저희)\b", s) or re.search(r"(버렸어요|안 사요|충격|놀랐어요)", s):
        return "고백·체험단정"
    if re.search(r"\d", s):
        return "숫자·역사"
    return "미친제품·발견"


def _roles_of(doc: dict, lab: dict | None) -> tuple[list[dict], str]:
    """편 1개의 역할 조각 — LLM 라벨이 있으면 그것, 없으면 규칙 노드 → 역할(첫 조각=훅)."""
    if lab:
        return [{"text": b.get("text", ""), "role": b.get("role") if b.get("role") in ROLES else "원리·속성",
                 "node": b.get("node") if b.get("node") in NODES else "속성",
                 "axes": [a for a in (b.get("axes") or []) if a in AXES], "evidence": b.get("evidence") or "없음"} for b in lab["beats"]], "llm"
    out = []
    for i, c in enumerate(label_rules(doc["text"])):
        out.append({"text": c["text"], "role": "훅" if i == 0 else NODE2ROLE[c["node"]], "node": c["node"], "axes": c["axes"], "evidence": "없음"})
    return out, "rules"


def _skeleton(docs, beats_by) -> dict:
    seqs = {}
    for d in docs:
        bs = beats_by[d["id"]]
        macro = _collapse([MACRO[b["role"]] for b in bs])
        seqs[d["id"]] = macro
    cnt = Counter(">".join(s) for s in seqs.values())
    # 탐욕 묶기: 많은 순으로 대표를 세우고, 편집거리 1 이내면 그 대표에 붙인다
    reps: list[list[str]] = []
    member = defaultdict(list)
    for key, _ in cnt.most_common():
        s = key.split(">")
        hit = next((r for r in reps if _lev(r, s) <= 1), None)
        if hit is None:
            reps.append(s)
            hit = s
        for vid, sq in seqs.items():
            if ">".join(sq) == key:
                member[">".join(hit)].append(vid)
    n = len(docs)
    formulas = []
    for i, (rep, vids) in enumerate(sorted(member.items(), key=lambda x: -len(x[1]))[:5], 1):
        share_by_role, sents_by_role, fine = defaultdict(list), defaultdict(list), Counter()
        for vid in vids:
            bs = beats_by[vid]
            tot = sum(len(_norm(b["text"])) for b in bs) or 1
            per = defaultdict(int)
            pern = Counter()
            for b in bs:
                per[MACRO[b["role"]]] += len(_norm(b["text"]))
                pern[MACRO[b["role"]]] += 1
            for m in rep.split(">"):
                share_by_role[m].append(per.get(m, 0) / tot)
                sents_by_role[m].append(pern.get(m, 0))
            fine[">".join(_collapse([b["role"] for b in bs]))] += 1
        formulas.append({"id": f"F{i}", "slots": rep.split(">"), "count": len(vids), "share": round(len(vids) / n, 3),
                         "len_ratio": {m: round(st.mean(v), 3) for m, v in share_by_role.items()},
                         "beats_per_slot": {m: round(st.mean(v), 2) for m, v in sents_by_role.items()},
                         "fine_examples": [k for k, _ in fine.most_common(3)], "videos": vids[:8]})
    role_freq = Counter(b["role"] for bs in beats_by.values() for b in bs)
    tot = sum(role_freq.values()) or 1
    first_role = Counter(beats_by[d["id"]][0]["role"] for d in docs if beats_by[d["id"]])
    return {"macro_map": MACRO, "formulas": formulas, "covered_share": round(sum(f["count"] for f in formulas) / max(1, n), 3),
            "role_freq": {r: round(c / tot, 3) for r, c in role_freq.most_common()},
            "first_role": dict(first_role.most_common()),
            "chars": _dist([len(_norm(d["text"])) for d in docs]),
            "sec": _dist([d["words"][-1]["t1"] for d in docs if d.get("words")])}


def _hooks(docs, labs) -> dict:
    rows = []
    for d in docs:
        first = sentences(d["text"])[0] if sentences(d["text"]) else d["text"][:40]
        t = (labs.get(d["id"]) or {}).get("hook_type")
        rows.append({"id": d["id"], "views": d.get("views") or 0, "text": first,
                     "type": t if t in HOOKS else hook_rule(first), "type_rule": hook_rule(first), "src": "llm" if t in HOOKS else "rules"})
    cnt = Counter(r["type"] for r in rows)
    n = len(rows) or 1
    ex, seen = [], Counter()
    for r in sorted(rows, key=lambda r: -r["views"]):          # 조회수 순, 유형마다 최대 3개 → 10개
        if seen[r["type"]] < 3 and len(ex) < 10:
            ex.append({k: r[k] for k in ("id", "views", "type", "text")})
            seen[r["type"]] += 1
    agree = sum(1 for r in rows if r["type"] == r["type_rule"]) / n
    return {"types": {k: round(v / n, 3) for k, v in cnt.most_common()}, "top3": [k for k, _ in cnt.most_common(3)], "examples": ex,
            "first_len_chars": _dist([len(_norm(r["text"])) for r in rows]), "rule_vs_llm_agree": round(agree, 3)}


def _appeal(docs, beats_by) -> dict:
    vid_ax, beat_ax, ev = Counter(), Counter(), Counter()
    nb = 0
    for d in docs:
        bs = beats_by[d["id"]]
        nb += len(bs)
        for a in {a for b in bs for a in b["axes"]}:
            vid_ax[a] += 1
        for b in bs:
            for a in b["axes"]:
                beat_ax[a] += 1
            ev[b["evidence"]] += 1
    n = len(docs) or 1
    tot_ev = sum(ev.values()) or 1
    return {"axes": [{"axis": a, "video_share": round(vid_ax[a] / n, 3), "beat_share": round(beat_ax[a] / max(1, nb), 3)}
                     for a, _ in vid_ax.most_common()],
            "evidence": {k: round(v / tot_ev, 3) for k, v in ev.most_common()}}


def _signature_phrases(own_texts, con_texts, n=3, min_df=0.08, min_lift=4.0, top=25) -> list[dict]:
    """원문에서 떼어온 말버릇 — 원본 편의 min_df 이상에 나오고 대조보다 min_lift 배 이상 잦은 어절 n-gram."""
    def grams(t):
        w = re.sub(r"[.,!?]", " ", t).split()
        return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)} | {" ".join(w[i:i + 2]) for i in range(len(w) - 1)}
    od, cd = Counter(), Counter()
    for t in own_texts:
        od.update(grams(t))
    for t in con_texts:
        cd.update(grams(t))
    no, nc = max(1, len(own_texts)), max(1, len(con_texts))
    out = []
    for g, c in od.items():
        df = c / no
        if df < min_df:
            continue
        lift = df / ((cd.get(g, 0) + 1) / (nc + 1))
        if lift >= min_lift:
            out.append({"phrase": g, "own_df": round(df, 3), "contrast_df": round(cd.get(g, 0) / nc, 4), "lift": round(lift, 1)})
    return sorted(out, key=lambda x: (-x["own_df"], -x["lift"]))[:top]


def _speech(docs, contrast) -> dict:
    F = [features(d["text"]) for d in docs]
    CF = [features(c["text"]) for c in contrast]
    oe = Counter(e for f in F for e in f["endings"])
    to = sum(oe.values()) or 1
    # 대조 어미 비율 = 묶음(채널·발굴DB)마다 비율을 낸 뒤 평균 — 1,868편 묶음 하나가 8편 채널의 특유 어미를 덮지 않게
    grp = defaultdict(Counter)
    for c, f in zip(contrast, CF):
        grp[c["chan"] if c["src"] != "db" else "발굴DB"].update(f["endings"])
    gshare = [{e: n / (sum(g.values()) or 1) for e, n in g.items()} for g in grp.values()]
    cshare = {e: sum(g.get(e, 0) for g in gshare) / max(1, len(gshare)) for e in {e for g in gshare for e in g}}
    ce = Counter(cshare)
    tc = 1.0
    endings = [{"ending": e, "share": round(c / to, 3), "contrast_share": round(cshare.get(e, 0), 3)} for e, c in oe.most_common()]
    cum, elist = 0.0, []
    for e in endings:
        if e["ending"] == "기타":
            continue
        elist.append(e["ending"])
        cum += e["share"]
        if cum >= 0.9:
            break
    foreign = [e for e, c in ce.items() if c / tc >= 0.03 and oe.get(e, 0) / to < 0.01 and e != "기타"]
    char_set = [e["ending"] for e in endings if e["ending"] != "기타" and e["share"] >= 0.01 and e["share"] >= CHAR_LIFT * e["contrast_share"]]
    keys = ["n_sent", "chars", "sent_len_mean", "polite_ratio", "hearsay_ratio", "person1_ratio", "connect_per_sent", "question_ratio", "exclaim_ratio"]
    conn = Counter(m for d in docs for s_ in sentences(d["text"]) for m in CONNECT.findall(s_))
    tconn = sum(conn.values()) or 1
    return {"connectives": [{"c": c, "share": round(n / tconn, 3)} for c, n in conn.most_common(8)],
            "endings": endings[:20], "ending_list": elist, "ending_char_set": char_set, "foreign_endings": sorted(foreign),
            "stats": {k: _dist([f[k] for f in F]) for k in keys},
            "contrast_stats": {k: _dist([f[k] for f in CF]) for k in keys},
            "signature_phrases": _signature_phrases([d["text"] for d in docs], [c["text"] for c in contrast])}


def _shot_contract(docs, labs, beats_by, bench_pv: dict) -> dict:
    agg = defaultdict(Counter)
    dur = defaultdict(list)
    nshot = defaultdict(list)
    used = 0
    for d in docs:
        lab = labs.get(d["id"])
        if not lab or not d.get("words") or d["id"] not in bench_pv:
            continue
        kinds = {s.get("i"): s.get("kind") for s in (lab.get("shots") or []) if s.get("kind") in SHOT_KINDS}
        spans = shot_spans(bench_pv[d["id"]])          # 라벨 때 시트를 만든 것과 같은 함수 → 번호가 같다
        bs = beats_by[d["id"]]
        tspans = align_beats(bs, d["words"])
        used += 1
        for b, (t0, t1) in zip(bs, tspans):
            dur[b["role"]].append(max(0.0, t1 - t0))
            k = 0
            for si, (a, c) in enumerate(spans):
                ov = min(t1, c) - max(t0, a)
                if ov > 0.05 and si in kinds:
                    agg[b["role"]][kinds[si]] += ov
                    k += 1
            nshot[b["role"]].append(k)
    out = {}
    for r in ROLES:
        if not agg[r] and not dur[r]:
            continue
        tot = sum(agg[r].values()) or 1
        out[r] = {"shot_kinds": {k: round(v / tot, 3) for k, v in agg[r].most_common(4)},
                  "sec": _dist(dur[r]), "shots_per_beat": round(st.mean(nshot[r]), 2) if nshot[r] else 0}
    return {"videos": used, "method": "제미나이 beat 글 ↔ asr 낱말 시각(align_beats) ↔ bench 컷 구간 겹친 시간 가중 · 컷 종류=제미나이 시트 판독",
            "by_role": out}


def _s1(docs, labs, contrast, imitators) -> dict:
    def rate(texts):
        tot = Counter()
        for t in texts:
            for a, v in features(t)["axes_sent"].items():
                tot[a] += v
        n = max(1, len(texts))
        return {a: round(tot[a] / n, 3) for a in AXES}
    db = [c for c in contrast if c["src"] == "db" and c["id"] not in imitators]
    own_all = rate([d["text"] for d in docs])
    groups = defaultdict(list)                       # 대조 축 비율 = 묶음(채널·발굴DB)마다 낸 뒤 평균(판별기·어미와 같은 방식)
    for c in contrast:
        if c["id"] not in imitators:
            groups[c["chan"] if c["src"] != "db" else "발굴DB"].append(c["text"])
    by_group = {g: rate(t) for g, t in groups.items()}
    # 고르기 기준 = 같은 카테고리(발굴 DB 홈템)가 있으면 그것 — 음식·잡학 채널과 견주면 '공간' 같은 축이 품목 탓으로 부풀어서
    # 이 채널의 '고르는 버릇'이 아니라 '다루는 품목'을 재게 된다. 없으면 대조 묶음 평균
    con_all = by_group["발굴DB"] if "발굴DB" in by_group else (
        {a: round(st.mean(r[a] for r in by_group.values()), 3) for a in AXES} if by_group else rate([]))
    # 같은 품목 짝: 원본의 검색어(제미나이 match_kw, 3자 이상 구절)가 대조 글에 그대로 들어간 것
    pairs = []
    for d in docs:
        kws = [k for k in ((labs.get(d["id"]) or {}).get("match_kw") or []) if len(_norm(k)) >= 3]
        hits = [c for c in db if any(k in c["text"] for k in kws)]
        if hits:
            pairs.append({"id": d["id"], "kw": kws, "contrast": [h["id"] for h in hits[:5]], "n": len(hits)})
    own_p = rate([d["text"] for d in docs if d["id"] in {p["id"] for p in pairs}])
    con_p = rate([c["text"] for c in db if c["id"] in {x for p in pairs for x in p["contrast"]}])

    def lifts(o, c):
        return {a: round((o[a] + 0.01) / (c[a] + 0.01), 2) for a in AXES}
    la, lp = lifts(own_all, con_all), lifts(own_p, con_p)
    use_pairs = len(pairs) >= 10
    L, O, C = (lp, own_p, con_p) if use_pairs else (la, own_all, con_all)
    pick = sorted([{"axis": a, "own": O[a], "contrast": C[a], "lift": L[a], "lift_all": la[a]} for a in AXES
                   if L[a] >= PICK_LIFT and O[a] >= 0.08], key=lambda x: -(x["own"] * math.log(x["lift"])))
    drop = sorted([{"axis": a, "own": O[a], "contrast": C[a], "lift": L[a], "lift_all": la[a]} for a in AXES
                   if L[a] <= DROP_LIFT and C[a] >= 0.05], key=lambda x: x["lift"])
    lift_by_group = {g: {a: round((own_all[a] + 0.01) / (r[a] + 0.01), 2) for a in AXES} for g, r in by_group.items()}
    return {"basis": "같은 품목 짝" if use_pairs else ("같은 카테고리(발굴 DB 홈템, 베낀 글 제외)" if "발굴DB" in by_group else "대조 묶음 평균"), "n_pairs": len(pairs),
            "lift_by_group": lift_by_group, "rate_by_group": by_group,
            "n_contrast": len(db), "imitators_removed": len(imitators),
            "own_rate": own_all, "contrast_rate": con_all, "lift_all": la, "own_rate_pairs": own_p, "contrast_rate_pairs": con_p, "lift_pairs": lp,
            "pick": pick, "drop": drop, "pairs": pairs[:30],
            "method": "축 = AXES 키워드(label_rules) 문장 비율 평균, 원본·대조 같은 자. lift=(원본+0.01)/(대조+0.01). 집는 축 lift≥1.25·원본≥0.08, 빼는 축 lift≤0.8·대조≥0.05"}


def _s2(docs, beats_by, contrast) -> dict:
    shapes = Counter(chain_shape([b["node"] for b in beats_by[d["id"]]], 4) for d in docs)
    n = len(docs) or 1
    big = Counter()
    for d in docs:
        nd = _collapse([b["node"] for b in beats_by[d["id"]]])
        big.update(f"{a}>{b}" for a, b in zip(nd, nd[1:]))
    tb = sum(big.values()) or 1
    r_own = Counter(chain_shape(features(d["text"])["nodes"], 3) for d in docs)
    r_con = Counter(chain_shape(features(c["text"])["nodes"], 3) for c in contrast)
    nc = max(1, len(contrast))
    ranked = sorted(r_own, key=lambda s: -(r_own[s] / n) / ((r_con.get(s, 0) + 1) / (nc + 1)))
    top3, cov = [], 0
    for s in ranked:
        if (r_own[s] / n) <= (r_con.get(s, 0) / nc):
            continue
        top3.append(s)
        cov += r_own[s]
        if cov / n >= 0.8:
            break
    return {"shapes": [{"shape": s, "share": round(c / n, 3)} for s, c in shapes.most_common(8)],
            "node_bigrams": [{"pair": k, "share": round(v / tb, 3)} for k, v in big.most_common(10)],
            "starts": dict(Counter(_collapse([b["node"] for b in beats_by[d["id"]]])[0] for d in docs if beats_by[d["id"]]).most_common()),
            "ends": dict(Counter(_collapse([b["node"] for b in beats_by[d["id"]]])[-1] for d in docs if beats_by[d["id"]]).most_common()),
            "rule_chain3_own": [{"shape": s, "share": round(c / n, 3), "contrast_share": round(r_con.get(s, 0) / nc, 3)} for s, c in r_own.most_common(10)],
            "chain_top3": top3, "chain_top3_cover": round(cov / n, 3)}


def _s3(docs, labs) -> dict:
    idx = []
    for d in docs:
        lab = labs.get(d["id"]) or {}
        idx.append({"id": d["id"], "views": d.get("views"), "item": lab.get("item") or d.get("title", "")[:30], "category": lab.get("category"),
                    "price_band": lab.get("price_band"), "install": lab.get("install"), "match_kw": lab.get("match_kw") or [],
                    "hook_type": lab.get("hook_type"), "text": d["text"]})
    return {"keys": ["category", "install", "price_band", "match_kw"], "weights": {"category": 3, "install": 2, "price_band": 1, "match_kw": 1},
            "index": idx, "category_count": dict(Counter(x["category"] for x in idx).most_common()),
            "install_count": dict(Counter(x["install"] for x in idx).most_common())}


def _judge_fit(docs, contrast, speech, s1, s2) -> dict:
    # 축 중심 = 원본 축 비율 평균(원본 편 점수는 자기 빼고 잰 중심 = LOO)
    F = [features(d["text"]) for d in docs]
    vecs = {"axis_centroid": [dict(f["axes_sent"]) for f in F], "ending_centroid": [_ending_vec(f["endings"] or ["기타"]) for f in F],
            "node_centroid": [_node_vec(f["nodes"]) for f in F]}

    def mean_vec(rows):
        ks = {k for r in rows for k in r}
        return {k: round(sum(r.get(k, 0) for r in rows) / max(1, len(rows)), 4) for k in sorted(ks)}
    core = {"ending_list": speech["ending_list"], "ending_char_set": speech["ending_char_set"], "foreign_endings": speech["foreign_endings"],
            "chain_top3": s2["chain_top3"]}
    core.update({k: mean_vec(v) for k, v in vecs.items()})
    own_vecs = []
    for i, d in enumerate(docs):                      # 원본 편은 자기를 뺀 중심으로 잰다(LOO)
        c_i = dict(core, **{k: mean_vec(v[:i] + v[i + 1:]) for k, v in vecs.items()})
        own_vecs.append(_judge_vec(d["text"], c_i))
    con_vecs = [_judge_vec(c["text"], core) for c in contrast]
    groups = defaultdict(list)                       # 대조는 채널(묶음)마다 같은 무게 — 발굴 DB 1,868편이 4채널 38편을 덮지 않게
    for c, v in zip(contrast, con_vecs):
        groups[c["chan"] if c["src"] != "db" else "발굴DB"].append(v)

    def con_rate(pred):
        return st.mean(sum(1 for x in g if pred(x)) / len(g) for g in groups.values()) if groups else 0.0
    def fit_range(k, need):
        v = [x[k] for x in own_vecs]
        los = sorted({round(_q(v, p), 3) for p in (0, .03, .05, .1, .15)})
        his = sorted({round(_q(v, p), 3) for p in (1, .97, .95, .9, .85)})
        best = (-9.0, [min(v), max(v)])
        for lo in los:
            for hi in his:
                if hi < lo:
                    continue
                oi = sum(lo <= x <= hi for x in v) / len(v)
                if oi < need:
                    continue
                j = oi - con_rate(lambda x, lo=lo, hi=hi: lo <= x[k] <= hi)
                if j > best[0] + 1e-9:
                    best = (j, [lo, hi])
        return best
    rng, wts, power = {}, {}, {}
    for k in JUDGE_FEATS:                            # 특징마다 범위 = 원본 ≥85% 안에 두면서 (원본 안 − 대조 안) 최대
        j, r = fit_range(k, 0.85)
        rng[k], power[k], wts[k] = r, round(j, 3), round(max(0.05, j), 3)
    hard = list(JUDGE_HARD)
    for k in hard:                                   # 필수 특징은 원본 ≥95% 를 담는 범위로 다시 잡는다(필수가 원본을 떨어뜨리지 않게)
        rng[k] = fit_range(k, 0.95)[1]

    def score(x):
        tot = sum(wts.values())
        return round(sum(wts[k] * (rng[k][0] <= x[k] <= rng[k][1]) for k in JUDGE_FEATS) / tot, 3)
    def ok(x, t):
        return score(x) >= t and all(rng[k][0] <= x[k] <= rng[k][1] for k in hard)
    own_s = [score(x) for x in own_vecs]
    best = (-9, 0.75)
    for t in sorted(set(own_s)):
        tp = sum(ok(x, t) for x in own_vecs) / max(1, len(own_vecs))
        fp = con_rate(lambda x, t=t: ok(x, t))
        if tp >= 0.9 and tp - fp > best[0]:
            best = (tp - fp, t)
    thr = best[1]
    return {"core": core, "ranges": rng, "weights": wts, "power": power, "threshold": thr, "hard": hard,
            "fit": {"own_pass": round(sum(ok(x, thr) for x in own_vecs) / max(1, len(own_vecs)), 3),
                    "contrast_pass": {g: round(sum(ok(x, thr) for x in v) / len(v), 3) for g, v in groups.items()},
                    "contrast_n": {g: len(v) for g, v in groups.items()}, "own_score": _dist(own_s),
                    "contrast_score": {g: _dist([score(x) for x in v]) for g, v in groups.items()}},
            "method": "특징마다 범위 = 원본 85%(필수 특징은 95%) 이상을 담는 분위 범위 중 (원본 안 비율 − 대조 안 비율, 대조는 묶음별 평균) 최대, 무게 = 그 차이. "
                      "원본 편의 축·어미·사슬 중심은 자기 뺀 평균(LOO). 필수 = JUDGE_HARD(존댓말·특유 어미, 설계로 고정). 문턱 = 원본 통과 ≥90% 중 (원본 통과 − 대조 통과) 최대"}


def build(asr_dir, meta=None, bench=None, contrast_dirs=(), labels_dir=None, exclude=(), channel: str | None = None, out=None) -> dict:
    """(판단 주인) 설명서 만들기 — 원본 받아쓰기(+제미나이 라벨 캐시)와 대조군을 같은 자로 재서 1~5칸·S1·S2·S3·판별기 범위를 낸다.
    asr_dir: Speechmatics asr 폴더 또는 engine 뜯기 폴더 · meta: top50.json · bench: bench.json(per_video 컷) ·
    contrast_dirs: 다른 채널 뜯기 폴더 · 발굴 DB 덤프 json · asr 폴더 · labels_dir: label_llm 캐시 · exclude: 숨길 편(LOO)."""
    docs = [d for d in _own_docs(asr_dir, meta) if d["id"] not in set(exclude)]
    if len(docs) < 5:
        raise ValueError(f"원본 대본 {len(docs)}편 — 5편 미만이면 설명서를 만들지 않는다")
    labs = _llm_labels(labels_dir, [d["id"] for d in docs])
    bench_pv = {}
    if bench:
        b = json.loads(Path(bench).read_text(encoding="utf-8")) if isinstance(bench, (str, Path)) else bench
        bench_pv = b.get("per_video", b)
    contrast = contrast_texts(list(contrast_dirs))
    own_texts = [d["text"] for d in docs]
    imitators = {c["id"] for c in contrast if max((copy_overlap(c["text"], t) for t in own_texts), default=0) >= COPY_MAX}
    contrast_clean = [c for c in contrast if c["id"] not in imitators]
    beats_by, src = {}, Counter()
    for d in docs:
        beats_by[d["id"]], s = _roles_of(d, labs.get(d["id"]))
        src[s] += 1
    speech = _speech(docs, contrast_clean)
    s1 = _s1(docs, labs, contrast, imitators)
    s2 = _s2(docs, beats_by, contrast_clean)
    # 판별기 대조는 같은 형식의 채널 폴더 + 발굴 DB(베낀 글 제외)
    frame = {
        "channel": channel or Path(asr_dir).parent.name,
        "built_by": "tools/calcopy/engine/script_frame.py:build",
        "inputs": {"asr_dir": str(asr_dir), "n_own": len(docs), "excluded": list(exclude), "labeler": dict(src),
                   "llm_models": dict(Counter((labs[v].get("_model") or "?") for v in labs)),
                   "contrast": dict(Counter(c["chan"] if c["src"] != "db" else "발굴DB" for c in contrast_clean)),
                   "imitators_removed": len(imitators)},
        "1_skeleton": _skeleton(docs, beats_by),
        "2_hook": _hooks(docs, labs),
        "3_appeal": _appeal(docs, beats_by),
        "4_speech": speech,
        "5_shot_contract": _shot_contract(docs, labs, beats_by, bench_pv) if bench_pv else {"videos": 0, "by_role": {}},
        "S1_selection": s1,
        "S2_chains": s2,
        "S3_search": _s3(docs, labs),
    }
    frame["judge"] = _judge_fit(docs, contrast_clean, speech, s1, s2)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(frame, ensure_ascii=False, indent=1), encoding="utf-8")
    return frame


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["label", "build"])
    ap.add_argument("--chan", required=True, help="채널 데이터 폴더(asr/ mp4/ top50.json bench_main/)")
    ap.add_argument("--contrast", nargs="*", default=[])
    ap.add_argument("--labels", default=None)
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--channel", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    chan = Path(a.chan)
    labels = Path(a.labels) if a.labels else chan / "script_labels"
    bench = chan / "bench_main" / "bench.json"
    if a.cmd == "label":
        b = json.loads(bench.read_text(encoding="utf-8"))["per_video"]
        for x in json.loads((chan / "top50.json").read_text(encoding="utf-8")):
            d, err = label_llm(chan, x["id"], b.get(x["id"], {}), labels)
            print(x["id"], "ok" if d else f"FAIL {err}", flush=True)
        return 0
    f = build(chan / "asr", chan / "top50.json", bench, a.contrast, labels, tuple(a.exclude), a.channel, a.out)
    print(json.dumps({"n_own": f["inputs"]["n_own"], "judge": f["judge"]["fit"], "threshold": f["judge"]["threshold"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
