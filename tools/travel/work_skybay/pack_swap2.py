"""모션 프리셋 사진 교체 시험 2차 — 세로 갤러리 캐러셀·사진 앱 광고·사진 위 말풍선(세로)·스타일 몽타주(사장님 10-22 "다른것도 더 만들어봐").

    py tools/travel/work_skybay/pack_swap2.py

템플릿 코드는 그대로, 사진 칸만 같은 크기로 잘라 덮고 화면 문구만 바꾼다(pack_swap.py 와 같은 방식).
문구 숫자는 insights.json 항목 그대로(20층 인피니티풀 251 · 온수 65 · 아침 7시 18 · 야경 10 · 투숙객도 유료 9 · 후기 7,908 · 9.1점).
"""
import shutil
import sys

from pack_swap import GUEST, O, WORK, put, text, ROOT


def main():
    # ① 세로 갤러리 캐러셀(1080×1920, 사진 12장)
    d = WORK / "2026-10-22_숙소_duotone_vertical"
    pool = [O(n) for n in (5, 6, 11, 12, 1, 7, 15, 3, 13, 19)] + GUEST
    for k in range(12):
        put(pool[k % len(pool)], d / ("t%d.jpg" % k))
    text(d / "cfg.js", [
        ("top:'60대도 할 수 있게'", "top:'후기 7,908건이 고른 호텔'"),
        ("slides:['쇼핑쇼츠, 아직 손으로 만드세요?','잘되는 영상 5곳에서 한 번에','해외 원본까지 찾아 줍니다','대본은 히트작 틀로 자동',"
         "'자막 지우기도 자동','성우 8명 중 골라 읽기','숫자 발음 자동 교정','틀 5종 버튼으로 꾸미기','효과음 자동 배치',"
         "'캡컷으로 그대로 내보내기','딸깍으로 만든다 · 숏템메이커','전체 과정은 롱폼 영상에서 ▶']",
         "slides:['강릉 가서 바다만 보고 오지 마세요','20층 인피니티풀 · 후기 251건','바다랑 맞닿은 온수풀','한쪽은 바다, 한쪽은 호수',"
         "'침대에 누운 채 보는 일출 · 206건','커튼 열자마자 오션뷰','로비 문만 나서면 바로 바다','코너룸은 누워서도 바다 구경',"
         "'밤엔 인피니티풀 야경','아침 7시 개장 때 한산','스카이베이 경포','방 고르는 법은 다음 편에서 ▶']"),
        ("cta:['숏템메이커','전체 과정은 롱폼 영상에서 ▶','자세한 건 고정댓글 · 프로필 링크']",
         "cta:['스카이베이 경포','방 고르는 법은 다음 편에서 ▶','후기 출처 · 여기어때']")])

    # ② 사진 앱 광고 → '광고 사진 말고 손님 사진'(480×600)
    d = WORK / "2026-10-22_숙소_photo_app_ad_vertical"
    for k, no in zip((0, 1, 2, 3, 6, 9), (5, 6, 11, 12, 1, 15)):
        put(O(no), d / "img" / ("h%02d.png" % k))
    put(GUEST[0], d / "img" / "selfie.png")
    shutil.copy(ROOT / "shopping_shorts/static/fonts/Pretendard-ExtraBold.otf", d / "brand" / "PretendardX.otf")
    text(d / "index.html", [
        ("One selfie in. One HD headshot out, free to download.", "실제 투숙객 후기로 고른 호텔"),
        ("4.7 · 3,568 reviews on Trustpilot", "9.1 · 후기 7,908건 · 여기어때"),
        ("Get your headshot", "스카이베이 경포"), ("for free.", "경포해변 바로 앞"), ("Try for free →", "후기 더 보기 →"),
        ('"Pick one"', '"광고 사진"'), ('"selfie."', '"말고."'), ('"Get a studio"', '"손님이 찍은"'), ('"headshot."', '"진짜 사진."'),
        ('"No studio"', '"보정 없이"'), ('"needed."', '"이 정도."'), ('"Still looks like"', '"후기 7,908건이"'), ('"you."', '"증명."'),
        ("✓ City backdrop", "✓ 앞 바다 뒤 호수"), ("✓ Sharp outfit", "✓ 20층 인피니티풀"), ("✓ Studio lighting", "✓ 누워서 일출"),
(">After<", ">손님 사진<"), ("HeadshotPro", "스카이베이 경포"), (">Recents<", ">최근<"), (">Select<", ">선택<"),
        ("</style>", '@font-face{font-family:"PretendardX";src:url("brand/PretendardX.otf")}\n*{font-family:"Geist","PretendardX",sans-serif}\n</style>')])

    # ③ 사진 위 후기 말풍선 쌓기 — 숏템 세로판(shortem/)
    d = WORK / "2026-10-22_숙소_photo_chat_stack_lp" / "shortem"
    put(O(5), d / "img" / "senior.png")
    text(d / "index.html", [("grayscale(1)", "grayscale(0)")])      # 원본은 흑백 인물 — 수영장은 색이 생명이라 컬러로
    text(d / "index.html", [
        ("쇼핑쇼츠, 저도 할 수 있을까요?", "겨울에 가도 수영 돼요?"),
        ("60대도 할 수 있게 만들었어요.", "온수라 한겨울에도 따뜻해요."), ("60대도 할 수 있게", "후기 7,908건 정리"),
        ("✓ 잘되는 영상 5곳에서 모으기", "✓ 20층 인피니티풀 · 후기 251건"), ("✓ 히트작 틀로 대본 자동", "✓ 겨울에도 온수 · 65건"),
        ("✓ 자막 제거 · 성우 8명", "✓ 아침 7시 개장 때 한산 · 18건"), ("✓ 꾸미기 틀 버튼 하나", "✓ 밤 야경 · 10건"),
        ("✓ 캡컷으로 그대로 내보내기", "✓ 투숙객도 유료 · 9건"), ("정말 딸깍이네요!", "바다 위에 붕~ 떠있는 기분!"),
        ("10분에 한 편.", "강릉 가면 여기."), ("딸깍으로 만드는", "바다 위에 뜨는"), ("자동화 쇼핑쇼츠", "스카이베이 인피니티풀"),
        ("전체 과정은", "방 고르는 법은"), ("롱폼 영상에서", "다음 편에서"), ("▞ 숏템메이커", "▞ 스카이베이 경포"),
        ("숏템메이커", "스카이베이 경포"), ("채널에서 롱폼 보기 →", "다음 편 보기 →"), ("자세한 건 고정댓글", "후기 출처 · 여기어때")])

    # ④ 스타일 몽타주(1280×720, 사진 20장)
    d = WORK / "2026-10-22_숙소_style_world_montage"
    order = [11, 5, 6, 12, 1, 7, 15, 3, 13, 19, 4, 8, 10, 14, 16, 17, 18, 21, 22, 24]
    for k, no in enumerate(order):
        put(O(no), d / "img" / ("m%02d.png" % k))
    text(d / "index.html", [("Every Midjourney style is a world.", "스카이베이 경포, 스무 개의 장면.")])
    print("교체 끝")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
