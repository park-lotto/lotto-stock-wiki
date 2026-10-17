# -*- coding: utf-8 -*-
"""숏템리폿 현장썰 2편~ 실행기 — 1편(현장썰_01_가짜잠자리) make_render.py·checks.py 를 **그대로** 불러 편 폴더 경로만 바꿔 끼운다 (관제 097, 2026-10-18).
    PYTHONUTF8=1 py channel/hottemreport/현장썰_run.py <편 폴더 이름> tts|dry|render|checks

판단 주인은 1편 파일 그대로(시각 = make_render.timeline, 자막 = captions, 소리 = bgm_mix·add_source_bed, 검사 = checks.main).
이 파일은 새 판단을 갖지 않는다 — 편마다 다른 것은 편 폴더의 대본.json·재료.json 뿐.
  tts    : 대본.json final.lines 를 한 줄로 이어 tts_pause.py(필재·속도 voice.speed) 통째 1회 → render/narr_full.mp3
  dry    : make_render.main(render=False) — 시각·자막 계획만 출력
  render : make_render.main() — render/final.mp4
  checks : checks.main() — render/checks.json
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
ONE = H / "현장썰_01_가짜잠자리"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    slug, what = sys.argv[1], sys.argv[2]
    D = H / slug
    W = Path("C:/숏템_칼카피/hottemreport") / slug
    R = W / "render"
    R.mkdir(parents=True, exist_ok=True)
    sys.argv = [sys.argv[0]] + sys.argv[3:]
    if what == "tts":
        S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
        txt = " ".join(l["text"] for l in S["final"]["lines"])
        (R / "narr.txt").write_text(txt, encoding="utf-8")
        root = H.parents[1]
        r = subprocess.run(["py", str(root / "tools/calcopy/engine/tts_pause.py"), str(R / "narr.txt"), str(R / "narr_full.mp3"),
                            "--speed", str(S["voice"]["speed"])], cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout[-3000:], r.stderr[-1500:])
        js = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("{") and '"pauses"' in ln]
        if r.returncode or not js:
            raise SystemExit(f"tts 실패 rc={r.returncode}")
        (R / "narr_full.pauses.json").write_text(js[-1], encoding="utf-8")   # 1편 make_render.line_cuts 가 읽는 쉼 기록
        return
    if what in ("dry", "render"):
        mr = _load("hj_make_render", ONE / "make_render.py")
        mr.D, mr.W, mr.SRC, mr.R = D, W, W / "src", R
        mr.RAW, mr.WAV = R / "narr_full.mp3", R / "narr_gapped.wav"
        # line_cuts 의 마침표 쉼 찾기 문턱(0.12초) — tts_pause 가 쉼을 숨소리로 채워 −40dB 아래가 0.10초뿐인 문장 끝이 있다
        # (2편 실측: '부어 봤는데요.' 끝 9.25~9.35). 0.05초로 낮춰 같은 함수를 부른다(3편: 쉼이 0.08+0.10초 두 조각으로 갈림)(예상 ±0.3초 안 가장 가까운 쉼 규칙은 그대로).
        _orig_sil = mr.ha._silences

        class _HA:
            def __getattr__(self, k):
                return getattr(mr.ha_real, k)

            @staticmethod
            def _silences(p, noise, d):
                # 3편: 숨소리 채운 쉼은 −45dB 아래로 안 내려감(14.73~14.91) · 4편: −35dB 에서만 잡힘(9.13~9.18) → 두 문턱 합집합
                # 5편: 문장 끝 쉼이 −35dB·0.05초뿐(13.09~13.14) → −40/−35/−30dB·0.03초 합집합
                return sorted(set().union(*(_orig_sil(p, n, min(d, 0.03)) for n in ("-40dB", "-35dB", "-30dB"))))
        mr.ha_real, mr.ha = mr.ha, _HA()
        # 편마다 다른 상수(재료.json "consts", 예: 원본이 끝 원음 바로 뒤에서 끝나면 TAIL 을 줄인다)
        M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
        for k, v in (M.get("consts") or {}).items():
            if k.startswith("_"):
                continue
            assert hasattr(mr, k), k
            print(f"[편 상수] {k}: {getattr(mr, k)} → {v}")
            setattr(mr, k, v)
        mr.main(render=(what == "render"))
        return
    if what == "checks":
        ck = _load("hj_checks", ONE / "checks.py")
        ck.D, ck.R = D, R
        (R / "look").mkdir(exist_ok=True)
        ck.main()
        return
    raise SystemExit(f"모르는 일: {what}")


if __name__ == "__main__":
    main()
