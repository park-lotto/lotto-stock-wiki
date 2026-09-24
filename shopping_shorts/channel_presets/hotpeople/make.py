# -*- coding: utf-8 -*-
"""원클릭 CLI — 씨앗 한 줄로 뜨거운사람들 틀 영상까지.

  py -m shopping_shorts.channel_presets.hotpeople.make --seed "안세영 | 배드민턴 세계 1위" --workdir out/hotpeople/안세영
  py -m shopping_shorts.channel_presets.hotpeople.make --workdir out/hotpeople/안세영 --from footage   # 그 단계부터 다시

흐름: setup → research(위키백과) → script(클로드, 규칙 반려→재작성) → footage(유튜브 검색·다운로드·장면·제미니 선택)
      → render(PIL 판 + ffmpeg) → review(mp4 실측 + review.png). 멈추면 어디서 왜 멈췄는지 그대로 찍는다.
"""
import argparse
import json
import sys

from shopping_shorts.channelkit import pipeline, providers, registry


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", help="'인물명 | 주제'")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--from", dest="from_step")
    ap.add_argument("--script-llm", default=None, choices=["claude", "gemini"])
    ap.add_argument("--no-pick", action="store_true", help="장면 선택 모델 없이 순서대로(비용 0, 품질 낮음)")
    a = ap.parse_args(argv)
    registry.use("hotpeople")
    if a.from_step:
        pipeline.reset_to(a.workdir, a.from_step)
        print(f"[make] {a.from_step} 단계부터 다시")
    seed = a.seed or ((pipeline.load(a.workdir)["data"].get("setup") or {}).get("seed"))
    if not seed:
        ap.error("--seed '인물명 | 주제'")
    r = pipeline.run_all(a.workdir, channel="hotpeople", source_text=seed,
                         llm=providers.script_llm(which=a.script_llm),
                         reviewer=None if a.no_pick else [providers.gemini_reader(), providers.gemini_reader("gemini-2.5-flash")])
    if r["status"] != "ok":
        print("[make] 멈춤:", json.dumps({k: v for k, v in r.items() if k != "job"}, ensure_ascii=False, indent=1)[:2000])
        return 1
    d = pipeline.load(a.workdir)["data"]
    print(f"[make] 완료 → {d['render']['mp4']} ({d['review']['duration']}s, 컷 {len(d['render']['cuts'])}, "
          f"대본 시도 {d['script']['attempts']}회, 장면 모델 보정 {d['footage']['fixed']}) · 검수 시트 {d['review']['sheet']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
