"""Gemini API 히로 이미지 생성 (실패 시 골드 그라데이션 폴백)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = "gemini-2.5-flash-image"


def _load_env() -> dict:
    env, ep = {}, ROOT / ".env"
    if ep.exists():
        for line in ep.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def build_prompt(data: dict) -> str:
    sectors = ", ".join(data.get("lead_sectors", [])[:3]) or "한국 증시"
    return (
        f"Minimal premium financial editorial illustration about Korean stock market. "
        f"Theme: {sectors}. Mood: {data.get('headline','')}. "
        f"Dark charcoal background with gold accents, abstract, cinematic, high-end. "
        f"No text, no letters, no numbers. (텍스트/글자 없음)"
    )


def _call_gemini(prompt: str, key: str) -> bytes:
    """google-genai로 이미지 1장 생성, PNG bytes 반환. 실패 시 예외."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            return part.inline_data.data
    raise RuntimeError("Gemini 응답에 이미지 없음")


def _fallback_gradient(out_path: Path) -> None:
    from PIL import Image
    w, h = 840, 480
    img = Image.new("RGB", (w, h))
    px = img.load()
    top, bot = (212, 175, 55), (26, 26, 30)  # gold → charcoal
    for y in range(h):
        t = y / h
        r = int(top[0]*(1-t) + bot[0]*t)
        g = int(top[1]*(1-t) + bot[1]*t)
        b = int(top[2]*(1-t) + bot[2]*t)
        for x in range(w):
            px[x, y] = (r, g, b)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


def generate_hero(prompt: str, out_path: Path, api_key: str | None = None) -> dict:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    key = api_key or _load_env().get("GEMINI_API_KEY", "")
    if key:
        try:
            data = _call_gemini(prompt, key)
            out_path.write_bytes(data)
            return {"ok": True, "path": str(out_path), "fallback": False}
        except Exception as e:
            print(f"  ⚠️  Gemini 이미지 실패, 폴백 사용: {e}")
    # 키 없음 or 실패 → 폴백
    try:
        _fallback_gradient(out_path)
    except Exception as e:
        print(f"  ⚠️  폴백 생성도 실패: {e}")
        return {"ok": False, "path": str(out_path), "fallback": True}
    return {"ok": True, "path": str(out_path), "fallback": True}
