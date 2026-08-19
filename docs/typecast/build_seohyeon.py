# -*- coding: utf-8 -*-
"""Seohyeon 톤업 1.4배 전용 청취 페이지 — 사장님 지목 세팅 확정용.

① 속도 1.3/1.4/1.5 ② 감정강도 1.0~2.0 ③ 실제 대본 3줄(훅·본문·마무리)
mp3는 data URI로 박아 파일 하나로 재생된다.

실행: py docs/typecast/build_seohyeon.py  →  out/typecast_Seohyeon_toneup.html
"""
import base64
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "out", "typecast_samples")
OUT = os.path.join(ROOT, "out", "typecast_Seohyeon_toneup.html")

DEMO = "시어머니가 알려주신 이 세제로 욕실을 청소했더니 구석구석 반짝반짝, 찌든 때가 싹 없어졌더라고요."

SPEED = [("Seohyeon_toneup_x1.3.mp3", "1.3배", "조금 느긋"),
         ("Seohyeon_toneup_x1.4.mp3", "1.4배", "★지목하신 속도"),
         ("Seohyeon_toneup_x1.5.mp3", "1.5배", "조금 빠름")]
INTEN = [("Seohyeon_toneup_x1.4_int1.0.mp3", "1.0", "밋밋 — 톤업 최소"),
         ("Seohyeon_toneup_x1.4.mp3", "1.3", "★기본값"),
         ("Seohyeon_toneup_x1.4_int1.6.mp3", "1.6", "더 들뜸"),
         ("Seohyeon_toneup_x1.4_int2.0.mp3", "2.0", "최대 — 과한지 확인용")]
REAL = [("Seohyeon_real1_훅.mp3", "훅", "이거 하나면 청소 시간이 반으로 줄어요."),
        ("Seohyeon_real2_본문.mp3", "본문", "물때가 낀 자리에 뿌리고 3분만 두면 문질러 닦을 필요도 없더라고요."),
        ("Seohyeon_real3_마무리.mp3", "마무리", "저만 알고 싶은 건데, 링크 걸어둘게요.")]


def b64(fn):
    with open(os.path.join(SRC, fn), "rb") as f:
        return base64.b64encode(f.read()).decode()


def dur(fn):
    """정렬 사이드카 마지막 end → 길이(초). ffprobe 없이 읽는다."""
    try:
        with open(os.path.join(SRC, fn) + ".align.json", encoding="utf-8") as f:
            return max(json.load(f)["character_end_times_seconds"])
    except Exception:
        return None


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rows(items, first_col):
    out = []
    for fn, a, b in items:
        p = os.path.join(SRC, fn)
        if not os.path.exists(p):
            print("  없음:", fn)
            continue
        d = dur(fn)
        hl = ' class="hl"' if "★" in b else ""
        dtxt = f"{d:.2f}초" if d else "-"
        out.append(f'<tr{hl}><td class="v">{esc(a)}</td>'
                   f'<td class="d">{dtxt}</td>'
                   f'<td><audio controls preload="none" '
                   f'src="data:audio/mpeg;base64,{b64(fn)}"></audio></td>'
                   f'<td class="n">{esc(b)}</td></tr>')
    return "\n".join(out)


html = f"""<title>Seohyeon 톤업 1.4배</title>
<style>
:root{{--bg:#fbfaf8;--fg:#1a1a1a;--mut:#6b6560;--line:#e5e0d8;--card:#fff;--accent:#7a5c3e;--hl:#fff6e6}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#16151a;--fg:#eceaf0;--mut:#9c96a3;--line:#2e2b35;--card:#1e1d24;--accent:#c9a227;--hl:#2a2418}}}}
:root[data-theme="dark"]{{--bg:#16151a;--fg:#eceaf0;--mut:#9c96a3;--line:#2e2b35;--card:#1e1d24;--accent:#c9a227;--hl:#2a2418}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 -apple-system,"Segoe UI",Roboto,"Malgun Gothic",sans-serif;padding:32px 20px 80px}}
.wrap{{max-width:860px;margin:0 auto}}
h1{{font-size:26px;margin:0 0 6px;letter-spacing:-.02em}}
.sub{{color:var(--mut);font-size:14px;margin-bottom:26px}}
h2{{font-size:18px;margin:34px 0 4px;letter-spacing:-.01em}}
.note{{color:var(--mut);font-size:13px;margin:0 0 12px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}}
th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}}
th{{font-size:12px;color:var(--mut);font-weight:600;letter-spacing:.03em;background:color-mix(in srgb,var(--card) 92%,var(--fg))}}
tr:last-child td{{border-bottom:0}}
tr.hl td{{background:var(--hl)}}
td.v{{font-weight:600;white-space:nowrap}}
td.d{{color:var(--mut);font-size:13px;white-space:nowrap;font-variant-numeric:tabular-nums}}
td.n{{color:var(--mut);font-size:13px}}
audio{{height:34px;width:250px;vertical-align:middle}}
.scroll{{overflow-x:auto}}
.demo{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;padding:13px 15px;margin-bottom:8px;font-size:15px}}
.demo b{{display:block;font-size:12px;color:var(--mut);font-weight:600;letter-spacing:.04em;margin-bottom:5px}}
</style>
<div class="wrap">
<h1>Seohyeon · 톤업 · 1.4배</h1>
<div class="sub">2026-08-19 · 지목하신 세팅을 중심으로 앞뒤를 같이 냈습니다</div>

<div class="demo"><b>공통 대사 (①②)</b>{esc(DEMO)}</div>

<h2>① 속도 — 1.4가 맞는지</h2>
<p class="note">감정 톤업 강도 1.3 고정. 1.4를 가운데 두고 앞뒤를 비교하시면 판단이 쉽습니다.</p>
<div class="scroll"><table><tr><th>속도</th><th>길이</th><th>재생</th><th>비고</th></tr>
{rows(SPEED, "속도")}
</table></div>

<h2>② 톤업 강도 — 얼마나 들뜨게</h2>
<p class="note">속도 1.4 고정. 같은 톤업이라도 강도로 인상이 꽤 달라집니다.</p>
<div class="scroll"><table><tr><th>강도</th><th>길이</th><th>재생</th><th>비고</th></tr>
{rows(INTEN, "강도")}
</table></div>

<h2>③ 실제 대본으로</h2>
<p class="note">확정 후보(톤업 1.3 · 1.4배)로 훅·본문·마무리를 실제 문장에 얹었습니다.
데모 문장 하나로는 안 드러나는 호흡이 여기서 보입니다.</p>
<div class="scroll"><table><tr><th>역할</th><th>길이</th><th>재생</th><th>대사</th></tr>
{rows(REAL, "역할")}
</table></div>
</div>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"완료: {OUT}  ({os.path.getsize(OUT)//1024}KB)")
