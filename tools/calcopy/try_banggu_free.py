# -*- coding: utf-8 -*-
"""말맛 원인 가르기 — 같은 재료(1차 시험이 뽑아 둔 것)로 **쓰는 방법만 바꿔** 다시 쓴다.

1차(칸 채우기+고정 문장+가짜 예시)는 원본보다 고정 문장 2%→18%, 설명서 낱말 0.5→1.8/100자였다(taste_compare.py).
여기서는 ①원본 3편 전문을 말맛 예시로 보여 주고 ②고정 문장을 코드가 붙이지 않고 ③줄 단위로 자유롭게 쓰게 한다.
재료가 같으니 결과가 달라지면 '쓰는 방법' 탓, 그대로면 '재료' 탓이다.
서버: cd /tmp/banggu_pkg && (환경 실어서) python3 try_banggu_free.py --src /tmp/banggu_live.json --out /tmp/banggu_free.json
"""
import argparse, json, sys, time

sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

GOLD = """[원본 1 — 대체형]
제목: 영업기밀을 빼앗겨버린 아웃백
아웃백에서 사람들이 가장 열광한다는 부쉬맨브레드
똑같은 빵을 사서 집에서 먹어보면 의외로 퍽퍽한 노맛에 사람들이 놀라곤 하는데
이 차이는 사실 아웃백에서 쓰는 업소용 오븐에 있었음
아웃백 빵을 못잊은 빵돌이들은 이 맛을 똑같이 재현하기 위해 실험에 실험을 거듭한 결과
빵을 해동 후 전자레인지 30초 돌릴 때 물 한 컵을 같이 넣으면 업소용 오븐처럼 촉촉하게 빵을 데울 수 있다는 것을 발견하게 됨
인터넷에서 사면 개당 500원 수준이라 아웃백에 가야 할 이유가 없어져버렸다고ㅋㅋ

[원본 2 — 숨은 이유형]
제목: 한국에 완벽 로컬라이징 되어버린 텀블러
마치 분신술처럼 두 개로 나눠 쓸 수 있다는 아소부 텀블러
하지만 겉모습 외에는 딱히 특별한 점이 없어 보이는데
뚜껑을 살펴보니 빨대가 찝찝하지 않도록 팝업 형태로 넣어둘 수 있고
뒤집어 흔들어봐도 새지 않는 엄청난 밀폐력을 가졌는데ㄷㄷ
심지어 빨대 끝이 실리콘이라 마지막 음료까지 남김없이 마실 수 있다고 함
그러나 정작 한국인이 꽂힌 순간은 따로 있었는데
그건 바로 출퇴근길 스테인레스에 사골국 담아 다니면 한겨울에도 따땃한 출퇴근이 가능해서라고ㅋㅋ
혼잣말: 아 가방 안에서 안 새는 텀블러를 어떻게 참냐고 ㅋㅋ

[원본 3 — 원리형]
제목: 물감을 전혀 묻힐 수 없는 붓
이 붓을 쓰는 모습을 보면 사람들이 놀라는 부분이 있는데
바로 평범하게 생긴 이 붓이 패드에서 어떻게 써질 수가 있냐는 거
사실 요즘 패드는 전류에 반응하는 정전식 스크린을 사용하는데
붓의 털 부분에 전기가 통하는 전도성 섬유를 사용해 배터리나 부자재 없이도 패드가 붓을 인식하게 만들었다는 거
이런 장점 덕분에 어디에서나 사용할 수 있다는데
심지어 패드에서 붓을 쓸 때 느껴지는 터치감이 펜과는 전혀 다른 쾌감을 전해준다고ㄷㄷ"""

PROMPT = """너는 커뮤니티 썰 쇼츠 채널의 작가다. 아래 [원본] 세 편은 그 채널에서 수백만 조회가 난 대본이다.
이 **말맛·호흡·말끝·줄 길이**를 그대로 따라, [재료]의 제품으로 새 대본 한 편을 써라.

지킬 것
- 원본처럼 **남에게 들은 얘기를 옮기는 말투**다. 줄은 '~는데'로 넘기고 '~다고'·'~음'·'~는 거'로 닫는다. '~다.' '~요.' 로 끝내지 마라.
- 원본의 **줄 순서 꼴**(소개 → 틈 벌리기 → 풀기 → 한 번 더 → 닫기)은 빌리되, **원본 문장을 그대로 쓰지 마라.** 편마다 여는 말이 달라야 한다.
- 설명서 말투(방식·구조·용도·가능·제공·외관)를 쓰지 마라. **눈에 보이는 장면**과 입말로 써라(원본의 '퍽퍽한 노맛' · '분신술처럼' · '따땃한' · '찝찝하지 않도록' 같은 결).
- 제목은 원본처럼 **무슨 일이 벌어졌다는 꼴**이나 말이 안 되는 점을 건다. 제품 종류 낱말로 끝내고 12~20자.
- 사실은 [재료]에 있는 것만. 숫자·나라·'품절'·'1위'를 지어내지 마라. 보는 사람에게 말 걸지 말고, 사라는 말도 하지 마라.
- 본문 6~9줄, 공백 빼고 150~230자. 맨 끝 혼잣말 한 줄(내 감상, ㅋㅋ)은 넣어도 되고 빼도 된다.

출력은 JSON 객체 하나: {"title": "...", "lines": ["...", "..."], "comment": "... 또는 빈 문자열"}

%s

[제품] %s
[이번 갈래] %s
[재료 — 영상에서 인용으로 확인된 것만]
%s%s"""


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", default="/tmp/banggu_live.json"); ap.add_argument("--out", default="/tmp/banggu_free.json")
    a = ap.parse_args()
    from google.genai import types
    from shopping_shorts import usage_meter, vertex_route
    from banggu import material as mat, rules, script, spec

    def call(prompt):
        def _vx(cl, m):
            return cl.models.generate_content(model=m, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json")).text
        for wait in (0, 10, 25, 45):
            time.sleep(wait)
            ok, got = vertex_route.try_call("script_generate", _vx, what="칼카피시험")
            if ok:
                time.sleep(2); return got or ""
        raise RuntimeError("버텍스 호출 실패")

    res = []
    with usage_meter.track(op="대본시험", customer_id=0):
        for j in json.load(open(a.src, encoding="utf-8"))["jobs"]:
            m = (j.get("all_videos") or {}).get("material") or {}
            for s0 in j.get("scripts") or []:
                kind = s0["kind"]; fb = ""; last = None
                for attempt in range(2):
                    try:
                        out = mat.parse(call(PROMPT % (GOLD, j["product"], spec.KIND_KO[kind], script.material_block(m), fb)))
                    except (ValueError, RuntimeError) as e:
                        print("건너뜀", j["product"], e); break
                    s = {"kind": kind, "title": (out.get("title") or "").strip(),
                         "lines": [{"role": "", "text": str(t).strip()} for t in (out.get("lines") or []) if str(t).strip()],
                         "comment": (out.get("comment") or "").strip()}
                    src_all = " ".join(v.get("quote", "") + " " + v.get("text", "") for v in m.values()) + " " + j.get("seed", "")
                    issues = [i for i in rules.lint(s, {"source_text": src_all, "seed_text": j.get("seed", "")}) if i.rule != "bg_number" or True]
                    rej = rules.rejects(issues); last = (s, rej, attempt + 1)
                    if not rej:
                        break
                    fb = rules.feedback(issues)
                if last:
                    s, rej, n = last
                    res.append({"job": j["job"], "product": j["product"], "kind": kind, "attempts": n, "rejects": [list(i) for i in rej], "script": s, "secs": script.seconds(s)})
                    print("\n##### %s · %s · 시도 %d · 남은 반려 %d · %.1f초" % (j["product"], spec.KIND_KO[kind], n, len(rej), script.seconds(s)))
                    print("  [제목] " + s["title"]); [print("  " + L["text"]) for L in s["lines"]]
                    if s["comment"]: print("  [혼잣말] " + s["comment"])
                    for i in rej: print("    ! %s «%s» %s" % (i.rule, i.found, i.why))
    json.dump({"jobs": [{"job": r["job"], "product": r["product"], "scripts": [r]} for r in res]}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
