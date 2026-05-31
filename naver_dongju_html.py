# -*- coding: utf-8 -*-
"""
다운로드된 동주 카테고리 글들을 HTML 아카이브로 변환
- index.html : 전체 목록 + 검색
- 각 폴더/index.html : 원본 내용 + 이미지 인라인 표시
"""
import sys, io, os, re, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SAVE_DIR = r"C:\Users\CH\Desktop\로또의 주식\raw\naver_premium\dongju"

IMG_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif'}

def img_to_base64(path):
    ext = os.path.splitext(path)[1].lower()
    mime = {'jpg':'jpeg','jpeg':'jpeg','png':'png','gif':'gif','webp':'webp','avif':'avif'}.get(ext.lstrip('.'), 'jpeg')
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{data}"

def make_post_html(post_dir, folder_name):
    txt_path = os.path.join(post_dir, "content.txt")
    if not os.path.exists(txt_path):
        return None, None

    with open(txt_path, encoding='utf-8') as f:
        raw = f.read()

    # 제목/날짜/URL 파싱
    title = re.search(r'^제목:\s*(.+)', raw, re.M)
    date  = re.search(r'^날짜:\s*(.+)', raw, re.M)
    url   = re.search(r'^URL:\s*(.+)',  raw, re.M)
    title = title.group(1).strip() if title else folder_name
    date  = date.group(1).strip()  if date  else ""
    url   = url.group(1).strip()   if url   else ""

    # 본문 구간
    body_match = re.search(r'={60}\n본문\n={60}\n(.+?)(?=\n={60}|$)', raw, re.S)
    body_text = body_match.group(1).strip() if body_match else raw

    # 이미지 목록 파싱
    img_match = re.search(r'이미지 목록\n={60}\n(.+?)(?=\n={60}|$)', raw, re.S)
    img_urls = {}
    if img_match:
        for line in img_match.group(1).splitlines():
            m = re.match(r'\[이미지 (\d+)\] (\S+)', line)
            if m:
                img_urls[int(m.group(1))] = m.group(2)

    # 영상 목록
    vid_match = re.search(r'영상 목록\n={60}\n(.+?)$', raw, re.S)
    vid_lines = []
    if vid_match:
        for line in vid_match.group(1).splitlines():
            m = re.match(r'\[(영상|비디오)\] (.+)', line)
            if m:
                vid_lines.append(m.group(2).strip())

    # 본문 HTML 변환 (줄바꿈 → <br>, 단락)
    body_html = ""
    for para in body_text.split('\n\n'):
        para = para.strip()
        if not para:
            continue
        para = para.replace('\n', '<br>')
        body_html += f"<p>{para}</p>\n"

    # 이미지 HTML (base64 인라인)
    imgs_html = ""
    for idx in sorted(img_urls.keys()):
        fname = img_urls[idx]
        img_path = os.path.join(post_dir, fname)
        if os.path.exists(img_path):
            try:
                b64 = img_to_base64(img_path)
                imgs_html += f'<div class="img-wrap"><img src="{b64}" alt="이미지 {idx}"><p class="img-cap">이미지 {idx}</p></div>\n'
            except:
                imgs_html += f'<div class="img-wrap img-fail">이미지 {idx} 로드 실패 ({fname})</div>\n'

    # 영상 HTML
    vids_html = ""
    for vsrc in vid_lines:
        if "youtube.com" in vsrc or "youtu.be" in vsrc:
            vid_id = re.search(r'(?:embed/|v=|youtu\.be/)([A-Za-z0-9_-]{11})', vsrc)
            if vid_id:
                vids_html += f'<div class="vid-wrap"><iframe src="https://www.youtube.com/embed/{vid_id.group(1)}" frameborder="0" allowfullscreen></iframe></div>\n'
            else:
                vids_html += f'<div class="vid-wrap"><a href="{vsrc}" target="_blank">[영상 링크] {vsrc}</a></div>\n'
        elif "tv.naver.com" in vsrc or "vod.naver" in vsrc:
            vids_html += f'<div class="vid-wrap naver-vid"><a href="{vsrc}" target="_blank">[네이버 영상] {vsrc}</a></div>\n'
        else:
            vids_html += f'<div class="vid-wrap"><a href="{vsrc}" target="_blank">[영상] {vsrc}</a></div>\n'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d0d0d; color: #e8e8e8; font-family: 'Pretendard', 'Apple SD Gothic Neo', sans-serif; font-size: 16px; line-height: 1.8; }}
  .header {{ background: #111; border-bottom: 1px solid #222; padding: 16px 24px; position: sticky; top: 0; z-index: 10; }}
  .header a {{ color: #00ff88; text-decoration: none; font-size: 14px; }}
  .header a:hover {{ text-decoration: underline; }}
  .container {{ max-width: 860px; margin: 0 auto; padding: 40px 24px 80px; }}
  .meta {{ color: #888; font-size: 13px; margin-bottom: 8px; }}
  h1 {{ font-size: 26px; font-weight: 800; color: #fff; margin-bottom: 12px; line-height: 1.4; }}
  .source-link {{ color: #00ff88; font-size: 12px; text-decoration: none; }}
  .source-link:hover {{ text-decoration: underline; }}
  .divider {{ border: none; border-top: 1px solid #222; margin: 28px 0; }}
  .body-text p {{ margin-bottom: 18px; }}
  .section-title {{ color: #00ff88; font-size: 13px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin: 36px 0 16px; }}
  .img-wrap {{ margin: 20px 0; text-align: center; }}
  .img-wrap img {{ max-width: 100%; border-radius: 8px; border: 1px solid #222; }}
  .img-cap {{ color: #555; font-size: 12px; margin-top: 6px; }}
  .img-fail {{ color: #555; font-size: 13px; padding: 12px; background: #1a1a1a; border-radius: 6px; }}
  .vid-wrap {{ margin: 20px 0; }}
  .vid-wrap iframe {{ width: 100%; aspect-ratio: 16/9; border-radius: 8px; }}
  .vid-wrap a {{ color: #00ff88; word-break: break-all; }}
  .naver-vid {{ background: #1a1a2e; border-radius: 8px; padding: 16px; }}
  .back-btn {{ display: inline-block; margin-top: 40px; padding: 10px 20px; background: #00ff88; color: #000; font-weight: 700; border-radius: 6px; text-decoration: none; font-size: 14px; }}
</style>
</head>
<body>
<div class="header">
  <a href="../index.html">← 목록으로</a>
</div>
<div class="container">
  <p class="meta">{date} &nbsp;|&nbsp; <a href="{url}" class="source-link" target="_blank">원본 보기 ↗</a></p>
  <h1>{title}</h1>
  <hr class="divider">
  <div class="body-text">
{body_html}
  </div>
"""
    if imgs_html:
        html += f'<p class="section-title">이미지</p>\n{imgs_html}\n'
    if vids_html:
        html += f'<p class="section-title">영상</p>\n{vids_html}\n'

    html += f'<a href="../index.html" class="back-btn">← 목록으로</a>\n</div>\n</body>\n</html>'
    return title, html


def make_index_html(entries):
    rows = ""
    for i, (folder, title, date, n_img, n_vid) in enumerate(entries, 1):
        tags = ""
        if n_img > 0:
            tags += f'<span class="tag img">이미지 {n_img}</span>'
        if n_vid > 0:
            tags += f'<span class="tag vid">영상 {n_vid}</span>'
        rows += f"""<a href="{folder}/index.html" class="post-item">
  <div class="post-num">{i:02d}</div>
  <div class="post-body">
    <div class="post-title">{title}</div>
    <div class="post-meta">{date} {tags}</div>
  </div>
</a>\n"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>동주 매매일지 아카이브</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d0d0d; color: #e8e8e8; font-family: 'Pretendard', 'Apple SD Gothic Neo', sans-serif; }}
  .top {{ background: #111; border-bottom: 1px solid #222; padding: 24px; }}
  .top h1 {{ font-size: 22px; font-weight: 800; color: #fff; }}
  .top p {{ color: #888; font-size: 13px; margin-top: 4px; }}
  .search-wrap {{ padding: 20px 24px; max-width: 860px; margin: 0 auto; }}
  input#q {{ width: 100%; padding: 12px 16px; background: #1a1a1a; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 15px; outline: none; }}
  input#q::placeholder {{ color: #555; }}
  .list {{ max-width: 860px; margin: 0 auto; padding: 0 24px 60px; }}
  .post-item {{ display: flex; align-items: center; gap: 16px; padding: 16px; background: #111; border: 1px solid #1e1e1e; border-radius: 10px; margin-bottom: 10px; text-decoration: none; color: inherit; transition: border-color .2s; }}
  .post-item:hover {{ border-color: #00ff88; }}
  .post-num {{ color: #444; font-size: 13px; font-weight: 700; min-width: 28px; text-align: right; }}
  .post-title {{ color: #e8e8e8; font-size: 15px; font-weight: 600; margin-bottom: 4px; }}
  .post-meta {{ color: #666; font-size: 12px; }}
  .tag {{ display: inline-block; margin-left: 8px; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; }}
  .tag.img {{ background: #1a2a1a; color: #00ff88; }}
  .tag.vid {{ background: #1a1a2a; color: #6699ff; }}
  .count {{ color: #666; font-size: 13px; margin: 0 24px 16px; max-width: 860px; }}
</style>
</head>
<body>
<div class="top">
  <h1>동주 매매일지 아카이브</h1>
  <p>수급단타왕×만쥬 주식스터디 | 동주 카테고리 전체 ({len(entries)}개)</p>
</div>
<div class="search-wrap">
  <input id="q" type="text" placeholder="제목 검색...">
</div>
<p class="count" id="cnt">{len(entries)}개 글</p>
<div class="list" id="list">
{rows}
</div>
<script>
document.getElementById('q').addEventListener('input', function() {{
  const q = this.value.toLowerCase();
  const items = document.querySelectorAll('.post-item');
  let n = 0;
  items.forEach(el => {{
    const show = el.querySelector('.post-title').textContent.toLowerCase().includes(q);
    el.style.display = show ? 'flex' : 'none';
    if(show) n++;
  }});
  document.getElementById('cnt').textContent = n + '개 글';
}});
</script>
</body>
</html>"""


# ── 메인 실행 ──
folders = sorted([d for d in os.listdir(SAVE_DIR) if os.path.isdir(os.path.join(SAVE_DIR, d))])
entries = []

print(f"총 {len(folders)}개 폴더 처리 중...")

for folder in folders:
    post_dir = os.path.join(SAVE_DIR, folder)
    title, html = make_post_html(post_dir, folder)
    if html is None:
        continue

    # 이미지/영상 수 카운트
    imgs = [f for f in os.listdir(post_dir) if os.path.splitext(f)[1].lower() in IMG_EXTS]
    txt_path = os.path.join(post_dir, "content.txt")
    raw = open(txt_path, encoding='utf-8').read()
    date_m = re.search(r'^날짜:\s*(.+)', raw, re.M)
    date = date_m.group(1).strip() if date_m else ""
    n_vid = raw.count('[영상]') + raw.count('[비디오]')

    # 개별 포스트 HTML 저장
    out_path = os.path.join(post_dir, "index.html")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    entries.append((folder, title, date, len(imgs), n_vid))
    print(f"  [{folder[:30]}] -> 완료 (이미지 {len(imgs)}개)")

# 인덱스 HTML 저장
index_html = make_index_html(entries)
index_path = os.path.join(SAVE_DIR, "index.html")
with open(index_path, 'w', encoding='utf-8') as f:
    f.write(index_html)

print(f"\n완료! 총 {len(entries)}개 글 변환")
print(f"인덱스: {index_path}")
