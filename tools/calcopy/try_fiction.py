# -*- coding: utf-8 -*-
"""픽션 썰(A) 시험 — 조사 없이 제품 영상 장면에서 기능만 뽑고, 서사 틀에 기능을 사건으로 배정해 이야기를 지어낸다(버텍스).
서버: cd /tmp/banggu_pkg && (환경 실어서) python3 try_fiction.py --want 3 --max-jobs 6 --out /tmp/fiction.json

틀(1개, Whispered Tales 원본 2편에서 뽑음): "윗선 반대 vs 실무자 집착"
  성립 조건(코드가 판정): '과한 기능' 2개 이상 + 반전에 쓸 다른 기능 1개 이상. 안 맞으면 그 제품은 쓰지 않는다(억지 방지).
  사건 배정(코드): 폭주1·폭주2 = 과한 기능 / 대사 = 남은 기능 / 반전 = 가장 센 남은 기능.
쓰기(모델): 문장 전부. 원본 전문을 본보기로. 실명 회사 금지. 기능·숫자는 재료에 있는 것만.
검사(코드): 배정 기능이 그 줄에 들어갔나 · 실명 · 없는 숫자 · 원본 베낌 → 1회 고쳐 쓰기.
"""
import argparse, json, re, sqlite3, sys, time
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

ORIGINALS = """[원본 1 — 160만 조회]
가구공장 사장이 개발팀한테 당황했던 이유
최근 한 하이엔드 브랜드 제조사가 극강의 오피스 체어를 만드는데 원가 따지지 말고 만들어 보라고 했더니
개발팀이 진짜 미친 짓을 해버린 건데
엉덩이 밑에 4000RPM 쿨링팬을 박아버리더니 앉으면 알아서 바람이 나오는 미친 센서를 넣어버렸다는 거
사장님 "아니 팬까지 넣으면 가격이 어떻게 해?" 라고 하자
"허리 뒤에 전동 모터도 넣었는데요?" 라며 괴물 의자를 완성해버림
근데 진짜 소름 끼치는 반전은 자세 바꿀 때마다 등받이랑 헤드레스트가 모터로 실시간 추종해주니까
하루 종일 앉아있어도 허리가 호강한다고

[원본 2 — 232만 조회]
OO 내부에서도 난리 났다는 폴더블의 미친 속사정
원래 회사는 기존 폴더블 라인업만 유지하려 했는데
개발팀 한 엔지니어가 "가로로 넓은 화면 안 만들면 올해 경쟁사한테 다 빼앗깁니다!" 하며 원가를 무시한 채 강행해버린 거임
이에 당황한 경영진이 "아니 부품 단가는 어떡할 거냐고!" 쏘아붙이자
"어차피 우리가 만드는 디스플레이 똑같이 얹어서 싹 다 찍어내면 단가 떡락해요" 라는 미친 한 수를 던져버렸다는 거
진짜 소름 돋는 포인트는 화면이 가로로 넓어져 영상 볼 때 몰입감이 미쳐버린다고"""

FEAT_PROMPT = """아래는 한 제품을 찍은 영상들의 장면 태깅이다. 이 제품의 기능을 5~8개 뽑아라. 화면에 보이는 것만, 지어내지 마라.
기능마다 성격을 하나 정한다:
  과한 기능  : "이걸 굳이 여기까지?" 싶은 고급·과잉 스펙(모터·센서·팬·특수소재·자동화 등). 평범한 기본 기능은 아니다.
  불편 해결  : 누구나 겪는 일상 불편을 없앰
  뜻밖의 쓰임 : 원래 용도와 다른 쓰임
  가격 이점  : 값·유지비 이점
  기본       : 그 밖의 평범한 기능
power(0~10): 보는 사람이 "오?" 할 세기.
출력 JSON: {"product_kind": "제품 종류 낱말 하나", "feats": [{"id": "f1", "text": "기능 한 줄", "type": "과한 기능|불편 해결|뜻밖의 쓰임|가격 이점|기본", "power": 7, "cuts": ["장면번호"]}]}

[제품] %s
[장면 태깅 — 번호 | 화면 | 용처 | 특징]
%s"""

WRITE_PROMPT = """너는 쇼핑 쇼츠 '썰' 작가다. 아래 [원본] 두 편은 수백만 조회가 난 대본이다. 이 **말맛·호흡·대사 주고받기**를 따라 새 이야기를 지어라.

이야기 틀: 윗선(사장·경영진)은 반대하거나 걱정하고, 실무자(개발팀·엔지니어)는 집착해서 과하게 만들어 버린다. 대사를 주고받다가 마지막에 반전.
사건 순서와 칸마다 **반드시 넣을 기능**은 정해져 있다(바꾸지 마라):
%s

지킬 것
- 등장인물(누가 반대하고 누가 고집하나), 대사, 비유, 문장은 네가 새로 지어라. 원본 문장을 그대로 쓰지 마라.
- ★실제 회사·브랜드·인물 이름을 쓰지 마라("한 제조사", "개발팀", "사장님"처럼). 이 이야기는 지어낸 썰이다.
- 기능·숫자·가격은 [기능]에 있는 것만. 없는 숫자를 만들지 마라.
- 대사는 큰따옴표로. 대사 줄에도 그 칸의 기능이 들어가야 한다(기능 없는 감정 대사만 쓰지 마라).
- 반말 썰체(~는데 / ~는 거 / ~버림 / ~다고). 보는 사람에게 사라고 하지 마라. 8~10줄, 공백 빼고 180~260자.

출력 JSON: {"title": "첫 줄(훅)", "lines": [{"beat": "칸 이름", "text": "한 줄", "feat": "f번호 또는 빈칸"}]}

[원본]
%s

[제품 종류] %s
[기능]
%s
%s"""

BRANDS = r"삼성|애플|LG|엘지|샤오미|다이슨|필립스|소니|나이키|아디다스|이케아|다이소|쿠팡|오뚜기|농심|삼양|팔도|테슬라|구글|아마존|현대|기아"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--want", type=int, default=3); ap.add_argument("--max-jobs", type=int, default=6)
    ap.add_argument("--out", default="/tmp/fiction.json"); ap.add_argument("--scan", type=int, default=150); ap.add_argument("--products", default="")
    a = ap.parse_args()
    from google.genai import types
    from shopping_shorts import backbone_assemble as ba, config, usage_meter, vertex_route
    import seedflow as sf
    calls = {"n": 0}

    def call(prompt):
        def _vx(cl, m):
            return cl.models.generate_content(model=m, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json")).text
        for wait in (0, 10, 25):
            time.sleep(wait)
            ok, got = vertex_route.try_call("script_generate", _vx, what="픽션썰시험")
            if ok:
                calls["n"] += 1
                return sf.parse(got or "")
        raise RuntimeError("버텍스 호출 실패")

    c = sqlite3.connect("file:%s?mode=ro" % config.DB_PATH, uri=True); c.row_factory = sqlite3.Row
    rows = c.execute("select job_id, extract_json, backbone_main from mix_jobs where extract_json is not null and length(extract_json) > 2000 order by created_at desc limit ?", (a.scan,)).fetchall()
    res, seen, tried = [], set(), 0
    with usage_meter.track(op="대본시험", customer_id=0):
        for r in rows:
            if len(res) >= a.want or tried >= a.max_jobs:
                break
            try:
                srcs = ba.sources_from_extract(json.loads(r["extract_json"]))
            except Exception:      # noqa: BLE001
                continue
            seed = ba.seed_source(srcs, r["backbone_main"]) if srcs else None
            product = (((seed or {}).get("source_brief") or {}).get("product") or "").strip()
            want_p = [x.strip() for x in a.products.split(",") if x.strip()]
            if not product or product in seen or (want_p and product not in want_p) or product in ("와플 메이커", "팔도 만능 비빔장", "확장형 아일랜드 식탁"):
                continue
            seen.add(product); tried += 1
            scenes = [x for s in srcs for x in (s.get("segments") or []) if x.get("seg_id")][:90]
            block = "\n".join("[%s] %s | %s | %s" % (x["seg_id"], (x.get("scene_desc") or "")[:70], (x.get("use_point") or "")[:50],
                                                     " / ".join(str(b) for b in (x.get("product_benefits") or [])[:2])) for x in scenes)
            fo = call(FEAT_PROMPT % (product, block))
            feats = [f for f in fo.get("feats") or [] if isinstance(f, dict) and f.get("id")]
            over = sorted([f for f in feats if f.get("type") == "과한 기능"], key=lambda f: -(f.get("power") or 0))
            rest = sorted([f for f in feats if f.get("type") != "과한 기능"], key=lambda f: -(f.get("power") or 0))
            if len(over) < 2 or len(over) + len(rest) < 4:
                print("\n✗ %s — 틀 안 맞음(과한 기능 %d개) → 쓰지 않음" % (product, len(over)))
                res.append({"product": product, "fit": False, "feats": feats}); continue
            twist = (over[2:] + rest)[0] if len(over) > 2 else rest[0]
            talk = [f for f in (rest + over[2:]) if f is not twist][0]
            plan = [("설정", None, "윗선이 정한 방향(원가 무시하고 최고로 / 원래는 평범하게 가려 했다 중 하나)"),
                    ("폭주1", over[0], "실무자가 과하게 넣어버림"), ("폭주2", over[1], "하나 더 넣어버림"),
                    ("대사", talk, "윗선의 걱정 대사 → 실무자의 대답 대사(대답에 이 기능)"), ("반전", twist, "근데 진짜 소름 돋는 건 — 가장 센 기능")]
            plan_txt = "\n".join("  %d. %s — %s%s" % (i + 1, b, d, (" ← 반드시: %s [%s]" % (f["text"], f["id"])) if f else "") for i, (b, f, d) in enumerate(plan))
            feats_txt = "\n".join("  %s (%s) %s" % (f["id"], f.get("type"), f["text"]) for f in feats)
            kind = fo.get("product_kind") or product
            fb, out, bad = "", None, []
            for attempt in range(2):
                out = call(WRITE_PROMPT % (plan_txt, ORIGINALS, kind, feats_txt, fb))
                lines = [L for L in out.get("lines") or [] if (L.get("text") or "").strip()]
                body = " ".join([out.get("title") or ""] + [L["text"] for L in lines])
                bad = []
                for b, f, _ in plan:
                    if f and not any(L.get("feat") == f["id"] for L in lines):
                        bad.append("%s 칸에 기능 %s(%s)이 없다" % (b, f["id"], f["text"][:20]))
                if re.search(BRANDS, body):
                    bad.append("실명 회사·브랜드를 썼다: %s" % ", ".join(sorted(set(re.findall(BRANDS, body)))))
                known = set(re.findall(r"\d+", " ".join(f["text"] for f in feats) + " " + block))
                ghost = sorted({n for n in re.findall(r"\d+", body) if n not in known})
                if ghost:
                    bad.append("재료에 없는 숫자: %s" % ", ".join(ghost))
                cp = sf.gram_share(body, ORIGINALS)
                if cp > 0.25:
                    bad.append("원본 문장을 많이 옮겼다(%.0f%%)" % (cp * 100))
                if not bad:
                    break
                fb = "\n[다시 써라 — 문제]\n" + "\n".join("- " + x for x in bad)
            res.append({"product": product, "fit": True, "feats": feats, "plan": [(b, f["id"] if f else "", d) for b, f, d in plan], "script": out, "problems": bad,
                        "attempts": attempt + 1, "copy": round(sf.gram_share(" ".join(L["text"] for L in out.get("lines") or []), ORIGINALS), 2)})
            print("\n##### %s | 과한 기능 %d개 · 시도 %d · 남은 문제 %d · 원본과 겹침 %.0f%%" % (product, len(over), attempt + 1, len(bad), res[-1]["copy"] * 100))
            for f in feats:
                print("   %s (%s·%s) %s" % (f["id"], f.get("type"), f.get("power"), f["text"]))
            print("  [훅] " + (out.get("title") or ""))
            for L in out.get("lines") or []:
                print("  (%s·%s) %s" % (L.get("beat"), L.get("feat") or "-", L.get("text")))
            for x in bad:
                print("  ! " + x)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n===== 본 제품 %d · 틀 맞음 %d · 문제 없이 쓴 것 %d · 버텍스 호출 %d회" % (len(res), sum(1 for r in res if r["fit"]), sum(1 for r in res if r["fit"] and not r["problems"]), calls["n"]))


if __name__ == "__main__":
    main()
