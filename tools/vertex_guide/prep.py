"""Vertex 키 발급 안내 영상 — 캡처를 장면별로 자르고(개인정보 가림) 강조 상자 좌표를 scenes.json으로 만든다.
  py tools/vertex_guide/prep.py <캡처폴더> <출력폴더>

좌표는 **화면 좌표(CSS px, 가로 2000 기준)** 로 적는다 — 캡처 PNG는 배율 1.24(2477px)라 여기서 곱한다.
★개인정보(이메일·이름·프로젝트ID·서비스계정ID·크레딧 잔액·프로필 사진)는 자르는 칸 밖으로 빼거나 blur로 덮는다.
  잘라낸 뒤에도 남는 글자는 여기 blur 목록에 반드시 적는다 — check 단계(verify_masks)가 원본과 비교해 확인한다.
"""
import sys, json, pathlib
from PIL import Image, ImageFilter, ImageDraw

SRC = pathlib.Path(sys.argv[1]); OUT = pathlib.Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
K = 1.24

# crop=(x0,y0,x1,y1) · blur=[(x0,y0,x1,y1)] · hl=[(x0,y0,x1,y1)] 전부 화면 좌표. step = 좌상단 배지, cap = 자막(두 줄까지)
SCENES = [
    dict(img="02_freetrial_tos_checked.png", crop=(545, 295, 985, 792), step="1", title="구글 클라우드 무료 체험 시작",
         blur=[(565, 155, 960, 205)], hl=[(566, 335, 958, 500), (566, 750, 610, 778)],
         cap=["cloud.google.com 에서 「무료로 시작하기」", "국가 대한민국 · 약관 2개 체크 → 「계속」"]),
    dict(img="03_freetrial_step2.png", crop=(545, 95, 985, 480), step="1", title="결제 정보 입력",
         blur=[(600, 820, 820, 862)], hl=[(598, 325, 958, 380)],
         cap=["계좌 유형은 「개인」으로 바꾸세요", "이름·주소·카드 등록 — 직접 유료 전환 전엔 청구되지 않아요"]),
    dict(img="05_enable_mfa.png", crop=(0, 95, 760, 340), step="1-2", title="이 화면이 뜨면 — 2단계 인증",
         blur=[], hl=[(30, 219, 126, 249)],
         cap=["구글 클라우드는 2단계 인증을 켜야 들어갈 수 있어요", "「MFA 사용 설정」을 누르세요 (이미 켜 두셨으면 안 떠요)"]),
    dict(img="06_twosv_page.png", crop=(640, 50, 1350, 700), step="1-2", title="2단계 인증 켜기",
         blur=[], hl=[(652, 645, 795, 683)],
         cap=["「2단계 인증 사용 설정」 → 휴대폰으로 확인", "켠 뒤 몇 분 지나 구글 클라우드로 돌아가면 열려요"]),
    dict(img="10_vertex_api_library.png", crop=(0, 42, 1100, 560), step="2", title="Agent Platform API 사용",
         blur=[], hl=[(160, 256, 520, 288)],
         cap=["검색창에 「Agent Platform API」 (예전 이름: Vertex AI API)", "「사용」을 누르세요 — 「API 사용 설정됨」이면 끝"]),
    dict(img="11_service_accounts.png", crop=(222, 103, 1000, 350), step="3", title="서비스 계정 만들기",
         blur=[(288, 316, 690, 340)], hl=[(352, 111, 472, 138)],
         cap=["메뉴 › IAM 및 관리자 › 서비스 계정", "위쪽 「+ 서비스 계정 만들기」"]),
    dict(img="13_sa_name_filled.png", crop=(222, 103, 900, 600), step="3", title="이름 정하기",
         blur=[(265, 290, 660, 336)], hl=[(266, 199, 654, 232), (266, 419, 368, 448)],
         cap=["이름은 아무거나 (예: shorts)", "「만들고 계속하기」"]),
    dict(img="16_role_search.png", crop=(222, 103, 900, 600), step="3", title="역할 고르기",
         blur=[], hl=[(290, 376, 612, 428)],
         cap=["역할 검색에 「Agent Platform 사용자」", "(예전 이름: Vertex AI 사용자) — 눌러서 선택"]),
    dict(img="17_role_selected.png", crop=(222, 103, 900, 600), step="3", title="역할 확인 → 완료",
         blur=[], hl=[(266, 288, 464, 322), (236, 509, 282, 538)],
         cap=["역할은 이것 하나만 — 소유자·편집자는 주지 마세요", "「완료」"]),
    dict(img="20_add_key_menu.png", crop=(222, 103, 1000, 520), step="4", title="키 만들기",
         blur=[], hl=[(346, 143, 392, 174), (238, 438, 334, 464)],
         cap=["만든 서비스 계정을 눌러 「키」 탭", "「키 추가」 › 「새 키 만들기」"]),
    dict(img="21_create_key_dialog.png", crop=(700, 300, 1300, 700), step="4", title="JSON으로 받기",
         blur=[], hl=[(793, 505, 862, 530), (1168, 628, 1218, 654)],
         cap=["「JSON」 그대로 → 「만들기」 → .json 파일이 내려받아져요", "이 파일은 비밀번호와 같아요 — 다른 곳에 올리지 마세요"]),
    dict(img="31_settings_vertex_pasted.png", crop=(300, 278, 1065, 660), step="5", title="숏템메이커에 붙여넣기",
         blur=[], hl=[(321, 490, 1043, 585), (321, 594, 450, 636)],
         cap=["파일을 메모장으로 열어 전체 복사", "마이페이지 › 내 키 등록 › 🚀 내 구글 Vertex 연결 → 「확인하고 연결」"]),
]


def px(r):
    return tuple(int(round(v * K)) for v in r)


def main():
    out = []
    for i, s in enumerate(SCENES):
        im = Image.open(SRC / s["img"]).convert("RGB")
        for b in s["blur"]:
            box = px(b)
            region = im.crop(box).filter(ImageFilter.GaussianBlur(14))
            # 흐림만으로는 긴 글자가 읽힐 수 있다 — 한 번 더 모자이크로 뭉갠다
            w, h = region.size
            region = region.resize((max(1, w // 14), max(1, h // 14))).resize((w, h), Image.NEAREST)
            im.paste(region, box[:2])
        c = px(s["crop"])
        crop = im.crop(c)
        name = f"scene_{i:02d}.png"
        crop.save(OUT / name)
        hls = []
        for h in s["hl"]:
            x0, y0, x1, y1 = px(h)
            hls.append([x0 - c[0], y0 - c[1], x1 - x0, y1 - y0])
        out.append({"file": name, "w": crop.width, "h": crop.height, "step": s["step"], "title": s["title"],
                    "cap": s["cap"], "hl": hls})
    (OUT / "scenes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} scenes → {OUT}")


if __name__ == "__main__":
    main()
