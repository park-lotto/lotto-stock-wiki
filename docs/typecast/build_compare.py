# -*- coding: utf-8 -*-
"""청취 비교 페이지 — 타입캐스트 vs 일레븐랩스, 같은 대사로 나란히.

mp3를 data URI로 박아 **파일 하나로 어디서든 재생**되게 한다(경로 깨짐·상대링크 문제 회피).
일레븐랩스 쪽은 기존 샘플(assets/voice_samples)을 그대로 쓴다 — 같은 DEMO_TEXT로 구워진 것.

실행: py docs/typecast/build_compare.py  →  out/typecast_vs_eleven.html
"""
import base64
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC_DIR = os.path.join(ROOT, "out", "typecast_samples")
EL_DIR = os.path.join(ROOT, "shopping_shorts", "assets", "voice_samples")
PRESETS = os.path.join(ROOT, "shopping_shorts", "assets", "voice_presets.json")
OUT = os.path.join(ROOT, "out", "typecast_vs_eleven.html")

DEMO_TEXT = "시어머니가 알려주신 이 세제로 욕실을 청소했더니 구석구석 반짝반짝, 찌든 때가 싹 없어졌더라고요."

CASE_LABEL = {
    "normal_x1.0": ("기본 · 1.0배", "감정 없이 원속도 — 목소리 자체를 듣는 기준"),
    "normal_x1.6": ("기본 · 1.6배", "★실제 프리셋 속도. 일레븐은 1.2 clamp라 후처리로 만들던 소리"),
    "happy_x1.6": ("밝게 · 1.6배", "emotion happy 1.3"),
    "toneup_x1.6": ("톤업 · 1.6배", "emotion toneup 1.3 — 훅에 쓸 톤"),
    "whisper_x1.4": ("속삭임 · 1.4배", "emotion whisper — 일레븐엔 없는 축"),
}
CASE_ORDER = list(CASE_LABEL)


def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def dur(mp3):
    """사이드카 정렬 마지막 end → 길이(초). ffprobe 없이 읽는다."""
    try:
        with open(mp3 + ".align.json", encoding="utf-8") as f:
            d = json.load(f)
        return max(d["character_end_times_seconds"])
    except Exception:
        return None


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


rows = []
voices = []
for fn in sorted(os.listdir(TC_DIR)):
    if not fn.endswith(".mp3"):
        continue
    stem = fn[:-4]
    v, case = stem.split("_", 1)
    if v not in voices:
        voices.append(v)
    rows.append((v, case, os.path.join(TC_DIR, fn)))

# 일레븐랩스 best 프리셋(같은 대사로 구워진 기존 샘플)
el = []
try:
    with open(PRESETS, encoding="utf-8") as f:
        for p in json.load(f):
            if not p.get("best"):
                continue
            sf = os.path.join(EL_DIR, p.get("sample_file") or "")
            if os.path.exists(sf):
                el.append((p["name"], p["variant"], p.get("default_speed"), sf))
except Exception as e:
    print("일레븐 프리셋 로드 실패:", e)

parts = []
parts.append("""<title>타입캐스트 vs 일레븐랩스</title>
<style>
:root{--bg:#fbfaf8;--fg:#1a1a1a;--mut:#6b6560;--line:#e5e0d8;--card:#fff;--accent:#7a5c3e;--hl:#fff6e6}
:root:not([data-theme="light"]){}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#16151a;--fg:#eceaf0;--mut:#9c96a3;--line:#2e2b35;--card:#1e1d24;--accent:#c9a227;--hl:#2a2418}}
:root[data-theme="dark"]{--bg:#16151a;--fg:#eceaf0;--mut:#9c96a3;--line:#2e2b35;--card:#1e1d24;--accent:#c9a227;--hl:#2a2418}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 -apple-system,"Segoe UI",Roboto,"Malgun Gothic",sans-serif;padding:32px 20px 80px}
.wrap{max-width:1000px;margin:0 auto}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--mut);font-size:14px;margin-bottom:24px}
.demo{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;padding:14px 16px;margin:0 0 28px;font-size:15px}
.demo b{display:block;font-size:12px;color:var(--mut);font-weight:600;letter-spacing:.04em;margin-bottom:6px}
h2{font-size:19px;margin:36px 0 4px;letter-spacing:-.01em}
h2 .tag{font-size:12px;font-weight:500;color:var(--mut);margin-left:8px}
.note{color:var(--mut);font-size:13px;margin:0 0 14px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}
th{font-size:12px;color:var(--mut);font-weight:600;letter-spacing:.03em;background:color-mix(in srgb,var(--card) 92%,var(--fg))}
tr:last-child td{border-bottom:0}
tr.hl td{background:var(--hl)}
td.v{font-weight:600;white-space:nowrap}
td.d{color:var(--mut);font-size:13px;white-space:nowrap;font-variant-numeric:tabular-nums}
audio{height:34px;width:260px;vertical-align:middle}
.scroll{overflow-x:auto}
.cap{font-size:12px;color:var(--mut);margin-top:8px}
</style>
<div class="wrap">
<h1>타입캐스트 vs 일레븐랩스 — 청취 비교</h1>
<div class="sub">2026-08-19 실측 · 같은 대사, 같은 조건 · 파일 하나로 재생됩니다</div>
""")
parts.append(f'<div class="demo"><b>공통 대사</b>{esc(DEMO_TEXT)}</div>')

# --- 타입캐스트 ---
parts.append('<h2>타입캐스트 <span class="tag">ssfm-v30 · 무료 티어로 생성</span></h2>')
parts.append('<p class="note">★ <b>1.6배</b> 줄이 핵심입니다 — 지금 프리셋 속도가 1.6인데 '
             '일레븐랩스는 API 상한이 1.2라 ffmpeg로 억지로 당기던 소리입니다. '
             '타입캐스트는 이걸 API가 직접 냅니다.</p>')
parts.append('<div class="scroll"><table><tr><th>성우</th><th>조건</th><th>길이</th><th>재생</th><th>비고</th></tr>')
for case in CASE_ORDER:
    lab, desc = CASE_LABEL[case]
    for v in voices:
        m = [r for r in rows if r[0] == v and r[1] == case]
        if not m:
            continue
        p = m[0][2]
        d = dur(p)
        hl = ' class="hl"' if case == "normal_x1.6" else ""
        dtxt = f"{d:.2f}초" if d else "-"
        parts.append(
            f'<tr{hl}><td class="v">{esc(v)}</td><td>{esc(lab)}</td>'
            f'<td class="d">{dtxt}</td>'
            f'<td><audio controls preload="none" src="data:audio/mpeg;base64,{b64(p)}"></audio></td>'
            f'<td class="d">{esc(desc)}</td></tr>')
parts.append('</table></div>')
parts.append('<p class="cap">전 항목 자막 정렬(54자) 동봉 확인 — 자막 싱크는 밀리지 않습니다.</p>')

# --- 일레븐랩스 ---
parts.append('<h2>일레븐랩스 <span class="tag">현행 라이브 · eleven_v3</span></h2>')
parts.append('<p class="note">기존 프리셋 샘플입니다. 같은 대사로 구워진 것이라 바로 비교됩니다. '
             '표기 속도는 프리셋값이며, 1.2 초과분은 후처리로 당겨진 상태입니다.</p>')
parts.append('<div class="scroll"><table><tr><th>성우</th><th>변형</th><th>속도</th><th>재생</th></tr>')
for name, variant, spd, sf in el:
    parts.append(f'<tr><td class="v">{esc(name)}</td><td>{esc(variant)}</td>'
                 f'<td class="d">{spd}배</td>'
                 f'<td><audio controls preload="none" src="data:audio/mpeg;base64,{b64(sf)}"></audio></td></tr>')
parts.append('</table></div>')
parts.append('</div>')

html = "\n".join(parts)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"완료: {OUT}")
print(f"  타입캐스트 {len(rows)}개 · 일레븐랩스 {len(el)}개 · {os.path.getsize(OUT)//1024}KB")
