# -*- coding: utf-8 -*-
"""벤치마킹 단계별 칸 표(관제 319) — 판단 주인 = 이 파일의 STEPS 한 곳.

사장님 11-06: "단계를 정해서 지침서에 나온 걸 하나씩 다 봐야 되는 거 아닌가, 통과하고 / 말로 하니까 이게 안 되는 듯."
Jev(해결 1.00·뿌리 0.86·위험 0.26) → 지침서(`tools/calcopy/칼카피_분석지침서.md`)를 기계가 읽는 칸 표로 옮기고, 흐름 단계 끝마다 그 칸을 전부 검사한다.
Jev 관문 구조 A(해결 0.76·위험 0.26·신뢰 1.00): 재기 = 실행기 bm_gate(measure — 판단 없음) · 판정 = 서버 flow_bench._step_gate(evaluate) ·
  주인 함수가 흐름에서 불리는 칸만 막고, 아직 안 이은 칸(wait)은 '이어야 할 목록'으로 기록한다. 검사 결과가 아예 없으면 멈춘다(조용한 통과 금지).
Jev 잇기 W2(해결 0.50·위험 0.32·신뢰 0.97): rules_of·script_of·palette_of 는 bm_rules 로 잇고, frames_cmd(사람용 0.1초 띠)는 잇지 않는다 —
  회원 흐름의 판독은 agy 가 영상을 직접 보고 eye_frames 가 컷 앞뒤 프레임을 뽑는다(대체 표시 행).

행 칸: id · phase(flow_bench STAGES 키, 없으면 None) · slot(칸 이름) · owner('engine/파일.py:함수' — tools/calcopy 기준) ·
  out(산출물 자리 '경로#키', {ch}=channel/<slug> · {id}=편 · {work}=시험 편 작업 폴더 · '*' 글롭) · check(통과 조건) · doc(지침서 줄) ·
  wait(아직 안 이음 — {kind: 함수|칸, why}) · none(해당 단계 없음 — 이유) · at(그 줄에 있어야 할 글 — 지침서 줄이 밀리면 시험이 잡는다).
check: ("files", k) 파일 k 개 이상 · ("have",) 값 있음(None·'failed' 아님) · ("full",) 비지 않음 · ("lines", r) 줄 중 값 있는 비율 ≥ r ·
  ("slot",) 줄마다 칸이 있음(null·[] 허용 — 없음도 분모) · ("ge", x) 숫자 ≥ x · ("owner",) 주인 함수 안의 판정이 곧 관문(여기서 다시 재지 않는다 — 두 벌 금지).
"""
from __future__ import annotations

import ast
import json
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CAL = ROOT / "tools" / "calcopy"
GUIDE = CAL / "칼카피_분석지침서.md"
GATE_PHASES = ("bm_fetch", "bm_tear", "bm_read", "bm_trial")      # 칸을 재는 단계 끝(그 뒤 단계는 주인 함수의 판정 = bench_match·페이블·묶음이 관문)

_W_ASK = "판독 질문(flow_bench READ_SCHEMA·LINE_SCHEMA·LINE_VOCAB)에 이 칸이 없다 — 질문에 넣어야 채워진다"
_N_HOME = "집 PC kal.py 길(사람·워커 몫) — 회원 벤치마킹 흐름은 flow_bench 단계가 대신한다"
_N_ENGINE = "제작 엔진 구현·적용(축별 B·C) — 벤치 영상에서 재는 칸이 아니다"


_W_EAR = {"kind": "칸", "why": "analyze 가 빈 받아쓰기·제미나이 없음을 failed 로 적는다(나레 없는 채널은 정상 빈 답) — 없음/실패 가르기는 analyze 주인 몫(Jev K2 임시: 신뢰 0.93·위험 0.18·해결 0.20)"}


def R(id, phase, slot, owner, out, check, doc, wait=None, none=None, at=None, note=None):
    return {"id": id, "phase": phase, "slot": slot, "owner": owner, "out": out, "check": tuple(check) if check else None,
            "doc": doc, "wait": wait, "none": none, "at": at, "note": note}


def N(id, doc, why, at=None):
    """해당 단계 없음 행 — 지침서 줄을 버리지 않고 이유를 남긴다."""
    return R(id, None, "", None, None, None, doc, none=why, at=at)


def W(kind, why):
    return {"kind": kind, "why": why}


K = "engine/kal_analyze.py:"
AN = "engine/analyze.py:analyze"
TJ = "{ch}/뜯기/{id}/뜯기.json#"
LR = "{ch}/줄판독/{id}.json#"

STEPS = [
    # ── 머리말·§0 정체성 ─────────────────────────────────────────────
    N("H0", [(1, 14)], "머리말 — 문서 운영 규칙(끝까지 읽기·변경 공유·표준 우선·엔진 순서). 엔진 순서 ①(1차 = 벤치 99%)은 P-match 행이 잰다", at="프리셋 분석 지침서"),
    N("G0", [(16, 21)], "정체성 기준 ①~⑧ 요약·표 머리 — 기준 하나하나는 아래 행(줄마다 센다·띠·숫자·분모·없는 것·미측정·대응·같은 자)", at="## 0. 정체성"),
    R("G0-rule", "bm_read", "효과 붙는 조건 규칙+빈도 k/n", K + "rules_of", "{ch}/_kal/규칙빈도.json#by_speaker", ("full",), [22, 50, 81, 153, 173],
      note="스타일분석.md 손 문서 대신 규칙빈도.json(분모 포함)"),
    R("G0-strip", "bm_read", "0.1초 띠·원본 프레임(전환·0초)", K + "eye_frames", LR + "frame0", ("have",), [23, 80],
      note="frames_cmd(사람용 2fps 시트·10fps 띠) 대체 — 판독자 = agy(영상 직접)·오푸스(컷 앞뒤 프레임). Jev W2 해결 0.50·위험 0.32"),
    R("G0-num", "bm_read", "등장 곡선 숫자(enter_curve)", K + "check_doc", LR + "lines[].enter_curve", ("lines", 1.0), [24, 153, 282],
      wait=W("칸", _W_ASK + " (enter_curve)")),
    R("G0-cps", "bm_read", "타이핑 cps(type_cps)", K + "check_doc", LR + "lines[].type_cps", ("lines", 1.0), [24, 153, 282],
      wait=W("칸", _W_ASK + " (type_cps)")),
    R("G0-hex", "bm_read", "색 hex + 몇 편(팔레트)", K + "palette_of", "{ch}/팔레트.json#roles.본문", ("full",), [25, 81, 153],
      wait=W("칸", "팔레트 입력 fill_hex 가 " + _W_ASK)),
    R("G0-name", "bm_read", "이름 = 화면 글자로 확인된 것만", K + "check_doc", "{ch}/줄판독/{id}.json", ("files", 1), [26, 84, 85, 283],
      note="check_doc NAME_RE — 화면 글자에 없는 이름은 거절"),
    R("G0-eye", "bm_read", "판독 = 눈(오푸스 확정), 기계는 받아쓰기·픽셀", "hybrid/flow_bench.py:bm_read_got", None, ("owner",), [27, 47, 48],
      note="지침서는 '제미나이에게 묻기 = 아마추어'인데 회원 흐름 1차 판독은 agy(제미나이 구독) → 오푸스가 전 줄 확정. 문구와 어긋남 — 보고"),
    R("G0-sfx", "bm_tear", "효과음 고립 후보·표식·우연 기대", AN, TJ + "sfx_rules", ("have",), [28, 146, 183],
      wait=_W_EAR),
    R("G0-narr", "bm_read", "나레 비율(줄 기준)", "hybrid/flow_bench.py:_fill_of", LR + "narr_share", ("have",), [29]),
    R("G0-narr-s", "bm_read", "나레 비율(초 기준)", "hybrid/flow_bench.py:_fill_of", LR + "narr_share_sec", ("have",), [29],
      wait=W("칸", "_fill_of 가 줄 기준만 낸다 — 초 기준 칸 없음")),
    R("G0-see", "bm_confirm", "결과물을 눈으로·같은 자", "hybrid/flow_bench.py:bm_verdict", None, ("owner",), [30, 106, 111]),
    N("G0-map", [31], "측정값→엔진 설정 대응(§4) — 제작 엔진 지원 현황, 벤치 영상에서 재는 칸 아님"),
    R("P-match", "bm_pan", "1차 = 벤치 100% 동일(같은 자 대조)", K + "bench_match", None, ("owner",), [12, 32, 34, 90, 105, 106, 108, 109, (268, 273)],
      note="잡도리가 match_ok 까지 돈다(flow_bench.bm_panbokki)"),
    N("G0-up", [33], "업그레이드 단계 — 1차 통과 뒤(§2-6-1), 벤치마킹 흐름 밖"),
    N("G0-acc", [(35, 38)], "실사고 근거 모음"),
    # ── §1 실행 대본 ─────────────────────────────────────────────
    N("S1", [(40, 43), 45, 46], _N_HOME, at="## 1. 실행 대본"),
    R("S1-tts", "bm_trial", "목소리(시험 편 = 칼카피 흐름 TTS 한 곳)", "engine/voices.py:tts_for", None, ("owner",), [44]),
    R("S1-strict", "bm_read", "줄판독 check --strict 오류 0", K + "check_doc", LR + "lines[].confidence", ("lines", 1.0), [49, 83],
      wait=W("칸", "흐름은 check_doc(strict=False) — strict 칸(role·fit·motion·confidence) " + _W_ASK)),
    R("S1-copy", "bm_tear", "카피 = 뜯기 → 설명서 → 프리셋 저장", "engine/preset_save.py:save", "{ch}/preset/*/manifest.json", ("files", 1), [51, 88, 89, 95]),
    R("S1-pan", "bm_pan", "미달 칸 → 설정 자리 고치고 다시 만들기", "hybrid/flow_bench.py:bm_panbokki", None, ("owner",), [52, 110]),
    N("S1-end", [53, 54], "장부·커밋·세션 알림 — 사람 몫"),
    # ── §2 단계 파이프라인 ─────────────────────────────────────────────
    N("S2", [(56, 60)], "단계 파이프라인 머리(8칸 꼴)", at="## 2. 단계 파이프라인"),
    N("S20", [62, 63], "선정 머리·같은 결 판정(channel_find.judge_same_kind) — 회원이 채널을 준다, 같은 결 판정은 집 PC 선정 몫", at="### 2-0. 선정"),
    R("S20-pick", "bm_fetch", "조회 순 고르기(벤치 편)", "engine/bench_member.py:pick_videos", "src/{id}.mp4", ("files", 2), [64, 65, 66, 68, 69],
      note="0순위-B 보고: 지침서 주인 kal.py:step_select ↔ 회원 흐름 bench_member.pick_videos 두 벌"),
    N("S20-bar", [67], "끝 기준 숫자(구독 대비 조회 ≥1·업로드 빈도) — 지침서 스스로 '미확인·사장님 결정 대기'"),
    N("S20-ask", [70], "물을 것 = 시작 입력(flow.start_bench 이름·채널)"),
    R("S21-get", "bm_fetch", "받기(1080 세로·info.json)", "engine/bench_member.py:fetch", "src/{id}.info.json", ("files", 2), [72, 73, 74], at="### 2-1. 수집"),
    R("S21-size", "bm_tear", "1080×1920(세로 높이 1920)", AN, TJ + "probe.h", ("ge", 1920), [75]),
    R("S21-n", "bm_fetch", "표본 6~8편(규칙 분모 ≥5)", "engine/bench_member.py:pick_videos", "src/{id}.mp4", ("files", 6), [76],
      wait=W("칸", "회원 흐름 기본 3편(bench_member.MAX_VIDEOS·flow n) — 6편 받기는 디스크·시간 결정 필요")),
    R("S21-disk", "bm_setup", "디스크 관문(3GB 미만 거절)", "hybrid/flow_bench.py:bm_env_got", None, ("owner",), [77],
      wait=W("칸", "bm_env_got 이 disk_gb 를 기록만 한다 — 3GB 거절 없음")),
    R("S22-win", "bm_tear", "창(layout.window)", AN, TJ + "layout.window", ("have",), [79, 80, 141, 158], at="### 2-2. 분석"),
    R("S22-band", "bm_tear", "자막 띠(layout.caption_band)", AN, TJ + "layout.caption_band", ("have",), [80, 153]),
    R("S22-cap", "bm_tear", "자막 줄(OCR items)", AN, TJ + "captions.items", ("full",), [80]),
    R("S22-cuts", "bm_tear", "컷 시각(cuts.times)", AN, TJ + "cuts.times", ("have",), [80, 142, 163]),
    R("S22-font", "bm_tear", "글꼴 후보", AN, TJ + "fonts.top3", ("full",), [80, 94, 140, 153]),
    R("S22-lufs", "bm_tear", "통합 음량 LUFS(audio.bench.I)", AN, TJ + "audio.bench.I", ("have",), [80, 146, 183]),
    R("S22-tp", "bm_tear", "트루피크(audio.bench.TP)", AN, TJ + "audio.bench.TP", ("have",), [80, 146, 183]),
    R("S22-lra", "bm_tear", "음량 범위(audio.bench.LRA)", AN, TJ + "audio.bench.LRA", ("have",), [80, 146, 183]),
    R("S22-skel", "bm_read", "줄판독 뼈대(기계값)", K + "skeleton", "{ch}/줄판독_뼈대/{id}.json", ("files", 1), [80, 284], at="analyze.analyze"),
    R("S22-script", "bm_read", "어미·말꼴·자수(대본 언어)", K + "script_of", "{ch}/_kal/대본언어.json", ("files", 1), [81, 82, 145, 178]),
    R("S22-enter", "bm_read", "등장 어휘 정규화(enter_key)", K + "enter_key", "{ch}/_kal/규칙빈도.json#by_speaker", ("full",), [81, 84, 283]),
    R("S22-check", "bm_read", "칸 검사(check_doc) 통과 편", K + "check_doc", "{ch}/줄판독/{id}.json", ("files", 1), [81, 280]),
    N("S22-hand", [82, 86], "스타일분석.md·워커묶음·브리프 = 사람 문서 / 물을 것 없음 — 회원 흐름은 규칙빈도.json·대본언어.json·팔레트.json"),
    R("S22-unread", "bm_read", "미측정 칸 이유 기록(_unread)", "hybrid/runner_ops.py:c_bm_fill", LR + "_unread", ("have",), [83]),
    R("S22-role", "bm_read", "역할(role) 줄마다", K + "rules_of", LR + "lines[].role", ("lines", 1.0), [84, 144, 173, 282],
      wait=W("칸", _W_ASK + " (role — EYE_SLOTS 에는 있으나 묻지 않음)")),
    R("S23-frame", "bm_tear", "틀 설명서(frame.json)", "engine/to_frame.py:main", "{ch}/뜯기/{id}/frame.json", ("files", 1), [89, 91, 141]),
    R("S23-var", "bm_tear", "공통값/편마다 값 가르기", "engine/preset_save.py:variables", "{ch}/preset/*/manifest.json", ("files", 1), [91]),
    N("S23-plan", [92], "판 설정 초안·styles/<판>.json·placement.place = 하이브리드 공용 렌더러 길 — 회원 프리셋은 frame.json·manifest 묶음(preset_brief)"),
    R("S23-layer", "bm_tear", "자막·제목 층 값(설명서 layers)", "engine/to_frame.py:build", "{ch}/preset/*/frame.json", ("files", 1), [93, 140, 141, 159]),
    R("S23-loo", "bm_tear", "loo 렌더 대조", "engine/loo_preset.py:build", None, ("owner",), [93],
      wait=W("함수", "회원 흐름에 loo 대조 없음 — 시험 편 대조(bench_match)가 그 몫을 하는지 판정 필요")),
    N("S23-ask", [94], "실수 기록(글꼴 오선택·bbox None) — S22-font 가 글꼴 칸을 잰다"),
    R("S24-make", "bm_trial", "시험 편 완성본", "hybrid/flow_bench.py:bm_trial", "{work}/final.mp4", ("files", 1), [97, 98], at="### 2-4. 제작"),
    N("S24-own", [99, 102, 103], "preset_make·material_auto 길 — 시험 편은 회원 과제(shortem_make 1판 길), 실수·물을 것은 제작 엔진 몫"),
    R("S24-tl", "bm_trial", "자막표(시각 기록 timeline.json)", "hybrid/flow_bench.py:bm_trial", "{work}/timeline.json", ("files", 1), [100]),
    R("S24-B", "bm_pan", "B표(검수 관문)", "engine/remake.py:gate_of", None, ("owner",), [101]),
    R("S25-rules", "bm_pan", "자·합격선(MATCH_RULES·match_table)", K + "match_table", None, ("owner",), [107], at=None),
    R("S25-frame", "bm_pan", "프레임 대조(framecmp·FRAME_PASS)", K + "frame_compare", None, ("owner",), [106, 107, 240, 241, 266],
      wait=W("함수", "bench_match 가 픽셀 대조(with_pixel·frame_compare)를 부르지 않는다 — 줄 자만 잰다")),
    R("S26-brief", "bm_make", "프리셋 묶음(적용)", "engine/preset_brief.py:render", "out/*.zip", ("owner",), [113, 114, 115, 116], at="### 2-6. 적용"),
    N("S261", [(118, 125)], "업그레이드 단계 — 1차 통과 뒤, 벤치마킹 흐름 밖", at="### 2-6-1"),
    N("S27", [(127, 129)], "하이브리드·변형 — 벤치마킹 흐름 밖", at="### 2-7"),
    N("S28", [(131, 134)], "운영·개선 — 사람이 지침서·검사 도구를 고친다", at="### 2-8"),
    # ── §3 축 × 단계 ─────────────────────────────────────────────
    N("S3", [(136, 139)], "축 표 머리", at="## 3. 축"),
    R("S3-zoom", "bm_tear", "줌 %/초·컷 분포(cuts.bench·zoom)", AN, TJ + "cuts.zoom", ("have",), [142, 163]),
    R("S3-trans", "bm_read", "전환 종류(transition) 줄마다", K + "apply_eye", LR + "lines[].transition", ("lines", 1.0), [142, 163, 282]),
    R("S3-fit", "bm_read", "대사↔장면 fit(0~10)", K + "check_doc", LR + "lines[].fit", ("lines", 1.0), [143, 168, 282], wait=W("칸", _W_ASK + " (fit)")),
    R("S3-beats", "bm_read", "이야기 순서(beats)", "hybrid/flow_bench.py:_fill_of", LR + "beats", ("full",), [144, 173]),
    R("S3-bgm", "bm_tear", "BGM 유무·페이드·덕킹(bgm_rules)", AN, TJ + "bgm_rules", ("have",), [146, 183],
      wait=_W_EAR),
    R("S3-voice", "bm_tear", "목소리 규칙(voice_rules)", AN, TJ + "voice_rules", ("have",), [146, 183],
      wait=_W_EAR),
    R("S3-over", "bm_tear", "스티커·짤(overlay_rules)", AN, TJ + "overlay_rules", ("have",), [147, 188]),
    R("S3-f0", "bm_read", "0초 첫 화면(frame0)", K + "apply_eye", LR + "frame0", ("have",), [148, 193, 282]),
    R("S3-face", "bm_read", "0초 얼굴 비율(frame0.face_frac)", K + "apply_eye", LR + "frame0.face_frac", ("have",), [193, 282], wait=W("칸", _W_ASK + " (frame0.face_frac)")),
    R("S35-reveal", "bm_read", "반전·공개 시점(초)", "hybrid/flow_bench.py:_fill_of", LR + "reveal_t", ("have",), [173], wait=W("칸", "beats 는 순서만 — 반전·공개 줄 시각 칸 없음")),
    R("S39-thumb", "bm_trial", "썸네일 jpg(벤치 대조)", "hybrid/flow_bench.py:bm_trial", "{work}/*.jpg", ("files", 1), [193], wait=W("칸", "시험 편 썸네일 jpg 를 벤치 첫 화면과 대조하는 자리 없음")),
    N("S3-topic", [149, 150], "소재·제품·채널 단위 — 시험 편 소재는 회원 과제(1판 규칙), 채널 통계는 집 PC 선정"),
    N("S31", [152, 154, 155], _N_ENGINE, at="### 3-1. 자막"),
    R("S31-sp", "bm_read", "화자(speaker) 줄마다", K + "check_doc", LR + "lines[].speaker", ("lines", 1.0), [153, 283]),
    R("S31-layer", "bm_read", "층(채널/원본박힘) 줄마다", K + "check_doc", LR + "lines[].layer", ("lines", 1.0), [153]),
    R("S31-enter", "bm_read", "등장 종류(enter) 줄마다", K + "check_doc", LR + "lines[].enter", ("lines", 1.0), [153]),
    R("S31-y", "bm_read", "자막 위치 y", K + "skeleton", LR + "lines[].y", ("lines", 0.9), [153]),
    R("S31-emph", "bm_read", "강조·스티커·효과음 칸(꾸밈 없는 줄도 분모)", K + "check_doc", LR + "lines[].emph", ("slot",), [153, 188, 284]),
    R("S31-font", "bm_read", "글꼴(font) 줄마다", K + "check_doc", LR + "lines[].font", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (font)")),
    R("S31-px", "bm_read", "크기 px(size_px) 줄마다", K + "check_doc", LR + "lines[].size_px", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (size_px)")),
    R("S31-lgap", "bm_read", "자간 px(letter_gap_px) 줄마다", K + "check_doc", LR + "lines[].letter_gap_px", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (letter_gap_px)")),
    R("S31-lngap", "bm_read", "행간 px(line_gap_px) 줄마다", K + "check_doc", LR + "lines[].line_gap_px", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (line_gap_px)")),
    R("S31-outline", "bm_read", "외곽선 px·hex(outline) 줄마다", K + "check_doc", LR + "lines[].outline", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (outline)")),
    R("S31-ring", "bm_read", "테(ring) 줄마다", K + "check_doc", LR + "lines[].ring", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (ring)")),
    R("S31-shadow", "bm_read", "그림자(shadow) 줄마다", K + "check_doc", LR + "lines[].shadow", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (shadow)")),
    R("S31-glow", "bm_read", "글로우(glow) 줄마다", K + "check_doc", LR + "lines[].glow", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (glow)")),
    R("S31-box", "bm_read", "상자 hex·alpha·pad·radius(box) 줄마다", K + "check_doc", LR + "lines[].box", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (box)")),
    # 지침서 §3-1 A·§6 칸 하나 = 행 하나(감시 적발 A, 11-06) — 판독 질문에 없거나 뜯기가 안 내는 칸은 잇기 대기(기록만)
    R("S31-x", "bm_read", "가로 위치 x 줄마다", K + "check_doc", LR + "lines[].x", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (x)")),
    R("S31-align", "bm_read", "정렬(align) 줄마다", K + "check_doc", LR + "lines[].align", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (align)")),
    R("S31-maxw", "bm_read", "줄 최대 폭(max_w) 줄마다", K + "check_doc", LR + "lines[].max_w", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (max_w)")),
    R("S31-wrap", "bm_read", "줄바꿈 규칙(wrap) 줄마다", K + "check_doc", LR + "lines[].wrap", ("lines", 1.0), [153], wait=W("칸", _W_ASK + " (wrap — 지침서 §3-1 A '줄바꿈 규칙', line_read.md 에도 칸 없음)")),
    R("S31-enterms", "bm_read", "등장 ms(enter_ms) 줄마다", K + "check_doc", LR + "lines[].enter_ms", ("lines", 1.0), [153, 281], wait=W("칸", _W_ASK + " (enter_ms — line_read.md 기본 칸)")),
    R("S31-variant", "bm_read", "등장 변형(variant) 줄마다", K + "check_doc", LR + "lines[].variant", ("slot",), [281], wait=W("칸", _W_ASK + " (variant — line_read.md 기본 칸)")),
    R("S31-cutat", "bm_read", "컷 시각(cut_at) 줄마다", K + "skeleton", LR + "lines[].cut_at", ("slot",), [281, 284], wait=W("칸", "뼈대 칸 — 막기 전 실측 필요(편마다 칸 있는 줄 대조)")),
    R("S31-sfx", "bm_read", "줄별 효과음 칸(sfx — 없음 null 도 분모)", K + "check_doc", LR + "lines[].sfx", ("slot",), [153, 281], wait=W("칸", "LINE_SCHEMA 에 sfx 있음 — 막기 전 실측 필요(편마다 칸 있는 줄 대조)")),
    R("S31-emhex", "bm_read", "강조 낱말 색(emph[].hex)", K + "check_doc", LR + "lines[].emph_hex", ("lines", 1.0), [153], wait=W("칸", "emph 안쪽 {word,hex,grow,outline} 을 재기(runner_ops._gate_path)가 못 보고 판독 질문에도 없다 — 줄 칸으로 묻거나 재기가 안쪽을 보게(실행 끝난 뒤)")),
    R("S31-emgrow", "bm_read", "강조 낱말 커짐(emph[].grow)", K + "check_doc", LR + "lines[].emph_grow", ("lines", 1.0), [153], wait=W("칸", "emph 안쪽 grow — S31-emhex 와 같은 이유")),
    R("S31-react", "bm_read", "잉?·와우 반응 스티커 자리", K + "check_doc", LR + "lines[].sticker_xy", ("lines", 1.0), [153, 188], wait=W("칸", _W_ASK + " (sticker 자리 x·y)")),
    R("S31-duck", "bm_read", "원음 구간 나레 끔(줄마다)", K + "check_doc", LR + "lines[].narr_off", ("slot",), [146, 183], wait=W("칸", _W_ASK + " (원음 줄에서 나레를 끄는지)")),
    R("S31-fill", "bm_read", "채움색 hex 줄마다", K + "palette_of", LR + "lines[].fill_hex", ("lines", 1.0), [153], wait=W("칸", _W_ASK + " (fill_hex)")),
    R("S31-exit", "bm_read", "퇴장(exit) 줄마다", K + "check_doc", LR + "lines[].exit", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (exit)")),
    R("S31-cursor", "bm_read", "커서(cursor) 줄마다", K + "check_doc", LR + "lines[].cursor", ("lines", 1.0), [153, 282], wait=W("칸", _W_ASK + " (cursor)")),
    R("S31-glyph", "bm_tear", "글자 꾸밈(획·외곽선·그림자 실측)", AN, TJ + "text_fx", ("have",), [153]),
    R("S31-motion", "bm_tear", "자막 등장 곡선 줄 비율(starts ÷ 자막 수 ≥ 0.9)", AN, TJ + "caption_motion.starts", ("ratio", "S22-cap", 0.9), [153],
      note="감시 적발 B(11-06): '값 있음'이면 스냅봤니 22줄 중 3줄로 통과했다 — 줄마다 센다(지침서 §0)"),
    R("S31-motion-end", "bm_tear", "자막 퇴장 곡선 줄 비율(ends ÷ 자막 수 ≥ 0.9)", AN, TJ + "caption_motion.ends", ("ratio", "S22-cap", 0.9), [153]),
    N("S32", [157, 159, 160], _N_ENGINE, at="### 3-2. 제목"),
    R("S32-bg", "bm_tear", "배경색(bg_rgb)", AN, TJ + "layout.bg_rgb", ("have",), [158]),
    R("S32-band", "bm_tear", "제목 띠(above_bands)", AN, TJ + "layout.above_bands", ("have",), [158]),
    R("S32-title", "bm_tear", "제목 글꼴·줄", AN, TJ + "fonts.title", ("have",), [158]),
    R("S32-tpx", "bm_tear", "제목 px·줄 높이·잉크 y(띠별)", AN, TJ + "fonts.title.bands", ("full",), [158], wait=W("칸", "fonts.title 이 실패면 띠별 값도 없다 — S32-title 이 먼저(스냅봤니 3편 모두 failed)")),
    R("S32-slant", "bm_tear", "제목 기울임°", AN, TJ + "fonts.title.slant_deg", ("have",), [158], wait=W("칸", "analyze 가 fontmatch.slant_deg 를 띠 안에만 적는다 — 칸 이름 확인 필요")),
    R("S32-word", "bm_tear", "제목 낱말 색 hex", AN, TJ + "fonts.title.word_hex", ("have",), [158], wait=W("칸", "뜯기에 제목 낱말별 색 칸 없음(지침서 §3-2 B '스키마 밖')")),
    R("S32-tbox", "bm_tear", "제목 상자 hex", AN, TJ + "fonts.title.box_hex", ("have",), [158], wait=W("칸", "뜯기에 제목 상자 색 칸 없음")),
    R("S32-logo", "bm_tear", "로고 자리·그림", AN, TJ + "fonts.brand", ("have",), [158], wait=W("칸", "로고 자리는 brand 띠 OCR 만, 그림은 안 뜯음(지침서 §3-2 B '로고 그림 = 스키마 밖')")),
    R("S32-src", "bm_read", "출처 줄 hex", K + "check_doc", LR + "layout.source_hex", ("have",), [158, 282], wait=W("칸", _W_ASK + " (layout.source_hex)")),
    R("S32-srcpx", "bm_read", "출처 줄 px·y", K + "check_doc", LR + "layout.source_px", ("have",), [158], wait=W("칸", _W_ASK + " (layout.source_px·source_y)")),
    R("S32-wm", "bm_read", "워터마크 투명도", K + "check_doc", LR + "layout.watermark.alpha", ("have",), [158, 282], wait=W("칸", _W_ASK + " (layout.watermark.alpha)")),
    N("S33", [162, 164, 165], _N_ENGINE, at="### 3-3. 장면 전환"),
    R("S33-still", "bm_tear", "정지 화면 비율", "narr_video.py:still_move", None, ("owner",), [163], wait=W("함수", "회원 흐름에 정지 비율 측정 없음")),
    R("S33-motion", "bm_read", "카메라 움직임(motion) 줄마다", K + "check_doc", LR + "lines[].motion", ("lines", 1.0), [163, 282], wait=W("칸", _W_ASK + " (motion)")),
    N("S34", [167, 169, 170], _N_ENGINE, at="### 3-4. 장면"),
    R("S34-scene", "bm_read", "장면 한마디(scene) 줄마다", K + "check_doc", LR + "lines[].scene", ("lines", 1.0), [168]),
    R("S34-desc", "bm_read", "장면 설명(scene_desc)", K + "check_doc", LR + "lines[].scene_desc", ("lines", 1.0), [168, 282], wait=W("칸", _W_ASK + " (scene_desc)")),
    N("S35", [172, 174, 175], _N_ENGINE + " · 끝 꼴은 beats 의 마지막 칸", at="### 3-5. 스토리"),
    N("S36", [177, 179, 180], _N_ENGINE + " · 말속도는 규칙빈도.json by_speaker cps", at="### 3-6. 대본"),
    N("S37", [182, 184, 185], _N_ENGINE, at="### 3-7. 소리"),
    R("S37-f0", "bm_tear", "목소리 성별·f0·닮은 목소리", "engine/sound/narr_report.py:main", None, ("owner",), [183], wait=W("함수", "회원 흐름에 narr_report 없음")),
    N("S38", [187, 189, 190], _N_ENGINE, at="### 3-8. 스티커"),
    R("S38-st", "bm_read", "스티커 칸 줄마다(sticker)", K + "check_doc", LR + "lines[].sticker", ("slot",), [188]),
    N("S39", [192, 194, 195], _N_ENGINE + " · 시험 편 썸네일은 제작 엔진(thumb.face_check)", at="### 3-9. 썸네일"),
    N("S310", [(197, 204)], "소재·제품·채널 단위 — 시험 편 소재는 회원 과제, 채널 통계는 집 PC", at="### 3-10. 소재"),
    # ── §4~§10 ─────────────────────────────────────────────
    N("S4", [(206, 239), (242, 253)], "측정값→엔진 설정 대응표·자막팩 요청서 — 제작 엔진 지원 현황(벤치 영상 칸 아님). 4-1 framecmp 는 S25-frame", at="## 4. 측정값"),
    N("S5", [(255, 258), 275, (277, 277)], "재현일치도 표 머리·실측 기록", at="## 5. 재현일치도"),
    R("S5-len", "bm_pan", "len.duration(길이)", K + "MATCH_RULES", None, ("owner",), [259]),
    R("S5-cut", "bm_pan", "cut.median(컷 중앙)", K + "MATCH_RULES", None, ("owner",), [260]),
    R("S5-cps", "bm_pan", "speech.cps.나레", K + "MATCH_RULES", None, ("owner",), [261]),
    R("S5-chunk", "bm_pan", "chunk.chars·chunk.sec", K + "MATCH_RULES", None, ("owner",), [262]),
    R("S5-enter", "bm_pan", "enter.mode.나레/원음", K + "MATCH_RULES", None, ("owner",), [263]),
    R("S5-fx", "bm_pan", "fx.rate·fx.pos·plain.rate", K + "MATCH_RULES", None, ("owner",), [264]),
    R("S5-mix", "bm_pan", "mix.lufs(−14±1)·narr.share", K + "MATCH_RULES", None, ("owner",), [265]),
    N("S6", [279, 281], "줄판독 칸 머리 — 정의 주인 hybrid/briefs/line_read.md", at="## 6. 줄판독"),
    R("S6-doc", "bm_read", "문서 칸(name_evidence)", "hybrid/runner_ops.py:c_bm_fill", LR + "name_evidence", ("have",), [282]),
    N("S7", [(286, 298)], "구현 계획(할 일 목록) — 칸 아님", at="## 7. 구현 계획"),
    N("S8", [(300, 303)], "워커 나누기 — 집 PC", at="## 8. 워커"),
    N("S9", [(305, 315)], "시운전 기록", at="## 9. 시운전"),
    N("S10", [(317, 326)], "알려진 숙제·기록", at="## 10. 알려진 숙제"),
]
BY_ID = {r["id"]: r for r in STEPS}


# ---------------------------------------------------------------- 엔진 v1 결정 파일 행(hybrid/engine_v1.json — 판단 주인은 그 파일)
# Jev(해결 1.00·뿌리 0.79·위험 0.19, C:	\main_jev1gate_q1.out): 결정 파일의 '채택 + 관문 조건 있음 + 벤치 관문 단계' 행을 같은 R 꼴로 받아
#   evaluate 가 STEPS 와 같이 판정한다. 산출물 자리(out)가 없는 행은 wait(기록만 — 이유 = 안 이음/측정 자리 없음), out 이 생기면 같은 길로 막는다.
#   gate_rows(실행기 do)는 out 있는 행만이라 결정 파일 행이 늘어도 회원 PC 재기는 그대로다.
@lru_cache(maxsize=1)
def v1_rows() -> tuple:
    from tools.calcopy.hybrid import engine_v1 as E
    return tuple(E.gate_rows_for_bench(GATE_PHASES))


# ---------------------------------------------------------------- 지침서 덮임
def _lines_of(doc) -> set[int]:
    s = set()
    for x in doc or []:
        a, b = (x, x) if isinstance(x, int) else x
        s.update(range(a, b + 1))
    return s


def coverage(guide: Path = GUIDE) -> dict:
    """지침서 줄(빈 줄 뺀) 중 표 행이 가리키는 줄 비율. 안 덮인 줄 번호를 같이 낸다."""
    text = guide.read_text(encoding="utf-8").splitlines()
    content = {i + 1 for i, t in enumerate(text) if t.strip()}
    covered = set().union(*(_lines_of(r["doc"]) for r in STEPS))
    miss = sorted(content - covered)
    return {"lines": len(content), "covered": len(content & covered), "pct": round(100 * len(content & covered) / max(1, len(content)), 1),
            "miss": miss, "beyond": sorted(covered - set(range(1, len(text) + 1)))}


def anchors_ok(guide: Path = GUIDE) -> list[str]:
    """at 글이 그 행 첫 줄에 있나 — 지침서 줄이 밀렸으면 표를 다시 맞추라는 뜻."""
    text = guide.read_text(encoding="utf-8").splitlines()
    bad = []
    for r in STEPS:
        if r["at"]:
            ls = sorted(_lines_of(r["doc"]))
            if not any(i <= len(text) and r["at"] in text[i - 1] for i in ls):
                bad.append(f"{r['id']}: {ls[0]}~{ls[-1]}줄에 '{r['at']}' 없음")
    return bad


# ---------------------------------------------------------------- 정적 호출 그래프(대조표 시험)
def _mod_file(mod: str) -> Path | None:
    if not mod.startswith("tools.calcopy"):
        return None
    p = ROOT / Path(*mod.split("."))
    return p.with_suffix(".py") if p.with_suffix(".py").is_file() else (p / "__init__.py" if (p / "__init__.py").is_file() else None)


@lru_cache(maxsize=None)
def _parse(path: str) -> dict:
    """모듈 하나 → {name: 그 이름 몸통이 가리키는 (모듈 파일, 이름) 집합}. 모듈 안 import 는 위치 상관없이 모은다(함수 안 import 가 이 코드의 꼴)."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    alias, names = {}, {}

    def imp(node):
        if isinstance(node, ast.Import):
            for a in node.names:
                alias[a.asname or a.name.split(".")[0]] = ("mod", a.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                sub = f"{node.module}.{a.name}"
                alias[a.asname or a.name] = ("mod", sub) if _mod_file(sub) else ("name", node.module, a.name)
    for n in ast.walk(tree):
        imp(n)
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == "_F":
            for t in n.targets:
                if isinstance(t, ast.Name):
                    alias[t.id] = ("mod", "tools.calcopy.hybrid.flow")
    tops = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            tops[n.name] = n
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                if isinstance(t, ast.Name):
                    tops[t.id] = n
    for name, node in tops.items():
        refs = set()
        for x in ast.walk(node):
            if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) and alias.get(x.value.id, (None,))[0] == "mod":
                f = _mod_file(alias[x.value.id][1])
                if f:
                    refs.add((str(f), x.attr))
            elif isinstance(x, ast.Name):
                if x.id in tops and x.id != name:
                    refs.add((path, x.id))
                elif alias.get(x.id, (None,))[0] == "name":
                    f = _mod_file(alias[x.id][1])
                    if f:
                        refs.add((str(f), alias[x.id][2]))
        names[name] = refs
    return names


def _owner_key(owner: str) -> tuple[str, str]:
    f, name = owner.split(":")
    return str(CAL / f), name


def bench_roots() -> set[tuple[str, str]]:
    """흐름 뿌리 = flow_bench.PHASES 처리기 전부 + 그 처리기가 내는 실행기 명령(cmd 글)의 runner_ops 함수(CMDS 표에서 찾음)."""
    fb, ro = str(CAL / "hybrid" / "flow_bench.py"), str(CAL / "hybrid" / "runner_ops.py")
    roots = set()
    t = ast.parse(Path(fb).read_text(encoding="utf-8"))
    cmds = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Assign) and any(isinstance(x, ast.Name) and x.id == "PHASES" for x in n.targets) and isinstance(n.value, ast.Dict):
            roots |= {(fb, v.id) for v in n.value.values if isinstance(v, ast.Name)}
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value == "cmd" and isinstance(v, ast.Constant):
                    cmds.add(v.value)
    table = {}
    for n in ast.walk(ast.parse(Path(ro).read_text(encoding="utf-8"))):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.Name):
                    table.setdefault(k.value, v.id)
    roots |= {(ro, table[c]) for c in cmds if c in table}
    return roots


def reached() -> set[tuple[str, str]]:
    seen, todo = set(), list(bench_roots())
    while todo:
        k = todo.pop()
        if k in seen:
            continue
        seen.add(k)
        try:
            todo += [x for x in _parse(k[0]).get(k[1], ()) if x not in seen]
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
    return seen


def wiring() -> dict:
    """대조표 — 주인 함수가 벤치마킹 흐름에서 닿나. missing = 막는 행인데 안 닿음(= 이어야 할 것, 0 이어야 통과).
    stale = '함수 안 이음' 으로 적어 두었는데 실제로는 닿음(표가 거짓)."""
    got = reached()
    rows = [r for r in STEPS if r["owner"] and not r["none"]]
    on = {r["id"]: _owner_key(r["owner"]) in got for r in rows}
    return {"reached": sorted(i for i, v in on.items() if v), "unreached": sorted(i for i, v in on.items() if not v),
            "missing": sorted(r["id"] for r in rows if not on[r["id"]] and not (r["wait"] and r["wait"]["kind"] == "함수")),
            "stale": sorted(r["id"] for r in rows if on[r["id"]] and r["wait"] and r["wait"]["kind"] == "함수")}


# ---------------------------------------------------------------- 재기(실행기 bm_gate — 판단 없음)
def gate_rows(phase: str) -> list[dict]:
    """그 단계에서 잴 행(산출물 자리만) — 서버가 do 에 실어 보낸다. 회원 PC 는 표를 갖지 않고 이 목록대로 읽기만 한다(runner_ops.gate_measure)."""
    return [{"id": r["id"], "out": r["out"]} for r in (*STEPS, *v1_rows())
            if r["phase"] == phase and r["out"] and (r["check"] or ("owner",))[0] not in ("owner", "v1")]


def measure(W, phase: str, slug: str, ids: list[str] | None = None, work: str | None = None) -> dict:
    """(재기 · 판단 없음 · 읽기만) 재는 코드 주인 = runner_ops.gate_measure(회원 PC 실행기와 같은 함수) — 여기는 표에서 행을 골라 부르기만."""
    from tools.calcopy.hybrid import runner_ops as RO
    return {"phase": phase, **RO.gate_measure(Path(W), gate_rows(phase), slug, ids, work)}


# ---------------------------------------------------------------- 판정(서버 flow_bench._step_gate 가 부른다)
def _ok(check: tuple, per: dict, ids: list[str] | None) -> tuple[bool, str]:
    kind = check[0]
    vals = {k: v for k, v in per.items() if ids is None or k in ("*", "-") or k in ids}
    if kind == "files":
        n = sum(int(v.get("count") or (1 if v.get("file") else 0)) for v in vals.values())
        return n >= check[1], f"파일 {n}개(필요 {check[1]})"
    if not vals:
        return False, "잰 편 없음"
    bad = []
    for k, v in vals.items():
        if not v.get("file"):
            bad.append(f"{k}: 파일 없음")
        elif v.get("error"):
            bad.append(f"{k}: 읽기 실패 {v['error']}")
        elif v.get("failed"):
            bad.append(f"{k}: 실패 — {v['failed']}")
        elif kind == "have" and v.get("v", 0) is None and "num" not in v and "len" not in v:
            bad.append(f"{k}: 값 없음")
        elif kind == "full" and not (v.get("len") or v.get("num")):
            bad.append(f"{k}: 비어 있음")
        elif kind == "ge" and not (isinstance(v.get("num"), (int, float)) and v["num"] >= check[1]):
            bad.append(f"{k}: {v.get('num')} < {check[1]}")
        elif kind == "lines" and not (v.get("n") and v.get("set", 0) / v["n"] >= check[1] - 1e-9):
            bad.append(f"{k}: 줄 {v.get('set', 0)}/{v.get('n', 0)}")
        elif kind == "slot" and not (v.get("n") and v.get("has") == v["n"]):
            bad.append(f"{k}: 칸 있는 줄 {v.get('has', 0)}/{v.get('n', 0)}")
    return not bad, " · ".join(bad)[:300] or "통과"


def evaluate(phase: str, got: dict, ids: list[str] | None = None) -> dict:
    """(판단 주인 · 단계 칸 통과) got = measure 결과의 rows. ids = 이 단계에서 쓰는 편(그 밖 편은 안 본다).
    → {miss: [막는 행 id], wait: [안 이은 행 id(막지 않음)], ok: [통과 id], why: {id: 글}}. 잰 값이 없는 막는 행 = miss(조용한 통과 금지)."""
    miss, wait, ok, why = [], [], [], {}
    for r in v1_rows():          # 결정 파일 행 — 측정 자리가 생기기 전엔 기록만
        if r["phase"] == phase and (not r["out"] or r["check"][0] == "v1"):
            wait.append(r["id"])
            why[r["id"]] = r["wait"]["why"]
    for r in (*STEPS, *(x for x in v1_rows() if x["out"] and x["check"][0] != "v1")):
        if r["phase"] != phase or not r["out"] or not r["check"] or r["check"][0] == "owner":
            continue
        row = (got or {}).get(r["id"])
        if row and r["check"][0] == "ratio":       # 줄 비율 — 이 칸 개수 ÷ 짝 칸 개수(같은 편끼리) ≥ 문턱
            base = ((got or {}).get(r["check"][1]) or {}).get("per") or {}
            per = {k: ({**v, "num": round((v.get("len") or 0) / (base.get(k) or {}).get("len"), 3)}
                       if (base.get(k) or {}).get("len") else {**v, "num": None}) for k, v in row["per"].items()}
            good, w = _ok(("ge", r["check"][2]), per, ids)
        else:
            good, w = _ok(r["check"], row["per"], ids) if row else (False, "잰 값 없음")
        why[r["id"]] = w
        (ok if good else (wait if r["wait"] else miss)).append(r["id"])
    return {"miss": miss, "wait": wait, "ok": ok, "why": why}


# ---------------------------------------------------------------- 사람이 읽는 지침·검수 문서(표에서 만든다)
STAGE_KO = {"bm_setup": "준비 확인", "bm_fetch": "벤치 영상 받기", "bm_tear": "영상 뜯기", "bm_read": "영상 보기(줄판독·규칙)", "bm_trial": "시험 영상 만들기",
            "bm_pan": "잡도리(같은 자 대조)", "bm_confirm": "판 확정", "bm_make": "프리셋 묶음 만들기"}
CHECK_KO = {"files": "파일 {0}개 이상", "have": "값 있음(실패 아님)", "full": "비어 있지 않음", "lines": "줄 {0:.0%} 이상 채움", "slot": "줄마다 칸 있음(없음도 분모)",
            "ge": "≥ {0}", "owner": "주인 함수 안 판정이 관문", "ratio": "개수 ÷ {0} 개수 ≥ {1}", "v1": "결정 파일 관문(측정 자리 없음)"}


def wait_counts() -> dict:
    """잇기 대기 수는 표에서 센다(손으로 적지 않는다)."""
    w = [r for r in STEPS if r["wait"]]
    return {"all": len(w), "칸": sum(r["wait"]["kind"] == "칸" for r in w), "함수": sum(r["wait"]["kind"] == "함수" for r in w)}


def _doc_s(doc) -> str:
    return ", ".join(str(x) if isinstance(x, int) else f"{x[0]}~{x[1]}" for x in doc)


def _stuck() -> int:
    from tools.calcopy.hybrid import flow
    return flow.REDO_STUCK


def render_md() -> str:
    cov, wr = coverage(), wiring()
    out = ["# 벤치마킹 단계별 지침·검수 (자동 생성 — 손으로 고치지 마라)", "",
           "> 주인 = `tools/calcopy/hybrid/bench_steps.py` STEPS. 고칠 땐 표를 고치고 `py -X utf8 -m tools.calcopy.hybrid.bench_steps doc` 로 다시 만든다.",
           f"> 원본 지침서 `tools/calcopy/칼카피_분석지침서.md` 줄 덮임 {cov['covered']}/{cov['lines']} ({cov['pct']}%) · 표 {len(STEPS)}행",
           f"> 관문 = `flow_bench._step_gate` — 단계 끝마다 이 표의 칸을 재고(`bm_gate`) 막는 칸이 미달이면 다시 재기, 같은 칸 {_stuck()}번 연속이면 멈춤.",
           f"> 대조표: 주인 함수 닿음 {len(wr['reached'])} · 안 닿음 {len(wr['unreached'])} (이어야 할 것 {len(wr['missing'])})",
           f"> 잇기 대기 {wait_counts()['all']} (칸 {wait_counts()['칸']} · 함수 {wait_counts()['함수']}) — 표에서 센 값",
           f"> 엔진 v1 결정 파일 행(관문 단계, 기록만) {len(v1_rows())} — 주인 `hybrid/engine_v1.json`, 전체 결정표 `tools/calcopy/엔진v1_결정표.md`", ""]
    for ph in ("bm_setup", "bm_fetch", "bm_tear", "bm_read", "bm_trial", "bm_pan", "bm_confirm", "bm_make"):
        rows = [r for r in (*STEPS, *v1_rows()) if r["phase"] == ph]
        if not rows:
            continue
        out += [f"## {STAGE_KO[ph]} (`{ph}`)" + (" — 관문 단계" if ph in GATE_PHASES else ""), "",
                "| 칸 | 주인 함수 | 산출물 자리 | 통과 조건 | 상태 | 지침서 줄 |", "|---|---|---|---|---|---|"]
        for r in rows:
            c = r["check"] or ("owner",)
            ck = CHECK_KO[c[0]].format(*c[1:]) if len(c) > 1 else CHECK_KO[c[0]]
            state = (f"잇기 대기({r['wait']['kind']}): {r['wait']['why']}" if r["wait"] else ("막음" if ph in GATE_PHASES and c[0] != "owner" else "주인 판정"))
            if r["id"] in wr["missing"]:
                state += " · ★주인 함수 안 불림"
            out.append(f"| {r['slot']} | `{r['owner']}` | `{r['out'] or '—'}` | {ck} | {state}{(' · ' + r['note']) if r['note'] else ''} | {_doc_s(r['doc'])} |")
        out.append("")
    out += ["## 해당 단계 없음 — 이유", "", "| 행 | 이유 | 지침서 줄 |", "|---|---|---|"]
    out += [f"| {r['id']} | {r['none']} | {_doc_s(r['doc'])} |" for r in STEPS if r["none"]]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    a = list(argv if argv is not None else sys.argv[1:])
    if not a or a[0] == "doc":
        p = CAL / "벤치마킹_단계별_지침검수.md"
        p.write_bytes(render_md().encode("utf-8"))
        print(p)
        return 0
    if a[0] == "cov":
        print(json.dumps({**coverage(), "anchors": anchors_ok(), **wiring()}, ensure_ascii=False, indent=1))
        return 0
    if a[0] == "gate":       # gate <작업 폴더> <slug> [시험 편 폴더] — 읽기만으로 단계마다 통과/미달
        W, slug, work = Path(a[1]), a[2], (a[3] if len(a) > 3 else None)
        ids_keep = None
        for ph in GATE_PHASES:
            m = measure(W, ph, slug, work=work)
            e = evaluate(ph, m["rows"], ids_keep)
            print(json.dumps({"phase": ph, "ids": m["ids"], **e}, ensure_ascii=False, indent=1))
        return 0
    print("쓰는 법: doc | cov | gate <작업 폴더> <slug> [시험 편 폴더]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
