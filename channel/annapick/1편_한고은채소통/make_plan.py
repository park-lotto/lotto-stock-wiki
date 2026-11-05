# -*- coding: utf-8 -*-
# _deprecated_2026-10-25 → tools/calcopy/hybrid/styles/안나픽판.json (관제 263 지시서 07 · 표준 §3-1: 새 편은 공용 렌더러로. 읽기 전용 참고물 — 설명서 프리셋 생성기는 회원 옛 길이 결과를 읽으므로 지우지 않는다)
"""얜샷템 2편(안나픽 벤치 itYwQVyuCcc) 한고은 채소 보관통 — 대본.json·재료.json 을 이 표 한 곳에서 만든다 (관제 097, 2026-10-17).
    PYTHONUTF8=1 py channel/annapick/1편_한고은채소통/make_plan.py
원본 = 고은언니 한고은 LcQv9yOh3Wc(2026-03-26, 1920x1080 29.97) 한 편. 원음 = 한고은 본인 말만(받아쓰기 3회 1명), 나머지 = 우리 나레 2줄.
시각은 나레 9.0자/초 추정(TTS 전) — TTS(일레븐랩스 미나) 뒤 나레 줄 길이만 실측으로 바꾸고 원음 조각은 그대로.
판단 주인: 컷·크롭·원음 구간 = 아래 BLOCKS 표 하나. 대본.json·재료.json 은 여기서만 쓴다(손으로 고치지 않는다)."""
import json
from pathlib import Path

D = Path(__file__).resolve().parent
SRC = "hge_LcQv9yOh3Wc.mp4"
URL = "https://www.youtube.com/watch?v=LcQv9yOh3Wc"
DATE = "고은언니 한고은 유튜브 2026.03.26"
NARR_CPS = 8.4      # 만템 나레 8.4자/초(얜샷템 결) — TTS 전 추정에만 씀
LEAD = 0.10         # 블록 사이 쉼(나레↔원음)
# TTS 실측(10-17): 미나 1회 narr_mina.mp3(7.76초, 1.0) → atempo 1.55 narr_t155.wav(5.00초). 말 구간 = N1 0.00~1.95 · N2 2.20~5.00
NARR_SLICE = {"N1": [0.00, 1.95], "N2": [2.20, 5.00]}

# 원음 조각: 원본 [시작, 끝] — 자동자막 낱말 시각 + silencedetect(−30dB) + 받아쓰기 3회(근거.md §2)
# 캡션 조각: (원본 시각, 글) — 원본 자동자막 낱말 시작 시각
BLOCKS = [
    {"id": "H", "kind": "원음", "span": [780.62, 783.72], "said": "정말 난 너무 놀랬어. 한 달, 두 달이 가도 너무 신선해요.",
     "caps": [(780.62, "정말 난 너무 놀랬어"), (781.95, "한 달, 두 달이 가도"), (783.05, "너무 신선해요")],
     "cuts": [dict(ss=751.06, crop=[520, 0, 840, 840], ours="검은 쟁반 위 상추·로메인 더미(한고은 손·노란 소매가 위에서 잎을 만짐)",
                   why="훅 원음 '한 달 두 달이 가도 너무 신선해요' ↔ 싱싱한 잎 더미. 원본 자막 '[푸릇푸릇]'(y861~)·아래 자막(y900~) 밖", audio_ss=780.62)]},
    {"id": "N1", "kind": "나레", "text": "한고은의, 1킬로 채소 보관법이라는데.",
     "tts": "한고은의 일 킬로 채소 보관법이라는데.", "facts": ["f1"],
     "caps": ["한고은의 1킬로", "채소 보관법이라는데"],
     "cuts": [dict(ss=745.10, crop=[525, 0, 860, 860], ours="부엌에서 비닐봉지째 온 샐러드 채소를 꺼내 드는 한고은",
                   why="'1킬로 채소 보관법' — 본인 말 746.9 '유러피안 샐러드 1kg 하면 요렇게 와요'와 같은 샷. 아래 자막(y915~) 밖", mute=True)]},
    {"id": "O2", "kind": "원음", "span": [763.30, 771.90], "said": "이렇게 갑자기 많은 양을 구매를 하면 이거 금방 상하지 않나요라고 가장 걱정을 하시더라고요. 저도 그게 항상 가장 고민이었어요.",
     "caps": [(763.30, "이렇게 갑자기"), (764.72, "많은 양을 구매를 하면"), (766.28, "이거 금방 상하지 않나요"), (767.52, "라고 가장 걱정을"),
              (768.84, "하시더라고요"), (769.48, "저도 그게 항상"), (770.84, "가장 고민이었어요")],
     "cuts": [dict(ss=763.30, crop=[500, 0, 850, 850], ours="상추·로메인 근접(많은 양)", why="'갑자기 많은 양을 구매를 하면' 원음과 같은 샷(원본 컷 763.16~766.23). '[궁금할 수 있어]'(y864~) 밖", sync=True),
              dict(ss=766.23, crop=[675, 0, 690, 690], ours="부엌 카운터 뒤에서 말하는 한고은(허리 위)", why="'금방 상하지 않나요…걱정을 하시더라고요' 같은 샷. 왼쪽 아래 댓글 말풍선(y696~) 밖", sync=True),
              dict(ss=769.40, crop=[545, 0, 860, 860], ours="두 손을 펴며 말하는 한고은", why="'저도 그게 항상 가장 고민이었어요' 같은 샷. 주황 자막(y880~) 밖", sync=True)]},
    {"id": "N2", "kind": "나레", "text": "TV에서 우연히 알게 된, 물 빠지는 채반, 보관통이라네요.",
     "tts": "티비에서 우연히 알게 된 물 빠지는 채반 보관통이라네요.", "facts": ["f2", "f3"],
     "caps": ["TV에서 우연히 알게 된", "물 빠지는 채반", "보관통이라네요"],
     "cuts": [dict(ss=776.95, crop=[520, 0, 880, 880], ours="구멍 뚫린 스텐 채반을 기울여 보여주는 손(노란 소매)", why="'물 빠지는 채반' — 776.4 본인 말 '이렇게 보시면 배수구 물 안 닿게'와 같은 샷. 아래 자막(y924~) 밖", mute=True),
              dict(ss=803.76, crop=[260, 0, 840, 840], ours="수돗물 아래 채반째 채소를 씻는 손(노란 소매)", why="'보관통이래요' — 채반에 담아 씻는 쓰임. 주황 자막(y870~) 밖", mute=True)]},
    {"id": "O5", "kind": "원음", "span": [788.18, 793.52], "said": "그냥 보관을 하셔서 먹고 싶을 때 씻어서 하셔도 되고. 저는 씻어서 보관해요. 귀찮으니까.",
     "caps": [(788.24, "그냥 보관을 하셔서"), (789.36, "먹고 싶을 때"), (790.40, "씻어서 하셔도 되고"), (791.72, "저는 씻어서 보관해요"), (792.80, "귀찮으니까")],
     "cuts": [dict(ss=788.18, crop=[560, 0, 840, 840], ours="상추 담은 통에 투명 뚜껑을 덮는 손(노란 소매)", why="'그냥 보관을 하셔서…씻어서 하셔도 되고' 같은 샷. '[이거 진짜 꿀팁이야]'(y855~) 밖", sync=True),
              dict(ss=791.55, audio_ss=791.62, crop=[710, 200, 715, 715], ours="손사래 치며 말하는 한고은 얼굴", why="'저는 씻어서 보관해요. 귀찮으니까' 같은 샷(입 맞음 — 소리 +0.07초 늦춰 '귀찮으니까' 끝(793.64)까지, 화면은 원본 컷 793.62 전 793.52에서 끊음). 빨간 꾸밈 글 '먹을 때 귀찮아'(792.77~793.62, y92~183)은 y200부터 잘라 뺌(머리 윗부분 조금 잘림)·아래 자막(y924~) 밖", sync=True)]},
]

FACTS = {
    "f1": {"text": "본인 말 745.4~750.4 '어, 인터넷으로 구매를 합니다. 거기에 유러피안 샐러드 1kg 하면 요렇게 와요.'(자동자막 낱말 시각) · 설명란 '일주일에 무려 풀 1kg을 먹는 비결' · 챕터 '12:17 ① 1KG 대용량 샐러드 싱싱하게 보관하는 법'", "url": URL, "kind": "본인 말+설명란"},
    "f2": {"text": "본인 말 772.24~775.6 '그랬는데 알고 한 건 아니에요. 어느 날 TV에서 이걸 팔더라고요.'(받아쓰기 3회 일치)", "url": URL, "kind": "본인 말"},
    "f3": {"text": "본인 말 776.4~780.1 '이렇게 보시면 배수구 물 안 닿게 해 가지고 여기다 보관을 하잖아요' + 화면 776.95~778.5 구멍 뚫린 안쪽 채반·803.8~805 채반째 씻기", "url": URL, "kind": "본인 말+화면"},
}


def main():
    t, lines, orig, caps, shots = 0.0, [], [], [], []
    for b in BLOCKS:
        if b["kind"] == "나레":
            n = len(b["tts"].replace(" ", "").replace(".", "").replace(",", ""))
            sl = NARR_SLICE.get(b["id"]); talk = round(sl[1] - sl[0], 2) if sl else round(n / NARR_CPS, 2)
            dur = round(talk + LEAD, 2)
            lines.append({"fn": b["id"], "text": b["text"], "tts": b["tts"], "facts": b["facts"], "sources": [URL], "est_sec": talk, "slice": sl, "cps": round(n / talk, 2)})
            w = [len(c.replace(" ", "")) for c in b["caps"]]
            a = t
            for c, k in zip(b["caps"], w):
                d_ = (dur - LEAD) * k / sum(w)
                caps.append({"t0": round(a, 2), "t1": round(a + d_, 2), "text": c, "kind": "나레"}); a += d_
            cut_d = [dur] if len(b["cuts"]) == 1 else None
        else:
            a0, a1 = b["span"]; dur = round(a1 - a0 + (LEAD if b is not BLOCKS[-1] else 0), 2)
            orig.append({"after_line": len(lines) - 1, "id": b["id"], "spans": [b["span"]], "dur": round(a1 - a0, 2), "said": b["said"], "t_final": [round(t, 2), round(t + a1 - a0, 2)]})
            for j, (at, c) in enumerate(b["caps"]):
                e = b["caps"][j + 1][0] if j + 1 < len(b["caps"]) else a1
                caps.append({"t0": round(t + max(0, at - a0), 2), "t1": round(t + e - a0, 2), "text": c, "kind": "원음"})
        # 컷 길이: 원음 sync 컷 = 다음 컷 ss 까지(원본 컷 경계), 마지막은 블록 끝 / 나레 컷 = 블록 길이를 계획 비율로
        cs = b["cuts"]
        if b["kind"] == "원음":
            bounds = [c["ss"] for c in cs] + [round(b["span"][0] + dur, 2)]
            if cs[0].get("audio_ss") is not None:      # 화면 다른 곳(B롤) — 소리만 원음
                lens = [dur]
            else:
                lens = [round(bounds[k + 1] - bounds[k] - (b["span"][0] - cs[0]["ss"] if k == 0 else 0), 2) for k in range(len(cs))]
        else:
            # N2: 둘째 컷(803.76~805.06 원본 샷 1.30초) 고정, 첫 컷은 채반 근접 샷 끝(778.54)에서 거꾸로 잰다 — 원본 컷 776.17 전으로는 안 간다
            lens = [dur] if len(cs) == 1 else [round(dur - 1.30, 2), 1.30]
            if len(cs) == 2:
                cs[0]["ss"] = round(778.54 - lens[0], 2)
                assert cs[0]["ss"] >= 776.20, f"N2 첫 컷이 원본 컷 776.17 을 넘는다({cs[0]['ss']}) — 컷을 더 나눠야 함"
        tt = t
        for c, L in zip(cs, lens):
            ss = c["ss"] if not (b["kind"] == "원음" and c is cs[0] and c.get("sync")) else b["span"][0]
            s = {"i": len(shots), "line": b["id"], "src": SRC, "url": URL, "src_date": DATE, "ss": round(ss, 2), "dur": L,
                 "src_span": [round(ss, 2), round(ss + L, 2)], "t_final": [round(tt, 2), round(tt + L, 2)], "kind": "원본재편집", "full": True,
                 "src_crop": c["crop"], "res": "1920x1080", "scale": round(1080 / c["crop"][2], 2), "ours": c["ours"], "why": c["why"]}
            if c.get("mute"):
                s["mute"] = True
            else:
                s["audio_src"] = SRC
                s["audio_ss"] = round(c["audio_ss"] if c.get("audio_ss") is not None else ss, 2)
            shots.append(s); tt += L
        t = round(t + dur, 2)
    total = round(t, 2)
    S = {"topic": "한고은이 샐러드 채소 1kg을 두 달 신선하게 둔다는 채반 달린 스텐 보관통 — '오늘의 PPL 아니지만' 본인이 직접 소개",
         "bench": {"id": "itYwQVyuCcc", "channel": "안나픽", "title": "채소값 확 아끼는 최고의 방법! 한고은 냉장고 속 숨겨진 비밀템은?", "dur": 25.1, "views": 1077305, "upload": "2026-09-23"},
         "our_channel": "얜샷템",
         "titles": {"hook": "샐러드 1kg 사는 한고은의\n두 달 가는 채소 보관통", "source_label": "출처 : 고은언니 한고은",
                    "rule": "1줄 인물·상황 / 2줄 제품 — 벤치 '\"두달 지나도 싱싱해요\" / 한고은 채소보관법'과 다른 말. '두 달 가는' = 본인 말 '한 달, 두 달이 가도 너무 신선해요'"},
         "facts": FACTS,
         "final": {"lines": lines, "orig_audio": orig,
                   "model": "오푸스 손 작성(제미나이 안 씀). 벤치 꼴 = 원음으로 시작 → 4초 전후 나레 1줄(~다는데요) → 원음 … 원음으로 끝. 우리는 나레 2줄(채널 0~2줄 범위).",
                   "check": {"total_sec": total, "narr_chars": [len(l["tts"].replace(" ", "").replace(".", "").replace(",", "")) for l in lines],
                             "orig_sec": round(sum(o["dur"] for o in orig), 2), "orig_share": round(sum(o["dur"] for o in orig) / total, 3), "narr_cps": [l["cps"] for l in lines],
                             "superlative": 0, "numbers": "1킬로(본인 말 1kg)", "english_in_tts": 0,
                             "bench_copy": "벤치 나레 '50대에도 동안을 유지하는 비결이 바로 채소라는 보도'와 겹치는 어절 0"}},
         "captions_plan": caps,
         "notes": ["원음 자막 = 본인 말 그대로(벤치처럼 따옴표 없음 — 얜샷템 틀 자막 꼴을 따른다).", "TTS = 일레븐랩스 미나(사장님 10-17) — 키 확인 대기로 TTS 전 멈춤."]}
    (D / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    import statistics as st
    M = {"_note": "얜샷템 2편(벤치 itYwQVyuCcc) 재료 계획 — TTS·렌더 전. 원본 = 고은언니 한고은 LcQv9yOh3Wc 한 편(1080p). 창 1080x1080(만템 색톤 얜샷템 틀 예정). 나레 시각은 9.0자/초 추정.",
         "cand_dir": "C:/숏템_칼카피/annapick/1편_한고은채소통/src",
         "narration": "일레븐랩스 미나(kr-mina, voice_id aiUUgjHa4mpHf6UenZuf, eleven_v3, 속도 1.35) — 벤치 나레 여성",
         "sources": {"LcQv9yOh3Wc": {"채널": "고은언니 한고은", "제목": "편식하던 남편도 -20kg 감량시킨 한고은 부부가 아침에 먹는 것 (샐러드 1kg, 부부레시피)", "업로드": "2026-03-26", "해상도": "1920x1080 29.97", "길이": 1123.06,
                                     "주의": "같은 영상 8:49~11:55 셀로닉스 오메가3 유료 광고 구간 — 안 씀(쓴 구간 745~806 은 광고 아님, 본인 말 '오늘의 PPL 아니지만' 784.0)"}},
         "source_audio": {"keep": True, "note": "원음 = 한고은 본인 말만(받아쓰기 3회 1명). 원본 RMS −20~−24 dBFS(B14 −35dB 기준 위)."},
         "shots": shots,
         "check": {"total": total, "bench": 25.1, "ratio": round(total / 25.1, 3), "n_shots": len(shots), "shot_median": st.median([s["dur"] for s in shots]),
                   "bench_cut_median": 2.17, "max_scale": max(s["scale"] for s in shots), "orig_share": S["final"]["check"]["orig_share"], "orig_share_rule": [0.61, 1.0],
                   "cap_max_chars": max(len(c["text"].replace(" ", "")) for c in caps), "narr_cps_est": NARR_CPS, "sources_used": [DATE]}}
    (D / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(M["check"], ensure_ascii=False))
    for s in shots:
        print(s["i"], s["line"], s["ss"], s["dur"], s["t_final"], s["src_crop"], "mute" if s.get("mute") else f"audio {s['audio_ss']}")
    for c in caps:
        print(f"  {c['t0']:6.2f}-{c['t1']:6.2f} {c['kind']} {c['text']}")


if __name__ == "__main__":
    main()
