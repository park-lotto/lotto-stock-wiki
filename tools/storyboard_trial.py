# -*- coding: utf-8 -*-
"""[서버용·읽기 전용] 장면 먼저 → 스토리보드 시험 (2026-10-04 사장님 "분석부터 매칭까지 이 화면 전체", 3.6).

  ① 장면 목록(1단계): 모든 조각을 "무엇을 보여 주나"로 묶는다(빠지는 조각 0 — 모델이 빠뜨리면 코드가 '기타'로) +
     조각별 쓰임 표시(훅감·비포·애프터·반전·반응) + 재료 종류 + 없는 장면
  ② 스타일 추천(2단계): 승인 스타일을 칸 구조가 같은 것끼리 묶어, 재료 종류에 맞는 판 + 칸마다 맞는 쓰임 장면이 있나로 4개
  ③ 스토리보드(2단계): 추천 1·2위 각각 — 칸 목록·칸별 첫 줄/문장 틀(templates)·말투(voice)를 그대로 주고, ⭐꼭 쓰기 장면은 반드시 넣게
  ③-2 검수: **제품 사실을 지어냈나만** 본다(화면에 없는 가격·숫자·기능). 스타일이 요구하는 화면 밖 이야기(가족 반응·전문가 출처·댓글 유도)는 허용
  ④ 코드 검사: 없는 컷 번호·칸끼리 겹침·길이(컷 합×1.2 < 문장)·화면에 없는 숫자·빈칸 틀
  모델 호출: ①1 + ②1 + (③1 + ③-2 1) × 스타일 2개 = 6번. script_generate._call_json(vertex=True) = gemini-3.6-flash. DB 무변경.

    set -a && . /etc/shopping-shorts.env && set +a && cd /home/ubuntu/lotto-stock-wiki
    python3 tools/storyboard_trial.py f3d86941c30b:49ef-6,1e75-3 9fed785a6af4:32b1-2,dccd-3      # 작업:⭐꼭 쓰기 조각(끝자리)
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from shopping_shorts import storyboard as sb   # noqa: E402 — 판단은 전부 라이브 모듈(관제 120). 이 파일은 시안 서버용 입출력만.

DB = "shopping_shorts/data/reference.db"


def _save_tmp(jid, out):
    json.dump(out, open("/tmp/sbtrial_%s.json" % jid, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if sys.argv[1:2] == ["gen"]:
        print("RESULT " + json.dumps(sb.make_boards(DB, sys.argv[2], sys.argv[3].split(","), *(sys.argv[4:8])), ensure_ascii=False))
    elif sys.argv[1:2] == ["insert"]:
        print("RESULT " + json.dumps(sb.insert(DB, sys.argv[2], json.load(sys.stdin)), ensure_ascii=False))
    elif sys.argv[1:2] == ["families"]:
        print("RESULT " + json.dumps(sb.families(DB), ensure_ascii=False))
    else:
        for arg in sys.argv[1:]:
            jid, _, rest = arg.partition(":")
            star_s, _, role_s = rest.partition(":")
            out = sb.inventory(DB, jid, star_s, role_s)
            roles_txt = " / ".join("%s: %s" % (r, ", ".join(v)) for r, v in out["role_pick"].items())
            keys = ["auto"] + [str(out["styles"][0]["family"])] if out["styles"] else ["auto"]
            out["boards"] = sb.make_boards(DB, jid, keys, ",".join(out["star"]), "|".join("%s=%s" % (r, ",".join(v)) for r, v in out["role_pick"].items()), R=out)
            _save_tmp(jid, out)
            print(jid, "%.0f초" % out["secs"], "스토리보드", list(out["boards"]), flush=True)
