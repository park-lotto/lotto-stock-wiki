"""대본 md + 필재 음성 → plan.json(장면·화면·자막 시각). 화면 매핑 = STYLE 표 한 곳.
싱크(10-29 사장님 "자막이랑 음성 속도 안 맞아 / 화면 싱크도"):
- 자막 = 필재 음성의 글자별 실제 발음 시각(타입캐스트 align.json)으로 문장마다 시작·끝을 잡는다(글자 수 비율 추정 금지).
- 한 장면에 영상이 여럿이면 = 나레이션의 기준 구절이 실제로 들리는 순간에 넘긴다(ANCHOR). 기준 구절이 없으면 똑같이 나눈다.
음성 = public/full/sXX.mp3(필재), 정렬 = ALIGN/_sXX_NN.mp3.align.json(조각 순서대로 이어 붙임).
"""
import glob, json, os, re, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
MD = r"C:\Users\TheRose\Desktop\로또의 주식\.tracks\유튜브제작\out\숏클출시강의\데일리_1편_대본_페이블.md"
ALIGN = r"C:\Users\TheRose\AppData\Local\Temp\claude\C--Users-TheRose-Desktop-------\a17fd5ad-08c3-4d3b-8d4a-1f8c5662e159\scratchpad\tc\align"
V2 = r"C:\Users\TheRose\숏템자료\모션그래픽엔진\work\2026-10-29_숏클데일리_v2"
INK = os.path.join(V2, "INK_hq")
T = r"C:\Users\TheRose\숏템자료\여행\hotel_copy"

# 장면 제목 앞부분 → (스타일 이름, 영상들, 둘째 영상부터 넘어가는 기준 구절). 없는 파일은 빠진다.
STYLE = [
    ("오프닝", "공장 실사(흑백) → 결과 격자", [V2 + r"\K_opening_grid\opening_with_factory.mp4"], []),
    ("0 공감", "손그림 → 검색 화면", [INK + r"\P1\out.mp4", V2 + r"\L_youtube_search\out.mp4"], ["자, 보시면"]),
    ("1 문제 인식 ①", "손그림(몇 시간)", [V2 + r"\N_hours_pain\out.mp4"], []),
    ("1 문제 인식 ②", "손그림(천 회 벽)", [INK + r"\P2\out.mp4"], []),
    ("1 문제 인식 ③", "손그림(수익 0원)", [INK + r"\P3\out.mp4"], []),
    ("1 문제 인식 ④", "손그림(남은 건 캡컷)", [INK + r"\P4\out.mp4"], []),
    ("1 문제 인식 ⑤", "손그림(원본 하루 종일)", [INK + r"\P5\out.mp4"], []),
    ("2 일반 해결책", "손그림(갈림길)", [INK + r"\Q1\out.mp4"], []),
    ("2-①", "손그림(직접 만들기)", [INK + r"\Q1\out.mp4"], []),
    ("2-②", "손그림(반자동)", [INK + r"\Q2\out.mp4"], []),
    ("2-③", "숏템메이커 실제 화면", [V2 + r"\B2_shortem_live\out.mp4"], []),
    ("2-④", "손그림(AI 생성·크레딧)", [INK + r"\Q3\out.mp4"], []),
    ("3 한계", "채팅 왕복", [V2 + r"\A2_chat_pingpong\out.mp4"], []),
    ("3.5", "손그림(바라는 것)", [INK + r"\P6\out.mp4"], []),
    ("4 해결 방향", "손그림(시스템+여러 채널)", [INK + r"\Q4\out.mp4"], []),
    ("4.5", "손그림(대리→부장)", [INK + r"\P7\out.mp4"], []),
    ("5 왜 원본", "손그림(돌고 도는 원본)", [INK + r"\P8\out.mp4"], []),
    ("6-① ", "엔진 비교 → 6단계", [V2 + r"\D_split_engine\out.mp4"], []),
    ("6-②", "보물창고 → 348 격자", [V2 + r"\H_grid\out.mp4"], []),
    ("6-③", "폰으로 담기", [V2 + r"\S_phone_capture\out.mp4"], []),
    ("6-④", "클로드 터미널 → 진행판", [V2 + r"\C3_claude_terminal_real\out.mp4", V2 + r"\C2_claude_real\progress_real.mp4",
                                 V2 + r"\F_progress_web\out.mp4"], []),
    ("6-⑤", "보면서 고치기", [V2 + r"\R1_edit_by_pointing\out.mp4"], []),
    # 시험 8번 = DESIGN_batch2 구간표(s22 실제 문장 시각, 초). 숫자 앵커 = 그 초에 넘김
    ("6-⑥", "결과 등장 ×8", [V2 + r"\I1_result_cards\out_A.mp4", V2 + r"\J1_result_vertical\out_A.mp4",
                         V2 + r"\J2_result_flatlay\out_A.mp4", V2 + r"\I2_telegram_arrive\out.mp4",
                         V2 + r"\I1_result_cards\out_B.mp4", V2 + r"\J2_result_flatlay\out_B.mp4",
                         V2 + r"\J1_result_vertical\out_B.mp4", T + r"\숨은계곡_채널2\out.mp4",
                         V2 + r"\K_opening_grid\out_wide_v2.mp4"],
     [10.88, 15.48, 19.60, 24.88, 29.34, 33.36, 36.34, 40.72]),
    ("6-⑦", "원하는 시간에 올리기", [V2 + r"\R2_publish_schedule\out.mp4"], []),
    ("6-⑧", "손그림(일꾼 배분)", [INK + r"\P9\out.mp4"], []),
    ("6-⑨", "채널 리포트", [V2 + r"\G_report\out.mp4"], []),
    ("6-⑩", "손그림(흑백→컬러)", [INK + r"\P10\out.mp4"], []),
    ("6-⑪", "실사(휴대폰 공장 회수)", [r"C:\Users\TheRose\Desktop\숏클_장면샘플\M_휴대폰50대_쇼츠공장_실사.mp4"], []),
    ("7 ", "시청자 질문 → CTA", [V2 + r"\R3_faq_bubbles\out.mp4"], []),
]
# 자막은 대본 표기로 보여 준다(TTS 읽기 표기 → 원래 글자). tts_prep.py READ 표의 역방향.
SHOW = [("투지폰", "2G폰"), ("엘이디", "LED"), ("엠씨피", "MCP"), ("에이아이", "AI"), ("피씨", "PC"), ("티비", "TV")]


def sections():
    text = re.split(r"\n# 쇼츠", open(MD, encoding="utf-8").read())[0]  # 쇼츠 4편은 롱폼에서 뺀다
    for m in re.finditer(r"^## \[(.+?)\][^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        if any(l.startswith(">") for l in m.group(2).splitlines()):
            yield m.group(1)


def chars_of(i):
    out, off = [], 0.0
    for p in sorted(glob.glob(os.path.join(ALIGN, f"_s{i:02d}_*.mp3.align.json"))):
        d = json.load(open(p, encoding="utf-8"))
        for c, s, e in zip(d["characters"], d["character_start_times_seconds"], d["character_end_times_seconds"]):
            out.append((c, s + off, e + off))
        off += d["character_end_times_seconds"][-1]
    return out


def captions(chars):
    """글자 시각 → 문장 자막 [(시작, 끝, 글)]. 문장 끝(.?!) 또는 줄바꿈에서 끊는다."""
    caps, buf, t0 = [], "", None
    for k, (c, s, e) in enumerate(chars):
        if t0 is None and c.strip():
            t0 = s
        buf += c
        nxt = chars[k + 1][0] if k + 1 < len(chars) else "\n"
        if (c in ".?!" and nxt in " \n") or (c == "\n" and buf.strip()) or k == len(chars) - 1:
            t = " ".join(buf.split())
            if t and t0 is not None:
                for a, b in SHOW:
                    t = t.replace(a, b)
                caps.append([round(t0, 2), round(e, 2), t])
            buf, t0 = "", None
    return caps


def find_t(chars, phrase):
    text = "".join(c for c, _, _ in chars)
    i = text.find(phrase)
    return round(chars[i][1], 2) if i >= 0 else None


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout)


def main():
    os.makedirs(os.path.join(HERE, "public", "sv"), exist_ok=True)
    plan = []
    for i, name in enumerate(sections()):
        sec = dur(os.path.join(HERE, "public", "full", f"s{i:02d}.mp3"))
        label, vids, anchors = "미정", [], []
        for key, lab, vv, an in STYLE:
            if name.startswith(key.strip()):
                label, vids, anchors = lab, [v for v in vv if os.path.exists(v)], an
                break
        ch = chars_of(i)
        starts = [0.0]
        for k in range(1, len(vids)):
            a = anchors[k - 1] if k - 1 < len(anchors) else None
            t = a if isinstance(a, (int, float)) else (find_t(ch, a) if a else None)
            starts.append(t if t is not None else round(sec * k / len(vids), 2))
        vs = []
        for k, v in enumerate(vids):
            dst = f"sv/s{i:02d}_{k}.mp4"
            shutil.copyfile(v, os.path.join(HERE, "public", dst))
            vs.append({"src": dst, "sec": round(dur(v), 2), "at": starts[k]})
        plan.append({"i": i, "name": name, "style": label, "sec": round(sec, 2), "caps": captions(ch), "vids": vs})
        print(f"{i:02d} {sec:6.1f}s 자막{len(plan[-1]['caps']):3d} 영상{len(vs)} {[v['at'] for v in vs]} {name}", flush=True)
    json.dump(plan, open(os.path.join(HERE, "public", "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TOTAL", round(sum(p["sec"] for p in plan) / 60, 2), "min")


main()
