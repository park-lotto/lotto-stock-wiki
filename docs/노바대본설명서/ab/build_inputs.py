"""소재 2개(유리 페인트·밀착랩)의 비교 입력을 만든다 — 근거(f1…) + 장면 목록(P3 형식 재료).
장면 = 실제 완성본 4편(영상_1·2·4·5)의 샷(원본 클립·시작 초·장면 설명)을 원본 클립별 묶음으로. 설명은 제작 때 사람이 눈으로 적은 것 그대로.
사용: py build_inputs.py   → inputs/glasspaint.json, inputs/wrap.json"""
import hashlib, json, os

W = r"C:/Users/TheRose/Desktop/쇼츠AI_작업"
HERE = os.path.dirname(os.path.abspath(__file__))
SEG_SEC = 2.0   # 장면 조각 길이 — 라이브는 장면 전환으로 자른 조각(보통 1~4초). 여기선 샷 설명 단위라 2초로 둔다(보고에 적음)


def raw_map():
    m = {}
    for d in ("_공유_소재/clips_raw", "_공유_소재2/clips_raw"):
        for f in os.listdir(os.path.join(W, d)):
            m[hashlib.md5(open(os.path.join(W, d, f), "rb").read()).hexdigest()] = f[:-4]
    return m


def scenes(projects):
    rm = raw_map()
    seen, out = set(), []
    for p in projects:
        prod = os.path.join(W, p, "_제작자료")
        plan = json.load(open(os.path.join(prod, "plan_v1.json"), encoding="utf-8"))
        meta = json.load(open(os.path.join(prod, "work_v1", "meta.json"), encoding="utf-8"))
        cm = {k: rm[hashlib.md5(open(os.path.normpath(os.path.join(prod, v["path"])), "rb").read()).hexdigest()]
              for k, v in plan["clips"].items()}
        why = meta.get("shot_why") or {}
        for i, s in enumerate(meta["shots"]):
            clip, t = cm[s[0]], round(float(s[1]), 1)
            desc = str(why.get(str(i), "")).replace("★", "").replace("훅:", "").replace("불편:", "").replace("CTA:", "").strip()
            if (clip, t) in seen or not desc:
                continue
            seen.add((clip, t))
            out.append({"clip": clip, "t": t, "desc": desc})
    groups, segs, texts = {}, {}, {}
    for n, sc in enumerate(sorted(out, key=lambda x: (x["clip"], x["t"])), 1):
        cid = "s%02d" % n
        segs[cid], texts[cid] = SEG_SEC, sc["desc"]
        groups.setdefault(sc["clip"], []).append(cid)
    return {"groups": [{"name": "원본 %s" % k, "ids": v} for k, v in groups.items()], "segs": segs, "texts": texts,
            "src_of": {c: next(s for s in out if s["desc"] == texts[c]) for c in texts}}


def main():
    os.makedirs(os.path.join(HERE, "inputs"), exist_ok=True)
    res = json.load(open(os.path.join(W, "_대본비교_유리페인트", "research_glasspaint.json"), encoding="utf-8"))
    g = {"key": "glasspaint", "product": "창문에 바르는 젖빛 유리 페인트", "source_title": "유리 페인트", "kind": "홈템",
         "missing": ["사무실 유리 장면", "바깥에서 집 안이 안 보이는 장면"],
         "facts": [{"id": "f%d" % (i + 1), "text": f["text"], "url": f.get("url", "")} for i, f in enumerate(res["facts"])]}
    g.update(scenes(["영상_4_썰쇼핑형", "영상_5_인스타쇼핑형"]))
    # 밀착랩 — 소재 설명란(zlGE_YHGySc)과 클립에서 확인한 것만. 카탈로그 `_공유_소재/공유_클립_카탈로그.md` 참고
    S = "https://www.youtube.com/watch?v=zlGE_YHGySc"
    w = {"key": "wrap", "product": "꾹 누르면 붙는 밀착 랩", "source_title": "제조사도 예상 못 한 랩의 뜻밖의 활용법", "kind": "홈템",
         "missing": ["아기 식판(이유식) 장면", "나무 그릇·종이 접시 근접 장면", "일반 랩이 미끄러지는 비교 장면"],
         "facts": [
             {"id": "f1", "text": "손으로 꾹 누르기만 하면 그 자리에 착 붙는다. 나무 그릇·종이 접시처럼 마른 표면에도 눌러서 붙인다(소재 설명란).", "url": S},
             {"id": "f2", "text": "페인트칠할 때 테이프 대신 붙였다 떼면 경계선이 깔끔하게 남는다(소재 설명란, 코스트코 활용 영상에서 확인).", "url": S},
             {"id": "f3", "text": "여행 갈 땐 신발을 통째로 싸서 가방에 넣는다(소재 설명란, 코스트코 활용 영상에서 확인).", "url": S},
             {"id": "f4", "text": "이유식 먹일 땐 식판에 붙였다가 그대로 떼어 낸다(소재 설명란 — 장면 없음).", "url": S},
             {"id": "f5", "text": "가격이 좀 있는 편이라 꼭 필요할 때 한 장씩 아껴 쓴다(소재 설명란).", "url": S},
             {"id": "f6", "text": "코스트코 활용 영상(Quick & Easy The Costco Way)에서 소개된 제품이다.", "url": "https://www.youtube.com/watch?v=3LBie-y-x40"},
             {"id": "f7", "text": "제조사 광고 영상에서 랩을 씌우고 꾹 누른 과일 그릇을 거꾸로 들어도 쏟아지지 않는다.", "url": "https://www.youtube.com/watch?v=lic7OMPANw4"},
             {"id": "f8", "text": "음식 그릇·주스 컵·고기 냉동 포장 등 주방 밀봉에 쓰는 랩이다(사용 영상).", "url": "https://www.youtube.com/watch?v=3LBie-y-x40"},
         ]}
    w.update(scenes(["영상_1_썰쇼핑형", "영상_2_인스타쇼핑형"]))
    for d in (g, w):
        json.dump(d, open(os.path.join(HERE, "inputs", d["key"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(d["key"], "근거", len(d["facts"]), "· 장면", len(d["texts"]), "· 묶음", len(d["groups"]))


if __name__ == "__main__":
    main()
