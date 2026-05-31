# -*- coding: utf-8 -*-
import sys, io, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SAVE_DIR = r"C:\Users\CH\Desktop\로또의 주식\raw\naver_premium\dongju"
IMG_EXTS = {'.jpg','.jpeg','.png','.gif','.webp','.avif'}

def get_meta(post_dir):
    txt = os.path.join(post_dir, "content.txt")
    title = os.path.basename(post_dir)
    date = ""
    if os.path.exists(txt):
        with open(txt, encoding='utf-8') as f:
            for line in f:
                if line.startswith("제목:"): title = line.split("제목:",1)[1].strip()
                elif line.startswith("날짜:"): date = line.split("날짜:",1)[1].strip()
                elif line.startswith("===") : break
    n_img = len([f for f in os.listdir(post_dir) if os.path.splitext(f)[1].lower() in IMG_EXTS])
    return title, date, n_img

folders = sorted([d for d in os.listdir(SAVE_DIR) if os.path.isdir(os.path.join(SAVE_DIR, d))])
entries = []
for folder in folders:
    post_dir = os.path.join(SAVE_DIR, folder)
    title, date, n_img = get_meta(post_dir)
    entries.append((folder, title, date, n_img))

rows = ""
for i, (folder, title, date, n_img) in enumerate(entries, 1):
    tag = f'<span style="margin-left:8px;padding:2px 8px;background:#1a2a1a;color:#00ff88;border-radius:4px;font-size:11px;font-weight:700">이미지 {n_img}</span>' if n_img else ""
    rows += f'<a href="{folder}/index.html" class="item"><span class="num">{i:03d}</span><span class="body"><span class="ttl">{title}</span><span class="dt">{date}{tag}</span></span></a>\n'

html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><title>동주 아카이브</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d0d0d;color:#e8e8e8;font-family:'Apple SD Gothic Neo',sans-serif}}
.top{{background:#111;border-bottom:1px solid #222;padding:24px}}
.top h1{{font-size:22px;font-weight:800;color:#fff}}
.top p{{color:#666;font-size:13px;margin-top:4px}}
.sw{{padding:16px 24px;max-width:860px;margin:0 auto}}
input{{width:100%;padding:12px 16px;background:#1a1a1a;border:1px solid #333;border-radius:8px;color:#fff;font-size:15px;outline:none}}
input::placeholder{{color:#555}}
.cnt{{color:#555;font-size:13px;padding:0 24px 12px;max-width:860px;margin:0 auto}}
.list{{max-width:860px;margin:0 auto;padding:0 24px 60px}}
.item{{display:flex;align-items:center;gap:14px;padding:14px 16px;background:#111;border:1px solid #1e1e1e;border-radius:10px;margin-bottom:8px;text-decoration:none;color:inherit;transition:border-color .15s}}
.item:hover{{border-color:#00ff88}}
.num{{color:#444;font-size:12px;font-weight:700;min-width:32px;text-align:right}}
.body{{display:flex;flex-direction:column;gap:4px}}
.ttl{{color:#e8e8e8;font-size:15px;font-weight:600}}
.dt{{color:#555;font-size:12px}}
</style></head><body>
<div class="top">
  <h1>동주 매매일지 아카이브</h1>
  <p>수급단타왕×만쥬 주식스터디 | 동주 카테고리 전체 ({len(entries)}개) | 2024.11 ~ 2026.05</p>
</div>
<div class="sw"><input id="q" placeholder="종목명·날짜·키워드 검색..."></div>
<p class="cnt" id="cnt">{len(entries)}개</p>
<div class="list" id="list">
{rows}
</div>
<script>
const q=document.getElementById('q');
const cnt=document.getElementById('cnt');
q.addEventListener('input',function(){{
  const v=this.value.toLowerCase();
  let n=0;
  document.querySelectorAll('.item').forEach(el=>{{
    const show=el.querySelector('.ttl').textContent.toLowerCase().includes(v);
    el.style.display=show?'flex':'none';
    if(show)n++;
  }});
  cnt.textContent=n+'개';
}});
</script>
</body></html>"""

out = os.path.join(SAVE_DIR, "index.html")
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"index.html 완료 ({len(entries)}개)")
