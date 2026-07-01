"""Gemini Omni Flash(gemini-omni-flash-preview) 영상 생성 실테스트.

옴니 = Veo 3.1 패밀리 → SDK generate_videos 사용(비동기 operation 폴링).
텍스트/이미지 → 영상. .env의 GEMINI 키 재사용(atomizer 로더).

실행:
  python scripts/test_omni.py "프롬프트"                 # 텍스트→영상
  python scripts/test_omni.py "프롬프트" --image out/x.png # 이미지→영상(움직임 부여)

비용: 720p+오디오 영상출력 ≈ $0.10/초 (8초 ≈ $0.80). 실비 발생.
"""
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from google import genai
from google.genai import types
from pipeline.atoms.atomizer import _load_gemini_keys

OUT = Path(__file__).parent.parent / "out"
OUT.mkdir(exist_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("--image", default=None, help="시작 이미지 경로(이미지→영상)")
    ap.add_argument("--model", default="gemini-omni-flash-preview")
    ap.add_argument("--seconds", type=int, default=8)
    args = ap.parse_args()

    keys = _load_gemini_keys()
    if not keys:
        print("키 없음(.env GEMINI_*)"); return
    client = genai.Client(api_key=keys[0])

    t0 = time.time()
    is_veo = "veo" in args.model
    print(f"[요청] {args.model} / 경로={'generate_videos(Veo)' if is_veo else 'generate_content(Omni)'} / img={bool(args.image)}")

    if is_veo:
        # Veo 3.1 패밀리 — predictLongRunning(비동기 operation)
        kwargs = {"model": args.model, "prompt": args.prompt}
        if args.image:
            kwargs["image"] = types.Image.from_file(location=args.image)
        try:
            op = client.models.generate_videos(**kwargs)
        except Exception as e:
            print(f"[실패-요청] {type(e).__name__}: {e}"); return
        polls = 0
        while not op.done:
            time.sleep(8); polls += 1
            op = client.operations.get(op)
            print(f"  ...생성중 {int(time.time()-t0)}s")
        vid = op.response.generated_videos[0]
        client.files.download(file=vid.video)
        path = OUT / "omni_test.mp4"; vid.video.save(str(path))
        print(f"[성공] {path} / 총 {time.time()-t0:.0f}초 / 폴링 {polls}회")
    else:
        # Omni Flash — generateContent(대화형 영상). 응답 parts에서 video 추출.
        parts = [args.prompt]
        if args.image:
            parts.insert(0, types.Part.from_bytes(
                data=Path(args.image).read_bytes(), mime_type="image/png"))
        try:
            resp = client.models.generate_content(
                model=args.model, contents=parts,
                config=types.GenerateContentConfig(response_modalities=["VIDEO"]),
            )
        except Exception as e:
            print(f"[실패-요청] {type(e).__name__}: {e}"); return
        saved = False
        for p in resp.candidates[0].content.parts:
            blob = getattr(p, "inline_data", None)
            if blob and blob.data:
                path = OUT / "omni_test.mp4"; path.write_bytes(blob.data)
                print(f"[성공] {path} / 총 {time.time()-t0:.0f}초"); saved = True
        if not saved:
            print(f"[응답] 영상파트 없음: {resp}")


if __name__ == "__main__":
    main()
