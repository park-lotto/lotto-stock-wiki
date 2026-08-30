# -*- coding: utf-8 -*-
"""숏템메이커 1기 QR 생성 — 신청폼 / 카드결제 페이지"""
import os
import qrcode
from qrcode.constants import ERROR_CORRECT_H

TARGETS = {
    "숏템메이커_1기_신청폼_QR": "https://docs.google.com/forms/d/e/1FAIpQLScd2daWqtFnea1e_5y5ZKq6OkDPOeuw3qLg3tBinv6G2P4eCQ/viewform",
    "숏템메이커_1기_카드결제_QR": "https://stmaker.kr/surl/O/3068",
}

OUT_DIRS = [
    r"C:\Users\TheRose\Desktop\로또의 주식\out",
    r"C:\Users\TheRose\Desktop",
]


def main():
    for name, url in TARGETS.items():
        qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H,
                           box_size=14, border=3)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        for d in OUT_DIRS:
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, name + ".png")
            img.save(p)
            print(f"{p}  ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
