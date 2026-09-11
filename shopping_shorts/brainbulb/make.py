# -*- coding: utf-8 -*-
"""원클릭 CLI — 링크(또는 텍스트) 하나로 뇌전구 규격 영상까지.

  py -m shopping_shorts.brainbulb.make --url <기사URL> --workdir out/brainbulb/<이름> [--voice tc_…] [--sfx-dir …] [--bg 이미지]
  py -m shopping_shorts.brainbulb.make --text-file 소재.txt --workdir …

흐름: 링크 → 기사 본문 → (pipeline) setup → script(Gemini, 린터 반려→재작성) → layout → lint → voice(Typecast, 컷별)
      → timing → subtitle → sfx → render → review. 멈추면 어디서 왜 멈췄는지 그대로 찍는다.
"""
import argparse
import json
import os
import sys

from . import pipeline, providers

DEFAULT_VOICE = "tc_69fc0cff784968297fb45daa"      # Typecast 'Sanghyun' (ssfm-v30). 볼케이노가 쓴 목소리는 서버가 골라 미상


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url"); ap.add_argument("--text-file")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--tempo", type=float, default=1.25)   # 실측: 볼케이노 나레가 Typecast 기본보다 약 1.35배 빠르다(같은 문장 1.8s vs 2.7s)
    ap.add_argument("--sfx-dir", default=None)
    ap.add_argument("--bg", default=None)
    ap.add_argument("--model", default="gemini-3.1-flash-lite")
    ap.add_argument("--from", dest="from_step", default=None, help="이 단계부터 다시 (예: voice, subtitle)")
    a = ap.parse_args(argv)
    if a.from_step:
        pipeline.reset_to(a.workdir, a.from_step)
        print(f"[make] {a.from_step} 단계부터 다시")
    if a.url:
        src = providers.fetch_article(a.url)
        text = src["text"]
        print(f"[make] 기사 {len(text)}자 — {src['title'][:50]}")
    elif a.text_file:
        text = open(a.text_file, encoding="utf-8").read()
    else:
        ap.error("--url 또는 --text-file")
    os.makedirs(a.workdir, exist_ok=True)
    with open(os.path.join(a.workdir, "source.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)
    r = pipeline.run_all(a.workdir, source_text=text, llm=providers.gemini_llm(a.model),
                         tts=providers.typecast_synth(a.voice, tempo=a.tempo), sfx_dir=a.sfx_dir, bg_image=a.bg)
    if r["status"] != "ok":
        print("[make] 멈춤:", json.dumps({k: v for k, v in r.items() if k != "job"}, ensure_ascii=False, indent=1)[:1500])
        return 1
    d = pipeline.load(a.workdir)["data"]
    print(f"[make] 완료 → {d['render']['mp4']}  ({d['timing']['total']}s, 컷 {len(d['timing']['groups'])}, 대본 시도 {d['script']['attempts']}회)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
