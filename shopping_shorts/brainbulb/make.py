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

DEFAULT_VOICE = "tc_6059dad0b83880769a50502f"      # Typecast 'Changsu' = 박창수 (사장님 지정 2026-09-12). 볼케이노는 여성 나레(228Hz)+남성 PUNCH(104Hz) 2인 구성(실측)


def _voices(a):
    if a.voice:
        return a.voice
    from . import spec
    v = dict(spec.POLICY_VOICES)
    for k, val in (("NARR", a.voice_narr), ("CHAR", a.voice_char), ("PUNCH", a.voice_punch)):
        if val:
            v[k] = val
    return v


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url"); ap.add_argument("--text-file")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--voice", default=None, help="전 역할 같은 목소리(tc_…). 기본은 역할별 3명(spec.POLICY_VOICES)")
    ap.add_argument("--voice-narr", default=None); ap.add_argument("--voice-char", default=None); ap.add_argument("--voice-punch", default=None)
    ap.add_argument("--tempo", type=float, default=1.3)    # 사장님: "템포 더 빠르게"(v004 1.15=7.9자/초에도). 볼케이노 7.4는 여성 목소리라 더 빨리 들린다
    _vol = os.path.expanduser("~/.volcano/jobs/20260911_뇌전구_박수홍")     # 로컬에 있는 볼케이노 팩(저작권 미확인 — 커밋 안 함)
    ap.add_argument("--sfx-dir", default=os.path.join(_vol, "sfx_norm") if os.path.isdir(os.path.join(_vol, "sfx_norm")) else None)
    ap.add_argument("--meme-dir", default=os.path.join(_vol, "pepe", "fm") if os.path.isdir(os.path.join(_vol, "pepe", "fm")) else None)
    ap.add_argument("--no-images", action="store_true", help="EvoLink 생성 생략(검은 슬롯)")
    ap.add_argument("--quality", default=None, help="gpt-image-2 low|medium|high (기본 spec.IMAGE_QUALITY)")
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
    from . import images as _images
    imagegen = None if a.no_images else _images.evolink_imagegen(quality=a.quality)
    r = pipeline.run_all(a.workdir, source_text=text, llm=providers.gemini_llm(a.model),
                         tts=providers.typecast_synth(_voices(a), tempo=a.tempo), imagegen=imagegen,
                         sfx_dir=a.sfx_dir, meme_dir=a.meme_dir, bg_image=a.bg)
    if r["status"] != "ok":
        print("[make] 멈춤:", json.dumps({k: v for k, v in r.items() if k != "job"}, ensure_ascii=False, indent=1)[:1500])
        return 1
    d = pipeline.load(a.workdir)["data"]
    print(f"[make] 완료 → {d['render']['mp4']}  ({d['timing']['total']}s, 컷 {len(d['timing']['groups'])}, 대본 시도 {d['script']['attempts']}회)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
