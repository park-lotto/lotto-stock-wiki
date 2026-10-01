"""Vertex 안내 영상 v3 — 기존 영상(v2)에 장면 2개를 **끼워 넣는다**(관제 053, 2026-10-01).
  py tools/vertex_guide/prep_v3.py <캡처폴더> <출력폴더>
  node tools/vertex_guide/remotion/render.mjs <출력폴더> <새장면만.mp4>
  py tools/vertex_guide/splice_v3.py <기존 v2.mp4> <새장면만.mp4> <out.mp4>

왜 따로인가: v2 원본 캡처(.playwright-mcp/vertex_cap/, 집 PC)가 이 PC에 없어 전체 재렌더가 안 된다.
캡처 출처: 고객(회원 153) 콘솔 캡처(가로 ~1200px, 배율 1.0) — 이메일·이름·프로젝트ID·결제계정ID는 blur.
좌표는 캡처 px 그대로(k=1.0). 장면 정의 규칙(crop/blur/hl/cap)은 prep.py와 같다.
"""
import sys, json, pathlib
from PIL import Image, ImageFilter

SRC = pathlib.Path(sys.argv[1]); OUT = pathlib.Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)

# at = v2 영상에서 **이 장면 뒤에** 끼운다(0부터 세는 v2 장면 번호, prep.py SCENES 순서). 8=「역할 확인 → 완료」, 16=「숏템메이커에 붙여넣기」
SCENES = [
    dict(img="71_iam_role_save.png", crop=(0, 0, 1222, 738), step="3", title="역할이 들어갔나 — 「저장」 확인", after=8,
         blur=[(325, 428, 700, 450), (325, 453, 700, 475), (737, 78, 1010, 100)],
         hl=[(737, 200, 946, 237), (737, 340, 782, 372)],
         cap=["IAM 목록에서 서비스 계정 줄의 역할이 「Agent Platform 사용자」인지 보세요", "따로 넣으셨다면 꼭 「저장」 — 안 누르면 역할이 안 들어가요(저장 뒤 5분)"]),
    dict(img="72_billing_linked_projects.png", crop=(0, 60, 1198, 661), step="!", title="「권한이 없습니다」가 뜨면 — 결제 연결 확인", after=16,
         blur=[(270, 222, 430, 242), (393, 388, 495, 410)],
         paint=[(666, 135, 803, 178)],   # 고객이 캡처에 그려 둔 빨간 상자(「결제 계정 폐쇄」) — 흰 테두리로 지운다. 폐쇄를 강조하면 안 된다
         hl=[(270, 330, 560, 412)],
         cap=["결제 › 계정 관리 — 「연결된 프로젝트」에 내 프로젝트가 있어야 해요", "없으면 결제 › 「결제 계정 연결」 — 「결제 계정 폐쇄」는 누르지 마세요"]),
]


def main():
    out = []
    for i, s in enumerate(SCENES):
        im = Image.open(SRC / s["img"]).convert("RGB")
        for b in s["blur"]:
            region = im.crop(b).filter(ImageFilter.GaussianBlur(10))
            w, h = region.size
            region = region.resize((max(1, w // 12), max(1, h // 12))).resize((w, h), Image.NEAREST)
            im.paste(region, b[:2])
        from PIL import ImageDraw
        d = ImageDraw.Draw(im)
        for b in s.get("paint", []):
            d.rectangle(b, outline="white", width=6)
        c = s["crop"]; crop = im.crop(c)
        name = f"scene_v3_{i:02d}.png"; crop.save(OUT / name)
        hls = [[x0 - c[0], y0 - c[1], x1 - x0, y1 - y0] for (x0, y0, x1, y1) in s["hl"]]
        out.append({"file": name, "w": crop.width, "h": crop.height, "step": s["step"], "title": s["title"],
                    "cap": s["cap"], "hl": hls, "after": s["after"]})
    (OUT / "scenes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} scenes → {OUT}")


if __name__ == "__main__":
    main()
