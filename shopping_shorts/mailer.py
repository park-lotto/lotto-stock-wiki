# -*- coding: utf-8 -*-
"""가입 안내 메일 — SMTP 한 곳(0순위-B: 보내는 판단을 여기서만 한다).

★설정이 없으면 **조용히 아무것도 안 한다**(no-op). 메일 실패로 가입이 막히면 안 된다.
  필요한 환경변수(/etc/shopping-shorts.env):
      SMTP_HOST   예) smtp.gmail.com
      SMTP_PORT   기본 587 (STARTTLS) · 465면 SSL로 붙는다
      SMTP_USER   보내는 계정
      SMTP_PASS   앱 비밀번호(지메일은 2단계인증 후 '앱 비밀번호')
      SMTP_FROM   표시용 발신주소(없으면 SMTP_USER)
  하나라도 비면 enabled()=False → 호출부는 그냥 넘어간다.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


def _cfg():
    return (os.environ.get("SMTP_HOST", "").strip(),
            int(os.environ.get("SMTP_PORT", "587") or 587),
            os.environ.get("SMTP_USER", "").strip(),
            os.environ.get("SMTP_PASS", "").strip())


def enabled():
    host, _port, user, pw = _cfg()
    return bool(host and user and pw)


def send(to_email, subject, html, text=None):
    """보냈으면 True. 설정 없음·실패는 False(예외를 밖으로 내보내지 않는다)."""
    if not (to_email or "").strip() or not enabled():
        return False
    host, port, user, pw = _cfg()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("SMTP_FROM", "").strip() or user
    msg["To"] = to_email
    msg.set_content(text or "HTML 메일입니다. HTML을 지원하는 앱에서 열어주세요.")
    msg.add_alternative(html, subtype="html")
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15,
                                  context=ssl.create_default_context()) as sv:
                sv.login(user, pw)
                sv.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as sv:
                sv.starttls(context=ssl.create_default_context())
                sv.login(user, pw)
                sv.send_message(msg)
        return True
    except Exception as e:
        import sys
        print(f"[mail] 발송 실패 {to_email}: {e}", file=sys.stderr)
        return False


def setup_notice_html(base_url, name=None):
    """가입 안내 메일 본문. 상세는 /setup 한 곳에서만 관리한다 —
    메일에 전문을 복사하면 두 벌이 되어 언젠가 어긋난다(0순위-B)."""
    who = (name or "").strip()
    hello = f"{who}님, " if who else ""
    url = base_url.rstrip("/") + "/setup"
    return f"""\
<div style="font-family:'Malgun Gothic',system-ui,sans-serif;font-size:16px;line-height:1.7;color:#1A1714;max-width:560px">
  <p style="font-size:13px;letter-spacing:.1em;color:#C2410C;font-weight:700;margin:0 0 8px">숏템메이커</p>
  <h2 style="margin:0 0 14px;font-size:24px">{hello}가입해 주셔서 감사합니다.</h2>
  <p style="margin:0 0 16px">가입과 동시에 <b>체험이 시작되고 포인트 50P가 자동으로</b> 들어갔습니다. 바로 써보실 수 있습니다.</p>
  <p style="margin:0 0 8px"><b>준비하실 것은 세 가지입니다.</b></p>
  <ol style="margin:0 0 20px;padding-left:20px">
    <li>채널 개설 + (원하시면) API 키 발급 — 키는 <b>안 받으셔도</b> 포인트로 쓰실 수 있습니다</li>
    <li><b>📥 담기 확장프로그램 설치</b> — 필수. PC 크롬·엣지에서 합니다</li>
    <li>캡컷 연동 — 원하는 분만</li>
  </ol>
  <p style="margin:0 0 24px">
    <a href="{url}" style="display:inline-block;background:#C2410C;color:#fff;text-decoration:none;
       padding:13px 22px;border-radius:10px;font-weight:700">설치와 준비 안내 보기</a>
  </p>
  <p style="margin:0;color:#8A8078;font-size:14px">열리지 않으면 주소창에 붙여넣어 주세요 — {url}</p>
</div>"""
