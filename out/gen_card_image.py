"""
Gemini 2.0 Flash image generation -> HTML card injection sample
"""
import os, sys, base64, re
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from google import genai
from google.genai import types

# ── 설정 ──────────────────────────────────────
API_KEY   = os.getenv("GEMINI_API_KEY", "AIzaSyA3qGt-GJu0LEAB_DkuRTELSu1JHVEfgI8")
OUT_DIR   = Path(__file__).parent
IMG_FILE  = OUT_DIR / "jensen_ai.png"
HTML_FILE = OUT_DIR / "sample_jensen_briefing.html"

# ── 이미지 생성 프롬프트 ──────────────────────
PROMPT = """
A cinematic portrait of a visionary tech CEO standing on a dark futuristic stage.
He is Asian, wearing a black leather jacket, holding a microphone, speaking confidently.
Background: deep dark blue/black with green neon glow effects and circuit board patterns.
Style: dramatic lighting, high contrast, photorealistic, professional press photo quality.
The figure is positioned on the RIGHT side of the image, leaving LEFT side empty for text overlay.
Aspect ratio: 16:9 wide format, 800x450px.
"""

def generate_image():
    print("🎨 Gemini 2.0 Flash 이미지 생성 중...")
    client = genai.Client(api_key=API_KEY)

    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=PROMPT,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"]
        )
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image"):
            img_bytes = part.inline_data.data
            # base64 디코딩이 필요한 경우
            if isinstance(img_bytes, str):
                img_bytes = base64.b64decode(img_bytes)
            IMG_FILE.write_bytes(img_bytes)
            print(f"✅ 이미지 저장: {IMG_FILE}")
            return True

    print("❌ 이미지 생성 실패")
    return False

def inject_image_to_html():
    """생성된 이미지를 HTML 헤더에 삽입"""
    if not HTML_FILE.exists():
        print(f"❌ HTML 파일 없음: {HTML_FILE}")
        return

    html = HTML_FILE.read_text(encoding="utf-8")

    # 이미지를 base64로 읽어서 HTML에 인라인 삽입 (경로 의존성 제거)
    img_b64 = base64.b64encode(IMG_FILE.read_bytes()).decode()
    img_src  = f"data:image/png;base64,{img_b64}"

    # 헤더 영역에 배경 이미지로 삽입
    new_header_style = f"""background: linear-gradient(140deg, #060810 0%, #0d1225 55%, #131b35 100%);
    background-image: url('{img_src}');
    background-size: cover;
    background-position: right center;
    position: relative;"""

    # 헤더에 어두운 오버레이 + 이미지 삽입
    img_tag = f"""
  <!-- AI 생성 이미지 -->
  <div style="
    position: absolute; right: 0; top: 0; bottom: 0; width: 45%;
    background: url('{img_src}') center/cover no-repeat;
    mask-image: linear-gradient(to left, rgba(0,0,0,0.9) 40%, transparent 100%);
    -webkit-mask-image: linear-gradient(to left, rgba(0,0,0,0.9) 40%, transparent 100%);
    border-radius: 0 20px 0 0;
  "></div>"""

    # .header div 안에 position: relative 추가하고 이미지 태그 삽입
    html = html.replace(
        '<div class="header">',
        '<div class="header" style="position:relative; overflow:hidden;">'
    )
    html = html.replace(
        '<div class="tag-row">',
        img_tag + '\n  <div class="tag-row" style="position:relative;z-index:2;">'
    )
    # 헤더 내 다른 요소들도 z-index 올리기
    html = html.replace(
        '<div class="header-title">',
        '<div class="header-title" style="position:relative;z-index:2;">'
    )
    html = html.replace(
        '<div class="info-pills">',
        '<div class="info-pills" style="position:relative;z-index:2;">'
    )

    HTML_FILE.write_text(html, encoding="utf-8")
    print(f"✅ HTML 업데이트 완료: {HTML_FILE}")

if __name__ == "__main__":
    success = generate_image()
    if success:
        inject_image_to_html()
        print("\n🎉 완료! 브라우저에서 sample_jensen_briefing.html 열어보세요.")
    else:
        print("\n⚠️  이미지 생성 실패. API 모델명 또는 키를 확인하세요.")
