"""대본 md → 장면별 임시 음성(edge-tts) + plan.json(장면·화면 스타일·영상 파일).
필재 연결되면 이 파일의 TTS 부분만 바꾼다. 화면 매핑 = STYLE 표 한 곳."""
import asyncio, json, os, re, subprocess, sys
import edge_tts

HERE = os.path.dirname(os.path.abspath(__file__))
MD = r"C:\Users\TheRose\Desktop\로또의 주식\.tracks\유튜브제작\out\숏클출시강의\데일리_1편_대본_페이블.md"
V2 = r"C:\Users\TheRose\숏템자료\모션그래픽엔진\work\2026-10-29_숏클데일리_v2"
INK = os.path.join(V2, "INK_hq")

# 장면 제목 앞부분 → (스타일 이름, 영상 후보들). 후보 중 처음 있는 파일을 쓴다. 없으면 자리표시 카드.
STYLE = [
    ("오프닝", "실사+결과 격자", [V2 + r"\K_opening_grid\out_wide_v2.mp4"]),
    ("0 공감", "손그림 → 검색 화면", [INK + r"\P1\out.mp4", V2 + r"\L_youtube_search\out_v3.mp4"]),
    ("1 문제 인식 ①", "손그림(몇 시간)", [V2 + r"\N_hours_pain\out.mp4"]),
    ("1 문제 인식 ②", "손그림(천 회 벽)", [INK + r"\P2\out.mp4"]),
    ("1 문제 인식 ③", "손그림(수익 0원)", [INK + r"\P3\out.mp4"]),
    ("1 문제 인식 ④", "손그림(남은 건 캡컷)", [INK + r"\P4\out.mp4"]),
    ("1 문제 인식 ⑤", "손그림(원본 하루 종일)", [INK + r"\P5\out.mp4"]),
    ("2 일반 해결책", "손그림(갈림길)", []),
    ("2-①", "손그림(직접 만들기)", []),
    ("2-②", "손그림(반자동)", []),
    ("2-③", "실제 화면(숏템메이커)", []),
    ("2-④", "손그림(AI 생성·크레딧)", []),
    ("3 한계", "채팅창 왕복", [V2 + r"\E_waiting\out.mp4"]),
    ("3.5", "손그림(바라는 것)", [INK + r"\P6\out.mp4"]),
    ("4 해결 방향", "손그림(시스템+여러 채널)", []),
    ("4.5", "손그림(대리→부장)", [INK + r"\P7\out.mp4"]),
    ("5 왜 원본", "손그림(돌고 도는 원본)", [INK + r"\P8\out.mp4"]),
    ("6-① ", "엔진 비교 → 6단계", [V2 + r"\D_split_engine\out.mp4"]),
    ("6-②", "보물창고 → 348 격자", [V2 + r"\H_grid\out.mp4"]),
    ("6-③", "폰으로 담기(실제 시연 영상 대기)", []),
    ("6-④", "진행판(웹)", [V2 + r"\F_progress_web\out.mp4"]),
    ("6-⑤", "보면서 고치기(새로 만듦)", []),
    ("6-⑥", "결과 등장 ×8", [V2 + r"\I1_result_cards\out.mp4", V2 + r"\J2_result_flatlay\out.mp4", V2 + r"\J1_result_vertical\out.mp4", V2 + r"\I2_telegram_arrive\out.mp4"]),
    ("6-⑦", "예약 발행 타임라인(새로 만듦)", []),
    ("6-⑧", "손그림(일꾼 배분)", [INK + r"\P9\out.mp4"]),
    ("6-⑨", "채널 리포트", [V2 + r"\G_report\out.mp4"]),
    ("6-⑩", "손그림(흑백→컬러)", [INK + r"\P10\out.mp4"]),
    ("6-⑪", "실사(휴대폰 공장 회수)", [r"C:\Users\TheRose\Desktop\숏클_장면샘플\M_휴대폰50대_쇼츠공장_실사.mp4"]),
    ("7 ", "질문·CTA 카드", []),
]


def sections():
    text = open(MD, encoding="utf-8").read()
    text = re.split(r"\n# 쇼츠", text)[0]  # 쇼츠 4편 대본(# 쇼츠 …)은 롱폼에서 뺀다
    out = []
    for m in re.finditer(r"^## \[(.+?)\][^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        name, body = m.group(1), m.group(2)
        lines = [l[1:].strip() for l in body.splitlines() if l.startswith(">")]
        if lines:
            out.append((name, " ".join(lines)))
    return out


def style_of(name):
    for key, label, vids in STYLE:
        if name.startswith(key.strip()):  # 앞부분만 본다('오프닝 회수' 오매칭 방지)
            return label, [v for v in vids if os.path.exists(v)]
    return "미정", []


async def main():
    os.makedirs(os.path.join(HERE, "public", "full"), exist_ok=True)
    plan = []
    for i, (name, txt) in enumerate(sections()):
        mp3 = os.path.join(HERE, "public", "full", f"s{i:02d}.mp3")
        if not os.path.exists(mp3):
            await edge_tts.Communicate(txt, "ko-KR-InJoonNeural", rate="+15%").save(mp3)
        sec = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3],
                                   capture_output=True, text=True).stdout)
        label, vids = style_of(name)
        plan.append({"i": i, "name": name, "style": label, "videos": vids, "sec": round(sec, 2), "text": txt})
        print(f"{i:02d} {sec:6.1f}s  {label:22s} {len(vids)} {name}", flush=True)
    json.dump(plan, open(os.path.join(HERE, "public", "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TOTAL", round(sum(p["sec"] for p in plan) / 60, 1), "min")


asyncio.run(main())
