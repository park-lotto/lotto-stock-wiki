# -*- coding: utf-8 -*-
"""
스탁브레인 마스코트 — 시황부장 (확실히 보이는 일반 창 버전)
항상 위에 떠 있는 작은 창. [💬 대화 열기] 누르면 대시보드가 열린다.
실행:  pythonw dashboard/mascot.py
"""
import sys, os, time, threading, subprocess, urllib.request, webbrowser, math, glob, shutil
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "http://localhost:8090"
FACE = "🧑‍💼"
BG = "#16161a"
GOLD = "#d4af37"


def find_python():
    """subprocess 로 실행 가능한 '진짜' 파이썬 경로. 스토어 별칭(WindowsApps) 회피."""
    la = os.environ.get("LOCALAPPDATA", "")
    cands = (glob.glob(os.path.join(la, "Python", "pythoncore-*", "python.exe"))
             + glob.glob(os.path.join(la, "Programs", "Python", "Python3*", "python.exe")))
    for c in cands:
        if os.path.exists(c):
            return c
    # sys.executable 이 WindowsApps 별칭이 아니면 사용
    if sys.executable and "WindowsApps" not in sys.executable:
        return sys.executable
    # PATH 이름 해석 (cmd 처럼) — 최후 수단
    return shutil.which("python") or "python"


def server_up():
    try:
        urllib.request.urlopen(URL, timeout=1)
        return True
    except Exception:
        return False


open_btn = None  # 아래에서 버튼 생성 후 할당


def _set_btn(text, state):
    if open_btn is not None:
        try:
            open_btn.config(text=text, state=state)
        except Exception:
            pass


def open_dashboard():
    _set_btn("여는 중…", "disabled")

    def work():
        ok = True
        if not server_up():
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            py = find_python()
            try:
                subprocess.Popen([py, os.path.join(ROOT, "dashboard", "server.py")],
                                 cwd=ROOT, creationflags=flags)
            except Exception:
                ok = False
            up = False
            for _ in range(15):
                if server_up():
                    up = True
                    break
                time.sleep(1)
            ok = ok and up
        if ok:
            webbrowser.open(URL)
        # 메인 스레드에서 버튼 복구
        root.after(0, lambda: _set_btn("💬 대화 열기" if ok else "⚠ 실패 · 다시", "normal"))
    threading.Thread(target=work, daemon=True).start()


root = tk.Tk()
root.title("시황부장")
root.attributes("-topmost", True)
root.config(bg=BG)
root.resizable(False, False)

W, H = 210, 250
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{W}x{H}+{sw - W - 50}+{sh - H - 100}")

tk.Label(root, text="스탁브레인 시황부장", fg=GOLD, bg=BG,
         font=("Malgun Gothic", 11, "bold")).pack(pady=(16, 4))

# 캐릭터: assets/시황부장.png 있으면 그림, 없으면 이모지
_img = None
_png = os.path.join(ROOT, "dashboard", "assets", "시황부장.png")
if os.path.exists(_png):
    try:
        _img = tk.PhotoImage(file=_png)
        # 너무 크면 축소 (대략 130px 목표)
        while _img.width() > 150:
            _img = _img.subsample(2, 2)
    except Exception:
        _img = None
if _img is not None:
    face_lbl = tk.Label(root, image=_img, bg=BG)
    face_lbl.image = _img  # GC 방지
else:
    face_lbl = tk.Label(root, text=FACE, bg=BG, font=("Segoe UI Emoji", 60))
face_lbl.pack(pady=4)

open_btn = tk.Button(root, text="💬 대화 열기", command=open_dashboard,
                     bg=GOLD, fg="#0a0a0a", font=("Malgun Gothic", 11, "bold"),
                     relief="flat", padx=18, pady=8, cursor="hand2")
open_btn.pack(pady=10)

tk.Button(root, text="닫기", command=root.destroy,
          bg="#2a2a30", fg="#cfcdc7", font=("Malgun Gothic", 9),
          relief="flat", padx=12, pady=4, cursor="hand2").pack()

# 둥실 애니메이션
_t = {"v": 0}
def animate():
    _t["v"] += 1
    face_lbl.place_configure  # noop guard
    face_lbl.config(pady=int(4 + (math.sin(_t["v"] / 6.0) + 1) * 4))
    root.after(80, animate)
animate()

root.mainloop()
