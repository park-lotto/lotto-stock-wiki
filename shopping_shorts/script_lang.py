# -*- coding: utf-8 -*-
"""소스 언어 판정 — **여기 한 곳에서만** 정한다(0순위-B).

왜 있는가(2026-08-14 사장님 "샤오홍슈에 있는 영상은 대본과 아예 닿지 않게 하라"):
믹스 소스에 샤오홍슈(중국어)가 섞이면 그 원문이 대본에 그대로 옮겨붙는다.
실측(job 9423ef05385e, 소스 5개 중 4개가 샤오홍슈):

    소스           세그  한글  한자
    인스타          15   154    0
    s1~s4(샤오홍슈) 27/20/31/17  0  480/341/474/422
    → 비트1 나레이션: "가게에서 Ciabatta 恰巴塔扭扭棒 사면 개당 10위안이나 한다길래…"

한자 6자 + 통화 '위안'이 그대로 나갔다. 다른 4칸은 한자 0이라 **전체 오염이 아니라
한 칸에 원문이 옮겨붙은 것**이다.

처방: 외국어 소스의 **말(full_text·segments[].text)만 지운다.**
- 화면(scene_desc·action·change·is_key·shot_role)은 **그대로 남긴다** — 장면 재료로는 계속 쓴다.
- product_benefits도 남긴다 — 추출이 화면을 보고 **한국어로** 쓴 문장이라 오염원이 아니다
  (무자막 해외영상이 이미 이 경로로 대본에 녹는다, test_product_benefits 참조).
즉 "장면은 다 쓰되 말은 한국어 소스에서만 나온다".
"""
import re
import sys

_HAN = re.compile(r"[一-鿿]")      # CJK 한자
_KOR = re.compile(r"[가-힣]")      # 한글 음절

# 한자가 이만큼은 있어야 '중국어 소스'로 본다 — 한국어 자막에 한자 한두 자가
# 섞인 경우(회사명·한자어 표기)를 외국어로 오판하지 않기 위한 바닥선.
_MIN_HAN = 5


def _counts(script):
    """소스 하나의 (한글 수, 한자 수). full_text와 세그 text를 함께 센다."""
    parts = [script.get("full_text") or ""]
    parts += [(s.get("text") or "") for s in (script.get("segments") or [])]
    blob = " ".join(parts)
    return len(_KOR.findall(blob)), len(_HAN.findall(blob))


def is_foreign(script):
    """이 소스의 '말'이 한국어가 아닌가. 한자가 바닥선 이상이고 한글보다 많으면 외국어."""
    kor, han = _counts(script)
    return han >= _MIN_HAN and han > kor


def mute_foreign_speech(source_scripts):
    """외국어 소스의 말만 지운 **복사본**을 돌려준다(원본 불변). 대상 0개면 입력 그대로.

    화면·특장점은 건드리지 않는다 — 장면 재료로는 계속 쓰인다."""
    if not source_scripts:
        return source_scripts
    muted = []
    hit = []
    for sc in source_scripts:
        if not isinstance(sc, dict) or not is_foreign(sc):
            muted.append(sc)
            continue
        nb = dict(sc)
        nb["full_text"] = ""
        nb["segments"] = [dict(s, text="") for s in (sc.get("segments") or [])]
        # structure는 원문 문장 구조 요약이라 같이 비운다(원문이 프롬프트로 새는 두 번째 길).
        nb["structure"] = {}
        muted.append(nb)
        hit.append(sc.get("video_id") or sc.get("name") or "?")
    if not hit:
        return source_scripts
    print("[언어분리] 외국어 소스 %d개 말 제외(화면·특장점은 유지): %s"
          % (len(hit), ", ".join(map(str, hit))), file=sys.stderr)
    if len(hit) == len(source_scripts):
        # 전부 외국어면 말 재료가 0이 된다 — 대본은 product_benefits(한국어)로만 쓰인다.
        # 무자막 해외영상과 같은 상태라 파이프라인은 돌지만, 말맛 재료가 없다는 건 알려준다.
        print("[언어분리] ⚠ 모든 소스가 외국어 — 대본은 특장점(한국어)만으로 쓰인다",
              file=sys.stderr)
    return muted
