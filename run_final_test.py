"""7개 리포트 최종 프롬프트 검증"""
import os, json, requests
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pipeline.sector_signal.prompt_v_final import PROMPT

load_dotenv()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

REPORTS = [
    # 로컬 파일
    ("삼성전기",     None, "C:/Users/TheRose/Downloads/20260610_company_31633000.pdf"),
    ("LG이노텍",     None, "C:/Users/TheRose/Downloads/20260611_company_784094000.pdf"),
    ("일진전기",     None, "C:/Users/TheRose/Downloads/20260611_company_331731000 (1).pdf"),
    ("클로봇",       None, "C:/Users/TheRose/Downloads/20260610_company_381739000 (1).pdf"),
    # URL
    ("HD현대일렉트릭", "https://stock.pstatic.net/stock-research/company/18/20260611_company_545237000.pdf", None),
    ("신성이엔지",    "https://stock.pstatic.net/stock-research/company/18/20260610_company_135650000.pdf",  None),
    ("HD현대마린솔루션","https://stock.pstatic.net/stock-research/company/56/20260610_company_533058000.pdf", None),
]

def get_pdf_bytes(url, local_path):
    if local_path:
        return Path(local_path).read_bytes()
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.content

results = []
for name, url, local in REPORTS:
    print(f"[{name}]...", end=" ", flush=True)
    try:
        pdf_bytes = get_pdf_bytes(url, local)
        print(f"{len(pdf_bytes)//1024}KB", end=" ", flush=True)

        tmp = Path(f"_tmp_{name}.pdf")
        tmp.write_bytes(pdf_bytes)
        with open(tmp, "rb") as fh:
            file_obj = client.files.upload(
                file=fh,
                config=types.UploadFileConfig(mime_type="application/pdf"),
            )
        tmp.unlink()

        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[file_obj, PROMPT],
        )
        try:
            client.files.delete(name=file_obj.name)
        except Exception:
            pass

        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw)
        results.append(result)
        print("OK")
    except Exception as e:
        results.append({"name": name, "error": str(e)[:200]})
        print(f"FAIL: {e}")

out = Path("test_final.json")
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n저장: {out.resolve()}  ({sum(1 for r in results if 'error' not in r)}/{len(results)})")
